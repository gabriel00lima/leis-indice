# Diário Oficial da União

Coleta os atos normativos federais publicados na **Seção 1 do DOU** a partir dos
[dados abertos da Imprensa Nacional](https://www.in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados)
(um ZIP de XML por mês, sem login, licença CC0, publicado com cerca de duas semanas de atraso).

Ficam só: leis, leis complementares, leis delegadas, emendas constitucionais, medidas
provisórias, decretos e decretos legislativos **numerados**. Portarias, resoluções,
atos de pessoal e decretos sem número ficam de fora.

Os ZIPs (50 a 150 MB por mês) são baixados numa pasta temporária e apagados. No
repositório ficam só os dados derivados em [`data/dou/`](../../data/dou/).

## Arquivos

- `coletar.py`: lê a página da base de dados, baixa os ZIPs da Seção 1 dos meses
  novos, extrai os atos e liga cada um às normas do acervo ctresb/leis.
- `conferir.py`: confere o acervo e o monitor contra o DOU (ver abaixo).
- `tests/`: testes com um ZIP sintético no formato da Imprensa Nacional.

A Action [`dou.yml`](../../.github/workflows/dou.yml) roda todo dia às 07:30 (Brasília),
mas só baixa algo quando a Imprensa Nacional publica um mês novo (ou troca os ZIPs de
um mês). A primeira coleta começa em `DESDE` (jan/2025) e baixa no máximo 8 meses por
execução. Em pull requests ela baixa um mês real numa pasta temporária, sem commitar.

## Formato de `data/dou/`

| Arquivo | Conteúdo |
|---|---|
| `index.json` | Manifesto: fonte, total e lista de meses (`arquivo`, `total`, `por_tipo`, `zips`) |
| `meses/AAAA-MM.json` | Atos do mês, mais recentes primeiro, um por linha |
| `recentes.json` | Os 150 atos mais recentes (feed do site) |
| `por_norma.json` | `id da norma -> [{rel, data, identifica, url, norma, mes, ato}]`, com `rel` = `publicacao`, `altera` ou `revoga` |
| `conferencia.json` | Resultado de `conferir.py` |
| `estado.json` | Uso interno: ZIPs já processados por mês |

Um ato:

```json
{"id": "1", "data": "2025-03-12", "secao": "DO1", "edicao": "48", "pagina": 1,
 "tipo": "Lei", "prefixo": "lei", "numero": "15100", "data_ato": "2025-03-10",
 "identifica": "LEI Nº 15.100, DE 10 DE MARÇO DE 2025", "ementa": "Altera…",
 "orgao": "Atos do Poder Legislativo", "url": "https://pesquisa.in.gov.br/…",
 "norma": "federal/leis-ordinarias/2025/lei-15100-2025-03-10",
 "altera": ["federal/leis-ordinarias/1990/lei-8078-1990-09-11"], "revoga": [], "cita": ["constituicao"]}
```

- `data` é a data de publicação no DOU; `data_ato`, a data de assinatura.
- `norma` é o `id` do próprio ato no acervo (`null` se ainda não tem arquivo lá).
- `altera`, `revoga` e `cita` usam os mesmos `id` de `data/index/`. Vêm da ementa e dos
  parágrafos do texto, com as mesmas regras do índice (`indice/extrator.py`), mais as
  listas no plural ("Leis nºs 8.078, de 1990, e 10.406, de 2002").

## Conferência com o monitor

`conferencia.json` tem:

- `fora_do_acervo`: atos publicados há mais de 7 dias que ainda não têm arquivo no
  ctresb/leis. Mostra o atraso do acervo.
- `monitor`: para cada lei de [`monitor/acompanhar.txt`](../../monitor/acompanhar.txt), os
  atos do DOU que a alteram ou revogam e a `situacao`:
  - `em_dia`: o arquivo no acervo mudou depois do último ato e o monitor já viu essa versão;
  - `acervo_atrasado`: o DOU alterou a lei, mas o arquivo no acervo é mais antigo (o monitor
    não tem como avisar ainda); a Action registra um aviso;
  - `monitor_pendente`: o acervo já mudou, mas o monitor ainda não rodou desde então;
  - `sem_atos`: nenhum ato no período coletado; `nao_verificado`: sem acesso à API do GitHub.

É uma conferência aproximada: um commit no acervo depois do ato não garante que a
alteração específica foi incorporada.

## Rodar localmente

```bash
python -m unittest discover -s integracoes/dou/tests -v
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/ctresb/leis.git /tmp/leis
python integracoes/dou/coletar.py --acervo /tmp/leis --mes 2025-09
python integracoes/dou/conferir.py
```
