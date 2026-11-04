// "Comparar versões": em cada artigo alterado, um botão abre a lista das mudanças,
// com a redação de antes e a de depois lado a lado. As regras de leitura ficam em
// versoes.js; aqui só busca os textos e monta a tela.

import { citacoes, chave } from "./citacoes.js";
import { RAW, resolverChave, vinculos, urlLei, rotuloDoId, formatarData } from "./dados.js";
import {
  artigoVigente, extrairAlteracao, completarComNotas, montarLinhaDoTempo,
  originaisDoPlanalto, diferenca, normArt,
} from "./versoes.js";

const MAX_LEIS = 40;          // leis alteradoras baixadas por artigo, no máximo
const PARALELO = 6;
const FONTE_CF = RAW + "fonte/constituicao.htm"; // compilado do Planalto, com redações tachadas

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v === true ? "" : v);
  }
  e.append(...filhos.filter(f => f != null && f !== false));
  return e;
}

// ---------- dados ----------

const textos = new Map();
function baixarTexto(id) {
  if (!textos.has(id)) {
    textos.set(id, fetch(RAW + id + ".md").then(r => (r.ok ? r.text() : null)).catch(() => null));
  }
  return textos.get(id);
}

let originaisCF = null;
function htmlDaConstituicao() {
  if (!originaisCF) {
    originaisCF = fetch(FONTE_CF)
      .then(r => (r.ok ? r.arrayBuffer() : null))
      .then(b => (b ? new TextDecoder("windows-1252").decode(b) : null))
      .catch(() => null);
  }
  return originaisCF;
}

// Ligações com os artigos envolvidos, da API estática (api/v1/normas/<id>.json).
let ligacoesP = null;
function ligacoesDa(id) {
  if (!ligacoesP) {
    ligacoesP = fetch("api/v1/normas/" + id.split("/").map(encodeURIComponent).join("/") + ".json")
      .then(r => (r.ok ? r.json() : null))
      .then(j => j && [...(j.ligacoes?.alterada_por || []), ...(j.ligacoes?.revogada_por || [])])
      .catch(() => null);
  }
  return ligacoesP;
}

const dataDoId = id => (/(\d{4}-\d{2}-\d{2})$/.exec(id || "") || [])[1] || "";

function alvoDe(id, info) {
  if (id === "constituicao") return { constituicao: true };
  const m = /\/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-\d{2}-\d{2}$/.exec(id);
  if (!m) return null;
  return { prefixo: m[1], numero: String(info.numero || m[2]).replace(/\D/g, "") || m[2], ano: m[3] };
}

// Leis citadas nas notas de alteração de um artigo (id já resolvido quando possível).
async function leisDasNotas(vigente) {
  const ids = new Set();
  for (const d of vigente.values()) {
    for (const nota of d.notas) {
      if (!/reda[çc][ãa]o|acrescid|inclu[íi]d|revogad|renumerad/i.test(nota)) continue;
      for (const c of citacoes(nota)) {
        if (c.constituicao) continue;
        const id = c.id || await resolverChave(chave(c.tipo.prefixo, c.numero, c.ano)).catch(() => null);
        if (id) ids.add(id);
      }
    }
  }
  return ids;
}

async function candidatas(id, art, vigente) {
  const ids = await leisDasNotas(vigente);
  const lig = await ligacoesDa(id);
  if (lig) {
    const semArtigo = [];
    for (const l of lig) {
      if (String(l.id).startsWith("externo:")) continue;
      const disp = (l.dispositivos || []).filter(d => !/ADCT/i.test(d));
      if (disp.some(d => normArt(d) === art)) ids.add(l.id);
      else if (!(l.dispositivos || []).length) semArtigo.push(l.id);
    }
    // Ligações sem artigo identificado só entram se forem poucas (senão seria baixar o histórico todo).
    if (semArtigo.length <= 15) semArtigo.forEach(x => ids.add(x));
  } else {
    const v = await vinculos(id).catch(() => null);
    const todas = [...(v?.alterada_por || []), ...(v?.revogada_por || [])].filter(x => !String(x).startsWith("externo:"));
    if (todas.length <= MAX_LEIS) todas.forEach(x => ids.add(x));
  }
  return [...ids].sort((a, b) => dataDoId(a).localeCompare(dataDoId(b))).slice(-MAX_LEIS);
}

