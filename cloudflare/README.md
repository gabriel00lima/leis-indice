# Deploy no Cloudflare (Workers + R2)

O site gerado por `site/build.sh` já passa de 1 GB e de 200 mil arquivos (só a API em `api/v1/`
tem 175 mil), acima do limite de 1 GB do GitHub Pages. Por isso as leis estaduais não tinham
página própria. No Cloudflare o site é servido em duas partes:

| Parte | O que vai | Onde fica | Limite |
|---|---|---|---|
| Arquivos estáticos do Worker | páginas, JS, CSS, `data/`, `og/`, sitemaps (~4 mil arquivos, ~150 MB) | `_cf/assets` → upload do `wrangler deploy` | 20 mil arquivos no plano grátis (100 mil no pago), 25 MiB cada |
| Bucket R2 `leis-do-brasil` | `lei/`, `api/`, `pagefind/` (~270 mil arquivos, ~1,6 GB com as estaduais) | `_cf/r2` → `publicar_r2.sh` (rclone) | 10 GB grátis |

O Worker (`src/worker.js`) só roda quando o caminho não está entre os arquivos estáticos: procura
no R2 (`lei/<id>` também acha `lei/<id>.html`) e, se não achar, devolve o `404.html`.
Arquivo estático não conta no limite de requisições do Worker.

## Por que Cloudflare

- **Tamanho**: R2 não tem limite prático de arquivos e cobra só armazenamento (10 GB grátis), sem
  taxa de saída. Netlify e Vercel também limitam deploys e banda no plano grátis, e o plano grátis da
  Vercel proíbe uso comercial.
- **Custo**: grátis hoje. Plano grátis: 100 mil requisições por dia ao Worker (só páginas de lei, API e
  busca no texto chegam a ele), R2 com 10 GB, 1 milhão de gravações e 10 milhões de leituras por mês.
  Se passar disso, o Workers Paid custa US$ 5/mês.
- **Domínio próprio**: grátis, com HTTPS automático. O domínio pode ser registrado no registro.br
  (`.com.br`) e apontado para o Cloudflare, ou comprado no próprio Cloudflare (`.com`) a preço de custo.
- **Backend futuro**: o mesmo Worker recebe as rotas de login e pagamento, com banco D1 (SQLite) e KV
  para sessões, sem outro servidor. Webhooks de pagamento (Stripe, Mercado Pago) chegam numa rota do Worker.

## Como o deploy roda

O job `cloudflare` em `.github/workflows/deploy-site.yml` roda junto com o deploy do GitHub Pages,
sempre que ele roda (push, coletas, diário). Sem os segredos `CLOUDFLARE_API_TOKEN` e
`CLOUDFLARE_ACCOUNT_ID`, termina verde com um aviso e não faz nada.

1. Descobre o endereço público: variável `SITE_URL` do repositório, ou o endereço `workers.dev` da conta.
2. `SITE_URL=… PAGINAS_ESTADUAIS=1 bash site/build.sh`: links canônicos, sitemaps e API com o endereço
   novo, e página própria para as 68 mil normas estaduais (no Pages elas continuam em `lei.html?id=`).
3. `bash cloudflare/separar.sh`: divide `_site/` em `_cf/assets` e `_cf/r2` e falha se os estáticos
   passarem do limite.
4. Cria o bucket se não existir e roda `bash cloudflare/publicar_r2.sh`: `rclone sync --checksum`, que só
   envia o que mudou. Pasta que o build não gerou (ex.: a API falhou) fica como está no bucket.
   O primeiro envio leva uns 20 a 40 minutos; os seguintes, poucos minutos.
5. `wrangler deploy` publica o Worker e os estáticos.

## Rodar localmente

```bash
SITE_URL=http://localhost:8787/ PAGINAS_ESTADUAIS=1 bash site/build.sh
bash cloudflare/separar.sh
cd cloudflare && npm ci
# copia algumas páginas para o R2 local, ex.:
npx wrangler r2 object put leis-do-brasil/lei/constituicao.html --file ../_cf/r2/lei/constituicao.html --local
npx wrangler dev        # http://localhost:8787
npm test                # testes das rotas
```

Os passos que dependem da conta do Cloudflare estão em `docs/configuracao.md`, seção 6.
