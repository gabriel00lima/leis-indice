// Gera as imagens de prévia (Open Graph, 1200x630) em site/og/:
//   padrao.jpg            página inicial e normas sem imagem própria
//   tipo-<pasta>.jpg      uma por tipo de norma (leis-ordinarias, decretos-lei...)
//   <nome-do-arquivo>.jpg uma por lei principal (lista de site/destaques.json)
//
// As imagens são commitadas; o build só as copia. Rodar de novo quando mudar a
// lista de principais ou o visual:
//
//   node scripts/gerar_previas.mjs
//
// Precisa do Playwright com Chromium (npm i -D playwright && npx playwright install chromium).
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const saida = join(raiz, "site", "og");
mkdirSync(saida, { recursive: true });

const destaques = JSON.parse(readFileSync(join(raiz, "site", "destaques.json"), "utf8"));

const TIPOS = {
  "constituicao": ["Constituição Federal", "A lei maior do país, com todas as emendas."],
  "leis-ordinarias": ["Lei Ordinária", "Texto integral, artigos com link próprio e relações com outras normas."],
  "leis-complementares": ["Lei Complementar", "Texto integral, artigos com link próprio e relações com outras normas."],
  "decretos-lei": ["Decreto-Lei", "Texto integral, artigos com link próprio e relações com outras normas."],
  "emendas-constitucionais": ["Emenda Constitucional", "O que mudou na Constituição, artigo por artigo."],
};

const dataBR = d => (d || "").split("-").reverse().join("/");
const numeroBR = n => Number(n).toLocaleString("pt-BR");

function subtituloDe(p) {
  if (p.id === "constituicao") return "Promulgada em 05/10/1988";
  const nome = { "Lei Ordinária": "Lei", "Lei Complementar": "Lei Complementar", "Decreto-Lei": "Decreto-Lei" }[p.tipo] || p.tipo;
  return `${nome} nº ${numeroBR(p.numero)}, de ${dataBR(p.data)}`;
}

const cartoes = [
  { nome: "padrao", sobre: "Acervo aberto das leis federais", titulo: "Leis do Brasil",
    texto: "Busque e leia as leis federais, com links entre normas e o histórico das alterações." },
  ...Object.entries(TIPOS).map(([pasta, [titulo, texto]]) => ({ nome: "tipo-" + pasta, sobre: "Norma federal", titulo, texto })),
  ...destaques.principais.map(p => ({
    nome: p.id.split("/").pop(), sobre: subtituloDe(p), titulo: p.apelido, texto: p.descricao,
  })),
];

const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const pagina = c => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=block" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0}
html,body{width:1200px;height:630px}
body{background:#053a22;color:#fff;font-family:Inter,sans-serif;position:relative;overflow:hidden}
.luz{position:absolute;inset:0;background:radial-gradient(900px 520px at 100% 0%,rgba(17,135,78,.55),transparent 60%),radial-gradient(700px 500px at 0% 100%,rgba(3,38,22,.9),transparent 70%)}
.selo-fundo{position:absolute;right:-40px;top:-120px;font-family:"Source Serif 4",serif;font-size:720px;line-height:1;color:rgba(242,193,46,.07);font-weight:700}
.dentro{position:absolute;inset:72px 80px 96px;display:flex;flex-direction:column}
.marca{display:flex;align-items:center;gap:18px;font-weight:700;font-size:30px;letter-spacing:-.01em}
.selo{width:60px;height:60px;border-radius:14px;background:#032616;border:2px solid rgba(242,193,46,.35);display:grid;place-items:center;color:#f2c12e;font-family:"Source Serif 4",serif;font-size:38px}
.sobre{margin-top:auto;color:#f2c12e;font-weight:600;font-size:28px;letter-spacing:.01em}
h1{font-family:"Source Serif 4",serif;font-weight:700;font-size:${c.titulo.length > 28 ? 72 : 84}px;line-height:1.04;letter-spacing:-.02em;margin-top:14px;max-width:1000px}
p{margin-top:22px;font-size:30px;line-height:1.35;color:rgba(255,255,255,.82);max-width:960px}
.faixa{position:absolute;left:0;right:0;bottom:0;height:18px;background:linear-gradient(90deg,#0a6b3d 0 62%,#f2c12e 62% 81%,#163f8f 81% 100%)}
.url{position:absolute;right:80px;bottom:44px;font-size:22px;color:rgba(255,255,255,.55);font-weight:500}
</style></head><body>
<div class="luz"></div><div class="selo-fundo">§</div>
<div class="dentro">
  <div class="marca"><span class="selo">§</span>Leis do Brasil</div>
  <div class="sobre">${esc(c.sobre)}</div>
  <h1>${esc(c.titulo)}</h1>
  <p>${esc(c.texto)}</p>
</div>
<div class="url">gabriel00lima.github.io/leis-indice</div>
<div class="faixa"></div>
</body></html>`;

const navegador = await chromium.launch();
const aba = await navegador.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
for (const c of cartoes) {
  await aba.setContent(pagina(c), { waitUntil: "networkidle" });
  await aba.evaluate(() => document.fonts.ready);
  await aba.screenshot({ path: join(saida, c.nome + ".jpg"), type: "jpeg", quality: 88 });
  console.log("og/" + c.nome + ".jpg");
}
await navegador.close();
