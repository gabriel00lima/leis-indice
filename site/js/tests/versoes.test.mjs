// Testes da leitura de versões (site/js/versoes.js). Rodar: node --test site/js/tests/versoes.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  artigoVigente, extrairAlteracao, completarComNotas, montarLinhaDoTempo,
  originaisDoPlanalto, diferenca, chaveDaDescricao, artigosMencionados,
} from "../versoes.js";

const CDC = { prefixo: "lei", numero: "8078", ano: "1990" };
const CF = { constituicao: true };

const VIGENTE_CDC = `---
titulo: "Lei nº 8.078 de 11/09/1990"
---
# Lei nº 8.078 de 11/09/1990

**Art. 38.** O ônus da prova cabe a quem as patrocina.

**Art. 39.** É vedado ao fornecedor de produtos ou serviços, dentre outras práticas abusivas: *(“Caput” do artigo com redação dada pela Lei nº 8.884, de 11/6/1994)*

I - condicionar o fornecimento de produto ou de serviço;

XII - deixar de estipular prazo para o cumprimento de sua obrigação. *(Inciso acrescido pela Lei nº 9.008, de 21/3/1995)*

XIII - aplicar fórmula ou índice de reajuste diverso do legal ou contratualmente estabelecido. *(Inciso acrescido pela Lei nº 9.870, de 23/11/1999)*

**Parágrafo único.** Os serviços prestados equiparam-se às amostras grátis.

**Art. 40.** O fornecedor de serviço será obrigado a entregar orçamento.
`;

const LEI_9870 = `---
titulo: "Lei nº 9.870"
---
# Lei nº 9.870

Dispõe sobre o valor total das anuidades escolares e altera o art. 39 da Lei nº 8.078, de 1990.

**Art. 1º** O valor das anuidades será contratado.

**Art. 7º** São legitimados à propositura das ações previstas na Lei nº 8.078, de 1990, as associações de alunos.

**Art. 8º** O art. 39 da Lei nº 8.078, de 1990, passa a vigorar acrescido do seguinte inciso:

"XIII - aplicar fórmula ou índice de reajuste diverso do legal ou contratualmente estabelecido."

**Art. 9º** A Lei nº 9.131, de 24 de novembro de 1995, passa a vigorar acrescida dos seguintes artigos:

"Art. 39. Texto de outra lei que não deve entrar."
`;

const LEI_9008 = `# Lei nº 9.008

**Art. 1º** Fica criado o Conselho.

**Art. 7º.** Os arts. 4º, 39, 82, 91 e 98 da Lei nº 8.078, de 1990, passam a vigorar com a seguinte redação:

"Art. 4º. A Política Nacional das Relações de Consumo tem por objetivo:

................................................................................ "

"Art. 39. ..........................................................................

XII - deixar de estipular prazo para o cumprimento de sua obrigação."

"Art. 82. ..........................................................................

I - o Ministério Público,"

**Art. 8º** Esta Lei entra em vigor na data de sua publicação.
`;

const EC_28 = `# Emenda Constitucional nº 28

***Dá nova redação ao inciso XXIX do art. 7º e revoga o art. 233 da Constituição Federal.***

**Art**. 1º O inciso XXIX do art. 7º da Constituição Federal passa a vigorar com a seguinte redação:

“XXIX - ação, quanto aos créditos resultantes das relações de trabalho, com prazo prescricional de cinco anos;” (NR)

“a) (Revogada)”.

“b) (Revogada)”.

**Art**. 2º Revoga-se o art. 233 da Constituição Federal.
`;

test("artigoVigente separa os dispositivos e as notas", () => {
  const v = artigoVigente(VIGENTE_CDC, "39");
  assert.deepEqual([...v.keys()], ["caput", "caput/iI", "caput/iXII", "caput/iXIII", "pu"]);
  assert.equal(v.get("caput").texto, "É vedado ao fornecedor de produtos ou serviços, dentre outras práticas abusivas:");
  assert.match(v.get("caput").notas[0], /8\.884/);
  assert.equal(artigoVigente(VIGENTE_CDC, "40").get("caput").texto, "O fornecedor de serviço será obrigado a entregar orçamento.");
});

test("lê acréscimo de inciso com o artigo só no comando", () => {
  const r = extrairAlteracao(LEI_9870, CDC, "39");
  assert.equal(r.acao, "acrescimo");
  assert.deepEqual([...r.dispositivos.keys()], ["caput/iXIII"]);
  assert.match(r.dispositivos.get("caput/iXIII").texto, /^aplicar fórmula/);
});

test("lê vários artigos entre aspas e ignora reticências", () => {
  const r39 = extrairAlteracao(LEI_9008, CDC, "39");
  assert.deepEqual([...r39.dispositivos.keys()], ["caput/iXII"]);
  const r4 = extrairAlteracao(LEI_9008, CDC, "4");
  assert.deepEqual([...r4.dispositivos.keys()], ["caput"]);
  assert.equal(extrairAlteracao(LEI_9008, CDC, "5"), null);
});

