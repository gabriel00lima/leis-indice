import { marked } from "../vendor/marked.esm.js";
import DOMPurify from "../vendor/purify.es.mjs";
import { regexCitacao, interpretar, citacoes, chave, ID_CONSTITUICAO } from "./citacoes.js";
import {
  RAW, GITHUB, API, buscarEntrada, resolverChave, vinculos, rotuloDoId, urlLei,
  formatarData, usandoExemplo,
} from "./dados.js";

const $ = s => document.querySelector(s);
const params = new URLSearchParams(location.search);

// ---------- utilidades ----------

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

function lerFrontmatter(md) {
  const m = /^---\n([\s\S]*?)\n---\n?/.exec(md);
  const fm = {};
  if (!m) return [fm, md];
  for (const linha of m[1].split("\n")) {
    const kv = /^([a-z_]+):\s*(.*)$/.exec(linha);
    if (!kv) continue;
    let v = kv[2].trim();
    if (v.startsWith('"') && v.endsWith('"')) { try { v = JSON.parse(v); } catch { v = v.slice(1, -1); } }
    else if (v === "true" || v === "false") v = v === "true";
    fm[kv[1]] = v;
  }
  return [fm, md.slice(m[0].length)];
}

const idArtigo = (num, letra) => "art-" + num + (letra ? "-" + letra.toLowerCase() : "");

// Link de uma citação: id exato quando a data é completa; senão resolvido pelo índice.
function hrefCitacao(ref) {
  const ancora = ref.artigo ? "art-" + ref.artigo.toLowerCase() : null;
  if (ref.id) return urlLei(ref.id, ancora);
  return "lei.html?ref=" + encodeURIComponent(chave(ref.tipo.prefixo, ref.numero, ref.ano)) + (ancora ? "#" + ancora : "");
}

// ---------- links cruzados no texto ----------

const RE_ART_INTERNO = /\barts?\.\s*(\d+)[º°]?(?:-([A-Z]))?/g;

function linkarTexto(no, idAtual) {
  const texto = no.nodeValue;
  const partes = [];
  let ultimo = 0, achou = false;

  const empurrarInternos = (trecho) => {
    let i = 0, m;
    RE_ART_INTERNO.lastIndex = 0;
    while ((m = RE_ART_INTERNO.exec(trecho))) {
      const depois = trecho.slice(m.index + m[0].length, m.index + m[0].length + 80);
      const deOutra = !/^[^.;]{0,60}?\s(?:desta|deste|nesta|neste)\b/.test(depois) &&
        /^\s*(?:,[^.;]{0,50})?\s+d[aoe]s?\s+(?!presente)/.test(depois);
      const alvo = idArtigo(m[1], m[2]);
      if (deOutra || !document.getElementById(alvo)) continue;
      partes.push(trecho.slice(i, m.index), el("a", { href: "#" + alvo, class: "ref-interna", texto: m[0] }));
      i = m.index + m[0].length;
      achou = true;
    }
    partes.push(trecho.slice(i));
  };

  const re = regexCitacao();
  let m;
  while ((m = re.exec(texto))) {
    const ref = interpretar(m);
    if (!ref || ref.id === idAtual) continue;
    empurrarInternos(texto.slice(ultimo, m.index));
    const titulo = ref.constituicao ? "Constituição Federal"
      : `${ref.tipo.nome} nº ${ref.numero}${ref.ano ? "/" + ref.ano : ""}`;
    partes.push(el("a", {
      href: hrefCitacao(ref), class: "ref-externa",
      title: titulo + (ref.artigo ? ", art. " + ref.artigo : ""), texto: m[0],
    }));
    ultimo = m.index + m[0].length;
    achou = true;
  }
  empurrarInternos(texto.slice(ultimo));
  if (achou) no.replaceWith(...partes.filter(p => p !== ""));
}

function linkarTudo(raiz, idAtual) {
  const walker = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.parentElement.closest("a, h1, h2, h3, h4, h5, h6, code")
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const nos = [];
  while (walker.nextNode()) nos.push(walker.currentNode);
  for (const n of nos) linkarTexto(n, idAtual);
}

