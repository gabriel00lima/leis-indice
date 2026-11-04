"""Conversão da resposta de /dadosabertos/legislacao/urn do Senado para o formato compacto
gravado em data/senado/normas/<id>.json.

Sem dependências fora da biblioteca padrão; testado em integracoes/senado/tests/.

A resposta do Senado (DetalheDocumento v3) traz, para cada norma:
- ``vides``: normas e decisões POSTERIORES que mexeram nesta (alterações, revogações,
  regulamentações, acórdãos do STF em ADI/ADC/ADPF...), cada uma com os dispositivos afetados;
- ``edivs``: normas ANTERIORES que esta alterou (o índice do site já cobre isso, então é ignorado);
- ``publicacoes``: publicação original, retificações e republicações no DOU.

Listas com um único elemento às vezes chegam como objeto, e listas vazias como ``""``.
"""

from __future__ import annotations

import re
import unicodedata

# ---------- utilidades ----------


def lista(x) -> list:
    """Normaliza os campos do Senado que podem vir como lista, objeto único ou string vazia."""
    if x is None or x == "" or x == {}:
        return []
    if isinstance(x, list):
        return [i for i in x if i not in (None, "")]
    return [x]


def obj(x) -> dict:
    """Campo que deveria ser objeto, mas pode vir como string vazia."""
    return x if isinstance(x, dict) else {}


