# O que configurar manualmente

Estes passos só o dono do repositório consegue fazer, pelas configurações do GitHub. Faça na ordem; cada um leva um ou dois minutos.

## 1. Ativar o GitHub Pages

1. Abra **Settings → Pages** (`https://github.com/gabriel00lima/leis-indice/settings/pages`).
2. Em **Build and deployment → Source**, escolha **GitHub Actions**.
3. Vá em **Actions → Deploy do site → Run workflow** para a primeira publicação.

O site fica em `https://gabriel00lima.github.io/leis-indice/`.

> Em repositório privado, o Pages exige plano pago (GitHub Pro ou superior). Em repositório público é gratuito.

## 2. Permissões das Actions

O índice e o monitor fazem commits automáticos em `data/`, então as Actions precisam poder escrever:

1. Abra **Settings → Actions → General** (`https://github.com/gabriel00lima/leis-indice/settings/actions`).
2. Em **Workflow permissions**, marque **Read and write permissions**.
3. Salve.

Se a `main` tiver regra de proteção que exija PR, as Actions não conseguirão commitar direto. Nesse caso, permita o bot `github-actions` como exceção ou deixe a `main` sem essa regra.

## 3. Segredos (Settings → Secrets and variables → Actions)

Abra `https://github.com/gabriel00lima/leis-indice/settings/secrets/actions` e clique em **New repository secret** para cada um que for usar:

| Segredo | Para quê | Obrigatório? |
|---|---|---|
| `ANTHROPIC_API_KEY` | Resumos em linguagem simples das mudanças nas leis (monitor) e rascunhos da "Lei explicada" | Só se quiser resumos por IA |
| `TELEGRAM_BOT_TOKEN` | Enviar os alertas do monitor pelo Telegram | Só se quiser alertas no Telegram |
| `TELEGRAM_CHAT_ID` | Chat ou canal que recebe os alertas | Junto com o token |
| `DATAJUD_API_KEY` | Chave da API pública do DataJud (jurisprudência) | Não: a coleta já lê a chave pública na wiki do CNJ; só use se ela parar de funcionar |

Sem esses segredos, o monitor e o índice continuam funcionando; só não há resumo por IA nem envio de mensagem.

### Como obter as chaves

- **Chave da Anthropic**: crie em `https://console.anthropic.com/settings/keys`. Recomenda-se definir um limite de gastos mensal no console.
- **Bot do Telegram**: no Telegram, fale com `@BotFather`, envie `/newbot` e siga as instruções; ele devolve o token.
- **Chat ID**: mande qualquer mensagem para o seu bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates`; o número em `"chat":{"id": ...}` é o chat ID. Para um canal, adicione o bot como administrador e o ID começa com `-100`.

### Rascunhos da "Lei explicada" com IA (opcional)

Os resumos da "Lei explicada" já estão escritos no repositório e não dependem de IA. Para pedir um rascunho novo pela aba **Actions → Lei explicada → Run workflow**, além do segredo `ANTHROPIC_API_KEY`, marque em **Settings → Actions → General** a opção **Allow GitHub Actions to create and approve pull requests**: o workflow abre um PR com o rascunho para revisão.

## 4. Google Search Console (opcional, para aparecer mais rápido no Google)

O site já gera `sitemap.xml`, mas num endereço `github.io/leis-indice` o Google não lê o `robots.txt` do projeto, então o sitemap precisa ser enviado à mão uma vez:

1. Abra `https://search.google.com/search-console` e adicione a propriedade do tipo **Prefixo do URL** com `https://gabriel00lima.github.io/leis-indice/`.
2. Na verificação, escolha **Tag HTML**, copie só o valor de `content="..."` e me passe (ou coloque como `<meta name="google-site-verification" content="...">` no `<head>` de `site/index.html`). Depois do deploy, clique em **Verificar**.
3. Em **Sitemaps**, envie `sitemap.xml`.

Sem isso o Google acaba achando as páginas pelos links, só que mais devagar. As prévias no WhatsApp não dependem deste passo.

## 5. Conferir que tudo rodou