test("ementa não conta e alíneas seguem o inciso do bloco anterior", () => {
  const r = extrairAlteracao(EC_28, CF, "7");
  assert.deepEqual([...r.dispositivos.keys()], ["caput/iXXIX", "caput/iXXIX/aa", "caput/iXXIX/ab"]);
  assert.equal(r.dispositivos.get("caput/iXXIX/aa").texto, "(Revogado)");
  assert.equal(r.revogados.length, 0);
  const r233 = extrairAlteracao(EC_28, CF, "233");
  assert.equal(r233.revogados[0].chave, "artigo");
});

test("linha do tempo: acréscimos, notas e o que está em vigor", () => {
  const vig = artigoVigente(VIGENTE_CDC, "39");
  const eventos = [
    { lei: { id: "federal/leis-ordinarias/1995/lei-9008-1995-03-21", data: "1995-03-21" }, ...extrairAlteracao(LEI_9008, CDC, "39") },
    { lei: { id: "federal/leis-ordinarias/1999/lei-9870-1999-11-23", data: "1999-11-23" }, ...extrairAlteracao(LEI_9870, CDC, "39") },
  ];
  const linha = montarLinhaDoTempo(completarComNotas(eventos, vig), vig);
  assert.deepEqual(linha.map(e => e.lei.data), ["1994-06-11", "1995-03-21", "1999-11-23"]);
  const [nota, a, b] = linha;
  assert.equal(nota.mudancas[0].chave, "caput");
  assert.equal(nota.mudancas[0].antes, null);   // redação original não está no acervo
  assert.equal(nota.mudancas[0].daNota, true);
  assert.equal(a.mudancas[0].tipo, "acrescentou");
  assert.equal(a.mudancas[0].antes, "");
  assert.ok(b.mudancas[0].emVigor);
});

test("versão anterior vem da lei anterior; original do Planalto quando há", () => {
  const vig = new Map([["caput", { chave: "caput", texto: "texto três", notas: ["Redação dada pela Lei nº 3, de 1/1/2003"] }]]);
  const ev = (n, t) => ({ lei: { id: `federal/leis-ordinarias/200${n}/lei-${n}-200${n}-01-01`, data: `200${n}-01-01` },
    acao: "redacao", revogados: [], dispositivos: new Map([["caput", { chave: "caput", rotulo: "caput", texto: t, notas: [], ordem: 0 }]]) });
  const linha = montarLinhaDoTempo([ev(2, "texto dois"), ev(3, "texto três")], vig, new Map([["caput", "texto um"]]));
  assert.equal(linha[0].mudancas[0].antes, "texto um");
  assert.equal(linha[0].mudancas[0].antesLei, "original");
  assert.equal(linha[1].mudancas[0].antes, "texto dois");
  assert.ok(linha[1].mudancas[0].emVigor);
  assert.ok(!linha[0].mudancas[0].emVigor);
});

test("originaisDoPlanalto pega a redação tachada sem nota", () => {
  const html = `<p><a name="art7"></a>Art. 7&ordm; S&atilde;o direitos dos trabalhadores:</p>
  <p><strike>XII - sal&aacute;rio-fam&iacute;lia para os seus dependentes;</strike></p>
  <p>XII - salário-família pago em razão do dependente; <a href="#">(Redação dada pela Emenda Constitucional nº 20, de 1998)</a></p>
  <p>XIII - duração do trabalho normal não superior a oito horas diárias;</p>
  <p><strike>XXIX - ação, com prazo prescricional de:</strike></p>
  <p><strike><a name="x"></a></strike> a) <strike>cinco anos para o trabalhador urbano;</strike><br>
  b) <strike>até dois anos para o trabalhador rural;</strike></p>
  <p>XXIX - ação, com prazo de cinco anos; (Redação dada pela Emenda Constitucional nº 28, de 2000)</p>
  <p>Art. 8º É livre a associação.</p>
  <p><strike>I - não deve entrar;</strike></p>`;
  const o = originaisDoPlanalto(html, "7");
  assert.equal(o.get("caput/iXII"), "salário-família para os seus dependentes;");
  assert.equal(o.get("caput/iXIII"), "duração do trabalho normal não superior a oito horas diárias;");
  assert.equal(o.get("caput/iXXIX/aa"), "cinco anos para o trabalhador urbano;");
  assert.equal(o.get("caput/iXXIX/ab"), "até dois anos para o trabalhador rural;");
  assert.ok(!o.has("caput/iI"));
});

test("utilitários", () => {
  assert.deepEqual(artigosMencionados("Os arts. 4º, 39, 82, 91 e 98 da Lei"), ["4", "39", "82", "91", "98"]);
  assert.deepEqual(artigosMencionados("o art. 54-A e o art. 1.228"), ["54-A", "1228"]);
  assert.equal(chaveDaDescricao("o inciso IV do § 2º"), "p2/iIV");
  assert.equal(chaveDaDescricao("o parágrafo único"), "pu");
  assert.equal(chaveDaDescricao("o inciso III"), "caput/iIII");
  const d = diferenca("seis anos de idade", "5 (cinco) anos de idade");
  assert.equal(d.filter(p => p.tipo !== "entrou").map(p => p.texto).join(""), "seis anos de idade");
  assert.equal(d.filter(p => p.tipo !== "saiu").map(p => p.texto).join(""), "5 (cinco) anos de idade");
  assert.equal(d.filter(p => p.tipo === "saiu").map(p => p.texto).join("").trim(), "seis");
});
