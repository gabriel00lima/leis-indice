// Feed "Publicado no Diário Oficial".
import { manifestoDou, arquivoDou, urlLeiDou, tituloAto } from "./comum.js";
import { rotuloDoId, APELIDOS, formatarData, numeroBR } from "../js/dados.js";

const $ = s => document.querySelector(s);
const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];
const POR_PAGINA = 40;
const params = new URLSearchParams(location.search);

const estado = { atos: [], tipo: params.get("tipo") || "", mes: params.get("mes") || "",
  q: params.get("q") || "", soAltera: params.get("altera") === "1", limite: POR_PAGINA };

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "texto") e.textContent = v; else if (k === "classe") e.className = v; else e.setAttribute(k, v);
  }
  for (const f of filhos.flat()) if (f != null) e.append(f);
  return e;
}

const nomeNorma = id => APELIDOS[id] || rotuloDoId(id);
const nomeMes = m => { const [a, n] = m.split("-"); return `${MESES_LONGOS[+n - 1]} de ${a}`; };
const semAcento = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function relacoes(rotulo, classe, ids) {
  if (!ids || !ids.length) return null;
  const mostrar = ids.slice(0, 8);
  return el("div", { classe: "ato-rel " + classe }, el("b", { texto: rotulo }),
    mostrar.map(id => el("a", { href: urlLeiDou(id), texto: nomeNorma(id), title: rotuloDoId(id) })),
    ids.length > mostrar.length ? el("span", { classe: "dica", texto: `+${ids.length - mostrar.length}` }) : null);
}

function cartao(a) {
  const [, m, d] = (a.data || "").split("-");
  const titulo = tituloAto(a.identifica);
  const classeTipo = { lei: "tipo-lei", lcp: "tipo-lei", mpv: "tipo-mpv", emc: "tipo-emc" }[a.prefixo] || "chip-neutro";
  return el("li", { classe: "ato" },
    el("div", { classe: "ato-dia", title: "Publicado no DOU em " + formatarData(a.data) },
      el("strong", { texto: d ? String(+d) : "?" }), el("span", { texto: m ? MESES_CURTOS[+m - 1] : "" })),
    el("div", {},
      el("div", { classe: "ato-topo" },
        el("span", { classe: "chip " + classeTipo, texto: a.tipo }),
        a.secao && a.secao !== "DO1" ? el("span", { classe: "chip chip-neutro", texto: "Edição extra" }) : null),
      el("h3", {}, a.norma ? el("a", { href: urlLeiDou(a.norma), texto: titulo }) : titulo),
      a.ementa ? el("p", { classe: "ato-ementa", texto: a.ementa }) : null,
      relacoes("Revoga", "rel-revoga", a.revoga),
      relacoes("Altera", "rel-altera", a.altera),
      relacoes("Cita", "rel-cita", a.cita),
      el("div", { classe: "ato-links" },
        a.norma ? el("a", { href: urlLeiDou(a.norma), texto: "Ler o texto no acervo" })
          : el("span", { classe: "fora", texto: "Ainda não está no acervo" }),
        a.url ? el("a", { href: a.url, rel: "noopener", target: "_blank",
          texto: "Ver no DOU" + (a.pagina ? ` (edição ${a.edicao}, pág. ${a.pagina})` : "") }) : null)));
}

function filtrados() {
  const q = semAcento(estado.q).trim();
  const qNum = q.replace(/[.\s]/g, "");
  return estado.atos.filter(a =>
    (!estado.tipo || a.tipo === estado.tipo) &&
    (!estado.soAltera || a.altera.length || a.revoga.length) &&
    (!q || semAcento(a.identifica + " " + a.ementa).includes(q) || (qNum && a.numero === qNum)));
}

function desenhar() {
  const lista = filtrados();
  const feed = $("#feed");
  feed.replaceChildren(...lista.slice(0, estado.limite).map(cartao));
  const onde = estado.mes ? `em ${nomeMes(estado.mes)}` : "nos meses mais recentes";
  $("#status").textContent = lista.length
    ? `${numeroBR(lista.length)} ${lista.length === 1 ? "ato" : "atos"} ${onde}.`
    : `Nenhum ato ${onde} com esses filtros.`;
  $("#mais").hidden = lista.length <= estado.limite;
  for (const b of $("#tipos").children) b.setAttribute("aria-pressed", String(b.dataset.tipo === estado.tipo));
  const u = new URLSearchParams();
  if (estado.tipo) u.set("tipo", estado.tipo);
  if (estado.mes) u.set("mes", estado.mes);
  if (estado.q) u.set("q", estado.q);
  if (estado.soAltera) u.set("altera", "1");
  history.replaceState(null, "", location.pathname + (u.size ? "?" + u : ""));
}

function botoesTipo(contagem) {
  const tipos = [["", "Todos", estado.atos.length], ...Object.entries(contagem).sort((x, y) => y[1] - x[1]).map(([t, n]) => [t, t, n])];
  $("#tipos").replaceChildren(...tipos.map(([t, rotulo, n]) => {
    const b = el("button", { type: "button", "data-tipo": t, "aria-pressed": "false" }, rotulo, el("span", { texto: numeroBR(n) }));
    b.addEventListener("click", () => { estado.tipo = t; estado.limite = POR_PAGINA; desenhar(); });
    return b;
  }));
}

