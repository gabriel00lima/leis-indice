// Reconhece citações a normas federais no texto ("Lei nº 9.008, de 21/3/1995",
// "Decreto-Lei nº 2.848, de 7 de dezembro de 1940", "Lei nº 8.078/90",
// "Constituição Federal") e as converte em referências resolvíveis.
// Usado pelo site (no navegador) e por scripts/gerar_exemplo_site.mjs (no Node).

// Ordem importa: os nomes mais longos vêm antes ("Lei Complementar" antes de "Lei").
export const TIPOS = [
  { nome: "Lei Complementar", re: "Lei\\s+Complementar", pasta: "leis-complementares", prefixo: "lcp" },
  { nome: "Decreto-Lei", re: "Decreto[-\\s][Ll]ei", pasta: "decretos-lei", prefixo: "del" },
  { nome: "Decreto Legislativo", re: "Decreto\\s+Legislativo", pasta: "decretos-legislativos", prefixo: "dlg" },
  { nome: "Medida Provisória", re: "Medida\\s+Provis[óo]ria", pasta: "medidas-provisorias", prefixo: "mpv" },
  { nome: "Emenda Constitucional", re: "Emenda\\s+Constitucional", pasta: "emendas-constitucionais", prefixo: "emc" },
  { nome: "Lei Delegada", re: "Lei\\s+Delegada", pasta: "leis-delegadas", prefixo: "ldl" },
  { nome: "Decreto", re: "Decreto", pasta: "decretos", prefixo: "dec" },
  { nome: "Lei", re: "Lei", pasta: "leis-ordinarias", prefixo: "lei" },
];

export const ID_CONSTITUICAO = "constituicao";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
  "agosto", "setembro", "outubro", "novembro", "dezembro"];

const NUM = "(\\d{1,3}(?:\\.\\s?\\d{3})+|\\d+)";
const MES = "(\\d{1,2}|" + MESES.join("|") + "|marco)";
const DATA =
  "(?:\\s*,\\s*de\\s+(\\d{1,2})[º°]?(?:\\s*\\/\\s*|\\s+de\\s+)" + MES +
  "(?:\\s*\\/\\s*|\\s+de\\s+)(\\d{4}|\\d{2})" +
  "|\\s*,\\s*de\\s+(\\d{4})" +
  "|\\s*\\/\\s*(\\d{4}|\\d{2})(?!\\d))?";
const NORMA =
  "\\b(" + TIPOS.map(t => t.re).join("|") + ")\\s+(?:n[º°o]\\.?|n\\.\\s?[º°o])\\s*" + NUM +
  "(?:-([A-Z]))?" + DATA;
const CONST = "\\b(Constitui[çc][ãa]o\\s+(?:Federal|da\\s+Rep[úu]blica))";
const ART = "(?:\\b(arts?\\.)\\s*(\\d+)[º°]?(?:-([A-Z]))?[^.;:()]{0,70}?\\s+(?:d[aoe]s?|na|no)\\s+)?";

// Grupo 1-3: artigo opcional; 4: Constituição; 5: tipo; 6: número; 7: letra;
// 8-10: dia/mês/ano; 11: ", de AAAA"; 12: "/AA".
export function regexCitacao() {
  return new RegExp(ART + "(?:" + CONST + "|" + NORMA + ")", "g");
}

function tipoDe(texto) {
  const limpo = texto.replace(/\s+/g, " ");
  for (const t of TIPOS) if (new RegExp("^" + t.re + "$").test(limpo)) return t;
  return null;
}

function anoCompleto(a) {
  if (!a) return null;
  if (a.length === 4) return a;
  const n = parseInt(a, 10);
  const atual = new Date().getFullYear() % 100;
  return (n <= atual ? "20" : "19") + a.padStart(2, "0");
}

function mesNumero(m) {
  if (/^\d+$/.test(m)) return parseInt(m, 10);
  const i = MESES.indexOf(m.toLowerCase().replace("marco", "março"));
  return i >= 0 ? i + 1 : null;
}

const p2 = n => String(n).padStart(2, "0");

// Converte um match de regexCitacao() em referência.
// Retorna { tipo, numero, letra, ano, data, id, artigo } ou null.
// "id" só vem preenchido quando a data completa permite montar o caminho exato.
export function interpretar(m) {
  const artigo = m[2] ? m[2] + (m[3] ? "-" + m[3] : "") : null;
  if (m[4]) {
    return { tipo: null, numero: null, ano: "1988", data: "1988-10-05", id: ID_CONSTITUICAO, artigo, constituicao: true };
  }
  const tipo = tipoDe(m[5]);
  if (!tipo) return null;
  const numero = m[6].replace(/[.\s]/g, "");
  const letra = m[7] || null;
  let ano = null, data = null;
  if (m[10]) {
    ano = anoCompleto(m[10]);
    const mes = mesNumero(m[9]);
    const dia = parseInt(m[8], 10);
    if (mes && dia >= 1 && dia <= 31) data = `${ano}-${p2(mes)}-${p2(dia)}`;
  } else if (m[11]) {
    ano = m[11];
  } else if (m[12]) {
    ano = anoCompleto(m[12]);
  }
  const id = data && !letra
    ? `federal/${tipo.pasta}/${ano}/${tipo.prefixo}-${numero}-${data}`
    : null;
  return { tipo, numero, letra, ano, data, id, artigo };
}

// Chave usada para achar a norma no índice quando não há data completa.
export function chave(prefixo, numero, ano) {
  return `${prefixo}:${String(numero).replace(/^0+/, "")}:${ano || ""}`;
}

// Extrai a chave de um id do acervo ("federal/leis-ordinarias/1990/lei-8078-1990-09-11").
export function chaveDoId(id) {
  const m = /\/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-\d{2}-\d{2}$/.exec(id);
  return m ? chave(m[1], m[2], m[3]) : null;
}

// Lista todas as citações de um texto (para gerar links.json de exemplo).
export function citacoes(texto) {
  const out = [];
  const re = regexCitacao();
  let m;
  while ((m = re.exec(texto))) {
    const ref = interpretar(m);
    if (ref) out.push({ ...ref, inicio: m.index, fim: m.index + m[0].length, trecho: m[0] });
  }
  return out;
}

// Classifica a relação de uma citação pelo contexto em volta.
// "alterada": nota "(redação dada pela Lei X)" — X altera o texto atual;
// "revogada": nota "(revogado pela Lei X)" — X revoga o texto atual;
// "revoga": "Fica revogada a Lei X" — o texto atual revoga X; senão "cita".
export function relacao(texto, inicio) {
  const antes = texto.slice(Math.max(0, inicio - 160), inicio).toLowerCase();
  const nota = antes.lastIndexOf("*(");
  const trechoNota = nota >= 0 && antes.indexOf(")*", nota) < 0 ? antes.slice(nota) : "";
  if (trechoNota) {
    if (/revogad/.test(trechoNota)) return "revogada";
    if (/reda[çc][ãa]o dada|acrescid|inclu[íi]d|renumerad|transformad|alterad/.test(trechoNota)) return "alterada";
  }
  if (/\b(?:fica|ficam)\s+revogad[oa]s?[^.]{0,80}$/.test(antes)) return "revoga";
  return "cita";
}
