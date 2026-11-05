"""Extração de metadados e referências entre normas a partir dos .md do ctresb/leis.

Este módulo não faz I/O de git: recebe o texto de um arquivo e devolve
metadados e uma lista de referências "cruas" (tipo, número, ano), que só
são resolvidas para caminhos do repositório fonte na etapa de agregação
(ver construir.py). Assim, quando uma lei nova entra no repositório, as
referências antigas a ela passam a ser resolvidas sem reprocessar o texto.
"""

from __future__ import annotations

import html
import re
import unicodedata

# ---------------------------------------------------------------------------
# Tipos de norma: expressão no texto -> prefixo usado nos nomes de arquivo
# do ctresb/leis (ex.: federal/leis-ordinarias/1990/lei-8078-1990-09-11.md).
# A ordem importa: as formas mais longas vêm antes ("Lei Complementar" antes
# de "Lei", "Decreto-Lei" antes de "Decreto").
# ---------------------------------------------------------------------------
_TIPOS = [
    (r"lei\s+complementar", "lcp"),
    (r"lei\s+delegada", "ldl"),
    (r"lei\s+constitucional", "lct"),
    (r"decreto[\s-]*lei|del\b|dl\b", "del"),
    (r"decreto\s+legislativo", "dlg"),
    (r"decreto", "dec"),
    (r"emenda\s+constitucional\s+de\s+revis[ãa]o", "emr"),
    (r"emenda\s+constitucional|emenda\s+[àa]\s+constitui[çc][ãa]o|emc\b", "emc"),
    (r"medida\s+provis[óo]ria|mpv?\b", "mpv"),
    (r"lei", "lei"),
]
_INDICE = {prefixo: i for i, (_, prefixo) in reversed(list(enumerate(_TIPOS)))}
_TIPO_GRUPOS = "|".join(f"(?P<t{i}>{p})" for i, (p, _) in enumerate(_TIPOS))

_MESES = (
    "janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|"
    "outubro|novembro|dezembro"
)

# Número: "8.078", "8078", "2.200-2" (reedição de MP), "141".
_NUM = r"(?P<num>\d{1,3}(?:\.\s?\d{3})+|\d+)(?:-(?P<reed>\d{1,2})(?!\d))?"
# Ano depois do número: "/90", "/1990", ", de 1990", ", de 11 de setembro de 1990",
# ", de 21/3/1995", " de 6.8.1997".
_ANO = (
    r"(?:\s*/\s*(?P<ano1>\d{4}|\d{2})(?!\d)"
    r"|,?\s+de\s+(?:\d{1,2}[º°o]?\s+de\s+(?:" + _MESES + r")\s+de\s+"
    r"|\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*)?(?P<ano2>\d{4}|\d{2})(?!\d))?"
)

# "Lei federal nº", "Lei Complementar Estadual nº", "Lei paulista nº"...: indica a esfera
# da norma citada (importa nas leis estaduais, que citam leis dos dois tipos).
_ESFERA = (
    r"(?:\s+(?:(?P<fed>federal|nacional)|(?P<est>estadual|paulista|mineira|fluminense)))?"
)

REF_RE = re.compile(
    r"(?<![\w-])(?:" + _TIPO_GRUPOS + r")" + _ESFERA +
    r"\s*(?:n(?:\.\s*|\s*)?[º°o]\.?|n\.|nº\.?|n°)?\s*"
    + _NUM + _ANO,
    re.IGNORECASE,
)

CONSTITUICAO_RE = re.compile(
    r"\bConstitui[çc][ãa]o(?:\s+Federal|\s+da\s+Rep[úu]blica|\s+de\s+1988)\b"
    r"|\bCF(?:/88|/1988)?\b",
)
DATA_CONSTITUICAO = "1988-10-05"

