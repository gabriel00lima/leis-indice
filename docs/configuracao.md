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
| `ANTHROPIC_API_KEY` | Resumos em linguagem simples das mudanças nas leis (monitor) | Só se quiser resumos por IA |
| `TELEGRAM_BOT_TOKEN` | Enviar os alertas do monitor pelo Telegram | Só se quiser alertas no Telegram |
| `TELEGRAM_CHAT_ID` | Chat ou canal que recebe os alertas | Junto com o token |
| `DATAJUD_API_KEY` | Chave da API pública do DataJud (jurisprudência) | Não: a coleta já lê a chave pública na wiki do CNJ; só use se ela parar de funcionar |

Sem esses segredos, o monitor e o índice continuam funcionando; só não há resumo por IA nem envio de mensagem.

### Como obter as chaves

- **Chave da Anthropic**: crie em `https://console.anthropic.com/settings/keys`. Recomenda-se definir um limite de gastos mensal no console.
- **Bot do Telegram**: no Telegram, fale com `@BotFather`, envie `/newbot` e siga as instruções; ele devolve o token.
- **Chat ID**: mande qualquer mensagem para o seu bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates`; o número em `"chat":{"id": ...}` é o chat ID. Para um canal, adicione o bot como administrador e o ID começa com `-100`.

## 4. Conferir que tudo rodou

Na aba **Actions**, confira que os workflows do monitor, do índice e do deploy aparecem e terminam em verde. O deploy também roda sozinho uma vez por dia.

---

Os nomes dos segredos do monitor acima são os definitivos; o README de cada pasta tem os detalhes.
