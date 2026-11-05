#!/usr/bin/env python3
"""Constrói/atualiza o índice e as ligações entre normas em data/.

Cobre as normas federais principais e as leis estaduais de SP, RJ e MG
(ver ESCOPO_FEDERAL e ESCOPO_ESTADUAL).

Uso típico (é o que a GitHub Action faz):

    git clone --filter=blob:none --no-checkout --depth 1 \\
        https://github.com/ctresb/leis.git /tmp/leis
    python indice/construir.py --fonte /tmp/leis --saida data

O clone é "blobless": traz só as árvores (~60 MB), nenhum texto. O script
compara o SHA de cada arquivo do escopo com o que foi processado na última
execução (data/cache/) e baixa, via sparse checkout, apenas os arquivos novos
ou alterados. Na primeira execução (ou com --completo) baixa o escopo inteiro
(~230 MB das federais e ~650 MB das estaduais de SP, RJ e MG).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extrator  # noqa: E402

VERSAO_FORMATO = 1
# Aumente quando a lógica do extrator mudar: força reprocessar tudo.
VERSAO_EXTRATOR = 2

REPOSITORIO_FONTE = "ctresb/leis"

# Escopo indexado: Constituição, emendas, leis complementares, leis ordinárias
# e decretos-lei (onde estão os códigos: Penal, CLT, Processo Penal...).
ESCOPO_FEDERAL = [
    "constituicao.md",
    "federal/emendas-constitucionais",
    "federal/leis-complementares",
    "federal/leis-ordinarias",
    "federal/decretos-lei",
]

# Estados: as mesmas categorias, quando o acervo as tem. Os decretos estaduais
# (61 mil em SP, 44 mil em MG) ficam de fora para o índice continuar leve; ainda
# assim, citações a eles são resolvidas para o arquivo do acervo.
UFS = {"SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Minas Gerais"}
ESCOPO_ESTADUAL = {
    "SP": ["constituicao", "emendas-constitucionais", "leis-complementares", "leis-ordinarias",
           "decretos-lei", "decretos-lei-complementares"],
    "RJ": ["constituicao", "leis-ordinarias"],
    "MG": ["constituicao", "emendas-constitucionais", "leis-complementares", "leis-ordinarias",
           "leis-delegadas", "leis-constitucionais", "decretos-lei"],
}

ESCOPO = ESCOPO_FEDERAL + [
    f"estaduais/{uf}/{cat}" for uf, cats in ESCOPO_ESTADUAL.items() for cat in cats
]

PREFIXOS = {
    "constituicao": "constituicao",
    "emendas-constitucionais": "emc",
    "leis-complementares": "lcp",
    "leis-ordinarias": "lei",
    "decretos-lei": "del",
}

# Pasta de uma norma estadual -> prefixo que o extrator usa para o tipo citado.
# Os nomes de arquivo variam por estado (SP: lc-, ec-, dl-; MG: lcp-, emc-...),
# então o tipo vem da pasta.
PREFIXO_DA_PASTA = {
    "leis-ordinarias": "lei",
    "leis-complementares": "lcp",
    "emendas-constitucionais": "emc",
    "decretos-lei": "del",
    "decretos-lei-complementares": "dlc",
    "leis-delegadas": "ldl",
    "leis-constitucionais": "lct",
    "decretos": "dec",
    "decretos-legislativos": "dlg",
}

# Nome de arquivo estadual: "<prefixo>-<número>-<ano>[-<mm>-<dd>][-<sufixo>].md"
# (SP: lei-11727-2004-05-25-id51045, MG: lei-14365-2002, RJ: lei-9890-2022-9c9c09ff23).
NOME_ESTADUAL = re.compile(r"^[a-z]+-(?P<num>\d+)-(?P<ano>\d{4})(?:-(?P<mes>\d{2})-(?P<dia>\d{2}))?(?:-|\.md$)")

# Acima disso, é mais rápido baixar o escopo inteiro do que arquivo a arquivo.
LIMITE_INCREMENTAL = 4000

NOME_ARQUIVO = re.compile(
    r"^(?P<prefixo>[a-z]+)-(?P<num>\d+)(?:-(?P<reed>\d+))?-(?P<data>\d{4}-\d{2}-\d{2})(?:-s\d+)?\.md$"
)


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------
def git(fonte: Path, *args: str, entrada: str | None = None) -> str:
    r = subprocess.run(
        ["git", "-C", str(fonte), *args],
        input=entrada,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falhou:\n{r.stderr}")
    return r.stdout


def listar_escopo(fonte: Path) -> dict[str, str]:
    """{caminho: sha do blob} dos .md do escopo. Usa só árvores (não baixa textos)."""
    saida = git(fonte, "ls-tree", "-r", "HEAD", "--", *ESCOPO)
    arquivos = {}
    for linha in saida.splitlines():
        info, caminho = linha.split("\t", 1)
        _modo, tipo, sha = info.split()
        if tipo == "blob" and caminho.endswith(".md"):
            arquivos[caminho] = sha
    return arquivos


def listar_federal(fonte: Path) -> list[str]:
    """Todos os .md federais (fora do escopo inclusive), para resolver referências."""
    saida = git(fonte, "ls-tree", "-r", "--name-only", "HEAD", "--", "federal")
    return [
        c for c in saida.splitlines()
        if c.endswith(".md") and not c.split("/")[1].startswith("_")
        and not c.startswith("federal/anexos/")
    ]


def listar_estaduais(fonte: Path, uf: str) -> list[str]:
    """Todos os .md de um estado (inclusive fora do escopo), para resolver referências."""
    saida = git(fonte, "ls-tree", "-r", "--name-only", "HEAD", "--", f"estaduais/{uf}")
    return [c for c in saida.splitlines() if c.endswith(".md") and "/_" not in c]


def baixar(fonte: Path, caminhos: list[str], completo: bool) -> None:
    """Sparse checkout só do necessário (o git baixa os blobs em lote)."""
    if completo:
        padroes = [("/" + p + ("/" if not p.endswith(".md") else "")) for p in ESCOPO]
    else:
        padroes = ["/" + c for c in caminhos]
    git(fonte, "config", "core.sparseCheckout", "true")
    info = fonte / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "sparse-checkout").write_text("\n".join(padroes) + "\n", encoding="utf-8")
    git(fonte, "read-tree", "-mu", "HEAD")


# ---------------------------------------------------------------------------
# Resolução de referências (prefixo, número, ano) -> id
# ---------------------------------------------------------------------------
class Resolvedor:
    def __init__(self, caminhos: list[str]):
        self.tabela: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        for c in caminhos:
            m = NOME_ARQUIVO.match(c.rsplit("/", 1)[-1])
            if not m:
                continue
            num = m.group("num").lstrip("0") or "0"
            item = (m.group("data"), c[:-3])
            self.tabela[(m.group("prefixo"), num)].append(item)
            if m.group("reed"):
                self.tabela[(m.group("prefixo"), f"{num}-{m.group('reed')}")].append(item)
        for v in self.tabela.values():
            v.sort()

    def achar(self, prefixo: str, numero: str, ano: int | None, data_citante: str) -> str | None:
        candidatos = self.tabela.get((prefixo, numero))
        if not candidatos and "-" in numero:
            candidatos = self.tabela.get((prefixo, numero.split("-")[0]))
        if candidatos and ano:
            candidatos = [c for c in candidatos if c[0].startswith(str(ano))]
        if not candidatos:
            return None
        if len(candidatos) == 1:
            return candidatos[0][1]
        # Numeração que reinicia (ex.: LC nº 1 de 1962 e de 1967): a mais recente
        # anterior à norma que cita.
        anteriores = [c for c in candidatos if not data_citante or c[0] <= data_citante]
        return (anteriores[-1] if anteriores else candidatos[0])[1]

    def resolver(self, prefixo: str, numero: str, ano: int | None, data_citante: str) -> str:
        if prefixo == "constituicao":
            return "constituicao"
        return self.achar(prefixo, numero, ano, data_citante) or (
            f"externo:{prefixo}-{numero}" + (f"-{ano}" if ano else "")
        )


class ResolvedorEstadual(Resolvedor):
    """Normas de um estado, pelo nome do arquivo e pela pasta (que dá o tipo)."""

    def __init__(self, uf: str, caminhos: list[str]):
        self.uf = uf
        self.tabela = defaultdict(list)
        self.constituicao = None
        for c in caminhos:
            partes = c.split("/")
            if len(partes) < 4:
                continue
            if partes[2] == "constituicao":
                self.constituicao = c[:-3]
                continue
            prefixo = PREFIXO_DA_PASTA.get(partes[2])
            m = NOME_ESTADUAL.match(partes[-1])
            if not prefixo or not m:
                continue
            data = m.group("ano") + (f"-{m.group('mes')}-{m.group('dia')}" if m.group("mes") else "")
            self.tabela[(prefixo, m.group("num").lstrip("0") or "0")].append((data, c[:-3]))
        for v in self.tabela.values():
            v.sort()


def resolver_referencia(federal: Resolvedor, estaduais: dict, uf: str | None,
                        prefixo: str, numero: str, ano: int | None, data_citante: str) -> str | None:
    """Id da norma citada, ou None quando a referência deve ser ignorada.

    Numa norma federal, vale o resolvedor federal ("Lei estadual nº…" é ignorada).
    Numa norma estadual: "Lei federal nº…" e os códigos vão para a federal; o resto
    procura primeiro no próprio estado e depois nas federais. Sem achar em nenhum,
    vira "externo:<prefixo>-<número>[-<ano>]-<uf>": o acervo federal é quase completo
    nas leis, então uma lei que não está lá provavelmente é do estado.
    """
    base, _, esfera = prefixo.partition(":")
    if uf is None:
        if esfera == "estadual" or base == "constituicao-estadual":
            return None
        return federal.resolver(base, numero, ano, data_citante)
    if base == "constituicao":
        return "constituicao"
    est = estaduais.get(uf)
    if base == "constituicao-estadual":
        return est.constituicao if est else None
    if esfera == "federal":
        return federal.resolver(base, numero, ano, data_citante)
    achado = est.achar(base, numero, ano, data_citante) if est else None
    if not achado and esfera != "estadual":
        achado = federal.achar(base, numero, ano, data_citante)
    return achado or (f"externo:{base}-{numero}" + (f"-{ano}" if ano else "") + f"-{uf.lower()}")


# ---------------------------------------------------------------------------
# Arquivos de saída
# ---------------------------------------------------------------------------
def categoria(caminho: str) -> str:
    """'leis-ordinarias' (federal), 'constituicao' ou 'estaduais/SP/leis-ordinarias'."""
    if caminho == "constituicao.md":
        return "constituicao"
    partes = caminho.split("/")
    if partes[0] == "estaduais":
        return "/".join(partes[:3])
    return partes[1]


def uf_de(id_ou_caminho: str) -> str | None:
    partes = id_ou_caminho.split("/")
    return partes[1] if partes[0] == "estaduais" and len(partes) > 1 else None


def raiz_da_categoria(cat: str) -> str:
    """Prefixo dos ids da categoria (o que o site usa para achar o shard de um id)."""
    if cat == "constituicao" or cat.startswith("estaduais/"):
        return cat
    return "federal/" + cat


def json_linhas(obj) -> str:
    """JSON válido com um item por linha (diffs legíveis no git)."""
    if isinstance(obj, list):
        corpo = ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=False) for x in obj)
        return "[\n" + corpo + "\n]\n" if obj else "[]\n"
    if isinstance(obj, dict):
        corpo = ",\n".join(
            json.dumps(k, ensure_ascii=False) + ":" + json.dumps(v, ensure_ascii=False)
            for k, v in obj.items()
        )
        return "{\n" + corpo + "\n}\n" if obj else "{}\n"
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def escrever(caminho: Path, conteudo: str) -> bool:
    """Escreve só se mudou. Devolve True se mudou."""
    if caminho.exists() and caminho.read_text(encoding="utf-8") == conteudo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return True


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def construir(fonte: Path, saida: Path, completo: bool = False, baixar_textos: bool = True) -> dict:
    estado = ler_json(saida / "estado.json", {})
    if estado.get("versao_extrator") != VERSAO_EXTRATOR or estado.get("escopo") != ESCOPO:
        completo = True

    commit = git(fonte, "rev-parse", "HEAD").strip()
    atuais = listar_escopo(fonte)

    # Estado anterior: índice e cache de referências, por categoria.
    indice: dict[str, dict] = {}
    cache: dict[str, list] = {}  # caminho -> [sha, referencias]
    if not completo:
        for arq in sorted((saida / "index").rglob("*.json")):
            for e in ler_json(arq, []):
                indice[e["path"]] = e
        for arq in sorted((saida / "cache").rglob("*.json")):
            cache.update(ler_json(arq, {}))

    mudados = [c for c, sha in atuais.items() if c not in cache or cache[c][0] != sha]
    removidos = [c for c in cache if c not in atuais]
    for c in removidos:
        cache.pop(c, None)
        indice.pop(c, None)

    if mudados and baixar_textos:
        baixar(fonte, mudados, completo or len(mudados) > LIMITE_INCREMENTAL)

    for c in sorted(mudados):
        texto = (fonte / c).read_text(encoding="utf-8", errors="replace")
        meta, corpo = extrator.metadados(c, texto)
        uf = uf_de(c)
        indice[c] = {"id": c[:-3], "path": c, **meta, **({"uf": uf} if uf else {})}
        cache[c] = [atuais[c], extrator.extrair_referencias(corpo, meta["data"], estadual=bool(uf))]

    # --- agregação -----------------------------------------------------------
    resolvedor = Resolvedor(listar_federal(fonte))
    estaduais = {uf: ResolvedorEstadual(uf, listar_estaduais(fonte, uf)) for uf in ESCOPO_ESTADUAL}
    arestas: dict[tuple[str, str, str], set] = defaultdict(set)
    for c, (_sha, refs) in cache.items():
        esta = c[:-3]
        uf = uf_de(c)
        data_citante = indice.get(c, {}).get("data", "")
        for direcao, prefixo, numero, ano, tipo, disp in refs:
            outra = resolver_referencia(resolvedor, estaduais, uf, prefixo, numero, ano, data_citante)
            if outra is None:
                continue
            de, para = (esta, outra) if direcao == "sai" else (outra, esta)
            if de == para:
                continue
            arestas[(de, para, tipo)].update(disp)

    links = [
        {"de": de, "para": para, "tipo": tipo,
         "dispositivos": sorted(d, key=extrator._chave_artigo)}
        for (de, para, tipo), d in sorted(arestas.items())
    ]
    ids_indexados = {e["id"]: e for e in indice.values()}

    def arquivo_arestas(lista: list) -> str:
        envolvidos = sorted({l["de"] for l in lista} | {l["para"] for l in lista})
        leis_links = {
            i: {k: ids_indexados[i][k] for k in ("titulo", "tipo", "numero", "data", "ementa", "revogada")}
            for i in envolvidos if i in ids_indexados
        }
        return (
            '{"versao":' + str(VERSAO_FORMATO) + ',\n"leis":' + json_linhas(leis_links).rstrip()
            + ',\n"links":' + json_linhas(lista).rstrip() + "\n}\n"
        )

    vizinhos: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    inverso = {"cita": "citada_por", "altera": "alterada_por", "revoga": "revogada_por"}
    for l in links:
        vizinhos[l["de"]][l["tipo"]].add(l["para"])
        vizinhos[l["para"]][inverso[l["tipo"]]].add(l["de"])

    # --- escrita -------------------------------------------------------------
    mudou = False
    por_categoria: dict[str, list] = defaultdict(list)
    for c in sorted(indice):
        por_categoria[categoria(c)].append(indice[c])
    cats = [categoria(p) for p in ESCOPO]  # federais primeiro, depois SP, RJ, MG

    def adjacencia_de(entradas: list) -> dict:
        adj = {}
        for e in entradas:
            v = vizinhos.get(e["id"])
            if v:
                adj[e["id"]] = {
                    k: sorted(v.get(k, ()))
                    for k in ("cita", "altera", "revoga", "citada_por", "alterada_por", "revogada_por")
                }
        return adj

    shards = []
    for cat in cats:
        entradas = por_categoria.get(cat, [])
        uf = uf_de(cat)
        mudou |= escrever(saida / "index" / f"{cat}.json", json_linhas(entradas))
        tipos = sorted({e["tipo"] for e in entradas if e["tipo"]})
        pasta_cat = cat.split("/")[-1]
        shard = {
            "categoria": cat,
            "arquivo": f"index/{cat}.json",
            # Federais: uma adjacência por categoria. Estados: uma por UF.
            "adjacencia": f"adjacencia/estaduais/{uf}.json" if uf else f"adjacencia/{cat}.json",
            "tipo": min(tipos, key=len) if tipos else "",
            "prefixo": (PREFIXO_DA_PASTA.get(pasta_cat, "") if uf else PREFIXOS.get(cat, "")),
            "total": len(entradas),
            "esfera": "estadual" if uf else "federal",
            "raiz": raiz_da_categoria(cat),
        }
        if uf:
            shard["uf"] = uf
        if uf and pasta_cat == "constituicao":
            shard["prefixo"] = "constituicao-estadual"
        shards.append(shard)
        cache_cat = {c: cache[c] for c in sorted(cache) if categoria(c) == cat}
        mudou |= escrever(saida / "cache" / f"{cat}.json", json_linhas(cache_cat))
        if not uf:
            mudou |= escrever(saida / "adjacencia" / f"{cat}.json", json_linhas(adjacencia_de(entradas)))
    for uf in ESCOPO_ESTADUAL:
        entradas = [e for cat in cats if uf_de(cat) == uf for e in por_categoria.get(cat, [])]
        mudou |= escrever(saida / "adjacencia" / "estaduais" / f"{uf}.json", json_linhas(adjacencia_de(entradas)))

    # Arestas: as que tocam uma norma estadual ficam num arquivo por UF; o resto em arestas.json.
    links_por_uf: dict[str | None, list] = defaultdict(list)
    for l in links:
        links_por_uf[uf_de(l["de"]) or uf_de(l["para"])].append(l)
    mudou |= escrever(saida / "arestas.json", arquivo_arestas(links_por_uf.get(None, [])))
    for uf in ESCOPO_ESTADUAL:
        mudou |= escrever(saida / "arestas" / "estaduais" / f"{uf}.json", arquivo_arestas(links_por_uf.get(uf, [])))

    # links.json: manifesto das partes de adjacência (formato lido pelo site e pelo grafo).
    # "pasta" é o segundo trecho do id: a categoria nas federais, a UF nas estaduais.
    manifesto_links = {
        "versao": VERSAO_FORMATO,
        "shards": [{"arquivo": f"adjacencia/{cat}.json", "pasta": cat} for cat in cats if not uf_de(cat)]
        + [{"arquivo": f"adjacencia/estaduais/{uf}.json", "pasta": uf, "esfera": "estadual", "uf": uf}
           for uf in ESCOPO_ESTADUAL],
        "arestas": "arestas.json",
        "arestas_estaduais": {uf: f"arestas/estaduais/{uf}.json" for uf in ESCOPO_ESTADUAL},
    }
    mudou |= escrever(saida / "links.json", json.dumps(manifesto_links, ensure_ascii=False, indent=2) + "\n")

    agora = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    manifesto_antigo = ler_json(saida / "index.json", {})
    manifesto = {
        "versao": VERSAO_FORMATO,
        "gerado_em": manifesto_antigo.get("gerado_em", agora) if not mudou else agora,
        "fonte": {"repositorio": REPOSITORIO_FONTE, "commit": commit, "escopo": ESCOPO},
        "total": len(indice),
        "total_federal": sum(1 for c in indice if not uf_de(c)),
        "estaduais": {
            uf: {
                "nome": UFS[uf],
                "total": sum(1 for c in indice if uf_de(c) == uf),
                "links": len(links_por_uf.get(uf, [])),
                "arestas": f"arestas/estaduais/{uf}.json",
            }
            for uf in ESCOPO_ESTADUAL
        },
        "shards": shards,
        "links": {
            "arquivo": "links.json",
            "arestas": "arestas.json",
            "total": len(links),
            "por_tipo": {t: sum(1 for l in links if l["tipo"] == t) for t in ("cita", "altera", "revoga")},
        },
    }
    sem_data = lambda m: {k: v for k, v in m.items() if k != "gerado_em"}  # noqa: E731
    if mudou or sem_data(manifesto) != sem_data(manifesto_antigo):
        manifesto["gerado_em"] = agora
        mudou = True
    escrever(saida / "index.json", json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
    escrever(saida / "estado.json", json.dumps({
        "commit": commit,
        "versao_extrator": VERSAO_EXTRATOR,
        "escopo": ESCOPO,
    }, ensure_ascii=False, indent=2) + "\n")

    resumo = {
        "commit": commit,
        "completo": completo,
        "processados": len(mudados),
        "removidos": len(removidos),
        "normas": len(indice),
        "links": len(links),
        "mudou": mudou,
    }
    return resumo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonte", required=True, type=Path, help="clone blobless do ctresb/leis")
    ap.add_argument("--saida", default=Path("data"), type=Path)
    ap.add_argument("--completo", action="store_true", help="reprocessa tudo, ignorando o cache")
    args = ap.parse_args(argv)
    resumo = construir(args.fonte, args.saida, completo=args.completo)
    print(json.dumps(resumo, ensure_ascii=False))
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(f"mudou={'true' if resumo['mudou'] else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
