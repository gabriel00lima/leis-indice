import { marked } from "../vendor/marked.esm.js";
import DOMPurify from "../vendor/purify.es.mjs";
import { prepararComparacao } from "./comparar.js";
import { regexCitacao, interpretar, citacoes, chave, ID_CONSTITUICAO } from "./citacoes.js";
import {
  RAW, GITHUB, API, buscarEntrada, resolverChave, vinculos, rotuloDoId, urlLei,
  formatarData, usandoExemplo, ehExterno, numeroBR, APELIDOS, UFS, ufDoId,
} from "./dados.js";
import { citacaoABNT, rotuloArtigo } from "./abnt.js";

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

// UF da norma aberta (null nas federais). Numa lei estadual, "Lei nº X" pode ser do
// estado ou federal: o link vai por ?ref=…&uf=, que procura primeiro no estado.
let ufAtual = null;

// Link de uma citação: id exato quando a data é completa; senão resolvido pelo índice.
// Devolve null quando não dá para resolver (ex.: "Constituição do Estado" numa lei federal).
function hrefCitacao(ref) {
  const ancora = ref.artigo ? "art-" + ref.artigo.toLowerCase() : null;
  const hash = ancora ? "#" + ancora : "";
  if (ref.estadual && ref.constituicao) {
    return ufAtual ? "lei.html?ref=constituicao-estadual::&uf=" + ufAtual + hash : null;
  }
  if (ufAtual && !ref.constituicao && ref.esfera !== "federal") {
    return "lei.html?ref=" + encodeURIComponent(chave(ref.tipo.prefixo, ref.numero, ref.ano)) + "&uf=" + ufAtual + hash;
  }
  if (ref.id) return urlLei(ref.id, ancora);
  if (!ref.tipo) return null;
  return "lei.html?ref=" + encodeURIComponent(chave(ref.tipo.prefixo, ref.numero, ref.ano)) + hash;
}

// ---------- links cruzados no texto ----------

const RE_ART_INTERNO = /\b(?:arts?\.|[Aa]rtigos?)\s*(\d{1,3}(?:\.\d{3})+|\d+)[º°]?(?:-([A-Z]))?/g;

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
      const alvo = idArtigo(m[1].replace(/\./g, ""), m[2]);
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
    if (!ref || (ref.id && ref.id === idAtual)) continue;
    const href = hrefCitacao(ref);
    if (!href) continue;
    empurrarInternos(texto.slice(ultimo, m.index));
    const titulo = ref.estadual ? "Constituição do Estado" : ref.constituicao ? "Constituição Federal"
      : `${ref.tipo.nome} nº ${ref.numero}${ref.ano ? "/" + ref.ano : ""}`;
    partes.push(el("a", {
      href, class: "ref-externa",
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

let idPagina = null;

function marcarArtigos(raiz) {
  for (const p of raiz.querySelectorAll("p")) {
    const forte = p.firstElementChild;
    if (!forte || forte.tagName !== "STRONG" || p.firstChild !== forte) continue;
    // "Art. 1.196." (Código Civil) tem ponto de milhar: vira art-1196.
    const m = /^Art(?:igo)?\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:[º°.])?(?:\s*-\s*([A-Z])\b)?/.exec(forte.textContent.trim());
    if (!m) continue;
    const id = idArtigo(m[1].replace(/\./g, ""), m[2]);
    if (document.getElementById(id)) continue;
    p.id = id;
    p.classList.add("artigo");
    const a = el("a", { href: "#" + id, class: "ancora", "aria-label": "Link para este artigo", texto: "#" });
    p.prepend(a);
    if (idPagina) {
      const citar = el("button", { type: "button", class: "citar-art", "data-art": id, title: "Citar este artigo (ABNT)", texto: "Citar" });
      forte.after(" ", citar);
    }
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
        if ((c.id && c.id === idAtual) || c.constituicao || !c.tipo) continue;
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
      el("a", { href: hrefCitacao({ ...r, artigo: null }) || "#", texto: nome }),
      el("span", { class: "resumo", texto: " " + resumo + (g.artigos.length ? ": " : "") }),
      arts));
  }
}

