// Estados e municípios do IBGE (data/ibge/, gerado por ibge/coletar.py).
// Utilitários para filtros por UF/município. Sem dependências.
//
//   import * as loc from "./js/localidades.js";
//   await loc.estados();                    // [{ codigo, sigla, nome, slug, regiao, capital, municipios }]
//   await loc.estado("sp");                 // por sigla, código (35) ou slug ("sao-paulo")
//   await loc.municipios("RJ");             // [{ codigo, nome, uf, slug, capital }] da UF
//   await loc.municipio(3550308);           // por código IBGE, ou ("sao-paulo", "SP") por slug
//   await loc.buscarMunicipios("sao jo", { uf: "SP", limite: 10 });
//   loc.preencherSelectUF(select);  loc.preencherSelectMunicipio(select, "MG");

const BASES = ["data/ibge/", "../data/ibge/"];

export function slug(texto) {
  return String(texto ?? "")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

async function baixar(arquivo) {
  let erro;
  for (const b of BASES) {
    try {
      const r = await fetch(b + arquivo);
      if (r.ok) return await r.json();
      erro = new Error(`${r.status} ao baixar ${b + arquivo}`);
    } catch (e) { erro = e; }
  }
  throw erro ?? new Error(`${arquivo} não encontrado`);
}

let estadosP = null;
export function estados() {
  return (estadosP ??= baixar("estados.json"));
}

let municipiosP = null;
function todos() {
  return (municipiosP ??= baixar("municipios.json").then(({ campos, linhas }) => {
    const lista = linhas.map((l) => {
      const o = Object.fromEntries(campos.map((c, i) => [c, l[i]]));
      o.capital = !!o.capital;
      o._busca = " " + o.slug.replace(/-/g, " ");
      return o;
    });
    const porCodigo = new Map(lista.map((m) => [m.codigo, m]));
    const porUF = new Map();
    for (const m of lista) {
      if (!porUF.has(m.uf)) porUF.set(m.uf, []);
      porUF.get(m.uf).push(m);
    }
    return { lista, porCodigo, porUF };
  }));
}

// Aceita sigla ("SP"/"sp"), código IBGE (35 ou "35") ou slug do nome ("sao-paulo").
export async function estado(chave) {
  const lista = await estados();
  const k = String(chave ?? "").trim();
  if (/^\d+$/.test(k)) return lista.find((e) => e.codigo === Number(k)) ?? null;
  const s = k.toUpperCase();
  return lista.find((e) => e.sigla === s) ?? lista.find((e) => e.slug === slug(k)) ?? null;
}

export async function nomeUF(sigla) {
  return (await estado(sigla))?.nome ?? sigla;
}

export async function municipios(uf) {
  const { lista, porUF } = await todos();
  if (!uf) return lista;
  const e = await estado(uf);
  return e ? porUF.get(e.sigla) ?? [] : [];
}

// municipio(3550308) ou municipio("sao-paulo", "SP") / municipio("São Paulo", "SP").
export async function municipio(chave, uf) {
  const { porCodigo } = await todos();
  if (/^\d{7}$/.test(String(chave))) return porCodigo.get(Number(chave)) ?? null;
  const s = slug(chave);
  return (await municipios(uf)).find((m) => m.slug === s) ?? null;
}

// Busca por nome, sem acento e por início de palavra; capitais e nomes que
// começam com o termo vêm primeiro.
export async function buscarMunicipios(termo, { uf = null, limite = 20 } = {}) {
  const t = slug(termo).replace(/-/g, " ");
  if (!t) return [];
  const base = await municipios(uf);
  const achados = [];
  for (const m of base) {
    const pos = m._busca.indexOf(" " + t);
    if (pos < 0) continue;
    achados.push([pos === 0 ? 0 : 1, m.capital ? 0 : 1, m]);
  }
  achados.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2].nome.localeCompare(b[2].nome, "pt-BR"));
  return achados.slice(0, limite).map((a) => a[2]);
}

function opcoes(select, itens, vazio) {
  select.replaceChildren();
  if (vazio != null) select.append(new Option(vazio, ""));
  for (const [valor, rotulo] of itens) select.append(new Option(rotulo, valor));
}

// Preenche um <select> com as UFs (valor = sigla), ordenadas por nome.
export async function preencherSelectUF(select, { vazio = "Todos os estados" } = {}) {
  const lista = [...(await estados())].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  opcoes(select, lista.map((e) => [e.sigla, `${e.nome} (${e.sigla})`]), vazio);
}

// Preenche um <select> com os municípios da UF (valor = código IBGE).
export async function preencherSelectMunicipio(select, uf, { vazio = "Todos os municípios" } = {}) {
  const lista = uf ? await municipios(uf) : [];
  opcoes(select, lista.map((m) => [String(m.codigo), m.nome]), vazio);
  select.disabled = !lista.length;
}
