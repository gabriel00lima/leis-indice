# API pública (JSON estático)

`gerar.py` transforma `data/` em arquivos JSON publicados com o site no GitHub Pages:

**https://gabriel00lima.github.io/leis-indice/api/v1/** · documentação para quem usa: [`site/api.html`](../site/api.html)
(no ar em https://gabriel00lima.github.io/leis-indice/api.html).

Não há servidor: o `site/build.sh` roda o gerador a cada deploy (depois de toda atualização do índice e uma vez por dia)
e a saída vai para `_site/api/`. **Nada daqui é commitado**; a fonte de verdade continua sendo `data/`.

```bash
python3 api/gerar.py --data data --saida _site/api      # ~10 s, ~55 mil arquivos, ~80 MB
python3 -m unittest discover -s api/tests -v
```

## Rotas (relativas a `/api/v1/`)

| Rota | Conteúdo |
|---|---|
| `index.json` | Data, commit do acervo, totais, jurisdições e listas |
| `normas/{id}.json` | Metadados + `texto` (links do .md) + `ligacoes` nos 6 sentidos, com `dispositivos` |
| `ref/{jurisdicao}/{prefixo}/{numero}.json` | Normas com aquele número (ex. `ref/federal/lei/8078.json`) |
| `listas/{lista}.json` | Normas de uma categoria, em `{campos, linhas}` |
| `busca/{jurisdicao}.json` | Todas as normas da jurisdição, ementa cortada em 160 caracteres |

- `{id}` = caminho no ctresb/leis sem `.md` (o mesmo de `data/`).
- `{lista}` = o id sem o arquivo e sem a pasta do ano: `federal/leis-ordinarias`, `estaduais/SP/leis-ordinarias`, `constituicao`.
- `{prefixo}` = começo do nome do arquivo (`lei`, `lcp`, `del`, `emc`...). `{numero}` = campo `numero` só com letras e dígitos, minúsculo.
- `{jurisdicao}` = `federal` para `federal/...` e `constituicao`; a UF em minúsculas para `estaduais/<UF>/...`
  (`sp`, `rj`, `mg`); `<uf>-<município>` para `municipais/<UF>/<município>/...`.

## Leis estaduais e outras partes novas

O gerador lê **todas** as partes listadas em `data/index.json` (`shards[].arquivo`, array de objetos ou `{campos, linhas}`)
e a adjacência de `shards[].adjacencia` e de `data/links.json`. Uma parte nova, como `estaduais/SP/leis-ordinarias`,
aparece sozinha na API: rotas `normas/estaduais/SP/...`, `listas/estaduais/SP/...`, `ref/sp/...` e `busca/sp.json`,
e uma entrada `sp` em `index.json → jurisdicoes`. Não é preciso mudar nada aqui.

## Compatibilidade

A versão fica no caminho (`v1`). Campos novos podem ser acrescentados em `v1`; remover ou renomear campo, ou mudar
o formato de uma rota, exige `VERSAO = 2` (e manter `v1` gerado enquanto houver uso).
