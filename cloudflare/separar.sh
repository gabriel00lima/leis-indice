#!/usr/bin/env bash
# Divide o _site/ gerado por site/build.sh em duas partes para o Cloudflare:
#   _cf/assets/  arquivos estáticos do Worker (limite: 20 mil arquivos no plano grátis,
#                100 mil no pago, 25 MiB cada)
#   _cf/r2/      lei/, api/ e pagefind/, enviados ao bucket R2 por publicar_r2.sh
# Move os arquivos (não copia). Rodar da raiz: bash cloudflare/separar.sh
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
site="$raiz/_site"
saida="$raiz/_cf"
limite="${LIMITE_ASSETS:-20000}"
pastas_r2=(lei api pagefind)

test -f "$site/index.html" || { echo "::error::_site/index.html não existe; rode site/build.sh antes"; exit 1; }

rm -rf -- "${saida:?}"
mkdir -p "$saida/r2"
for p in "${pastas_r2[@]}"; do
  if [ -d "$site/$p" ]; then mv "$site/$p" "$saida/r2/$p"; fi
done
mv "$site" "$saida/assets"
# Arquivos do GitHub Pages que não fazem sentido aqui.
rm -f "$saida/assets/.nojekyll"

n_assets=$(find "$saida/assets" -type f | wc -l)
n_r2=$(find "$saida/r2" -type f | wc -l)
echo "assets: $n_assets arquivos ($(du -sh "$saida/assets" | cut -f1)); R2: $n_r2 arquivos ($(du -sh "$saida/r2" | cut -f1))"

if [ "$n_assets" -gt "$limite" ]; then
  echo "::error::$n_assets arquivos estáticos passam do limite de $limite do Workers; mova mais pastas para o R2 em cloudflare/separar.sh"
  exit 1
fi
grandes=$(find "$saida/assets" -type f -size +25M)
if [ -n "$grandes" ]; then
  echo "::error::arquivos acima de 25 MiB (limite por arquivo do Workers):"
  echo "$grandes"
  exit 1
fi
