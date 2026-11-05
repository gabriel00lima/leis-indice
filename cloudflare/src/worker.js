// Worker do site Leis do Brasil no Cloudflare.
//
// Como o pedido chega aqui:
//   1. O Cloudflare procura o caminho nos arquivos estáticos (_cf/assets: páginas,
//      JS, CSS, data/). Se achar, entrega direto, sem rodar este código.
//   2. Se não achar, roda fetch() abaixo, que procura no bucket R2 (lei/, api/,
//      pagefind/: centenas de milhares de arquivos, além do limite de arquivos
//      estáticos do Workers).
//   3. Se também não estiver no R2, devolve o 404.html do site.
//
// Rotas de backend (login, pagamento) entram aqui no futuro, antes do R2.

import { cacheControl, candidatas, tipoPorNome } from "./rotas.js";

async function doR2(request, env, chaves) {
  for (const chave of chaves) {
    const obj = await env.SITE.get(chave, { onlyIf: request.headers });
    if (obj === null) continue;
    const headers = new Headers();
    obj.writeHttpMetadata(headers);
    if (!headers.has("content-type")) headers.set("content-type", tipoPorNome(chave));
    headers.set("etag", obj.httpEtag);
    headers.set("cache-control", cacheControl(chave));
    headers.set("access-control-allow-origin", "*");
    // onlyIf não atendido (If-None-Match igual): objeto sem corpo.
    if (!("body" in obj)) return new Response(null, { status: 304, headers });
    return new Response(request.method === "HEAD" ? null : obj.body, { headers });
  }
  return null;
}

async function pagina404(request, env) {
  const url = new URL("/404.html", request.url);
  const r = await env.ASSETS.fetch(new Request(url, { method: "GET" }));
  return new Response(r.body, {
    status: 404,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/_saude") {
      return Response.json({ ok: true, versao: env.VERSAO || null });
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Método não permitido", { status: 405, headers: { allow: "GET, HEAD" } });
    }

    // Cache da borda (só vale em domínio próprio; no workers.dev é ignorado).
    const cache = caches.default;
    const chaveCache = new Request(url.toString(), { method: "GET" });
    if (request.method === "GET" && !request.headers.has("if-none-match")) {
      const emCache = await cache.match(chaveCache);
      if (emCache) return emCache;
    }

    const resposta = await doR2(request, env, candidatas(url.pathname));
    if (!resposta) return pagina404(request, env);

    if (request.method === "GET" && resposta.status === 200) {
      ctx.waitUntil(cache.put(chaveCache, resposta.clone()));
    }
    return resposta;
  },
};
