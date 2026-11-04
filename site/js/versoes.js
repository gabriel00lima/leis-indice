// Comparação de versões de um artigo.
//
// O acervo ctresb/leis guarda só o texto em vigor de cada norma (o histórico git
// do arquivo não tem as redações antigas). As redações anteriores são
// reconstruídas a partir das próprias leis que alteraram o artigo: cada uma traz,
// entre aspas, o texto que deu a ele ("O art. 4º da Lei nº 8.078 ... passa a
// vigorar com a seguinte redação: “Art. 4º ...”").
//
// Este módulo não mexe no DOM: recebe Markdown e devolve estruturas. É usado pelo
// site (js/comparar.js) e pelos testes em site/tests/.

import { citacoes } from "./citacoes.js";

// ---------- limpeza de texto ----------

const PALAVRAS_NOTA = /\b(?:reda[çc][ãa]o\s+dada|reda[çc][ãa]o\s+original|acrescid[oa]s?|acrescentad[oa]s?|inclu[íi]d[oa]s?|revogad[oa]s?|vetad[oa]s?|renumerad[oa]s?|transformad[oa]s?|vide|vig[êe]ncia|convertid[ao]|NR)\b/i;
const PARENTESES = /\((?:[^()]|\([^()]*\))*\)/g;

// Tira as notas editoriais "*(Redação dada pela Lei nº ...)*" e a marcação Markdown.
// Devolve { texto, notas }.
export function limparLinha(linha) {
  const notas = [];
  let t = String(linha).replace(/\*\*/g, "").replace(/\\([*_."'()\[\]-])/g, "$1");
  t = t.replace(PARENTESES, p => {
    if (!PALAVRAS_NOTA.test(p)) return p;
    // "(VETADO)" e "(Revogado)" sozinhos são o próprio texto do dispositivo: viram nota e marca.
    notas.push(p.slice(1, -1).replace(/\*/g, "").trim());
    return " ";
  });
  t = t.replace(/[*_]+/g, "").replace(/\s+/g, " ").trim();
  // Restos de nota mal formatada ("concorrentemente: ").
  t = t.replace(/\s*:\s*$/, ":").replace(/\s+([,.;:])/g, "$1");
  return { texto: t, notas };
}

const ASPAS_INICIO = /^[\s"“”'‘’«]+/;
const ASPAS_FIM = /["“”'’»]\s*(?:\(\s*NR\s*\))?\s*[;,.]?\s*(?:e|ou)?\s*$/i;

const ehReticencias = t => /^[\s.…_-]*$/.test(t) && /[.…]{3,}|…/.test(t);
const tirarReticenciasFinais = t => t.replace(/\s*[.…_]{4,}\s*$/, "").trim();

// ---------- dispositivos ----------

const ROMANO = "[IVXLCDM]+";

// Classifica uma linha já limpa (sem notas nem aspas).
export function classificar(t) {
  let m;
  if ((m = /^Art\.?\s*(\d+(?:\.\d{3})*)\s*[º°o]?\s*(?:-\s*([A-Z]{1,2})\b)?\s*[.:–—-]?\s*([\s\S]*)$/i.exec(t)) && /^art/i.test(t)) {
    return { tipo: "art", art: m[1].replace(/\./g, "") + (m[2] ? "-" + m[2].toUpperCase() : ""), resto: m[3] };
  }
  if ((m = /^§\s*(\d+)\s*[º°o]?\s*(?:-\s*([A-Z])\b)?\s*[.:–—-]?\s*([\s\S]*)$/.exec(t))) {
    const n = m[1] + (m[2] ? "-" + m[2] : "");
    return { tipo: "par", chave: "p" + n, rotulo: `§ ${m[1]}${Number(m[1]) < 10 ? "º" : ""}${m[2] ? "-" + m[2] : ""}`, resto: m[3] };
  }
  if ((m = /^Par[áa]grafo\s+[úu]nico\s*[.:–—-]?\s*([\s\S]*)$/i.exec(t))) {
    return { tipo: "par", chave: "pu", rotulo: "parágrafo único", resto: m[1] };
  }
  if ((m = new RegExp(`^(${ROMANO})(?:\\s*-\\s*([A-Z]))?\\s*[–—-]\\s*([\\s\\S]*)$`).exec(t))) {
    const n = m[1] + (m[2] ? "-" + m[2] : "");
    return { tipo: "inc", chave: "i" + n, rotulo: "inciso " + n, resto: m[3] };
  }
  if ((m = /^([a-z])(?:-([A-Z]))?\s*\)\s*([\s\S]*)$/.exec(t))) {
    const n = m[1] + (m[2] ? "-" + m[2] : "");
    return { tipo: "ali", chave: "a" + n, rotulo: "alínea " + n, resto: m[3] };
  }
  if ((m = /^(\d+)(?:-([A-Z]))?\s*[.)]\s+([\s\S]*)$/.exec(t))) {
    const n = m[1] + (m[2] ? "-" + m[2] : "");
    return { tipo: "item", chave: "n" + n, rotulo: "item " + n, resto: m[3] };
  }
  return { tipo: "texto", resto: t };
}

// Rótulo legível a partir da chave ("p1/iIII/ab" -> "§ 1º, inciso III, alínea b").
export function rotuloDaChave(chave) {
  if (chave === "caput") return "caput";
  if (chave === "artigo") return "artigo inteiro";
  return chave.split("/").filter(p => p !== "caput").map(p => {
    const v = p.slice(1);
    switch (p[0]) {
      case "p": return v === "u" ? "parágrafo único" : `§ ${v.replace(/^(\d+)/, n => n + (Number(n) < 10 ? "º" : ""))}`;
      case "i": return "inciso " + v;
      case "a": return "alínea " + v;
      case "n": return "item " + v;
      default: return p;
    }
  }).join(", ");
}

// Leitor incremental de dispositivos: recebe linhas limpas e monta
// Map chave -> { chave, rotulo, texto, omitido, notas } de um artigo.
class Leitor {
  constructor(artInicial = null, artAlvo = null) {
    this.art = artInicial;
    this.alvo = artAlvo;
    this.par = null; this.inc = null; this.ali = null;
    this.atual = null;
    this.mapa = new Map();
    this.ordem = 0;
  }
  chave(nivel, k) {
    if (nivel === "caput") return "caput";
    if (nivel === "par") return k;
    const base = this.par || "caput";
    if (nivel === "inc") return base + "/" + k;
    if (nivel === "ali") return base + "/" + (this.inc || "") + "/" + k;
    return base + "/" + (this.inc || "") + "/" + (this.ali || "") + "/" + k;
  }
  gravar(chave, resto, notas) {
    let texto = tirarReticenciasFinais(resto);
    // "(Revogado)" e "(VETADO)" sozinhos foram lidos como nota: voltam a ser o texto.
    if (!texto) {
      const n = notas.find(x => /^(?:revogad[oa]|vetad[oa])\b/i.test(x)) || notas.find(x => /revogad|vetad/i.test(x));
      if (n) texto = /vetad/i.test(n) ? "(Vetado)" : "(Revogado)";
    }
    const omitido = ehReticencias(resto) || texto === "";
    const d = { chave: chave.replace(/\/{2,}/g, "/"), texto, omitido: omitido && !texto, notas: [...notas], ordem: this.ordem++ };
    d.rotulo = rotuloDaChave(d.chave);
    this.atual = d;
    if (this.alvo && this.art !== this.alvo) return;
    // Se a chave já existe (texto repetido), fica a primeira ocorrência não omitida.
    const ant = this.mapa.get(d.chave);
    if (!ant || (ant.omitido && !d.omitido)) this.mapa.set(d.chave, d);
  }
  linha(bruta) {
    const { texto: limpo, notas } = limparLinha(bruta);
    if (!limpo && !notas.length) return;
    if (ehReticencias(limpo) && !notas.length) { this.atual = null; return; }
    const c = classificar(limpo);
    switch (c.tipo) {
      case "art":
        this.art = c.art; this.par = this.inc = this.ali = null;
        return this.gravar("caput", c.resto, notas);
      case "par":
        this.par = c.chave; this.inc = this.ali = null;
        return this.gravar(this.chave("par", c.chave), c.resto, notas);
      case "inc":
        this.inc = c.chave; this.ali = null;
        return this.gravar(this.chave("inc", c.chave), c.resto, notas);
      case "ali":
        this.ali = c.chave;
        return this.gravar(this.chave("ali", c.chave), c.resto, notas);
      case "item":
        if (!this.ali && !this.inc) break; // número solto: texto comum
        return this.gravar(this.chave("item", c.chave), c.resto, notas);
    }
    // Continuação (ex.: "Pena - reclusão..." depois do caput no Código Penal).
    if (this.atual && (!this.alvo || this.art === this.alvo) && this.mapa.get(this.atual.chave) === this.atual) {
      this.atual.texto = (this.atual.texto ? this.atual.texto + "\n" : "") + tirarReticenciasFinais(limpo);
      this.atual.omitido = false;
      this.atual.notas.push(...notas);
    }
  }
}

// Normaliza "4º", "54-A", "art. 1.228" para a forma usada nas chaves ("4", "54-A", "1228").
export function normArt(s) {
  const m = /(\d+(?:\.\d{3})*)\s*[º°o]?\s*(?:-\s*([A-Z]{1,2}))?/i.exec(String(s));
  return m ? m[1].replace(/\./g, "") + (m[2] ? "-" + m[2].toUpperCase() : "") : null;
}

// Separa o Markdown em linhas de conteúdo, sem frontmatter e títulos.
function linhasDe(md) {
  return String(md).replace(/^---\n[\s\S]*?\n---\n?/, "").split("\n").map(l => l.trim()).filter(Boolean);
}

// Texto em vigor de um artigo, a partir do Markdown da norma.
// Para a Constituição, para antes do ADCT (que repete a numeração dos artigos).
export function artigoVigente(md, art) {
  const leitor = new Leitor(null, art);
  let dentro = false;
  for (const l of linhasDe(md)) {
    if (/^#{1,6}\s/.test(l)) {
      if (/DISPOSI[ÇC][ÕO]ES\s+CONSTITUCIONAIS\s+TRANSIT[ÓO]RIAS/i.test(l)) break;
      if (dentro) leitor.atual = null;
      continue;
    }
    if (/^>/.test(l)) continue;
    const limpo = limparLinha(l).texto;
    const c = /^Art\.?\s*\d/i.test(limpo) ? classificar(limpo) : null;
    if (c && c.tipo === "art") {
      if (dentro && c.art !== art) break;
      if (c.art === art) dentro = true;
    }
    if (dentro) leitor.linha(l);
  }
  return leitor.mapa;
}

// ---------- leis que alteram ----------

// alvo: { constituicao: true } ou { prefixo: "lei", numero: "8078", ano: "1990" }.
function citaAlvo(texto, alvo) {
  return citacoes(texto).filter(c => alvo.constituicao
    ? c.constituicao
    : c.tipo?.prefixo === alvo.prefixo && String(c.numero) === String(alvo.numero) && (!c.ano || !alvo.ano || c.ano === String(alvo.ano)));
}

const RE_ARTS = /\barts?\.\s*((?:\d+(?:\.\d{3})*\s*[º°o]?(?:\s*-\s*[A-Z]{1,2}\b)?(?:\s*(?:,|e)\s*)?)+)/gi;

// Artigos mencionados num trecho ("os arts. 4º, 39 e 82" -> ["4", "39", "82"]).
export function artigosMencionados(trecho) {
  const out = [];
  for (const m of String(trecho).matchAll(RE_ARTS)) {
    for (const p of m[1].split(/\s*(?:,|\be\b)\s*/)) {
      const a = normArt(p);
      if (a && !out.includes(a)) out.push(a);
    }
  }
  return out;
}

// Chave de um dispositivo descrito por extenso ("o inciso IV do § 2º do art. 57").
export function chaveDaDescricao(desc) {
  const partes = [];
  const par = /§\s*(\d+)\s*[º°o]?(?:\s*-\s*([A-Z]))?/.exec(desc);
  if (/par[áa]grafo\s+[úu]nico/i.test(desc)) partes.push("pu");
  else if (par) partes.push("p" + par[1] + (par[2] ? "-" + par[2] : ""));
  const inc = new RegExp(`\\bincisos?\\s+(${ROMANO})(?:\\s*-\\s*([A-Z]))?\\b`).exec(desc);
  const ali = /\bal[íi]neas?\s+["“]?([a-z])["”]?(?:\s*-\s*([A-Z]))?/.exec(desc);
  if (inc) partes.push("i" + inc[1] + (inc[2] ? "-" + inc[2] : ""));
  if (ali) partes.push("a" + ali[1] + (ali[2] ? "-" + ali[2] : ""));
  if (!partes.length) return /\bcaput\b/i.test(desc) ? "caput" : "artigo";
  if (partes[0][0] !== "p") partes.unshift("caput");
  return partes.join("/");
}

// Lê uma lei alteradora e devolve o que ela fez com o artigo `art` da norma `alvo`:
// { acao: "redacao"|"acrescimo"|"revogacao"|null, dispositivos: Map, revogados: [{ chave, descricao }] }
// ou null se ela não mexe no artigo (ou o texto não deu para ler).
export function extrairAlteracao(md, alvo, art) {
  const dispositivos = new Map();
  const revogados = [];
  let acao = null;

  let ativo = false;          // o último comando falava da norma-alvo
  let comando = null;         // { acao, arts }
  let leitor = null;          // dentro de um bloco entre aspas
  let leitorDoComando = null; // o mesmo comando pode ter vários blocos entre aspas seguidos
  let listaRevogacao = false; // "Ficam revogados:" seguido de incisos

  const fecharBloco = () => {
    if (!leitor) return;
    for (const [k, d] of leitor.mapa) {
      if (!dispositivos.has(k) || (dispositivos.get(k).omitido && !d.omitido)) dispositivos.set(k, d);
    }
    if (leitor.mapa.size && !acao) acao = comando?.acao || "redacao";
    leitor.mapa = new Map();
    leitor = null;
  };

  const registrarRevogacao = (texto, refs) => {
    let inicio = 0;
    for (const r of refs) {
      const trecho = texto.slice(inicio, r.fim).replace(/\s+d[aoe]s?\s+(?:Lei|Decreto|Constitui|Medida|Emenda|C[óo]digo)[\s\S]*$/, "");
      inicio = r.fim;
      // Cada "art. N" do trecho, com o que vem antes dele desde o último separador.
      const pedacos = trecho.split(/;|,\s*(?=(?:o|a|os|as)\s)|\s+e\s+(?=(?:o|a|os|as)\s)/);
      for (const p of pedacos) {
        const arts = artigosMencionados(p);
        if (!arts.includes(art)) continue;
        const desc = p.replace(/^.*?\b(?:revogad[oa]s?|revoga(?:m)?-se|revoga)\s*[:,]?\s*/i, "").trim();
        revogados.push({ chave: chaveDaDescricao(desc.replace(RE_ARTS, "")), descricao: desc || p.trim() });
        acao = acao || "revogacao";
      }
    }
  };

  let articulado = false; // pula ementa e preâmbulo (a ementa resume o que a lei faz)
  for (const bruta of linhasDe(md)) {
    if (/^#{1,6}\s/.test(bruta)) { fecharBloco(); ativo = false; comando = null; continue; }
    const { texto } = limparLinha(bruta);
    if (!articulado) { if (/^Art(?:\.|igo)?\s*(?:1\b|1\s*[º°o]|[úu]nico)/i.test(texto)) articulado = true; else continue; }
    const abre = ASPAS_INICIO.test(bruta) && /^["“”'‘]/.test(bruta.replace(/^\*+/, ""));

    if (leitor || (abre && ativo && comando)) {
      if (!leitor) {
        if (!leitorDoComando || leitorDoComando.comando !== comando) {
          const arts = comando.arts;
          leitorDoComando = new Leitor(arts.length === 1 ? arts[0] : null, art);
          leitorDoComando.comando = comando;
        }
        leitor = leitorDoComando;
      }
      const fecha = ASPAS_FIM.test(bruta.replace(/\s*\*\((?:[^()]|\([^()]*\))*\)\*\s*$/, ""));
      let conteudo = bruta.replace(/^\s*\*{0,2}["“”'‘]+/, "");
      if (fecha) conteudo = conteudo.replace(/\s*\*\((?:[^()]|\([^()]*\))*\)\*\s*$/, "").replace(ASPAS_FIM, "");
      leitor.linha(conteudo);
      if (fecha) fecharBloco();
      continue;
    }
    if (abre) continue; // citação de outra norma

    // Fora de aspas: é um comando da lei alteradora (ou texto próprio dela).
    const refs = citaAlvo(texto, alvo);
    const outraNorma = citacoes(texto).some(c => !refs.includes(c)) && !refs.length;
    const remissiva = /\b(?:referid[ao]|mesm[ao]|citad[ao]|daquel[ae])\s+(?:Lei|Decreto|Código|Constitui)/i.test(texto);
    const adct = alvo.constituicao && /Disposi[çc][õo]es\s+Constitucionais\s+Transit[óo]rias/i.test(texto) && !/\bConstitui[çc][ãa]o\s+Federal\b/i.test(texto.replace(/Disposi[çc][õo]es\s+Constitucionais\s+Transit[óo]rias/gi, ""));

    if (adct) { ativo = false; comando = null; listaRevogacao = /revog/i.test(texto) && /:\s*$/.test(texto); continue; }

    if (/revog/i.test(texto) && (refs.length || (ativo && remissiva))) {
      registrarRevogacao(texto, refs.length ? refs : [{ inicio: texto.length, fim: texto.length }]);
      listaRevogacao = /:\s*$/.test(texto);
      ativo = true; comando = null;
      continue;
    }
    if (listaRevogacao && refs.length && /^[IVXLCDM]+\s*[–—-]|^[a-z]\)/.test(texto)) {
      registrarRevogacao(texto, refs);
      continue;
    }
    if (/^(?:Ficam?|Revogam-se)\b.*revogad|revogam-se/i.test(texto) && /:\s*$/.test(texto)) { listaRevogacao = true; ativo = false; continue; }

    const ehComando = /passa(?:m)?\s+a\s+vigorar|seguinte\s+reda[çc][ãa]o|nova\s+reda[çc][ãa]o|acrescid|acrescentad|acrescid|inclu[íi]d|renumerad|alterad[oa]s?\s+(?:da|na)\s+seguinte/i.test(texto);
    if (refs.length || (remissiva && ativo)) {
      ativo = true;
      const semArtProprio = texto.replace(/^Art\.?\s*\d+(?:\.\d{3})*\s*[º°o]?(?:-[A-Z])?\.?\s*/i, "");
      const desloc = texto.length - semArtProprio.length;
      const antes = refs.length ? semArtProprio.slice(0, refs[refs.length - 1].fim - desloc) : semArtProprio;
      comando = ehComando ? {
        acao: /acrescid|acrescentad|inclu[íi]d/i.test(texto) && !/reda[çc][ãa]o|altera[çc]/i.test(texto) ? "acrescimo" : "redacao",
        arts: artigosMencionados(antes),
      } : null;
      if (!ehComando) ativo = false;
      continue;
    }
    if (outraNorma) { ativo = false; comando = null; listaRevogacao = false; continue; }
    if (/^Art\.?\s*\d/i.test(texto)) { ativo = false; comando = null; listaRevogacao = false; }
  }
  fecharBloco();

  // Descarta dispositivos que vieram só como reticências.
  for (const [k, d] of dispositivos) if (d.omitido) dispositivos.delete(k);
  if (!dispositivos.size && !revogados.length) return null;
  return { acao, dispositivos, revogados };
}

// ---------- redação original da Constituição (HTML compilado do Planalto) ----------

// O acervo guarda em fonte/constituicao.htm o texto compilado do Planalto, que mantém
// as redações antigas tachadas (<strike>). A primeira redação tachada sem nota de
// alteração é a original de 1988.
const ENTIDADES = { nbsp: " ", amp: "&", quot: '"', lt: "<", gt: ">", ordm: "º", ordf: "ª", sect: "§", deg: "°", ndash: "–", mdash: "—", laquo: "«", raquo: "»", ldquo: "“", rdquo: "”", lsquo: "‘", rsquo: "’", hellip: "…" };
function decodificarEntidades(t) {
  return t.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === "#") return String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
    if (ENTIDADES[e.toLowerCase()]) return ENTIDADES[e.toLowerCase()];
    // Letras acentuadas: &aacute; &ccedil; &atilde; ...
    const m2 = /^([a-zA-Z])(acute|grave|circ|tilde|uml|cedil)$/.exec(e);
    if (m2) return (m2[1] + { acute: "\u0301", grave: "\u0300", circ: "\u0302", tilde: "\u0303", uml: "\u0308", cedil: "\u0327" }[m2[2]]).normalize("NFC");
    return m;
  });
}

// Devolve Map chave -> texto original (só dispositivos que mudaram desde 1988).
export function originaisDoPlanalto(html, art) {
  const TA = "\u0001", TF = "\u0002";
  const texto = String(html)
    .replace(/<!--[\s\S]*?-->/g, "").replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, "").replace(/\s+/g, " ")
    .replace(/<(?:strike|s|del)\b[^>]*>/gi, TA).replace(/<\/(?:strike|s|del)>/gi, TF)
    .replace(/<br\s*\/?>|<\/p>|<\/h\d>|<\/div>/gi, "\n")
    .replace(/<[^>]+>/g, " ");
  const originais = new Map(), semAlteracao = new Map(), tachados = new Set();
  const leitor = new Leitor(null, null);
  let tachando = false, dentro = false;
  for (const bruta of decodificarEntidades(texto).split("\n")) {
    // Separa o que está tachado do que não está.
    let fora = "", dentroTachado = "";
    for (const ch of bruta) {
      if (ch === TA) tachando = true;
      else if (ch === TF) tachando = false;
      else if (tachando) dentroTachado += ch; else fora += ch;
    }
    // O Planalto às vezes deixa só o rótulo ("a)", "IV -") fora do <strike>.
    const foraLimpo = limparLinha(fora).texto;
    const cf = classificar(foraLimpo);
    const soRotulo = cf.tipo !== "texto" && !cf.resto.replace(/[\s.;:,–—-]/g, "");
    const tachada = !!dentroTachado.trim() && (soRotulo || !foraLimpo.replace(/[\s.;:,–—-]/g, ""));
    // Tachada: o que sobra fora do <strike> é só rótulo ou pontuação, então a linha inteira vale.
    const linha = (tachada ? bruta.replace(/[\u0001\u0002]/g, "") : fora).replace(/\s+/g, " ").trim();
    if (!linha) continue;
    if (/^ATO\s+DAS\s+DISPOSI[ÇC][ÕO]ES\s+CONSTITUCIONAIS\s+TRANSIT[ÓO]RIAS/i.test(linha)) break;
    const c = classificar(limparLinha(linha).texto);
    if (c.tipo === "art") {
      if (dentro && c.art !== art) break;
      dentro = c.art === art;
    }
    if (!dentro) continue;
    const antes = leitor.atual;
    leitor.linha(linha);
    const d = leitor.atual;
    if (!d || d === antes) continue;
    const semNota = !notaDiz(d.notas, /reda[çc][ãa]o\s+dada|inclu[íi]d|acrescid|renumerad/i);
    if (tachada) {
      if (semNota && !originais.has(d.chave)) originais.set(d.chave, d.texto);
      tachados.add(d.chave);
    } else if (semNota && !tachados.has(d.chave) && !semAlteracao.has(d.chave)) {
      // Nunca alterado até a data do arquivo: o texto dele ainda é o de 1988.
      semAlteracao.set(d.chave, d.texto);
    }
  }
  for (const [k, t] of semAlteracao) if (!tachados.has(k)) originais.set(k, t);
  return originais;
}

// ---------- notas do texto em vigor ----------

// Cada nota "(Redação dada pela Lei nº X)" diz que X deu ao dispositivo o texto atual.
// Completa os eventos com isso quando a lei X não está no acervo ou não deu para ler
// a redação nela. Devolve a lista de eventos (nova), em ordem cronológica.
export function completarComNotas(eventos, vigente) {
  const lista = eventos.map(e => ({ ...e, dispositivos: new Map(e.dispositivos) }));
  const mesmaNorma = (lei, c) => {
    if (lei.ref) return lei.ref.tipo?.prefixo === c.tipo?.prefixo && lei.ref.numero === c.numero && (lei.ref.ano || "") === (c.ano || "");
    const m = /\/([a-z]+)-(\d+)(?:-[a-z0-9]+)*?-(\d{4})-\d{2}-\d{2}$/.exec(lei.id || "");
    return !!m && m[1] === c.tipo?.prefixo && m[2] === String(c.numero) && (!c.ano || m[3] === c.ano);
  };
  for (const d of vigente.values()) {
    for (const nota of d.notas) {
      if (!/reda[çc][ãa]o\s+dada|acrescid|inclu[íi]d/i.test(nota) || /^vide\b/i.test(nota)) continue;
      const cits = citacoes(nota).filter(c => !c.constituicao && c.tipo);
      if (!cits.length) continue;
      // "dada pela MP nº X, convertida na Lei nº Y": vale a lei de conversão, se ela estiver na lista.
      const c = cits.find(x => lista.some(e => mesmaNorma(e.lei, x))) || cits[cits.length - 1];
      let ev = lista.find(e => mesmaNorma(e.lei, c));
      if (ev?.dispositivos.has(d.chave)) continue;
      if (!ev) {
        ev = { lei: { id: c.id || null, ref: c, data: c.data || (c.ano ? c.ano + "-12-31" : ""), soNota: true },
          acao: null, dispositivos: new Map(), revogados: [] };
        lista.push(ev);
      }
      ev.dispositivos.set(d.chave, { ...d, daNota: true,
        acrescido: /acrescid|inclu[íi]d/i.test(nota) && !/reda[çc][ãa]o\s+dada/i.test(nota) });
    }
  }
  return lista.sort((a, b) => String(a.lei.data || "").localeCompare(String(b.lei.data || "")));
}

// ---------- linha do tempo ----------

export const normalizar = t => String(t || "")
  .normalize("NFC").replace(/["“”'‘’]/g, "").replace(/\s+/g, " ")
  .replace(/[\s.;:,]+$/, "").trim().toLowerCase();

const notaDiz = (notas, re) => notas.some(n => re.test(n));

// eventos: [{ lei: { id, nome, data }, acao, dispositivos: Map, revogados }] em ordem cronológica.
// vigente: Map do artigoVigente().
// Devolve [{ lei, mudancas: [{ chave, rotulo, tipo, antes, antesLei, depois, emVigor }] }]
// tipo: "alterou" | "acrescentou" | "revogou".
// antes === null quando a redação anterior não está no acervo.
// originais (opcional): Map chave -> texto original, quando a fonte o tem.
export function montarLinhaDoTempo(eventos, vigente, originais = new Map()) {
  const historico = new Map(); // chave -> [{ texto, lei }]
  const saida = [];
  const ultimo = k => historico.get(k)?.at(-1) || null;

  for (const ev of eventos) {
    const mudancas = [];
    for (const [k, d] of ev.dispositivos) {
      const ant = ultimo(k);
      if (ant && normalizar(ant.texto) === normalizar(d.texto)) continue; // repetiu a mesma redação
      if (!ant && originais.has(k) && normalizar(originais.get(k)) === normalizar(d.texto)) continue;
      const v = vigente.get(k);
      const revogou = /^\((?:revogad|vetad)/i.test(d.texto);
      const acrescido = !revogou && !ant && !originais.has(k) && (ev.acao === "acrescimo" || d.acrescido ||
        (v && notaDiz(v.notas, /acrescid|inclu[íi]d/i) && !notaDiz(v.notas, /reda[çc][ãa]o dada/i)) ||
        (!v && ev.acao === "acrescimo"));
      mudancas.push({
        chave: k, rotulo: d.rotulo, tipo: revogou ? (/vetad/i.test(d.texto) ? "vetou" : "revogou") : acrescido ? "acrescentou" : "alterou",
        antes: ant ? ant.texto : acrescido ? "" : originais.get(k) ?? null,
        antesLei: ant?.lei || (!acrescido && originais.has(k) ? "original" : null),
        depois: d.texto, ordem: d.ordem, daNota: !!d.daNota,
      });
      if (!historico.has(k)) historico.set(k, []);
      historico.get(k).push({ texto: d.texto, lei: ev.lei });
    }
    for (const r of ev.revogados) {
      const alvoChaves = r.chave === "artigo" ? [...historico.keys()] : [r.chave];
      const antesTexto = r.chave === "artigo"
        ? alvoChaves.map(k => ultimo(k)).filter(Boolean).map(x => x.texto).join("\n") || null
        : ultimo(r.chave)?.texto ?? originais.get(r.chave) ?? null;
      mudancas.push({
        chave: r.chave, rotulo: rotuloDaChave(r.chave), tipo: "revogou",
        antes: antesTexto, antesLei: r.chave === "artigo" ? null : ultimo(r.chave)?.lei || null,
        depois: "", descricao: r.descricao, ordem: 1e6,
      });
      for (const k of alvoChaves) {
        if (!historico.has(k)) historico.set(k, []);
        historico.get(k).push({ texto: "", lei: ev.lei, revogado: true });
      }
    }
    mudancas.sort((a, b) => a.ordem - b.ordem);
    if (mudancas.length) saida.push({ lei: ev.lei, acao: ev.acao, mudancas });
  }

  // Marca o que continua em vigor: a última versão de cada dispositivo que bate com o texto atual.
  for (const ev of saida) for (const m of ev.mudancas) m.emVigor = false;
  for (const [k, lista] of historico) {
    const v = vigente.get(k);
    const ult = lista.at(-1);
    for (let i = saida.length - 1; i >= 0; i--) {
      const m = saida[i].mudancas.find(x => x.chave === k && saida[i].lei === ult.lei);
      if (!m) continue;
      if (m.tipo === "revogou") m.emVigor = !v || !v.texto || /revogad/i.test(v.notas.join(" "));
      else m.emVigor = !!v && normalizar(v.texto) === normalizar(m.depois);
      break;
    }
  }
  return saida;
}

// ---------- diferença palavra a palavra ----------

// Devolve [{ tipo: "igual"|"saiu"|"entrou", texto }] comparando por palavras.
export function diferenca(a, b) {
  const pa = String(a).split(/(\s+)/), pb = String(b).split(/(\s+)/);
  const n = pa.length, m = pb.length;
  if (n * m > 400000) return [{ tipo: "saiu", texto: a }, { tipo: "entrou", texto: b }];
  const lcs = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) {
    lcs[i][j] = pa[i] === pb[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  }
  const out = [];
  const push = (tipo, texto) => {
    const ult = out.at(-1);
    if (ult && ult.tipo === tipo) ult.texto += texto; else out.push({ tipo, texto });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (pa[i] === pb[j]) { push("igual", pa[i]); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) push("saiu", pa[i++]);
    else push("entrou", pb[j++]);
  }
  while (i < n) push("saiu", pa[i++]);
  while (j < m) push("entrou", pb[j++]);
  // Um espaço "igual" entre duas mudanças entra nelas, para a marcação não ficar picotada.
  const final = [];
  out.forEach((p, k) => {
    if (p.tipo === "igual" && !p.texto.trim() && k > 0 && k < out.length - 1) {
      final.push({ tipo: "saiu", texto: p.texto }, { tipo: "entrou", texto: p.texto });
    } else final.push(p);
  });
  const juntos = [];
  for (const p of final) {
    // Junta trechos do mesmo lado, mesmo com trechos do outro lado entre eles.
    const ult = juntos.at(-1), penult = juntos.at(-2);
    if (ult && ult.tipo === p.tipo) ult.texto += p.texto;
    else if (p.tipo !== "igual" && ult && ult.tipo !== "igual" && penult?.tipo === p.tipo) penult.texto += p.texto;
    else juntos.push({ ...p });
  }
  return juntos;
}
