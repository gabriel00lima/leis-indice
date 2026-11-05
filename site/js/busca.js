import {
  manifesto, listaShards, carregarTudo, usandoExemplo, urlLei, formatarData, normalizarTexto,
  destaques, numeroBR, APELIDOS,
} from "./dados.js";
import { buscarNoTexto } from "./busca-texto.js";

const $ = s => document.querySelector(s);
const form = $("#form"), q = $("#q"), tipoSel = $("#tipo"), sit = $("#sit"), ordem = $("#ordem");
const status = $("#status"), lista = $("#resultados"), mais = $("#mais");
const areaInicio = $("#area-inicio"), areaResultados = $("#area-resultados"), carregando = $("#carregando");

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

const ano = d => String(d || "").slice(0, 4);
const SIGLAS = {
  "Lei Ordinária": "Lei", "Decreto-Lei": "DL", "Lei Complementar": "LC",
  "Emenda Constitucional": "EC", "Constituição": "CF",
};

// ================= página inicial =================

function cartaoPrincipal(p) {
  const a = el("a", { class: "cartao-lei", href: urlLei(p.id) },
    el("span", { class: "etiqueta", texto: SIGLAS[p.tipo] ? `${p.tipo} · ${ano(p.data)}` : ano(p.data) }),
    el("h3", { texto: p.apelido }),
    el("p", { class: "cartao-titulo", texto: p.titulo }),
    el("p", { class: "cartao-desc", texto: p.descricao }),
    el("p", { class: "cartao-numeros" },
      el("span", {}, el("strong", { texto: numeroBR(p.citada_por) }), " citações"),
      el("span", {}, el("strong", { texto: numeroBR(p.alterada_por) }), " leis alteraram")));
  return a;
}

function itemRanking(e, i, max, rotulo) {
  const pct = Math.max(4, Math.round(100 * e.total / max));
  const nome = el("a", { href: urlLei(e.id), texto: APELIDOS[e.id] || e.titulo });
  return el("li", { class: e.revogada ? "revogada" : null },
    el("span", { class: "posicao", texto: String(i + 1) }),
    el("div", { class: "ranking-corpo" },
      el("span", { class: "ranking-nome" }, nome,
        ...(e.revogada ? [el("span", { class: "chip chip-revogada", texto: "Revogada" })] : [])),
      el("span", { class: "ranking-sub", texto: APELIDOS[e.id] ? e.titulo : (e.ementa || "") }),
      el("span", { class: "trilho" }, el("span", { class: "preenchido", style: `width:${pct}%` }))),
    el("span", { class: "ranking-valor", title: rotulo }, numeroBR(e.total)));
}

// "Ver todas": a grade começa recolhida (o CSS mostra as primeiras).
function montarVerTodas(total) {
  const grade = $("#lista-principais"), botao = $("#ver-principais");
  botao.hidden = total <= 6;
  botao.textContent = `Ver todas as ${total} leis principais`;
  botao.addEventListener("click", () => {
    const abrir = grade.classList.toggle("recolhida") === false;
    botao.setAttribute("aria-expanded", String(abrir));
    botao.textContent = abrir ? "Mostrar menos" : `Ver todas as ${total} leis principais`;
    if (!abrir) $("#principais").scrollIntoView({ block: "start" });
  });
}

// Abas "Mais citadas" / "Mais alteradas".
function montarAbas() {
  const abas = [...document.querySelectorAll('.abas [role="tab"]')];
  const escolher = aba => {
    for (const a of abas) {
      const sel = a === aba;
      a.setAttribute("aria-selected", String(sel));
      a.tabIndex = sel ? 0 : -1;
      $("#" + a.getAttribute("aria-controls")).hidden = !sel;
    }
    $("#desc-ranking").textContent = aba.dataset.desc;
  };
  abas.forEach((a, i) => {
    a.addEventListener("click", () => escolher(a));
    a.addEventListener("keydown", ev => {
      const passo = { ArrowRight: 1, ArrowLeft: -1 }[ev.key];
      if (!passo) return;
      const prox = abas[(i + passo + abas.length) % abas.length];
      escolher(prox); prox.focus();
    });
  });
}

