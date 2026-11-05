// Jurisprudência por artigo na página da lei: acórdãos do STJ que citam cada artigo
// e números do DataJud (CNJ). Lê data/jurisprudencia/, gerado pela Action "Jurisprudência"
// (formato em integracoes/jurisprudencia/README.md).
//
// Módulo independente de lei.js: espera o texto ser montado (parágrafos .artigo com id "art-N")
// e só então acrescenta os selos nos artigos e a caixa no painel lateral.

const BASES = ["data/jurisprudencia/", "../data/jurisprudencia/"];
const VISIVEIS = 3; // decisões abertas por artigo; o resto fica atrás de "mostrar mais"

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos.filter(f => f != null && f !== ""));
  return e;
}

const numeroBR = n => Number(n || 0).toLocaleString("pt-BR");
const dataBR = d => /^\d{4}-\d{2}-\d{2}/.test(d || "") ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : (d || "");
const numArt = a => Number((/^art-(\d+)/.exec(a) || [])[1] || 0);
function rotuloArt(a) {
  const m = /^art-(\d+)(?:-([a-z]))?$/.exec(a);
  if (!m) return a;
  const n = Number(m[1]);
  return "Art. " + (n >= 1000 ? n.toLocaleString("pt-BR") : n) + (n < 10 ? "º" : "") + (m[2] ? "-" + m[2].toUpperCase() : "");
}
const plural = (n, um, varios) => numeroBR(n) + " " + (n === 1 ? um : varios);

let base = null;
async function json(arquivo) {
  for (const b of base ? [base] : BASES) {
    try {
      const r = await fetch(b + arquivo);
      if (!r.ok) continue;
      const d = await r.json();
      base = b;
      return d;
    } catch { /* tenta a próxima base */ }
  }
  return null;
}

const blocos = new Map();
function bloco(slug, nome) {
  const k = slug + "/" + nome;
  if (!blocos.has(k)) blocos.set(k, json(`stj/${slug}/${nome}.json`));
  return blocos.get(k);
}

// Espera o lei.js terminar de montar o texto (ou desistir).
function esperarTexto() {
  const texto = document.getElementById("texto");
  const pronto = () => texto.querySelector(".artigo") || document.getElementById("carregando-texto")?.hidden;
  return new Promise(resolve => {
    if (pronto()) return resolve(texto);
    const obs = new MutationObserver(() => {
      if (pronto()) { obs.disconnect(); setTimeout(() => resolve(texto), 60); }
    });
    obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
    setTimeout(() => { obs.disconnect(); resolve(texto); }, 30000);
  });
}

// Item de artigo: formato novo { i, d: ["§ 3º, V"], w: "ementa"|"lista", x: trecho, h: [ini, fim], ig }
// ou só o id (dados antigos).
const item = v => typeof v === "string" ? { i: v } : (v || {});

const COMO = {
  ementa: ["juris-como forte", "Discute o artigo", "A ementa trata deste artigo (trecho abaixo)."],
  lista: ["juris-como", "Dispositivo relevante", "O artigo está na lista de dispositivos relevantes da ementa."],
  "": ["juris-como fraco", "Citado de passagem", "O STJ registrou o artigo nas referências legislativas, mas a ementa não fala dele."],
};

function trechoMarcado(x, h) {
  const p = el("blockquote", { class: "juris-trecho" });
  if (Array.isArray(h) && h[1] > h[0]) {
    p.append(x.slice(0, h[0]), el("mark", { texto: x.slice(h[0], h[1]) }), x.slice(h[1]));
  } else p.append(x);
  return p;
}