// ---------- âncoras de artigos e sumário ----------

function marcarArtigos(raiz) {
  for (const p of raiz.querySelectorAll("p")) {
    const forte = p.firstElementChild;
    if (!forte || forte.tagName !== "STRONG" || p.firstChild !== forte) continue;
    const m = /^Art\.\s*(\d+)(?:[º°.])?(?:\s*-\s*([A-Z])\b)?/.exec(forte.textContent.trim());
    if (!m) continue;
    const id = idArtigo(m[1], m[2]);
    if (document.getElementById(id)) continue;
    p.id = id;
    p.classList.add("artigo");
    const a = el("a", { href: "#" + id, class: "ancora", "aria-label": "Link para este artigo", texto: "#" });
    p.prepend(a);
  }
  let n = 0;
  for (const h of raiz.querySelectorAll("h2, h3, h4, h5")) if (!h.id) h.id = "sec-" + ++n;
}

function montarSumario(raiz) {
  const nav = $("#sumario");
  nav.innerHTML = "";
  const titulos = raiz.querySelectorAll("h2, h3, h4");
  if (!titulos.length) { nav.append(el("p", { class: "vazio", texto: "Sem divisões." })); return; }
  const ul = el("ul");
  for (const h of titulos) {
    ul.append(el("li", { class: "nivel-" + h.tagName[1] }, el("a", { href: "#" + h.id, texto: h.textContent })));
  }
  nav.append(ul);
}

// ---------- alterações anotadas no texto ----------

// Percorre as notas em itálico "(Redação dada pela Lei nº ...)" e agrupa por norma.
function coletarAlteracoes(raiz, idAtual) {
  const grupos = new Map();
  let artAtual = null;
  for (const bloco of raiz.querySelectorAll("p, li, h2, h3, h4, h5")) {
    if (bloco.id?.startsWith("art-")) artAtual = bloco.id;
    for (const em of bloco.querySelectorAll("em")) {
      const t = em.textContent.trim();
      if (!t.startsWith("(")) continue;
      const nota = t.toLowerCase();
      const acao = /revogad/.test(nota) ? "revogou"
        : /vetad/.test(nota) ? "vetou"
        : /acrescid|inclu[íi]d/.test(nota) ? "acrescentou"
        : /reda[çc][ãa]o dada|alterad|renumerad|transformad/.test(nota) ? "alterou" : null;
      if (!acao) continue;
      for (const c of citacoes(t)) {
        if (c.id === idAtual || c.constituicao) continue;
        const k = c.tipo.prefixo + ":" + c.numero + ":" + (c.ano || "");
        if (!grupos.has(k)) grupos.set(k, { ref: c, acoes: new Map(), artigos: [] });
        const g = grupos.get(k);
        g.acoes.set(acao, (g.acoes.get(acao) || 0) + 1);
        if (artAtual && !g.artigos.includes(artAtual)) g.artigos.push(artAtual);
      }
    }
  }
  return [...grupos.values()].sort((a, b) =>
    String(a.ref.data || a.ref.ano || "").localeCompare(String(b.ref.data || b.ref.ano || "")));
}

function mostrarAlteracoes(grupos) {
  const ol = $("#alteracoes");
  ol.innerHTML = "";
  if (!grupos.length) { ol.append(el("li", { class: "vazio", texto: "Nenhuma nota de alteração no texto." })); return; }
  for (const g of grupos) {
    const r = g.ref;
    const nome = `${r.tipo.nome} nº ${Number(r.numero).toLocaleString("pt-BR")}${r.ano ? "/" + r.ano : ""}`;
    const resumo = [...g.acoes].map(([acao, n]) => `${acao} ${n} ${n === 1 ? "dispositivo" : "dispositivos"}`).join(", ");
    const arts = el("span", { class: "artigos" });
    g.artigos.slice(0, 8).forEach((a, i) => {
      if (i) arts.append(", ");
      arts.append(el("a", { href: "#" + a, texto: a.replace("art-", "art. ").replace(/-([a-z])$/, (_, l) => "-" + l.toUpperCase()) }));
    });
    if (g.artigos.length > 8) arts.append(` e mais ${g.artigos.length - 8}`);
    ol.append(el("li", {},
      el("span", { class: "quando", texto: r.data ? formatarData(r.data) : (r.ano || "") }),
      el("a", { href: hrefCitacao({ ...r, artigo: null }), texto: nome }),
      el("span", { class: "resumo", texto: " " + resumo + (g.artigos.length ? ": " : "") }),
      arts));
  }
}

