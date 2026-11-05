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

## Precisão: o acórdão discute o artigo ou só o cita?

As referências legislativas do STJ dizem **quais** artigos um acórdão cita, mas muitas citações são de passagem (o art. 105, III, da CF aparece em quase todo recurso especial; o art. 1.022 do CPC em toda alegação de omissão). Por isso a coleta (`precisao.py`) cruza cada referência com o texto da própria ementa:

- **Parágrafo, inciso e alínea** vêm da referência estruturada (`ART:00206 PAR:00003 INC:00005` → `§ 3º, V`). O site filtra por eles.
- **Onde o artigo aparece na ementa**: `w: "ementa"` quando o corpo da ementa trata do artigo (com o trecho, `x`, e a posição da citação, `h`, para destacar), `w: "lista"` quando só está em "Dispositivos relevantes citados", e sem `w` quando nem aparece. A citação só conta se a ementa disser que é da mesma norma ("art. 155 do CPP" não vale para o CP); se a ementa não disser a norma, só vale quando o número do artigo é de uma única norma nas referências.
- **Relevância** (`precisao.pontuar`): discutir o artigo na ementa pesa mais; depois tema repetitivo, tese, acórdão focado (cita poucos artigos), Seção ou Corte Especial; embargos de declaração e agravos internos pesam menos. A data desempata.
- **Lotes**: acórdãos com ementa idêntica (julgamentos em série) aparecem uma vez, com "+N com a mesma ementa".
- **Tese**: o campo `teseJuridica` do STJ ou o "Tese de julgamento:" da ementa (`s` na decisão).

Medição com 39.669 acórdãos de jun. a set. de 2026: o artigo é discutido na ementa em 68% dos pares acórdão–artigo do CPC, 66% do CDC e do CP, 62% do CC e só 41% da CF; o resto é citação de passagem, que antes aparecia misturada e ordenada só por data.

## Arquivos gerados (`data/jurisprudencia/`)

```
indice.json                 { gerado_em, stj_gerado_em, leis: { <id da norma>: { nome, slug, stj, datajud, total } } }
stj/<slug>.json             resumo: { lei, nome, total, v: 2, periodo: [ini, fim], artigos: { "art-5": 123 }, na_ementa: { "art-5": 40 },
                              dispositivos: { "art-5": { "inc. LV": 9 } }, sem_artigo, bloco, por_artigo }
stj/<slug>/<n>.json         detalhe dos artigos n*100 a n*100+99: { artigos: { "art-5": [item] }, decisoes: { id: decisão } }
                            item = { i: id, d: ["inc. LV"], w: "ementa"|"lista", x: "trecho da ementa", h: [ini, fim], ig: iguais }
stj/<slug>/sem.json         acórdãos que citam a norma sem indicar artigo (mesmo formato, chave "sem-artigo")
stj/_fonte.json             data da última coleta do STJ
datajud/<slug>.json         { lei, gerado_em, tribunais: [{ sigla, total, total_tribunal }], assuntos: [{ nome, total }] }
```

Decisão: `{ p: "REsp 2.260.689", o: "Terceira Turma", r: "Nancy Andrighi", j: "2026-08-04", e: "indexação da ementa…", s: "tese", t: "Tema repetitivo 1076", u: "link da consulta processual" }`.

Para manter os dados pequenos, cada artigo guarda a **contagem** e as **8 decisões mais relevantes** (`stj.decisoes_por_artigo`), mais as 3 melhores de cada um dos 6 dispositivos mais citados; a indexação da ementa é cortada em 260 caracteres (`stj.tamanho_ementa`). O site baixa o resumo ao abrir a lei e o bloco de detalhe só quando alguém clica no selo de um artigo.

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