async function emParalelo(itens, fn, aoAvancar) {
  const out = new Array(itens.length);
  let i = 0, feitos = 0;
  await Promise.all(Array.from({ length: Math.min(PARALELO, itens.length) }, async () => {
    while (i < itens.length) {
      const k = i++;
      out[k] = await fn(itens[k]);
      aoAvancar?.(++feitos, itens.length);
    }
  }));
  return out;
}

async function calcularVersoes(ctx, art, aoAvancar) {
  const vigente = artigoVigente(ctx.corpo, art);
  const alvo = alvoDe(ctx.id, ctx.info);
  const ids = alvo ? await candidatas(ctx.id, art, vigente) : [];
  const [lidos, html] = await Promise.all([
    emParalelo(ids, async lid => {
      const md = await baixarTexto(lid);
      if (!md) return null;
      const r = extrairAlteracao(md, alvo, art);
      return r && { lei: { id: lid, data: dataDoId(lid) }, ...r };
    }, aoAvancar),
    ctx.id === "constituicao" ? htmlDaConstituicao() : null,
  ]);
  const originais = html ? originaisDoPlanalto(html, art) : new Map();
  const eventos = completarComNotas(lidos.filter(Boolean), vigente);
  return { linha: montarLinhaDoTempo(eventos, vigente, originais), consultadas: ids.length };
}

// ---------- tela ----------

const NOMES_TIPO = { alterou: "Nova redação", acrescentou: "Acrescentado", revogou: "Revogado", vetou: "Vetado" };

function nomeDaLei(lei) {
  if (lei.id) return rotuloDoId(lei.id);
  const r = lei.ref;
  return r ? `${r.tipo.nome} nº ${Number(r.numero).toLocaleString("pt-BR")}${r.ano ? "/" + r.ano : ""}` : "Norma";
}

function linkDaLei(lei) {
  const nome = nomeDaLei(lei);
  if (lei.id) return el("a", { href: urlLei(lei.id), texto: nome });
  const r = lei.ref;
  if (r?.tipo) return el("a", { href: "lei.html?ref=" + encodeURIComponent(chave(r.tipo.prefixo, r.numero, r.ano)), texto: nome });
  return el("span", { texto: nome });
}

function textoComDiferenca(a, b, lado) {
  const bloco = el("div", { class: "versao-texto" });
  for (const p of diferenca(a, b)) {
    if (p.tipo === "igual") bloco.append(p.texto);
    else if (p.tipo === "saiu" && lado === "antes") bloco.append(el("del", { texto: p.texto }));
    else if (p.tipo === "entrou" && lado === "depois") bloco.append(el("ins", { texto: p.texto }));
  }
  return bloco;
}

function coluna(titulo, conteudo, classe) {
  return el("div", { class: "versao-coluna " + classe }, el("div", { class: "versao-rotulo", texto: titulo }), conteudo);
}

