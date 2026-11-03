"""Sonda temporária das fontes (roda no Actions, onde a rede é livre)."""
import json, re, sys, urllib.request, html

UA = {"User-Agent": "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"}

def get(url, headers=None, data=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def tentar(nome, f):
    print("=" * 20, nome)
    try: f()
    except Exception as e: print("ERRO", repr(e))

STJ = "https://dadosabertos.web.stj.jus.br/api/3/action/"
def stj():
    p = json.loads(get(STJ + "package_show?id=espelhos-de-acordaos-terceira-turma"))["result"]
    for r in p["resources"]:
        if r["format"].lower() == "csv": print(get(r["url"]).decode("utf-8", "replace"))
    r = [r for r in p["resources"] if r["format"].lower() == "json"][-2]
    d = json.loads(get(r["url"]))
    print("REGISTROS", len(d), "CHAVES", list(d[0].keys()))
    com = [x for x in d if x.get("referenciasLegislativas")]
    print("COM REF", len(com))
    for x in com[:4]:
        print(json.dumps({k: (v[:300] if isinstance(v, str) else v) for k, v in x.items()}, ensure_ascii=False, indent=1)[:5000])
    # amostra de prefixos das referências
    from collections import Counter
    c = Counter()
    for x in d:
        for ref in x.get("referenciasLegislativas") or []:
            c[ref.split("\n")[0][:40]] += 1
    print(c.most_common(40))
    print("RECURSOS", [(r["name"], r["format"]) for r in p["resources"]][:80])
tentar("stj", stj)

def datajud():
    txt = get("https://datajud-wiki.cnj.jus.br/api-publica/acesso").decode("utf-8", "replace")
    for m in re.finditer(r"(?i)apikey|authorization", txt):
        print("...", html.unescape(re.sub(r"<[^>]+>", " ", txt[max(0, m.start()-300): m.end()+300])).replace("\n", " "))
    plano = html.unescape(re.sub(r"<[^>]+>", "", txt))
    m = re.search(r"APIKey\s+([A-Za-z0-9+/=_-]{20,})", plano)
    if not m: print("SEM CHAVE"); return
    chave = m.group(1); print("CHAVE", chave)
    H = {"Authorization": "APIKey " + chave, "Content-Type": "application/json"}
    for corpo in [{"size": 1, "query": {"match_all": {}}},
                  {"size": 0, "track_total_hits": True, "aggs": {"a": {"terms": {"field": "assuntos.codigo", "size": 15}}}},
                  {"size": 0, "track_total_hits": True, "query": {"match": {"assuntos.codigo": 1156}}}]:
        try:
            print(get("https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search", H, json.dumps(corpo).encode()).decode()[:3500])
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, e.read()[:500])
tentar("datajud", datajud)
