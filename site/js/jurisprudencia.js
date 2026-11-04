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

function itemDecisao(d) {
  const nome = d.u ? el("a", { href: d.u, rel: "noopener", target: "_blank", texto: d.p, title: "Abrir o processo no site do STJ" })
    : el("strong", { texto: d.p });
  const meta = [d.o, d.r ? "Rel. Min. " + d.r : null, d.j ? dataBR(d.j) : null].filter(Boolean).join(" · ");
  return el("li", {},
    el("div", { class: "juris-proc" }, nome, d.t ? el("span", { class: "juris-tema", texto: d.t }) : null),
    meta ? el("div", { class: "juris-meta", texto: meta }) : null,
    d.e ? el("p", { class: "juris-ementa", texto: d.e }) : null);
}

function listaDecisoes(ids, decisoes, total) {
  const itens = (ids || []).map(i => decisoes?.[i]).filter(Boolean);
  const caixa = el("div", { class: "juris-bloco" });
  if (!itens.length) { caixa.append(el("p", { class: "vazio", texto: "Não foi possível carregar as decisões." })); return caixa; }
  const ul = el("ul", { class: "juris-lista" });
  itens.slice(0, VISIVEIS).forEach(d => ul.append(itemDecisao(d)));
  if (itens.length > VISIVEIS) {
    const li = el("li", { class: "juris-mais" }, el("button", { type: "button", class: "link-botao", texto: `Mostrar mais ${itens.length - VISIVEIS}` }));
    li.firstChild.addEventListener("click", () => li.replaceWith(...itens.slice(VISIVEIS).map(itemDecisao)));
    ul.append(li);
  }
  caixa.append(ul);
  if (total > itens.length) {
    caixa.append(el("p", { class: "dica", texto: `As ${numeroBR(itens.length)} mais recentes de ${plural(total, "acórdão", "acórdãos")}.` }));
  }
  return caixa;
}

// Selo "⚖ N" no fim do caput de cada artigo citado; abre a lista logo abaixo do caput.
function marcarArtigos(texto, resumo, slug) {
  for (const [art, n] of Object.entries(resumo.artigos || {})) {
    const p = document.getElementById(art);
    if (!p || !p.classList.contains("artigo") || p.querySelector(".juris-selo")) continue;
    const botao = el("button", {
      type: "button", class: "juris-selo", "aria-expanded": "false",
      title: `${plural(n, "acórdão do STJ cita", "acórdãos do STJ citam")} este artigo`,
    }, el("span", { class: "juris-icone", "aria-hidden": "true", texto: "⚖" }), plural(n, "decisão", "decisões"));
    let painel = null;
    botao.addEventListener("click", async () => {
      const abrir = botao.getAttribute("aria-expanded") !== "true";
      botao.setAttribute("aria-expanded", String(abrir));
      if (abrir && !painel) {
        painel = el("div", { class: "juris-artigo", role: "region", "aria-label": "Jurisprudência do " + rotuloArt(art) },
          el("div", { class: "juris-cab" },
            el("strong", { texto: "STJ sobre o " + rotuloArt(art).replace(/^Art/, "art") }),
            el("span", { texto: plural(n, "acórdão", "acórdãos") })),
          el("p", { class: "vazio", texto: "Carregando…" }));
        p.after(painel);
        const b = await bloco(slug, String(Math.floor(numArt(art) / (resumo.bloco || 100))));
        painel.lastChild.replaceWith(listaDecisoes(b?.artigos?.[art], b?.decisoes, n));
      }
      if (painel) painel.hidden = !abrir;
    });
    p.append(" ", botao);
  }
}

function caixaPainel(resumo, datajud, slug, info) {
  const caixa = el("section", { class: "caixa juris-caixa", id: "sec-jurisprudencia" }, el("h2", { texto: "Jurisprudência" }));

  if (resumo && resumo.total) {
    const artigos = Object.entries(resumo.artigos || {}).sort((a, b) => b[1] - a[1]);
    caixa.append(el("dl", { class: "juris-numeros" },
      el("div", {}, el("dd", { texto: numeroBR(resumo.total) }), el("dt", { texto: "acórdãos do STJ citam esta norma" })),
      el("div", {}, el("dd", { texto: numeroBR(artigos.length) }), el("dt", { texto: "artigos citados" }))));
    if (artigos.length) {
      caixa.append(el("p", { class: "dica", texto: "Mais citados. O selo ⚖ ao lado de cada artigo abre as decisões." }));
      const ol = el("ol", { class: "juris-top" });
      const maior = artigos[0][1];
      for (const [art, n] of artigos.slice(0, 8)) {
        const barra = el("span", { class: "juris-barra", "aria-hidden": "true" });
        barra.style.setProperty("--p", Math.max(4, Math.round(n / maior * 100)) + "%");
        ol.append(el("li", {}, el("a", { href: "#" + art, texto: rotuloArt(art) }), barra, el("span", { class: "contagem", texto: numeroBR(n) })));
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
      caixa.append(el("p", { class: "dica", texto: `Acórdãos julgados de ${dataBR(resumo.periodo[0])} a ${dataBR(resumo.periodo[1])}, segundo as referências legislativas que o próprio STJ registra em cada um.` }));
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
  // Com ?ref=, o lei.js troca a URL por ?id= depois de resolver.
  const id = new URLSearchParams(location.search).get("id");
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
