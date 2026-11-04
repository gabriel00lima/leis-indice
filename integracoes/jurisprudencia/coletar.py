#!/usr/bin/env python3
"""Coleta jurisprudência para as normas de config.json e grava JSON estático em data/jurisprudencia/.

Fontes:
  stj      Espelhos de acórdãos do portal de dados abertos do STJ (CKAN). Cada acórdão traz
           "referenciasLegislativas" com os artigos citados, o que permite ligar decisão -> artigo.
  datajud  API pública do DataJud (CNJ). Só metadados: aqui, quantos processos há em cada assunto
           da Tabela Processual Unificada ligado à norma.

Uso:
  python coletar.py stj     --saida data/jurisprudencia --cache ~/.cache/juris [--amostra]
  python coletar.py datajud --saida data/jurisprudencia
  python coletar.py indice  --saida data/jurisprudencia

Só biblioteca padrão. Formato dos arquivos: README.md desta pasta.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
UA = "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"
TAMANHO_BLOCO = 100  # artigos por arquivo de detalhe (art. 1-99 no bloco 0, 100-199 no 1...)


def agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def carregar_config(caminho: Path | None = None) -> dict:
    return json.loads((caminho or AQUI / "config.json").read_text(encoding="utf-8"))


def http(url: str, dados: bytes | None = None, cabecalhos: dict | None = None,
         tentativas: int = 4, timeout: int = 120) -> bytes:
    espera = 5
    for i in range(tentativas):
        req = urllib.request.Request(url, data=dados, headers={"User-Agent": UA, **(cabecalhos or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or i == tentativas - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == tentativas - 1:
                raise
        time.sleep(espera)
        espera *= 2
    raise RuntimeError("inalcançável")


def gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if caminho.exists() and caminho.read_text(encoding="utf-8") == texto:
        return
    caminho.write_text(texto, encoding="utf-8")


# ---------------------------------------------------------------- STJ: interpretação

RE_ART = re.compile(r"\bART:0*(\d+)([A-Z])?\b")
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no"}


def artigos_da_referencia(ref: str) -> list[str]:
    """'LEG:FED LEI:013105 ANO:2015\\n ***** CPC-15 ...\\n ART:00787 ART:00803 INC:00001' -> ['art-787', 'art-803']."""
    linhas = ref.split("\n")[1:]  # a 1ª linha é o cabeçalho da norma
    vistos: list[str] = []
    for m in RE_ART.finditer("\n".join(linhas)):
        if m.group(1) == "0" * len(m.group(1)):
            continue
        a = "art-" + str(int(m.group(1))) + ("-" + m.group(2).lower() if m.group(2) else "")
        if a not in vistos:
            vistos.append(a)
    return vistos


def norma_da_referencia(ref: str, chaves: dict[str, str]) -> str | None:
    """Devolve o slug da norma acompanhada cuja chave ('LEI:010406 ANO:2002') abre a referência."""
    cab = ref.split("\n", 1)[0].strip()
    cab = re.sub(r"^LEG:\S+\s+", "", cab)
    for chave, slug in chaves.items():
        if cab == chave or cab.startswith(chave + " "):
            return slug
    return None


def titulo(s: str | None) -> str:
    if not s:
        return ""
    palavras = s.strip().lower().split()
    return " ".join(p if (i and p in _MINUSCULAS) else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def resumir(texto: str | None, limite: int) -> str:
    t = re.sub(r"\s+", " ", texto or "").strip()
    if len(t) <= limite:
        return t
    corte = t.rfind(" ", 0, limite)
    return t[: corte if corte > limite * 0.6 else limite].rstrip(" ,;.-") + "…"


def data_iso(aaaammdd: str | None) -> str:
    s = re.sub(r"\D", "", aaaammdd or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else ""


def numero_br(n: str | None) -> str:
    s = re.sub(r"\D", "", n or "")
    return f"{int(s):,}".replace(",", ".") if s else ""


def resumo_decisao(x: dict, tamanho_ementa: int) -> dict:
    reg = re.sub(r"\D", "", x.get("numeroRegistro") or "")
    d = {
        "p": " ".join(filter(None, [x.get("siglaClasse"), numero_br(x.get("numeroProcesso"))])),
        "o": titulo(x.get("nomeOrgaoJulgador")),
        "r": titulo(x.get("ministroRelator")),
        "j": data_iso(x.get("dataDecisao")),
        "e": resumir(x.get("ementa"), tamanho_ementa),
    }
    if x.get("tema"):
        d["t"] = "Tema repetitivo " + str(x["tema"]).strip()
    if reg:
        d["u"] = ("https://processo.stj.jus.br/processo/pesquisa/?tipoPesquisa=tipoPesquisaNumeroRegistro&termo="
                  + reg)
    return {k: v for k, v in d.items() if v}


def extrair(registros: list[dict], chaves: dict[str, str], tamanho_ementa: int) -> list[dict]:
    """Só os acórdãos que citam alguma norma acompanhada, já resumidos."""
    saida = []
    for x in registros:
        refs: dict[str, list[str]] = {}
        for ref in x.get("referenciasLegislativas") or []:
            slug = norma_da_referencia(ref, chaves)
            if not slug:
                continue
            arts = refs.setdefault(slug, [])
            for a in artigos_da_referencia(ref):
                if a not in arts:
                    arts.append(a)
        if refs:
            saida.append({"id": str(x.get("id")), "d": resumo_decisao(x, tamanho_ementa), "refs": refs})
    return saida


def bloco_do_artigo(art: str) -> int:
    m = re.match(r"art-(\d+)", art)
    return int(m.group(1)) // TAMANHO_BLOCO if m else 0


def agregar(extratos: list[dict], leis: list[dict], por_artigo: int) -> dict[str, dict]:
    """extratos -> {slug: {"resumo": {...}, "blocos": {n: {...}}}}."""
    vistos: dict[str, dict] = {}
    for e in extratos:  # o mesmo acórdão pode vir em dois arquivos; fica a última versão
        vistos[e["id"]] = e
    ordem = sorted(vistos.values(), key=lambda e: (e["d"].get("j", ""), e["id"]), reverse=True)

    saida = {}
    for lei in leis:
        slug = lei["slug"]
        contagem: dict[str, int] = {}
        recentes: dict[str, list[str]] = {}
        total = 0
        datas = []
        for e in ordem:
            arts = e["refs"].get(slug)
            if arts is None:
                continue
            total += 1
            if e["d"].get("j"):
                datas.append(e["d"]["j"])
            for a in arts or ["sem-artigo"]:
                contagem[a] = contagem.get(a, 0) + 1
                lista = recentes.setdefault(a, [])
                if len(lista) < por_artigo:
                    lista.append(e["id"])
        blocos: dict[int, dict] = {}
        for a, ids in recentes.items():
            b = blocos.setdefault(-1 if a == "sem-artigo" else bloco_do_artigo(a), {"artigos": {}, "decisoes": {}})
            b["artigos"][a] = ids
            for i in ids:
                b["decisoes"][i] = vistos[i]["d"]
        artigos = {a: n for a, n in contagem.items() if a != "sem-artigo"}
        saida[slug] = {
            "resumo": {
                "lei": lei["id"], "nome": lei.get("nome", ""), "total": total,
                "periodo": [min(datas), max(datas)] if datas else None,
                "artigos": artigos, "sem_artigo": contagem.get("sem-artigo", 0),
                "bloco": TAMANHO_BLOCO, "por_artigo": por_artigo,
            },
            "blocos": blocos,
        }
    return saida


# ---------------------------------------------------------------- STJ: coleta

def recursos_stj(cfg: dict) -> list[dict]:
    base = cfg["stj"]["ckan"]
    pacotes = json.loads(http(base + "package_list"))["result"]
    pacotes = [p for p in pacotes if p.startswith(cfg["stj"]["prefixo_pacotes"])]
    recursos = []
    for p in sorted(pacotes):
        info = json.loads(http(base + "package_show?id=" + p))["result"]
        for r in info["resources"]:
            if (r.get("format") or "").lower() == "json" and re.match(r"\d{8}\.json$", r.get("name") or ""):
                recursos.append({"pacote": p, "id": r["id"], "nome": r["name"], "url": r["url"],
                                 "versao": r.get("last_modified") or r.get("metadata_modified") or ""})
    return recursos


def coletar_stj(cfg: dict, saida: Path, cache: Path, amostra: bool = False) -> None:
    leis = [l for l in cfg["leis"] if l.get("stj")]
    chaves = {l["stj"]: l["slug"] for l in leis}
    tam = cfg["stj"].get("tamanho_ementa", 260)
    assinatura = hashlib.sha1(json.dumps([sorted(chaves.items()), tam]).encode()).hexdigest()[:12]

    recursos = recursos_stj(cfg)
    print(f"STJ: {len(recursos)} arquivos mensais em {len({r['pacote'] for r in recursos})} órgãos julgadores")
    if amostra:
        recursos = recursos[-2:]
    cache.mkdir(parents=True, exist_ok=True)

    extratos: list[dict] = []
    baixados = 0
    for i, r in enumerate(recursos, 1):
        arq = cache / f"{r['id']}.json.gz"
        dados = None
        if arq.exists():
            try:
                dados = json.loads(gzip.decompress(arq.read_bytes()))
                if dados.get("versao") != r["versao"] or dados.get("assinatura") != assinatura:
                    dados = None
            except (OSError, ValueError):
                dados = None
        if dados is None:
            try:
                registros = json.loads(http(r["url"], timeout=300))
            except Exception as e:  # um arquivo ruim não derruba a coleta
                print(f"  aviso: {r['pacote']}/{r['nome']}: {e}", file=sys.stderr)
                continue
            dados = {"versao": r["versao"], "assinatura": assinatura,
                     "itens": extrair(registros, chaves, tam)}
            arq.write_bytes(gzip.compress(json.dumps(dados, ensure_ascii=False).encode()))
            baixados += 1
            print(f"  [{i}/{len(recursos)}] {r['pacote']}/{r['nome']}: {len(registros)} acórdãos, "
                  f"{len(dados['itens'])} citam normas acompanhadas", flush=True)
        extratos.extend(dados["itens"])
    print(f"STJ: {baixados} arquivos baixados, {len(recursos) - baixados} do cache; {len(extratos)} citações")

    agregado = agregar(extratos, leis, cfg["stj"].get("decisoes_por_artigo", 5))
    destino = saida / "stj"
    for slug, a in agregado.items():
        gravar_json(destino / f"{slug}.json", a["resumo"])
        pasta = destino / slug
        novos = {f"{'sem' if n == -1 else n}.json" for n in a["blocos"]}
        if pasta.exists():
            for velho in pasta.glob("*.json"):
                if velho.name not in novos:
                    velho.unlink()
        for n, b in a["blocos"].items():
            gravar_json(pasta / f"{'sem' if n == -1 else n}.json", b)
        r = a["resumo"]
        print(f"  {slug}: {r['total']} acórdãos, {len(r['artigos'])} artigos citados")
    gravar_json(saida / "stj" / "_fonte.json", {"gerado_em": agora(), "arquivos": len(recursos),
                                                "amostra": amostra})


# ---------------------------------------------------------------- DataJud

RE_CHAVE = re.compile(r"APIKey\s+([A-Za-z0-9+/]{20,}={0,2})")


def chave_datajud(cfg: dict) -> tuple[str, str]:
    """Chave pública: segredo DATAJUD_API_KEY > página oficial da wiki > reserva do config."""
    if os.environ.get("DATAJUD_API_KEY"):
        return os.environ["DATAJUD_API_KEY"].strip(), "segredo"
    try:
        pagina = http(cfg["datajud"]["pagina_da_chave"], tentativas=2).decode("utf-8", "replace")
        chave = extrair_chave(pagina)
        if chave:
            return chave, "wiki"
    except Exception as e:
        print(f"  aviso: não li a chave na wiki do DataJud: {e}", file=sys.stderr)
    return cfg["datajud"]["chave_reserva"], "reserva"


def extrair_chave(pagina_html: str) -> str | None:
    texto = html.unescape(re.sub(r"<[^>]+>", " ", pagina_html)).replace("[Chave Pública]", " ")
    m = RE_CHAVE.search(texto)
    return m.group(1) if m else None


def normalizar(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def consultar(cfg: dict, chave: str, tribunal: str, corpo: dict, tentativas: int = 6) -> dict:
    """Busca no Elasticsearch do DataJud. Só aceita respostas sem shard falho (senão os números saem baixos)."""
    url = cfg["datajud"]["url"].format(tribunal=tribunal)
    cab = {"Authorization": "APIKey " + chave, "Content-Type": "application/json"}
    espera = 15
    ultimo = "sem resposta"
    for _ in range(tentativas):
        try:
            r = json.loads(http(url, json.dumps(corpo).encode(), cab, tentativas=2, timeout=120))
            if not r.get("_shards", {}).get("failed"):
                return r
            ultimo = f"{r['_shards']['failed']} shard(s) falharam"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise
            ultimo = f"HTTP {e.code}"
        except Exception as e:
            ultimo = repr(e)
        print(f"  DataJud {tribunal}: {ultimo}; nova tentativa em {espera}s", file=sys.stderr, flush=True)
        time.sleep(espera)
        espera = min(espera * 2, 120)
    raise RuntimeError(f"DataJud {tribunal}: {ultimo}")


def coletar_datajud(cfg: dict, saida: Path) -> None:
    leis = [l for l in cfg["leis"] if l.get("datajud")]
    chave, origem = chave_datajud(cfg)
    print(f"DataJud: chave lida de: {origem}")
    por_tribunal: dict[str, list[dict]] = {}
    for l in leis:
        por_tribunal.setdefault(l["datajud"]["tribunal"], []).append(l)

    falhas = 0
    for tribunal, grupo in por_tribunal.items():
        try:
            r = consultar(cfg, chave, tribunal, {
                "size": 0, "track_total_hits": True,
                "aggs": {"a": {"terms": {"field": "assuntos.nome.keyword", "size": 3000}}},
            })
        except Exception as e:
            print(f"  aviso: {e}; mantidos os arquivos anteriores de {tribunal}", file=sys.stderr)
            falhas += 1
            continue
        total_tribunal = r["hits"]["total"]["value"]
        nomes = {}
        for b in r["aggregations"]["a"]["buckets"]:
            nomes.setdefault(normalizar(b["key"]), []).append((b["key"], b["doc_count"]))
        for l in grupo:
            assuntos = []
            chaves_reais = []
            for nome in l["datajud"]["assuntos"]:
                achados = nomes.get(normalizar(nome))
                if not achados:
                    print(f"  {l['slug']}: assunto não encontrado no {tribunal.upper()}: {nome}")
                    continue
                chaves_reais += [k for k, _ in achados]
                assuntos.append({"nome": achados[0][0].strip(), "total": sum(n for _, n in achados)})
            if not assuntos:
                continue
            try:
                soma = consultar(cfg, chave, tribunal, {
                    "size": 0, "track_total_hits": True,
                    "query": {"terms": {"assuntos.nome.keyword": chaves_reais}},
                })["hits"]["total"]["value"]
            except Exception as e:
                print(f"  aviso: {l['slug']}: {e}; mantido o arquivo anterior", file=sys.stderr)
                falhas += 1
                continue
            assuntos.sort(key=lambda a: -a["total"])
            gravar_json(saida / "datajud" / f"{l['slug']}.json", {
                "lei": l["id"], "gerado_em": agora()[:10],
                "tribunais": [{"sigla": tribunal.upper(), "total": soma, "total_tribunal": total_tribunal}],
                "assuntos": assuntos,
            })
            print(f"  {l['slug']}: {soma} processos no {tribunal.upper()} em {len(assuntos)} assuntos")
        time.sleep(3)
    if falhas == len(por_tribunal) and falhas:
        print("DataJud indisponível agora; nada foi alterado.", file=sys.stderr)


# ---------------------------------------------------------------- índice

def gerar_indice(cfg: dict, saida: Path) -> None:
    leis = {}
    for l in cfg["leis"]:
        item = {"nome": l.get("nome", ""), "slug": l["slug"]}
        stj = saida / "stj" / f"{l['slug']}.json"
        if stj.exists():
            r = json.loads(stj.read_text(encoding="utf-8"))
            item.update(stj=f"stj/{l['slug']}.json", total=r["total"])
        if (saida / "datajud" / f"{l['slug']}.json").exists():
            item["datajud"] = f"datajud/{l['slug']}.json"
        if len(item) > 2:
            leis[l["id"]] = item
    fonte = saida / "stj" / "_fonte.json"
    anterior = saida / "indice.json"
    novo = {"leis": leis}
    if fonte.exists():
        novo["stj_gerado_em"] = json.loads(fonte.read_text(encoding="utf-8"))["gerado_em"][:10]
    # Só troca a data quando algo mudou, para não gerar commit vazio.
    if anterior.exists():
        velho = json.loads(anterior.read_text(encoding="utf-8"))
        if {k: v for k, v in velho.items() if k != "gerado_em"} == novo:
            return
    novo["gerado_em"] = agora()[:10]
    gravar_json(anterior, novo)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonte", choices=["stj", "datajud", "indice"])
    ap.add_argument("--saida", type=Path, default=Path("data/jurisprudencia"))
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "juris-stj")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--amostra", action="store_true", help="STJ: só os 2 últimos arquivos (teste rápido)")
    a = ap.parse_args(argv)
    cfg = carregar_config(a.config)
    if a.fonte == "stj":
        coletar_stj(cfg, a.saida, a.cache.expanduser(), a.amostra)
    elif a.fonte == "datajud":
        coletar_datajud(cfg, a.saida)
    gerar_indice(cfg, a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
