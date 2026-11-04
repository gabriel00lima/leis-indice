// Dados do normas.leg.br coletados pelo GitHub Actions (normas_leg/coletar.py).
// A API de lá não tem CORS; por isso o site lê só o que foi gravado em
// data/normas-leg/<id>.json: { urn, artigos: {"art-5": "art5", ...}, texto_md? }.
// Normas sem esse arquivo não têm estrutura no normas.leg.br (ou ainda não foram
// consultadas): o site então mostra só o link para a norma inteira.

const SITE = "https://normas.leg.br/?urn=";
const BASES = ["data/", "../data/"];
const cache = new Map();

// Link para a norma (ou um dispositivo dela) no normas.leg.br.
export function urlNormas(urn, fragmento) {
  if (!urn) return null;
  return SITE + urn + (fragmento ? "!" + fragmento : "");
}

// data/normas-leg/<id>.json, ou null se não existe.
export function dadosNormasLeg(id) {
  if (!id) return Promise.resolve(null);
  if (!cache.has(id)) {
    cache.set(id, (async () => {
      for (const b of BASES) {
        try {
          const r = await fetch(b + "normas-leg/" + id.split("/").map(encodeURIComponent).join("/") + ".json");
          if (r.ok) return await r.json();
          if (r.status === 404) continue;
        } catch { /* tenta a próxima base */ }
      }
      return null;
    })());
  }
  return cache.get(id);
}

// Texto alternativo em Markdown, quando o coletor guardou um.
export async function textoNormasLeg(id) {
  const d = await dadosNormasLeg(id);
  return d?.texto_md ? d : null;
}

// Põe em cada artigo marcado (p.artigo#art-N) um link discreto para o mesmo
// artigo no normas.leg.br. Só quando há o mapa de artigos: os fragmentos de
// artigos incluídos por emenda (ex. "art103-2,emc-45-2004-12-08") não dá para adivinhar.
export async function linkarArtigos(raiz, id) {
  const d = await dadosNormasLeg(id);
  if (!d?.artigos || !d.urn) return 0;
  let n = 0;
  for (const p of raiz.querySelectorAll("p.artigo[id^='art-']")) {
    const frag = d.artigos[p.id];
    if (!frag || p.querySelector(".no-normas")) continue;
    const a = document.createElement("a");
    a.className = "no-normas";
    a.href = urlNormas(d.urn, frag);
    a.target = "_blank";
    a.rel = "noopener";
    a.title = "Ver este artigo no normas.leg.br (Senado e Câmara)";
    a.textContent = "normas.leg.br ↗";
    p.append(" ", a);
    n++;
  }
  return n;
}