// ---------- vínculos (links.json) ----------

const ROTULOS = [
  ["alterada_por", "Alterada por"], ["revogada_por", "Revogada por"],
  ["altera", "Altera"], ["revoga", "Revoga"], ["cita", "Cita"], ["citada_por", "Citada por"],
];

async function mostrarVinculos(id) {
  const box = $("#vinculos");
  const v = await vinculos(id).catch(() => null);
  box.innerHTML = "";
  const grafo = el("p", {}, el("a", { href: "grafo/?id=" + encodeURIComponent(id), class: "botao", texto: "Ver no grafo" }));
  if (!v || !ROTULOS.some(([k]) => v[k]?.length)) {
    box.append(el("p", { class: "vazio", texto: "Sem relações registradas no índice." }), grafo);
    return;
  }
  for (const [k, rotulo] of ROTULOS) {
    const ids = v[k] || [];
    if (!ids.length) continue;
    const det = el("details", { open: ids.length <= 6 ? "" : null },
      el("summary", {}, rotulo + " ", el("span", { class: "contagem", texto: String(ids.length) })));
    const ul = el("ul");
    for (const outro of ids) ul.append(el("li", {}, el("a", { href: urlLei(outro), texto: rotuloDoId(outro) })));
    det.append(ul);
    box.append(det);
  }
  box.append(grafo);
}

// ---------- histórico git (API do GitHub) ----------

async function mostrarHistorico(caminho) {
  const ol = $("#historico");
  $("#historico-link").replaceChildren(
    el("a", { href: `${GITHUB}/commits/main/${caminho}`, texto: "Ver histórico completo e diffs no GitHub" }));
  try {
    const r = await fetch(`${API}/commits?path=${encodeURIComponent(caminho)}&per_page=15`);
    if (r.status === 403 || r.status === 429) throw new Error("limite de consultas da API do GitHub atingido; tente mais tarde");
    if (!r.ok) throw new Error("erro " + r.status);
    const commits = await r.json();
    ol.innerHTML = "";
    if (!commits.length) { ol.append(el("li", { class: "vazio", texto: "Nenhum commit encontrado." })); return; }
    for (const c of commits) {
      const msg = c.commit.message.split("\n")[0];
      const data = (c.commit.committer?.date || c.commit.author?.date || "").slice(0, 10);
      ol.append(el("li", {},
        el("span", { class: "quando", texto: formatarData(data) }),
        el("a", { href: c.html_url, texto: msg })));
    }
  } catch (err) {
    ol.innerHTML = "";
    ol.append(el("li", { class: "vazio", texto: "Não foi possível carregar: " + err.message + "." }));
  }
}

// ---------- página ----------

function mostrarErro(titulo, detalhe) {
  $("#titulo").textContent = titulo;
  $("#texto").replaceChildren(el("p", { class: "erro", texto: detalhe }),
    el("p", {}, el("a", { href: "./", class: "botao", texto: "Voltar à busca" })));
  $("#sumario").innerHTML = "";
  for (const s of ["#sec-vinculos", "#sec-alteracoes", "#sec-historico"]) $(s).hidden = true;
}

function irParaAncora() {
  if (!location.hash) return;
  const alvo = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (alvo) alvo.scrollIntoView({ block: "start" });
}