async function montarInicio() {
  let d;
  try { d = await destaques(); } catch { d = null; }
  if (!d) {
    for (const s of ["#principais", "#rankings"]) $(s).hidden = true;
    return;
  }

  // Números do topo
  const stat = (k, v) => { const x = document.querySelector(`[data-stat="${k}"]`); if (x) x.textContent = v; };
  stat("total", numeroBR(d.total));
  stat("ligacoes", numeroBR(d.ligacoes));
  stat("atualizado", formatarData(String(d.gerado_em || "").slice(0, 10)));

  // Leis principais
  $("#lista-principais").replaceChildren(...d.principais.map(cartaoPrincipal));
  montarVerTodas(d.principais.length);

  // Rankings
  const maxC = d.mais_citadas[0]?.total || 1;
  $("#mais-citadas").replaceChildren(...d.mais_citadas.map((e, i) => itemRanking(e, i, maxC, "citações")));
  const maxA = d.mais_alteradas[0]?.total || 1;
  $("#mais-alteradas").replaceChildren(...d.mais_alteradas.map((e, i) => itemRanking(e, i, maxA, "leis que alteraram")));
  montarAbas();

  // Recentes
  $("#recentes").replaceChildren(...d.recentes.map(e =>
    el("li", {},
      el("span", { class: "data-recente", texto: formatarData(e.data) }),
      el("div", {},
        el("a", { href: urlLei(e.id), texto: e.titulo }),
        el("p", { texto: e.ementa || "" })))));
  const ultima = d.recentes[0]?.data;
  if (ultima) {
    $("#texto-recentes").replaceChildren("A mais nova é de ", el("strong", { texto: formatarData(ultima) }),
      ". O acervo de origem leva algumas semanas para incluir o que sai no Diário Oficial.");
  }

  // Rodapé
  const c = d.fonte?.commit;
  $("#rodape-indice").replaceChildren(
    `${numeroBR(d.total)} normas, gerado em ${formatarData(String(d.gerado_em).slice(0, 10))}`,
    ...(c ? [el("br"), "Commit do acervo: ", el("a", { href: `https://github.com/ctresb/leis/commit/${c}`, texto: c.slice(0, 7) })] : []));
}

function plural(t) {
  return { "Lei Ordinária": "Leis ordinárias", "Decreto-Lei": "Decretos-leis", "Lei Complementar": "Leis complementares",
    "Emenda Constitucional": "Emendas constitucionais", "Constituição": "Constituição" }[t] || t;
}

// ================= busca =================

const POR_PAGINA = 40;
let entradas = null;
let tipoCarregado = undefined;
let achados = [], mostrados = 0, termosAtuais = [];

function preparar(e) {
  if (e._busca) return e;
  const apelido = APELIDOS[e.id] || "";
  e._apelido = normalizarTexto(apelido);
  e._busca = normalizarTexto(`${apelido} ${e.titulo} ${e.tipo} ${e.ementa}`);
  e._numero = String(e.numero || "").replace(/\D/g, "");
  e._ano = ano(e.data);
  return e;
}

function pontuar(e, termos) {
  let p = 0;
  for (const t of termos) {
    const dig = t.replace(/\D/g, "");
    if (dig && dig === t.replace(/[.\-/]/g, "")) {
      if (e._numero === dig) p += 100;
      else if (dig.length === 4 && e._ano === dig) p += 20;
      else if (e._busca.includes(t)) p += 5;
      else return 0;
    } else if (e._busca.includes(t)) {
      p += e._apelido.includes(t) ? 60 : normalizarTexto(e.titulo).includes(t) ? 10 : 3;
    } else {
      return 0;
    }
  }
  if (APELIDOS[e.id]) p += 5;
  if (!e.revogada) p += 1;
  return p;
}

function termosDe(texto) {
  return normalizarTexto(texto)
    .replace(/\b(n[ºo°]|numero|de|da|do|das|dos|e|a|o)\b/g, " ")
    .split(/\s+/).filter(Boolean)
    .map(t => /^[\d.]+(\/\d{2,4})?$/.test(t) ? t.split("/")[0].replace(/\./g, "") : t);
}

// Destaca os termos buscados num texto (sem innerHTML).
function realcar(texto, termos) {
  const frag = document.createDocumentFragment();
  const palavras = termos.filter(t => t.length > 2 && !/^\d+$/.test(t));
  if (!palavras.length || !texto) { frag.append(texto || ""); return frag; }
  const norm = normalizarTexto(texto);
  const marcas = [];
  for (const t of palavras) {
    let i = norm.indexOf(t);
    while (i >= 0) { marcas.push([i, i + t.length]); i = norm.indexOf(t, i + t.length); }
  }
  marcas.sort((a, b) => a[0] - b[0]);
  let pos = 0;
  for (const [ini, fim] of marcas) {
    if (ini < pos) continue;
    frag.append(texto.slice(pos, ini), el("mark", { texto: texto.slice(ini, fim) }));
    pos = fim;
  }
  frag.append(texto.slice(pos));
  return frag;
}

async function garantirIndice() {
  const tipo = tipoSel.value || null;
  const shards = await listaShards();
  const alvo = shards.some(s => s.tipo) ? tipo : null;
  if (entradas && (tipoCarregado === null || tipoCarregado === alvo)) return;
  carregando.hidden = false;
  status.textContent = "Carregando o índice (só na primeira busca)…";
  try {
    entradas = (await carregarTudo((f, t) => {
      if (t > 1) status.textContent = `Carregando o índice… ${f} de ${t} partes`;
      carregando.firstElementChild.style.width = Math.round(100 * f / t) + "%";
    }, alvo)).map(preparar);
    tipoCarregado = alvo;
  } finally {
    carregando.hidden = true;
  }
}

