# data/ — índice e ligações entre normas federais

Gerado automaticamente por [`indice/construir.py`](../indice/construir.py) via a Action
[`indice.yml`](../.github/workflows/indice.yml). **Não edite à mão**: a próxima execução sobrescreve.

Fonte: [ctresb/leis](https://github.com/ctresb/leis). O texto das normas **não** é copiado; aqui ficam só
metadados e relações.

## Escopo

| Categoria (`pasta`) | Prefixo | Normas (nov/2026) |
|---|---|---|
| `constituicao` (arquivo `constituicao.md`) | `constituicao` | 1 |
| `emendas-constitucionais` | `emc` | 172 |
| `leis-complementares` | `lcp` | 239 |
| `leis-ordinarias` (inclui Código Civil, CDC, CTN, CPC...) | `lei` | 16.784 |
| `decretos-lei` (inclui Código Penal, CPP, CLT) | `del` | 12.376 |

O escopo está na constante `ESCOPO` de `indice/construir.py`. Mudá-lo força um reprocessamento completo.

## Identificadores

`id` = caminho do arquivo no ctresb/leis **sem `.md`**:

- `federal/leis-ordinarias/1990/lei-8078-1990-09-11`
- `constituicao` (a Constituição de 1988)

O texto fica em `https://raw.githubusercontent.com/ctresb/leis/main/<id>.md`.

Uma norma citada pode estar fora do escopo indexado:

- se ela existe no acervo (ex.: um decreto), o `id` é o caminho real dela, mas ela não tem entrada em `index/`;
- se não foi encontrada, o `id` é `externo:<prefixo>-<número>[-<ano>]`, ex. `externo:dec-4453-1922`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `index.json` | Manifesto: commit da fonte, totais e lista de partes |
| `index/<pasta>.json` | Metadados de cada norma da categoria |
| `links.json` | Todas as ligações (lista de arestas) + metadados das normas envolvidas |
| `adjacencia/<pasta>.json` | As mesmas ligações agrupadas por norma, nos dois sentidos (para backlinks) |
| `cache/<pasta>.json` | Uso interno: SHA de cada arquivo processado e referências brutas |
| `estado.json` | Uso interno: último commit processado e versão do extrator |

Todos os JSON têm um item por linha, para que os diffs no git mostrem só o que mudou.

### `index.json`

```json
{
  "versao": 1,
  "gerado_em": "2026-11-03T16:20:24+00:00",
  "fonte": { "repositorio": "ctresb/leis", "commit": "c9f21b4…", "escopo": ["constituicao.md", "federal/leis-ordinarias", "…"] },
  "total": 29572,
  "shards": [
    { "categoria": "leis-ordinarias", "arquivo": "index/leis-ordinarias.json",
      "adjacencia": "adjacencia/leis-ordinarias.json",
      "tipo": "Lei Ordinária", "prefixo": "lei", "total": 16784 }
  ],
  "links": { "arquivo": "links.json", "total": 62438, "por_tipo": { "cita": 49027, "altera": 9337, "revoga": 4074 } }
}
```

Caminhos são relativos a `data/`. `gerado_em` só muda quando algum dado muda.
Em `emendas-constitucionais`, `tipo` é `"Emenda Constitucional"`, mas a parte também tem as 6 de Revisão.

### `index/<pasta>.json`

Array, ordenado por `id`:

```json
{"id": "federal/leis-ordinarias/1990/lei-8078-1990-09-11",
 "path": "federal/leis-ordinarias/1990/lei-8078-1990-09-11.md",
 "titulo": "Lei nº 8.078 de 11/09/1990", "tipo": "Lei Ordinária", "numero": "8078",
 "data": "1990-09-11", "ementa": "Dispõe sobre a proteção do consumidor…",
 "revogada": false, "urn": "urn:lex:br:federal:lei:1990-09-11;8078"}
```

Os campos vêm do frontmatter do acervo (a Constituição não tem frontmatter; seus metadados são fixos).

### `links.json`

```json
{"versao": 1,
 "leis": { "<id>": {"titulo": "…", "tipo": "…", "numero": "…", "data": "AAAA-MM-DD", "ementa": "…", "revogada": false} },
 "links": [
   {"de": "federal/leis-ordinarias/1995/lei-9008-1995-03-21",
    "para": "federal/leis-ordinarias/1990/lei-8078-1990-09-11",
    "tipo": "altera", "dispositivos": ["art. 4º", "art. 39", "art. 82"]}
 ]}
```

- `tipo`: `cita`, `altera` ou `revoga`. Leia como "`de` cita/altera/revoga `para`".
- `dispositivos`: artigos **da norma `para`** envolvidos, quando identificados (`"art. 5º"`, `"art. 54-A"`,
  `"ADCT art. 76"`). Lista vazia = não identificado ou a norma inteira.
  Um `revoga` com dispositivos é revogação parcial.
- Uma aresta é única por (`de`, `para`, `tipo`); o mesmo par pode ter `cita` e `altera` ao mesmo tempo.
- `leis` só traz as normas **indexadas** que aparecem em alguma aresta. Ids sem entrada são não indexados.

### `adjacencia/<pasta>.json`

Objeto `id -> vizinhos`, só para normas da categoria que têm alguma ligação:

```json
{"federal/leis-ordinarias/1990/lei-8078-1990-09-11":
  {"cita": ["constituicao", "…"], "altera": ["…"], "revoga": [],
   "citada_por": ["…"], "alterada_por": ["…lei-9008-1995-03-21", "…"], "revogada_por": []}}
```

`altera` = normas que esta altera; `alterada_por` = normas que alteraram esta (o mesmo vale para `cita` e `revoga`).

## Como as ligações são extraídas

Por expressões regulares sobre o texto, em [`indice/extrator.py`](../indice/extrator.py):

1. **Anotações dos compiladores** entre parênteses, ex. `(Redação dada pela Lei nº 9.008, de 21/3/1995)`,
   `(Inciso acrescido pela Medida Provisória nº 1.393…)`, `(Revogado pela Lei nº …)`.
   Viram `altera`/`revoga` **da norma citada para a norma que contém a anotação**, no artigo onde ela aparece.
   `(Vide …)` e similares viram `cita`.
2. **Texto corrido**: um parágrafo com "revogam-se", "fica revogado"… vira `revoga`; com "passa a vigorar",
   "fica acrescido"… vira `altera`; o resto vira `cita`. Se a citação vem como "art. 48 da Lei nº X",
   o artigo vai para `dispositivos`.
3. Referências sem ano completo são resolvidas pelo número; quando a numeração reinicia (ex. LC nº 1 de 1962
   e de 1967), vale a mais recente anterior à norma que cita.
4. "Constituição Federal" só conta como a de 1988 em normas posteriores a 05/10/1988. Alguns códigos
   citados pelo nome ("Código Civil", "Código Penal", "CLT"…) também viram `cita`.

É heurístico: há falsos positivos (ex. citações dentro do texto novo que uma lei dá a outra) e omissões
(listas como "Leis nºs 1, 2 e 3" só pegam quando cada uma traz "Lei nº").
Muitos arquivos do acervo são a versão original, sem anotações de alteração; nesses, as alterações só
aparecem pelo lado da lei que altera.

## Atualização incremental

A Action roda todo dia às 05:00 (Brasília):

1. Clona o acervo com `--filter=blob:none --depth 1`: só a árvore (~60 MB), nenhum texto.
2. Compara o SHA de cada `.md` do escopo com o guardado em `cache/`. Só os novos ou alterados são baixados
   (sparse checkout); os removidos saem do índice. A primeira execução baixa o escopo todo (~230 MB, ~40 s).
3. Reagrega as ligações a partir do cache (referências brutas são resolvidas de novo, então uma lei que
   entra no acervo passa a ser ligada às citações antigas).
4. Commita `data/` se algo mudou e dispara o deploy do site.

Para reprocessar tudo: Actions → Índice das leis federais → Run workflow → marque "Reprocessar".
Ao mudar a lógica do extrator, aumente `VERSAO_EXTRATOR` em `indice/construir.py`.

Rodar localmente:

```bash
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/ctresb/leis.git /tmp/leis
python indice/construir.py --fonte /tmp/leis --saida data
python -m unittest discover -s indice/tests
```
