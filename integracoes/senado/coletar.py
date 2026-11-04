#!/usr/bin/env python3
"""Coleta, no Senado (Dados Abertos), o histórico de alterações e as decisões de controle de
constitucionalidade (ADI, ADC, ADPF...) de cada norma do índice, buscando pela URN.

Grava em data/senado/:
- normas/<id>.json  um arquivo por norma que tem alterações ou decisões (formato em README.md);
- estado.json       quando cada norma foi consultada, para a coleta ser incremental;
- adi.json          resumo das normas com dispositivos declarados inconstitucionais ou suspensos.

O Senado não documenta limites de uso, então a coleta é deliberadamente lenta: uma requisição
por vez, pausa entre elas, teto de normas e de tempo por execução, e para ao primeiro sinal de
sobrecarga (429/503). Uso: python integracoes/senado/coletar.py --data data [--limite 1500]
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import senado  # noqa: E402

API = "https://legis.senado.leg.br/dadosabertos/legislacao/urn?urn="
USER_AGENT = "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"
REVISITAR_DIAS = 45  # depois de tudo coletado, reconsulta as normas mais antigas


class Sobrecarga(Exception):
    pass


def ler_json(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return padrao


def escrever_json_linhas(p: Path, d: dict):
    """Um item por linha, como o resto de data/, para diffs pequenos."""
    p.parent.mkdir(parents=True, exist_ok=True)
    linhas = [json.dumps(k, ensure_ascii=False) + ":" + json.dumps(v, ensure_ascii=False) for k, v in d.items()]
    p.write_text("{\n" + ",\n".join(linhas) + "\n}\n", encoding="utf-8")


def carregar_indice(data: Path):
    """Lista de normas (id, urn, prefixo, numero, data, sha, importância)."""
    manifesto = ler_json(data / "index.json")
    if not manifesto:
        sys.exit(f"{data}/index.json não encontrado")
    normas = []
    for s in manifesto["shards"]:
        cache = ler_json(data / "cache" / Path(s["arquivo"]).name, {}) or {}
        adj = ler_json(data / s["adjacencia"], {}) if s.get("adjacencia") else {}
        for e in ler_json(data / s["arquivo"], []):
            if not e.get("urn"):
                continue
            v = adj.get(e["id"], {})
            normas.append({
                "id": e["id"], "urn": e["urn"], "prefixo": s.get("prefixo"),
                "numero": str(e.get("numero") or ""), "data": e.get("data"),
                "sha": (cache.get(e["path"]) or [None])[0],
                "peso": len(v.get("citada_por", [])) + 3 * len(v.get("alterada_por", [])),
            })
    return normas


def resolvedor(normas):
    mapa = {}
    for n in normas:
        if n["prefixo"] and n["numero"] and n["data"]:
            mapa[(n["prefixo"], n["numero"].lstrip("0"), n["data"])] = n["id"]

    def resolver(chave):
        prefixo, numero, data = chave
        return mapa.get((prefixo, numero.lstrip("0"), data))
    return resolver


def ordem_de_coleta(normas, estado, hoje: date):
    """Nunca consultadas (as mais citadas primeiro), depois as que mudaram no acervo,
    depois as consultadas há mais de REVISITAR_DIAS dias (as mais antigas primeiro)."""
    novas, mudaram, velhas = [], [], []
    for n in normas:
        e = estado.get(n["id"])
        if not e:
            novas.append(n)
        elif n["sha"] and e.get("sha") != n["sha"]:
            mudaram.append(n)
        else:
            dias = (hoje - date.fromisoformat(e["em"])).days
            if dias >= REVISITAR_DIAS:
                velhas.append((e["em"], n))
    novas.sort(key=lambda n: -n["peso"])
    mudaram.sort(key=lambda n: -n["peso"])
    velhas.sort(key=lambda t: t[0])
    return novas + mudaram + [n for _, n in velhas]


def consultar(urn: str, timeout: int = 90) -> dict | None:
    req = urllib.request.Request(API + urllib.parse.quote(urn, safe=":;.-"),
                                 headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            try:
                corpo = r.read()
            except http.client.IncompleteRead as e:
                # Respostas grandes (ex.: CLT, ~800 KB) às vezes chegam inteiras, mas com
                # Content-Length maior que o corpo. Aproveita o que veio se for JSON válido.
                corpo = e.partial
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (429, 502, 503, 504):
            raise Sobrecarga(f"HTTP {e.code}") from e
        raise
    if not corpo.strip():
        return None
    return json.loads(corpo)


def json_compacto(registro: dict) -> str:
    """Uma chave por linha e, nas listas, um item por linha: legível no diff sem inflar o arquivo."""
    def valor(v):
        if isinstance(v, list) and v:
            return "[\n" + ",\n".join(json.dumps(i, ensure_ascii=False) for i in v) + "\n]"
        return json.dumps(v, ensure_ascii=False)
    return "{\n" + ",\n".join(json.dumps(k) + ": " + valor(v) for k, v in registro.items()) + "\n}\n"


def caminho_norma(saida: Path, id_: str) -> Path:
    return saida / "normas" / (id_ + ".json")


def gravar_resumo_adi(saida: Path, estado: dict):
    adi = {id_: {"inconstitucionais": e["inc"], "artigos": e.get("arts", [])}
           for id_, e in sorted(estado.items()) if e.get("inc")}
    escrever_json_linhas(saida / "adi.json", adi)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default="data", type=Path)
    ap.add_argument("--limite", type=int, default=1500, help="máximo de consultas nesta execução")
    ap.add_argument("--tempo", type=int, default=45 * 60, help="tempo máximo em segundos")
    ap.add_argument("--pausa", type=float, default=1.0, help="segundos entre consultas")
    ap.add_argument("--ids", nargs="*", help="consultar só estes ids (teste)")
    a = ap.parse_args(argv)

    saida = a.data / "senado"
    estado_arq = saida / "estado.json"
    bruto = ler_json(estado_arq, {}) or {}
    estado = bruto.get("normas", {})

    normas = carregar_indice(a.data)
    resolver = resolvedor(normas)
    hoje = datetime.now(timezone.utc).date()
    fila = [n for n in normas if n["id"] in set(a.ids)] if a.ids else ordem_de_coleta(normas, estado, hoje)
    print(f"{len(normas)} normas no índice, {len(estado)} já consultadas, {len(fila)} na fila; "
          f"limite {a.limite} consultas / {a.tempo}s")

    inicio = time.monotonic()
    feitas = erros_seguidos = com_dados = 0

    def salvar():
        saida.mkdir(parents=True, exist_ok=True)
        cabecalho = {"versao": 1, "fonte": "https://legis.senado.leg.br/dadosabertos/legislacao/urn",
                     "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "consultadas": len(estado), "total_indice": len(normas)}
        linhas = [json.dumps(k) + ":" + json.dumps(v, ensure_ascii=False) for k, v in sorted(estado.items())]
        corpo = ",\n".join(json.dumps(k) + ":" + json.dumps(v, ensure_ascii=False) for k, v in cabecalho.items())
        estado_arq.write_text("{\n" + corpo + ',\n"normas":{\n' + ",\n".join(linhas) + "\n}\n}\n", encoding="utf-8")
        gravar_resumo_adi(saida, estado)

    for n in fila:
        if feitas >= a.limite or time.monotonic() - inicio > a.tempo:
            break
        if feitas:
            time.sleep(a.pausa)
        feitas += 1
        try:
            resposta = consultar(n["urn"])
        except Sobrecarga as e:
            print(f"Senado sobrecarregado ({e}) em {n['id']}: esperando 2 min")
            time.sleep(120)
            try:
                resposta = consultar(n["urn"])
            except Sobrecarga:
                print("Continua sobrecarregado: encerrando a coleta por hoje.")
                break
        except Exception as e:  # rede, JSON inválido...
            erros_seguidos += 1
            print(f"erro em {n['id']}: {e}")
            if erros_seguidos >= 10:
                print("10 erros seguidos: encerrando.")
                break
            time.sleep(5)
            continue
        erros_seguidos = 0

        registro = senado.converter(resposta, resolver) if resposta else None
        arq = caminho_norma(saida, n["id"])
        e = {"em": hoje.isoformat(), "sha": n["sha"]}
        if registro is None:
            e["achou"] = False
        else:
            r = senado.resumo(registro)
            e.update({"alt": r["alteracoes"], "ctrl": r["controle"], "inc": r["inconstitucionais"]})
            if r["artigos_afetados"]:
                e["arts"] = r["artigos_afetados"]
        if registro and (registro["alteracoes"] or registro["controle"]):
            registro = {"id": n["id"], "urn": n["urn"], "consultado_em": hoje.isoformat(), **registro}
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(json_compacto(registro), encoding="utf-8")
            com_dados += 1
        elif arq.exists():
            arq.unlink()
        estado[n["id"]] = e
        if feitas % 100 == 0:
            salvar()
            print(f"{feitas} consultas, {com_dados} com dados, {time.monotonic() - inicio:.0f}s")

    salvar()
    print(f"Fim: {feitas} consultas, {com_dados} normas com alterações ou decisões, "
          f"{len(estado)}/{len(normas)} já consultadas, {time.monotonic() - inicio:.0f}s")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"Senado: {feitas} consultas nesta execução, {len(estado)}/{len(normas)} normas já consultadas.\n")


if __name__ == "__main__":
    main()
