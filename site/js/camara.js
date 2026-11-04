// Projetos de lei da Câmara ligados à norma aberta em lei.html:
// o projeto que deu origem a ela e os projetos em tramitação que a alteram.
// Dados gerados por integracoes/camara/coletar.py em data/camara/.

import { resolverChave, formatarData } from "./dados.js";

const BASES = ["data/", "../data/"];
const MOSTRAR = 8;

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

async function baixar(caminho) {
  for (const b of BASES) {
    try {
      const r = await fetch(b + caminho);
      if (r.ok) return { base: b, dados: await r.json() };
      if (r.status === 404 && b === BASES[0]) {
        // data/ existe mas o arquivo não: confirma pelo manifesto antes de tentar outra base.
        const m = await fetch(b + "camara/index.json");
        if (m.ok) return { base: b, dados: null };
      }
    } catch { /* próxima base */ }
  }
  return null;
}

function itemProjeto(p, comRelacao) {
  const li = el("li", { class: "projeto" });
  li.append(el("a", { href: p.url, class: "projeto-sigla", target: "_blank", rel: "noopener", texto: p.sigla }));
  if (comRelacao && p.relacao === "revoga") li.append(el("span", { class: "chip chip-revogada projeto-rel", texto: "revoga" }));
  li.append(el("p", { class: "projeto-ementa", texto: p.ementa }));
  const meta = [];
  if (p.situacao) meta.push(p.situacao);
  if (p.atualizado) meta.push("atualizado em " + formatarData(p.atualizado));
  else if (p.apresentacao) meta.push("apresentado em " + formatarData(p.apresentacao));
  if (meta.length) li.append(el("p", { class: "projeto-meta", texto: meta.join(" · ") }));
  return li;
}

async function idDaPagina() {
  const params = new URLSearchParams(location.search);
  // Nas páginas geradas (lei/<id>.html, site/paginas.py) o id vem no <body data-lei>.
  const id = params.get("id") || document.body.dataset.lei;
  if (id) return id;
  const ref = params.get("ref");
  return ref ? resolverChave(ref).catch(() => null) : null;
}

async function iniciar() {
  const sec = document.getElementById("sec-camara");
  if (!sec) return;
  const id = await idDaPagina();
  if (!id) return;
  const r = await baixar("camara/normas/" + id + ".json");
  if (!r) return; // dados da Câmara ainda não publicados
  const d = r.dados || { origem: [], tramitando: [], encerrados: 0 };
  const caixa = document.getElementById("camara");
  caixa.innerHTML = "";
  sec.hidden = false;

  if (d.origem?.length) {
    caixa.append(el("h3", { texto: d.origem.length > 1 ? "Projetos de origem" : "Projeto de origem" }));
    const ul = el("ul", { class: "projetos" });
    d.origem.forEach(p => ul.append(itemProjeto(p, false)));
    caixa.append(ul);
  }

  const lista = d.tramitando || [];
  caixa.append(el("h3", { texto: "Projetos em tramitação que alteram esta lei" + (lista.length ? ` (${lista.length})` : "") }));
  if (!lista.length) {
    caixa.append(el("p", { class: "vazio", texto: "Nenhum projeto em tramitação na Câmara cita esta norma na ementa." }));
  } else {
    const ul = el("ul", { class: "projetos" });
    lista.slice(0, MOSTRAR).forEach(p => ul.append(itemProjeto(p, true)));
    caixa.append(ul);
    if (lista.length > MOSTRAR) {
      const botao = el("button", { type: "button", class: "botao projetos-mais", texto: `Ver todos os ${lista.length}` });
      botao.addEventListener("click", () => {
        lista.slice(MOSTRAR).forEach(p => ul.append(itemProjeto(p, true)));
        botao.remove();
      });
      caixa.append(botao);
    }
  }
  if (d.encerrados) {
    caixa.append(el("p", { class: "dica", texto: `Outros ${d.encerrados.toLocaleString("pt-BR")} projetos que a alteravam já foram arquivados, retirados ou viraram lei.` }));
  }
}

iniciar().catch(() => {});