def data_iso(d: str | None) -> str | None:
    """'21/05/1993' -> '1993-05-21'."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", d or "")
    return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}" if m else None


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def espacos(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---------- dispositivos ----------

RE_ART = re.compile(r"^Art\.\s*(\d+)(?:\s*-\s*([A-Za-z]))?\b")


def artigo_do_dispositivo(disp: str) -> str | None:
    """'Art. 394-A, caput, Inciso 2' -> '394-a' (mesmo formato das âncoras art-394-a do site)."""
    m = RE_ART.match(espacos(disp))
    if not m:
        return None
    return m[1] + ("-" + m[2].lower() if m[2] else "")


# ---------- classificação ----------

# Efeitos de controle de constitucionalidade (item.comentario), em ordem de gravidade.
EFEITOS_CONTROLE = [
    ("inconstitucional", re.compile(r"inconstitucional|inconstitucionalidade")),
    ("suspenso", re.compile(r"suspens")),
    ("interpretacao-conforme", re.compile(r"interpreta[cç][aã]o conforme")),
    ("constitucional", re.compile(r"constitucional|recepcionad|recep[cç][aã]o")),
]

RE_DECISAO = re.compile(
    r"(A[çc][ãa]o Direta de Inconstitucionalidade(?: por Omiss[ãa]o)?|"
    r"A[çc][ãa]o Declarat[óo]ria de Constitucionalidade|"
    r"Argui[çc][ãa]o de Descumprimento de Preceito Fundamental|"
    r"Recurso Extraordin[áa]rio|Mandado de Injun[çc][ãa]o)\s+n[º°o]\s*([\d.]+)",
    re.I,
)

SIGLAS = {
    "acao direta de inconstitucionalidade por omissao": "ADO",
    "acao direta de inconstitucionalidade": "ADI",
    "acao declaratoria de constitucionalidade": "ADC",
    "arguicao de descumprimento de preceito fundamental": "ADPF",
    "recurso extraordinario": "RE",
    "mandado de injuncao": "MI",
}


def decisao_stf(nome: str) -> dict | None:
    """'Acórdão da Ação Direta de Inconstitucionalidade nº 5.938 de 29/05/2019' -> {classe: ADI, numero: 5938}."""
    m = RE_DECISAO.search(nome or "")
    if not m:
        return None
    classe = SIGLAS.get(sem_acento(m[1]))
    if not classe:
        return None
    return {"classe": classe, "numero": m[2].replace(".", "")}


def efeito_controle(comentario: str, judicial: bool = False) -> str | None:
    """Efeito de controle de constitucionalidade descrito no comentário, ou None.
    Suspensões só contam quando vêm de decisão judicial ou são "suspensão de execução"
    (Resolução do Senado, art. 52, X, da CF); uma MP também pode suspender vigência."""
    c = sem_acento(comentario or "")
    for nome, re_ in EFEITOS_CONTROLE:
        if re_.search(c):
            if nome == "suspenso" and not (judicial or "execucao" in c):
                continue
            return nome
    return None


def acao_alteracao(comentario: str) -> str:
    """Comentário de item ('Acréscimo', 'Revogação de Parte do Texto'...) -> verbo curto do site."""
    c = sem_acento(comentario or "")
    if "vetad" in c:
        return "vetado"
    if "revigora" in c:
        return "revigorou"
    if "revoga" in c or "encerramento de vigencia" in c or "supress" in c:
        return "revogou"
    if "acrescimo" in c:
        return "acrescentou"
    if "renumera" in c:
        return "renumerou"
    if "regulament" in c:
        return "regulamentou"
    if "ressalva" in c:
        return "ressalvou"
    if "correlat" in c:
        return "correlato"
    if "alterac" in c:
        return "alterou"
    return espacos(comentario).lower() or "outro"


def tipo_vide(comentario: str) -> str:
    """'Declaração de Alteração Permanente' -> 'Alteração Permanente'."""
    return re.sub(r"^Declara[çc][ãa]o (de |da |do )?", "", espacos(comentario)) or espacos(comentario)


# ---------- normas citadas ----------

PREFIXOS = [
    ("lei complementar", "lcp"), ("decreto-lei", "del"), ("decreto lei", "del"),
    ("emenda constitucional", "emc"), ("medida provisoria", "mpv"), ("decreto legislativo", "dlg"),
    ("lei delegada", "ldl"), ("decreto", "dec"), ("lei", "lei"),
]
RE_NORMA = re.compile(r"^(.+?)\s+n[º°o]\s*([\d.]+)(?:-([A-Z]))?\s+de\s+(\d{2}/\d{2}/\d{4})", re.I)


def chave_norma(nome: str) -> tuple[str, str, str] | None:
    """'Lei nº 8.656 de 21/05/1993' -> ('lei', '8656', '1993-05-21')."""
    m = RE_NORMA.match(espacos(nome))
    if not m:
        return None
    tipo = sem_acento(m[1])
    for nome_tipo, prefixo in PREFIXOS:
        if tipo == nome_tipo:
            numero = m[2].replace(".", "") + ("-" + m[3].upper() if m[3] else "")
            return prefixo, numero, data_iso(m[4])
    return None


# ---------- conversão ----------


def documento(resposta: dict) -> dict | None:
    docs = lista(obj(obj(obj(resposta).get("DetalheDocumento")).get("documentos")).get("documento"))
    return docs[0] if docs else None


def converter(resposta: dict, resolver=None) -> dict | None:
    """Resposta crua do Senado -> registro compacto. ``resolver((prefixo, numero, data))`` devolve o id
    da norma no índice do site (ou None). Devolve None se a URN não foi encontrada."""
    doc = documento(resposta)
    if not doc:
        return None
    ident = obj(doc.get("identificacao"))
    resolver = resolver or (lambda _k: None)

    alteracoes, controle = [], []
    for v in lista(obj(doc.get("vides")).get("vide")):
        nome = espacos(v.get("nomeNormaPosterior"))
        data = data_iso(v.get("datAssinatura"))
        itens = [{"dispositivo": espacos(i.get("dispositivo")), "comentario": espacos(i.get("comentario"))}
                 for i in lista(obj(v.get("itens")).get("item"))]
        decisao = decisao_stf(nome)
        tipo = tipo_vide(v.get("comentario"))
        efeitos = [(i, efeito_controle(i["comentario"], bool(decisao))) for i in itens]

        # Decisão judicial ou item com efeito de controle -> controle de constitucionalidade.
        if decisao or any(e for _, e in efeitos) or efeito_controle(tipo):
            efeito_geral = efeito_controle(tipo)
            disps = []
            for i, e in efeitos:
                disps.append({"dispositivo": i["dispositivo"], "art": artigo_do_dispositivo(i["dispositivo"]),
                              "efeito": e or efeito_geral or "outro", "texto": i["comentario"]})
            registro = {"data": data, "nome": nome, "tipo": tipo, "dispositivos": disps}
            if decisao:
                registro["decisao"] = decisao
            elif not disps and efeito_geral:
                registro["efeito"] = efeito_geral
            controle.append(registro)
            # Uma lei (não um acórdão) pode alterar uns dispositivos e suspender outros:
            # os itens comuns continuam no histórico de alterações.
            itens = [i for i, e in efeitos if not e] if not decisao else []
            if not itens:
                continue

        k = chave_norma(nome)
        registro = {"data": data, "nome": nome, "tipo": tipo,
                    "dispositivos": [{"dispositivo": i["dispositivo"], "art": artigo_do_dispositivo(i["dispositivo"]),
                                      "acao": acao_alteracao(i["comentario"])} for i in itens]}
        id_ = resolver(k) if k else None
        if id_:
            registro["id"] = id_
        alteracoes.append(registro)

    ordem = lambda r: (r.get("data") or "9999", r.get("nome") or "")
    alteracoes.sort(key=ordem)
    controle.sort(key=ordem)

    publicacoes = [{"tipo": espacos(p.get("tipo")), "data": data_iso(p.get("data")), "descricao": espacos(p.get("dispositivo"))}
                   for p in lista(obj(doc.get("publicacoes")).get("publicacao"))]

    return {
        "codigo": str(doc.get("id") or ""),
        "nome": espacos(ident.get("normaNome")),
        "apelidos": [a for a in (espacos(x) for x in (ident.get("apelido") or "").split(" , ")[1:]) if a],
        "publicacoes": publicacoes,
        "alteracoes": alteracoes,
        "controle": controle,
    }


def resumo(registro: dict) -> dict:
    """Contagens usadas no estado (data/senado/estado.json) e no selo da página."""
    arts_adi = sorted({d["art"] for c in registro["controle"] for d in c["dispositivos"]
                       if d["art"] and d["efeito"] in ("inconstitucional", "suspenso")})
    return {
        "alteracoes": len(registro["alteracoes"]),
        "controle": len(registro["controle"]),
        "inconstitucionais": sum(1 for c in registro["controle"] for d in c["dispositivos"]
                                 if d["efeito"] in ("inconstitucional", "suspenso")),
        "artigos_afetados": arts_adi,
    }
