#!/usr/bin/env python3
"""Monta e confere a seção "Lei explicada" do site.

Lê os resumos em site/explicadas/*.md, confere o cabeçalho de cada um e gera
site/explicadas/index.json, que o site usa para listar os resumos.

Com rede (padrão), baixa o texto de cada lei do acervo ctresb/leis e confere se
cada artigo citado nos links "#art-N" existe de verdade, usando a mesma regra
que o site usa para criar as âncoras (js/lei.js, marcarArtigos).

Uso (na raiz do repositório):
  python3 scripts/explicadas.py              # gera index.json e confere os artigos
  python3 scripts/explicadas.py --verificar  # só confere; falha se index.json estiver desatualizado
  python3 scripts/explicadas.py --sem-rede   # pula a conferência dos artigos
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "site" / "explicadas"
SAIDA = PASTA / "index.json"
DATA = RAIZ / "data"
RAW = "https://raw.githubusercontent.com/ctresb/leis/main/"

OBRIGATORIOS = ["lei", "nome", "resumo", "revisado_em", "origem"]
CAMPOS_INDICE = ["slug", "lei", "nome", "sigla", "resumo", "para_quem", "revisado_em", "origem", "ordem"]
SECOES = ["Em poucas palavras", "O que você precisa saber"]

RE_FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)
# Mesma regra de js/lei.js: parágrafo que começa com **Art. N** (N pode ter ponto de milhar).
RE_ARTIGO = re.compile(r"^\*\*Art\.\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:[º°.])?(?:\s*-\s*([A-Z])\b)?", re.M)
# Links no resumo: (#art-5) aponta para a própria lei; (lei.html?id=X#art-5) para outra.
RE_LINK = re.compile(r"\]\((?:lei\.html\?id=([^)#\s]+))?#(art-[0-9a-z-]+)\)")


def ler_frontmatter(texto: str) -> tuple[dict, str]:
    m = RE_FRONT.match(texto)
    if not m:
        return {}, texto
    campos: dict = {}
    for linha in m.group(1).splitlines():
        kv = re.match(r"^([a-z_]+):\s*(.*)$", linha)
        if not kv:
            continue
        valor: object = kv.group(2).strip()
        if isinstance(valor, str) and len(valor) >= 2 and valor[0] == valor[-1] == '"':
            valor = json.loads(valor)
        elif isinstance(valor, str) and re.fullmatch(r"\d+", valor):
            valor = int(valor)
        campos[kv.group(1)] = valor
    return campos, texto[m.end():]


def ids_do_indice() -> set[str] | None:
    """Ids de data/index.json (array ou manifesto com partes). None se não houver índice."""
    raiz = DATA / "index.json"
    if not raiz.exists():
        return None
    dados = json.loads(raiz.read_text(encoding="utf-8"))
    partes = [dados] if isinstance(dados, list) else [
        json.loads((DATA / s["arquivo"]).read_text(encoding="utf-8")) for s in dados.get("shards", [])
    ]
    ids: set[str] = set()
    for parte in partes:
        if isinstance(parte, dict):
            pos = parte["campos"].index("id")
            ids.update(linha[pos] for linha in parte["linhas"])
        else:
            ids.update(e["id"] for e in parte)
    return ids


def ancoras(texto_lei: str) -> set[str]:
    vistos: set[str] = set()
    for m in RE_ARTIGO.finditer(texto_lei):
        vistos.add("art-" + m.group(1).replace(".", "") + ("-" + m.group(2).lower() if m.group(2) else ""))
    return vistos


_cache: dict[str, set[str]] = {}


def ancoras_da_lei(lei_id: str) -> set[str]:
    if lei_id not in _cache:
        url = RAW + lei_id + ".md"
        with urllib.request.urlopen(url, timeout=60) as r:
            _cache[lei_id] = ancoras(r.read().decode("utf-8"))
    return _cache[lei_id]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true", help="não grava; falha se index.json estiver desatualizado")
    ap.add_argument("--sem-rede", action="store_true", help="não confere os artigos citados no texto das leis")
    args = ap.parse_args()

    erros: list[str] = []
    ids = ids_do_indice()
    entradas = []
    slugs_por_lei: dict[str, str] = {}

    for arq in sorted(PASTA.glob("*.md")):
        slug = arq.stem
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            erros.append(f"{arq.name}: o nome do arquivo deve ter só letras minúsculas, números e hífen")
        campos, corpo = ler_frontmatter(arq.read_text(encoding="utf-8"))
        for c in OBRIGATORIOS:
            if not campos.get(c):
                erros.append(f"{arq.name}: falta o campo '{c}' no cabeçalho")
        for s in SECOES:
            if f"## {s}" not in corpo:
                erros.append(f"{arq.name}: falta a seção '## {s}'")
        lei = campos.get("lei", "")
        if lei in slugs_por_lei:
            erros.append(f"{arq.name}: a lei {lei} já tem resumo em {slugs_por_lei[lei]}.md")
        slugs_por_lei[lei] = slug
        if ids is not None and lei and lei != "constituicao" and lei not in ids:
            erros.append(f"{arq.name}: a lei '{lei}' não está no índice (data/)")

        citados = sorted({(alvo or lei, anc) for alvo, anc in RE_LINK.findall(corpo)})
        if not args.sem_rede:
            for alvo, anc in citados:
                try:
                    if anc not in ancoras_da_lei(alvo):
                        erros.append(f"{arq.name}: o artigo #{anc} não existe em {alvo}")
                except OSError as e:
                    erros.append(f"{arq.name}: não deu para baixar {alvo} ({e})")

        entrada = {k: campos.get(k) for k in CAMPOS_INDICE if k != "slug"}
        entrada["slug"] = slug
        entrada["artigos_citados"] = len({a for alvo, a in citados if alvo == lei})
        entradas.append({k: entrada[k] for k in CAMPOS_INDICE + ["artigos_citados"] if entrada.get(k) is not None})

    entradas.sort(key=lambda e: (e.get("ordem", 999), e["nome"]))
    novo = json.dumps({"explicadas": entradas}, ensure_ascii=False, indent=2) + "\n"

    if erros:
        print("Problemas encontrados:", file=sys.stderr)
        for e in erros:
            print(" -", e, file=sys.stderr)
        return 1

    atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
    if args.verificar:
        if atual != novo:
            print("site/explicadas/index.json está desatualizado: rode python3 scripts/explicadas.py", file=sys.stderr)
            return 1
        print(f"{len(entradas)} resumos conferidos.")
        return 0
    if atual != novo:
        SAIDA.write_text(novo, encoding="utf-8")
    print(f"{len(entradas)} resumos conferidos; index.json {'atualizado' if atual != novo else 'sem mudanças'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