async function iniciar() {
  let id = params.get("id");
  const ref = params.get("ref");

  if (!id && ref) {
    const achado = await resolverChave(ref).catch(() => null);
    if (!achado) {
      const [prefixo, numero, ano] = ref.split(":");
      const busca = `./?q=${encodeURIComponent(numero + (ano ? " " + ano : ""))}`;
      mostrarErro("Norma não encontrada no índice",
        `Não achamos ${prefixo} ${numero}${ano ? "/" + ano : ""} no índice.`);
      $("#texto").append(el("p", {}, el("a", { href: busca, texto: "Procurar pelo número na busca" })));
      return;
    }
    id = achado;
    history.replaceState(null, "", urlLei(id) + location.hash);
  }
  if (!id) { mostrarErro("Nenhuma lei indicada", "Abra uma lei a partir da busca."); return; }

  const caminho = id + ".md";
  const [resposta, entrada] = await Promise.all([
    fetch(RAW + caminho).catch(() => null),
    buscarEntrada(id).catch(() => null),
  ]);
  if (!resposta || !resposta.ok) {
    mostrarErro("Lei não encontrada",
      `O arquivo ${caminho} não existe no acervo ctresb/leis (ou o GitHub não respondeu).`);
    return;
  }
  const [fm, corpo] = lerFrontmatter(await resposta.text());
  const info = { ...(entrada || {}), ...fm };
  if (id === ID_CONSTITUICAO && !info.titulo) {
    info.titulo = "Constituição da República Federativa do Brasil de 1988";
    info.tipo = "Constituição"; info.data = "1988-10-05";
  }

  document.title = (info.titulo || rotuloDoId(id)) + " — Leis do Brasil";
  $("#titulo").textContent = info.titulo || rotuloDoId(id);
  const meta = $("#meta");
  meta.textContent = [info.tipo, formatarData(info.data), info.versao_texto].filter(Boolean).join(" · ");
  if (info.revogada) meta.append(" ", el("span", { class: "selo revogada", texto: "Revogada" }));
  if (await usandoExemplo().catch(() => false)) meta.append(" ", el("span", { class: "selo", texto: "índice de exemplo" }));
  $("#ementa").textContent = info.ementa || "";
  const acoes = $("#acoes");
  if (info.fonte) acoes.append(el("a", { href: info.fonte, texto: "Fonte oficial" }));
  acoes.append(el("a", { href: `${GITHUB}/blob/main/${caminho}`, texto: "Ver no GitHub" }));
  acoes.append(el("a", { href: `${GITHUB}/commits/main/${caminho}`, texto: "Histórico" }));
  acoes.append(el("a", { href: "grafo/?id=" + encodeURIComponent(id), texto: "Grafo" }));

  // O título já está no cabeçalho; tira o "# Título" repetido do começo do texto.
  const semTitulo = corpo.replace(/^\s*#\s+[^\n]+\n/, "");
  const html = DOMPurify.sanitize(marked.parse(semTitulo, { gfm: true }));
  const texto = $("#texto");
  texto.innerHTML = html;
  for (const a of texto.querySelectorAll("a[href^='http']")) a.rel = "noopener";

  marcarArtigos(texto);
  linkarTudo(texto, id);
  montarSumario(texto);
  mostrarAlteracoes(coletarAlteracoes(texto, id));
  irParaAncora();

  mostrarVinculos(id);
  mostrarHistorico(caminho);
}

$("#ir-art").addEventListener("submit", ev => {
  ev.preventDefault();
  const v = $("#art").value.trim().replace(/[º°.]/g, "");
  const m = /^(\d+)(?:-?([a-z]))?$/i.exec(v);
  if (!m) return;
  const alvo = idArtigo(m[1], m[2]);
  if (document.getElementById(alvo)) location.hash = alvo;
  else $("#art").setCustomValidity("Artigo não encontrado"), $("#art").reportValidity(), $("#art").setCustomValidity("");
});
window.addEventListener("hashchange", irParaAncora);

iniciar().catch(err => mostrarErro("Erro ao abrir a lei", err.message));
