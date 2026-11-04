// Seção "No Diário Oficial" no painel da página da lei (lei.html).
import { manifestoDou, arquivoDou, tituloAto } from "./comum.js";

const ROTULOS = { publicacao: "Publicada", altera: "Alterada", revoga: "Revogação" };
const COR = { publicacao: "var(--verde)", altera: "var(--rel-altera)", revoga: "var(--rel-revoga)" };

function data(d) { const [a, m, dia] = String(d || "").split("-"); return dia ? `${dia}/${m}/${a}` : ""; }

// lei.js troca ?ref= por ?id= depois de resolver; espera um pouco por isso.
async function idDaLei() {
  for (let i = 0; i < 40; i++) {
    const id = new URLSearchParams(location.search).get("id");
    if (id) return id;
    await new Promise(r => setTimeout(r, 250));
  }
  return null;
}

async function iniciar() {
  const painel = document.getElementById("painel");
  const id = await idDaLei();
  if (!painel || !id) return;
  let lista;
  try {
    const m = await manifestoDou();
    lista = (await arquivoDou(m.arquivos.por_norma))[id];
  } catch { return; }
  if (!lista || !lista.length) return;

  const css = document.createElement("link");
  css.rel = "stylesheet"; css.href = new URL("dou.css", import.meta.url).href;
  document.head.append(css);

  const sec = document.createElement("section");
  sec.className = "caixa dou-na-lei";
  sec.id = "sec-dou";
  const h = document.createElement("h2"); h.textContent = "No Diário Oficial";
  const dica = document.createElement("p"); dica.className = "dica";
  dica.textContent = "Atos publicados no DOU que publicam, alteram ou revogam esta norma.";
  const ol = document.createElement("ol");
  for (const x of lista.slice(0, 10)) {
    const li = document.createElement("li");
    const b = document.createElement("b"); b.textContent = ROTULOS[x.rel] || x.rel; b.style.color = COR[x.rel] || "";
    const a = document.createElement("a"); a.textContent = tituloAto(x.identifica);
    a.href = x.norma && x.rel !== "publicacao" ? "lei.html?id=" + encodeURIComponent(x.norma) : x.url;
    const s = document.createElement("small"); s.textContent = `DOU de ${data(x.data)} · `;
    const dou = document.createElement("a"); dou.href = x.url; dou.target = "_blank"; dou.rel = "noopener"; dou.textContent = "ver no DOU";
    s.append(dou);
    li.append(b, a, s);
    ol.append(li);
  }
  const mais = document.createElement("p"); mais.className = "mais-link";
  const link = document.createElement("a"); link.href = "dou/"; link.textContent = "Tudo o que saiu no Diário Oficial →";
  mais.append(link);
  sec.append(h, dica, ol, mais);
  painel.prepend(sec);
}

iniciar();