function cartaoMudanca(m, ctx, lei) {
  let antes, depois;
  const rotuloAntes = m.antesLei === "original" ? "Redação original"
    : m.antesLei ? "Antes (" + nomeDaLei(m.antesLei) + ")" : "Antes";
  if (m.antes === null) {
    antes = el("div", { class: "versao-vazia" },
      "A redação anterior não está no acervo. ",
      ctx.info.fonte ? el("a", { href: ctx.info.fonte, rel: "noopener", texto: "Ver na fonte oficial" }) : null);
  } else if (m.antes === "") {
    antes = el("div", { class: "versao-vazia", texto: "Este dispositivo não existia." });
  } else {
    antes = m.depois && m.tipo !== "revogou" ? textoComDiferenca(m.antes, m.depois, "antes") : el("div", { class: "versao-texto", texto: m.antes });
  }
  if (m.tipo === "revogou" && !m.depois) {
    depois = el("div", { class: "versao-vazia", texto: m.descricao ? `Revogado (“${m.descricao}”).` : "Revogado." });
  } else {
    depois = m.antes ? textoComDiferenca(m.antes, m.depois, "depois") : el("div", { class: "versao-texto", texto: m.depois });
  }
  const rodape = [];
  if (m.daNota) rodape.push(el("p", { class: "versao-obs", texto:
    `Este é o texto em vigor, que a nota do acervo atribui a esta norma. ${lei.id ? "O arquivo dela no acervo não traz a nova redação" : "Ela ainda não está no acervo"}.` }));
  return el("div", { class: "versao-mudanca tipo-" + m.tipo },
    el("div", { class: "versao-cabeca" },
      el("strong", { texto: m.rotulo === "caput" ? "Caput" : m.rotulo.charAt(0).toUpperCase() + m.rotulo.slice(1) }),
      el("span", { class: "versao-tipo", texto: NOMES_TIPO[m.tipo] || m.tipo }),
      m.emVigor ? el("span", { class: "versao-vigor", texto: "em vigor" }) : null),
    el("div", { class: "versao-lado-a-lado" },
      coluna(rotuloAntes, antes, "lado-antes"),
      coluna("Depois (" + nomeDaLei(lei) + ")", depois, "lado-depois")),
    ...rodape);
}

function montarPainel(painel, ctx, art, resultado) {
  const { linha, consultadas } = resultado;
  painel.querySelector(".versoes-corpo").replaceChildren();
  const corpo = painel.querySelector(".versoes-corpo");
  if (!linha.length) {
    corpo.append(el("p", { class: "vazio", texto: consultadas
      ? `Consultamos ${consultadas} ${consultadas === 1 ? "lei" : "leis"} que alteraram esta norma, mas nenhuma traz uma nova redação deste artigo que deu para ler.`
      : "Não achamos alterações deste artigo no acervo." }));
    return;
  }
  const ol = el("ol", { class: "versoes-lista" });
  for (const ev of linha) {
    const data = ev.lei.data && !/-12-31$/.test(ev.lei.data) ? formatarData(ev.lei.data) : (ev.lei.ref?.ano || ev.lei.data?.slice(0, 4) || "");
    ol.append(el("li", { class: "versoes-evento" },
      el("div", { class: "versoes-quando" }, el("span", { class: "versoes-data", texto: data }), linkDaLei(ev.lei)),
      ...ev.mudancas.map(m => cartaoMudanca(m, ctx, ev.lei))));
  }
  corpo.append(ol);
  const semAntes = linha.some(ev => ev.mudancas.some(m => m.antes === null));
  corpo.append(el("p", { class: "versoes-nota" },
    "As redações antigas vêm do texto das leis que alteraram o artigo (no acervo ctresb/leis)",
    ctx.id === "constituicao" ? " e do texto compilado do Planalto, que guarda as redações tachadas" : "",
    ". ",
    semAntes ? "Quando a redação anterior não aparece em nenhuma delas, ela fica em branco. " : "",
    "Não substitui a publicação oficial."));
}

function idDoArtigo(art) { return "art-" + art.toLowerCase(); }

