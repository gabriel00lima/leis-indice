#!/usr/bin/env python3
"""Coleta estados e municípios da API de Localidades do IBGE e grava JSON estático.

Uso (a partir da raiz do repositório):
    python ibge/coletar.py --saida data/ibge

Fonte: https://servicodados.ibge.gov.br/api/docs/localidades (sem chave).
Só a biblioteca padrão. Se a resposta vier incompleta (menos de 27 UFs ou de
5.500 municípios), nada é gravado e o script sai com erro.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://servicodados.ibge.gov.br/api/v1/localidades"
URL_ESTADOS = f"{API}/estados?orderBy=nome"
URL_MUNICIPIOS = f"{API}/municipios?view=nivelado"

# Espelho em CSV dos mesmos códigos do IBGE, usado só se a API não responder
# (ela às vezes não aceita conexões dos runners do GitHub, fora do Brasil).
ESPELHO = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/"
REGIOES = {"Norte": (1, "N"), "Nordeste": (2, "NE"), "Sudeste": (3, "SE"),
           "Sul": (4, "S"), "Centro-Oeste": (5, "CO")}

MIN_UFS = 27
MIN_MUNICIPIOS = 5500

# Código IBGE do município-capital de cada UF (a API não informa capitais).
CAPITAIS = {
    "AC": 1200401, "AL": 2704302, "AM": 1302603, "AP": 1600303, "BA": 2927408,
    "CE": 2304400, "DF": 5300108, "ES": 3205309, "GO": 5208707, "MA": 2111300,
    "MG": 3106200, "MS": 5002704, "MT": 5103403, "PA": 1501402, "PB": 2507507,
    "PE": 2611606, "PI": 2211001, "PR": 4106902, "RJ": 3304557, "RN": 2408102,
    "RO": 1100205, "RR": 1400100, "RS": 4314902, "SC": 4205407, "SE": 2800308,
    "SP": 3550308, "TO": 1721000,
}


def slug(texto: str) -> str:
    """"São João d'Aliança" -> "sao-joao-d-alianca" (minúsculas, sem acentos)."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    saida, hifen = [], False
    for c in t.lower():
        if c.isalnum():
            saida.append(c); hifen = False
        elif not hifen and saida:
            saida.append("-"); hifen = True
    return "".join(saida).strip("-")


def _abrir(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/csv",
        "User-Agent": "leis-indice (github.com/gabriel00lima/leis-indice)",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def baixar(url: str, tentativas: int = 3, timeout: int = 30, json_: bool = True) -> object:
    erro = None
    for i in range(tentativas):
        try:
            dados = _abrir(url, timeout)
            return json.loads(dados) if json_ else dados.decode("utf-8-sig")
        except Exception as e:  # noqa: BLE001 - rede instável: tenta de novo
            erro = e
            espera = 2 ** (i + 1)
            print(f"falha em {url} ({e}); nova tentativa em {espera}s", file=sys.stderr)
            time.sleep(espera)
    raise ErroRede(f"Não foi possível baixar {url}: {erro}")


class ErroRede(Exception):
    pass


def do_espelho(csv_estados: str, csv_municipios: str) -> tuple[list, list]:
    """Converte os CSV do espelho para os formatos da API (estados e view nivelada)."""
    estados, sigla_por_codigo = [], {}
    for l in csv.DictReader(io.StringIO(csv_estados.lstrip("\ufeff"))):
        cod_r, sig_r = REGIOES[l["regiao"]]
        estados.append({"id": int(l["codigo_uf"]), "sigla": l["uf"], "nome": l["nome"],
                        "regiao": {"id": cod_r, "sigla": sig_r, "nome": l["regiao"]}})
        sigla_por_codigo[int(l["codigo_uf"])] = l["uf"]
    municipios = [
        {"municipio-id": int(l["codigo_ibge"]), "municipio-nome": l["nome"],
         "UF-sigla": sigla_por_codigo[int(l["codigo_uf"])]}
        for l in csv.DictReader(io.StringIO(csv_municipios.lstrip("\ufeff")))
    ]
    return estados, municipios


def coletar() -> tuple[list, list, str]:
    """Tenta a API do IBGE; se não responder, usa o espelho. Devolve (estados, municípios, fonte)."""
    try:
        return baixar(URL_ESTADOS), baixar(URL_MUNICIPIOS, timeout=90), "ibge"
    except ErroRede as e:
        print(f"::warning::API do IBGE indisponível ({e}); usando o espelho {ESPELHO}", file=sys.stderr)
    e = baixar(ESPELHO + "estados.csv", json_=False)
    m = baixar(ESPELHO + "municipios.csv", json_=False)
    return (*do_espelho(e, m), "espelho")


def _uf_de_municipio(m: dict) -> dict | None:
    """UF de um município no formato aninhado. Alguns municípios novos vêm com
    microrregiao = null; nesse caso a UF sai da região imediata."""
    try:
        return m["microrregiao"]["mesorregiao"]["UF"]
    except (KeyError, TypeError):
        pass
    try:
        return m["regiao-imediata"]["regiao-intermediaria"]["UF"]
    except (KeyError, TypeError):
        return None


def normalizar_estados(bruto: list) -> list[dict]:
    estados = []
    for e in bruto:
        r = e.get("regiao") or {}
        estados.append({
            "codigo": int(e["id"]),
            "sigla": e["sigla"],
            "nome": e["nome"],
            "slug": slug(e["nome"]),
            "regiao": {"codigo": int(r["id"]), "sigla": r["sigla"], "nome": r["nome"]} if r else None,
            "capital": CAPITAIS.get(e["sigla"]),
        })
    estados.sort(key=lambda x: x["sigla"])
    return estados


def normalizar_municipios(bruto: list) -> list[list]:
    """Aceita a view "nivelado" (chaves planas) ou a aninhada (padrão da API).
    Devolve linhas [codigo, nome, uf, slug, capital] ordenadas por UF e nome."""
    linhas, vistos = [], set()
    for m in bruto:
        if "municipio-id" in m:
            codigo, nome, uf = m["municipio-id"], m["municipio-nome"], m["UF-sigla"]
        else:
            u = _uf_de_municipio(m)
            if not u:
                raise ValueError(f"Município sem UF: {m.get('id')} {m.get('nome')}")
            codigo, nome, uf = m["id"], m["nome"], u["sigla"]
        codigo = int(codigo)
        if codigo in vistos:  # a view nivelada repete o município por região
            continue
        vistos.add(codigo)
        linhas.append([codigo, nome, uf, slug(nome), 1 if CAPITAIS.get(uf) == codigo else 0])
    linhas.sort(key=lambda l: (l[2], l[3], l[0]))
    return linhas


def validar(estados: list[dict], municipios: list[list]) -> None:
    if len(estados) < MIN_UFS:
        raise SystemExit(f"Só {len(estados)} UFs na resposta do IBGE; esperado {MIN_UFS}.")
    if len(municipios) < MIN_MUNICIPIOS:
        raise SystemExit(f"Só {len(municipios)} municípios na resposta; esperado ≥ {MIN_MUNICIPIOS}.")
    siglas = {e["sigla"] for e in estados}
    orfaos = {l[2] for l in municipios} - siglas
    if orfaos:
        raise SystemExit(f"Municípios com UF desconhecida: {sorted(orfaos)}")


def _linhas_json(itens: list) -> str:
    """Um item por linha, para diffs pequenos no git."""
    return "[\n" + ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in itens) + "\n]"


