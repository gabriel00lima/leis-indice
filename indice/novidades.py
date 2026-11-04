#!/usr/bin/env python3
"""Registra em data/novidades.json o que mudou no acervo desde a última execução.

Roda na Action do índice logo depois de indice/construir.py. Compara o SHA de
cada arquivo no cache recém-gerado (data/cache/) com o do último commit deste
repositório (git show HEAD:data/cache/...) e anota um evento por norma:

- "nova": a norma entrou no acervo;
- "texto": o texto mudou. Quando dá, compara as duas versões artigo por
  artigo (com o mesmo código do monitor/) e guarda os artigos incluídos,
  alterados e removidos;
- "removida": o arquivo saiu do acervo.

O registro é a fonte dos feeds RSS por lei (site/feeds.py): alterações feitas
por outras leis já vêm das ligações em data/adjacencia/, e o que só aparece
como mudança de texto no acervo vem daqui.

    python indice/novidades.py --fonte /tmp/leis --data data
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "monitor"))
import monitor  # noqa: E402  (comparar(): diferença artigo por artigo)

# Quantas normas por execução ganham a comparação artigo por artigo. Cada uma
# baixa a versão antiga do arquivo (~0,5 s); acima disso fica só o evento.
LIMITE_COMPARACOES = 300
# Quanto do histórico fica guardado.
DIAS_GUARDADOS = 400
MAX_EVENTOS = 20000
# Artigos guardados por lista em cada evento (o total fica em "total_<lista>").
MAX_ARTIGOS = 40


def git(pasta: Path, *args: str, binario: bool = False):
    r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binario else r.stdout.decode("utf-8", errors="replace")


def shas_do_cache(arquivos: dict[str, str]) -> dict[str, str]:
    """{caminho: sha} a partir do conteúdo dos arquivos data/cache/<pasta>.json."""
    shas = {}
    for conteudo in arquivos.values():
        try:
            for caminho, (sha, _refs) in json.loads(conteudo).items():
                shas[caminho] = sha
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return shas


def cache_atual(data: Path) -> dict[str, str]:
    return shas_do_cache({p.name: p.read_text(encoding="utf-8") for p in sorted((data / "cache").glob("*.json"))})


def cache_anterior(repo: Path, data: Path, ref: str) -> dict[str, str] | None:
    """Cache do último commit. None se não houver (primeira execução)."""
    rel = data.resolve().relative_to(repo.resolve()).as_posix()
    try:
        nomes = git(repo, "ls-tree", "--name-only", f"{ref}:{rel}/cache").split()
    except RuntimeError:
        return None
    if not nomes:
        return None
    return shas_do_cache({n: git(repo, "show", f"{ref}:{rel}/cache/{n}") for n in nomes if n.endswith(".json")})


def texto_do_blob(fonte: Path, sha: str) -> str | None:
    """Conteúdo de um blob do acervo. No clone "blobless" o git baixa o blob na hora."""
    try:
        return git(fonte, "cat-file", "blob", sha, binario=True).decode("utf-8", errors="replace")
    except RuntimeError:
        return None


def comparar(fonte: Path, sha_antes: str, sha_depois: str) -> dict | None:
    antes, depois = texto_do_blob(fonte, sha_antes), texto_do_blob(fonte, sha_depois)
    if antes is None or depois is None:
        return None
    m = monitor.comparar(antes, depois)
    cab = {k: v for k, v in m["cabecalho"].items() if k not in {"versao_texto"}}
    mud = {"preambulo": m["preambulo_mudou"], "cabecalho": sorted(cab)}
    for k in ("incluidos", "alterados", "removidos"):
        mud[k] = m[k][:MAX_ARTIGOS]
        if len(m[k]) > MAX_ARTIGOS:
            mud["total_" + k] = len(m[k])  # a lista guardada é só o começo
    return mud


def ler_registro(caminho: Path) -> list[dict]:
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return bruto.get("eventos", []) if isinstance(bruto, dict) else []


def escrever_registro(caminho: Path, eventos: list[dict], commit: str) -> None:
    linhas = ",\n".join(json.dumps(e, ensure_ascii=False) for e in eventos)
    corpo = (
        '{"versao":1,\n"fonte":' + json.dumps({"repositorio": "ctresb/leis", "commit": commit})
        + ',\n"eventos":[\n' + linhas + ("\n" if eventos else "") + "]}\n"
    )
    caminho.write_text(corpo, encoding="utf-8")


def registrar(fonte: Path, data: Path, repo: Path, ref: str = "HEAD", hoje: str | None = None,
              comparar_textos: bool = True) -> dict:
    hoje = hoje or dt.date.today().isoformat()
    antes = cache_anterior(repo, data, ref)
    depois = cache_atual(data)
    arq = data / "novidades.json"
    eventos = ler_registro(arq)

    if antes is None:
        return {"novos": 0, "motivo": "sem cache anterior"}

    commit = ""
    try:
        commit = git(fonte, "rev-parse", "HEAD").strip()
    except RuntimeError:
        pass

    novos: list[dict] = []
    comparacoes = 0
    for caminho in sorted(set(antes) | set(depois)):
        a, d = antes.get(caminho), depois.get(caminho)
        if a == d:
            continue
        ev = {"em": hoje, "id": caminho[:-3], "evento": "texto" if a and d else ("nova" if d else "removida")}
        if commit:
            ev["commit"] = commit[:12]
        if a and d and comparar_textos and comparacoes < LIMITE_COMPARACOES:
            comparacoes += 1
            mud = comparar(fonte, a, d)
            if mud is not None:
                ev["mudanca"] = mud
        novos.append(ev)

    # Mais novos primeiro; a mesma norma pode ter vários eventos ao longo do tempo.
    limite = (dt.date.fromisoformat(hoje) - dt.timedelta(days=DIAS_GUARDADOS)).isoformat()
    todos = [e for e in novos + eventos if e.get("em", "") >= limite][:MAX_EVENTOS]
    if novos or todos != eventos or not arq.exists():
        escrever_registro(arq, todos, commit or "")
    return {
        "novos": len(novos),
        "nova": sum(e["evento"] == "nova" for e in novos),
        "texto": sum(e["evento"] == "texto" for e in novos),
        "removida": sum(e["evento"] == "removida" for e in novos),
        "comparados": comparacoes,
        "total": len(todos),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonte", required=True, type=Path, help="clone blobless do ctresb/leis")
    ap.add_argument("--data", default=Path("data"), type=Path)
    ap.add_argument("--repo", default=RAIZ, type=Path, help="repositório deste projeto (para ler HEAD)")
    ap.add_argument("--ref", default="HEAD")
    args = ap.parse_args(argv)
    print(json.dumps(registrar(args.fonte, args.data, args.repo, args.ref), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