async function abrir(ctx, art, { rolar = false } = {}) {
  const p = document.getElementById(idDoArtigo(art));
  if (!p) return;
  const aberto = document.getElementById("versoes-" + idDoArtigo(art));
  const botao = p.querySelector(".botao-versoes");
  if (aberto) {
    if (rolar) { aberto.scrollIntoView({ block: "start" }); return; }
    aberto.remove(); botao?.setAttribute("aria-expanded", "false"); return;
  }
  const rotulo = "art. " + art.replace(/^(\d+)/, n => n + (Number(n) < 10 ? "º" : ""));
  const copiar = el("button", { type: "button", class: "link-botao", texto: "Copiar link" });
  const fechar = el("button", { type: "button", class: "versoes-fechar", "aria-label": "Fechar comparação", texto: "×" });
  const progresso = el("p", { class: "vazio", texto: "Procurando as leis que alteraram este artigo…" });
  const painel = el("section", { class: "versoes", id: "versoes-" + idDoArtigo(art), "aria-label": "Versões do " + rotulo },
    el("header", { class: "versoes-topo" },
      el("h3", { texto: "Como o " + rotulo + " mudou" }), copiar, fechar),
    el("div", { class: "versoes-corpo" }, progresso));
  // O painel entra depois do último parágrafo do artigo (antes do próximo artigo ou título).
  let fim = p;
  while (fim.nextElementSibling && !fim.nextElementSibling.matches(".artigo, h1, h2, h3, h4, h5, h6, .versoes")) fim = fim.nextElementSibling;
  fim.after(painel);
  botao?.setAttribute("aria-expanded", "true");
  fechar.addEventListener("click", () => {
    painel.remove(); botao?.setAttribute("aria-expanded", "false");
    if (location.hash === "#" + painel.id) history.replaceState(null, "", location.pathname + location.search);
    p.scrollIntoView({ block: "nearest" });
  });
  copiar.addEventListener("click", async () => {
    const url = location.href.split("#")[0] + "#" + painel.id;
    try { await navigator.clipboard.writeText(url); copiar.textContent = "Link copiado"; }
    catch { copiar.textContent = "Não deu para copiar"; }
    setTimeout(() => { copiar.textContent = "Copiar link"; }, 2000);
  });
  if (rolar) painel.scrollIntoView({ block: "start" });
  try {
    const r = await calcularVersoes(ctx, art, (n, total) => {
      progresso.textContent = `Lendo as leis que alteraram este artigo (${n} de ${total})…`;
    });
    montarPainel(painel, ctx, art, r);
  } catch (err) {
    painel.querySelector(".versoes-corpo").replaceChildren(
      el("p", { class: "erro", texto: "Não foi possível montar a comparação: " + err.message }));
  }
}

// Artigos com notas de alteração no texto em vigor.
function artigosAlterados(raiz) {
  const out = new Set();
  let atual = null;
  for (const bloco of raiz.querySelectorAll("p, li, h2, h3, h4, h5")) {
    if (bloco.matches("h2, h3, h4, h5")) { atual = null; continue; }
    if (bloco.id?.startsWith("art-")) atual = bloco;
    if (!atual) continue;
    for (const em of bloco.querySelectorAll("em")) {
      if (/reda[çc][ãa]o dada|acrescid|inclu[íi]d|revogad|renumerad/i.test(em.textContent)) { out.add(atual); break; }
    }
  }
  return out;
}

function artDoId(pid) {
  const m = /^art-(\d+)(?:-([a-z]{1,2}))?$/.exec(pid);
  return m ? m[1] + (m[2] ? "-" + m[2].toUpperCase() : "") : null;
}

function porBotao(ctx, p) {
  const art = artDoId(p.id);
  if (!art || p.querySelector(".botao-versoes")) return;
  const b = el("button", { type: "button", class: "botao-versoes", "aria-expanded": "false",
    title: "Ver como este artigo era antes de cada alteração" }, "Comparar versões");
  b.addEventListener("click", () => abrir(ctx, art));
  p.append(" ", b);
}

// ctx: { raiz (o <article>), id, corpo (Markdown sem frontmatter), info (frontmatter + índice) }
export async function prepararComparacao(ctx) {
  for (const p of artigosAlterados(ctx.raiz)) porBotao(ctx, p);
  // Artigos alterados sem nota no texto (o índice sabe quais leis mexeram neles).
  const lig = await ligacoesDa(ctx.id);
  if (lig) {
    for (const l of lig) {
      for (const d of l.dispositivos || []) {
        if (/ADCT/i.test(d)) continue;
        const art = normArt(d);
        const p = art && document.getElementById(idDoArtigo(art));
        if (p && ctx.raiz.contains(p)) porBotao(ctx, p);
      }
    }
  }
  const doHash = () => {
    const m = /^#versoes-art-(.+)$/.exec(decodeURIComponent(location.hash));
    const art = m && artDoId("art-" + m[1]);
    if (art) abrir(ctx, art, { rolar: true });
  };
  window.addEventListener("hashchange", doHash);
  doHash();
}