def gravar(saida: Path, estados: list[dict], municipios: list[list], fonte: str = "ibge") -> bool:
    """Grava os arquivos. Devolve False se nada mudou (e não mexe em gerado_em)."""
    saida.mkdir(parents=True, exist_ok=True)
    por_uf: dict[str, int] = {}
    for l in municipios:
        por_uf[l[2]] = por_uf.get(l[2], 0) + 1
    for e in estados:
        e["municipios"] = por_uf.get(e["sigla"], 0)

    txt_estados = _linhas_json(estados) + "\n"
    txt_municipios = (
        '{"campos":["codigo","nome","uf","slug","capital"],"linhas":'
        + _linhas_json(municipios) + "}\n"
    )
    hash_ = hashlib.sha256((txt_estados + txt_municipios).encode()).hexdigest()

    manifesto_p = saida / "index.json"
    if manifesto_p.exists():
        try:
            if json.loads(manifesto_p.read_text())["sha256"] == hash_:
                return False
        except (ValueError, KeyError):
            pass

    (saida / "estados.json").write_text(txt_estados, encoding="utf-8")
    (saida / "municipios.json").write_text(txt_municipios, encoding="utf-8")
    manifesto = {
        "versao": 1,
        "gerado_em": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fonte": (
            {"nome": "IBGE — API de Localidades", "estados": URL_ESTADOS, "municipios": URL_MUNICIPIOS}
            if fonte == "ibge" else
            {"nome": "Espelho dos códigos do IBGE (kelvins/municipios-brasileiros)",
             "estados": ESPELHO + "estados.csv", "municipios": ESPELHO + "municipios.csv"}
        ),
        "sha256": hash_,
        "total_estados": len(estados),
        "total_municipios": len(municipios),
        "arquivos": {"estados": "estados.json", "municipios": "municipios.json"},
    }
    manifesto_p.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", default="data/ibge", type=Path)
    ap.add_argument("--estados-json", type=Path, help="usar arquivo local em vez da API (testes)")
    ap.add_argument("--municipios-json", type=Path, help="usar arquivo local em vez da API (testes)")
    a = ap.parse_args(argv)

    if a.estados_json and a.municipios_json:
        bruto_e = json.loads(a.estados_json.read_text())
        bruto_m = json.loads(a.municipios_json.read_text())
        fonte = "ibge"
    else:
        try:
            bruto_e, bruto_m, fonte = coletar()
        except ErroRede as e:
            raise SystemExit(str(e))
    estados = normalizar_estados(bruto_e)
    municipios = normalizar_municipios(bruto_m)
    validar(estados, municipios)
    mudou = gravar(a.saida, estados, municipios, fonte)
    print(f"{len(estados)} UFs, {len(municipios)} municípios ({fonte}) — {'atualizado' if mudou else 'sem mudanças'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
