#!/usr/bin/env python3
"""Gera a API pública (JSON estático) a partir de data/.

Roda no build do site (site/build.sh), que publica o resultado em
https://gabriel00lima.github.io/leis-indice/api/v1/. Nada aqui é commitado:
os arquivos são derivados de data/ a cada deploy.

    python3 api/gerar.py [--data data] [--saida _site/api]

Formato documentado em api/README.md e na página site/api.html.
"""
import argparse
import importlib.util
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSAO = 1
SITE = "https://gabriel00lima.github.io/leis-indice/"
ACERVO_RAW = "https://raw.githubusercontent.com/ctresb/leis/main/"
ACERVO_GITHUB = "https://github.com/ctresb/leis/blob/main/"

TIPOS_LIGACAO = ("cita", "altera", "revoga", "citada_por", "alterada_por", "revogada_por")
# Para cada tipo de ligação: (sentido da aresta, tipo da aresta em arestas.json).
ARESTA = {
    "cita": ("saida", "cita"), "altera": ("saida", "altera"), "revoga": ("saida", "revoga"),
    "citada_por": ("entrada", "cita"), "alterada_por": ("entrada", "altera"),
    "revogada_por": ("entrada", "revoga"),
}
CAMPOS_LISTA = ("id", "titulo", "tipo", "numero", "data", "revogada", "ementa")
EMENTA_BUSCA = 160  # caracteres da ementa em busca/<jurisdicao>.json


# ---------------------------------------------------------------- identificadores

def jurisdicao(id_):
    """Esfera e UF de uma norma a partir do id (caminho no ctresb/leis).

    federal/...            -> federal
    constituicao           -> federal (CF/1988)
    estaduais/SP/...       -> estadual, UF SP
    municipais/<UF>/<mun>  -> municipal
    """
    partes = id_.split("/")
    if id_ == "constituicao" or partes[0] == "federal":
        return {"esfera": "federal", "uf": None, "chave": "federal"}
    if partes[0] == "estaduais" and len(partes) > 1:
        uf = partes[1].upper()
        return {"esfera": "estadual", "uf": uf, "chave": uf.lower()}
    if partes[0] == "municipais" and len(partes) > 2:
        uf = partes[1].upper()
        return {"esfera": "municipal", "uf": uf, "chave": f"{uf.lower()}-{partes[2].lower()}"}
    return {"esfera": partes[0], "uf": None, "chave": partes[0]}


def lista_de(id_):
    """Lista (pasta) a que a norma pertence: o id sem o arquivo e sem a pasta do ano.

    federal/leis-ordinarias/1990/lei-8078-1990-09-11 -> federal/leis-ordinarias
    estaduais/SP/leis-ordinarias/1990/lei-1-1990-01-01 -> estaduais/SP/leis-ordinarias
    constituicao -> constituicao
    """
    partes = id_.split("/")[:-1]
    if partes and re.fullmatch(r"\d{4}", partes[-1]):
        partes = partes[:-1]
    return "/".join(partes) or id_


def prefixo_de(id_):
    """Prefixo do tipo, tirado do nome do arquivo: lei, del, lcp, emc..."""
    return id_.rsplit("/", 1)[-1].split("-", 1)[0]


def numero_limpo(numero):
    return re.sub(r"[^0-9A-Za-z]", "", str(numero or "")).lower()


def caminho_norma(id_):
    return f"normas/{id_}.json"


# ---------------------------------------------------------------- leitura de data/

def ler_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def entradas_da_parte(dados):
    """Uma parte de índice pode ser array de objetos ou {campos, linhas}."""
    if isinstance(dados, dict) and "linhas" in dados:
        campos = dados["campos"]
        return [dict(zip(campos, linha)) for linha in dados["linhas"]]
    return list(dados)


