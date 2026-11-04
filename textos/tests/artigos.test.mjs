import { test } from "node:test";
import assert from "node:assert/strict";
import { dividirArtigos, textoPlano } from "../artigos.mjs";

const MD = `---
titulo: "Lei de teste"
---
# Lei de teste

Preâmbulo que não é artigo.

### TÍTULO I — DAS REGRAS

**Art. 1º** O consumidor pode desistir do contrato no prazo de 7 dias. *(Redação dada pela Lei nº 1, de 2000)*

I - por telefone;

**Parágrafo único.** Os valores serão devolvidos.

**Art. 2º** *(Revogado)*

#### CAPÍTULO II — DO TELETRABALHO

**Art. 75-B.** Considera-se [teletrabalho](http://x) a prestação de serviços fora da empresa.

# ATO DAS DISPOSIÇÕES TRANSITÓRIAS

**Art. 1º** Repetido no ato transitório, sem âncora própria na página.

## TÍTULO X — OUTRO

**Art. 1º** Repetido de novo, debaixo de um h2.
`;

test("um registro por artigo, com a âncora da página da lei", () => {
  const a = dividirArtigos(MD);
  assert.deepEqual(a.map(x => [x.ancora, x.rotulo]), [
    ["art-1", "art. 1º"],
    ["art-75-b", "art. 75-B"],
    [null, "art. 1º"],
    ["sec-3", "art. 1º"],
  ]);
});

test("o artigo inclui incisos e parágrafos e guarda a seção", () => {
  const [a] = dividirArtigos(MD);
  assert.match(a.texto, /por telefone/);
  assert.match(a.texto, /Parágrafo único\. Os valores/);
  assert.equal(a.secao, "TÍTULO I — DAS REGRAS");
  assert.doesNotMatch(a.texto, /Redação dada/);
  assert.doesNotMatch(a.texto, /\*/);
});

test("artigo só com (Revogado) não entra", () => {
  assert.ok(!dividirArtigos(MD).some(x => x.ancora === "art-2"));
});

test("textoPlano tira links e marcação", () => {
  assert.equal(textoPlano("**Art. 3** Veja [a lei](http://x) e _isto_."), "Art. 3 Veja a lei e isto.");
});
