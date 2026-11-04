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
rm -f "$saida/build.sh" "$saida/README.md" "$saida/destaques.py" "$saida/paginas.py" "$saida/feeds.py"

if [ -d "$raiz/data" ]; then
  mkdir -p "$saida/data"
  cp -R "$raiz/data/." "$saida/data/"
fi

# Estatísticas e listas da página inicial, recalculadas a partir de data/.
if [ -f "$raiz/data/index.json" ] && command -v python3 >/dev/null; then
  python3 "$raiz/site/destaques.py" --data "$raiz/data" --saida "$saida/destaques.json"
fi

# Uma página HTML por norma (lei/<id>.html) com título, ementa e prévia para
# buscadores e WhatsApp, mais sitemap.xml, robots.txt e 404.html.
if [ -f "$raiz/data/index.json" ] && command -v python3 >/dev/null; then
  python3 "$raiz/site/paginas.py" --site "$saida"
fi

# Um feed RSS por norma (feed/<id>.xml) e o geral (feed/novidades.xml): é o que
# o botão "Seguir" da página da lei entrega. Ver site/feeds.py.
if [ -f "$raiz/data/index.json" ] && command -v python3 >/dev/null; then
  python3 "$raiz/site/feeds.py" --site "$saida" --monitor "$raiz/monitor/novidades.json" \
    || echo "::warning::feeds RSS não gerados (site/feeds.py falhou)"
fi

# API pública em JSON estático (_site/api/v1/), derivada de data/. Ver api/README.md.
# Se falhar, o site sai mesmo assim, sem a API, e o log do Action mostra o aviso.
if [ -f "$raiz/data/index.json" ] && [ -f "$raiz/api/gerar.py" ] && command -v python3 >/dev/null; then
  python3 "$raiz/api/gerar.py" --data "$raiz/data" --saida "$saida/api" \
    || echo "::warning::API não gerada (api/gerar.py falhou)"
fi

touch "$saida/.nojekyll"
echo "Site gerado em $saida"
