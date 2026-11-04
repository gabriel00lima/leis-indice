// Destaque "Lei explicada" no topo do texto da lei, quando existe resumo para ela.
// Fica separado de lei.js: só lê o id da página (depois que lei.js resolve ?ref=) e
// insere a caixa antes do texto. Os links "#art-N" ficam na mesma página (lei.js cuida
// do <base href> das páginas geradas).
import { explicadaDaLei, carregarExplicada, renderizar, textoRevisao, AVISO, el } from "./explicadas.js";

let feito = false;

// lei.html?id=<id>, ou a página gerada lei/<id> (site/paginas.py), que traz o id em <body data-lei>.
const idDaPagina = () => new URLSearchParams(location.search).get("id") || document.body.dataset.lei;

async function mostrar() {
  const id = idDaPagina();
  if (!id || feito) return;
  feito = true;
  const e = await explicadaDaLei(id);
  if (!e) return;
  const { secoes } = await carregarExplicada(e.slug);
  const leitura = "explicada.html?lei=" + encodeURIComponent(e.slug);

  const caixa = el("section", { class: "destaque-explicada", "aria-labelledby": "titulo-explicada" });
  const cabeca = el("header", {},
    el("p", { class: "selo-explicada" }, el("span", { "aria-hidden": "true", texto: "✦" }), " Lei explicada"),
    el("h2", { id: "titulo-explicada", texto: "Esta lei em linguagem simples" }));
  caixa.append(cabeca);

  const intro = secoes.get("Em poucas palavras");
  if (intro) caixa.append(el("div", { class: "explicada-texto explicada-intro" }, ...renderizar(intro, id, { mesmaPagina: true }).childNodes));

  const pontos = secoes.get("O que você precisa saber");
  if (pontos) {
    const det = el("details", { class: "explicada-pontos" },
      el("summary", { texto: "O que você precisa saber" }),
      el("div", { class: "explicada-texto" }, ...renderizar(pontos, id, { mesmaPagina: true }).childNodes));
    caixa.append(det);
  }

  caixa.append(
    el("div", { class: "destaque-explicada-rodape" },
      el("a", { class: "botao botao-cheio", href: leitura, texto: "Ler a explicação completa →" }),
      el("p", { class: "dica", texto: [AVISO, textoRevisao(e)].filter(Boolean).join(" ") })));

  const texto = document.getElementById("texto");
  texto.parentElement.insertBefore(caixa, texto);
}

const params = new URLSearchParams(location.search);
if (idDaPagina()) {
  mostrar();
} else if (params.get("ref")) {
  // lei.js troca ?ref= por ?id= e depois preenche o título; espera isso acontecer.
  const titulo = document.getElementById("titulo");
  new MutationObserver((_, obs) => {
    if (new URLSearchParams(location.search).get("id")) { obs.disconnect(); mostrar(); }
  }).observe(titulo, { childList: true, characterData: true, subtree: true });
}
