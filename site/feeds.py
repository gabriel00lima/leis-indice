#!/usr/bin/env python3
"""Gera um feed RSS por norma (feed/<id>.xml) e um feed geral (feed/novidades.xml).

É o que o botão "Seguir" da página da lei entrega: o link do feed, para usar
num leitor de RSS, num serviço que manda o feed por e-mail ou num bot do
Telegram. Tudo estático, gerado no build do site (site/build.sh).

Cada feed de norma junta, do mais novo ao mais velho:

- as normas que a alteraram ou revogaram (data/adjacencia/ + data/arestas.json),
  datadas pela publicação da norma que alterou;
- as mudanças de texto no acervo registradas pela Action do índice
  (data/novidades.json, gerado por indice/novidades.py), com os artigos
  incluídos, alterados e removidos;
- os avisos do monitor (monitor/novidades.json), com o resumo e o link da issue.

    python3 site/feeds.py --site _site [--url https://.../leis-indice/] [--monitor monitor/novidades.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paginas import (  # noqa: E402
    URL_PADRAO, NOME_SITE, ID_CONSTITUICAO, carregar_entradas, ler_apelidos, titulo_norma, frase, cortar, data_br,
)

RAIZ = Path(__file__).resolve().parent.parent
ACERVO = "https://github.com/ctresb/leis"
MAX_ITENS = 30
MAX_GERAL = 60
# No feed geral, um dia com mais mudanças de texto que isso vira um item só.
AGRUPAR_A_PARTIR_DE = 8
# Janela para casar um aviso do monitor com a mudança de texto do mesmo arquivo.
JANELA_MONITOR = dt.timedelta(days=3)

NOMES = {"lei": "Lei", "lcp": "Lei Complementar", "del": "Decreto-Lei", "dec": "Decreto",
         "dlg": "Decreto Legislativo", "mpv": "Medida Provisória", "emc": "Emenda Constitucional",
         "ldl": "Lei Delegada", "ecr": "Emenda Constitucional de Revisão"}
RE_ID = re.compile(r"/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-(\d{2})-(\d{2})$")
RE_ID_VALIDO = re.compile(r"[a-z0-9][a-z0-9/_.\-]*")


# ---------------------------------------------------------------- utilidades

def rotulo_do_id(id_: str) -> str:
    """O mesmo de rotuloDoId() em site/js/dados.js."""
    if id_ == ID_CONSTITUICAO:
        return "Constituição Federal de 1988"
    m = RE_ID.search(id_)
    if not m:
        return id_.rsplit("/", 1)[-1]
    n = f"{int(m.group(2)):,}".replace(",", ".")
    return f"{NOMES.get(m.group(1), m.group(1))} nº {n}/{m.group(3)}"


def data_do_id(id_: str) -> str:
    m = RE_ID.search(id_)
    return f"{m.group(3)}-{m.group(4)}-{m.group(5)}" if m else ""


def data_rss(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso[:10])
    except ValueError:
        d = dt.date(1970, 1, 1)
    # Meio-dia em Brasília: o dia não "volta" em leitores de outros fusos.
    return format_datetime(dt.datetime(d.year, d.month, d.day, 15, tzinfo=dt.timezone.utc))


def lista_artigos(artigos: list[str], maximo: int = 12, total: int | None = None) -> str:
    artigos = [a.replace("Art.", "art.") for a in artigos]
    total = max(total or 0, len(artigos))
    if total > maximo:
        return ", ".join(artigos[:maximo]) + f" e mais {total - maximo}"
    return ", ".join(artigos)


def html_de_markdown_simples(texto: str) -> str:
    """Resumos do monitor vêm em tópicos Markdown ("- ..."). Vira <ul> simples."""
    itens, soltos = [], []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        linha = re.sub(r"\*\*(.+?)\*\*", r"\1", linha).replace("`", "")
        if linha[:2] in ("- ", "* "):
            itens.append(f"<li>{escape(linha[2:])}</li>")
        else:
            soltos.append(f"<p>{escape(linha)}</p>")
    return "".join(soltos) + (f"<ul>{''.join(itens)}</ul>" if itens else "")


def descrever_mudanca(mud: dict | None) -> str:
    if not mud:
        return "<p>O arquivo desta norma mudou no acervo.</p>"
    partes = []
    if mud.get("incluidos"):
        partes.append(f"Artigos incluídos: {lista_artigos(mud['incluidos'], total=mud.get('total_incluidos'))}.")
    if mud.get("alterados"):
        partes.append(f"Artigos com texto alterado: {lista_artigos(mud['alterados'], total=mud.get('total_alterados'))}.")
    if mud.get("removidos"):
        partes.append(f"Artigos que saíram do texto: {lista_artigos(mud['removidos'], total=mud.get('total_removidos'))}.")
    if mud.get("preambulo"):
        partes.append("O trecho antes do primeiro artigo (título, ementa ou preâmbulo) mudou.")
    if not partes:
        return "<p>Só formatação ou dados do cabeçalho do acervo; o texto dos artigos é o mesmo.</p>"
    return "<ul>" + "".join(f"<li>{escape(p)}</li>" for p in partes) + "</ul>"


def item_xml(it: dict) -> str:
    return (
        "<item>"
        f"<title>{escape(it['titulo'])}</title>"
        f"<link>{escape(it['link'])}</link>"
        f"<guid isPermaLink=\"false\">{escape(it['guid'])}</guid>"
        f"<pubDate>{data_rss(it['data'])}</pubDate>"
        f"<description>{escape(it['descricao'])}</description>"
        "</item>"
    )


def feed_xml(titulo: str, link: str, descricao: str, url_feed: str, itens: list[dict], data_padrao: str) -> str:
    ultima = itens[0]["data"] if itens else data_padrao
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"<title>{escape(titulo)}</title>\n"
        f"<link>{escape(link)}</link>\n"
        f"<description>{escape(descricao)}</description>\n"
        "<language>pt-BR</language>\n"
        f'<atom:link href="{escape(url_feed)}" rel="self" type="application/rss+xml"/>\n'
        f"<lastBuildDate>{data_rss(ultima)}</lastBuildDate>\n"
        + "".join(item_xml(i) + "\n" for i in itens)
        + "</channel>\n</rss>\n"
    )


def ler_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


# ---------------------------------------------------------------- geração

class Gerador:
    def __init__(self, data: Path, url_site: str, apelidos: dict, monitor: list[dict]):
        self.url = url_site
        self.apelidos = apelidos
        grupos, _ = carregar_entradas(data)
        self.normas = {e["id"]: e for _, entradas in grupos for e in entradas if e.get("id")}
        self.shards = [s for s, _ in grupos if s]

        self.adj: dict[str, dict] = {}
        for s in self.shards:
            if s.get("adjacencia"):
                self.adj.update(ler_json(data / s["adjacencia"], {}))

        # Artigos atingidos por cada alteração/revogação: (de, para, tipo) -> [art.]
        self.disp: dict[tuple, list] = {}
        for l in ler_json(data / "arestas.json", {}).get("links", []):
            if l.get("tipo") in ("altera", "revoga") and l.get("dispositivos"):
                self.disp[(l["de"], l["para"], l["tipo"])] = l["dispositivos"]

        self.eventos: dict[str, list] = defaultdict(list)
        self.todos_eventos = ler_json(data / "novidades.json", {}).get("eventos", [])
        for ev in self.todos_eventos:
            self.eventos[ev.get("id", "")].append(ev)
        self.monitor: dict[str, list] = defaultdict(list)
        for av in monitor:
            self.monitor[av.get("id", "")].append(av)

    def link_lei(self, id_: str) -> str:
        if id_ in self.normas:
            return f"{self.url}lei/{id_}"
        return f"{self.url}lei.html?id={id_}"

    def nome(self, id_: str) -> str:
        e = self.normas.get(id_)
        nome = titulo_norma(e) if e else rotulo_do_id(id_)
        apelido = self.apelidos.get(id_)
        return f"{apelido} ({nome})" if apelido and apelido != nome else nome

    def itens_da_norma(self, id_: str) -> list[dict]:
        itens = []
        v = self.adj.get(id_, {})
        for tipo, chave in (("altera", "alterada_por"), ("revoga", "revogada_por")):
            for outra in v.get(chave, []):
                if outra.startswith("externo:"):
                    continue
                e = self.normas.get(outra)
                data = (e or {}).get("data") or data_do_id(outra)
                if not data:
                    continue
                disp = self.disp.get((outra, id_, tipo), [])
                rotulo = self.nome(outra)
                if tipo == "altera":
                    titulo = f"Alterada por {rotulo}"
                elif disp:
                    titulo = f"Revogação parcial por {rotulo}"
                else:
                    titulo = f"Revogada por {rotulo}"
                desc = ""
                if disp:
                    desc += f"<p>Dispositivos atingidos: {escape(lista_artigos(disp))}.</p>"
                if e and e.get("ementa"):
                    desc += f"<p>{escape(cortar(frase(e['ementa']), 400))}</p>"
                desc += f"<p>Publicada em {escape(data_br(data))}.</p>"
                itens.append({"titulo": titulo, "link": self.link_lei(outra), "data": data,
                              "guid": f"{tipo}:{outra}:{id_}", "descricao": desc})

        avisos = list(self.monitor.get(id_, []))
        for ev in self.eventos.get(id_, []):
            em = ev.get("em", "")
            if ev.get("evento") == "texto":
                desc = descrever_mudanca(ev.get("mudanca"))
                link = self.link_lei(id_)
                titulo = "Texto atualizado no acervo"
                # Aviso do monitor sobre a mesma mudança: usa o resumo dele e o link da issue.
                par = next((a for a in avisos if _perto(a.get("em", ""), em)), None)
                if par:
                    avisos.remove(par)
                    desc = html_de_markdown_simples(par.get("resumo", "")) or desc
                    if par.get("issue"):
                        desc += f'<p><a href="{escape(par["issue"])}">Comparação e diff completos</a></p>'
            elif ev.get("evento") == "nova":
                titulo, desc, link = "Entrou no acervo", "<p>O texto desta norma passou a fazer parte do acervo.</p>", self.link_lei(id_)
            elif ev.get("evento") == "removida":
                titulo, desc, link = "Saiu do acervo", "<p>O arquivo desta norma foi removido ou movido no acervo.</p>", f"{ACERVO}/commits/main/{id_}.md"
            else:
                continue
            desc += f'<p><a href="{escape(ACERVO)}/commits/main/{escape(id_)}.md">Histórico do arquivo no acervo</a></p>'
            itens.append({"titulo": titulo, "link": link, "data": em, "descricao": desc,
                          "guid": f"{ev.get('evento')}:{id_}:{em}:{ev.get('commit', '')}"})
        for a in avisos:
            desc = html_de_markdown_simples(a.get("resumo", ""))
            itens.append({"titulo": "Texto atualizado no acervo", "link": a.get("issue") or self.link_lei(id_),
                          "data": a.get("em", ""), "descricao": desc, "guid": f"monitor:{id_}:{a.get('em', '')}"})

        itens.sort(key=lambda i: (i["data"], i["guid"]), reverse=True)
        return itens[:MAX_ITENS]

    def feed_da_norma(self, id_: str) -> str:
        e = self.normas[id_]
        nome = self.nome(id_)
        return feed_xml(
            f"{nome} · {NOME_SITE}",
            self.link_lei(id_),
            f"Alterações, revogações e mudanças no texto de {titulo_norma(e)}, acompanhadas pelo {NOME_SITE}.",
            f"{self.url}feed/{id_}.xml",
            self.itens_da_norma(id_),
            e.get("data") or "1970-01-01",
        )

    def feed_geral(self) -> str:
        itens = []
        recentes = sorted((e for e in self.normas.values() if e.get("data")), key=lambda e: (e["data"], e["id"]), reverse=True)
        for e in recentes[:30]:
            desc = f"<p>{escape(cortar(frase(e.get('ementa')), 400))}</p>" if e.get("ementa") else ""
            itens.append({"titulo": f"Nova norma: {self.nome(e['id'])}", "link": self.link_lei(e["id"]),
                          "data": e["data"], "guid": f"norma:{e['id']}", "descricao": desc})

        por_dia = defaultdict(list)
        for ev in self.todos_eventos:
            if ev.get("evento") == "texto" and ev.get("id") in self.normas:
                por_dia[ev["em"]].append(ev)
        for dia, evs in por_dia.items():
            if len(evs) >= AGRUPAR_A_PARTIR_DE:
                lis = "".join(f'<li><a href="{escape(self.link_lei(ev["id"]))}">{escape(self.nome(ev["id"]))}</a></li>'
                              for ev in evs[:40])
                resto = f"<p>E mais {len(evs) - 40}.</p>" if len(evs) > 40 else ""
                itens.append({"titulo": f"{len(evs)} normas tiveram o texto atualizado no acervo",
                              "link": f"{ACERVO}/commits/main", "data": dia, "guid": f"texto-dia:{dia}:{len(evs)}",
                              "descricao": f"<ul>{lis}</ul>{resto}"})
            else:
                for ev in evs:
                    itens.append({"titulo": f"Texto atualizado: {self.nome(ev['id'])}", "link": self.link_lei(ev["id"]),
                                  "data": dia, "guid": f"texto:{ev['id']}:{dia}:{ev.get('commit', '')}",
                                  "descricao": descrever_mudanca(ev.get("mudanca"))})
        itens.sort(key=lambda i: (i["data"], i["guid"]), reverse=True)
        return feed_xml(f"Novidades · {NOME_SITE}", self.url,
                        "Normas federais que entraram no acervo e mudanças de texto, todo dia.",
                        f"{self.url}feed/novidades.xml", itens[:MAX_GERAL], "1970-01-01")


def _perto(a: str, b: str) -> bool:
    try:
        return abs(dt.date.fromisoformat(a) - dt.date.fromisoformat(b)) <= JANELA_MONITOR
    except ValueError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="_site", type=Path, help="pasta do site já montado (com data/)")
    ap.add_argument("--url", default=os.environ.get("SITE_URL") or URL_PADRAO)
    ap.add_argument("--monitor", default=RAIZ / "monitor" / "novidades.json", type=Path)
    args = ap.parse_args(argv)
    site, url_site = args.site, args.url.rstrip("/") + "/"
    data = site / "data"
    if not (data / "index.json").exists():
        print("feeds: sem data/index.json, nada a gerar")
        return 0

    apelidos = ler_apelidos(site) if (site / "js" / "dados.js").exists() else {}
    g = Gerador(data, url_site, apelidos, ler_json(args.monitor, []))
    destino = site / "feed"
    total = 0
    for id_ in g.normas:
        if not RE_ID_VALIDO.fullmatch(id_) or ".." in id_:
            continue
        arq = destino / f"{id_}.xml"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(g.feed_da_norma(id_), encoding="utf-8")
        total += 1
    (destino / "novidades.xml").write_text(g.feed_geral(), encoding="utf-8")
    print(f"feeds: {total} feeds de normas + novidades.xml em {destino}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
