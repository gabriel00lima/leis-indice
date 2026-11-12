#!/usr/bin/env python3
"""Coleta, do normas.leg.br, a estrutura artigo por artigo das normas do índice.

O normas.leg.br (Senado/Câmara) publica cada norma por URN em
    https://normas.leg.br/api/public/normas?urn=<urn>&tipo_documento=maior-detalhe
como JSON-LD. Para parte das normas (CF, Código Civil, LGPD, Lei 14.133, ...) a
resposta traz a árvore completa de dispositivos (hasPart), com texto e uma URN
para cada artigo, inciso e parágrafo. Para outras (CDC, Código Penal, muitos
decretos) traz só metadados, e algumas URNs nem existem lá.

A API não manda cabeçalhos CORS, então o navegador não consegue ler direto.
Por isso este script roda no GitHub Actions e grava o necessário em
data/normas-leg/:

  <id>.json     uma por norma com estrutura no normas.leg.br:
                  urn, versao, artigos {"art-5": "art5", "art-103-b": "art103-2,emc-45-..."}
                  e, só quando precisa, texto_md (o texto montado em Markdown).
  estado.json   controle do coletor (o site não lê): quando cada id foi
                consultado e o que veio.

texto_md é gravado só para as normas da lista de prioridade (normas_leg/prioridade.txt)
e para as que o acervo ctresb/leis traz sem texto (arquivo curto e sem nenhum
"Art."), que é quando o site precisa de um texto alternativo. Das demais guarda
só o mapa de artigos, que o site usa para o link "ver no normas.leg.br" de cada
artigo.

Uso:
  python normas_leg/coletar.py --data data [--fonte /tmp/leis] [--minutos 25]

--fonte é um clone do ctresb/leis feito com --filter=blob:limit=1500: os
arquivos pequenos vêm junto e servem para achar as normas sem texto.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://normas.leg.br/api/public/normas"
SITE = "https://normas.leg.br/?urn="
VERSAO = 1                 # mude quando o formato de <id>.json mudar: força nova coleta
REVISITAR_DIAS = 90        # de quanto em quanto tempo consultar de novo uma norma
REVISITAR_PRIORIDADE = 7   # idem para a lista de prioridade e as sem texto
PAUSA = 0.3                # segundos entre consultas, para não sobrecarregar o serviço
LIMITE_SEM_TEXTO = 1500    # bytes: arquivos do ctresb menores que isso são candidatos a "sem texto"

RAIZ = Path(__file__).resolve().parent
TIPO = re.compile(r"tipo\.dispositivo:([a-z.]+)")


# ---------------------------------------------------------------------------
# rede
# ---------------------------------------------------------------------------
def baixar_json(urn: str, tentativas: int = 4) -> dict | None:
    """JSON-LD da norma, ou None se o normas.leg.br não conhece a URN."""
    url = f"{API}?urn={urn}&tipo_documento=maior-detalhe"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "leis-indice (+https://github.com/gabriel00lima/leis-indice)",
    })
    erro: Exception | None = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                corpo = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    corpo = gzip.decompress(corpo)
            if not corpo.strip():
                return None
            d = json.loads(corpo)
            # URN desconhecida: a API responde 200 com {"urn": "..."} e nada mais.
            return d if "@type" in d else None
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            erro = e
        except Exception as e:  # IncompleteRead, timeout, JSON cortado...
            erro = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{urn}: {erro}")


# ---------------------------------------------------------------------------
# árvore de dispositivos -> artigos e Markdown
# ---------------------------------------------------------------------------
def lista(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def versao_atual(no: dict) -> dict:
    """workExample pode ser uma lista (uma por versão): fica com a mais recente."""
    ves = [v for v in lista(no.get("workExample")) if isinstance(v, dict)]
    if not ves:
        return {}
    return max(ves, key=lambda v: str(v.get("legislationDate") or ""))


def tipo_de(no: dict) -> str:
    t = no.get("legislationType")
    m = TIPO.search(t.get("@id", "") if isinstance(t, dict) else str(t or ""))
    return m.group(1) if m else ""


def limpar(txt: str | None) -> str:
    """Tira as marcas LexML (<span xlink:href>, <lx:p>...) e deixa só o texto."""
    if not txt:
        return ""
    txt = re.sub(r"</?(?:lx:)?p\b[^>]*>", " ", txt)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = html.unescape(txt)
    return re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s+", " ", txt)).strip()


def fragmento(urn: str) -> str:
    """'urn:...;1988!art103-2,emc-45-2004-12-08' -> 'art103-2,emc-45-2004-12-08'."""
    return urn.rsplit("!", 1)[1] if "!" in urn else ""


def id_artigo(frag: str) -> str | None:
    """Fragmento de artigo -> âncora do site. 'art5' -> 'art-5'; 'art103-2,...' -> 'art-103-b'."""
    m = re.fullmatch(r"art(\d+)(?:-(\d+))?(?:,.*)?", frag)
    if not m:
        return None
    letra = ""
    if m.group(2):
        n = int(m.group(2))
        letra = "-" + (chr(96 + n) if 1 <= n <= 26 else str(n))
    return f"art-{int(m.group(1))}{letra}"


NIVEL_TITULO = {"parte": 2, "livro": 2, "titulo": 2, "capitulo": 3, "secao": 4, "subsecao": 5}


def escapar_md(txt: str) -> str:
    """Evita que o texto vire lista ou título no Markdown."""
    txt = txt.replace("*", r"\*").replace("_", r"\_")
    txt = re.sub(r"^(\d+)([.)])", r"\1\\\2", txt)
    txt = re.sub(r"^([#>+-])", r"\\\1", txt)
    return txt


def montar(raiz: dict) -> tuple[dict[str, str], list[str], int]:
    """(artigos, linhas de Markdown, número de nós) a partir de hasPart."""
    artigos: dict[str, str] = {}
    linhas: list[str] = []
    nos = 0

    def visitar(no: dict) -> None:
        nonlocal nos
        if not isinstance(no, dict):
            return
        nos += 1
        tipo = tipo_de(no)
        frag = fragmento(no.get("legislationIdentifier") or "")
        v = versao_atual(no)
        nome = limpar(v.get("name") or no.get("name"))
        texto = limpar(v.get("text"))
        filhos = lista(no.get("hasPart"))

        if tipo == "artigo":
            aid = id_artigo(frag)
            if aid and aid not in artigos:
                artigos[aid] = frag
            # O texto do artigo fica no caput; junta "**Art. 5º** caput" num parágrafo só.
            caput = next((f for f in filhos if isinstance(f, dict) and tipo_de(f) == "caput"), None)
            corpo = limpar(versao_atual(caput).get("text")) if caput else texto
            linhas.append(f"**{escapar_md(nome or 'Art.')}** {escapar_md(corpo)}".rstrip())
            for f in filhos:
                if f is caput:
                    for g in lista(f.get("hasPart")):
                        visitar(g)
                else:
                    visitar(f)
            return
        if tipo in NIVEL_TITULO:
            rotulo = " — ".join(p for p in (nome, texto) if p)
            if rotulo:
                linhas.append("#" * NIVEL_TITULO[tipo] + " " + rotulo)
        elif tipo in ("ementa", "preambulo", "fecho", "assinaturas", "caput",
                      "paragrafo", "inciso", "alinea", "item", "pena"):
            if tipo == "preambulo" and texto.lower().startswith("preâmbulo"):
                texto = texto[len("preâmbulo"):].strip()
            par = " ".join(p for p in (nome, texto) if p)
            if par:
                linhas.append(escapar_md(par))
        elif texto:
            linhas.append(escapar_md(" ".join(p for p in (nome, texto) if p)))
        for f in filhos:
            visitar(f)

    for p in lista(raiz.get("hasPart")):
        visitar(p)
    return artigos, linhas, nos


def resumir(d: dict, com_texto: bool) -> dict | None:
    """Conteúdo de data/normas-leg/<id>.json, ou None se não há estrutura."""
    if not d.get("hasPart"):
        return None
    artigos, linhas, _ = montar(d)
    if not artigos:
        return None
    out = {
        "versao": VERSAO,
        "urn": d.get("legislationIdentifier"),
        "titulo": d.get("headline") or d.get("name"),
        "atualizado": d.get("dateModified") or d.get("sdDatePublished"),
        "licenca": d.get("license") or d.get("sdLicense"),
        "artigos": artigos,
    }
    if com_texto:
        out["texto_md"] = "\n\n".join(linhas) + "\n"
    return out


# ---------------------------------------------------------------------------
# índice, prioridade e normas sem texto
# ---------------------------------------------------------------------------
def entradas_do_indice(data: Path) -> dict[str, str]:
    """{id: urn} de todas as normas do índice."""
    man = json.loads((data / "index.json").read_text(encoding="utf-8"))
    partes = [man] if isinstance(man, list) else [
        json.loads((data / s["arquivo"]).read_text(encoding="utf-8")) for s in man["shards"]]
    out = {}
    for p in partes:
        if isinstance(p, dict) and "linhas" in p:
            p = [dict(zip(p["campos"], l)) for l in p["linhas"]]
        for e in p:
            if e.get("urn"):
                out[e["id"]] = e["urn"]
    return out


def ler_prioridade() -> list[str]:
    arq = RAIZ / "prioridade.txt"
    if not arq.exists():
        return []
    ids = []
    for l in arq.read_text(encoding="utf-8").splitlines():
        l = l.split("#", 1)[0].strip()
        if l:
            ids.append(l.removesuffix(".md"))
    return ids


TEM_ARTIGO = re.compile(r"\bArt\b|\bArt\.|\bArtigo\b", re.I)


def sem_texto_no_acervo(fonte: Path, ids: set[str]) -> set[str]:
    """Ids cujo .md no ctresb/leis é curto e não tem nenhum artigo.

    Só olha os blobs que já estão no clone (feito com blob:limit), sem baixar nada.
    """
    arv = subprocess.run(["git", "-C", str(fonte), "ls-tree", "-r", "HEAD"],
                         capture_output=True, text=True, check=True).stdout
    sha_de = {}
    for l in arv.splitlines():
        meta, caminho = l.split("\t", 1)
        if caminho.endswith(".md") and caminho[:-3] in ids:
            sha_de[meta.split()[2]] = caminho[:-3]
    lote = subprocess.run(
        ["git", "-C", str(fonte), "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        capture_output=True, text=True, check=True).stdout
    pequenos = [s for s, t, n in (l.split() for l in lote.splitlines())
                if t == "blob" and s in sha_de and int(n) < LIMITE_SEM_TEXTO]
    if not pequenos:
        return set()
    conteudo = subprocess.run(["git", "-C", str(fonte), "cat-file", "--batch"],
                              input=("\n".join(pequenos) + "\n").encode(), capture_output=True, check=True).stdout
    out, i = set(), 0
    while i < len(conteudo):
        fim = conteudo.index(b"\n", i)
        sha, _, tam = conteudo[i:fim].decode().split()
        corpo = conteudo[fim + 1: fim + 1 + int(tam)].decode("utf-8", "replace")
        i = fim + 1 + int(tam) + 1
        corpo = re.sub(r"^---\n.*?\n---\n", "", corpo, flags=re.S)
        if not TEM_ARTIGO.search(corpo):
            out.add(sha_de[sha])
    return out


# ---------------------------------------------------------------------------
# execução
# ---------------------------------------------------------------------------
def agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def caminho_de(saida: Path, id_: str) -> Path:
    return saida / (id_ + ".json")


def gravar_se_mudou(arq: Path, dados: dict) -> bool:
    txt = json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n"
    if arq.exists() and arq.read_text(encoding="utf-8") == txt:
        return False
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(txt, encoding="utf-8")
    return True


def fila(indice: dict[str, str], estado: dict, prioridade: list[str], sem_texto: set[str], ref: datetime) -> list[str]:
    """Ordem de consulta: prioridade e sem texto vencidas, depois nunca vistas, depois as mais antigas."""
    def vencida(id_: str, dias: int) -> bool:
        e = estado.get(id_)
        if not e or e.get("v") != VERSAO:
            return True
        return datetime.fromisoformat(e["em"]) < ref - timedelta(days=dias)

    urgentes = [i for i in dict.fromkeys(prioridade + sorted(sem_texto))
                if i in indice and vencida(i, REVISITAR_PRIORIDADE)]
    vistos = set(urgentes)
    novas = [i for i in indice if i not in vistos and i not in estado]
    antigas = sorted((i for i in indice if i not in vistos and i in estado and vencida(i, REVISITAR_DIAS)),
                     key=lambda i: estado[i]["em"])
    return urgentes + novas + antigas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--fonte", type=Path, help="clone do ctresb/leis com --filter=blob:limit=1500")
    ap.add_argument("--minutos", type=float, default=25, help="tempo máximo de coleta")
    ap.add_argument("--max", type=int, default=0, help="no máximo N consultas (0 = sem limite)")
    ap.add_argument("--ids", nargs="*", help="consultar só estes ids")
    a = ap.parse_args(argv)

    saida = a.data / "normas-leg"
    arq_estado = saida / "estado.json"
    estado = json.loads(arq_estado.read_text(encoding="utf-8")) if arq_estado.exists() else {}
    indice = entradas_do_indice(a.data)
    prioridade = ler_prioridade()
    ref = agora()

    sem_texto = {i for i, e in estado.items() if e.get("sem_texto")}
    if a.fonte:
        sem_texto = sem_texto_no_acervo(a.fonte, set(indice))
        print(f"{len(sem_texto)} normas do índice sem texto no ctresb/leis")
        for i, e in estado.items():   # o acervo pode ter ganhado o texto desde a última vez
            if e.get("sem_texto") and i not in sem_texto:
                e.pop("sem_texto"); e["em"] = "2000-01-01T00:00:00+00:00"
    com_texto = set(prioridade) | sem_texto

    ordem = [i for i in (a.ids or []) if i in indice] if a.ids is not None else fila(indice, estado, prioridade, sem_texto, ref)
    limite = time.monotonic() + a.minutos * 60
    feitas = gravadas = falhas = 0
    for id_ in ordem:
        if time.monotonic() > limite or (a.max and feitas >= a.max):
            break
        feitas += 1
        try:
            d = baixar_json(indice[id_])
        except Exception as e:
            falhas += 1
            print(f"  falhou {id_}: {e}", file=sys.stderr)
            if falhas >= 25 and falhas > feitas // 2:
                print("Muitas falhas seguidas: o normas.leg.br pode estar fora do ar. Parando.", file=sys.stderr)
                break
            continue
        resumo = resumir(d, id_ in com_texto) if d else None
        arq = caminho_de(saida, id_)
        if resumo:
            gravadas += gravar_se_mudou(arq, resumo)
        elif arq.exists():
            arq.unlink()
        e = {"v": VERSAO, "em": agora().isoformat(),
             "r": "estruturado" if resumo else ("sem_estrutura" if d else "ausente")}
        if resumo:
            e["n"] = len(resumo["artigos"])
        if id_ in sem_texto:
            e["sem_texto"] = True
        estado[id_] = e
        if feitas % 100 == 0:
            print(f"  {feitas} consultas, {gravadas} arquivos novos ou alterados")
        time.sleep(PAUSA)

    # Ids que saíram do índice.
    for id_ in [i for i in estado if i not in indice]:
        estado.pop(id_)
        if caminho_de(saida, id_).exists():
            caminho_de(saida, id_).unlink()

    saida.mkdir(parents=True, exist_ok=True)
    arq_estado.write_text(json.dumps(dict(sorted(estado.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    contagem: dict[str, int] = {}
    for e in estado.values():
        contagem[e["r"]] = contagem.get(e["r"], 0) + 1
    print(f"{feitas} consultas ({falhas} falhas), {gravadas} arquivos gravados. "
          f"Situação: {contagem}; faltam {len(indice) - len(estado)} normas nunca consultadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