Na aba **Actions**, confira que os workflows do monitor, do índice e do deploy aparecem e terminam em verde. O deploy também roda sozinho uma vez por dia.

## 6. Mudar o site para o Cloudflare (sai do limite de 1 GB do GitHub Pages)

O site já passa de 1 GB, o limite do GitHub Pages, e por isso as leis estaduais não têm página própria. O deploy no Cloudflare já está pronto no repositório (ver `cloudflare/README.md`) e começa a rodar sozinho assim que os dois segredos abaixo existirem. Hoje é grátis; se o tráfego crescer muito, o plano pago custa US$ 5/mês.

1. **Criar a conta**: `https://dash.cloudflare.com/sign-up` (plano Free).
2. **Ativar o Workers**: no painel, abra **Workers & Pages** uma vez e aceite o subdomínio `workers.dev` sugerido (ex.: `gabriel00lima.workers.dev`).
3. **Ativar o R2**: no painel, abra **R2 Object Storage** e clique em **Purchase R2 Plan** / **Enable R2**. O Cloudflare pede um cartão mesmo no plano grátis, mas só cobra acima de 10 GB (o site usa ~2 GB).
4. **Criar o token**: abra `https://dash.cloudflare.com/profile/api-tokens` → **Create Token** → modelo **Edit Cloudflare Workers** → **Use template**. Em **Permissions**, clique em **+ Add more** e adicione **Account · Workers R2 Storage · Edit**. Em **Account Resources**, escolha a sua conta. **Continue to summary** → **Create Token** e copie o token (ele só aparece uma vez).
5. **Copiar o Account ID**: na página inicial do painel, menu **⋯** ao lado do nome da conta → **Copy account ID** (ou na coluna direita de **Workers & Pages**).
6. **Cadastrar os segredos** em `https://github.com/gabriel00lima/leis-indice/settings/secrets/actions`:
   - `CLOUDFLARE_API_TOKEN` = o token do passo 4
   - `CLOUDFLARE_ACCOUNT_ID` = o ID do passo 5
7. **Primeiro deploy**: **Actions → Deploy do site → Run workflow**. O job `cloudflare` leva uns 30 a 40 minutos na primeira vez (envia ~270 mil arquivos); depois, poucos minutos. O endereço aparece no log do passo "Endereço público do site": `https://leis-do-brasil.<seu-subdominio>.workers.dev/`.

Se o passo "Enviar … ao R2" falhar com erro de acesso (403 / InvalidAccessKeyId), crie um token próprio do R2 em **R2 → Manage R2 API Tokens → Create API token** (permissão **Object Read & Write**) e cadastre também os segredos `R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY` com os valores que ele mostrar.

### Domínio próprio (opcional, recomendado)

1. Registre o domínio: `.com.br` em `https://registro.br` (cerca de R$ 40/ano) ou `.com` no próprio Cloudflare (**Domain Registration → Register Domains**, a preço de custo).
2. Se registrou fora do Cloudflare: no painel, **Add a domain** → plano Free, e troque os servidores DNS no registro.br para os dois que o Cloudflare indicar (em **registro.br → Domínio → DNS → Alterar servidores DNS**). A troca leva de minutos a algumas horas.
3. Em **Workers & Pages → leis-do-brasil → Settings → Domains & Routes → Add → Custom domain**, digite o domínio (ex.: `leisdobrasil.com.br`).
4. Em `https://github.com/gabriel00lima/leis-indice/settings/variables/actions`, aba **Variables** → **New repository variable**: `SITE_URL` = `https://leisdobrasil.com.br/` (com o seu domínio). Rode o deploy de novo para os links canônicos, sitemaps e a API passarem a usar o domínio.
5. Refaça a seção 4 (Google Search Console) com o domínio novo, agora do tipo **Domínio** (verificação por DNS no Cloudflare).

Depois que o site novo estiver no ar, me avise: troco o GitHub Pages por um redirecionamento para o endereço novo, para quem tiver o link antigo.

---

Os nomes dos segredos do monitor acima são os definitivos; o README de cada pasta tem os detalhes.
