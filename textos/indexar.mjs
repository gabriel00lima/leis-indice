#!/usr/bin/env node
// Gera o índice de texto completo (Pagefind) das leis principais, um registro
// por artigo, em <site>/pagefind/. Roda no build do Pages (site/build.sh),
// depois de destaques.json: os textos são baixados do ctresb/leis na hora e
// nada disso é commitado.
//
//   node textos/indexar.mjs --site _site [--acervo pasta-local] [--ids a,b]
//
// Quais leis: as "principais" de destaques.json, mais as vigentes das listas
// "mais citadas" e "mais alteradas". --ids troca essa lista.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { dividirArtigos } from "./artigos.mjs";

const RAW = "https://raw.githubusercontent.com/ctresb/leis/main/";

const { values: op } = parseArgs({
  options: {
    site: { type: "string", default: "_site" },
    acervo: { type: "string" },
    raw: { type: "string", default: RAW },
    ids: { type: "string" },
  },
});

const site = path.resolve(op.site);
const saida = path.join(site, "pagefind");

async function lerJson(f) { return JSON.parse(await readFile(f, "utf8")); }

// [{ id, nome, titulo }]
async function escolherLeis() {
  if (op.ids) return op.ids.split(",").map(id => ({ id: id.trim(), nome: id.trim(), titulo: "" }));
  const d = await lerJson(path.join(site, "destaques.json"));
  const leis = new Map();
  for (const p of d.principais || []) leis.set(p.id, { id: p.id, nome: p.apelido || p.titulo, titulo: p.titulo });
  for (const e of [...(d.mais_citadas || []), ...(d.mais_alteradas || [])]) {
    if (e.revogada || leis.has(e.id) || e.id.startsWith("externo:")) continue;
    leis.set(e.id, { id: e.id, nome: e.titulo, titulo: e.titulo });
  }
  return [...leis.values()];
}

async function baixar(id) {
  if (op.acervo) return readFile(path.join(op.acervo, id + ".md"), "utf8");
  for (let tentativa = 1; ; tentativa++) {
    try {
      const r = await fetch(op.raw + id.split("/").map(encodeURIComponent).join("/") + ".md",
        { signal: AbortSignal.timeout(30000) });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.text();
    } catch (err) {
      if (tentativa >= 3) throw err;
      await new Promise(ok => setTimeout(ok, 1000 * tentativa));
    }
  }
}

// Baixa com no máximo n downloads ao mesmo tempo, mantendo a ordem.
async function emParalelo(itens, n, fn) {
  const res = new Array(itens.length);
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, itens.length) }, async () => {
    while (i < itens.length) { const k = i++; res[k] = await fn(itens[k]).then(v => [v], e => [null, e]); }
  }));
  return res;
}

async function main() {
  const inicio = Date.now();
  const leis = await escolherLeis();
  const textos = await emParalelo(leis, 6, l => baixar(l.id));

  const pagefind = await import("pagefind");
  const { index, errors } = await pagefind.createIndex({ forceLanguage: "pt" });
  if (!index) throw new Error("Pagefind: " + errors.join("; "));

  const resumo = [];
  let registros = 0;
  for (const [k, lei] of leis.entries()) {
    const [md, erro] = textos[k];
    if (!md) { console.warn(`::warning::Texto não baixado (${lei.id}): ${erro?.message}`); continue; }
    const artigos = dividirArtigos(md);
    for (const a of artigos) {
      const r = await index.addCustomRecord({
        url: `lei/${lei.id}.html` + (a.ancora ? "#" + a.ancora : ""),
        content: a.texto,
        language: "pt",
        meta: { title: `${lei.nome}, ${a.rotulo}`, lei: lei.nome, id: lei.id, ancora: a.ancora || "", artigo: a.rotulo, secao: a.secao },
        filters: { lei: [lei.nome] },
      });
      if (r.errors?.length) throw new Error("Pagefind: " + r.errors.join("; "));
    }
    registros += artigos.length;
    if (!artigos.length) { console.warn(`::warning::Nenhum artigo reconhecido em ${lei.id}`); continue; }
    resumo.push({ id: lei.id, nome: lei.nome, artigos: artigos.length });
  }
  if (!resumo.length) throw new Error("nenhum texto baixado");

  const w = await index.writeFiles({ outputPath: saida });
  if (w.errors?.length) throw new Error("Pagefind: " + w.errors.join("; "));
  await pagefind.close();

  await mkdir(saida, { recursive: true });
  await writeFile(path.join(saida, "leis.json"), JSON.stringify({
    gerado_em: new Date().toISOString(), total_artigos: registros, leis: resumo,
  }));
  console.log(`Busca no texto: ${resumo.length} leis, ${registros} artigos em ${((Date.now() - inicio) / 1000).toFixed(1)} s`);
}

main().catch(err => { console.error(err); process.exit(1); });
