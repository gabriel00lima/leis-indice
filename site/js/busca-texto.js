// Busca dentro do texto das leis principais, com o índice Pagefind gerado no
// build (textos/indexar.mjs -> pagefind/). Mostra os artigos que batem com a
// busca acima da lista de normas. Sem o índice (site local, build sem Node),
// a seção simplesmente não aparece.
import { urlLei, numeroBR } from "./dados.js";

const BASE = new URL("../pagefind/", import.meta.url);
const INICIAL = 5, PASSO = 10;

// Termos do dia a dia que a lei escreve de outro jeito. Usados só quando a
// busca literal não acha nada.
const SINONIMOS = {
  "home office": "teletrabalho",
  "trabalho em casa": "teletrabalho",
  "pensao alimenticia": "alimentos",
  "direito do consumidor": "consumidor",
  "dano moral": "danos morais",
};
// Palavras que não ajudam a achar nada e o Pagefind realçaria em todo trecho.
const VAZIAS = new Set("a o as os e de da do das dos em no na nos nas ao aos à às um uma uns umas para por pelo pela com sem que se ou".split(" "));
const consulta = s => s.split(/\s+/).filter(p => !VAZIAS.has(p.toLowerCase())).join(" ");
const semAcento = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

let pf = null, info = null, secao = null, seq = 0, achados = [], mostrados = 0;

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

async function carregar() {
  if (pf) return pf;
  pf = (async () => {
    const [m, i] = await Promise.all([
      import(new URL("pagefind.js", BASE).href),
      fetch(new URL("leis.json", BASE)).then(r => r.ok ? r.json() : null).catch(() => null),
    ]);
    await m.options({ basePath: BASE.pathname, excerptLength: 26 });
    info = i;
    const css = el("link", { rel: "stylesheet", href: new URL("../css/busca-texto.css", import.meta.url).href });
    document.head.append(css);
    return m;
  })();
  pf.catch(() => { pf = Promise.resolve(null); });
  return pf;
}

function montarSecao(antesDe) {
  if (secao) return secao;
  secao = el("section", { class: "no-texto", "aria-labelledby": "no-texto-titulo", hidden: "" },
    el("div", { class: "no-texto-cabeca" },
      el("h3", { id: "no-texto-titulo", texto: "Dentro do texto das leis" }),
      el("p", { class: "no-texto-sub" })),
    el("ol", { class: "trechos" }),
    el("button", { type: "button", class: "link-botao no-texto-mais", hidden: "" }));
  secao.querySelector(".no-texto-mais").addEventListener("click", () => mostrar(PASSO));
  antesDe.before(secao);
  return secao;
}

// O trecho do Pagefind é HTML com <mark>. Lido com DOMParser (não executa nada)
// e remontado só com texto e <mark>.
function trecho(html) {
  const frag = document.createDocumentFragment();
  const doc = new DOMParser().parseFromString(`<p>${html}</p>`, "text/html");
  for (const n of doc.body.firstChild.childNodes) {
    if (n.nodeName === "MARK") frag.append(el("mark", { texto: n.textContent }));
    else frag.append(n.textContent);
  }
  return frag;
}

async function mostrar(n) {
  const minha = seq;
  const lote = await Promise.all(achados.slice(mostrados, mostrados + n).map(r => r.data()));
  if (minha !== seq) return;
  const ol = secao.querySelector(".trechos");
  for (const d of lote) {
    const m = d.meta || {};
    ol.append(el("li", { class: "trecho" },
      el("a", { class: "trecho-titulo", href: m.id ? urlLei(m.id, m.ancora || null) : d.url },
        el("span", { class: "trecho-lei", texto: m.lei || m.title }),
        m.artigo ? el("span", { class: "trecho-artigo", texto: m.artigo }) : ""),
      m.secao ? el("p", { class: "trecho-secao", texto: m.secao }) : "",
      el("p", { class: "trecho-texto" }, "… ", trecho(d.excerpt), " …")));
  }
  mostrados += lote.length;
  const botao = secao.querySelector(".no-texto-mais");
  const resta = achados.length - mostrados;
  botao.hidden = resta <= 0;
  botao.textContent = `Mostrar mais ${numeroBR(Math.min(PASSO, resta))} trechos`;
}

// texto: a busca digitada. antesDe: elemento antes do qual a seção entra.
// opcoes.ocultar: true quando os filtros excluem as leis principais.
export async function buscarNoTexto(texto, antesDe, opcoes = {}) {
  const minha = ++seq;
  const t = String(texto || "").trim();
  // Números ("8.078", "13.709/2018") e termos curtos ficam com a busca por título.
  const palavras = t.replace(/[\d.\/\-ºª°]+/g, " ").trim();
  if (secao) secao.hidden = true;
  if (!palavras || palavras.length < 3 || opcoes.ocultar) return;

  const m = await carregar();
  if (!m || minha !== seq) return;
  let r, usado = t;
  try {
    r = await m.search(consulta(t) || t);
    const alt = SINONIMOS[semAcento(t)];
    if (!r?.results?.length && alt) { usado = alt; r = await m.search(consulta(alt)); }
  } catch { return; }
  if (minha !== seq || !r) return;

  montarSecao(antesDe);
  achados = r.results || [];
  mostrados = 0;
  secao.querySelector(".trechos").replaceChildren();
  if (!achados.length) return;
  const nLeis = info?.leis?.length;
  secao.querySelector(".no-texto-sub").textContent =
    `${numeroBR(achados.length)} ${achados.length === 1 ? "artigo menciona" : "artigos mencionam"} “${usado}”` +
    (nLeis ? ` nas ${numeroBR(nLeis)} leis mais consultadas` : "") + "." +
    (usado !== t ? ` A lei não usa “${t}”; este é o termo equivalente.` : "");
  await mostrar(INICIAL);
  if (minha === seq) secao.hidden = false;
}
