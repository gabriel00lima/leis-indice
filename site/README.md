# Site navegável das leis

Site estático (HTML + JS, sem framework e sem etapa de compilação) para buscar e ler as normas federais do acervo [ctresb/leis](https://github.com/ctresb/leis).

O site **não copia os textos**: cada página de lei baixa o `.md` direto de `raw.githubusercontent.com/ctresb/leis/main/` quando é aberta. Este repositório guarda só o índice (`data/`).

## Páginas

| Página | O que faz |
| --- | --- |
| `index.html` | Página inicial (apresentação, leis principais, mais citadas e mais alteradas, números do acervo, normas recentes) e busca por número, apelido, título ou assunto, com filtros de tipo, situação e ordem. A URL guarda a busca (`?q=8078&tipo=Lei%20Ordinária`). |
| `lei.html?id=<id>` | Texto da norma com sumário, âncoras por artigo (`#art-5`, `#art-11-a`), links cruzados, relações (de `links.json`), alterações anotadas no texto e histórico de commits do arquivo. |
| `lei.html?ref=<prefixo>:<número>:<ano>` | Resolve uma citação sem data completa (ex. `lei:8078:1990`) pelo índice e redireciona para a norma. |
| `lei/<id>` | Mesma página da lei, pré-gerada no build por `site/paginas.py` (ver "Páginas para buscadores e prévias"). É o endereço que o site usa nos links quando existe. |
| `grafo/?id=<id>` | Visualização do grafo (mantida em `site/grafo/`). |
| `explicada.html` | "Lei explicada": lista dos resumos em linguagem simples. Com `?lei=<slug>` (ex. `?lei=cdc`), mostra o resumo completo. |

`<id>` é o caminho da norma no ctresb/leis sem `.md`, ex. `federal/leis-ordinarias/1990/lei-8078-1990-09-11`. A Constituição de 1988 é `constituicao`.

## Links cruzados

`js/citacoes.js` reconhece no texto citações como "Lei nº 9.008, de 21/3/1995", "Decreto-Lei nº 2.848, de 7 de dezembro de 1940", "Lei nº 8.078/90", "Lei Complementar nº 101, de 2000" e "Constituição Federal", inclusive com artigo ("art. 170 da Constituição Federal" leva a `#art-170`).

- Com data completa, o link vai direto para o id montado (`federal/<pasta>/<ano>/<prefixo>-<número>-<AAAA-MM-DD>`).
- Sem data completa, o link usa `?ref=` e o índice resolve.
- "art. 12" sem outra norma depois (ou com "desta Lei") vira link para o artigo na mesma página.

As notas em itálico do acervo ("*(Redação dada pela Lei nº …)*") viram a lista "Alterações anotadas no texto", em ordem cronológica e com os artigos afetados.

## Lei explicada

Resumos em linguagem simples das leis mais usadas, em `explicadas/<slug>.md`. Cada arquivo tem um cabeçalho (`lei`, `nome`, `sigla`, `ordem`, `resumo`, `para_quem`, `revisado_em`, `origem`) e as seções `## Em poucas palavras`, `## O que você precisa saber`, `## Situações comuns` e `## Onde procurar ajuda` (opcionalmente `## Prazos que importam`).

- Artigos citados são links `[art. 49](#art-49)`; o site transforma em link para o artigo na página da lei. Outras normas: `lei.html?id=...#art-7` ou `lei.html?ref=lei:9099:1995`.
- A página da lei (`js/explicada-na-lei.js`) mostra em destaque "Em poucas palavras" e "O que você precisa saber"; a home lista os resumos (`js/explicadas-inicio.js`).
- Depois de criar ou editar um resumo, rode `python3 scripts/explicadas.py`: ele confere o cabeçalho, baixa o texto de cada lei e verifica se todos os artigos citados existem, e regenera `explicadas/index.json`. O workflow `explicadas.yml` roda a mesma conferência em cada PR.
- Rascunho com IA (opcional): `python3 scripts/explicadas_ia.py --slug <slug> [--lei <id> --nome <nome>]` com `ANTHROPIC_API_KEY`, ou pela aba Actions (workflow "Lei explicada" → Run workflow), que abre um PR. O arquivo sai com `origem: gerado com IA` e o site avisa o leitor; revise antes do merge.
- Os resumos não são aconselhamento jurídico; o aviso aparece em todas as páginas que os exibem.

## Dados que o site lê

O site procura `data/index.json`. Se não achar, usa `exemplo/` (22 normas reais, geradas por `node scripts/gerar_exemplo_site.mjs`) e mostra um aviso.

### `data/index.json`

Pode ser um **array** de entradas ou um **manifesto** que aponta para partes:

```json
{
  "gerado_em": "2026-11-03T12:00:00Z",
  "total": 192000,
  "shards": [
    { "arquivo": "index/leis-ordinarias.json", "tipo": "Lei Ordinária", "prefixo": "lei", "total": 16784 }
  ]
}
```

`arquivo` é relativo a `data/`. Cada parte é um array de entradas, ou `{ "campos": [...], "linhas": [[...]] }` para economizar espaço. `tipo` (opcional) deixa a busca carregar só a parte do tipo filtrado; `prefixo` (opcional) acelera a resolução de `?ref=`.

Entrada:

```json
{
  "id": "federal/leis-ordinarias/1990/lei-8078-1990-09-11",
  "path": "federal/leis-ordinarias/1990/lei-8078-1990-09-11.md",
  "titulo": "Lei nº 8.078 de 11/09/1990",
  "tipo": "Lei Ordinária",
  "numero": "8078",
  "data": "1990-09-11",
  "ementa": "Dispõe sobre a proteção do consumidor e dá outras providências.",
  "revogada": false,
  "urn": "urn:lex:br:federal:lei:1990-09-11;8078"
}
```

### `data/links.json`

Objeto `id -> relações`, todas listas de ids:

```json
{
  "federal/leis-ordinarias/1990/lei-8078-1990-09-11": {
    "cita": [], "altera": [], "revoga": [],
    "citada_por": [], "alterada_por": [], "revogada_por": []
  }
}
```

Também aceita um manifesto `{ "shards": [{ "arquivo": "links/leis-ordinarias.json", "pasta": "leis-ordinarias" }] }`, em que `pasta` é o segundo trecho do id.

### `destaques.json`

Estatísticas e listas da página inicial, calculadas a partir de `data/` por `site/destaques.py` (no build e à mão). A versão commitada em `site/destaques.json` é usada quando o build não roda.

## Páginas para buscadores e prévias

O Google e o WhatsApp não rodam o JavaScript da página, então `lei.html?id=` aparece para eles quase vazia. No build, `site/paginas.py` gera em `_site/`:

- `lei/<id>.html` para cada norma do índice: cópia de `lei.html` com `<title>`, `description`, `canonical`, Open Graph, Twitter card, JSON-LD (`schema.org/Legislation`) e o cabeçalho (título e ementa) já preenchidos. Um `<base href>` aponta para a raiz e `lei.js` lê o id em `<body data-lei>`; o resto da página continua igual. O Pages serve o arquivo sem a extensão (`/leis-indice/lei/federal/leis-ordinarias/1990/lei-8078-1990-09-11`).
- `sitemap.xml` (índice) e `sitemaps/<categoria>.xml`, `robots.txt` e `404.html`. A 404 manda `lei/<id>` sem página (norma ainda fora do índice) para `lei.html?id=<id>`.
- As metatags gerais em `index.html` e `grafo/index.html`, e `<meta name="leis:paginas">` nas páginas, que faz `urlLei()` apontar para `lei/<id>`. Sem o build (por exemplo, Pages em "Deploy from a branch"), os links continuam em `lei.html?id=`.

`lei.html?id=` de uma norma do índice redireciona para `lei/<id>`, para que o endereço copiado seja o que tem prévia.

As imagens de prévia (1200×630) ficam em `site/og/` e são commitadas: `padrao.jpg`, `tipo-<pasta>.jpg` e uma por lei principal (`<nome-do-arquivo>.jpg`). Para refazer depois de mudar as principais ou o visual: `node scripts/gerar_previas.mjs` (precisa do Playwright).

O endereço público vem de `SITE_URL` (padrão `https://gabriel00lima.github.io/leis-indice/`). São cerca de 6 KB por norma, uns 190 MB para as 29,5 mil federais (14 MB compactado no envio ao Pages).

## Rodar localmente

```bash
bash site/build.sh            # gera _site/ com site/ + data/
python3 -m http.server -d _site 8000
```

Abra http://localhost:8000. Precisa de servidor HTTP (os módulos JS não carregam via `file://`).

## Publicação

O workflow de GitHub Pages roda `bash site/build.sh` e publica `_site/`. Todos os caminhos são relativos, então o site funciona em `/leis-indice/`.

Se o Pages estiver em "Deploy from a branch" (raiz da `main`), o `index.html` da raiz redireciona para `site/` e o site lê os dados em `../data/`. Funciona, mas o modo recomendado é "GitHub Actions" (ver `docs/configuracao.md`).

## Limites conhecidos

- O histórico usa a API pública do GitHub (60 consultas por hora por IP sem login). Ao passar disso, a página mostra o link para o histórico no GitHub.
- O reconhecimento de citações é por expressão regular: citações com formato incomum ficam sem link.
- Bibliotecas em `vendor/`: marked 12.0.2 e DOMPurify 3.1.6 (licenças ao lado).