// ---------- vínculos (links.json) ----------

const ROTULOS = [
  ["alterada_por", "Alterada por"], ["revogada_por", "Revogada (no todo ou em parte) por"],
  ["altera", "Altera"], ["revoga", "Revoga (no todo ou em parte)"], ["cita", "Cita"], ["citada_por", "Citada por"],
];

function itemVinculo(outro) {
  const nome = APELIDOS[outro] || rotuloDoId(outro);
  if (ehExterno(outro)) {
    return el("li", { class: "externo" },
      el("a", { href: urlLei(outro), title: "Fora do índice: procurar na busca", texto: nome }),
      el("span", { class: "fora", texto: "fora do índice" }));
  }
  return el("li", {}, el("a", { href: urlLei(outro), texto: nome }));
}

async function mostrarVinculos(id) {
  const box = $("#vinculos");
  const v = await vinculos(id).catch(() => null);
  box.innerHTML = "";
  const grafo = el("a", { href: "grafo/?id=" + encodeURIComponent(id), class: "botao botao-cheio", texto: "Explorar no grafo →" });
  if (!v || !ROTULOS.some(([k]) => v[k]?.length)) {
    box.append(el("p", { class: "vazio", texto: "Nenhuma relação registrada no índice para esta norma." }), grafo);
    return v;
  }
  for (const [k, rotulo] of ROTULOS) {
    const ids = v[k] || [];
    if (!ids.length) continue;
    const det = el("details", { class: "rel rel-" + k, open: ids.length <= 5 ? "" : null },
      el("summary", {}, el("span", { texto: rotulo }), el("span", { class: "contagem", texto: numeroBR(ids.length) })));
    const ul = el("ul");
    const LIMITE = 60;
    for (const outro of ids.slice(0, LIMITE)) ul.append(itemVinculo(outro));
    if (ids.length > LIMITE) {
      const resto = el("li", {}, el("button", { class: "link-botao", type: "button", texto: `Mostrar mais ${numeroBR(ids.length - LIMITE)}` }));
      resto.firstChild.addEventListener("click", () => {
        resto.replaceWith(...ids.slice(LIMITE).map(itemVinculo));
      });
      ul.append(resto);
    }
    det.append(ul);
    box.append(det);
  }
  box.append(grafo);
  return v;
}

