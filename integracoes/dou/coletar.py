#!/usr/bin/env python3
"""Coleta os atos normativos federais publicados no Diário Oficial da União.

Fonte: dados abertos da Imprensa Nacional (in.gov.br, "Base de Dados"). Cada mês
tem um ZIP por seção do DOU com um XML por matéria. Usamos só a Seção 1 (atos
normativos), filtramos leis, leis complementares, emendas constitucionais,
medidas provisórias, decretos e decretos legislativos numerados, e guardamos em
data/dou/ só metadados pequenos ligados às normas do acervo ctresb/leis.
Os ZIPs (dezenas de MB por mês) são baixados para uma pasta temporária e apagados.

Uso típico (é o que a GitHub Action faz):

    git clone --filter=blob:none --no-checkout --depth 1 \\
        https://github.com/ctresb/leis.git /tmp/leis
    python integracoes/dou/coletar.py --acervo /tmp/leis --saida data/dou

Com --zip ARQUIVO.zip --mes AAAA-MM processa um ZIP já baixado (testes).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "indice"))
import extrator  # noqa: E402
from construir import Resolvedor, listar_federal  # noqa: E402

# Mudar quando a extração mudar: força reprocessar todos os meses.
VERSAO = 1
URL_BASE = "https://www.in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados"
LICENCA = "Dados abertos da Imprensa Nacional (CC0)"
# Primeiro mês coletado.
DESDE = "2025-01"
# Meses baixados por execução (cada um tem de 50 a 150 MB de ZIP).
MAX_MESES = 8
USER_AGENT = "leis-indice (+https://github.com/gabriel00lima/leis-indice)"
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# (expressão no início do "Identifica", prefixo do acervo, rótulo)
# Ordem: formas mais longas antes.
TIPOS = [
    ("EMENDA CONSTITUCIONAL", "emc", "Emenda Constitucional"),
    ("LEI COMPLEMENTAR", "lcp", "Lei Complementar"),
    ("LEI DELEGADA", "ldl", "Lei Delegada"),
    ("LEI", "lei", "Lei"),
    ("MEDIDA PROVISORIA", "mpv", "Medida Provisória"),
    ("DECRETO LEGISLATIVO", "dlg", "Decreto Legislativo"),
    ("DECRETO", "dec", "Decreto"),
]
_MESES_RE = "|".join(unicodedata.normalize("NFKD", m).encode("ascii", "ignore").decode().upper()
                     for m in MESES)
IDENTIFICA_RE = re.compile(
    r"^(?P<tipo>" + "|".join(t for t, _, _ in TIPOS) + r")\b\W*"
    r"N[O\W]{0,3}\s*(?P<num>\d{1,3}(?:\.\d{3})+|\d+)(?:-(?P<reed>\d+))?"
    r"\s*,?\s*DE\s+(?P<dia>\d{1,2})[O\W]{0,2}\s*DE\s+(?P<mes>" + _MESES_RE + r")\s+DE\s+(?P<ano>\d{4})"
)
ZIP_DO_MES = r"S01{mm}{aaaa}[^\"'/?<>]*\.zip"

# Listas no plural: "Leis nºs 8.078, de 11 de setembro de 1990, e 10.406, de 2002".
PLURAL_RE = re.compile(
    r"(?P<tipo>Leis\s+Complementares|Leis|Decretos-Leis|Decretos|Medidas\s+Provis[óo]rias)"
    r"\s+n(?:[º°o]s?|os|\.?\s*os)\.?\s*",
    re.IGNORECASE,
)
_ITEM_PLURAL = re.compile(
    r"(?P<num>\d{1,3}(?:\.\d{3})+|\d+)(?:-(?P<reed>\d{1,2}))?"
    r"(?:,?\s+de\s+(?:\d{1,2}[º°o]?\s+de\s+[a-zç]+\s+de\s+)?(?P<ano>\d{4}))?",
    re.IGNORECASE,
)
_SEP_PLURAL = re.compile(r"\s*(?:,\s*e\s+|,\s*|\s+e\s+)")
PREFIXO_PLURAL = {"leis complementares": "lcp", "leis": "lei", "decretos-leis": "del",
                  "decretos": "dec", "medidas provisórias": "mpv", "medidas provisorias": "mpv"}

TAG_RE = re.compile(r"<[^>]+>")
PARAGRAFO_RE = re.compile(r"</p>|<br\s*/?>", re.IGNORECASE)
EMENTA_HTML = re.compile(r'<p[^>]*class="ementa"[^>]*>(.*?)</p>', re.IGNORECASE | re.DOTALL)


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def texto_puro(trecho: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", trecho or ""))).strip()


def paragrafos(texto_html: str) -> list[str]:
    partes = PARAGRAFO_RE.split(texto_html or "")
    return [p for p in (texto_puro(x) for x in partes) if p]


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
def abrir(url: str, tentativas: int = 4, tempo: int = 60):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            return urllib.request.urlopen(req, timeout=tempo)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                raise
            ultimo = e
        except OSError as e:
            ultimo = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"falha ao abrir {url}: {ultimo}")


def links_do_mes(ano: int, mes: int) -> list[tuple[str, str]]:
    """[(nome do ZIP, URL)] da Seção 1 do mês, lidos da página da base de dados.

    O link tem um identificador de pasta que muda a cada mês, então não dá para
    montar a URL: é preciso ler a página. Lista vazia se o mês ainda não saiu."""
    url = URL_BASE + "?" + urllib.parse.urlencode({"ano": ano, "mes": MESES[mes - 1]})
    try:
        pagina = abrir(url).read().decode("utf-8", "replace")
    except urllib.error.HTTPError:
        return []
    padrao = re.compile(
        r"href=\"(?P<url>[^\"]*/documents/[^\"]*?/(?P<nome>"
        + ZIP_DO_MES.format(mm=f"{mes:02d}", aaaa=ano) + r"))[^\"]*\"",
        re.IGNORECASE,
    )
    vistos: dict[str, str] = {}
    for m in padrao.finditer(pagina):
        link = html.unescape(m.group(0)[6:-1])
        link = urllib.parse.urljoin("https://www.in.gov.br/", link)
        vistos.setdefault(m.group("nome"), link)
    return sorted(vistos.items())


def baixar(url: str, destino: Path) -> int:
    with abrir(url, tempo=300) as r, open(destino, "wb") as f:
        total = 0
        while bloco := r.read(1 << 20):
            f.write(bloco)
            total += len(bloco)
    if not zipfile.is_zipfile(destino):
        raise RuntimeError(f"{url} não devolveu um ZIP")
    return total


# ---------------------------------------------------------------------------
# Leitura dos XML
# ---------------------------------------------------------------------------
def materias(caminho_zip) -> "iter[ET.Element]":
    """Um <article> por XML do ZIP (aceita ZIP dentro de ZIP)."""
    with zipfile.ZipFile(caminho_zip) as z:
        for nome in z.namelist():
            baixo = nome.lower()
            if baixo.endswith(".zip"):
                yield from materias(io.BytesIO(z.read(nome)))
                continue
            if not baixo.endswith(".xml"):
                continue
            try:
                raiz = ET.fromstring(z.read(nome).decode("utf-8-sig", "replace"))
            except ET.ParseError:
                continue
            artigo = raiz if raiz.tag == "article" else raiz.find(".//article")
            if artigo is not None:
                yield artigo


def _data_br(s: str) -> str | None:
    try:
        return dt.datetime.strptime((s or "").strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def identificar(identifica: str):
    """'LEI Nº 15.123, DE 10 DE MARÇO DE 2025' -> (prefixo, rótulo, numero, data)."""
    m = IDENTIFICA_RE.match(_sem_acento(texto_puro(identifica)).upper())
    if not m:
        return None
    prefixo, rotulo = next((p, r) for t, p, r in TIPOS if t == m.group("tipo"))
    numero = m.group("num").replace(".", "").lstrip("0") or "0"
    if m.group("reed"):
        numero += "-" + m.group("reed").lstrip("0")
    mes = _MESES_RE.split("|").index(m.group("mes")) + 1
    try:
        data = dt.date(int(m.group("ano")), mes, int(m.group("dia"))).isoformat()
    except ValueError:
        return None
    return prefixo, rotulo, numero, data


def referencias_plurais(texto: str, ano_citante: int | None):
    """Referências em listas no plural, que o extrator do índice não pega."""
    refs = []
    for m in PLURAL_RE.finditer(texto):
        prefixo = PREFIXO_PLURAL.get(re.sub(r"\s+", " ", m.group("tipo").lower()))
        pos = m.end()
        while prefixo:
            item = _ITEM_PLURAL.match(texto, pos)
            if not item:
                break
            num = item.group("num").replace(".", "").lstrip("0") or "0"
            if item.group("reed"):
                num += "-" + item.group("reed")
            ano = int(item.group("ano")) if item.group("ano") else None
            refs.append((prefixo, num, ano, item.start(), item.end()))
            sep = _SEP_PLURAL.match(texto, item.end())
            if not sep or not re.match(r"\d", texto[sep.end():sep.end() + 1]):
                break
            pos = sep.end()
    return refs


def referencias(texto: str, data: str) -> list[tuple[str, str, int | None]]:
    ano = int(data[:4]) if data else None
    refs = [(p, n, a) for p, n, a, _, _ in extrator.referencias_em(texto, ano, data or "")]
    refs += [(p, n, a) for p, n, a, _, _ in referencias_plurais(texto, ano)]
    return refs


def ato_de(artigo: ET.Element) -> dict | None:
    """Metadados de um ato normativo, ou None se a matéria não for um."""
    a = artigo.attrib
    if not (a.get("pubName") or "").upper().startswith("DO1"):
        return None
    corpo = artigo.find("body")
    if corpo is None:
        return None
    identifica = texto_puro(corpo.findtext("Identifica") or "")
    achado = identificar(identifica)
    if not achado:
        return None
    prefixo, rotulo, numero, data_ato = achado
    texto_html = corpo.findtext("Texto") or ""
    ementa = texto_puro(corpo.findtext("Ementa") or "")
    if not ementa:
        m = EMENTA_HTML.search(texto_html)
        ementa = texto_puro(m.group(1)) if m else ""
    url = (a.get("pdfPage") or "").strip().replace("http://", "https://", 1)
    pagina = a.get("numberPage") or ""
    return {
        "id": a.get("idMateria") or a.get("id") or "",
        "data": _data_br(a.get("pubDate", "")),
        "secao": a.get("pubName", "").upper(),
        "edicao": (a.get("editionNumber") or "").strip(),
        "pagina": int(pagina) if pagina.isdigit() else None,
        "tipo": rotulo,
        "prefixo": prefixo,
        "numero": numero,
        "data_ato": data_ato,
        "identifica": identifica,
        "ementa": ementa[:600],
        "orgao": (a.get("artCategory") or "").strip(),
        "url": url,
        "_paragrafos": paragrafos(texto_html),
    }


def ligar(ato: dict, resolvedor: Resolvedor, existentes: set[str]) -> dict:
    """Resolve a própria norma no acervo e as normas alteradas, revogadas e citadas."""
    data = ato["data_ato"]
    proprio = resolvedor.resolver(ato["prefixo"], ato["numero"], int(data[:4]), data)
    ato["norma"] = proprio if proprio in existentes else None

    # Uma relação por norma alvo; a mais forte vence (revoga > altera > cita).
    melhor: dict[str, str] = {}
    peso = {"cita": 0, "altera": 1, "revoga": 2}

    def add(tipo: str, refs):
        for p, n, a in refs:
            alvo = resolvedor.resolver(p, n, a, data)
            if alvo in existentes and alvo != proprio and peso[tipo] >= peso.get(melhor.get(alvo), -1):
                melhor[alvo] = tipo

    ementa = ato["ementa"]
    if re.match(r"\s*(altera|acrescenta|modifica|d[áa] nova reda)", ementa, re.IGNORECASE):
        add("altera", referencias(ementa, data))
    elif re.match(r"\s*revoga", ementa, re.IGNORECASE):
        add("revoga", referencias(ementa, data))
    for par in ato.pop("_paragrafos"):
        if extrator.REVOGA_PARAGRAFO.search(par):
            add("revoga", referencias(par, data))
        elif extrator.ALTERA_PARAGRAFO.search(par):
            add("altera", referencias(par, data))
        else:
            add("cita", referencias(par, data))
    for tipo in peso:
        ato[tipo] = sorted(a for a, t in melhor.items() if t == tipo)
    return ato


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
def json_linhas(lista: list) -> str:
    return "[\n" + ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in lista) + "\n]\n"


def escrever(caminho: Path, conteudo: str) -> bool:
    if caminho.exists() and caminho.read_text(encoding="utf-8") == conteudo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return True


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def processar_zips(zips: list[Path], resolvedor: Resolvedor, existentes: set[str]) -> list[dict]:
    atos: dict[str, dict] = {}
    for z in zips:
        for artigo in materias(z):
            ato = ato_de(artigo)
            if not ato:
                continue
            ligar(ato, resolvedor, existentes)
            chave = ato["id"] or f"{ato['prefixo']}-{ato['numero']}-{ato['data']}"
            atos[chave] = ato
    # Mesmo ato republicado (retificação/republicação): fica o mais recente.
    unicos: dict[tuple, dict] = {}
    for ato in sorted(atos.values(), key=lambda x: (x["data"] or "", x["id"])):
        unicos[(ato["prefixo"], ato["numero"], ato["data_ato"])] = ato
    return sorted(unicos.values(), key=lambda x: (x["data"] or "", x["prefixo"], x["numero"]), reverse=True)


def meses_ate(desde: str, hoje: dt.date) -> list[str]:
    ano, mes = map(int, desde.split("-"))
    saida = []
    while (ano, mes) <= (hoje.year, hoje.month):
        saida.append(f"{ano}-{mes:02d}")
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return saida


def carregar_resolvedor(acervo: Path | None, data_dir: Path) -> tuple[Resolvedor, set[str]]:
    """Com o clone do acervo, resolve contra todas as normas federais (decretos e MPs
    inclusive); sem ele, só contra o índice em data/index/."""
    if acervo:
        caminhos = listar_federal(acervo) + ["constituicao.md"]
    else:
        caminhos = ["constituicao.md"]
        for parte in sorted((data_dir / "index").glob("*.json")):
            caminhos += [e["path"] for e in ler_json(parte, [])]
    existentes = {c[:-3] for c in caminhos}
    return Resolvedor(caminhos), existentes


def gerar_derivados(saida: Path, data_dir: Path) -> None:
    """index.json (manifesto), por_norma.json e recentes.json a partir dos meses."""
    estado = ler_json(saida / "estado.json", {})
    meses = []
    por_norma: dict[str, list] = defaultdict(list)
    todos = []
    for arq in sorted((saida / "meses").glob("*.json"), reverse=True):
        atos = ler_json(arq, [])
        mes = arq.stem
        meses.append({
            "mes": mes,
            "arquivo": f"dou/meses/{arq.name}",
            "total": len(atos),
            "por_tipo": dict(sorted(Counter(a["tipo"] for a in atos).items())),
            "zips": sorted(estado.get("meses", {}).get(mes, {}).get("zips", [])),
        })
        for a in atos:
            resumo = {"mes": mes, "ato": a["id"], "data": a["data"], "identifica": a["identifica"],
                      "url": a["url"], "norma": a["norma"]}
            if a["norma"]:
                por_norma[a["norma"]].append({**resumo, "rel": "publicacao"})
            for rel in ("altera", "revoga"):
                for alvo in a[rel]:
                    por_norma[alvo].append({**resumo, "rel": rel})
            todos.append(a)
    for lista in por_norma.values():
        lista.sort(key=lambda x: (x["data"] or "", x["ato"]), reverse=True)

    total = sum(m["total"] for m in meses)
    conteudo_por_norma = "{\n" + ",\n".join(
        f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
        for k, v in sorted(por_norma.items())
    ) + "\n}\n"
    mudou = escrever(saida / "por_norma.json", conteudo_por_norma)
    mudou |= escrever(saida / "recentes.json", json_linhas(todos[:150]))
    manifesto_antigo = ler_json(saida / "index.json", {})
    manifesto = {
        "versao": VERSAO,
        "gerado_em": manifesto_antigo.get("gerado_em"),
        "fonte": {"nome": "Diário Oficial da União, Seção 1", "url": URL_BASE, "licenca": LICENCA},
        "tipos": [r for _, _, r in TIPOS],
        "total": total,
        "meses": meses,
        "arquivos": {"recentes": "dou/recentes.json", "por_norma": "dou/por_norma.json",
                     "conferencia": "dou/conferencia.json"},
    }
    comparavel = {k: v for k, v in manifesto.items() if k != "gerado_em"}
    antigo_comparavel = {k: v for k, v in manifesto_antigo.items() if k != "gerado_em"}
    if mudou or comparavel != antigo_comparavel or not manifesto["gerado_em"]:
        manifesto["gerado_em"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    escrever(saida / "index.json", json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")


def coletar(args) -> int:
    saida: Path = args.saida
    data_dir = saida.parent
    resolvedor, existentes = carregar_resolvedor(args.acervo, data_dir)
    estado = ler_json(saida / "estado.json", {})
    if estado.get("versao") != VERSAO:
        estado = {"versao": VERSAO, "meses": {}}
    estado.setdefault("meses", {})

    if args.zip:
        mes = args.mes or dt.date.today().strftime("%Y-%m")
        atos = processar_zips(args.zip, resolvedor, existentes)
        escrever(saida / "meses" / f"{mes}.json", json_linhas(atos))
        estado["meses"][mes] = {"zips": sorted(z.name for z in args.zip),
                                "total": len(atos), "processado_em": dt.date.today().isoformat()}
        print(f"{mes}: {len(atos)} atos")
    else:
        hoje = dt.date.today()
        candidatos = [args.mes] if args.mes else list(reversed(meses_ate(args.desde, hoje)))
        baixados = 0
        for mes in candidatos:
            if baixados >= args.max_meses:
                print(f"limite de {args.max_meses} meses por execução; o resto fica para a próxima")
                break
            ano, m = map(int, mes.split("-"))
            links = links_do_mes(ano, m)
            if not links:
                print(f"{mes}: ainda não publicado na base de dados")
                continue
            nomes = sorted(n for n, _ in links)
            if estado["meses"].get(mes, {}).get("zips") == nomes and not args.mes:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                zips = []
                for nome, url in links:
                    destino = Path(tmp) / nome
                    tamanho = baixar(url, destino)
                    print(f"{mes}: {nome} ({tamanho / 1e6:.0f} MB)")
                    zips.append(destino)
                atos = processar_zips(zips, resolvedor, existentes)
            if not atos:
                print(f"::warning::{mes}: nenhum ato normativo encontrado nos ZIPs")
                continue
            escrever(saida / "meses" / f"{mes}.json", json_linhas(atos))
            estado["meses"][mes] = {"zips": nomes, "total": len(atos),
                                    "processado_em": hoje.isoformat()}
            print(f"{mes}: {len(atos)} atos ({dict(Counter(a['tipo'] for a in atos))})")
            baixados += 1

    estado["meses"] = dict(sorted(estado["meses"].items()))
    escrever(saida / "estado.json", json.dumps(estado, ensure_ascii=False, indent=2) + "\n")
    gerar_derivados(saida, data_dir)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", type=Path, default=RAIZ / "data" / "dou")
    p.add_argument("--acervo", type=Path, help="clone blobless do ctresb/leis (resolve decretos e MPs)")
    p.add_argument("--desde", default=DESDE, help="primeiro mês (AAAA-MM)")
    p.add_argument("--mes", help="processar só este mês (AAAA-MM), mesmo se já processado")
    p.add_argument("--max-meses", type=int, default=MAX_MESES)
    p.add_argument("--zip", type=Path, nargs="+", help="processar ZIP(s) locais em vez de baixar")
    args = p.parse_args(argv)
    return coletar(args)


if __name__ == "__main__":
    sys.exit(main())
