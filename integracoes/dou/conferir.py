#!/usr/bin/env python3
"""Confere o acervo e o monitor contra o que saiu no Diário Oficial da União.

Gera data/dou/conferencia.json com duas listas:

- fora_do_acervo: leis, leis complementares, emendas, MPs e decretos publicados
  no DOU há mais de DIAS_TOLERANCIA dias que ainda não têm arquivo no ctresb/leis;
- monitor: para cada lei de monitor/acompanhar.txt, os atos do DOU que a alteram
  ou revogam e se o acervo (e o monitor) já registraram uma mudança depois deles.

Uso: python integracoes/dou/conferir.py [--saida data/dou]
Com GITHUB_TOKEN no ambiente, consulta a data do último commit de cada lei
acompanhada no ctresb/leis (10 chamadas à API do GitHub).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
REPOSITORIO_FONTE = "ctresb/leis"
DIAS_TOLERANCIA = 7
NO_ACERVO = {"lei", "lcp", "emc", "mpv", "dec"}


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def acompanhadas(arquivo: Path) -> list[tuple[str, str]]:
    """[(id, apelido)] de monitor/acompanhar.txt."""
    saida = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        caminho, _, comentario = linha.partition("#")
        caminho = caminho.strip()
        if caminho.endswith(".md"):
            saida.append((caminho[:-3], comentario.strip()))
    return saida


def ultimo_commit(caminho: str, token: str | None) -> dict | None:
    if not token:
        return None
    url = (f"https://api.github.com/repos/{REPOSITORIO_FONTE}/commits?"
           + urllib.parse.urlencode({"path": caminho, "per_page": 1}))
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "User-Agent": "leis-indice"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            dados = json.load(r)
    except OSError as e:
        print(f"::warning::commits de {caminho}: {e}")
        return None
    if not dados:
        return None
    return {"sha": dados[0]["sha"], "data": dados[0]["commit"]["committer"]["date"][:10]}


def resumo(ato: dict, **extra) -> dict:
    return {"ato": ato["id"], "data": ato["data"], "tipo": ato["tipo"],
            "identifica": ato["identifica"], "ementa": ato["ementa"][:240], "url": ato["url"], **extra}


def conferir(saida: Path, monitor_dir: Path, hoje: dt.date, token: str | None) -> dict:
    atos = []
    for arq in sorted((saida / "meses").glob("*.json")):
        atos += ler_json(arq, [])

    limite = (hoje - dt.timedelta(days=DIAS_TOLERANCIA)).isoformat()
    fora = [
        resumo(a, dias=(hoje - dt.date.fromisoformat(a["data"])).days)
        for a in atos
        if a["prefixo"] in NO_ACERVO and not a["norma"] and a["data"] and a["data"] <= limite
    ]
    fora.sort(key=lambda x: (x["data"], x["ato"]), reverse=True)

    estado_monitor = ler_json(monitor_dir / "estado.json", {})
    leis = []
    for id_, apelido in acompanhadas(monitor_dir / "acompanhar.txt"):
        mudancas = [resumo(a, rel=rel) for a in atos for rel in ("altera", "revoga") if id_ in a[rel]]
        mudancas.sort(key=lambda x: (x["data"], x["ato"]), reverse=True)
        item = {"id": id_, "apelido": apelido, "atos": mudancas,
                "monitor_sha": estado_monitor.get(id_ + ".md")}
        commit = ultimo_commit(id_ + ".md", token) if mudancas else None
        item["acervo"] = commit
        if not mudancas:
            item["situacao"] = "sem_atos"
        elif commit is None:
            item["situacao"] = "nao_verificado"
        elif commit["data"] < mudancas[0]["data"]:
            item["situacao"] = "acervo_atrasado"
        elif item["monitor_sha"] and item["monitor_sha"] != commit["sha"]:
            item["situacao"] = "monitor_pendente"
        else:
            item["situacao"] = "em_dia"
        leis.append(item)

    return {
        "versao": 1,
        "conferido_em": hoje.isoformat(),
        "tolerancia_dias": DIAS_TOLERANCIA,
        "fora_do_acervo": fora,
        "monitor": leis,
    }


def relatorio(c: dict) -> str:
    linhas = ["## Conferência com o Diário Oficial", ""]
    linhas.append(f"- Atos publicados há mais de {c['tolerancia_dias']} dias que ainda não estão "
                  f"no acervo: **{len(c['fora_do_acervo'])}**")
    for a in c["fora_do_acervo"][:15]:
        linhas.append(f"  - {a['data']}: [{a['identifica']}]({a['url']})")
    linhas += ["", "| Lei acompanhada | Atos no DOU | Situação |", "|---|---|---|"]
    for l in c["monitor"]:
        linhas.append(f"| {l['apelido'] or l['id']} | {len(l['atos'])} | {l['situacao']} |")
    return "\n".join(linhas) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", type=Path, default=RAIZ / "data" / "dou")
    p.add_argument("--monitor", type=Path, default=RAIZ / "monitor")
    args = p.parse_args(argv)
    c = conferir(args.saida, args.monitor, dt.date.today(), os.environ.get("GITHUB_TOKEN"))
    destino = args.saida / "conferencia.json"
    antigo = ler_json(destino, {})
    if {k: v for k, v in antigo.items() if k != "conferido_em"} != {k: v for k, v in c.items() if k != "conferido_em"}:
        destino.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    texto = relatorio(c)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto)
    for l in c["monitor"]:
        if l["situacao"] == "acervo_atrasado":
            print(f"::warning::{l['apelido'] or l['id']}: alterada no DOU em {l['atos'][0]['data']}, "
                  "mas o acervo ainda não mudou")
    return 0


if __name__ == "__main__":
    sys.exit(main())
