import {
  listaExplicadas, explicadaPorSlug, carregarExplicada, renderizar, textoRevisao, AVISO, el, cartaoExplicada,
} from "./explicadas.js";
import { urlLei } from "./dados.js";

const $ = s => document.querySelector(s);
const params = new URLSearchParams(location.search);

function mostrarAviso(extra) {
  $("#aviso").replaceChildren(el("strong", { texto: "Importante: " }), AVISO + (extra ? " " + extra : ""));
}

async function mostrarLista() {
  const lista = await listaExplicadas();
  const grade = $("#lista");
  grade.replaceChildren(...lista.map(cartaoExplicada));
  grade.hidden = false;
  $("#estado").hidden = lista.length > 0;
  $("#estado").textContent = "Nenhum resumo publicado ainda.";
  mostrarAviso();
}

function slugSecao(t) {
  return "s-" + t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

async function mostrarExplicada(slug) {
  const e = await explicadaPorSlug(slug);
  if (!e) {
    $("#titulo").textContent = "Resumo não encontrado";
    $("#resumo").textContent = "Não existe uma explicação com esse nome. Veja a lista completa.";
    $("#acoes").replaceChildren(el("a", { class: "botao", href: "explicada.html", texto: "Todas as explicações" }));
    $("#estado").hidden = true;
    return;
  }
  const { corpo } = await carregarExplicada(slug);
  document.title = `${e.nome} explicada · Leis do Brasil`;
  document.querySelector('meta[name="description"]')?.setAttribute("content", e.resumo);

  $("#trilha").append(el("a", { href: "explicada.html", texto: "Lei explicada" }), el("span", { texto: e.nome }));
  $("#titulo").textContent = e.nome;
  if (e.sigla && e.sigla !== e.nome) { $("#subtitulo").textContent = e.sigla; $("#subtitulo").hidden = false; }
  $("#resumo").textContent = e.resumo;
  if (e.para_quem) {
    $("#publico").replaceChildren(el("strong", { texto: "Para quem é: " }), e.para_quem);
    $("#publico").hidden = false;
  }
  $("#acoes").replaceChildren(
    el("a", { class: "botao botao-cheio", href: urlLei(e.lei), texto: "Ler o texto completo da lei" }),
    el("a", { class: "botao", href: "explicada.html", texto: "Outras leis explicadas" }));

  const texto = $("#texto-explicada");
  texto.replaceChildren(...renderizar(corpo, e.lei).childNodes);
  const indice = $("#indice-secoes");
  for (const h of texto.querySelectorAll("h2")) {
    h.id = slugSecao(h.textContent);
    indice.append(el("li", {}, el("a", { href: "#" + h.id, texto: h.textContent })));
  }
  $("#leitura").hidden = false;
  $("#estado").hidden = true;
  mostrarAviso(textoRevisao(e) ? textoRevisao(e) + "." : "");
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

const slug = params.get("lei");
(slug ? mostrarExplicada(slug) : mostrarLista()).catch(err => {
  $("#estado").hidden = false;
  $("#estado").textContent = "Não foi possível carregar: " + err.message;
});