function itemDecisao(d, it = {}, comMarcas = false) {
  const nome = d.u ? el("a", { href: d.u, rel: "noopener", target: "_blank", texto: d.p, title: "Abrir o processo no site do STJ" })
    : el("strong", { texto: d.p });
  const meta = [d.o, d.r ? "Rel. Min. " + d.r : null, d.j ? dataBR(d.j) : null].filter(Boolean).join(" · ");
  const como = comMarcas ? COMO[it.w || ""] : null;
  return el("li", {},
    el("div", { class: "juris-proc" }, nome,
      d.t ? el("span", { class: "juris-tema", texto: d.t }) : null,
      como ? el("span", { class: como[0], title: como[2], texto: como[1] }) : null),
    meta ? el("div", { class: "juris-meta", texto: meta }) : null,
    it.d?.length ? el("div", { class: "juris-disp" }, "Cita: ", el("strong", { texto: it.d.join("; ") })) : null,
    it.x ? trechoMarcado(it.x, it.h) : null,
    d.e ? el("p", { class: it.x ? "juris-ementa juris-indexacao" : "juris-ementa", texto: d.e }) : null,
    d.s ? el("p", { class: "juris-tese" }, el("strong", { texto: "Tese: " }), d.s) : null,
    it.ig ? el("p", { class: "juris-iguais", texto: `+ ${plural(it.ig, "acórdão", "acórdãos")} com a mesma ementa ou do mesmo tema` }) : null);
}

function listaDecisoes(lista, decisoes, total, comMarcas = false) {
  const itens = (lista || []).map(item).filter(it => decisoes?.[it.i]);
  const caixa = el("div", { class: "juris-bloco" });
  if (!itens.length) { caixa.append(el("p", { class: "vazio", texto: "Nenhuma decisão para mostrar." })); return caixa; }
  const ul = el("ul", { class: "juris-lista" });
  const li = it => itemDecisao(decisoes[it.i], it, comMarcas);
  itens.slice(0, VISIVEIS).forEach(it => ul.append(li(it)));
  if (itens.length > VISIVEIS) {
    const mais = el("li", { class: "juris-mais" }, el("button", { type: "button", class: "link-botao", texto: `Mostrar mais ${itens.length - VISIVEIS}` }));
    mais.firstChild.addEventListener("click", () => mais.replaceWith(...itens.slice(VISIVEIS).map(li)));
    ul.append(mais);
  }
  caixa.append(ul);
  if (total > itens.length) {
    caixa.append(el("p", { class: "dica", texto: comMarcas
      ? `As ${numeroBR(itens.length)} mais relevantes de ${plural(total, "acórdão", "acórdãos")}: primeiro as que discutem o artigo na ementa, os repetitivos e as decisões focadas nele.`
      : `As ${numeroBR(itens.length)} mais recentes de ${plural(total, "acórdão", "acórdãos")}.` }));
  }
  return caixa;
}

// Filtro por parágrafo/inciso: botões com a contagem de cada dispositivo citado.
function filtroDispositivos(disp, total, aoEscolher) {
  const nav = el("div", { class: "juris-filtro", role: "group", "aria-label": "Filtrar por parágrafo ou inciso" });
  const botoes = [];
  const add = (rotulo, n, valor) => {
    const b = el("button", { type: "button", "aria-pressed": valor == null ? "true" : "false" }, rotulo, el("span", { texto: numeroBR(n) }));
    b.addEventListener("click", () => {
      botoes.forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      aoEscolher(valor);
    });
    botoes.push(b);
    nav.append(b);
  };
  add("Artigo inteiro", total, null);
  for (const [rot, n] of Object.entries(disp)) add(rot, n, rot);
  return nav;
}

