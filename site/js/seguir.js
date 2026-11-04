// Botão "Seguir" da página da lei: entrega o feed RSS da norma (feed/<id>.xml,
// gerado no build por site/feeds.py) e explica como recebê-lo num leitor de RSS,
// por e-mail ou no Telegram. Sem servidor e sem cadastro.

const id = new URLSearchParams(location.search).get("id") || document.body.dataset.lei;

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "texto") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}

function icone(d) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("aria-hidden", "true");
  s.innerHTML = d;
  return s;
}

const ICONE_SINO = '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/>';
const fora = { target: "_blank", rel: "noopener" };

function dataBR(texto) {
  const d = new Date(texto);
  return isNaN(d) ? "" : d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

function ultimas(xml) {
  const itens = [...xml.querySelectorAll("item")].slice(0, 3);
  if (!itens.length) {
    return el("p", { class: "seguir-vazio", texto: "Nenhuma alteração registrada até agora. Quando houver, ela aparece no feed." });
  }
  return el("ul", { class: "seguir-ultimas" }, ...itens.map(it => {
    const t = it.querySelector("title")?.textContent || "";
    const link = it.querySelector("link")?.textContent || "#";
    const data = dataBR(it.querySelector("pubDate")?.textContent || "");
    return el("li", {}, el("a", { href: link, texto: t }), data ? el("span", { texto: data }) : "");
  }));
}

function montarDialogo(urlFeed, xml) {
  const campo = el("input", { type: "text", readonly: "", value: urlFeed, "aria-label": "Link do feed RSS desta lei" });
  campo.addEventListener("focus", () => campo.select());
  const copiar = el("button", { type: "button", class: "botao-cheio seguir-copiar", texto: "Copiar link" });
  copiar.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(urlFeed); copiar.textContent = "Copiado"; }
    catch { campo.select(); copiar.textContent = "Use Ctrl+C"; }
    setTimeout(() => { copiar.textContent = "Copiar link"; }, 2000);
  });
  const fechar = el("button", { type: "button", class: "seguir-fechar", "aria-label": "Fechar", texto: "×" });
  const enc = encodeURIComponent(urlFeed);
  const geral = new URL("feed/novidades.xml", document.baseURI).href;

  const dlg = el("dialog", { class: "seguir-dialogo", "aria-labelledby": "seguir-titulo" },
    fechar,
    el("h2", { id: "seguir-titulo", texto: "Seguir esta lei" }),
    el("p", { class: "seguir-intro", texto: "Receba um aviso quando outra norma alterar ou revogar esta lei, ou quando o texto dela mudar no acervo. Funciona por RSS, sem cadastro." }),
    el("div", { class: "seguir-campo" }, campo, copiar),
    el("dl", { class: "seguir-modos" },
      el("dt", { texto: "Num leitor de RSS" }),
      el("dd", {},
        el("a", { href: `https://feedly.com/i/subscription/feed/${enc}`, ...fora, texto: "Feedly" }), " · ",
        el("a", { href: `https://www.inoreader.com/?add_feed=${enc}`, ...fora, texto: "Inoreader" }), " · ",
        el("a", { href: urlFeed, texto: "abrir o feed" }),
        " ou cole o link no seu leitor."),
      el("dt", { texto: "Por e-mail" }),
      el("dd", {}, "Cole o link num serviço que manda feeds por e-mail, como o ",
        el("a", { href: "https://blogtrottr.com/", ...fora, texto: "Blogtrottr" }), "."),
      el("dt", { texto: "No Telegram" }),
      el("dd", {}, "Mande o link para um bot de RSS, como o ",
        el("a", { href: "https://t.me/TheFeedReaderBot", ...fora, texto: "@TheFeedReaderBot" }), "."),
    ),
    el("h3", { texto: "Últimas no feed" }),
    ultimas(xml),
    el("p", { class: "seguir-geral" }, "Para acompanhar todas as normas novas: ",
      el("a", { href: geral, texto: "feed geral de novidades" }), "."),
  );
  fechar.addEventListener("click", () => dlg.close());
  // Clique fora da caixa fecha.
  dlg.addEventListener("click", ev => { if (ev.target === dlg) dlg.close(); });
  document.body.append(dlg);
  return dlg;
}

async function iniciar() {
  if (!id || id.startsWith("externo:")) return;
  const urlFeed = new URL(`feed/${id}.xml`, document.baseURI).href;
  const resp = await fetch(urlFeed).catch(() => null);
  // Sem feed (norma fora do índice, ou site gerado sem site/feeds.py): sem botão.
  if (!resp || !resp.ok) return;
  const xml = new DOMParser().parseFromString(await resp.text(), "application/xml");
  if (xml.querySelector("parsererror")) return;

  let dlg = null;
  const botao = el("button", { type: "button", class: "acao acao-seguir", "aria-haspopup": "dialog" }, icone(ICONE_SINO), "Seguir");
  botao.addEventListener("click", () => {
    dlg ||= montarDialogo(urlFeed, xml);
    dlg.showModal();
  });
  document.getElementById("acoes")?.prepend(botao);
}

iniciar();
