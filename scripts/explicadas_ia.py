#!/usr/bin/env python3
"""Gera (ou refaz) um resumo da "Lei explicada" com a API da Anthropic.

Opcional: os resumos em site/explicadas/ são escritos e revisados à mão. Este
script serve para criar um rascunho de uma lei nova ou atualizar um resumo
depois de mudanças grandes na lei. O resultado sempre precisa de revisão humana:
o arquivo sai marcado com "origem: gerado com IA" e o site avisa isso ao leitor.

Precisa de ANTHROPIC_API_KEY e do pacote anthropic (pip install -r scripts/requirements-explicadas.txt).

Uso (na raiz do repositório):
  python3 scripts/explicadas_ia.py --slug cdc                    # refaz um resumo existente
  python3 scripts/explicadas_ia.py --slug cpc \\
      --lei federal/leis-ordinarias/2015/lei-13105-2015-03-16 --nome "Código de Processo Civil"

Depois rode python3 scripts/explicadas.py para conferir os artigos citados e
atualizar site/explicadas/index.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "site" / "explicadas"
RAW = "https://raw.githubusercontent.com/ctresb/leis/main/"
MODELO = "claude-opus-5-5"
EXEMPLO = PASTA / "cdc.md"  # resumo escrito à mão usado como modelo de estilo

INSTRUCOES = """Você escreve resumos de leis brasileiras em linguagem simples para leigos, em português do Brasil.

Regras:
- Use só o texto da lei enviado. Não invente artigos, prazos nem valores. Se algo depende de regulamento ou de outra lei, diga isso.
- Cite os artigos como links Markdown no formato [art. 49](#art-49); para artigo com letra, [art. 54-A](#art-54-a); para números com ponto de milhar, [art. 1.228](#art-1228). Cite só artigos que existem no texto e estão em vigor (não revogados).
- Para outra lei, use [Lei nº 9.099/1995](lei.html?ref=lei:9099:1995); para a Constituição, [Constituição, art. 7º](lei.html?id=constituicao#art-7).
- Frases curtas, sem juridiquês. Explique termos técnicos quando forem inevitáveis. Não dê conselho para um caso concreto.
- Siga exatamente a estrutura do exemplo: cabeçalho YAML entre linhas "---" e as seções "## Em poucas palavras", "## O que você precisa saber" (lista de tópicos com o tema em negrito), "## Situações comuns" (perguntas em negrito seguidas da resposta), opcionalmente "## Prazos que importam" (tabela) e "## Onde procurar ajuda".
- No cabeçalho, preencha lei, nome, sigla, ordem, resumo (uma frase), para_quem, revisado_em e origem exatamente como pedido.
- Responda só com o arquivo Markdown, começando por "---", sem texto antes ou depois e sem bloco de código."""


def baixar(lei_id: str) -> str:
    with urllib.request.urlopen(RAW + lei_id + ".md", timeout=120) as r:
        return r.read().decode("utf-8")


def cabecalho_existente(slug: str) -> dict:
    arq = PASTA / f"{slug}.md"
    if not arq.exists():
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", arq.read_text(encoding="utf-8"), re.S)
    campos = {}
    for linha in (m.group(1).splitlines() if m else []):
        kv = re.match(r"^([a-z_]+):\s*(.*)$", linha)
        if kv:
            campos[kv.group(1)] = kv.group(2).strip()
    return campos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="nome do arquivo em site/explicadas/ (sem .md)")
    ap.add_argument("--lei", help="id da lei no acervo (obrigatório para resumo novo)")
    ap.add_argument("--nome", help="nome popular da lei (obrigatório para resumo novo)")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9-]+", args.slug):
        print("--slug deve ter só letras minúsculas, números e hífen", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY não está definida; nada a fazer.", file=sys.stderr)
        return 2

    atual = cabecalho_existente(args.slug)
    lei = args.lei or atual.get("lei")
    nome = args.nome or atual.get("nome")
    if not lei or not nome:
        print("Para um resumo novo, informe --lei e --nome.", file=sys.stderr)
        return 2
    ordem = atual.get("ordem") or str(len(list(PASTA.glob("*.md"))) + 1)

    import anthropic  # importado aqui para o --help funcionar sem o pacote

    texto_lei = baixar(lei)
    exemplo = EXEMPLO.read_text(encoding="utf-8")
    hoje = dt.date.today().isoformat()
    pedido = (
        f"Escreva o resumo da lei abaixo.\n\nCabeçalho obrigatório:\n"
        f"lei: {lei}\nnome: {nome}\nordem: {ordem}\nrevisado_em: {hoje}\n"
        f"origem: gerado com IA ({MODELO}), falta revisão humana\n\n"
        f"<exemplo_de_resumo>\n{exemplo}\n</exemplo_de_resumo>\n\n"
        f"<texto_da_lei id=\"{lei}\">\n{texto_lei}\n</texto_da_lei>"
    )

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODELO,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=INSTRUCOES,
        messages=[{"role": "user", "content": pedido}],
    ) as stream:
        resposta = stream.get_final_message()

    if resposta.stop_reason == "refusal":
        print("O modelo recusou o pedido; nada foi gravado.", file=sys.stderr)
        return 1
    if resposta.stop_reason == "max_tokens":
        print("A resposta foi cortada por tamanho; nada foi gravado.", file=sys.stderr)
        return 1
    md = "".join(b.text for b in resposta.content if b.type == "text").strip()
    md = re.sub(r"^```(?:markdown)?\n|\n```$", "", md).strip()
    if not md.startswith("---\n") or "## Em poucas palavras" not in md:
        print("Resposta fora do formato esperado; nada foi gravado.", file=sys.stderr)
        return 1

    destino = PASTA / f"{args.slug}.md"
    destino.write_text(md + "\n", encoding="utf-8")
    uso = resposta.usage
    print(f"Gravado {destino.relative_to(RAIZ)} ({uso.input_tokens} tokens de entrada, {uso.output_tokens} de saída).")
    print("Revise o texto e rode: python3 scripts/explicadas.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
