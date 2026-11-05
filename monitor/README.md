# Monitor de mudanças

Todo dia às 6h, um GitHub Action confere se alguma lei de
[`acompanhar.txt`](acompanhar.txt) mudou no acervo
[ctresb/leis](https://github.com/ctresb/leis). Quando muda, ele abre uma
**issue** neste repositório com o resumo do que mudou, links e o diff. O GitHub
avisa você por e-mail e pelo app.

Nada é baixado em massa: para cada lei acompanhada, o monitor faz uma consulta à
API do GitHub e, só se houver mudança, baixa as duas versões daquele arquivo.

## Como usar

- **Acompanhar outra lei:** adicione o caminho dela em `acompanhar.txt`. Na primeira
  execução ela só é registrada; os avisos começam na mudança seguinte.
- **Rodar agora:** aba *Actions* → *Monitor de mudanças* → *Run workflow*.
- **Resumo em linguagem simples (opcional):** crie o segredo `ANTHROPIC_API_KEY` em
  *Settings → Secrets and variables → Actions*. Sem ele, o resumo lista os artigos
  incluídos, alterados ou removidos e os campos do cabeçalho que mudaram.
- **Aviso no Telegram (opcional):** crie os segredos `TELEGRAM_BOT_TOKEN` e
  `TELEGRAM_CHAT_ID`.

## Arquivos

- `monitor.py`: o monitor.
- `acompanhar.txt`: a lista de leis.
- `estado.json`: último commit visto de cada lei (gerado automaticamente).