def carregar(data):
    data = Path(data)
    manifesto = ler_json(data / "index.json")
    if isinstance(manifesto, list):  # índice antigo: um array só
        manifesto = {"total": len(manifesto), "shards": []}
        normas = entradas_da_parte(ler_json(data / "index.json"))
        partes_adj = []
    else:
        normas = []
        partes_adj = []
        for shard in manifesto.get("shards", []):
            for e in entradas_da_parte(ler_json(data / shard["arquivo"])):
                e.setdefault("tipo", shard.get("tipo", ""))
                normas.append(e)
            if shard.get("adjacencia"):
                partes_adj.append(shard["adjacencia"])

    # Adjacência: pelas partes do índice e, para o que faltar, pelo links.json.
    if (data / "links.json").exists():
        links = ler_json(data / "links.json")
        if isinstance(links, dict) and "shards" in links:
            for s in links["shards"]:
                if s["arquivo"] not in partes_adj:
                    partes_adj.append(s["arquivo"])
    adjacencia = {}
    for arq in partes_adj:
        if (data / arq).exists():
            adjacencia.update(ler_json(data / arq))
    if not partes_adj and (data / "links.json").exists():
        links = ler_json(data / "links.json")
        if isinstance(links, dict) and "shards" not in links:
            adjacencia = links

    # Artigos envolvidos em cada ligação.
    dispositivos = {}
    arq_arestas = (manifesto.get("links") or {}).get("arestas", "arestas.json")
    if (data / arq_arestas).exists():
        for a in ler_json(data / arq_arestas).get("links", []):
            if a.get("dispositivos"):
                dispositivos[(a["de"], a["para"], a["tipo"])] = a["dispositivos"]

    return manifesto, normas, adjacencia, dispositivos


