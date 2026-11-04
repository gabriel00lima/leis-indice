// Referência de legislação conforme a ABNT NBR 6023:2018 (7.11.1, documento
// jurídico em meio eletrônico) e chamada no texto conforme a NBR 10520:2023.
//
// Elementos essenciais da legislação: jurisdição (em maiúsculas), epígrafe
// (tipo, número e data por extenso) e ementa, seguidos dos dados de
// publicação. Em meio eletrônico: local, editora, ano, "Disponível em:" e
// "Acesso em:". Exemplos da própria norma:
//   BRASIL. Lei nº 12.965, de 23 de abril de 2014. Estabelece princípios [...].
//     Brasília, DF: Presidência da República, 2014. Disponível em: http://...
//     Acesso em: 20 abr. 2014.
//   BRASIL. Constituição (1988). Emenda constitucional nº 9, de 9 de novembro
//     de 1995. Dá nova redação [...].
//   BRASIL. [Constituição (1988)]. Constituição da República Federativa do
//     Brasil de 1988. Brasília, DF: Presidência da República, [2016].
// A NBR 6023 não traz forma de referência para um artigo isolado: a obra
// referenciada é a norma inteira e o artigo vai na chamada, como
// (BRASIL, 1990, art. 49).

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
  "agosto", "setembro", "outubro", "novembro", "dezembro"];
// Abreviação dos meses (NBR 6023, anexo A).
const MESES_ABREV = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.",
  "set.", "out.", "nov.", "dez."];

const URL_CONSTITUICAO = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm";

// Tipo do frontmatter -> como a epígrafe aparece nos exemplos da NBR 6023.
const EPIGRAFE = {
  "lei ordinária": "Lei", "lei": "Lei",
  "lei complementar": "Lei complementar",
  "decreto-lei": "Decreto-lei",
  "decreto": "Decreto",
  "medida provisória": "Medida provisória",
  "emenda constitucional": "Emenda constitucional",
  "lei delegada": "Lei delegada",
};

const PASTA_TIPO = {
  "leis-ordinarias": "Lei", "leis-complementares": "Lei complementar",
  "decretos-lei": "Decreto-lei", "emendas-constitucionais": "Emenda constitucional",
  "decretos": "Decreto", "medidas-provisorias": "Medida provisória", "leis-delegadas": "Lei delegada",
};

const dia = d => (d === 1 ? "1º" : String(d));

function partesData(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  return m ? { ano: +m[1], mes: +m[2], dia: +m[3] } : null;
}

export function dataPorExtenso(iso) {
  const p = partesData(iso);
  return p ? `${dia(p.dia)} de ${MESES[p.mes - 1]} de ${p.ano}` : "";
}

export function dataAcesso(data = new Date()) {
  return `${data.getDate()} ${MESES_ABREV[data.getMonth()]} ${data.getFullYear()}`;
}

// "8078" -> "8.078"; mantém sufixos como "9-A".
function numeroNorma(n) {
  const m = /^(\d+)(.*)$/.exec(String(n || "").trim());
  return m ? Number(m[1]).toLocaleString("pt-BR") + m[2] : String(n || "");
}

// Constituição que a emenda altera, pela data da emenda.
function constituicaoDaEmenda(iso) {
  const d = String(iso || "");
  if (d >= "1988-10-05") return 1988;
  if (d >= "1967-01-24") return 1967;
  if (d >= "1946-09-18") return 1946;
  return 1934;
}

// Editora conforme o site de onde o texto vem.
function editoraDaFonte(url) {
  let host = "";
  try { host = new URL(url).hostname; } catch { return "[s. n.]"; }
  if (/(^|\.)planalto\.gov\.br$/.test(host)) return "Presidência da República";
  // Portal mantido em conjunto por Câmara e Senado (Ato Conjunto nº 2/2021).
  if (/(^|\.)normas\.leg\.br$/.test(host) || /(^|\.)lexml\.gov\.br$/.test(host)) return "Congresso Nacional";
  if (/(^|\.)senado\.(leg|gov)\.br$/.test(host)) return "Senado Federal";
  if (/(^|\.)camara\.(leg|gov)\.br$/.test(host)) return "Câmara dos Deputados";
  return "[s. n.]";
}

// "art-5" -> "art. 5º"; "art-10-a" -> "art. 10-A".
export function rotuloArtigo(ancora) {
  const m = /^art-(\d+)(?:-([a-z]))?$/i.exec(String(ancora || ""));
  if (!m) return "";
  const n = +m[1];
  return "art. " + n + (n < 10 ? "º" : "") + (m[2] ? "-" + m[2].toUpperCase() : "");
}

function frase(t) {
  t = String(t || "").replace(/\s+/g, " ").trim();
  return t && !/[.!?]$/.test(t) ? t + "." : t;
}

// Só normas federais e a Constituição de 1988 têm jurisdição conhecida aqui.
export function podeCitar(id) {
  return id === "constituicao" || String(id || "").startsWith("federal/");
}

/**
 * Monta a referência e a chamada.
 * @param {string} id      id da norma (caminho no acervo sem ".md")
 * @param {object} info    frontmatter/índice: tipo, numero, data, ementa, fonte
 * @param {object} [op]    { artigo: "art-49", acesso: Date }
 * @returns {{referencia: string, chamada: string} | null}
 */
export function citacaoABNT(id, info = {}, op = {}) {
  if (!podeCitar(id)) return null;
  const acesso = "Acesso em: " + dataAcesso(op.acesso || new Date()) + ".";
  const art = rotuloArtigo(op.artigo);

  if (id === "constituicao") {
    // Texto compilado e atualizado: ano da versão consultada, entre colchetes.
    const ano = (op.acesso || new Date()).getFullYear();
    return {
      referencia: "BRASIL. [Constituição (1988)]. Constituição da República Federativa do Brasil de 1988. " +
        `Brasília, DF: Presidência da República, [${ano}]. Disponível em: ${URL_CONSTITUICAO}. ${acesso}`,
      chamada: `(BRASIL, [${ano}]${art ? ", " + art : ""})`,
    };
  }

  const p = partesData(info.data);
  const pasta = String(id).split("/")[1];
  const tipo = EPIGRAFE[String(info.tipo || "").toLowerCase()] || PASTA_TIPO[pasta];
  if (!p || !tipo || !info.numero) return null;

  const prefixo = tipo === "Emenda constitucional" ? `Constituição (${constituicaoDaEmenda(info.data)}). ` : "";
  const epigrafe = `${tipo} nº ${numeroNorma(info.numero)}, de ${dataPorExtenso(info.data)}.`;
  const ementa = frase(info.ementa);
  const fonte = info.fonte || "";
  const publicacao = `Brasília, DF: ${editoraDaFonte(fonte)}, ${p.ano}.` +
    (fonte ? ` Disponível em: ${fonte}. ${acesso}` : "");

  return {
    referencia: ["BRASIL.", prefixo + epigrafe, ementa, publicacao].filter(Boolean).join(" ").replace(/\s+/g, " "),
    chamada: `(BRASIL, ${p.ano}${art ? ", " + art : ""})`,
  };
}
