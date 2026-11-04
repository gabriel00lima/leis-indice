// Dados do Diário Oficial (data/dou/, gerados por integracoes/dou/coletar.py).
// Caminhos relativos a este módulo, para servir tanto em dou/ quanto em lei.html.

const BASES = ["../data/dou/", "../../data/dou/"].map(b => new URL(b, import.meta.url).href);
let baseP = null;
const cache = new Map();

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ao baixar ${url}`);
  return r.json();
}

export function manifestoDou() {
  if (!baseP) baseP = (async () => {
    for (const b of BASES) {
      try { const m = await json(b + "index.json"); return { base: b, m }; } catch { /* próxima */ }
    }
    throw new Error("Dados do Diário Oficial ainda não gerados (data/dou/index.json).");
  })();
  return baseP.then(x => x.m);
}

// Arquivo de data/dou/ pelo caminho do manifesto ("dou/meses/2025-09.json") ou nome.
export async function arquivoDou(caminho) {
  await manifestoDou();
  const { base } = await baseP;
  const url = base + caminho.replace(/^dou\//, "");
  if (!cache.has(url)) cache.set(url, json(url).catch(e => { cache.delete(url); throw e; }));
  return cache.get(url);
}

export const urlLeiDou = id => new URL("../lei.html?id=" + encodeURIComponent(id), import.meta.url).href;

const MINUSCULAS = new Set(["de", "da", "do", "das", "dos", "e"]);
// "LEI Nº 15.100, DE 10 DE MARÇO DE 2025" -> "Lei nº 15.100, de 10 de março de 2025"
export function tituloAto(identifica) {
  return String(identifica || "").toLowerCase()
    .replace(/(^|\s)([a-zà-ú])/g, (t, esp, l) => esp + l.toUpperCase())
    .replace(/\b(De|Da|Do|Das|Dos|E)\b/g, p => (MINUSCULAS.has(p.toLowerCase()) ? p.toLowerCase() : p))
    .replace(/\bJaneiro|Fevereiro|Março|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|Dezembro\b/g, m => m.toLowerCase())
    .replace(/\bNº/g, "nº").replace(/\bN°/g, "nº")
    .replace(/(\d)º De /g, "$1º de ");
}
