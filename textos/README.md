# Busca dentro do texto das leis

Índice de texto completo das leis mais consultadas, para a busca da página inicial achar o artigo certo ("prazo de arrependimento" leva ao art. 49 do CDC, "teletrabalho" aos arts. 75-A e seguintes da CLT).

- **O que entra:** as "Leis principais" de `destaques.json` e as normas vigentes das listas "mais citadas" e "mais alteradas" (hoje 23 leis e cerca de 8 mil artigos). Para mudar, edite `PRINCIPAIS` em `site/destaques.py` ou passe `--ids`.
- **Como:** `indexar.mjs` baixa cada `.md` de `raw.githubusercontent.com/ctresb/leis/main/`, divide em artigos (`artigos.mjs`, com a mesma âncora `#art-49` da página da lei) e grava um índice [Pagefind](https://pagefind.app) em `_site/pagefind/`, um registro por artigo.
- **Quando:** no build do Pages (`site/build.sh`). Nada é commitado. Leva uns 10 s e ocupa cerca de 30 MB no Pages, em milhares de pedaços pequenos: o visitante baixa só os pedaços dos termos que buscou (dezenas de KB).
- **No site:** `site/js/busca-texto.js` mostra a seção "Dentro do texto das leis" acima da lista de normas, para buscas com palavras (números continuam só na busca por título). Sem o índice, a seção não aparece e o resto da busca segue igual.
- **Se falhar** (sem Node ou sem rede), o build avisa e o site sai sem essa seção.

```bash
npm ci --prefix textos
bash site/build.sh                       # já roda o indexador
node textos/indexar.mjs --site _site     # ou só ele, depois do build
node --test textos/tests/*.test.mjs      # testes da divisão em artigos
```

Opções: `--acervo <pasta>` lê os `.md` de uma cópia local em vez da rede; `--ids a,b` troca a lista de leis.
