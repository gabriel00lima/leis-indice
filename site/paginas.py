#!/usr/bin/env python3
"""Gera, dentro de _site/, uma página HTML pronta para cada norma do índice,
para que buscadores e prévias de link (WhatsApp, Telegram, X, Facebook) vejam
título, ementa e imagem sem rodar JavaScript.

Cada página é uma cópia de lei.html com o cabeçalho preenchido e as metatags
(description, canonical, Open Graph, Twitter, JSON-LD). O resto continua
interativo: lei.js lê o id em <body data-lei> e carrega o texto como sempre.

Também gera sitemap.xml (índice) + sitemaps/<categoria>.xml, robots.txt e
404.html (que manda /lei/<id> sem página para lei.html?id=<id>).

Roda no build do site (site/build.sh), depois de site/ e data/ copiados:

    python3 site/paginas.py --site _site [--url https://.../leis-indice/]

Endereço de cada norma: <url>lei/<id>, servido de _site/lei/<id>.html.
"""
import argparse
import html
import json
import os
import re
from pathlib import Path

URL_PADRAO = "https://gabriel00lima.github.io/leis-indice/"
NOME_SITE = "Leis do Brasil"
ID_CONSTITUICAO = "constituicao"
LARGURA_IMG, ALTURA_IMG = 1200, 630

# Apelidos usados no título das páginas. Os mesmos de site/js/dados.js (APELIDOS);
# lidos de lá para não manter duas listas.
RE_APELIDO = re.compile(r'^\s*"([^"]+)":\s*"([^"]+)",?\s*$', re.M)

esc = html.escape


def ler_apelidos(site):
    js = (site / "js" / "dados.js").read_text(encoding="utf-8")
    bloco = re.search(r"export const APELIDOS = \{(.*?)\n\};", js, re.S)
    return dict(RE_APELIDO.findall(bloco.group(1))) if bloco else {}


