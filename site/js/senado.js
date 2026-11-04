// Dados do Senado na página da lei: histórico de alterações por dispositivo e decisões do STF
// (ADI, ADC, ADPF...), lidos de data/senado/normas/<id>.json (gerado por integracoes/senado/).
// Módulo independente de lei.js: espera o texto da lei aparecer e então acrescenta
// o selo no cabeçalho, as marcas nos artigos e duas caixas no painel lateral.

import { urlLei, formatarData, numeroBR } from "./dados.js";

const $ = s => document.querySelector(s);
const BASES = ["data/", "../data/"];

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

async function carregar(id) {
  for (const b of BASES) {
    try {
      const r = await fetch(b + "senado/normas/" + id.split("/").map(encodeURIComponent).join("/") + ".json");
      if (r.ok) return await r.json();
    } catch { /* tenta a próxima base */ }
  }
  return null;
}

// O texto é montado por lei.js depois de baixar o .md; espera ele existir.
function textoPronto() {
  const t = $("#texto");
  if (t && t.childElementCount) return Promise.resolve(t);
  return new Promise(resolve => {
    const obs = new MutationObserver(() => {
      if (t.childElementCount) { obs.disconnect(); resolve(t); }
    });
    obs.observe(t, { childList: true });
  });
}

const EFEITOS = {
  "inconstitucional": { rotulo: "declarado inconstitucional", curto: "Inconstitucional", classe: "efeito-inc" },
  "suspenso": { rotulo: "suspenso por decisão do STF", curto: "Suspenso", classe: "efeito-inc" },
  "interpretacao-conforme": { rotulo: "com interpretação conforme a Constituição", curto: "Interpretação conforme", classe: "efeito-conf" },
  "constitucional": { rotulo: "declarado constitucional", curto: "Constitucional", classe: "efeito-ok" },
  "outro": { rotulo: "objeto de decisão", curto: "Decisão", classe: "efeito-conf" },
};
const GRAVES = new Set(["inconstitucional", "suspenso"]);

const rotuloArt = a => "art. " + a.replace(/-([a-z])$/, (_, l) => "-" + l.toUpperCase());

function nomeDecisao(c) {
  return c.decisao ? `${c.decisao.classe} ${numeroBR(c.decisao.numero)}` : c.nome;
}

function urlDecisao(c) {
  if (!c.decisao) return null;
  return "https://portal.stf.jus.br/processos/listarProcessos.asp?classe=" +
    encodeURIComponent(c.decisao.classe) + "&numeroProcesso=" + encodeURIComponent(c.decisao.numero);
}

function linkArtigo(art) {
  const alvo = "art-" + art;
  return document.getElementById(alvo)
    ? el("a", { href: "#" + alvo, texto: rotuloArt(art) })
    : el("span", { texto: rotuloArt(art) });
}

function listaArtigos(arts, limite = 8) {
  const span = el("span", { class: "artigos" });
  arts.slice(0, limite).forEach((a, i) => { if (i) span.append(", "); span.append(linkArtigo(a)); });
  if (arts.length > limite) span.append(` e mais ${arts.length - limite}`);
  return span;
}

const unicos = xs => [...new Set(xs.filter(Boolean))];

// ---------- selo no cabeçalho ----------

function seloCabecalho(d) {
  const graves = d.controle.flatMap(c => c.dispositivos.filter(x => GRAVES.has(x.efeito)));
  const selos = $("#selos");
  if (!selos) return;
  if (graves.length) {
    const n = graves.length;
    selos.append(el("a", {
      class: "chip chip-adi", href: "#sec-stf",
      title: "Dispositivos declarados inconstitucionais ou suspensos pelo STF, segundo o Senado Federal",
      texto: `${numeroBR(n)} ${n === 1 ? "dispositivo" : "dispositivos"} com ADI`,
    }));
  } else if (d.controle.length) {
    selos.append(el("a", { class: "chip chip-neutro", href: "#sec-stf", texto: "Analisada pelo STF" }));
  }
}

// ---------- marcas nos artigos ----------

function marcarArtigos(d) {
  const porArt = new Map();
  for (const c of d.controle) {
    for (const x of c.dispositivos) {
      if (!x.art || x.efeito === "constitucional") continue;
      if (!porArt.has(x.art)) porArt.set(x.art, []);
      porArt.get(x.art).push({ c, x });
    }
  }
  for (const [art, lista] of porArt) {
    const p = document.getElementById("art-" + art);
    if (!p) continue;
    const grave = lista.some(({ x }) => GRAVES.has(x.efeito));
    const decisoes = unicos(lista.map(({ c, x }) => c.decisao ? nomeDecisao(c) : EFEITOS[x.efeito]?.curto));
    const detalhe = lista.map(({ c, x }) => `${x.dispositivo}: ${EFEITOS[x.efeito]?.rotulo || x.texto} (${nomeDecisao(c)})`);
    const selo = el("a", {
      class: "selo-adi " + (grave ? "efeito-inc" : "efeito-conf"), href: "#sec-stf",
      title: detalhe.join("\n"),
      texto: decisoes.slice(0, 2).join(", ") + (decisoes.length > 2 ? "…" : ""),
    });
    p.querySelector(":scope > strong")?.after(" ", selo);
  }
}

// ---------- caixas do painel ----------

function caixa(id, titulo, dica) {
  const sec = el("section", { class: "caixa caixa-senado", id },
    el("h2", { texto: titulo }));
  if (dica) sec.append(el("p", { class: "dica", texto: dica }));
  return sec;
}