def apelidos():
    """Apelidos das leis principais (Código Civil, CLT...), de site/destaques.py."""
    caminho = RAIZ / "site" / "destaques.py"
    if not caminho.exists():
        return {}
    sys.dont_write_bytecode = True  # não deixar site/__pycache__ para o próximo build copiar
    try:
        spec = importlib.util.spec_from_file_location("destaques", caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {id_: apelido for id_, apelido, *_ in getattr(mod, "PRINCIPAIS", [])}
    except Exception as erro:  # o apelido é um extra; não derruba a API
        print(f"aviso: apelidos não carregados ({erro})", file=sys.stderr)
        return {}


# ---------------------------------------------------------------- montagem

def metadados(e):
    return {c: e.get(c, "" if c != "revogada" else False) for c in
            ("id", "titulo", "tipo", "numero", "data", "ementa", "revogada", "urn")}


def vizinho(id_, por_id, disp):
    e = por_id.get(id_)
    v = {"id": id_}
    if e:
        v.update(titulo=e.get("titulo", ""), tipo=e.get("tipo", ""), data=e.get("data", ""),
                 revogada=bool(e.get("revogada")), api=caminho_norma(id_))
    else:
        v["indexada"] = False
    if disp:
        v["dispositivos"] = disp
    return v


def montar_norma(e, por_id, adjacencia, dispositivos, apelido=None, base=SITE):
    id_ = e["id"]
    path = e.get("path") or f"{id_}.md"
    viz = adjacencia.get(id_, {})
    ligacoes = {}
    for tipo in TIPOS_LIGACAO:
        sentido, t = ARESTA[tipo]
        itens = []
        for outro in viz.get(tipo, []):
            chave = (id_, outro, t) if sentido == "saida" else (outro, id_, t)
            itens.append(vizinho(outro, por_id, dispositivos.get(chave)))
        ligacoes[tipo] = itens
    doc = {"versao": VERSAO}
    doc.update(metadados(e))
    if apelido:
        doc["apelido"] = apelido
    j = jurisdicao(id_)
    doc["jurisdicao"] = {"esfera": j["esfera"], "uf": j["uf"]}
    doc["lista"] = lista_de(id_)
    doc["texto"] = {"markdown": ACERVO_RAW + path, "github": ACERVO_GITHUB + path}
    doc["paginas"] = {"lei": f"{base}lei.html?id={id_}", "grafo": f"{base}grafo/?id={id_}"}
    doc["totais"] = {t: len(v) for t, v in ligacoes.items()}
    doc["ligacoes"] = ligacoes
    return doc


def linhas(normas, ementa_max=None):
    out = []
    for e in normas:
        ementa = e.get("ementa", "") or ""
        if ementa_max and len(ementa) > ementa_max:
            ementa = ementa[:ementa_max - 1].rstrip() + "…"
        out.append([e.get("id", ""), e.get("titulo", ""), e.get("tipo", ""), str(e.get("numero", "") or ""),
                    e.get("data", ""), bool(e.get("revogada")), ementa])
    return out


def escrever(caminho, obj, compacto=True):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")


def gerar(data, saida, base=SITE):
    manifesto, normas, adjacencia, dispositivos = carregar(data)
    normas.sort(key=lambda e: e["id"])
    por_id = {e["id"]: e for e in normas}
    nomes = apelidos()

    v1 = Path(saida) / f"v{VERSAO}"
    if v1.exists():
        shutil.rmtree(v1)
    v1.mkdir(parents=True)

    listas = defaultdict(list)
    refs = defaultdict(list)
    for e in normas:
        id_ = e["id"]
        escrever(v1 / caminho_norma(id_), montar_norma(e, por_id, adjacencia, dispositivos, nomes.get(id_), base))
        listas[lista_de(id_)].append(e)
        num = numero_limpo(e.get("numero"))
        if num:
            refs[(jurisdicao(id_)["chave"], prefixo_de(id_), num)].append(e)

    campos = list(CAMPOS_LISTA)
    resumo_listas = []
    for nome in sorted(listas):
        itens = listas[nome]
        tipos = sorted({e.get("tipo", "") for e in itens})
        j = jurisdicao(itens[0]["id"])
        arquivo = f"listas/{nome}.json"
        escrever(v1 / arquivo, {"versao": VERSAO, "lista": nome, "total": len(itens),
                                "campos": campos, "linhas": linhas(itens)})
        resumo_listas.append({"lista": nome, "arquivo": arquivo, "tipos": tipos, "total": len(itens),
                              "jurisdicao": j["chave"], "esfera": j["esfera"], "uf": j["uf"]})

    for (jur, prefixo, num), itens in refs.items():
        itens.sort(key=lambda e: e.get("data", ""))
        escrever(v1 / f"ref/{jur}/{prefixo}/{num}.json",
                 {"versao": VERSAO, "jurisdicao": jur, "prefixo": prefixo, "numero": num,
                  "normas": [{"id": e["id"], "titulo": e.get("titulo", ""), "tipo": e.get("tipo", ""),
                              "data": e.get("data", ""), "revogada": bool(e.get("revogada")),
                              "api": caminho_norma(e["id"])} for e in itens]})

    # Busca: uma parte por jurisdição, para quem só quer as federais não baixar as estaduais.
    por_jur = defaultdict(list)
    for e in normas:
        por_jur[jurisdicao(e["id"])["chave"]].append(e)
    for jur, itens in por_jur.items():
        escrever(v1 / f"busca/{jur}.json", {"versao": VERSAO, "jurisdicao": jur, "total": len(itens),
                                            "campos": campos, "linhas": linhas(itens, EMENTA_BUSCA)})

    jurisdicoes = defaultdict(lambda: {"total": 0, "listas": []})
    for l in resumo_listas:
        chave = l["jurisdicao"]
        jurisdicoes[chave]["esfera"] = l["esfera"]
        jurisdicoes[chave]["uf"] = l["uf"]
        jurisdicoes[chave]["total"] += l["total"]
        jurisdicoes[chave]["listas"].append(l["lista"])
        jurisdicoes[chave]["busca"] = f"busca/{chave}.json"

    total_ligacoes = sum(len(v.get(t, [])) for v in adjacencia.values() for t in ("cita", "altera", "revoga"))
    indice = {
        "versao": VERSAO,
        "gerado_em": manifesto.get("gerado_em"),
        "fonte": manifesto.get("fonte"),
        "base": f"{base}api/v{VERSAO}/",
        "documentacao": f"{base}api.html",
        "total": len(normas),
        "ligacoes": (manifesto.get("links") or {}).get("total", total_ligacoes),
        "jurisdicoes": dict(sorted(jurisdicoes.items())),
        "listas": resumo_listas,
        "rotas": {
            "norma": "normas/{id}.json",
            "lista": "listas/{lista}.json",
            "referencia": "ref/{jurisdicao}/{prefixo}/{numero}.json",
            "busca": "busca/{jurisdicao}.json",
        },
    }
    escrever(v1 / "index.json", indice, compacto=False)
    return indice


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(RAIZ / "data"))
    p.add_argument("--saida", default=str(RAIZ / "_site" / "api"))
    p.add_argument("--base", default=SITE, help="URL pública do site, com / no fim")
    a = p.parse_args()
    base = a.base if a.base.endswith("/") else a.base + "/"
    indice = gerar(a.data, a.saida, base)
    print(f"API gerada em {a.saida}/v{VERSAO}: {indice['total']} normas, {len(indice['listas'])} listas")


if __name__ == "__main__":
    main()