function mostrarContadores(v) {
  const dl = $("#contadores");
  dl.replaceChildren();
  if (!v) return;
  for (const [k, r] of [["citada_por", "normas citam esta"], ["alterada_por", "leis alteraram esta"], ["cita", "normas citadas aqui"]]) {
    const n = (v[k] || []).length;
    if (!n && k !== "citada_por") continue;
    dl.append(el("div", {}, el("dd", { texto: numeroBR(n) }), el("dt", { texto: r })));
  }
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

// ---------- citação ABNT ----------

let infoPagina = {};

async function copiarTexto(botao, texto) {
  const antes = botao.textContent;
  try { await navigator.clipboard.writeText(texto); botao.textContent = "Copiado"; }
  catch { botao.textContent = "Selecione e copie"; }
  setTimeout(() => { botao.textContent = antes; }, 1800);
}

function linhaCitacao(rotulo, valor, dica) {
  const campo = el("p", { class: "citacao-valor", texto: valor });
  const botao = el("button", { type: "button", class: "botao", texto: "Copiar" });
  botao.addEventListener("click", () => copiarTexto(botao, valor));
  return el("div", { class: "citacao-linha" },
    el("div", { class: "citacao-rotulo" }, el("strong", { texto: rotulo }), dica ? el("span", { texto: dica }) : ""),
    campo, botao);
}

function abrirCitacao(artigo) {
  const c = citacaoABNT(idPagina, infoPagina, { artigo });
  if (!c) return;
  const link = location.href.split("#")[0] + (artigo ? "#" + artigo : "");
  const dlg = $("#citacao");
  const corpo = $("#citacao-corpo");
  $("#citacao-titulo").textContent = artigo ? "Citar o " + rotuloArtigo(artigo) : "Citar esta norma";
  corpo.replaceChildren(
    linhaCitacao("Referência", c.referencia, "ABNT NBR 6023, para a lista de referências"),
    linhaCitacao("Citação no texto", c.chamada, "ABNT NBR 10520, autor-data"),
    linhaCitacao("Link direto", link, artigo ? "abre a página já no artigo" : ""));
  dlg.showModal();
}

// ---------- página ----------

function mostrarErro(titulo, detalhe) {
  $("#carregando-texto").hidden = true;
  $("#titulo").textContent = titulo;
  $("#texto").replaceChildren(el("p", { class: "erro", texto: detalhe }),
    el("p", {}, el("a", { href: "./", class: "botao", texto: "Voltar à busca" })));
  $("#sumario").innerHTML = "";
  for (const s of ["#sec-vinculos", "#sec-alteracoes", "#sec-historico"]) $(s).hidden = true;
}

const temPagina = id => !urlLei(id).startsWith("lei.html") && !ehExterno(id);

function irParaAncora() {
  if (!location.hash) return;
  const alvo = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (alvo) alvo.scrollIntoView({ block: "start" });
}

async function iniciar() {
  // Nas páginas geradas (lei/<id>.html) o id vem no <body data-lei>.
  let id = params.get("id") || document.body.dataset.lei;
  const ref = params.get("ref");

  if (!id && ref) {
    const achado = await resolverChave(ref, params.get("uf")).catch(() => null);
    if (!achado) {
      const [prefixo, numero, ano] = ref.split(":");
      const ufRef = params.get("uf");
      const busca = `./?q=${encodeURIComponent(numero + (ano ? " " + ano : ""))}` + (ufRef ? "&ambito=todas" : "");
      mostrarErro("Norma não encontrada no índice",
        `Não achamos ${prefixo} ${numero}${ano ? "/" + ano : ""} no índice.`);
      $("#texto").append(el("p", {}, el("a", { href: busca, texto: "Procurar pelo número na busca" })));
      return;
    }
    id = achado;
    if (temPagina(id)) { location.replace(urlLei(id) + location.hash); return; }
    history.replaceState(null, "", urlLei(id) + location.hash);
  }
  if (!id) { mostrarErro("Nenhuma lei indicada", "Abra uma lei a partir da busca."); return; }

  const caminho = id + ".md";
  ufAtual = ufDoId(id);
  const [resposta, entrada] = await Promise.all([
    fetch(RAW + caminho).catch(() => null),
    buscarEntrada(id).catch(() => null),
  ]);
  // lei.html?id= de uma norma do índice: vai para a página própria (lei/<id>),
  // que é o endereço com prévia para compartilhar.
  if (entrada && !document.body.dataset.lei && temPagina(id)) {
    location.replace(urlLei(id) + location.hash);
    return;
  }
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

  const apelido = APELIDOS[id];
  const tituloLei = info.titulo || rotuloDoId(id);
  document.title = (apelido ? `${apelido} (${tituloLei})` : tituloLei) + " · Leis do Brasil";
  $("#titulo").textContent = apelido || tituloLei;
  if (apelido && apelido !== tituloLei) { $("#subtitulo").textContent = tituloLei; $("#subtitulo").hidden = false; }

  const trilha = $("#trilha");
  if (ufAtual) trilha.append(el("a", { href: "./?ambito=" + ufAtual + "&ordem=recentes", texto: UFS[ufAtual] || ufAtual }));
  if (info.tipo) trilha.append(el("a", {
    href: "./?tipo=" + encodeURIComponent(info.tipo) + (ufAtual ? "&ambito=" + ufAtual : "") + "&ordem=recentes", texto: info.tipo }));
  if (info.data && id !== ID_CONSTITUICAO) trilha.append(el("span", { texto: String(info.data).slice(0, 4) }));

  const selos = $("#selos");
  selos.append(el("span", { class: info.revogada ? "chip chip-revogada" : "chip chip-vigente", texto: info.revogada ? "Revogada" : "Em vigor" }));
  if (info.data) selos.append(el("span", { class: "chip chip-neutro", texto: "Publicada em " + formatarData(info.data) }));
  if (ufAtual) selos.append(el("span", { class: "chip chip-uf", title: "Norma estadual", texto: "Estadual · " + ufAtual }));
  if (info.versao_texto) {
    const v = String(info.versao_texto);
    selos.append(el("span", { class: "chip chip-neutro", title: v, texto: "Texto " + (v.length > 60 ? v.slice(0, 57).trimEnd() + "…" : v) }));
  }
  if (await usandoExemplo().catch(() => false)) selos.append(el("span", { class: "chip", texto: "índice de exemplo" }));
  $("#ementa").textContent = info.ementa || "";

  const acoes = $("#acoes");
  const icone = d => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.innerHTML = d; return s; };
  const acao = (href, texto, d) => el("a", { href, class: "acao" }, icone(d), texto);
  if (info.fonte) acoes.append(acao(info.fonte, "Fonte oficial", '<path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>'));
  acoes.append(acao(`${GITHUB}/blob/main/${caminho}`, "Ver no GitHub", '<path d="M8 4 3 12l5 8M16 4l5 8-5 8"/>'));
  acoes.append(acao(`${GITHUB}/commits/main/${caminho}`, "Histórico", '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'));
  acoes.append(acao("grafo/?id=" + encodeURIComponent(id), "Grafo", '<circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="5" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="M7.3 11 16.7 6M7.3 13l9.4 5"/>'));
  const copiar = el("button", { type: "button", class: "acao" }, icone('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>'), "Copiar link");
  copiar.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); copiar.lastChild.textContent = "Link copiado"; }
    catch { copiar.lastChild.textContent = "Não deu para copiar"; }
    setTimeout(() => { copiar.lastChild.textContent = "Copiar link"; }, 2000);
  });
  acoes.append(copiar);
  infoPagina = info;
  if (citacaoABNT(id, info)) {
    const citar = el("button", { type: "button", class: "acao" }, icone('<path d="M7 7h4v4c0 3-1.5 5-4 6M15 7h4v4c0 3-1.5 5-4 6"/>'), "Citar (ABNT)");
    citar.addEventListener("click", () => abrirCitacao(null));
    acoes.append(citar);
  }

  // O título já está no cabeçalho; tira o "# Título" repetido do começo do texto.
  const semTitulo = corpo.replace(/^\s*#\s+[^\n]+\n/, "");
  const html = DOMPurify.sanitize(marked.parse(semTitulo, { gfm: true }));
  const texto = $("#texto");
  $("#carregando-texto").hidden = true;
  texto.innerHTML = html;
  for (const a of texto.querySelectorAll("a[href^='http']")) a.rel = "noopener";

  idPagina = citacaoABNT(id, info) ? id : null;
  marcarArtigos(texto);
  linkarTudo(texto, id);
  montarSumario(texto);
  mostrarAlteracoes(coletarAlteracoes(texto, id));
  prepararComparacao({ raiz: texto, id, corpo, info }).catch(() => {});
  irParaAncora();

  mostrarVinculos(id).then(mostrarContadores);
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
$("#texto").addEventListener("click", ev => {
  const b = ev.target.closest?.(".citar-art");
  if (b) abrirCitacao(b.dataset.art);
});
$("#citacao").addEventListener("click", ev => {
  if (ev.target === ev.currentTarget || ev.target.closest(".citacao-fechar")) ev.currentTarget.close();
});
window.addEventListener("hashchange", irParaAncora);
// As páginas geradas têm <base href> apontando para a raiz do site, então um
// href="#art-5" levaria para a página inicial. Mantém a âncora nesta página.
if (document.querySelector("base")) {
  document.addEventListener("click", ev => {
    const a = ev.target.closest?.('a[href^="#"]');
    if (!a || ev.defaultPrevented || ev.button || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    ev.preventDefault();
    const alvo = a.getAttribute("href");
    if (alvo === "#") { history.replaceState(null, "", location.pathname + location.search); scrollTo({ top: 0 }); }
    else location.hash = alvo;
  });
}
window.addEventListener("scroll", () => {
  $("#voltar-topo").classList.toggle("visivel", scrollY > 900);
}, { passive: true });

iniciar().catch(err => mostrarErro("Erro ao abrir a lei", err.message));
