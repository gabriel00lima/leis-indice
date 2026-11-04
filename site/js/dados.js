// Carregamento do índice (data/index.json) e dos vínculos (data/links.json).
// Se data/ ainda não existir no site publicado, usa os dados de exemplo.
// Formatos aceitos: ver site/README.md.

import { chaveDoId } from "./citacoes.js";

export const RAW = "https://raw.githubusercontent.com/ctresb/leis/main/";
export const GITHUB = "https://github.com/ctresb/leis";
export const API = "https://api.github.com/repos/ctresb/leis";

// "../data/" cobre o Pages em modo "Deploy from a branch" (site servido em /site/).
const BASES = ["data/", "../data/", "exemplo/"];
let base = null;

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ao baixar ${url}`);
  return r.json();
}

// Descobre onde estão os dados (data/ ou exemplo/) e lê o index.json.
let manifestoP = null;
export function manifesto() {
  if (!manifestoP) manifestoP = (async () => {
    for (const b of BASES) {
      try {
        const m = await json(b + "index.json");
        base = b;
        return Array.isArray(m) ? { total: m.length, entradas: m, shards: null } : m;
      } catch { /* tenta a próxima base */ }
    }
    throw new Error("Índice não encontrado em data/index.json.");
  })();
  return manifestoP;
}

export async function usandoExemplo() {
  await manifesto();
  return base === "exemplo/";
}

// ================= esferas (federal / estadual) =================

export const UFS = { SP: "São Paulo", RJ: "Rio de Janeiro", MG: "Minas Gerais" };

// "SP" para ids estaduais (estaduais/SP/...) e externos estaduais (externo:lei-5-1950-sp).
export function ufDoId(id) {
  const s = String(id);
  const m = /^estaduais\/([A-Z]{2})\//.exec(s) || /^externo:.*-([a-z]{2})$/.exec(s);
  return m ? m[1].toUpperCase() : null;
}
export const ehEstadual = id => !!ufDoId(id);

// Âmbito da busca: "" = federais (padrão, o mais leve), "SP"/"RJ"/"MG", "estaduais" ou "todas".
export function noAmbito(ambito, uf) {
  if (!ambito) return !uf;
  if (ambito === "todas") return true;
  if (ambito === "estaduais") return !!uf;
  return uf === ambito;
}
const ufDoShard = s => s.uf || (s.esfera === "estadual" ? (/estaduais\/([A-Z]{2})/.exec(s.arquivo || "") || [])[1] : null) || null;

// Shard em que um id deveria estar (pelo campo "raiz" do manifesto).
function shardsDoId(shards, id) {
  if (shards.some(s => s.raiz)) {
    return shards.filter(s => s.raiz && (id === s.raiz || id.startsWith(s.raiz + "/")));
  }
  const pasta = id.split("/")[1];
  return [...shards].sort((a, b) =>
    (b.arquivo?.includes(pasta) ? 1 : 0) - (a.arquivo?.includes(pasta) ? 1 : 0));
}

// Shards: { arquivo, tipo?, total? }. Índice em array único vira um shard só.
export async function listaShards() {
  const m = await manifesto();
  if (m.entradas) return [{ arquivo: null, tipo: null, total: m.total }];
  return m.shards;
}

const cacheShard = new Map();
export async function carregarShard(s) {
  const m = await manifesto();
  if (!s.arquivo) return m.entradas;
  if (!cacheShard.has(s.arquivo)) {
    cacheShard.set(s.arquivo, json(base + s.arquivo).then(normalizar));
  }
  return cacheShard.get(s.arquivo);
}

// Aceita shards como array de objetos ou { campos: [...], linhas: [[...]] }.
function normalizar(d) {
  if (Array.isArray(d)) return d;
  if (d && d.campos && d.linhas) {
    return d.linhas.map(l => Object.fromEntries(d.campos.map((c, i) => [c, l[i]])));
  }
  return d.entradas || [];
}

// Carrega os shards de um tipo e de um âmbito (padrão: só os federais), avisando o progresso.
export async function carregarTudo(aoProgredir, tipo, ambito = "") {
  const shards = (await listaShards()).filter(s =>
    (!tipo || !s.tipo || s.tipo === tipo) && (!s.arquivo || noAmbito(ambito, ufDoShard(s))));
  let feitos = 0;
  const partes = await Promise.all(shards.map(async s => {
    const e = await carregarShard(s);
    aoProgredir?.(++feitos, shards.length);
    return e;
  }));
  return partes.flat();
}

// Acha uma entrada do índice pelo id, carregando só o shard provável.
export async function buscarEntrada(id) {
  const shards = await listaShards();
  const ordenados = shards[0]?.arquivo ? shardsDoId(shards, id) : shards;
  for (const s of ordenados) {
    const e = (await carregarShard(s)).find(x => x.id === id);
    if (e) return e;
  }
  return null;
}

// Resolve tipo+número+ano para um id do índice (citações sem data completa).
// Com uf (citação dentro de uma lei estadual), procura primeiro no estado e depois nas
// federais; "constituicao-estadual::" dá a Constituição do estado.
export async function resolverChave(k, uf = null) {
  const [prefixo, numero, ano] = k.split(":");
  const shards = await listaShards();
  const casa = id => {
    const c = chaveDoId(id);
    if (!c) return false;
    const [p, n, a] = c.split(":");
    return p === prefixo && n === numero && (!ano || a === ano);
  };
  const ordem = uf
    ? [...shards.filter(s => ufDoShard(s) === uf), ...shards.filter(s => !ufDoShard(s))]
    : shards.filter(s => !s.arquivo || !ufDoShard(s));
  for (const s of ordem) {
    if (s.arquivo && s.prefixo && s.prefixo !== prefixo) continue;
    const entradas = await carregarShard(s);
    if (prefixo === "constituicao-estadual") return entradas[0]?.id || null;
    // a mais recente, quando o número se repete (sem ano)
    const achados = entradas.filter(x => casa(x.id));
    if (achados.length) return achados.sort((a, b) => String(b.data).localeCompare(String(a.data)))[0].id;
  }
  return null;
}

// Vínculos de uma norma. links.json pode ser um objeto único ou um manifesto
// { shards: [{ arquivo, pasta? }] } com objetos menores.
let linksP = null;
export async function vinculos(id) {
  await manifesto();
  if (!linksP) linksP = json(base + "links.json").catch(() => ({}));
  const l = await linksP;
  if (!l.shards) return l[id] || null;
  const pasta = id.split("/")[1] || id;
  const s = l.shards.find(x => x.pasta === pasta) || null;
  // Sem parte própria (ex.: decreto fora do índice), não há vínculos guardados.
  const alvos = s ? [s] : l.shards.some(x => x.esfera) ? [] : l.shards;
  for (const x of alvos) {
    if (!cacheShard.has("links:" + x.arquivo)) cacheShard.set("links:" + x.arquivo, json(base + x.arquivo).catch(() => ({})));
    const d = await cacheShard.get("links:" + x.arquivo);
    if (d[id]) return d[id];
  }
  return null;
}

// Estatísticas e listas pré-calculadas para a página inicial (site/destaques.py).
export async function destaques() {
  return json("destaques.json");
}

// Normas citadas mas fora do acervo/índice têm id "externo:<prefixo>-<número>[-<ano>]".
export const ehExterno = id => String(id).startsWith("externo:");

// Nome do tipo pela pasta das normas estaduais.
export const NOMES_PASTA = {
  "leis-ordinarias": "Lei", "leis-complementares": "Lei Complementar", "emendas-constitucionais": "Emenda Constitucional",
  "decretos-lei": "Decreto-Lei", "decretos-lei-complementares": "Decreto-Lei Complementar", "leis-delegadas": "Lei Delegada",
  "leis-constitucionais": "Lei Constitucional", "decretos": "Decreto", "decretos-legislativos": "Decreto Legislativo",
  "decretos-nao-numerados": "Decreto", "resolucoes": "Resolução", "deliberacoes": "Deliberação", "portarias": "Portaria",
};

// Partes de um id estadual: { uf, pasta, numero, ano }.
export function partesEstaduais(id) {
  const m = /^estaduais\/([A-Z]{2})\/([a-z-]+)\/(\d{4})\/([^/]+)$/.exec(String(id));
  if (!m) return null;
  const n = /^[a-z]+-(\d+)-(\d{4})/.exec(m[4]);
  return { uf: m[1], pasta: m[2], numero: n ? n[1] : null, ano: n ? n[2] : m[3] };
}

// Rótulo curto de uma norma a partir do id, sem precisar do índice.
export function rotuloDoId(id) {
  if (id === "constituicao") return "Constituição Federal de 1988";
  const ext = /^externo:([a-z]+)-([\d.]+)(?:-(\d{4}))?(?:-([a-z]{2}))?$/.exec(id);
  if (ext) {
    const nomesExt = { lei: "Lei", lcp: "Lei Complementar", del: "Decreto-Lei", dec: "Decreto",
      dlg: "Decreto Legislativo", mpv: "Medida Provisória", emc: "Emenda Constitucional", ldl: "Lei Delegada" };
    return `${nomesExt[ext[1]] || ext[1]} nº ${Number(ext[2]).toLocaleString("pt-BR")}${ext[3] ? "/" + ext[3] : ""}` +
      (ext[4] ? ` (${ext[4].toUpperCase()})` : "");
  }
  const est = partesEstaduais(id);
  if (est) {
    if (est.pasta === "constituicao") return `Constituição do Estado de ${UFS[est.uf] || est.uf}`;
    const nome = NOMES_PASTA[est.pasta] || "Norma";
    return est.numero
      ? `${nome} nº ${Number(est.numero).toLocaleString("pt-BR")}/${est.ano} (${est.uf})`
      : `${nome} de ${est.ano} (${est.uf})`;
  }
  const m = /\/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-\d{2}-\d{2}$/.exec(id);
  if (!m) return id.split("/").pop();
  const nomes = { lei: "Lei", lcp: "Lei Complementar", del: "Decreto-Lei", dec: "Decreto",
    dlg: "Decreto Legislativo", mpv: "Medida Provisória", emc: "Emenda Constitucional", ldl: "Lei Delegada" };
  const n = Number(m[2]).toLocaleString("pt-BR");
  return `${nomes[m[1]] || m[1]} nº ${n}/${m[3]}`;
}

export function urlLei(id, ancora) {
  if (ehExterno(id)) {
    const m = /^externo:[a-z]+-([\d.]+)(?:-(\d{4}))?/.exec(id);
    const uf = ufDoId(id);
    return "./?q=" + encodeURIComponent(m ? m[1] + (m[2] ? " " + m[2] : "") : id) + (uf ? "&ambito=" + uf : "");
  }
  const hash = ancora ? "#" + ancora : "";
  // Com o build completo (site/paginas.py), cada norma tem página própria em lei/<id>,
  // com título e prévia para buscadores e WhatsApp. Sem ele, só existe lei.html?id=.
  // As estaduais ainda não têm página própria (deixariam o site acima do limite de 1 GB do Pages).
  if (PAGINAS && !ufDoId(id)) return PAGINAS + id.split("/").map(encodeURIComponent).join("/") + hash;
  return "lei.html?id=" + encodeURIComponent(id) + hash;
}

const PAGINAS = document.querySelector('meta[name="leis:paginas"]')?.content || "";

export function formatarData(d) {
  if (!d) return "";
  const [a, m, dia] = String(d).split("-");
  return dia ? `${dia}/${m}/${a}` : d;
}

export const numeroBR = n => Number(n || 0).toLocaleString("pt-BR");

// Apelidos conhecidos, usados no cabeçalho da lei e na busca.
export const APELIDOS = {
  "constituicao": "Constituição Federal",
  "federal/leis-ordinarias/2002/lei-10406-2002-01-10": "Código Civil",
  "federal/decretos-lei/1940/del-2848-1940-12-07": "Código Penal",
  "federal/decretos-lei/1943/del-5452-1943-05-01": "CLT",
  "federal/leis-ordinarias/1990/lei-8078-1990-09-11": "Código de Defesa do Consumidor",
  "federal/leis-ordinarias/2015/lei-13105-2015-03-16": "Código de Processo Civil",
  "federal/decretos-lei/1941/del-3689-1941-10-03": "Código de Processo Penal",
  "federal/leis-ordinarias/1966/lei-5172-1966-10-25": "Código Tributário Nacional",
  "federal/leis-ordinarias/1990/lei-8069-1990-07-13": "Estatuto da Criança e do Adolescente",
  "federal/leis-ordinarias/1997/lei-9503-1997-09-23": "Código de Trânsito Brasileiro",
  "federal/leis-ordinarias/2018/lei-13709-2018-08-14": "LGPD",
  "federal/leis-ordinarias/2014/lei-12965-2014-04-23": "Marco Civil da Internet",
  "federal/leis-ordinarias/2006/lei-11340-2006-08-07": "Lei Maria da Penha",
  "federal/leis-ordinarias/2021/lei-14133-2021-04-01": "Nova Lei de Licitações",
  "federal/leis-complementares/2000/lcp-101-2000-05-04": "Lei de Responsabilidade Fiscal",
  "federal/decretos-lei/1942/del-4657-1942-09-04": "LINDB",
  "federal/leis-ordinarias/1990/lei-8112-1990-12-11": "Estatuto dos Servidores Públicos Federais",
  "federal/leis-ordinarias/2003/lei-10741-2003-10-01": "Estatuto da Pessoa Idosa",
  "federal/leis-ordinarias/1996/lei-9394-1996-12-20": "Lei de Diretrizes e Bases da Educação",
  "federal/leis-ordinarias/1984/lei-7210-1984-07-11": "Lei de Execução Penal",
  "federal/leis-ordinarias/2011/lei-12527-2011-11-18": "Lei de Acesso à Informação",
  "federal/leis-ordinarias/2006/lei-11343-2006-08-23": "Lei de Drogas",
  "federal/leis-ordinarias/1992/lei-8429-1992-06-02": "Lei de Improbidade Administrativa",
  "federal/leis-ordinarias/1995/lei-9099-1995-09-26": "Lei dos Juizados Especiais",
  "federal/leis-ordinarias/1993/lei-8666-1993-06-21": "Lei de Licitações (1993)",
  "federal/leis-ordinarias/1991/lei-8213-1991-07-24": "Lei de Benefícios da Previdência",
  "federal/leis-ordinarias/2015/lei-13146-2015-07-06": "Estatuto da Pessoa com Deficiência",
};

export function normalizarTexto(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
