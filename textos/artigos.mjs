// Divide o Markdown de uma norma do ctresb/leis em artigos, com a mesma âncora
// que a página da lei usa (site/js/lei.js): #art-5, #art-11-a. Sem dependências.

// Mesmo critério de marcarArtigos() em site/js/lei.js: parágrafo que começa
// com **Art. N** (opcionalmente "º", "." e "-A").
const RE_ARTIGO = /^\*\*\s*(Art\.\s*(\d+)(?:[º°.])?(?:\s*-\s*([A-Z])\b)?)/;
const RE_TITULO = /^(#{1,6})\s+(.*)$/;

export const idArtigo = (num, letra) => "art-" + num + (letra ? "-" + letra.toLowerCase() : "");

export function semFrontmatter(md) {
  const m = /^---\r?\n[\s\S]*?\r?\n---\r?\n?/.exec(md);
  return m ? md.slice(m[0].length) : md;
}

// Markdown -> texto corrido. Tira as notas do acervo em itálico, como
// "*(Redação dada pela Lei nº 13.105, de 2015)*", que só poluem a busca.
export function textoPlano(md) {
  return md
    .replace(/\*\([^)]*\)\*/g, " ")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/(\*\*|__|\*|_|`)/g, "")
    .replace(/^\s*(?:>|[-+]\s)\s*/gm, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\s*\n\s*/g, "\n")
    .trim();
}

// Devolve [{ ancora, rotulo, secao, texto }], um por artigo.
// - ancora: "art-49"; se o número se repete (ex.: ADCT da Constituição), a
//   página da lei não dá id ao repetido, então usa o título da seção ("sec-12"),
//   numerado como lei.js faz (h2 a h5 na ordem do texto), ou null (link para
//   o topo da lei) quando a seção é um h1, como o ADCT.
// - secao: o título mais próximo acima do artigo ("CAPÍTULO V — DAS PRÁTICAS…").
export function dividirArtigos(md) {
  const linhas = semFrontmatter(md).split(/\r?\n/);
  const artigos = [];
  const usadas = new Set();
  let atual = null, nSec = 0, ultimaSec = null, secao = "";

  const fechar = () => {
    if (!atual) return;
    const texto = textoPlano(atual.linhas.join("\n"));
    // Artigo só com "(Revogado)" ou vazio: nada para achar.
    if (texto.replace(/^Art\.\s*\S+\s*/, "").length >= 15) {
      artigos.push({ ancora: atual.ancora, rotulo: atual.rotulo, secao: atual.secao, texto });
    }
    atual = null;
  };

  for (const linha of linhas) {
    const t = RE_TITULO.exec(linha);
    if (t) {
      fechar();
      const nivel = t[1].length;
      // lei.js só numera h2 a h5; abaixo de um h1/h6 não há âncora de seção.
      if (nivel >= 2 && nivel <= 5) { nSec++; ultimaSec = "sec-" + nSec; } else ultimaSec = null;
      secao = textoPlano(t[2]);
      continue;
    }
    const a = RE_ARTIGO.exec(linha);
    if (a) {
      fechar();
      const id = idArtigo(a[2], a[3]);
      const ancora = usadas.has(id) ? ultimaSec : id;
      usadas.add(id);
      const rotulo = "art. " + a[2] + (/[º°]/.test(a[1]) ? "º" : "") + (a[3] ? "-" + a[3] : "");
      atual = { ancora, rotulo, secao, linhas: [linha] };
      continue;
    }
    if (atual) atual.linhas.push(linha);
  }
  fechar();
  return artigos;
}
