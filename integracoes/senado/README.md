# Integração com os Dados Abertos do Senado

Para cada norma do índice (`data/index/`), consulta
`https://legis.senado.leg.br/dadosabertos/legislacao/urn?urn=<urn>` (a URN vem do frontmatter do
acervo) e guarda, em `data/senado/`, o que o Senado registra sobre ela:

- **histórico de alterações**: cada norma posterior que alterou, acrescentou, revogou, renumerou ou
  regulamentou dispositivos desta, com a data e os dispositivos afetados;
- **controle de constitucionalidade**: acórdãos do STF (ADI, ADC, ADPF, ADO...) e resoluções do Senado
  que suspendem a execução de dispositivos, com o efeito em cada dispositivo
  (`inconstitucional`, `suspenso`, `interpretacao-conforme`, `constitucional`).

| Arquivo | O quê |
|---|---|
| `senado.py` | Converte a resposta do Senado no formato compacto (sem rede, testado) |
| `coletar.py` | Escolhe as normas da vez, consulta o Senado e grava `data/senado/` |
| `tests/` | `python -m unittest discover -s integracoes/senado/tests` |
| `../../.github/workflows/senado.yml` | Roda todo dia às 10:00 UTC e no PR (testes + 3 consultas reais) |

## Ritmo de coleta

O Senado não documenta limites, então a coleta é conservadora: uma consulta por vez, 1 s de pausa,
no máximo 1.500 consultas ou 45 minutos por execução. Em 429/502/503/504 espera 2 minutos e tenta
uma vez; se continuar, encerra o dia. Com ~29.600 normas, a primeira passada leva umas três semanas.

Ordem: normas nunca consultadas (as mais citadas e alteradas primeiro: Constituição, CLT, Código Penal...),
depois as que mudaram no acervo (SHA do arquivo diferente do da última consulta), depois as consultadas
há mais de 45 dias.

Para rodar à mão: `python integracoes/senado/coletar.py --data data --limite 20`
(ou `--ids federal/leis-ordinarias/1997/lei-9504-1997-09-30` para normas específicas).

## Formato de `data/senado/`

`normas/<id>.json` existe só para normas com alterações ou decisões:

```json
{
 "id": "federal/leis-ordinarias/1997/lei-9504-1997-09-30",
 "urn": "urn:lex:br:federal:lei:1997-09-30;9504",
 "consultado_em": "2026-11-04",
 "codigo": "551240", "nome": "Lei nº 9.504 de 30/09/1997", "apelidos": ["Lei Eleitoral (1997)"],
 "publicacoes": [{"tipo": "PUB", "data": "1997-10-01", "descricao": "Publicação Original [...]"}],
 "alteracoes": [
  {"data": "2015-09-29", "nome": "Lei nº 13.165 de 29/09/2015", "tipo": "Alteração Permanente",
   "id": "federal/leis-ordinarias/2015/lei-13165-2015-09-29",
   "dispositivos": [{"dispositivo": "Art. 45, caput", "art": "45", "acao": "alterou"}]}
 ],
 "controle": [
  {"data": "2018-06-21", "nome": "Acórdão da Ação Direta de Inconstitucionalidade nº 4.451 de 21/06/2018",
   "tipo": "Alteração Permanente", "decisao": {"classe": "ADI", "numero": "4451"},
   "dispositivos": [{"dispositivo": "Art. 45, caput, Inciso 2", "art": "45",
                     "efeito": "inconstitucional", "texto": "Declaração de Inconstitucionalidade"}]}
 ]
}
```

- `alteracoes` e `controle` em ordem de data (da mais antiga para a mais recente).
- `art` é o artigo no formato das âncoras do site (`art-394-a` → `"394-a"`); `null` para anexos etc.
- `acao`: `alterou`, `acrescentou`, `revogou`, `renumerou`, `regulamentou`, `ressalvou`, `vetado`,
  `revigorou`, `correlato`, ou o comentário do Senado em minúsculas.
- `id` aparece quando a norma alteradora está no índice do site.
- Uma decisão sem dispositivos (ex.: ADI que declarou a lei toda constitucional) tem `"dispositivos": []`.

`adi.json`: `{ "<id>": {"inconstitucionais": 4, "artigos": ["45", "59-a"]} }` só das normas com dispositivos
declarados inconstitucionais ou suspensos (para selos em listas e na busca).

`estado.json`: uso interno da coleta (`em` = data da consulta, `sha` = blob do arquivo no acervo,
`alt`/`ctrl`/`inc` = contagens, `achou: false` = URN não encontrada no Senado).

## No site

`site/js/senado.js` (carregado por `lei.html`, independente de `lei.js`) lê `data/senado/normas/<id>.json` e
mostra o selo "N dispositivos com ADI" no cabeçalho, uma marca ao lado de cada artigo afetado e duas
caixas no painel: "Decisões do STF" e "Alterações segundo o Senado". Sem arquivo, não mostra nada.

Os dados são informativos e podem estar desatualizados em relação ao Senado e ao STF.
