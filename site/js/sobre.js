// Página "O acervo em números": tipos, décadas e ligações, a partir de destaques.json.
import { destaques, numeroBR, formatarData } from "./dados.js";

const $ = s => document.querySelector(s);
const ano = d => String(d || "").slice(0, 4);

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

function plural(t) {
  return { "Lei Ordinária": "Leis ordinárias", "Decreto-Lei": "Decretos-leis", "Lei Complementar": "Leis complementares",
    "Emenda Constitucional": "Emendas constitucionais", "Constituição": "Constituição" }[t] || t;
}

async function montar() {
  let d;
  try { d = await destaques(); } catch { d = null; }
  if (!d) { $("#texto-numeros").textContent = "Não foi possível carregar as estatísticas do índice."; return; }

  const stat = (k, v) => { const x = document.querySelector(`[data-stat="${k}"]`); if (x) x.textContent = v; };
  stat("total", numeroBR(d.total));
  stat("revogadas", numeroBR(d.revogadas));
  stat("ligacoes", numeroBR(d.ligacoes));
  stat("desde", ano(d.mais_antiga));

  $("#texto-numeros").textContent =
    `${numeroBR(d.total_federal ?? d.total)} normas federais indexadas, de ${ano(d.mais_antiga)} até hoje. ` +
    `${numeroBR(d.revogadas)} estão marcadas como revogadas no acervo.`;

  // Por tipo
  const tipos = [...d.por_tipo].sort((a, b) => b.total - a.total);
  $("#por-tipo").replaceChildren(...tipos.map(t =>
    el("a", { class: "cartao-tipo", href: "./?tipo=" + encodeURIComponent(t.tipo) + "&ordem=recentes" },
      el("span", { class: "tipo-numero", texto: numeroBR(t.total) }),
      el("span", { class: "tipo-nome", texto: t.total === 1 ? t.tipo : plural(t.tipo) }),
      el("span", { class: "tipo-sub", texto: t.revogadas ? `${numeroBR(t.revogadas)} revogadas` : "vigente" }))));

  // Por década (barras)
  const maxD = Math.max(...d.por_decada.map(x => x.total));
  $("#por-decada").replaceChildren(...d.por_decada.map(x => {
    const h = Math.max(2, Math.round(100 * x.total / maxD));
    return el("div", { class: "barra", title: `${x.decada}s: ${numeroBR(x.total)} normas` },
      el("span", { class: "barra-valor", texto: x.total >= maxD * 0.12 ? numeroBR(x.total) : "" }),
      el("span", { class: "barra-coluna", style: `height:${h}%` }),
      el("span", { class: "barra-rotulo", texto: x.decada % 20 === 0 ? String(x.decada) : "" }));
  }));

  // Ligações
  const lt = d.ligacoes_por_tipo || {};
  const tiposLig = [["cita", "citações"], ["altera", "alterações"], ["revoga", "revogações"]];
  $("#ligacoes").replaceChildren(
    el("p", { class: "ligacoes-titulo" }, el("strong", { texto: numeroBR(d.ligacoes) }), " ligações entre normas extraídas do texto"),
    el("div", { class: "ligacoes-barra" },
      ...tiposLig.map(([k, r]) => el("span", { class: "seg seg-" + k, style: `flex:${lt[k] || 0}`, title: `${numeroBR(lt[k])} ${r}` }))),
    el("p", { class: "ligacoes-legenda" },
      ...tiposLig.map(([k, r]) => el("span", {}, el("i", { class: "seg-" + k }), `${numeroBR(lt[k])} ${r}`))));

  // Fonte
  const c = d.fonte?.commit;
  const gerado = formatarData(String(d.gerado_em || "").slice(0, 10));
  $("#fonte-indice").replaceChildren(
    `Índice gerado em ${gerado} a partir do acervo `, el("a", { href: "https://github.com/ctresb/leis", texto: "ctresb/leis" }),
    ...(c ? [" (commit ", el("a", { href: `https://github.com/ctresb/leis/commit/${c}`, texto: c.slice(0, 7) }), ")"] : []),
    `. A norma mais nova do acervo é de ${formatarData(d.recentes?.[0]?.data)}.`);
  $("#rodape-indice").replaceChildren(`${numeroBR(d.total)} normas, gerado em ${gerado}`);
}

montar();
