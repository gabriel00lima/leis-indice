"""Sonda temporária das fontes (roda no Actions, onde a rede é livre)."""
import json, re, urllib.request, html
from collections import Counter

UA = {"User-Agent": "leis-indice/1.0 (+https://github.com/gabriel00lima/leis-indice)"}
def get(url, headers=None, data=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()
def tentar(nome, f):
    print("=" * 20, nome, flush=True)
    try: f()
    except Exception as e: print("ERRO", repr(e))

STJ = "https://dadosabertos.web.stj.jus.br/api/3/action/"
def stj():
    cab = Counter(); tokens = Counter(); exemplos = {}
    alvo = re.compile(r"(CFB|DEL:002848|DEL:005452|LEI:008078|LEI:010406|LEI:013105)")
    for pac in ["espelhos-de-acordaos-quinta-turma", "espelhos-de-acordaos-primeira-turma", "espelhos-de-acordaos-segunda-secao"]:
        p = json.loads(get(STJ + "package_show?id=" + pac))["result"]
        res = [r for r in p["resources"] if r["format"].lower() == "json"]
        print(pac, len(res), "ultimo", res[-1]["name"], res[-1].get("last_modified"))
        for r in res[-3:]:
            d = json.loads(get(r["url"]))
            for x in d:
                for ref in x.get("referenciasLegislativas") or []:
                    l0 = ref.split("\n")[0]
                    m = alvo.search(l0)
                    if m:
                        cab[l0] += 1
                        for t in re.findall(r"\b([A-Z]{2,6}):([0-9A-Z*]+)", "\n".join(ref.split("\n")[2:] if "*****" in ref else ref.split("\n")[1:])):
                            tokens[t[0]] += 1
                        if len(exemplos.get(m.group(1), [])) < 3:
                            exemplos.setdefault(m.group(1), []).append(ref)
            print(" ", r["name"], len(d), "tamanho", len(json.dumps(d)), "dataDecisao ex", d[0].get("dataDecisao"), "id", d[0].get("id"))
    print(cab.most_common(20)); print(tokens.most_common(30))
    for k, v in exemplos.items():
        for e in v: print(k, "|", e.replace("\n", " ⏎ "))
    # artigos com letra
    print("ART com letra:", [t for t in re.findall(r"ART:\S+", json.dumps(exemplos)) if not t.rstrip('",').strip("ART:").isdigit()][:10])
tentar("stj", stj)

def datajud():
    txt = get("https://datajud-wiki.cnj.jus.br/api-publica/acesso").decode("utf-8", "replace")
    plano = html.unescape(re.sub(r"<[^>]+>", " ", txt))
    chave = re.search(r"APIKey\s+([A-Za-z0-9+/]{20,}={0,2})", plano.replace("[Chave Pública]", "")).group(1)
    print("CHAVE", chave)
    H = {"Authorization": "APIKey " + chave, "Content-Type": "application/json"}
    def q(corpo, n=3000):
        try: print(get("https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search", H, json.dumps(corpo).encode()).decode()[:n])
        except urllib.error.HTTPError as e: print("HTTP", e.code, e.read()[:500])
    q({"size": 1, "query": {"match_all": {}}}, 4000)
    q({"size": 0, "track_total_hits": True, "aggs": {"a": {"terms": {"field": "assuntos.codigo", "size": 60}}}}, 6000)
    q({"size": 0, "track_total_hits": True, "aggs": {"a": {"terms": {"field": "assuntos.nome.keyword", "size": 30}}}}, 4000)
    q({"size": 0, "track_total_hits": True, "query": {"terms": {"assuntos.codigo": [1156, 899, 864, 287, 8826]}}}, 600)
tentar("datajud", datajud)
