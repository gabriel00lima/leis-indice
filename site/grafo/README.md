# Grafo de leis

Página estática (`index.html`, sem dependências nem build) que mostra a vizinhança de uma lei:
quais leis ela **cita**, **altera** ou **revoga**, e quais a citam, alteram ou revogam.

- Abrir: `grafo/?id=<id>`, onde `<id>` é o caminho da lei no repositório
  [ctresb/leis](https://github.com/ctresb/leis) sem `.md`
  (ex.: `grafo/?id=federal/leis-ordinarias/1990/lei-8078-1990-09-11`).
- Parâmetros opcionais: `direcao=ambas|saida|entrada`, `profundidade=1|2`, `dados=<pasta com index.json e links.json>`.
- Cada nó leva ao grafo daquela lei; o painel lateral lista as ligações e tem links para `../lei.html?id=<id>` (página da lei no site) e para o arquivo-fonte no GitHub.

## Dados

Usa os mesmos dados do site, no formato descrito em [`site/README.md`](../README.md#dados-que-o-site-lê):

- `data/links.json`: objeto `id -> { cita, altera, revoga, citada_por, alterada_por, revogada_por }`,
  ou manifesto `{ "shards": [{ "arquivo", "pasta" }] }`. O grafo só baixa as partes das leis que exibe.
- `data/index.json`: metadados (título, ementa, data, revogada), array ou manifesto com shards.
  O grafo carrega só as partes das pastas exibidas; o índice inteiro só é baixado quando a busca é usada.

Procura em `../data/` e, se não houver, usa `../exemplo/` (22 normas reais) e mostra um aviso.
`?dados=<pasta>` aponta para outra base. Uma norma citada que não está no índice aparece como
"não indexada", com rótulo derivado do `id`. Na profundidade 2 o recorte é limitado a 150 nós.
