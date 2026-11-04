# normas.leg.br

O [normas.leg.br](https://normas.leg.br) (Senado e Câmara) publica as normas federais por URN, e para parte delas traz o texto **artigo por artigo**, cada dispositivo com sua própria URN (`…;1988!art5`, `…!art5_cpt_inc1`, `…!art103-2,emc-45-2004-12-08`).

## O que foi verificado (nov/2026)

- API: `GET https://normas.leg.br/api/public/normas?urn=<urn>&tipo_documento=maior-detalhe` devolve JSON-LD. `dados-basicos` volta vazio.
- **Sem CORS**: nenhuma resposta traz `Access-Control-Allow-Origin`, então o navegador não lê a API. A coleta é feita no GitHub Actions.
- Só parte das normas tem a árvore de dispositivos (`hasPart`): CF, Código Civil, LGPD, Lei 14.133, emendas recentes. CDC, Código Penal, LRF e muitos decretos têm só metadados. Algumas URNs (ex. Lei 14.802/2024) nem existem lá: a API responde `{"urn": ...}`.
- `workExample` pode ser uma lista (uma por versão do dispositivo); o coletor usa a mais recente.
- Artigos com letra usam número: 103-B é `art103-2`. Os incluídos por emenda levam o sufixo da emenda (`art103-2,emc-45-2004-12-08`), que não dá para adivinhar: por isso o site usa o mapa gravado.
- Os links de texto integral (`/api/binario/<uuid>/texto`) mudam de UUID e às vezes dão 404; não são usados.
- Respostas grandes (CF tem 4,8 MB) às vezes chegam cortadas: o coletor tenta de novo.

## O que fica em `data/normas-leg/`

| Arquivo | Conteúdo |
| --- | --- |
| `<id>.json` | Só para normas com estrutura: `urn`, `titulo`, `atualizado`, `artigos` (`{"art-5": "art5", "art-103-b": "art103-2,emc-…"}`) e, quando precisa, `texto_md`. |
| `estado.json` | Controle do coletor: quando cada id foi consultado e o resultado (`estruturado`, `sem_estrutura`, `ausente`). O site não lê. |

`texto_md` (o texto montado em Markdown, no mesmo estilo do ctresb/leis) é guardado só para as normas de `prioridade.txt` e para as que o ctresb/leis traz **sem texto** (arquivo com menos de 1.500 bytes e nenhum "Art.", em geral só a retificação ou `<<ANEXO>>`).

## No site

`site/js/normas-leg.js`:

- cada artigo ganha um link discreto "normas.leg.br ↗" (aparece ao passar o mouse) quando a norma tem `<id>.json`;
- se o ctresb/leis não responder, ou trouxer a norma sem texto, a página usa `texto_md` e avisa a origem;
- sem texto em lugar nenhum, a página avisa e aponta para o normas.leg.br.

## Coleta

`.github/workflows/normas-leg.yml`, todo dia às 10:15 UTC, no máximo ~25 minutos por execução (cerca de 1.000 normas). Ordem: prioridade e normas sem texto (revisitadas a cada 7 dias), normas nunca consultadas, e as consultadas há mais de 90 dias. A primeira passada pelo índice inteiro leva algumas semanas de execuções diárias.

```
python normas_leg/coletar.py --data data --ids constituicao   # só uma norma
python -m unittest discover -s normas_leg/tests
```