# Constituição do próprio estado, citada por normas estaduais (SP e RJ: 05/10/1989,
# MG: 21/09/1989). Resolvida para a constituição da UF da norma que cita.
CONSTITUICAO_ESTADUAL_RE = re.compile(
    r"\bConstitui[çc][ãa]o\s+(?:do\s+Estado|Estadual|Paulista|Mineira|Fluminense)\b"
    r"|\bConstitui[çc][ãa]o\s+Pol[íi]tica\s+do\s+Estado\b",
    re.IGNORECASE,
)
DATA_CONSTITUICAO_ESTADUAL = "1989-09-21"

PROJETO_ANTES = re.compile(r"projetos?\s+de\s*$|\bP\.?\s*$", re.IGNORECASE)

# Sufixos do prefixo que indicam a esfera explícita da norma citada.
FEDERAL = ":federal"
ESTADUAL = ":estadual"

# Códigos citados pelo nome. (expressão, data mínima da norma que cita,
# data máxima, prefixo, número, ano). Só vale como "cita".
CODIGOS = [
    (r"C[óo]digo\s+Civil", "2003-01-11", None, "lei", "10406", 2002),
    (r"C[óo]digo\s+Civil", None, "2003-01-10", "lei", "3071", 1916),
    (r"C[óo]digo\s+de\s+Processo\s+Civil", "2016-03-18", None, "lei", "13105", 2015),
    (r"C[óo]digo\s+de\s+Processo\s+Civil", "1974-01-01", "2016-03-17", "lei", "5869", 1973),
    (r"C[óo]digo\s+Penal(?!\s+Militar)", "1942-01-01", None, "del", "2848", 1940),
    (r"C[óo]digo\s+de\s+Processo\s+Penal(?!\s+Militar)", "1942-01-01", None, "del", "3689", 1941),
    (r"Consolida[çc][ãa]o\s+das\s+Leis\s+do\s+Trabalho|\bCLT\b", "1943-05-01", None, "del", "5452", 1943),
    (r"C[óo]digo\s+de\s+Defesa\s+do\s+Consumidor", "1990-09-11", None, "lei", "8078", 1990),
    (r"C[óo]digo\s+Tribut[áa]rio\s+Nacional", "1966-10-25", None, "lei", "5172", 1966),
    (r"C[óo]digo\s+de\s+Tr[âa]nsito\s+Brasileiro", "1997-09-23", None, "lei", "9503", 1997),
    (r"C[óo]digo\s+Eleitoral", "1965-07-15", None, "lei", "4737", 1965),
    (r"Estatuto\s+da\s+Crian[çc]a\s+e\s+do\s+Adolescente", "1990-07-13", None, "lei", "8069", 1990),
]
CODIGOS = [(re.compile(p), *resto) for p, *resto in CODIGOS]

# Anotações entre parênteses deixadas pelos compiladores (Planalto/Câmara).
PAREN_RE = re.compile(r"\(([^()]{3,500})\)")
ALTERA_KW = re.compile(
    r"reda[çc][ãa]o\s+dada|acrescid|acrescentad|inclu[íi]d|renumerad|alterad|"
    r"com\s+nova\s+reda[çc][ãa]o|transformad",
    re.IGNORECASE,
)
REVOGA_KW = re.compile(r"revogad", re.IGNORECASE)
VETO_KW = re.compile(r"vetad", re.IGNORECASE)

# Notas de alteração em linha própria, sem parênteses, como nos acervos estaduais:
#   SP: "*- Inciso I com redação dada pela Lei nº 9.000, de 1995.*"
#   RJ: "\\* Nova redação dada pela Emenda Constitucional nº 51/2011"
NOTA_LINHA = re.compile(r"^(?:\*\s*-|\\\*|_\s*-)\s*")

