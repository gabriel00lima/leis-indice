// Funções puras do Worker (testadas em cloudflare/tests/).

const CACHE_HTML = "public, max-age=300";            // páginas de lei: 5 min
const CACHE_JSON = "public, max-age=3600";           // API e dados: 1 h
const CACHE_OUTROS = "public, max-age=86400";        // índice da busca etc.: 1 dia

export function cacheControl(chave) {
  if (chave.endsWith(".html") || chave.endsWith(".xml")) return CACHE_HTML;
  if (chave.endsWith(".json")) return CACHE_JSON;
  return CACHE_OUTROS;
}

// lei/<id> e lei/<id>/ também abrem lei/<id>.html, como no GitHub Pages.
export function candidatas(caminho) {
  let chave;
  try {
    chave = decodeURIComponent(caminho.replace(/^\/+/, ""));
  } catch {
    return [];
  }
  if (!chave || chave.includes("..")) return [];
  if (chave.endsWith("/")) return [chave + "index.html", chave.slice(0, -1) + ".html"];
  if (/\.[A-Za-z0-9_]+$/.test(chave.split("/").pop())) return [chave];
  return [chave + ".html", chave + "/index.html"];
}


// Tipo pelo nome, para objetos enviados ao R2 sem Content-Type.
const TIPOS = {
  html: "text/html; charset=utf-8",
  json: "application/json",
  xml: "application/xml",
  js: "text/javascript; charset=utf-8",
  css: "text/css; charset=utf-8",
  txt: "text/plain; charset=utf-8",
  jpg: "image/jpeg",
  png: "image/png",
  svg: "image/svg+xml",
  wasm: "application/wasm",
};

export function tipoPorNome(chave) {
  const ext = (/\.([A-Za-z0-9]+)$/.exec(chave) || [])[1];
  return TIPOS[(ext || "").toLowerCase()] || "application/octet-stream";
}