async function buscar() {
  const texto = q.value.trim();
  const params = new URLSearchParams();
  if (texto) params.set("q", texto);
  for (const [k, e] of [["tipo", tipoSel], ["sit", sit], ["ordem", ordem]]) if (e.value) params.set(k, e.value);
  history.replaceState(null, "", params.toString() ? "?" + params : location.pathname);

  const filtrando = texto || tipoSel.value || sit.value;
  areaInicio.hidden = !!filtrando;
  areaResultados.hidden = !filtrando;
  document.body.classList.toggle("buscando", !!filtrando);
  if (!filtrando) return;

  $("#titulo-resultados").textContent = texto ? `Resultados para “${texto}”` : (tipoSel.value ? plural(tipoSel.value) : "Normas");
  buscarNoTexto(texto, lista, { ocultar: sit.value === "revogada" });
  try { await garantirIndice(); }
  catch (err) { status.textContent = "Não foi possível carregar o índice: " + err.message; return; }

  termosAtuais = termosDe(texto);
  achados = [];
  for (const e of entradas) {
    if (tipoSel.value && e.tipo !== tipoSel.value) continue;
    if (sit.value === "vigente" && e.revogada) continue;
    if (sit.value === "revogada" && !e.revogada) continue;
    const p = termosAtuais.length ? pontuar(e, termosAtuais) : 1;
    if (p) achados.push([p, e]);
  }
  const porData = (a, b) => String(b[1].data).localeCompare(String(a[1].data));
  if (ordem.value === "recentes") achados.sort(porData);
  else if (ordem.value === "antigas") achados.sort((a, b) => porData(b, a));
  else achados.sort((a, b) => b[0] - a[0] || porData(a, b));

  const n = achados.length;
  status.textContent = n
    ? `${numeroBR(n)} ${n === 1 ? "norma encontrada" : "normas encontradas"} em ${numeroBR(entradas.length)}`
    : "Nenhuma norma com isso no título ou na ementa. Tente o número sem pontos (ex.: 8078) ou outra palavra.";
  lista.replaceChildren();
  mostrados = 0;
  mostrarMais();
}

function mostrarMais() {
  const frag = document.createDocumentFragment();
  for (const [, e] of achados.slice(mostrados, mostrados + POR_PAGINA)) {
    const apelido = APELIDOS[e.id];
    const meta = el("div", { class: "resultado-meta" },
      el("span", { class: "chip", texto: e.tipo || "Norma" }),
      el("span", { texto: formatarData(e.data) }));
    if (e.revogada) meta.append(el("span", { class: "chip chip-revogada", texto: "Revogada" }));
    const titulo = el("a", { class: "resultado-titulo", href: urlLei(e.id) });
    titulo.append(realcar(apelido || e.titulo || e.id, termosAtuais));
    const li = el("li", { class: "resultado" + (e.revogada ? " revogada" : "") }, meta, titulo);
    if (apelido) li.append(el("p", { class: "resultado-sub", texto: e.titulo }));
    const em = el("p", { class: "resultado-ementa" });
    em.append(realcar(e.ementa || "", termosAtuais));
    li.append(em);
    frag.append(li);
  }
  mostrados += POR_PAGINA;
  lista.append(frag);
  mais.hidden = mostrados >= achados.length;
}

async function iniciar() {
  if (await usandoExemplo().catch(() => false)) $("#aviso-exemplo").hidden = false;
  const m = await manifesto().catch(() => null);
  let tipos = [];
  if (m?.shards) tipos = [...new Set(m.shards.map(s => s.tipo).filter(Boolean))];
  else if (m?.entradas) tipos = [...new Set(m.entradas.map(e => e.tipo).filter(Boolean))];
  for (const t of tipos.sort((a, b) => a.localeCompare(b, "pt-BR"))) tipoSel.add(new Option(t, t));

  const p = new URLSearchParams(location.search);
  q.value = p.get("q") || "";
  tipoSel.value = p.get("tipo") || "";
  sit.value = p.get("sit") || "";
  ordem.value = p.get("ordem") || "";
  montarInicio();
  buscar();
}

let espera;
q.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscar, 300); });
for (const e of [tipoSel, sit, ordem]) e.addEventListener("change", buscar);
form.addEventListener("submit", ev => { ev.preventDefault(); buscar(); areaResultados.scrollIntoView({ behavior: "smooth" }); });
mais.addEventListener("click", mostrarMais);
iniciar();