# Parágrafos de dispositivos que revogam ou alteram outras normas.
REVOGA_PARAGRAFO = re.compile(
    r"\b(revoga(?:m)?(?:-se)?|fica(?:m)?\s+revogad[oa]s?|revogad[oa]s?\s+(?:fica|est)|"
    r"revoga\s+a|revoga\s+o)\b",
    re.IGNORECASE,
)
ALTERA_PARAGRAFO = re.compile(
    r"passa(?:m)?\s+a\s+vigorar|fica(?:m)?\s+acrescid|acrescente-se|"
    r"acrescentam-se|fica(?:m)?\s+inclu[íi]d|passa(?:m)?\s+a\s+ter\s+a\s+seguinte|"
    r"d[áa]-se\s+nova\s+reda[çc][ãa]o|ficam?\s+alterad|alteram-se|altera\s+a\s+reda",
    re.IGNORECASE,
)

ARTIGO_LINHA = re.compile(
    r"^\s*(?:\*\*)?\s*Art(?:igo)?\.?\s*(\d+(?:\.\d{3})*)\s*[º°o]?\s*(?:-\s*([A-Z]{1,2}))?",
)
ARTIGO_CITADO = re.compile(
    r"\barts?\.\s*(\d+(?:\.\d{3})*)\s*[º°o]?(?:\s*-\s*([A-Z]{1,2})\b)?",
    re.IGNORECASE,
)
# Entre o "art. N" e o nome da norma só pode haver complementos (inciso,
# parágrafo, alínea, caput...) e uma preposição final.
_LIGACAO_ARTIGO = re.compile(
    r"^[^.;:]{0,80}?\b(?:d[aoe]s?|n[ao]s?|pel[ao]s?)\s*$",
    re.IGNORECASE,
)

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def ler_frontmatter(texto: str) -> tuple[dict, str]:
    """Devolve (metadados, corpo). YAML simples, uma chave por linha."""
    m = FRONTMATTER_RE.match(texto)
    if not m:
        return {}, texto
    meta = {}
    for linha in m.group(1).splitlines():
        if ":" not in linha or linha.startswith((" ", "\t", "-")):
            continue
        chave, valor = linha.split(":", 1)
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1].replace('\\"', '"')
        if valor in ("true", "false"):
            valor = valor == "true"
        meta[chave.strip()] = valor
    return meta, texto[m.end():]


def metadados(caminho: str, texto: str) -> tuple[dict, str]:
    """Metadados normalizados de uma norma + corpo sem frontmatter."""
    meta, corpo = ler_frontmatter(texto)
    if caminho == "constituicao.md":
        meta = {
            "titulo": "Constituição da República Federativa do Brasil de 1988",
            "tipo": "Constituição",
            "numero": "",
            "data": DATA_CONSTITUICAO,
            "ementa": "",
            "revogada": False,
            "urn": "urn:lex:br:federal:constituicao:1988-10-05;1988",
        }
    elif not meta.get("titulo"):
        m = re.search(r"^#\s+(.+)$", corpo, re.MULTILINE)
        meta.setdefault("titulo", m.group(1).strip() if m else caminho)
    def texto(v) -> str:
        # Algumas ementas estaduais (SP) vêm com HTML: <a href='/norma/28593'>Lei nº…</a>.
        return html.unescape(re.sub(r"<[^>]{1,300}>", "", str(v))).strip()

    return {
        "titulo": texto(meta.get("titulo", "")),
        "tipo": str(meta.get("tipo", "")).strip(),
        "numero": str(meta.get("numero", "")).strip(),
        "data": str(meta.get("data", "")).strip(),
        "ementa": texto(meta.get("ementa", "")),
        "revogada": bool(meta.get("revogada", False)),
        "urn": str(meta.get("urn", "")).strip(),
    }, corpo


def _prefixo(m: re.Match) -> str:
    for i, (_, prefixo) in enumerate(_TIPOS):
        if m.group(f"t{i}"):
            return prefixo
    raise AssertionError("tipo não identificado")


def _ano(m: re.Match, ano_citante: int | None) -> int | None:
    bruto = m.group("ano1") or m.group("ano2")
    if not bruto:
        return None
    ano = int(bruto)
    if len(bruto) == 2:
        limite = ano_citante or 2100
        ano = 2000 + ano if 2000 + ano <= limite else 1900 + ano
    if ano < 1800 or ano > 2100:
        return None
    return ano


