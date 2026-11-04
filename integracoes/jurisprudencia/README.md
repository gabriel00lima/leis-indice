# Jurisprudência por artigo

Mostra, na página de cada norma acompanhada, **quais acórdãos do STJ citam cada artigo** e quantos processos o Judiciário tem nos assuntos ligados à norma. A coleta roda na Action `Jurisprudência` (toda segunda) e grava JSON estático em `data/jurisprudencia/`; o site só lê esses arquivos.

Normas de agora: Constituição Federal, Código Civil, CPC, CDC, CLT e Código Penal. Para incluir outra, acrescente uma entrada em `config.json` (ver abaixo) e rode a Action.

## Fontes

| Fonte | O que dá | Como é usada |
| --- | --- | --- |
| [Dados abertos do STJ](https://dadosabertos.web.stj.jus.br/) · conjuntos "Espelhos de acórdãos" (um por órgão julgador, um JSON por mês, desde maio de 2022) | Ementa, relator, órgão, data e **referências legislativas** que o próprio STJ cataloga em cada acórdão (`LEG:FED LEI:013105 ANO:2015 … ART:01022`) | Liga acórdão → artigo. Sem chave. |
| [DataJud / CNJ](https://datajud-wiki.cnj.jus.br/) · API pública (Elasticsearch) | Só metadados de processos: classe, assuntos da Tabela Processual Unificada, andamentos. Não traz texto nem artigos citados. | Conta quantos processos há em cada assunto ligado à norma (lista escolhida à mão em `config.json`). STJ para CC, CPC, CDC e CP; TST para a CLT. A CF fica sem DataJud (o STF não está no DataJud). |

### Chave do DataJud

A chave é pública, mas o CNJ pode trocá-la a qualquer momento. A coleta usa, nesta ordem:

1. o segredo `DATAJUD_API_KEY` do repositório, se existir (opcional);
2. a chave publicada em <https://datajud-wiki.cnj.jus.br/api-publica/acesso>, lida a cada execução;
3. `datajud.chave_reserva` de `config.json`.

A API do DataJud vive sobrecarregada (erros 429 e shards que falham). A coleta só aceita respostas completas; se não conseguir, mantém os números anteriores e o passo não derruba a Action.

## Arquivos gerados (`data/jurisprudencia/`)

```
indice.json                 { gerado_em, stj_gerado_em, leis: { <id da norma>: { nome, slug, stj, datajud, total } } }
stj/<slug>.json             resumo: { lei, nome, total, periodo: [ini, fim], artigos: { "art-5": 123 }, sem_artigo, bloco, por_artigo }
stj/<slug>/<n>.json         detalhe dos artigos n*100 a n*100+99: { artigos: { "art-5": [ids] }, decisoes: { id: decisão } }
stj/<slug>/sem.json         acórdãos que citam a norma sem indicar artigo (mesmo formato, chave "sem-artigo")
stj/_fonte.json             data da última coleta do STJ
datajud/<slug>.json         { lei, gerado_em, tribunais: [{ sigla, total, total_tribunal }], assuntos: [{ nome, total }] }
```

Decisão: `{ p: "REsp 2.260.689", o: "Terceira Turma", r: "Nancy Andrighi", j: "2026-08-04", e: "ementa resumida…", t: "Tema repetitivo 1076", u: "link da consulta processual" }`.

Para manter os dados pequenos, cada artigo guarda só a **contagem** e as **5 decisões mais recentes** (`stj.decisoes_por_artigo`), e a ementa é cortada em 260 caracteres (`stj.tamanho_ementa`). O site baixa o resumo ao abrir a lei e o bloco de detalhe só quando alguém clica no selo de um artigo.

Os ids de artigo seguem as âncoras do site: `art-5`, `art-1022`, `art-103-a`.

## `config.json`

```json
{
  "id": "federal/leis-ordinarias/1990/lei-8078-1990-09-11",   // id da norma no site
  "slug": "cdc",                                              // nome dos arquivos
  "nome": "Código de Defesa do Consumidor",
  "stj": "LEI:008078 ANO:1990",                               // como o STJ escreve a norma nas referências
  "datajud": { "tribunal": "stj", "assuntos": ["Planos de Saúde", "..."] }   // opcional
}
```

A chave `stj` é o começo da referência sem o `LEG:FED`: `LEI:` lei ordinária, `DEL:` decreto-lei, `LCP:` lei complementar, `CFB:****** ANO:1988` Constituição. Os nomes de assunto precisam ser iguais aos da Tabela Processual Unificada; os que não existirem no tribunal aparecem no log e são ignorados.

## Rodar localmente

```bash
python integracoes/jurisprudencia/coletar.py stj --saida data/jurisprudencia            # tudo (~500 arquivos mensais)
python integracoes/jurisprudencia/coletar.py stj --saida /tmp/juris --amostra          # só 2 arquivos, para testar
python integracoes/jurisprudencia/coletar.py datajud --saida data/jurisprudencia
python -m unittest discover -s integracoes/jurisprudencia/tests -v
```

Os arquivos mensais do STJ ficam resumidos em `~/.cache/juris-stj/` (na Action, no cache do GitHub), então só o que mudou é baixado de novo.
