# leis-indice

Ferramentas sobre o acervo [ctresb/leis](https://github.com/ctresb/leis), que publica as leis do Brasil em Markdown (cerca de 1,2 milhão de normas, mais de 8 GB, atualizado todos os dias).

Este repositório **não copia** o acervo. Ele guarda só dados derivados (índices, metadados, relações entre leis) e o código que os gera. O texto integral de cada lei é buscado direto do GitHub quando alguém abre a página.

## O que o projeto faz

1. **Monitor de mudanças**: acompanha os commits do acervo e avisa, com um resumo simples, quando uma lei é criada, alterada ou revogada.
2. **Índice das leis federais**: uma GitHub Action baixa só os arquivos novos ou alterados do acervo e atualiza em `data/` os metadados (título, tipo, número, data, ementa, revogação, URN) e as ligações entre normas (cita, altera, revoga). Formato em [data/README.md](data/README.md).
3. **Site navegável**: site estático com busca, links cruzados entre leis e histórico de alterações, publicado no GitHub Pages.
4. **Grafo de leis**: visualização de quais leis citam, alteram ou revogam outras.
5. **Projetos na Câmara**: na página de cada lei, o projeto que deu origem a ela e os projetos em tramitação que a alteram, a partir dos dados abertos da Câmara ([integracoes/camara/](integracoes/camara/README.md)).

Depois da base federal (e da Constituição), a ideia é estender para leis estaduais e municipais.

## Estrutura das pastas

| Pasta | Conteúdo |
|---|---|
| `monitor/` | Código do monitor de mudanças |
| `indice/` | Código que gera o índice e as ligações em `data/` |
| `data/` | Índice gerado automaticamente (não editar à mão) |
| `site/` | Site estático publicado no GitHub Pages |
| `site/grafo/` | Página do grafo de leis |
| `integracoes/camara/` | Coleta dos projetos de lei da Câmara dos Deputados (gera `data/camara/`) |
| `docs/` | Documentação e passos de configuração |
| `.github/workflows/` | Automação: monitor, atualização do índice e deploy do site |

Cada pasta tem (ou terá) o próprio README com detalhes.

## Como o site é publicado

O workflow [`deploy-site.yml`](.github/workflows/deploy-site.yml) publica o site no GitHub Pages:

- Se existir `site/build.sh`, ele é executado a partir da raiz do repositório e deve gerar a pasta `_site/`.
- Se não existir, o conteúdo de `site/` é publicado como está, com `data/` copiada para `_site/data/`.

Ele roda em todo push na `main` que mexa em `site/` ou `data/`, uma vez por dia e manualmente pela aba Actions.

## Configuração inicial

Algumas coisas só o dono do repositório pode ativar (GitHub Pages, segredos, permissões das Actions). A lista está em [docs/configuracao.md](docs/configuracao.md).

## Licença

O código está sob a licença MIT (veja [LICENSE](LICENSE)). Os textos de leis e atos oficiais não são protegidos por direito autoral no Brasil (Lei nº 9.610/1998, art. 8º, IV); os dados derivados em `data/` vêm do acervo [ctresb/leis](https://github.com/ctresb/leis), que deve ser citado como fonte.
