"""Monitor de mudanças em leis do acervo ctresb/leis.

Lê a lista de leis em monitor/acompanhar.txt e, para cada uma, pergunta à API
do GitHub se houve commits novos naquele arquivo desde a última verificação.
Quando há, baixa só as duas versões daquele arquivo, compara artigo por artigo
e abre uma issue neste repositório com um resumo. Nada do acervo é clonado.

O estado (último commit visto de cada lei) fica em monitor/estado.json.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FONTE = "ctresb/leis"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
AQUI = Path(__file__).resolve().parent
LISTA = AQUI / "acompanhar.txt"
ESTADO = AQUI / "estado.json"
MODELO = "claude-opus-5-5"
LIMITE_DIFF = 60_000  # caracteres de diff enviados ao resumo


# ---------------------------------------------------------------- HTTP / GitHub

def _req(url: str, *, metodo: str = "GET", corpo: dict | None = None, raw: bool = False):
    headers = {"User-Agent": "leis-indice-monitor"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dados, headers=headers, method=metodo)
    with urllib.request.urlopen(req, timeout=60) as r:
        conteudo = r.read()
    return conteudo.decode("utf-8") if raw else json.loads(conteudo)


def commits_do_arquivo(caminho: str, limite: int = 100) -> list[dict]:
    """Commits mais recentes que tocaram o arquivo, do mais novo ao mais velho."""
    q = urllib.parse.urlencode({"path": caminho, "per_page": limite})
    return _req(f"{API}/repos/{FONTE}/commits?{q}")


def baixar(caminho: str, sha: str) -> str | None:
    url = f"{RAW}/{FONTE}/{sha}/{urllib.parse.quote(caminho)}"
    try:
        return _req(url, raw=True)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # arquivo não existia (ou foi removido) nesse commit
        raise


def abrir_issue(titulo: str, corpo: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    r = _req(f"{API}/repos/{repo}/issues", metodo="POST",
             corpo={"title": titulo, "body": corpo, "labels": ["mudança de lei"]})
    return r["html_url"]


# ---------------------------------------------------------------- comparação

RE_ART = re.compile(r"^\*\*(Art\.\s*[\dA-Za-zºo°\-]+\.?)\*\*")


def separar(texto: str) -> tuple[dict, str, dict[str, str]]:
    """Separa cabeçalho YAML, preâmbulo e artigos ({"Art. 4º": texto})."""
    cab: dict[str, str] = {}
    corpo = texto
    if texto.startswith("---\n"):
        fim = texto.find("\n---", 4)
        if fim != -1:
            for linha in texto[4:fim].splitlines():
                if ":" in linha and not linha.startswith(" "):
                    k, v = linha.split(":", 1)
                    cab[k.strip()] = v.strip().strip('"')
            corpo = texto[fim + 4:].lstrip("\n")

    artigos: dict[str, str] = {}
    preambulo: list[str] = []
    atual: str | None = None
    for linha in corpo.splitlines():
        m = RE_ART.match(linha)
        if m:
            atual = re.sub(r"\s+", " ", m.group(1)).rstrip(".")
            # artigos repetidos (ex.: texto revogado mantido) ganham sufixo
            base, n = atual, 2
            while atual in artigos:
                atual, n = f"{base} ({n})", n + 1
            artigos[atual] = linha + "\n"
        elif atual:
            artigos[atual] += linha + "\n"
        else:
            preambulo.append(linha)
    return cab, "\n".join(preambulo), artigos


def comparar(antigo: str, novo: str) -> dict:
    cab_a, pre_a, art_a = separar(antigo)
    cab_n, pre_n, art_n = separar(novo)
    cab_mudou = {
        k: (cab_a.get(k), cab_n.get(k))
        for k in sorted(set(cab_a) | set(cab_n))
        if cab_a.get(k) != cab_n.get(k) and k not in {"baixado_em", "capturado_em_fonte"}
    }
    return {
        "cabecalho": cab_mudou,
        "preambulo_mudou": pre_a.strip() != pre_n.strip(),
        "incluidos": [a for a in art_n if a not in art_a],
        "removidos": [a for a in art_a if a not in art_n],
        "alterados": [a for a in art_n if a in art_a and art_a[a].strip() != art_n[a].strip()],
    }


def diff_unificado(antigo: str, novo: str) -> str:
    return "".join(difflib.unified_diff(
        antigo.splitlines(keepends=True), novo.splitlines(keepends=True),
        "antes", "depois", n=1))


def resumo_simples(mud: dict) -> str:
    """Resumo sem IA, sempre disponível."""
    partes = []
    if mud["incluidos"]:
        partes.append(f"Artigos incluídos: {', '.join(mud['incluidos'])}.")
    if mud["alterados"]:
        partes.append(f"Artigos com texto alterado: {', '.join(mud['alterados'])}.")
    if mud["removidos"]:
        partes.append(f"Artigos que saíram do texto: {', '.join(mud['removidos'])}.")
    if mud["preambulo_mudou"]:
        partes.append("O trecho antes do primeiro artigo (título, ementa ou preâmbulo) mudou.")
    for k, (a, n) in mud["cabecalho"].items():
        if a is None:
            partes.append(f"Novo campo no cabeçalho: `{k}`.")
        elif n is None:
            partes.append(f"Campo removido do cabeçalho: `{k}`.")
        else:
            partes.append(f"Campo `{k}` mudou de `{a}` para `{n}`.")
    return "\n".join(f"- {p}" for p in partes) or "- Só mudanças de formatação ou espaços."


def resumo_claude(titulo: str, diff: str) -> str | None:
    """Resumo em linguagem simples, se ANTHROPIC_API_KEY estiver configurada."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    if len(diff) > LIMITE_DIFF:
        diff = diff[:LIMITE_DIFF] + "\n[... diff cortado por tamanho ...]"
    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=MODELO,
            max_tokens=4000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=(
                "Você explica mudanças em textos de leis brasileiras para leigos. "
                "Responda em português do Brasil, em 3 a 6 tópicos curtos, dizendo o que mudou "
                "e o efeito prático. Cite os artigos afetados e a lei que fez a alteração, se aparecer "
                "no texto. Se a mudança for só de formatação, metadados ou correção técnica do acervo, "
                "diga isso claramente em uma frase. Não invente nada que não esteja no diff."
            ),
            messages=[{"role": "user", "content": f"Norma: {titulo}\n\nDiff (antes → depois):\n\n{diff}"}],
        )
    except Exception as e:  # erro de API ou SDK antigo: cai no resumo simples
        print(f"  aviso: resumo com IA falhou ({e.__class__.__name__}); usando resumo simples")
        return None
    if resp.stop_reason == "refusal":
        return None
    texto = "".join(b.text for b in resp.content if b.type == "text").strip()
    return texto or None