async function carregarAtos(m) {
  if (estado.mes) {
    const mes = m.meses.find(x => x.mes === estado.mes);
    estado.atos = mes ? await arquivoDou(mes.arquivo) : [];
  } else {
    estado.atos = await arquivoDou(m.arquivos.recentes);
  }
  const contagem = {};
  for (const a of estado.atos) contagem[a.tipo] = (contagem[a.tipo] || 0) + 1;
  if (estado.tipo && !contagem[estado.tipo]) estado.tipo = "";
  botoesTipo(contagem);
  desenhar();
}

function monitor(c) {
  const lista = $("#monitor");
  const leis = (c.monitor || []).filter(l => l.atos.length);
  const rotulos = { em_dia: "em dia", acervo_atrasado: "acervo atrasado", monitor_pendente: "monitor pendente",
    nao_verificado: "não verificado" };
  if (!leis.length) {
    lista.replaceChildren(el("li", { classe: "vazio", texto: "Nenhuma lei acompanhada foi alterada no período coletado." }));
  } else {
    lista.replaceChildren(...leis.map(l => {
      const ultimo = l.atos[0];
      return el("li", {},
        el("div", { classe: "linha" }, el("a", { href: urlLeiDou(l.id), texto: l.apelido || nomeNorma(l.id) }),
          el("span", { classe: "sit sit-" + l.situacao, texto: rotulos[l.situacao] || l.situacao })),
        el("small", { texto: `${ultimo.rel === "revoga" ? "Revogada em parte" : "Alterada"} por ${tituloAto(ultimo.identifica)} (DOU de ${formatarData(ultimo.data)})`
          + (l.acervo ? ` · acervo mudou em ${formatarData(l.acervo.data)}` : "") }));
    }));
  }
  const quietas = (c.monitor || []).length - leis.length;
  $("#conferido").textContent = `Conferido em ${formatarData(c.conferido_em)}.` +
    (quietas > 0 ? ` ${quietas} ${quietas === 1 ? "lei acompanhada não teve" : "leis acompanhadas não tiveram"} alteração no período.` : "");

  const fora = c.fora_do_acervo || [];
  $("#fora").replaceChildren(...(fora.length ? fora.slice(0, 12).map(a =>
    el("li", {}, el("a", { href: a.url, target: "_blank", rel: "noopener", texto: tituloAto(a.identifica) }),
      el("small", { texto: `DOU de ${formatarData(a.data)} · há ${a.dias} dias` })))
    : [el("li", { classe: "vazio", texto: "Tudo o que saiu no DOU já está no acervo." })]));
  if (fora.length > 12) $("#fora").append(el("li", { classe: "dica", texto: `e mais ${fora.length - 12}.` }));
}

async function iniciar() {
  let m;
  try { m = await manifestoDou(); } catch (e) {
    $("#status").textContent = "Os dados do Diário Oficial ainda não foram coletados. A primeira coleta roda pela Action do DOU.";
    for (const s of ["#monitor", "#fora"]) $(s).replaceChildren(el("li", { classe: "vazio", texto: "Sem dados ainda." }));
    return;
  }
  const meses = m.meses || [];
  const n = $("#numeros");
  n.querySelector('[data-n="total"]').textContent = numeroBR(m.total);
  if (meses.length) {
    const [ini, fim] = [meses[meses.length - 1].mes, meses[0].mes];
    const curto = x => { const [a, k] = x.split("-"); return `${MESES_CURTOS[+k - 1]}/${a.slice(2)}`; };
    n.querySelector('[data-n="periodo"]').textContent = ini === fim ? curto(ini) : `${curto(ini)} – ${curto(fim)}`;
  }
  $("#mes").append(...meses.map(x => el("option", { value: x.mes, texto: `${nomeMes(x.mes)} (${numeroBR(x.total)})` })));
  $("#mes").value = estado.mes;
  $("#q").value = estado.q;
  $("#so-altera").checked = estado.soAltera;

  $("#mes").addEventListener("change", async e => {
    estado.mes = e.target.value; estado.limite = POR_PAGINA;
    $("#status").textContent = "Carregando…";
    await carregarAtos(m).catch(err => { $("#status").textContent = err.message; });
  });
  $("#q").addEventListener("input", e => { estado.q = e.target.value; estado.limite = POR_PAGINA; desenhar(); });
  $("#so-altera").addEventListener("change", e => { estado.soAltera = e.target.checked; estado.limite = POR_PAGINA; desenhar(); });
  $("#mais").addEventListener("click", () => { estado.limite += POR_PAGINA; desenhar(); });

  await carregarAtos(m).catch(err => { $("#status").textContent = err.message; });

  arquivoDou(m.arquivos.por_norma).then(pn => {
    const alteradas = Object.values(pn).filter(l => l.some(x => x.rel !== "publicacao")).length;
    n.querySelector('[data-n="alteram"]').textContent = numeroBR(alteradas);
    n.querySelector('[data-n="alteram"]').previousElementSibling.textContent = "leis do acervo alteradas";
  }).catch(() => {});
  arquivoDou(m.arquivos.conferencia).then(c => {
    n.querySelector('[data-n="fora"]').textContent = numeroBR((c.fora_do_acervo || []).length);
    monitor(c);
  }).catch(() => {
    for (const s of ["#monitor", "#fora"]) $(s).replaceChildren(el("li", { classe: "vazio", texto: "Conferência ainda não feita." }));
  });
}

iniciar();