def limpar(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def frase(s):
    """Ementas antigas vêm em CAIXA ALTA; na prévia, só a primeira letra maiúscula."""
    s = limpar(s)
    letras = [c for c in s if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.8:
        s = s.lower()
        s = s[:1].upper() + s[1:]
    return s


def cortar(s, n):
    if len(s) <= n:
        return s
    return s[: n - 1].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"


def data_br(d):
    p = str(d or "").split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(d or "")


def titulo_norma(e):
    t = limpar(e.get("titulo"))
    t = re.sub(r"\(\s*seq-sf:\s*\d+\s*\)", "", t).strip()
    if e["id"] == ID_CONSTITUICAO:
        return "Constituição da República Federativa do Brasil de 1988"
    return t or e["id"].rsplit("/", 1)[-1]


def carregar_entradas(data):
    manifesto = json.loads((data / "index.json").read_text(encoding="utf-8"))
    if isinstance(manifesto, list):
        return [(None, manifesto)], manifesto
    grupos = []
    for s in manifesto.get("shards", []):
        bruto = json.loads((data / s["arquivo"]).read_text(encoding="utf-8"))
        if isinstance(bruto, dict) and "linhas" in bruto:
            bruto = [dict(zip(bruto["campos"], l)) for l in bruto["linhas"]]
        grupos.append((s, bruto))
    return grupos, manifesto


def imagem_para(e, imagens):
    base = e["id"].rsplit("/", 1)[-1]
    pasta = e["id"].split("/")[1] if "/" in e["id"] else e["id"]
    for nome in (base, "tipo-" + pasta, "padrao"):
        if nome in imagens:
            return nome
    return None


def metatags(url, titulo, descricao, img, img_alt, tipo_og="article", extra=""):
    linhas = [
        f'<meta name="description" content="{esc(descricao)}">',
        f'<link rel="canonical" href="{esc(url)}">',
        f'<meta property="og:site_name" content="{NOME_SITE}">',
        '<meta property="og:locale" content="pt_BR">',
        f'<meta property="og:type" content="{tipo_og}">',
        f'<meta property="og:title" content="{esc(titulo)}">',
        f'<meta property="og:description" content="{esc(descricao)}">',
        f'<meta property="og:url" content="{esc(url)}">',
    ]
    if img:
        linhas += [
            f'<meta property="og:image" content="{esc(img)}">',
            '<meta property="og:image:type" content="image/jpeg">',
            f'<meta property="og:image:width" content="{LARGURA_IMG}">',
            f'<meta property="og:image:height" content="{ALTURA_IMG}">',
            f'<meta property="og:image:alt" content="{esc(img_alt)}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:image" content="{esc(img)}">',
        ]
    else:
        linhas.append('<meta name="twitter:card" content="summary">')
    linhas += [
        f'<meta name="twitter:title" content="{esc(titulo)}">',
        f'<meta name="twitter:description" content="{esc(descricao)}">',
    ]
    return "\n".join(linhas) + ("\n" + extra if extra else "")


def trocar_titulo(doc, titulo):
    return re.sub(r"<title>.*?</title>", lambda _: f"<title>{esc(titulo)}</title>", doc, count=1, flags=re.S)


def inserir_no_head(doc, bloco):
    """Logo depois de <title> (ou antes de </head>), tirando description antiga."""
    doc = re.sub(r'<meta name="description"[^>]*>\n?', "", doc)
    if "</title>" in doc:
        return doc.replace("</title>", "</title>\n" + bloco, 1)
    return doc.replace("</head>", bloco + "\n</head>", 1)


def marcar_paginas(doc):
    """<meta name="leis:paginas"> avisa o JS (urlLei) que existem as páginas /lei/<id>."""
    if '<meta name="leis:paginas"' in doc:
        return doc
    return re.sub(r"(<meta charset=[^>]*>)", r'\1\n<meta name="leis:paginas" content="lei/">', doc, count=1)


def json_ld(e, url, titulo, descricao):
    d = {
        "@context": "https://schema.org",
        "@type": "Legislation",
        "name": titulo,
        "url": url,
        "inLanguage": "pt-BR",
        "legislationJurisdiction": "BR",
        "legislationLegalForce": "https://schema.org/" + ("NotInForce" if e.get("revogada") else "InForce"),
        "isPartOf": {"@type": "WebSite", "name": NOME_SITE},
    }
    if descricao:
        d["abstract"] = descricao
    if e.get("tipo"):
        d["legislationType"] = e["tipo"]
    if e.get("data"):
        d["legislationDate"] = e["data"]
    if e.get("urn"):
        d["legislationIdentifier"] = e["urn"]
    txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{txt}</script>'


def pagina_da_lei(modelo, e, url_site, imagens, apelidos):
    id_ = e["id"]
    profundidade = id_.count("/") + 1  # lei/<id>.html
    base = "../" * profundidade
    url = f"{url_site}lei/{id_}"

    nome = titulo_norma(e)
    apelido = apelidos.get(id_)
    titulo_pag = (f"{apelido} ({nome})" if apelido and apelido != nome else nome) + f" · {NOME_SITE}"
    titulo_og = f"{apelido} ({nome})" if apelido and apelido != nome else nome
    ementa = frase(e.get("ementa"))
    situacao = "Revogada" if e.get("revogada") else "Em vigor"
    if ementa:
        descricao = cortar(ementa, 200)
    else:
        descricao = f"Texto integral de {nome}" + (f", publicada em {data_br(e['data'])}" if e.get("data") else "") + "."
    descricao_og = cortar(f"{situacao}. {descricao}", 220) if e.get("revogada") else descricao

    img = imagem_para(e, imagens)
    img_url = f"{url_site}og/{img}.jpg" if img else None
    bloco = metatags(url, titulo_og, descricao_og, img_url, f"{apelido or nome} · {NOME_SITE}",
                     extra=json_ld(e, url, nome, ementa))

    doc = modelo
    doc = trocar_titulo(doc, titulo_pag)
    doc = inserir_no_head(doc, f'<base href="{base}">\n{bloco}')
    doc = re.sub(r"<body([^>]*)>", lambda m: f'<body{m.group(1)} data-lei="{esc(id_)}">', doc, count=1)
    doc = re.sub(r'(<h1 id="titulo">)[^<]*(</h1>)', lambda m: m.group(1) + esc(apelido or nome) + m.group(2), doc, count=1)
    if apelido and apelido != nome:
        doc = re.sub(r'<p class="subtitulo-lei" id="subtitulo" hidden></p>',
                     lambda _: f'<p class="subtitulo-lei" id="subtitulo">{esc(nome)}</p>', doc, count=1)
    if ementa:
        doc = re.sub(r'(<p class="ementa" id="ementa">)(</p>)', lambda m: m.group(1) + esc(limpar(e.get("ementa"))) + m.group(2), doc, count=1)
    return doc


def pagina_404(url_site):
    # Página servida em qualquer caminho inexistente: só caminhos absolutos.
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Página não encontrada · {NOME_SITE}</title>
<script>
// /lei/<id> sem página gerada (norma nova, fora do índice): abre a versão interativa.
(function () {{
  var m = /^(.*?\\/)lei\\/(.+?)(?:\\.html)?\\/?$/.exec(location.pathname);
  if (m) location.replace(m[1] + "lei.html?id=" + encodeURIComponent(decodeURIComponent(m[2])) + location.hash);
}})();
</script>
<style>
body{{margin:0;font:16px/1.5 system-ui,sans-serif;background:#f6f6f2;color:#17211c;display:grid;place-items:center;min-height:100vh}}
main{{max-width:32rem;padding:2rem 1rem;text-align:center}}
h1{{font-family:Georgia,serif;color:#053a22}}
a{{color:#163f8f}}
.faixa{{position:fixed;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#0a6b3d 0 62%,#f2c12e 62% 81%,#163f8f 81% 100%)}}
</style>
</head>
<body>
<div class="faixa"></div>
<main>
<h1>Página não encontrada</h1>
<p>O endereço não existe ou a norma ainda não entrou no índice.</p>
<p><a href="{esc(url_site)}">Ir para a busca do {NOME_SITE}</a></p>
</main>
</body>
</html>
"""


def sitemap(urls):
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    linhas += [f"<url><loc>{esc(u)}</loc></url>" for u in urls]
    linhas.append("</urlset>")
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="_site", help="pasta do site já montado (com data/)")
    ap.add_argument("--url", default=os.environ.get("SITE_URL") or URL_PADRAO, help="endereço público do site")
    args = ap.parse_args()
    site = Path(args.site)
    url_site = args.url.rstrip("/") + "/"
    data = site / "data"

    if not (data / "index.json").exists():
        print("paginas: sem data/index.json, nada a gerar")
        return

    imagens = {p.stem for p in (site / "og").glob("*.jpg")}
    apelidos = ler_apelidos(site)
    grupos, manifesto = carregar_entradas(data)

    # Páginas que já existem ganham a marca e as metatags gerais do site.
    descricao_site = ("Busque e leia as leis federais do Brasil, com links entre normas, "
                      "histórico de alterações e grafo de relações.")
    img_site = f"{url_site}og/padrao.jpg" if "padrao" in imagens else None
    for rel, url, titulo in (("index.html", url_site, f"{NOME_SITE} · busca e leitura das leis federais"),
                             ("grafo/index.html", url_site + "grafo/", f"Grafo das leis · {NOME_SITE}"),
                             ("explicada.html", url_site + "explicada.html", f"Lei explicada · {NOME_SITE}"),
                             ("sobre.html", url_site + "sobre.html", f"O acervo em números · {NOME_SITE}")):
        p = site / rel
        if not p.exists():
            continue
        doc = marcar_paginas(p.read_text(encoding="utf-8"))
        if 'property="og:title"' not in doc:
            m = re.search(r'<meta name="description" content="([^"]*)"', doc)
            desc = html.unescape(m.group(1)) if m else descricao_site
            m = re.search(r"<title>(.*?)</title>", doc, re.S)
            tit = html.unescape(limpar(m.group(1))) if m else titulo
            doc = inserir_no_head(doc, metatags(url, tit, desc, img_site, NOME_SITE, tipo_og="website"))
        p.write_text(doc, encoding="utf-8")

    lei_html = site / "lei.html"
    modelo = marcar_paginas(lei_html.read_text(encoding="utf-8"))
    lei_html.write_text(modelo, encoding="utf-8")

    destino = site / "lei"
    mapas = []
    total = 0
    for shard, entradas in grupos:
        urls = []
        for e in entradas:
            id_ = e.get("id")
            if not id_ or not re.fullmatch(r"[a-z0-9][a-z0-9/_.\-]*", id_) or ".." in id_:
                continue
            arq = destino / (id_ + ".html")
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(pagina_da_lei(modelo, e, url_site, imagens, apelidos), encoding="utf-8")
            urls.append(f"{url_site}lei/{id_}")
        total += len(urls)
        nome = (shard or {}).get("categoria") or "normas"
        # Limite do protocolo: 50 mil URLs por arquivo.
        for i in range(0, len(urls), 50000):
            parte = f"{nome}.xml" if len(urls) <= 50000 else f"{nome}-{i // 50000 + 1}.xml"
            (site / "sitemaps").mkdir(exist_ok=True)
            (site / "sitemaps" / parte).write_text(sitemap(urls[i:i + 50000]), encoding="utf-8")
            mapas.append(parte)

    (site / "sitemaps" / "paginas.xml").write_text(sitemap([url_site, url_site + "grafo/", url_site + "sobre.html"]), encoding="utf-8")
    mapas.insert(0, "paginas.xml")
    indice = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    indice += [f"<sitemap><loc>{esc(url_site)}sitemaps/{m}</loc></sitemap>" for m in mapas]
    indice.append("</sitemapindex>")
    (site / "sitemap.xml").write_text("\n".join(indice) + "\n", encoding="utf-8")

    (site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {url_site}sitemap.xml\n", encoding="utf-8")
    (site / "404.html").write_text(pagina_404(url_site), encoding="utf-8")
    print(f"paginas: {total} normas -> {destino}/, sitemap com {len(mapas)} partes")


if __name__ == "__main__":
    main()
