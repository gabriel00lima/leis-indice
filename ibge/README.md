# ibge/ — estados e municípios oficiais

Coleta a [API de Localidades do IBGE](https://servicodados.ibge.gov.br/api/docs/localidades)
(sem chave) e grava JSON estático em `data/ibge/`, usado nos filtros por UF e município do site.

- Script: `python ibge/coletar.py --saida data/ibge` (só biblioteca padrão).
- Action: [`ibge.yml`](../.github/workflows/ibge.yml), todo dia 1 do mês, manualmente
  ("Run workflow") e quando `ibge/` muda na `main`. Em PRs roda os testes e a coleta, sem commitar.
- Se a API do IBGE não responder (ela às vezes recusa conexões dos runners do GitHub, fora do Brasil),
  o script usa o espelho em CSV [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros),
  com os mesmos códigos do IBGE; `index.json` registra qual fonte foi usada.
- Se a resposta vier com menos de 27 UFs ou de 5.500 municípios, nada é gravado e a Action falha.
- O manifesto guarda um `sha256` do conteúdo: sem mudança no IBGE, não há commit.

## Arquivos em `data/ibge/` (não edite à mão)

| Arquivo | Conteúdo |
|---|---|
| `index.json` | Manifesto: `gerado_em`, URLs da fonte, `sha256`, totais |
| `estados.json` | Lista de UFs: `{ codigo, sigla, nome, slug, regiao: { codigo, sigla, nome }, capital, municipios }` |
| `municipios.json` | `{ campos: ["codigo","nome","uf","slug","capital"], linhas: [[3550308,"São Paulo","SP","sao-paulo",1], …] }` |

- `codigo`: código IBGE (2 dígitos para UF, 7 para município).
- `slug`: nome em minúsculas, sem acento, palavras separadas por hífen (`sao-joao-d-alianca`).
  Use para casar com caminhos de arquivos e URLs.
- `capital`: código do município-capital (em `estados.json`) ou 1/0 (em `municipios.json`).
  A API não informa capitais; a lista fixa está em `CAPITAIS` no script.

## No site: `site/js/localidades.js`

```js
import * as loc from "./js/localidades.js";
await loc.estado("sp");                         // por sigla, código (35) ou slug
await loc.municipios("RJ");                     // municípios da UF
await loc.municipio(3550308);                   // por código, ou loc.municipio("sao-paulo", "SP")
await loc.buscarMunicipios("sao jo", { uf: "SP", limite: 10 });  // sem acento, por início de palavra
await loc.preencherSelectUF(selectUF);          // <select> com as 27 UFs (valor = sigla)
await loc.preencherSelectMunicipio(selectMun, "MG");  // valor = código IBGE
```

Os arquivos são baixados uma vez e ficam em memória.