// Selo "⚖ N" no fim do caput de cada artigo citado; abre a lista logo abaixo do caput.
function marcarArtigos(texto, resumo, slug) {
  const novo = (resumo.v || 1) >= 2;
  for (const [art, n] of Object.entries(resumo.artigos || {})) {
    const p = document.getElementById(art);
    if (!p || !p.classList.contains("artigo") || p.querySelector(".juris-selo")) continue;
    const discutem = resumo.na_ementa?.[art] || 0;
    const botao = el("button", {
      type: "button", class: "juris-selo" + (novo && !discutem ? " fraco" : ""), "aria-expanded": "false",
      title: novo
        ? `${plural(n, "acórdão do STJ cita", "acórdãos do STJ citam")} este artigo; ${discutem ? plural(discutem, "discute", "discutem") + " o artigo na ementa" : "nenhum discute o artigo na ementa"}`
        : `${plural(n, "acórdão do STJ cita", "acórdãos do STJ citam")} este artigo`,
    }, el("span", { class: "juris-icone", "aria-hidden": "true", texto: "⚖" }), plural(n, "decisão", "decisões"));
    let painel = null;
    botao.addEventListener("click", async () => {
      const abrir = botao.getAttribute("aria-expanded") !== "true";
      botao.setAttribute("aria-expanded", String(abrir));
      if (abrir && !painel) {
        const resumoNum = novo
          ? `${plural(n, "acórdão", "acórdãos")} · ${discutem ? plural(discutem, "discute", "discutem") + " na ementa" : "nenhum discute na ementa"}`
          : plural(n, "acórdão", "acórdãos");
        painel = el("div", { class: "juris-artigo", role: "region", "aria-label": "Jurisprudência do " + rotuloArt(art) },
          el("div", { class: "juris-cab" },
            el("strong", { texto: "STJ sobre o " + rotuloArt(art).replace(/^Art/, "art") }),
            el("span", { texto: resumoNum })),
          el("p", { class: "vazio", texto: "Carregando…" }));
        p.after(painel);
        const b = await bloco(slug, String(Math.floor(numArt(art) / (resumo.bloco || 100))));
        const todos = (b?.artigos?.[art] || []).map(item);
        let lista = listaDecisoes(todos, b?.decisoes, n, novo);
        const disp = resumo.dispositivos?.[art];
        const carregando = painel.lastChild;
        if (disp && Object.keys(disp).length) {
          const filtro = filtroDispositivos(disp, n, rot => {
            const escolhidos = rot ? todos.filter(it => it.d?.includes(rot)) : todos;
            const nova = listaDecisoes(escolhidos, b?.decisoes, rot ? disp[rot] : n, novo);
            lista.replaceWith(nova);
            lista = nova;
          });
          carregando.replaceWith(filtro, lista);
        } else carregando.replaceWith(lista);
      }
      if (painel) painel.hidden = !abrir;
    });
    p.append(" ", botao);
  }
}

