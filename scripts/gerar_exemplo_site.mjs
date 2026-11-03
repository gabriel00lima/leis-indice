#!/usr/bin/env node
// Gera dados de exemplo para o site (site/exemplo/index.json e links.json)
// baixando um punhado de normas de ctresb/leis. Serve só para desenvolver o
// site antes do índice completo (data/) existir. Mesmo formato do índice real.
//
// Uso: node scripts/gerar_exemplo_site.mjs

import { writeFile } from "node:fs/promises";
import { citacoes, relacao, chave, chaveDoId, ID_CONSTITUICAO } from "../site/js/citacoes.js";

const RAW = "https://raw.githubusercontent.com/ctresb/leis/main/";

const IDS = [
  "constituicao",
  "federal/leis-ordinarias/1990/lei-8078-1990-09-11",
  "federal/leis-ordinarias/1995/lei-9008-1995-03-21",
  "federal/leis-ordinarias/1994/lei-8884-1994-06-11",
  "federal/leis-ordinarias/2021/lei-14181-2021-07-01",
  "federal/leis-ordinarias/2015/lei-13146-2015-07-06",
  "federal/leis-ordinarias/2012/lei-12741-2012-12-08",
  "federal/leis-ordinarias/2017/lei-13486-2017-10-03",
  "federal/leis-ordinarias/2008/lei-11800-2008-10-29",
  "federal/leis-ordinarias/2009/lei-11989-2009-07-27",
  "federal/leis-ordinarias/2017/lei-13425-2017-03-30",
  "federal/leis-ordinarias/2002/lei-10406-2002-01-10",
  "federal/leis-ordinarias/2014/lei-12965-2014-04-23",
  "federal/leis-ordinarias/2018/lei-13709-2018-08-14",
  "federal/leis-ordinarias/1990/lei-8069-1990-07-13",
  "federal/leis-ordinarias/1997/lei-9503-1997-09-23",
  "federal/leis-ordinarias/1966/lei-5172-1966-10-25",
  "federal/leis-ordinarias/1990/lei-8112-1990-12-11",
  "federal/decretos-lei/1940/del-2848-1940-12-07",
  "federal/decretos-lei/1943/del-5452-1943-05-01",
  "federal/leis-complementares/2000/lcp-101-2000-05-04",
  "federal/emendas-constitucionais/2004/emc-45-2004-12-08",
];

function frontmatter(md) {
  const m = /^---\n([\s\S]*?)\n---\n/.exec(md);
  const out = {};
  if (!m) return out;
  for (const linha of m[1].split("\n")) {
    const kv = /^([a-z_]+):\s*(.*)$/.exec(linha);
    if (!kv) continue;
    let v = kv[2].trim();
    if (v.startsWith('"') && v.endsWith('"')) v = JSON.parse(v);
    else if (v === "true" || v === "false") v = v === "true";
    out[kv[1]] = v;
  }
  return out;
}

const indice = [];
const textos = {};
for (const id of IDS) {
  const r = await fetch(RAW + id + ".md");
  if (!r.ok) { console.error("falhou", id, r.status); continue; }
  const md = await r.text();
  textos[id] = md;
  const fm = frontmatter(md);
  if (id === ID_CONSTITUICAO) {
    Object.assign(fm, {
      titulo: "Constituição da República Federativa do Brasil de 1988",
      tipo: "Constituição", numero: "", data: "1988-10-05",
      ementa: "Constituição Federal de 1988 (texto compilado).", revogada: false,
      urn: "urn:lex:br:federal:constituicao:1988-10-05;1988",
    });
  }
  indice.push({
    id, path: id + ".md",
    titulo: fm.titulo, tipo: fm.tipo, numero: String(fm.numero ?? ""),
    data: fm.data, ementa: fm.ementa, revogada: !!fm.revogada, urn: fm.urn,
  });
  console.error("ok", id);
}

// Resolve citações sem data completa pelo índice (tipo+número+ano).
const porChave = new Map(indice.map(e => [chaveDoId(e.id), e.id]));
const existe = new Set(indice.map(e => e.id));
const links = {};
const vazio = () => ({ cita: [], altera: [], revoga: [], citada_por: [], alterada_por: [], revogada_por: [] });
for (const e of indice) links[e.id] = vazio();

for (const [id, md] of Object.entries(textos)) {
  const corpo = md.replace(/^---\n[\s\S]*?\n---\n/, "");
  for (const c of citacoes(corpo)) {
    const alvo = c.id && existe.has(c.id) ? c.id
      : c.tipo ? porChave.get(chave(c.tipo.prefixo, c.numero, c.ano)) : null;
    if (!alvo || alvo === id) continue;
    const rel = relacao(corpo, c.inicio);
    // Nota "(redação dada pela Lei X)" dentro da lei A: X altera A.
    const [origem, destino, ida, volta] =
      rel === "alterada" ? [alvo, id, "altera", "alterada_por"]
      : rel === "revogada" ? [alvo, id, "revoga", "revogada_por"]
      : rel === "revoga" ? [id, alvo, "revoga", "revogada_por"]
      : [id, alvo, "cita", "citada_por"];
    if (!links[origem][ida].includes(destino)) links[origem][ida].push(destino);
    if (!links[destino][volta].includes(origem)) links[destino][volta].push(origem);
  }
}

await writeFile(new URL("../site/exemplo/index.json", import.meta.url),
  JSON.stringify(indice, null, 1) + "\n");
await writeFile(new URL("../site/exemplo/links.json", import.meta.url),
  JSON.stringify(links, null, 1) + "\n");
console.error(`${indice.length} normas no índice de exemplo`);
