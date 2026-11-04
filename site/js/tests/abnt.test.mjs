import { test } from "node:test";
import assert from "node:assert/strict";
import { citacaoABNT, dataPorExtenso, dataAcesso, rotuloArtigo, podeCitar } from "../abnt.js";

const acesso = new Date(2026, 10, 4);

test("lei ordinária com fonte normas.leg.br", () => {
  const c = citacaoABNT("federal/leis-ordinarias/1990/lei-8078-1990-09-11", {
    tipo: "Lei Ordinária", numero: "8078", data: "1990-09-11",
    ementa: "Dispõe sobre a proteção do consumidor e dá outras providências.",
    fonte: "https://normas.leg.br/?urn=urn:lex:br:federal:lei:1990-09-11;8078",
  }, { artigo: "art-49", acesso });
  assert.equal(c.referencia,
    "BRASIL. Lei nº 8.078, de 11 de setembro de 1990. Dispõe sobre a proteção do consumidor e dá outras providências. " +
    "Brasília, DF: Congresso Nacional, 1990. Disponível em: https://normas.leg.br/?urn=urn:lex:br:federal:lei:1990-09-11;8078. " +
    "Acesso em: 4 nov. 2026.");
  assert.equal(c.chamada, "(BRASIL, 1990, art. 49)");
});

test("emenda constitucional leva Constituição (ano)", () => {
  const c = citacaoABNT("federal/emendas-constitucionais/1995/emc-9-1995-11-09", {
    tipo: "Emenda Constitucional", numero: "9", data: "1995-11-09", ementa: "Dá nova redação ao art. 177",
    fonte: "https://www.planalto.gov.br/x.htm",
  }, { acesso });
  assert.match(c.referencia, /^BRASIL\. Constituição \(1988\)\. Emenda constitucional nº 9, de 9 de novembro de 1995\. Dá nova redação ao art\. 177\. Brasília, DF: Presidência da República, 1995\./);
  assert.equal(c.chamada, "(BRASIL, 1995)");
  const antiga = citacaoABNT("federal/emendas-constitucionais/1969/emc-1-1969-10-17",
    { tipo: "Emenda Constitucional", numero: "1", data: "1969-10-17" }, { acesso });
  assert.match(antiga.referencia, /Constituição \(1967\)\. Emenda constitucional nº 1, de 17 de outubro de 1969\./);
});

test("Constituição de 1988", () => {
  const c = citacaoABNT("constituicao", {}, { artigo: "art-5", acesso });
  assert.match(c.referencia, /^BRASIL\. \[Constituição \(1988\)\]\. Constituição da República Federativa do Brasil de 1988\. Brasília, DF: Presidência da República, \[2026\]\. Disponível em: https:\/\/www\.planalto\.gov\.br\/.+\. Acesso em: 4 nov\. 2026\.$/);
  assert.equal(c.chamada, "(BRASIL, [2026], art. 5º)");
});

test("utilitários", () => {
  assert.equal(dataPorExtenso("2002-01-01"), "1º de janeiro de 2002");
  assert.equal(dataAcesso(new Date(2026, 4, 9)), "9 maio 2026");
  assert.equal(rotuloArtigo("art-10-a"), "art. 10-A");
  assert.equal(rotuloArtigo("art-9"), "art. 9º");
  assert.equal(podeCitar("estaduais/SP/x"), false);
  assert.equal(citacaoABNT("estaduais/SP/x", {}), null);
});