def _numero(m: re.Match) -> str:
    num = re.sub(r"[.\s]", "", m.group("num")).lstrip("0") or "0"
    if m.group("reed"):
        num += "-" + m.group("reed").lstrip("0")
    return num


def _artigo_citado(texto: str, inicio: int) -> str | None:
    """'art. 48' imediatamente antes de uma referência (ex.: 'art. 48 da Lei nº X')."""
    janela = texto[max(0, inicio - 120):inicio]
    ultimo = None
    for ultimo in ARTIGO_CITADO.finditer(janela):
        pass
    if not ultimo:
        return None
    if not _LIGACAO_ARTIGO.match(janela[ultimo.end():]):
        return None
    return _fmt_artigo(ultimo.group(1), ultimo.group(2))


def _fmt_artigo(num: str, letra: str | None) -> str:
    num = num.replace(".", "")
    sufixo = "º" if int(num) < 10 else ""
    return f"art. {num}{sufixo}" + (f"-{letra.upper()}" if letra else "")


def referencias_em(texto: str, ano_citante: int | None, data_citante: str, estadual: bool = False):
    """Todas as referências a normas num trecho: [(prefixo, numero, ano, inicio, fim)].

    O prefixo pode vir com sufixo de esfera (":federal", ":estadual") quando o texto diz
    "Lei federal nº…" ou "Lei estadual nº…". Os códigos citados pelo nome saem sempre como
    federais. Com estadual=True (norma de um estado), "Constituição do Estado" vira o
    prefixo "constituicao-estadual".
    """
    refs = []
    for m in REF_RE.finditer(texto):
        # "Projeto de Lei nº 908, de 2017" (comum nas leis paulistas) não é uma norma.
        if PROJETO_ANTES.search(texto, max(0, m.start() - 30), m.start()):
            continue
        prefixo = _prefixo(m)
        sufixo = FEDERAL if m.group("fed") else ESTADUAL if m.group("est") else ""
        # "Lei 1" solto sem "nº" e sem ano é ruído frequente; exige pelo menos um dos dois
        # para números curtos.
        fim_tipo = max(m.end("t" + str(_INDICE[prefixo])), m.end("fed"), m.end("est"))
        entre_tipo_e_numero = texto[fim_tipo:m.start("num")]
        tem_n = bool(re.search(r"n", entre_tipo_e_numero, re.IGNORECASE))
        ano = _ano(m, ano_citante)
        if not tem_n and ano is None and len(m.group("num")) < 3:
            continue
        refs.append((prefixo + sufixo, _numero(m), ano, m.start(), m.end()))
    if data_citante >= DATA_CONSTITUICAO:
        for m in CONSTITUICAO_RE.finditer(texto):
            refs.append(("constituicao", "", 1988, m.start(), m.end()))
    if estadual and data_citante >= DATA_CONSTITUICAO_ESTADUAL:
        for m in CONSTITUICAO_ESTADUAL_RE.finditer(texto):
            refs.append(("constituicao-estadual", "", 1989, m.start(), m.end()))
    for rx, dmin, dmax, prefixo, num, ano in CODIGOS:
        if (dmin and data_citante and data_citante < dmin) or (
            dmax and data_citante and data_citante > dmax
        ):
            continue
        for m in rx.finditer(texto):
            refs.append((prefixo + FEDERAL, num, ano, m.start(), m.end()))
    refs.sort(key=lambda r: r[3])
    # remove sobreposições (ex.: "Código Penal" dentro de outra referência)
    saida, fim = [], -1
    for r in refs:
        if r[3] >= fim:
            saida.append(r)
            fim = r[4]
    return saida


