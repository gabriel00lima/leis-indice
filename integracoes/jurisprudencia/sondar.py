"""Sonda temporária das fontes (roda no Actions, onde a rede é livre)."""
import json, re, sys, urllib.request

UA = {"User-Agent": "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"}

def get(url, headers=None, data=None, limite=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read(limite) if limite else r.read()
        return r.status, r.headers.get("content-type"), b

def tentar(nome, f):
    print("=" * 20, nome)
    try: f()
    except Exception as e: print("ERRO", repr(e))

STJ = "https://dadosabertos.web.stj.jus.br/api/3/action/"
def stj():
    s, t, b = get(STJ + "package_list")
    nomes = json.loads(b)["result"]; print(len(nomes)); print(nomes)
    for n in [x for x in nomes if "espelho" in x][:1] + [x for x in nomes if "integra" in x][:1]:
        s, t, b = get(STJ + "package_show?id=" + n)
        p = json.loads(b)["result"]
        print("PACOTE", n, p.get("title"), len(p["resources"]))
        for r in p["resources"][:3] + p["resources"][-3:]:
            print("  ", r.get("name"), r.get("format"), r.get("size"), r.get("url"), r.get("last_modified"))
        res = [r for r in p["resources"] if (r.get("format") or "").lower() == "json"]
        if res:
            u = res[-1]["url"]
            s, t, b = get(u, limite=3_000_000)
            print("BAIXADO", u, t, len(b))
            txt = b.decode("utf-8", "replace")
            print(txt[:3000])
            i = txt.find("referenciasLegislativas")
            print("REF>>", txt[i:i+1500] if i >= 0 else "sem campo")
tentar("stj", stj)

def datajud():
    for u in ["https://datajud-wiki.cnj.jus.br/api-publica/acesso", "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"]:
        try:
            s, t, b = get(u)
            txt = b.decode("utf-8", "replace")
            print(u, s, len(txt))
            for m in re.finditer(r"APIKey\s+[A-Za-z0-9+/=_-]{20,}", txt): print("CHAVE", m.group(0))
            break
        except Exception as e: print(u, repr(e))
    m = re.search(r"APIKey\s+([A-Za-z0-9+/=_-]{20,})", txt)
    chave = m.group(1)
    q = json.dumps({"size": 1, "query": {"match_all": {}}}).encode()
    s, t, b = get("https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search",
                  {"Authorization": "APIKey " + chave, "Content-Type": "application/json"}, q)
    print(b.decode()[:4000])
    q = json.dumps({"size": 0, "aggs": {"a": {"terms": {"field": "assuntos.codigo", "size": 30}}}}).encode()
    s, t, b = get("https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search",
                  {"Authorization": "APIKey " + chave, "Content-Type": "application/json"}, q)
    print(b.decode()[:4000])
tentar("datajud", datajud)
