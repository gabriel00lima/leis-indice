#!/usr/bin/env python3
"""Gera site/destaques.json a partir de data/: estatísticas do índice, leis
principais, mais citadas, mais alteradas, mais recentes e normas por década.

A página inicial lê esse arquivo para não precisar baixar o índice inteiro.
Roda no build do site (site/build.sh) e pode rodar à mão:

    python3 site/destaques.py [--data data] [--saida site/destaques.json]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Normas de referência mostradas na página inicial, com apelido e uma linha.
PRINCIPAIS = [
    ("constituicao", "Constituição Federal", "A lei maior do país: direitos fundamentais, organização do Estado e dos Poderes."),
    ("federal/leis-ordinarias/2002/lei-10406-2002-01-10", "Código Civil", "Pessoas, contratos, propriedade, família e sucessões."),
    ("federal/decretos-lei/1940/del-2848-1940-12-07", "Código Penal", "Crimes e penas."),
    ("federal/decretos-lei/1943/del-5452-1943-05-01", "CLT", "Consolidação das Leis do Trabalho."),
    ("federal/leis-ordinarias/1990/lei-8078-1990-09-11", "Código de Defesa do Consumidor", "Direitos de quem compra e deveres de quem vende."),
    ("federal/leis-ordinarias/2015/lei-13105-2015-03-16", "Código de Processo Civil", "Como tramitam os processos cíveis."),
    ("federal/decretos-lei/1941/del-3689-1941-10-03", "Código de Processo Penal", "Investigação e processo criminal."),
    ("federal/leis-ordinarias/1966/lei-5172-1966-10-25", "Código Tributário Nacional", "Regras gerais sobre tributos."),
    ("federal/leis-ordinarias/1990/lei-8069-1990-07-13", "Estatuto da Criança e do Adolescente", "Proteção integral a crianças e adolescentes."),
    ("federal/leis-ordinarias/1997/lei-9503-1997-09-23", "Código de Trânsito Brasileiro", "Trânsito, habilitação e infrações."),
    ("federal/leis-ordinarias/2018/lei-13709-2018-08-14", "LGPD", "Lei Geral de Proteção de Dados Pessoais."),
    ("federal/leis-ordinarias/2014/lei-12965-2014-04-23", "Marco Civil da Internet", "Direitos e deveres no uso da internet."),
    ("federal/leis-ordinarias/2006/lei-11340-2006-08-07", "Lei Maria da Penha", "Combate à violência doméstica contra a mulher."),
    ("federal/leis-ordinarias/2021/lei-14133-2021-04-01", "Nova Lei de Licitações", "Compras e contratos da administração pública."),
    ("federal/leis-complementares/2000/lcp-101-2000-05-04", "Lei de Responsabilidade Fiscal", "Limites de gasto e endividamento público."),
    ("federal/decretos-lei/1942/del-4657-1942-09-04", "LINDB", "Lei de Introdução às Normas do Direito Brasileiro."),
]

CAMPOS = ("id", "titulo", "tipo", "numero", "data", "ementa", "revogada")


def resumo(e, **extra):
    d = {k: e.get(k) for k in CAMPOS}
    if d["ementa"] and len(d["ementa"]) > 220:
        d["ementa"] = d["ementa"][:217].rstrip() + "…"
    d.update(extra)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(RAIZ / "data"))
    ap.add_argument("--saida", default=str(RAIZ / "site" / "destaques.json"))
    args = ap.parse_args()
    data = Path(args.data)

    manifesto = json.loads((data / "index.json").read_text(encoding="utf-8"))
    entradas = {}
    por_tipo = []
    for s in manifesto["shards"]:
        lista = json.loads((data / s["arquivo"]).read_text(encoding="utf-8"))
        for e in lista:
            entradas[e["id"]] = e
        por_tipo.append({
            "tipo": s.get("tipo"), "pasta": s.get("categoria"), "total": len(lista),
            "revogadas": sum(1 for e in lista if e.get("revogada")),
        })

    adj = {}
    links = json.loads((data / "links.json").read_text(encoding="utf-8"))
    for s in links.get("shards", []):
        caminho = data / s["arquivo"]
        if caminho.exists():
            adj.update(json.loads(caminho.read_text(encoding="utf-8")))

    def cont(i, chave):
        return len(adj.get(i, {}).get(chave, []))

    def top(chave, n):
        ids = sorted((i for i in entradas if cont(i, chave)), key=lambda i: (-cont(i, chave), i))[:n]
        return [resumo(entradas[i], total=cont(i, chave)) for i in ids]

    principais = []
    for i, apelido, descricao in PRINCIPAIS:
        if i in entradas:
            principais.append(resumo(entradas[i], apelido=apelido, descricao=descricao,
                                     citada_por=cont(i, "citada_por"), alterada_por=cont(i, "alterada_por")))

    datadas = [e for e in entradas.values() if e.get("data")]
    recentes = sorted(datadas, key=lambda e: (e["data"], e["id"]), reverse=True)[:8]
    decadas = Counter(int(e["data"][:4]) // 10 * 10 for e in datadas if e["data"][:4].isdigit())

    saida = {
        "gerado_em": manifesto.get("gerado_em"),
        "fonte": manifesto.get("fonte", {}),
        "total": len(entradas),
        "revogadas": sum(1 for e in entradas.values() if e.get("revogada")),
        "ligacoes": manifesto.get("links", {}).get("total"),
        "ligacoes_por_tipo": manifesto.get("links", {}).get("por_tipo", {}),
        "mais_antiga": min((e["data"] for e in datadas), default=None),
        "por_tipo": por_tipo,
        "por_decada": [{"decada": d, "total": decadas[d]} for d in sorted(decadas)],
        "principais": principais,
        "mais_citadas": top("citada_por", 10),
        "mais_alteradas": top("alterada_por", 10),
        "recentes": [resumo(e) for e in recentes],
    }
    Path(args.saida).write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"destaques: {len(entradas)} normas -> {args.saida}")


if __name__ == "__main__":
    main()