function caixaPainel(resumo, datajud, slug, info) {
  const caixa = el("section", { class: "caixa juris-caixa", id: "sec-jurisprudencia" }, el("h2", { texto: "Jurisprudência" }));

  if (resumo && resumo.total) {
    const novo = (resumo.v || 1) >= 2;
    // Com os dados novos, o ranking é por quantos acórdãos DISCUTEM o artigo na ementa, não só citam.
    const peso = novo ? resumo.na_ementa || {} : resumo.artigos || {};
    const todos = Object.entries(resumo.artigos || {});
    const comPeso = novo ? todos.filter(([a]) => peso[a]) : todos;
    const artigos = (comPeso.length ? comPeso : todos).sort((a, b) => (peso[b[0]] || 0) - (peso[a[0]] || 0) || b[1] - a[1]);
    caixa.append(el("dl", { class: "juris-numeros" },
      el("div", {}, el("dd", { texto: numeroBR(resumo.total) }), el("dt", { texto: "acórdãos do STJ citam esta norma" })),
      el("div", {}, el("dd", { texto: numeroBR(todos.length) }), el("dt", { texto: "artigos citados" }))));
    if (artigos.length) {
      caixa.append(el("p", { class: "dica", texto: novo
        ? "Mais discutidos: acórdãos cuja ementa trata do artigo. O selo ⚖ ao lado de cada artigo abre as decisões."
        : "Mais citados. O selo ⚖ ao lado de cada artigo abre as decisões." }));
      const ol = el("ol", { class: "juris-top" });
      const valor = ([art, n]) => novo ? peso[art] || 0 : n;
      const maior = Math.max(1, valor(artigos[0]));
      for (const par of artigos.slice(0, 8)) {
        const [art, n] = par;
        const barra = el("span", { class: "juris-barra", "aria-hidden": "true" });
        barra.style.setProperty("--p", Math.max(4, Math.round(valor(par) / maior * 100)) + "%");
        ol.append(el("li", {}, el("a", { href: "#" + art, texto: rotuloArt(art) }), barra,
          el("span", { class: "contagem", texto: numeroBR(valor(par)), title: novo ? `${numeroBR(peso[art] || 0)} discutem na ementa, de ${numeroBR(n)} que citam` : null })));
      }
      caixa.append(ol);
    }
    if (resumo.sem_artigo) {
      const det = el("details", { class: "rel" },
        el("summary", {}, el("span", { texto: "Citam a norma sem indicar artigo" }), el("span", { class: "contagem", texto: numeroBR(resumo.sem_artigo) })));
      det.addEventListener("toggle", async () => {
        if (!det.open || det.dataset.carregado) return;
        det.dataset.carregado = "1";
        const b = await bloco(slug, "sem");
        det.append(listaDecisoes(b?.artigos?.["sem-artigo"], b?.decisoes, resumo.sem_artigo));
      }, { once: false });
      caixa.append(det);
    }
    if (resumo.periodo) {
      caixa.append(el("p", { class: "dica", texto: `Acórdãos julgados de ${dataBR(resumo.periodo[0])} a ${dataBR(resumo.periodo[1])}, segundo as referências legislativas que o próprio STJ registra em cada um${novo ? "; a ementa de cada acórdão diz se ele discute o artigo ou só o cita de passagem" : ""}.` }));
    }
  }

  if (datajud?.tribunais?.length) {
    const t = datajud.tribunais[0];
    const bloco = el("div", { class: "juris-datajud" },
      el("h3", { texto: `Processos no ${t.sigla} (DataJud/CNJ)` }),
      el("p", { class: "juris-grande" }, el("strong", { texto: numeroBR(t.total) }),
        ` processos em ${plural(datajud.assuntos.length, "assunto ligado", "assuntos ligados")} a esta norma`));
    const ul = el("ul", { class: "juris-assuntos" });
    for (const a of datajud.assuntos.slice(0, 8)) {
      ul.append(el("li", {}, el("span", { texto: a.nome }), el("span", { class: "contagem", texto: numeroBR(a.total) })));
    }
    bloco.append(ul, el("p", { class: "dica", texto: "O DataJud só traz metadados (classe, assunto, andamento), não o texto das decisões. Os assuntos são da Tabela Processual Unificada do CNJ e foram escolhidos à mão; um processo pode ter mais de um." }));
    caixa.append(bloco);
  }

  caixa.append(el("p", { class: "mais-link" },
    el("a", { href: "https://dadosabertos.web.stj.jus.br/", rel: "noopener", texto: "Dados abertos do STJ" }),
    datajud ? " · " : "",
    datajud ? el("a", { href: "https://datajud-wiki.cnj.jus.br/", rel: "noopener", texto: "DataJud" }) : "",
    info?.gerado_em ? ` · atualizado em ${dataBR(info.gerado_em)}` : ""));

  const antes = document.getElementById("sec-alteracoes");
  if (antes) antes.before(caixa); else document.getElementById("painel")?.append(caixa);
}

async function iniciar() {
  const indice = await json("indice.json");
  if (!indice?.leis) return; // sem dados publicados: a página fica como está
  const texto = await esperarTexto();
  // Com ?ref=, o lei.js troca a URL por ?id= depois de resolver; em lei/<id>.html o id vem de <body data-lei>.
  const id = new URLSearchParams(location.search).get("id") || document.body.dataset.lei;
  const lei = id && indice.leis[id];
  if (!lei) return;
  const [resumo, datajud] = await Promise.all([
    lei.stj ? json(lei.stj) : null,
    lei.datajud ? json(lei.datajud) : null,
  ]);
  if (!resumo?.total && !datajud) return;
  if (resumo?.total) marcarArtigos(texto, resumo, lei.slug);
  caixaPainel(resumo, datajud, lei.slug, indice);
  // Link direto para um artigo (#art-5) continua no lugar depois de inserir os selos.
  if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ block: "start" });
}

iniciar().catch(err => console.warn("jurisprudência:", err));
