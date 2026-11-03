# Grafo de leis

Página estática (`index.html`, sem dependências nem build) que mostra a vizinhança de uma lei:
quais leis ela **cita**, **altera** ou **revoga**, e quais a citam, alteram ou revogam.

- Abrir: `grafo/?id=<id>`, onde `<id>` é o caminho da lei no repositório
  [ctresb/leis](https://github.com/ctresb/leis) sem `.md`
  (ex.: `grafo/?id=federal/leis-ordinarias/1990/lei-8078-1990-09-11`).
- Parâmetros opcionais: `direcao=ambas|saida|entrada`, `profundidade=1|2`, `dados=<url do JSON>`.
- Cada nó leva ao grafo daquela lei; o painel lateral lista as ligações com os dispositivos citados
  e tem links para `../lei.html?id=<id>` (página da lei no site) e para o arquivo-fonte no GitHub.

## Dados

A página procura `../data/links.json` (no site publicado, `data/` é copiado para a raiz do site).
Se não encontrar, usa `exemplo.json`, que tem algumas leis federais reais com ligações escritas à mão
e mostra um aviso de "dados de exemplo".

Formato esperado:

```json
{
  "versao": 1,
  "gerado_em": "2026-11-03T00:00:00Z",
  "leis": {
    "federal/leis-ordinarias/1990/lei-8078-1990-09-11": {
      "titulo": "Lei nº 8.078, de 11 de setembro de 1990",
      "tipo": "lei-ordinaria", "numero": "8078", "data": "1990-09-11",
      "ementa": "Dispõe sobre a proteção do consumidor…", "revogada": false
    }
  },
  "links": [
    { "de": "<id>", "para": "<id>", "tipo": "cita|altera|revoga", "dispositivos": ["art. 5º"] }
  ]
}
```

Uma lei citada que não está em `leis` aparece no grafo como "não indexada", com rótulo
derivado do próprio `id`. Na profundidade 2 o recorte é limitado a 150 nós.