function fonte(d) {
  const p = el("p", { class: "fonte-senado" }, "Fonte: ",
    el("a", { href: "https://legis.senado.leg.br/dadosabertos/legislacao/urn?urn=" + encodeURIComponent(d.urn), rel: "noopener", texto: "Senado Federal, Dados Abertos" }));
  if (d.consultado_em) p.append(`, consultado em ${formatarData(d.consultado_em)}.`);
  return p;
}

function caixaSTF(d) {
  const sec = caixa("sec-stf", "Decisões do STF", "Controle de constitucionalidade registrado pelo Senado Federal.");
  const ol = el("ol", { class: "linha-tempo linha-stf" });
  for (const c of [...d.controle].reverse()) {
    const efeitos = unicos(c.dispositivos.map(x => x.efeito));
    const grave = efeitos.some(e => GRAVES.has(e));
    const li = el("li", { class: grave ? "grave" : null },
      el("span", { class: "quando", texto: formatarData(c.data) }));
    const url = urlDecisao(c);
    li.append(url ? el("a", { href: url, rel: "noopener", title: c.nome, texto: nomeDecisao(c) }) : el("strong", { texto: c.nome }));
    if (!c.dispositivos.length) {
      li.append(el("span", { class: "resumo", texto: ` ${c.tipo.toLowerCase()} da norma.` }));
    } else {
      for (const e of efeitos) {
        const arts = unicos(c.dispositivos.filter(x => x.efeito === e).map(x => x.art));
        const linha = el("div", { class: "efeito-linha" },
          el("span", { class: "efeito " + (EFEITOS[e]?.classe || ""), texto: EFEITOS[e]?.curto || e }));
        if (arts.length) linha.append(" ", listaArtigos(arts));
        li.append(linha);
      }
    }
    ol.append(li);
  }
  sec.append(ol, fonte(d));
  return sec;
}

const ACOES = {
  alterou: "alterou", acrescentou: "acrescentou", revogou: "revogou", renumerou: "renumerou",
  regulamentou: "regulamentou", ressalvou: "ressalvou", vetado: "teve veto em", revigorou: "revigorou",
  correlato: "trata de",
};

function itemAlteracao(a) {
  const li = el("li", {}, el("span", { class: "quando", texto: formatarData(a.data) }));
  li.append(a.id ? el("a", { href: urlLei(a.id), texto: a.nome }) : el("span", { class: "nome-norma", texto: a.nome }));
  const porAcao = new Map();
  for (const x of a.dispositivos) {
    if (!porAcao.has(x.acao)) porAcao.set(x.acao, []);
    porAcao.get(x.acao).push(x);
  }
  if (!porAcao.size) {
    li.append(el("span", { class: "resumo", texto: " " + a.tipo.toLowerCase() }));
  }
  for (const [acao, xs] of porAcao) {
    const arts = unicos(xs.map(x => x.art));
    const linha = el("div", { class: "resumo" }, (ACOES[acao] || acao) + " ");
    if (arts.length) linha.append(listaArtigos(arts, 6));
    else linha.append(xs.map(x => x.dispositivo).slice(0, 3).join("; "));
    li.append(linha);
  }
  return li;
}

function caixaAlteracoes(d) {
  const sec = caixa("sec-senado-alteracoes", "Alterações segundo o Senado",
    "Normas posteriores que mudaram esta, dispositivo por dispositivo, da mais recente à mais antiga.");
  const ol = el("ol", { class: "linha-tempo" });
  const todas = [...d.alteracoes].reverse();
  const LIMITE = 12;
  todas.slice(0, LIMITE).forEach(a => ol.append(itemAlteracao(a)));
  sec.append(ol);
  if (todas.length > LIMITE) {
    const mais = el("button", { class: "link-botao", type: "button", texto: `Mostrar mais ${numeroBR(todas.length - LIMITE)}` });
    mais.addEventListener("click", () => {
      todas.slice(LIMITE).forEach(a => ol.append(itemAlteracao(a)));
      mais.remove();
    });
    sec.append(el("p", { class: "mais-link" }, mais));
  }
  sec.append(fonte(d));
  return sec;
}

// ---------- início ----------

async function iniciar() {
  const texto = await textoPronto();
  // lei.js troca ?ref= por ?id= quando resolve a norma; nas páginas geradas
  // (lei/<id>.html, site/paginas.py) o id vem no <body data-lei>.
  const id = new URLSearchParams(location.search).get("id") || document.body.dataset.lei;
  if (!id) return;
  const d = await carregar(id);
  if (!d || (!d.alteracoes?.length && !d.controle?.length)) return;

  seloCabecalho(d);
  if (texto.childElementCount) marcarArtigos(d);

  const ancora = $("#sec-alteracoes") || $("#painel")?.lastElementChild;
  const novas = [];
  if (d.controle.length) novas.push(caixaSTF(d));
  if (d.alteracoes.length) novas.push(caixaAlteracoes(d));
  if (ancora) ancora.after(...novas); else $("#painel")?.append(...novas);

  // Se a página abriu com #sec-stf ou um artigo marcado, rola de novo agora que existe.
  if (location.hash === "#sec-stf") document.getElementById("sec-stf")?.scrollIntoView({ block: "start" });
}

iniciar().catch(err => console.warn("Dados do Senado indisponíveis:", err));
