import { manifesto, listaShards, carregarTudo, usandoExemplo, urlLei, formatarData, normalizarTexto } from "./dados.js";

const $ = s => document.querySelector(s);
const form = $("#form"), q = $("#q"), tipoSel = $("#tipo"), sit = $("#sit"), ordem = $("#ordem");
const status = $("#status"), lista = $("#resultados"), mais = $("#mais"), atalhos = $("#atalhos");

const POR_PAGINA = 50;
let entradas = null;        // índice carregado (todas as normas ou só um tipo)
let tipoCarregado = undefined;
let achados = [], mostrados = 0;

function preparar(e) {
  if (e._busca) return e;
  e._busca = normalizarTexto(`${e.titulo} ${e.tipo} ${e.ementa}`);
  e._numero = String(e.numero || "").replace(/\D/g, "");
  e._ano = String(e.data || "").slice(0, 4);
  return e;
}

// Pontuação simples: número exato > ano > título > ementa.
function pontuar(e, termos) {
  let p = 0;
  for (const t of termos) {
    const dig = t.replace(/\D/g, "");
    if (dig && dig === t.replace(/[.\-/]/g, "")) {
      if (e._numero === dig) p += 100;
      else if (dig.length === 4 && e._ano === dig) p += 20;
      else if (e._busca.includes(t)) p += 5;
      else return 0;
    } else if (e._busca.includes(t)) {
      p += normalizarTexto(e.titulo).includes(t) ? 10 : 3;
    } else {
      return 0;
    }
  }
  return p;
}

function termosDe(texto) {
  return normalizarTexto(texto)
    .replace(/\b(n[ºo°]|numero|de|da|do|das|dos|e)\b/g, " ")
    .split(/\s+/).filter(Boolean)
    // "8.078/90" -> "8078"
    .map(t => /^[\d.]+(\/\d{2,4})?$/.test(t) ? t.split("/")[0].replace(/\./g, "") : t);
}

async function garantirIndice() {
  const tipo = tipoSel.value || null;
  const shards = await listaShards();
  const porTipo = shards.some(s => s.tipo);
  const alvo = porTipo ? tipo : null;
  if (entradas && (tipoCarregado === null || tipoCarregado === alvo)) return;
  status.textContent = "Carregando índice…";
  entradas = (await carregarTudo((f, t) => {
    if (t > 1) status.textContent = `Carregando índice… ${f} de ${t} partes`;
  }, alvo)).map(preparar);
  tipoCarregado = alvo;
}

async function buscar() {
  const texto = q.value.trim();
  const params = new URLSearchParams();
  if (texto) params.set("q", texto);
  for (const [k, el] of [["tipo", tipoSel], ["sit", sit], ["ordem", ordem]]) if (el.value) params.set(k, el.value);
  history.replaceState(null, "", params.toString() ? "?" + params : location.pathname);

  const filtrando = texto || tipoSel.value || sit.value;
  atalhos.hidden = !!filtrando;
  if (!filtrando) { lista.innerHTML = ""; status.textContent = ""; mais.hidden = true; return; }

  try { await garantirIndice(); }
  catch (err) { status.textContent = "Não foi possível carregar o índice: " + err.message; return; }

  const termos = termosDe(texto);
  achados = [];
  for (const e of entradas) {
    if (tipoSel.value && e.tipo !== tipoSel.value) continue;
    if (sit.value === "vigente" && e.revogada) continue;
    if (sit.value === "revogada" && !e.revogada) continue;
    const p = termos.length ? pontuar(e, termos) : 1;
    if (p) achados.push([p, e]);
  }
  const porData = (a, b) => String(b[1].data).localeCompare(String(a[1].data));
  if (ordem.value === "recentes") achados.sort(porData);
  else if (ordem.value === "antigas") achados.sort((a, b) => porData(b, a));
  else achados.sort((a, b) => b[0] - a[0] || porData(a, b));

  const n = achados.length;
  status.textContent = n ? `${n.toLocaleString("pt-BR")} ${n === 1 ? "norma encontrada" : "normas encontradas"}` : "Nenhuma norma encontrada.";
  lista.innerHTML = "";
  mostrados = 0;
  mostrarMais();
}

function mostrarMais() {
  const frag = document.createDocumentFragment();
  for (const [, e] of achados.slice(mostrados, mostrados + POR_PAGINA)) {
    const li = document.createElement("li");
    li.innerHTML = `
      <a class="titulo" href="${urlLei(e.id)}"></a>
      <span class="meta"></span>
      <p class="ementa"></p>`;
    li.querySelector(".titulo").textContent = e.titulo || e.id;
    li.querySelector(".meta").textContent = [e.tipo, formatarData(e.data)].filter(Boolean).join(" · ");
    if (e.revogada) {
      const b = document.createElement("span");
      b.className = "selo revogada"; b.textContent = "Revogada";
      li.querySelector(".meta").append(" ", b);
    }
    li.querySelector(".ementa").textContent = e.ementa || "";
    frag.append(li);
  }
  mostrados += POR_PAGINA;
  lista.append(frag);
  mais.hidden = mostrados >= achados.length;
}

async function iniciar() {
  if (await usandoExemplo().catch(() => false)) $("#aviso-exemplo").hidden = false;
  // Tipos disponíveis: do manifesto (shards por tipo) ou do índice único.
  const m = await manifesto().catch(() => null);
  let tipos = [];
  if (m?.shards) tipos = [...new Set(m.shards.map(s => s.tipo).filter(Boolean))];
  else if (m?.entradas) tipos = [...new Set(m.entradas.map(e => e.tipo).filter(Boolean))];
  for (const t of tipos.sort((a, b) => a.localeCompare(b, "pt-BR"))) tipoSel.add(new Option(t, t));

  const p = new URLSearchParams(location.search);
  q.value = p.get("q") || "";
  tipoSel.value = p.get("tipo") || "";
  sit.value = p.get("sit") || "";
  ordem.value = p.get("ordem") || "";
  buscar();
}

let espera;
q.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(buscar, 250); });
for (const el of [tipoSel, sit, ordem]) el.addEventListener("change", buscar);
form.addEventListener("submit", ev => { ev.preventDefault(); buscar(); });
mais.addEventListener("click", mostrarMais);
iniciar();
