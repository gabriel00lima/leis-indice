#!/usr/bin/env bash
# Envia _cf/r2/ (lei/, api/, pagefind/) ao bucket R2, só o que mudou.
# Usa rclone pela API S3 do R2. Credenciais, em ordem de preferência:
#   R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY (token S3 do R2), ou
#   CLOUDFLARE_API_TOKEN: o R2 aceita o id do token como Access Key ID e o
#   SHA-256 do token como Secret Access Key (o token precisa da permissão de R2).
# Sempre precisa de CLOUDFLARE_ACCOUNT_ID. Bucket: R2_BUCKET (padrão leis-do-brasil).
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
origem="$raiz/_cf/r2"
bucket="${R2_BUCKET:-leis-do-brasil}"
: "${CLOUDFLARE_ACCOUNT_ID:?defina CLOUDFLARE_ACCOUNT_ID}"
command -v rclone >/dev/null || { echo "::error::rclone não instalado"; exit 1; }

if [ -z "${R2_ACCESS_KEY_ID:-}" ] || [ -z "${R2_SECRET_ACCESS_KEY:-}" ]; then
  : "${CLOUDFLARE_API_TOKEN:?defina CLOUDFLARE_API_TOKEN ou R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY}"
  token_id=""
  for url in "https://api.cloudflare.com/client/v4/user/tokens/verify" \
             "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/tokens/verify"; do
    token_id=$(curl -fsS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "$url" 2>/dev/null \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("result") or {}).get("id",""))' || true)
    [ -n "$token_id" ] && break
  done
  [ -n "$token_id" ] || { echo "::error::não consegui ler o id do CLOUDFLARE_API_TOKEN (token inválido?)"; exit 1; }
  R2_ACCESS_KEY_ID="$token_id"
  R2_SECRET_ACCESS_KEY=$(printf '%s' "$CLOUDFLARE_API_TOKEN" | sha256sum | cut -d' ' -f1)
fi

export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

# Cada pasta é sincronizada só se o build a gerou: se a API falhar no build,
# a versão anterior dela continua no ar em vez de ser apagada.
# --checksum compara o MD5 local com o ETag do R2: só sobe o que mudou.
# --max-delete trava apagões por engano (ex.: índice vazio).
for pasta in lei api pagefind; do
  if [ -d "$origem/$pasta" ] && [ -n "$(find "$origem/$pasta" -type f -print -quit)" ]; then
    echo "R2: sincronizando $pasta/"
    rclone sync "$origem/$pasta" "r2:$bucket/$pasta" \
      --checksum --fast-list --transfers 64 --checkers 64 \
      --max-delete "${R2_MAX_DELETE:-20000}" --stats 30s --stats-one-line
  else
    echo "R2: $pasta/ não foi gerada neste build; mantendo a versão que está no bucket"
  fi
done
