"""Leitura das ementas e da situação das proposições da Câmara.

Funções puras, sem I/O, para poderem ser testadas sem rede:

- `normas_alteradas(ementa, data)`: normas que a proposição altera ou revoga,
  como referências cruas (prefixo, número, ano), no formato do extrator do índice.
- `em_tramitacao(situacao)`: se a situação atual indica que o projeto ainda tramita.
- `norma_gerada(urn, textos)`: a norma que a proposição virou, quando já virou lei.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "indice"))
import extrator  # noqa: E402

# "Altera as Leis nºs 8.078, de 1990, e 9.099, de 1995" -> uma referência por número.
_PLURAL = re.compile(
    r"(?<![\w-])(?P<tipo>Leis\s+Complementares|Leis|Decretos?[\s-]+Leis|Decretos-leis|"
    r"Medidas\s+Provis[óo]rias|Emendas\s+Constitucionais)"
    r"\s*(?:n(?:[º°o]s?|os)\.?|n\.)?\s*",
    re.IGNORECASE,
)
_SINGULAR = {
    "leis complementares": "Lei Complementar",
    "leis": "Lei",
    "medidas provisorias": "Medida Provisória",
    "medidas provisórias": "Medida Provisória",
    "emendas constitucionais": "Emenda Constitucional",
}
_ITEM = re.compile(
    r"(?:\s*,\s*(?:e\s+)?|\s+e\s+)?(?:\s*n[º°o]\.?\s*)?" + extrator._NUM + extrator._ANO,
    re.IGNORECASE,
)

# Verbos que indicam alteração da norma citada logo depois.
_VERBO = re.compile(
    r"\b(?:altera(?:m|r)?|acrescenta(?:m|r)?|acresce(?:m|r)?|revoga(?:m|r)?|modifica(?:m|r)?|"
    r"insere(?:m)?|inserir|inclui(?:r)?|incluem|d[áa]\s+nova\s+reda[çc][ãa]o|"
    r"suprime(?:m)?|renumera(?:m)?|reda[çc][ãa]o\s+(?:a|ao|aos|às)|nova\s+reda[çc][ãa]o)\b",
    re.IGNORECASE,
)
# Expressões que mudam de assunto: o que vem depois só é citado, não alterado.
_QUEBRA = re.compile(
    r"\b(?:para|a\s+fim\s+de|com\s+o\s+objetivo|nos\s+termos|conforme|de\s+que\s+trata[mn]?|"
    r"previst[oa]s?|institu[íi]d[oa]s?|referid[oa]s?|regulamenta(?:d[oa])?|dispõe|disp[õo]e|"
    r"estabelec|cria|institui|define|determina|autoriza|sobre|segundo|com\s+base)\b"
    r"|[;:]|\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]",
    re.IGNORECASE,
)
_REVOGA = re.compile(r"\brevoga", re.IGNORECASE)


def expandir_plurais(texto: str) -> str:
    saida, pos = [], 0
    for m in _PLURAL.finditer(texto):
        if m.start() < pos:
            continue
        chave = extrator._sem_acento(re.sub(r"\s+", " ", m.group("tipo").lower()))
        singular = _SINGULAR.get(chave) or ("Decreto-Lei" if chave.startswith("decreto") else "Lei")
        p, itens = m.end(), []
        while True:
            it = _ITEM.match(texto, p)
            if not it or it.end() == p:
                break
            itens.append(f"{singular} nº {it.group(0).strip(' ,').removeprefix('e ').strip()}")
            p = it.end()
        if not itens:
            continue
        saida.append(texto[pos:m.start()])
        saida.append(", ".join(itens))
        pos = p
    saida.append(texto[pos:])
    return "".join(saida)


def normas_alteradas(ementa: str, data: str) -> list[tuple[str, str, int | None, str]]:
    """[(prefixo, numero, ano, relacao)] com relacao em {"altera", "revoga"}.

    Uma norma conta como alterada quando um verbo de alteração aparece antes
    dela no mesmo trecho, sem uma expressão de mudança de assunto no meio
    (ex.: "Altera a Lei X para dispor sobre... nos termos da Lei Y": só X).
    """
    if not ementa:
        return []
    texto = expandir_plurais(re.sub(r"\s+", " ", ementa))
    ano = int(data[:4]) if data[:4].isdigit() else None
    saida, vistos = [], set()
    for prefixo, numero, ano_ref, ini, _fim in extrator.referencias_em(texto, ano, data or "9999"):
        prefixo = prefixo.split(":")[0]  # "del:federal" (código citado pelo nome) -> "del"
        antes = texto[:ini]
        verbos = list(_VERBO.finditer(antes))
        if not verbos:
            continue
        ultimo = verbos[-1]
        if _QUEBRA.search(antes, ultimo.end()):
            continue
        relacao = "revoga" if _REVOGA.match(ultimo.group(0)) else "altera"
        chave = (prefixo, numero, ano_ref)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append((prefixo, numero, ano_ref, relacao))
    return saida


# Situações da Câmara que encerram a tramitação.
_ENCERRADA = re.compile(
    r"arquivad|arquivo|transformad[oa]\s+em\s+norma|norma\s+jur[íi]dica|retirad|vetad|"
    r"perdeu\s+a\s+efic|efic[áa]cia\s+encerrada|prejudicad|devolvid|rejeitad|"
    r"tramita[çc][ãa]o\s+(?:encerrada|finalizada)|cancelad|sem\s+efeito|promulgad|"
    r"transformad[oa]\s+em\s+nova\s+proposi|declarad[oa]\s+(?:inconstit|prejud)",
    re.IGNORECASE,
)


def em_tramitacao(situacao: str | None) -> bool:
    if not situacao or not situacao.strip():
        return False
    return not _ENCERRADA.search(situacao)


# urn:lex:br:federal:lei:2019-09-20;13874  ->  ("lei", "13874", 2019)
_URN = re.compile(r"urn:lex:br:federal:([a-z.]+):(\d{4})-\d{2}-\d{2};(\d+)", re.IGNORECASE)
_URN_TIPOS = {
    "lei": "lei",
    "lei.complementar": "lcp",
    "emenda.constitucional": "emc",
    "decreto.lei": "del",
    "medida.provisoria": "mpv",
}
_TRANSFORMADO = re.compile(
    r"(Lei\s+Ordin[áa]ria|Lei\s+Complementar|Emenda\s+Constitucional|Lei)\s*"
    r"(?:n[º°o]\.?\s*)?(\d{1,3}(?:\.\d{3})+|\d+)\s*/\s*(\d{4})",
    re.IGNORECASE,
)


def chave_urn(urn: str | None):
    m = _URN.search(urn or "")
    if not m:
        return None
    prefixo = _URN_TIPOS.get(m.group(1).lower())
    if not prefixo:
        return None
    return prefixo, m.group(3).lstrip("0") or "0", int(m.group(2))


def norma_gerada(urn: str | None, *textos: str | None):
    """(prefixo, numero, ano) da norma que a proposição virou, ou None."""
    chave = chave_urn(urn)
    if chave:
        return chave
    for t in textos:
        if not t or not re.search(r"transformad", t, re.IGNORECASE):
            continue
        m = _TRANSFORMADO.search(t)
        if m:
            tipo = m.group(1).lower()
            prefixo = "lcp" if "complementar" in tipo else "emc" if "emenda" in tipo else "lei"
            return prefixo, m.group(2).replace(".", "").lstrip("0") or "0", int(m.group(3))
    return None
