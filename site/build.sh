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
rm -f "$saida/build.sh" "$saida/README.md" "$saida/destaques.py"

if [ -d "$raiz/data" ]; then
  mkdir -p "$saida/data"
  cp -R "$raiz/data/." "$saida/data/"
fi

# Estatísticas e listas da página inicial, recalculadas a partir de data/.
if [ -f "$raiz/data/index.json" ] && command -v python3 >/dev/null; then
  python3 "$raiz/site/destaques.py" --data "$raiz/data" --saida "$saida/destaques.json"
fi

touch "$saida/.nojekyll"
echo "Site gerado em $saida"