def _paragrafos(corpo: str):
    """Itera (artigo_atual, paragrafo). Parágrafo = bloco separado por linha em branco."""
    artigo = None
    adct = False
    bloco: list[str] = []

    def emitir():
        if bloco:
            return " ".join(bloco)
        return None

    for linha in corpo.splitlines():
        if linha.startswith("#") and "DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS" in linha.upper():
            adct = True
        if not linha.strip():
            p = emitir()
            if p:
                yield artigo, p
            bloco = []
            continue
        m = ARTIGO_LINHA.match(linha)
        if m:
            p = emitir()
            if p:
                yield artigo, p
            bloco = []
            artigo = _fmt_artigo(m.group(1), m.group(2))
            if adct:
                artigo = "ADCT " + artigo
        bloco.append(linha.strip())
    p = emitir()
    if p:
        yield artigo, p


def extrair_referencias(corpo: str, data_citante: str, estadual: bool = False) -> list[list]:
    """Referências de uma norma, agregadas.

    Cada item: [direcao, prefixo, numero, ano, tipo, dispositivos]
      direcao "sai":    esta norma -> norma referida   (cita/altera/revoga)
      direcao "entra":  norma referida -> esta norma   (anotação "Redação dada pela Lei X")
      dispositivos: artigos da norma DE DESTINO do link (quando conhecidos).
      prefixo pode ter sufixo de esfera (ver referencias_em).
    """
    try:
        ano_citante = int(data_citante[:4])
    except ValueError:
        ano_citante = None
    agregado: dict[tuple, set] = {}

    def add(direcao, ref, tipo, dispositivo):
        prefixo, numero, ano = ref[0], ref[1], ref[2]
        chave = (direcao, prefixo, numero, ano, tipo)
        conj = agregado.setdefault(chave, set())
        if dispositivo:
            conj.add(dispositivo)

    for artigo, par in _paragrafos(corpo):
        if par.startswith("# "):
            continue  # título do próprio arquivo
        ocupado: list[tuple[int, int]] = []
        # 0) nota em linha própria: o parágrafo inteiro é tratado como uma anotação
        nota = NOTA_LINHA.match(par)
        anotacoes = (
            [(0, len(par), par[nota.end():].strip("*_ "))] if nota and len(par) < 600
            else [(pm.start(), pm.end(), pm.group(1)) for pm in PAREN_RE.finditer(par)]
        )
        # 1) anotações entre parênteses
        for ini, fim, conteudo in anotacoes:
            refs = referencias_em(conteudo, ano_citante, data_citante, estadual)
            if not refs:
                continue
            ocupado.append((ini, fim))
            if VETO_KW.search(conteudo) and not ALTERA_KW.search(conteudo):
                continue
            # "Norma revogada pela Lei X" vale para a norma inteira, não para o artigo.
            onde = None if re.match(r"(?i)norma\b", conteudo) else artigo
            if REVOGA_KW.search(conteudo[: refs[0][3]]):
                add("entra", refs[0], "revoga", onde)
            elif ALTERA_KW.search(conteudo[: refs[0][3]]):
                add("entra", refs[0], "altera", onde)
            else:
                for r in refs:
                    add("sai", r, "cita", _artigo_citado(conteudo, r[3]))
                continue
            # demais referências dentro da anotação ("convertida na Lei nº X")
            for r in refs[1:]:
                add("sai", r, "cita", None)
        # 2) texto corrido
        refs = [
            r for r in referencias_em(par, ano_citante, data_citante, estadual)
            if not any(a <= r[3] < b for a, b in ocupado)
        ]
        if not refs:
            continue
        sem_paren = PAREN_RE.sub(" ", par)
        if REVOGA_PARAGRAFO.search(sem_paren):
            tipo = "revoga"
        elif ALTERA_PARAGRAFO.search(sem_paren):
            tipo = "altera"
        else:
            tipo = "cita"
        for r in refs:
            add("sai", r, tipo, _artigo_citado(par, r[3]))

    return sorted(
        [list(k) + [sorted(v, key=_chave_artigo)] for k, v in agregado.items()],
        key=lambda x: (x[0], x[1], x[2], x[3] or 0, x[4]),
    )


def _chave_artigo(a: str):
    m = re.search(r"(\d+)", a)
    return (a.startswith("ADCT"), int(m.group(1)) if m else 0, a)
