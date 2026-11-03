#!/usr/bin/env bash
# Gera _site/ (na raiz do repo) para publicação no GitHub Pages.
# Copia site/ e, se existir, data/ para _site/data/. Sem dependências.
# Rodar a partir da raiz do repositório: bash site/build.sh
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
saida="$raiz/_site"

rm -rf -- "${saida:?}"
mkdir -p "$saida"
cp -R "$raiz/site/." "$saida/"
rm -f "$saida/build.sh" "$saida/README.md"

if [ -d "$raiz/data" ]; then
  mkdir -p "$saida/data"
  cp -R "$raiz/data/." "$saida/data/"
fi

touch "$saida/.nojekyll"
echo "Site gerado em $saida"
