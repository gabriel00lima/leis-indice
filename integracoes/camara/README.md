# Câmara dos Deputados: projetos de lei

Liga as normas do índice (`data/index/`) aos projetos da Câmara:

- **projeto de origem**: a proposição (PL, PLP, PEC, MPV, PLN...) que virou a norma;
- **projetos em tramitação que alteram a norma**: proposições ainda em andamento cuja ementa diz que altera ou revoga a norma.

A página de cada lei mostra isso na caixa "Na Câmara dos Deputados" (`site/js/camara.js`).

## De onde vêm os dados

Arquivos anuais em massa dos [dados abertos da Câmara](https://dadosabertos.camara.leg.br/swagger/api.html):
`https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-<ano>.json`, de 1946 até o ano atual.
Um download por ano em vez de uma chamada por projeto, com pausa entre arquivos e novas tentativas em
HTTP 429/5xx (respeitando `Retry-After`).

A Action [`camara.yml`](../../.github/workflows/camara.yml) roda todo dia às 08:30 UTC. Ela guarda um resumo por ano no
cache da Action (fora do git) e, a cada execução, baixa de novo o ano atual, o anterior e os 15 anos de resumo mais antigo.
Assim, arquivamentos e projetos que viraram lei em anos antigos entram em até uma semana. Se o cache sumir, baixa tudo
de novo (uns 7 minutos, ~1,7 GB). Para forçar, rode a Action manualmente com "Baixar todos os anos".

## Como a ligação é feita

- **Altera**: a ementa é lida por `ementa.py`, que reaproveita o extrator do índice. Uma norma conta como alterada quando
  vem depois de um verbo como "altera", "acrescenta", "revoga" ou "dá nova redação", sem "para", "nos termos de",
  "dispõe sobre" etc. no meio. Listas como "Altera as Leis nºs 8.078, de 1990, e 9.099, de 1995" são expandidas.
- **Em tramitação**: decidido pela situação atual (`ultimoStatus.descricaoSituacao`). Arquivada, transformada em norma,
  retirada, vetada, prejudicada, devolvida e "tramitação finalizada" contam como encerradas.
- **Origem**: o arquivo em massa não traz `urnFinal`; a origem sai do despacho "Transformado na Lei Ordinária N/AAAA"
  da última tramitação. Quando a última tramitação é outra (comum em medidas provisórias), a origem não aparece.

## Saída em `data/camara/`

| Arquivo | Conteúdo |
|---|---|
| `index.json` | Totais e data da última mudança |
| `normas/<id>.json` | Uma norma: `origem`, `tramitando` e `encerrados` (quantos projetos que a alteravam já acabaram) |

Só existem arquivos para normas com algum projeto. Exemplo (`normas/federal/leis-ordinarias/1990/lei-8078-1990-09-11.json`):

```json
{
"id":"federal/leis-ordinarias/1990/lei-8078-1990-09-11",
"origem":[],
"tramitando":[{"id": 2643710, "sigla": "PL 5063/2026", "ementa": "Altera a Lei nº 8.078…", "apresentacao": "2026-08-13",
  "situacao": "Aguardando Autorização do Despacho", "atualizado": "2026-08-20",
  "url": "https://www.camara.leg.br/propostas-legislativas/2643710", "relacao": "altera"}],
"encerrados":449
}
```

## Testes

```sh
python -m unittest discover -s integracoes/camara/tests -v
```
