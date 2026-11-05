import { test } from "node:test";
import assert from "node:assert/strict";
import { candidatas, cacheControl } from "../src/rotas.js";

test("lei sem extensão procura o .html", () => {
  assert.deepEqual(candidatas("/lei/federal/leis-ordinarias/1990/lei-8078-1990-09-11"),
    ["lei/federal/leis-ordinarias/1990/lei-8078-1990-09-11.html",
     "lei/federal/leis-ordinarias/1990/lei-8078-1990-09-11/index.html"]);
});

test("arquivo com extensão é procurado como está", () => {
  assert.deepEqual(candidatas("/api/v1/ref/federal/lcp/101.json"), ["api/v1/ref/federal/lcp/101.json"]);
  assert.deepEqual(candidatas("/lei/estaduais/SP/leis-ordinarias/2020/lei-1-2020-01-01.html"),
    ["lei/estaduais/SP/leis-ordinarias/2020/lei-1-2020-01-01.html"]);
});

test("barra no fim e caracteres codificados", () => {
  assert.deepEqual(candidatas("/lei/constituicao/"), ["lei/constituicao/index.html", "lei/constituicao.html"]);
  assert.deepEqual(candidatas("/pagefind/a%20b.pf_meta"), ["pagefind/a b.pf_meta"]);
});

test("caminhos inválidos não vão ao R2", () => {
  assert.deepEqual(candidatas("/"), []);
  assert.deepEqual(candidatas("/lei/../segredo"), []);
  assert.deepEqual(candidatas("/%E0%A4%A"), []);
});

test("cache por tipo", () => {
  assert.equal(cacheControl("lei/x.html"), "public, max-age=300");
  assert.equal(cacheControl("api/v1/x.json"), "public, max-age=3600");
  assert.equal(cacheControl("pagefind/x.pf_fragment"), "public, max-age=86400");
});

test("tipo pelo nome", async () => {
  const { tipoPorNome } = await import("../src/rotas.js");
  assert.equal(tipoPorNome("lei/x.html"), "text/html; charset=utf-8");
  assert.equal(tipoPorNome("api/v1/a.JSON"), "application/json");
  assert.equal(tipoPorNome("pagefind/x.pf_fragment"), "application/octet-stream");
});
