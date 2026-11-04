// "Lei explicada": resumos em linguagem simples guardados em explicadas/*.md.
// Usado pela página explicada.html, pelo destaque na página da lei e pela home.
import { marked } from "../vendor/marked.esm.js";
import DOMPurify from "../vendor/purify.es.mjs";
import { formatarData, urlLei } from "./dados.js";

const BASE = "explicadas/";

export const AVISO =
  "Resumo em linguagem simples, feito para orientar. Não é aconselhamento jurídico e não substitui " +
  "o texto oficial da lei nem a orientação de um advogado ou da Defensoria Pública. As leis mudam: " +
  "confira sempre os artigos citados.";

let indice = null;

export async function listaExplicadas() {
  if (!indice) {
    indice = fetch(BASE + "index.json")
      .then(r => (r.ok ? r.json() : { explicadas: [] }))
      .then(d => d.explicadas || [])
      .catch(() => []);
  }
  return indice;
}

export async function explicadaDaLei(id) {
  return (await listaExplicadas()).find(e => e.lei === id) || null;
}

export async function explicadaPorSlug(slug) {
  return (await listaExplicadas()).find(e => e.slug === slug) || null;
}

function tirarFrontmatter(md) {
  return md.replace(/^---\n[\s\S]*?\n---\n?/, "");
}

// Divide o Markdown em seções "## Título" -> texto.
function secoes(md) {
  const mapa = new Map();
  let atual = "";
  for (const linha of md.split("\n")) {
    const m = /^##\s+(.+)$/.exec(linha);
    if (m) { atual = m[1].trim(); mapa.set(atual, []); continue; }
    if (!mapa.has(atual)) mapa.set(atual, []);
    mapa.get(atual).push(linha);
  }
  return new Map([...mapa].map(([k, v]) => [k, v.join("\n").trim()]));
}

export async function carregarExplicada(slug) {
  const r = await fetch(BASE + encodeURIComponent(slug) + ".md");
  if (!r.ok) throw new Error("resumo não encontrado");
  const corpo = tirarFrontmatter(await r.text());
  return { corpo, secoes: secoes(corpo) };
}

// Converte Markdown em HTML seguro. Links "#art-5" apontam para a lei do resumo:
// na página da própria lei ficam como âncora; nas outras viram link para a lei (urlLei).
export function renderizar(md, leiId, { mesmaPagina = false } = {}) {
  const div = document.createElement("div");
  div.innerHTML = DOMPurify.sanitize(marked.parse(md, { gfm: true }));
  for (const a of div.querySelectorAll("a[href]")) {
    const href = a.getAttribute("href");
    if (href.startsWith("#art-")) {
      if (!mesmaPagina) a.setAttribute("href", urlLei(leiId, href.slice(1)));
      a.classList.add("ref-artigo");
    } else if (/^https?:/.test(href)) {
      a.rel = "noopener";
    }
  }
  for (const t of div.querySelectorAll("table")) {
    const rolagem = document.createElement("div");
    rolagem.className = "tabela-rolagem";
    t.replaceWith(rolagem);
    rolagem.append(t);
  }
  return div;
}

export function textoRevisao(e) {
  const quando = e.revisado_em ? "Revisado em " + formatarData(e.revisado_em) : "";
  const ia = /\bia\b|intelig/i.test(e.origem || "");
  return [quando, ia ? "texto gerado com ajuda de IA" : ""].filter(Boolean).join(" · ");
}

export function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

export function cartaoExplicada(e) {
  return el("a", { class: "cartao-explicada", href: "explicada.html?lei=" + encodeURIComponent(e.slug) },
    el("span", { class: "etiqueta", texto: e.sigla && e.sigla !== e.nome ? e.sigla : "Lei explicada" }),
    el("h3", { texto: e.nome }),
    el("p", { class: "cartao-desc", texto: e.resumo }),
    el("span", { class: "cartao-rodape" },
      el("span", { texto: e.artigos_citados ? `${e.artigos_citados} artigos citados` : "" }),
      el("span", { class: "cartao-ler", texto: "Ler explicação →" })));
}
