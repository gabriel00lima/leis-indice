#!/usr/bin/env python3
"""Coleta, nos dados abertos da Câmara dos Deputados, os projetos que alteram
cada norma do índice e o projeto que deu origem a cada norma.

Fonte: arquivos anuais em massa da API v2
(https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-<ano>.json).
Um arquivo por ano, em vez de milhares de chamadas à API: evita o limite de
requisições (HTTP 429).

Uso (é o que a Action faz):

    python integracoes/camara/coletar.py --data data --cache "$RUNNER_TEMP/camara-cache"

Os resumos por ano ficam em --cache (cache da Action, fora do git). A cada
execução são baixados o ano atual, o anterior, os anos sem resumo e os N anos
de resumo mais antigo (--anos-por-execucao), para que mudanças de situação em
projetos antigos (arquivamento, virar lei) entrem em poucos dias.

Saída em data/camara/ (formato em integracoes/camara/README.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1] / "indice"))
import ementa as em  # noqa: E402
from construir import Resolvedor, json_linhas, escrever  # noqa: E402

VERSAO = 1
URL_ANO = "https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-{ano}.json"
URL_PROPOSICAO = "https://www.camara.leg.br/propostas-legislativas/{id}"
PRIMEIRO_ANO = 1946
# Tipos que podem alterar ou criar leis.
TIPOS = {"PL", "PLP", "PEC", "MPV", "PLV", "PLN", "PLS", "PLC"}
USER_AGENT = "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"
MAX_EMENTA = 300


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
# Download com respeito ao limite de requisições
# ---------------------------------------------------------------------------
def baixar(url: str, destino: Path, tentativas: int = 6) -> bool:
    """Baixa url em destino. False se 404. Repete em 429/5xx com espera crescente."""
    espera = 10
    for i in range(1, tentativas + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if e.code not in (429, 500, 502, 503, 504) or i == tentativas:
                raise
            retry = e.headers.get("Retry-After", "")
            pausa = int(retry) if retry.isdigit() else espera
            log(f"  HTTP {e.code} em {url}; nova tentativa em {pausa}s")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tentativas:
                raise
            pausa = espera
            log(f"  {e} em {url}; nova tentativa em {pausa}s")
        time.sleep(pausa)
        espera = min(espera * 2, 300)
    return False


# ---------------------------------------------------------------------------
# Resumo de um ano: só as proposições que alteram ou geraram normas do índice
# ---------------------------------------------------------------------------
def _status(p: dict) -> dict:
    s = p.get("ultimoStatus")
    if isinstance(s, dict):
        return s
    # Achatado (como no CSV): ultimoStatus_descricaoSituacao etc.
    return {k.split("_", 1)[1]: v for k, v in p.items() if k.startswith("ultimoStatus_")}


def resumir_ano(proposicoes: list[dict], resolver) -> list[dict]:
    saida = []
    for p in proposicoes:
        sigla = (p.get("siglaTipo") or "").strip().upper()
        if sigla not in TIPOS:
            continue
        ementa = (p.get("ementa") or "").strip()
        data = str(p.get("dataApresentacao") or "")[:10]
        st = _status(p)
        situacao = (st.get("descricaoSituacao") or "").strip()
        alteradas = {}
        for prefixo, numero, ano, relacao in em.normas_alteradas(ementa, data):
            alvo = resolver(prefixo, numero, ano, data)
            if alvo:
                alteradas.setdefault(alvo, relacao)
        gerada = em.norma_gerada(p.get("urnFinal"), situacao, st.get("despacho"), st.get("descricaoTramitacao"))
        origem = resolver(*gerada, "") if gerada else None
        if not alteradas and not origem:
            continue
        item = {
            "id": p.get("id"),
            "sigla": f"{sigla} {p.get('numero')}/{p.get('ano')}",
            "ementa": ementa if len(ementa) <= MAX_EMENTA else ementa[: MAX_EMENTA - 1].rstrip() + "…",
            "apresentacao": data,
            "situacao": situacao,
            "atualizado": str(st.get("dataHora") or st.get("data") or "")[:10],
            "tramitando": em.em_tramitacao(situacao),
        }
        if alteradas:
            item["altera"] = alteradas
        if origem:
            item["origem"] = origem
        saida.append(item)
    return saida


def carregar_resolvedor(data: Path):
    """resolver(prefixo, numero, ano, data_citante) -> id do índice ou None."""
    ids = []
    for arq in sorted((data / "index").glob("*.json")):
        ids += [e["id"] for e in json.loads(arq.read_text(encoding="utf-8"))]
    conhecidos = set(ids)
    r = Resolvedor([i + ".md" for i in ids if i != "constituicao"])

    def resolver(prefixo, numero, ano, data_citante):
        if prefixo == "constituicao":
            return "constituicao" if "constituicao" in conhecidos else None
        alvo = r.resolver(prefixo, numero, ano, data_citante)
        return alvo if alvo in conhecidos else None

    return resolver, conhecidos


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def escolher_anos(cache: Path, ano_atual: int, por_execucao: int, todos: bool) -> list[int]:
    anos = list(range(PRIMEIRO_ANO, ano_atual + 1))
    if todos:
        return anos
    idade = {}
    for a in anos:
        f = cache / f"{a}.json"
        if not f.exists():
            idade[a] = ""
        else:
            idade[a] = json.loads(f.read_text(encoding="utf-8")).get("baixado_em", "")
    faltando = [a for a in anos if idade[a] == ""]
    recentes = [a for a in (ano_atual, ano_atual - 1) if a not in faltando]
    resto = sorted((a for a in anos if a not in faltando and a not in recentes), key=lambda a: idade[a])
    return faltando + recentes + resto[:por_execucao]


def atualizar_cache(cache: Path, anos: list[int], resolver, pausa: float) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="camara-"))
    try:
        for ano in anos:
            arq = tmp / f"{ano}.json"
            t0 = time.time()
            ok = baixar(URL_ANO.format(ano=ano), arq)
            agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            if not ok:
                log(f"{ano}: sem arquivo (404)")
                escrever(cache / f"{ano}.json", json.dumps({"ano": ano, "baixado_em": agora, "itens": []}))
                continue
            tamanho = arq.stat().st_size
            dados = json.loads(arq.read_text(encoding="utf-8"))
            arq.unlink()
            lista = dados.get("dados", dados) if isinstance(dados, dict) else dados
            itens = resumir_ano(lista, resolver)
            escrever(cache / f"{ano}.json", json.dumps({"ano": ano, "baixado_em": agora, "total": len(lista), "itens": itens}, ensure_ascii=False))
            log(f"{ano}: {len(lista)} proposições, {len(itens)} ligadas ao índice "
                f"({tamanho / 1e6:.1f} MB, {time.time() - t0:.0f}s)")
            del dados, lista
            time.sleep(pausa)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def montar_saida(cache: Path, data: Path, conhecidos: set[str]) -> dict:
    por_norma: dict[str, dict] = defaultdict(lambda: {"tramitando": [], "origem": [], "encerrados": 0})
    total_props = tramitando = 0
    anos = []
    for f in sorted(cache.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        anos.append(d["ano"])
        for it in d.get("itens", []):
            total_props += 1
            base = {k: it[k] for k in ("id", "sigla", "ementa", "apresentacao", "situacao", "atualizado")}
            base["url"] = URL_PROPOSICAO.format(id=it["id"])
            if it.get("tramitando"):
                tramitando += 1
            for alvo, relacao in (it.get("altera") or {}).items():
                if alvo not in conhecidos:
                    continue
                if it.get("tramitando"):
                    por_norma[alvo]["tramitando"].append({**base, "relacao": relacao})
                else:
                    por_norma[alvo]["encerrados"] += 1
            if it.get("origem") in conhecidos:
                por_norma[it["origem"]]["origem"].append(base)

    pasta = data / "camara" / "normas"
    escritos, mudou = set(), False
    for alvo, v in por_norma.items():
        if not v["tramitando"] and not v["origem"]:
            continue
        v["tramitando"].sort(key=lambda x: (x["atualizado"] or x["apresentacao"]), reverse=True)
        v["origem"].sort(key=lambda x: x["apresentacao"])
        caminho = pasta / f"{alvo}.json"
        conteudo = json_linhas({"id": alvo, "origem": v["origem"], "tramitando": v["tramitando"], "encerrados": v["encerrados"]})
        mudou |= escrever(caminho, conteudo)
        escritos.add(caminho)
    if pasta.exists():
        for f in pasta.rglob("*.json"):
            if f not in escritos:
                f.unlink()
                mudou = True
        for d in sorted((p for p in pasta.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()

    normas_com_tramitacao = sum(1 for v in por_norma.values() if v["tramitando"])
    normas_com_origem = sum(1 for v in por_norma.values() if v["origem"])
    resumo = {
        "versao": VERSAO,
        "fonte": "https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/",
        "anos": [min(anos), max(anos)] if anos else [],
        "proposicoes_ligadas": total_props,
        "proposicoes_tramitando": tramitando,
        "normas_com_projetos": normas_com_tramitacao,
        "normas_com_origem": normas_com_origem,
        "arquivo": "camara/normas/<id>.json",
    }
    manifesto = data / "camara" / "index.json"
    anterior = {}
    if manifesto.exists():
        anterior = json.loads(manifesto.read_text(encoding="utf-8"))
    sem_data = {k: v for k, v in anterior.items() if k != "gerado_em"}
    if mudou or sem_data != resumo:
        resumo["gerado_em"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    else:
        resumo["gerado_em"] = anterior.get("gerado_em")
    escrever(manifesto, json.dumps(resumo, ensure_ascii=False, indent=2) + "\n")
    return resumo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--cache", type=Path, default=Path(".cache/camara"))
    ap.add_argument("--anos-por-execucao", type=int, default=15)
    ap.add_argument("--todos", action="store_true", help="baixar todos os anos")
    ap.add_argument("--anos", help="só estes anos, ex.: 2023,2024 (para testes)")
    ap.add_argument("--pausa", type=float, default=2.0, help="segundos entre downloads")
    args = ap.parse_args(argv)

    resolver, conhecidos = carregar_resolvedor(args.data)
    log(f"{len(conhecidos)} normas no índice")
    ano_atual = dt.date.today().year
    if args.anos:
        anos = [int(a) for a in args.anos.split(",")]
    else:
        anos = escolher_anos(args.cache, ano_atual, args.anos_por_execucao, args.todos)
    log(f"Anos a baixar: {anos}")
    atualizar_cache(args.cache, anos, resolver, args.pausa)
    resumo = montar_saida(args.cache, args.data, conhecidos)
    log(json.dumps(resumo, ensure_ascii=False))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### Câmara\n\n```json\n{json.dumps(resumo, ensure_ascii=False, indent=2)}\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
