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

Sem esses segredos, o monitor e o índice continuam funcionando; só não há resumo por IA nem envio de mensagem.

### Como obter as chaves

- **Chave da Anthropic**: crie em `https://console.anthropic.com/settings/keys`. Recomenda-se definir um limite de gastos mensal no console.
- **Bot do Telegram**: no Telegram, fale com `@BotFather`, envie `/newbot` e siga as instruções; ele devolve o token.
- **Chat ID**: mande qualquer mensagem para o seu bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates`; o número em `"chat":{"id": ...}` é o chat ID. Para um canal, adicione o bot como administrador e o ID começa com `-100`.

## 4. Diário Oficial: runner próprio (só se o site da Imprensa Nacional bloquear o GitHub)

A coleta do DOU (`.github/workflows/dou.yml`) baixa os ZIPs mensais de `in.gov.br`. O site da Imprensa Nacional
responde **403 (acesso negado)** aos servidores do GitHub, então a coleta precisa rodar numa máquina no Brasil,
como o seu computador. Uma vez por mês basta; se o computador estiver desligado, a execução do dia seguinte pega.

1. Abra **Settings → Actions → Runners → New self-hosted runner** (`https://github.com/gabriel00lima/leis-indice/settings/actions/runners/new`).
2. Escolha o sistema (macOS, Linux ou Windows) e rode os comandos que a página mostra. Quando o `config` perguntar
   os rótulos (*labels*), digite `dou`.
3. Deixe o runner rodando (`./run.sh`, ou instale como serviço com `./svc.sh install && ./svc.sh start`).
   A máquina precisa de `git`, `bash` e `jq` (no Windows, use o Git Bash).
4. Em **Settings → Secrets and variables → Actions → Variables** (`https://github.com/gabriel00lima/leis-indice/settings/variables/actions`),
   crie a variável `DOU_RUNNER` com o valor `dou`.
5. Rode **Actions → Diário Oficial da União → Run workflow**. A primeira vez baixa até 8 meses (alguns GB); as
   seguintes só baixam o mês novo.

Só o workflow do DOU usa esse runner; os outros continuam nos servidores do GitHub. Para desfazer, apague a variável.

## 5. Conferir que tudo rodou

Na aba **Actions**, confira que os workflows do monitor, do índice e do deploy aparecem e terminam em verde. O deploy também roda sozinho uma vez por dia.

---

Os nomes dos segredos do monitor acima são os definitivos; o README de cada pasta tem os detalhes.
