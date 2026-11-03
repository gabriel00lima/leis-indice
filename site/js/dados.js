// Carregamento do índice (data/index.json) e dos vínculos (data/links.json).
// Se data/ ainda não existir no site publicado, usa os dados de exemplo.
// Formatos aceitos: ver site/README.md.

import { chaveDoId } from "./citacoes.js";

export const RAW = "https://raw.githubusercontent.com/ctresb/leis/main/";
export const GITHUB = "https://github.com/ctresb/leis";
export const API = "https://api.github.com/repos/ctresb/leis";

const BASES = ["data/", "exemplo/"];
let base = null;

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ao baixar ${url}`);
  return r.json();
}

// Descobre onde estão os dados (data/ ou exemplo/) e lê o index.json.
let manifestoP = null;
export function manifesto() {
  if (!manifestoP) manifestoP = (async () => {
    for (const b of BASES) {
      try {
        const m = await json(b + "index.json");
        base = b;
        return Array.isArray(m) ? { total: m.length, entradas: m, shards: null } : m;
      } catch { /* tenta a próxima base */ }
    }
    throw new Error("Índice não encontrado em data/index.json.");
  })();
  return manifestoP;
}

export async function usandoExemplo() {
  await manifesto();
  return base === "exemplo/";
}

// Shards: { arquivo, tipo?, total? }. Índice em array único vira um shard só.
export async function listaShards() {
  const m = await manifesto();
  if (m.entradas) return [{ arquivo: null, tipo: null, total: m.total }];
  return m.shards;
}

const cacheShard = new Map();
export async function carregarShard(s) {
  const m = await manifesto();
  if (!s.arquivo) return m.entradas;
  if (!cacheShard.has(s.arquivo)) {
    cacheShard.set(s.arquivo, json(base + s.arquivo).then(normalizar));
  }
  return cacheShard.get(s.arquivo);
}

// Aceita shards como array de objetos ou { campos: [...], linhas: [[...]] }.
function normalizar(d) {
  if (Array.isArray(d)) return d;
  if (d && d.campos && d.linhas) {
    return d.linhas.map(l => Object.fromEntries(d.campos.map((c, i) => [c, l[i]])));
  }
  return d.entradas || [];
}

// Carrega todos os shards (ou só os de um tipo), avisando o progresso.
export async function carregarTudo(aoProgredir, tipo) {
  const shards = (await listaShards()).filter(s => !tipo || !s.tipo || s.tipo === tipo);
  let feitos = 0;
  const partes = await Promise.all(shards.map(async s => {
    const e = await carregarShard(s);
    aoProgredir?.(++feitos, shards.length);
    return e;
  }));
  return partes.flat();
}

// Acha uma entrada do índice pelo id, carregando só o shard provável.
export async function buscarEntrada(id) {
  const shards = await listaShards();
  const pasta = id.split("/")[1];
  const ordenados = [...shards].sort((a, b) =>
    (b.arquivo?.includes(pasta) ? 1 : 0) - (a.arquivo?.includes(pasta) ? 1 : 0));
  for (const s of ordenados) {
    const e = (await carregarShard(s)).find(x => x.id === id);
    if (e) return e;
  }
  return null;
}

// Resolve tipo+número+ano para um id do índice (citações sem data completa).
export async function resolverChave(k) {
  const [prefixo] = k.split(":");
  const shards = await listaShards();
  for (const s of shards) {
    if (s.arquivo && s.prefixo && s.prefixo !== prefixo) continue;
    const e = (await carregarShard(s)).find(x => chaveDoId(x.id) === k);
    if (e) return e.id;
  }
  return null;
}

// Vínculos de uma norma. links.json pode ser um objeto único ou um manifesto
// { shards: [{ arquivo, pasta? }] } com objetos menores.
let linksP = null;
export async function vinculos(id) {
  await manifesto();
  if (!linksP) linksP = json(base + "links.json").catch(() => ({}));
  const l = await linksP;
  if (!l.shards) return l[id] || null;
  const pasta = id.split("/")[1] || id;
  const s = l.shards.find(x => x.pasta === pasta) || null;
  const alvos = s ? [s] : l.shards;
  for (const x of alvos) {
    if (!cacheShard.has("links:" + x.arquivo)) cacheShard.set("links:" + x.arquivo, json(base + x.arquivo).catch(() => ({})));
    const d = await cacheShard.get("links:" + x.arquivo);
    if (d[id]) return d[id];
  }
  return null;
}

// Rótulo curto de uma norma a partir do id, sem precisar do índice.
export function rotuloDoId(id) {
  if (id === "constituicao") return "Constituição Federal de 1988";
  const m = /\/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-\d{2}-\d{2}$/.exec(id);
  if (!m) return id.split("/").pop();
  const nomes = { lei: "Lei", lcp: "Lei Complementar", del: "Decreto-Lei", dec: "Decreto",
    dlg: "Decreto Legislativo", mpv: "Medida Provisória", emc: "Emenda Constitucional", ldl: "Lei Delegada" };
  const n = Number(m[2]).toLocaleString("pt-BR");
  return `${nomes[m[1]] || m[1]} nº ${n}/${m[3]}`;
}

export function urlLei(id, ancora) {
  return "lei.html?id=" + encodeURIComponent(id) + (ancora ? "#" + ancora : "");
}

export function formatarData(d) {
  if (!d) return "";
  const [a, m, dia] = String(d).split("-");
  return dia ? `${dia}/${m}/${a}` : d;
}

export function normalizarTexto(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