# ---------------------------------------------------------------- execução

def ler_lista() -> list[str]:
    caminhos = []
    for linha in LISTA.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            caminhos.append(linha)
    return caminhos


def montar_relatorio(caminho: str, sha_a: str, sha_n: str, commits: list[dict],
                     antigo: str | None, novo: str | None) -> tuple[str, str]:
    titulo_lei = caminho
    if novo or antigo:
        titulo_lei = separar(novo or antigo)[0].get("titulo", caminho)
    link = f"https://github.com/{FONTE}/blob/{sha_n}/{caminho}"
    comp = f"https://github.com/{FONTE}/compare/{sha_a[:12]}...{sha_n[:12]}"
    lista_commits = "\n".join(
        f"- [{c['sha'][:8]}](https://github.com/{FONTE}/commit/{c['sha']}) "
        f"{c['commit']['message'].splitlines()[0]}" for c in commits)

    if novo is None:
        resumo = "- O arquivo foi **removido ou movido** no acervo. Atualize o caminho em `monitor/acompanhar.txt`."
        diff = ""
    elif antigo is None:
        resumo = "- O arquivo passou a existir no acervo."
        diff = ""
    else:
        diff = diff_unificado(antigo, novo)
        resumo = resumo_claude(titulo_lei, diff) or resumo_simples(comparar(antigo, novo))

    corpo = (
        f"**{titulo_lei}** mudou no acervo.\n\n"
        f"### Resumo\n\n{resumo}\n\n"
        f"### Links\n\n- [Texto atual]({link})\n- [Comparação completa]({comp})\n\n"
        f"### Commits\n\n{lista_commits}\n"
    )
    if diff:
        corte = diff if len(diff) < 20_000 else diff[:20_000] + "\n[... cortado ...]\n"
        corpo += f"\n<details><summary>Diff</summary>\n\n```diff\n{corte}```\n</details>\n"
    return f"Mudança: {titulo_lei}", corpo


def verificar(caminho: str, visto: str | None, *, abrir: bool) -> str | None:
    commits = commits_do_arquivo(caminho)
    if not commits:
        print(f"! {caminho}: nenhum commit encontrado (caminho errado?)")
        return visto
    mais_novo = commits[0]["sha"]
    if visto is None:
        print(f"+ {caminho}: passou a ser acompanhado em {mais_novo[:8]}")
        return mais_novo
    if mais_novo == visto:
        print(f"= {caminho}: sem mudanças")
        return visto

    novos = []
    for c in commits:
        if c["sha"] == visto:
            break
        novos.append(c)
    print(f"* {caminho}: {len(novos)} commit(s) novo(s)")
    antigo, novo = baixar(caminho, visto), baixar(caminho, mais_novo)
    titulo, corpo = montar_relatorio(caminho, visto, mais_novo, novos, antigo, novo)
    if abrir:
        print(f"  issue: {abrir_issue(titulo, corpo)}")
    else:
        print(f"\n--- {titulo} ---\n{corpo}\n")
    return mais_novo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sem-issue", action="store_true",
                    help="só imprime o relatório, não abre issue")
    args = ap.parse_args()

    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    abrir = not args.sem_issue and "GITHUB_REPOSITORY" in os.environ
    erros = 0
    for caminho in ler_lista():
        try:
            estado[caminho] = verificar(caminho, estado.get(caminho), abrir=abrir)
        except Exception as e:  # uma lei com problema não derruba as outras
            erros += 1
            print(f"! {caminho}: erro {e!r}")
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
