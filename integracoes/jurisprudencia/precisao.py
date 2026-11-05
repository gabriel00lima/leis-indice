"""Precisão da ligação acórdão -> artigo.

As referências legislativas do STJ dizem QUAIS artigos um acórdão cita, mas não se o artigo é o
centro da discussão ou só aparece de passagem (ex.: art. 105, III, da CF em todo recurso especial).
Este módulo lê a própria ementa para separar uma coisa da outra:

  dispositivos(ref)            'ART:00206 PAR:00003 INC:00005' -> {'art-206': ['§ 3º, V']}
  citacoes(ementa)             onde a ementa cita "art. 206, § 3º, V, do CC" (lei, artigo, posição)
  trecho(ementa, ini, fim)     a frase da ementa em volta da citação
  tese(acordao)                tese jurídica (campo do STJ ou "Tese de julgamento:" da ementa)
  pontuar(...)                 nota de relevância de um par (acórdão, artigo)

Só biblioteca padrão.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- referências estruturadas

RE_TOKEN = re.compile(r"\b(ART|PAR|INC|LET|ALI|ITEM|CAP):([0-9A-ZÁÉÍÓÚÇ*]+)")


def romano(n: int) -> str:
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def id_artigo(valor: str) -> str | None:
    """'00206' -> 'art-206'; '0168A' / '00103A' -> 'art-168-a'; '00000' -> None."""
    m = re.fullmatch(r"0*(\d+)([A-Z])?", valor)
    if not m or int(m.group(1)) == 0:
        return None
    return "art-" + str(int(m.group(1))) + ("-" + m.group(2).lower() if m.group(2) else "")


def _rotulo_par(v: str) -> str:
    if v.startswith("ÚNICO") or v.startswith("UNICO"):
        return "parágrafo único"
    n = int(re.sub(r"\D", "", v) or 0)
    return f"§ {n}º" if n < 10 else f"§ {n}"


def _rotulo_inc(v: str) -> str:
    n = int(re.sub(r"\D", "", v) or 0)
    return romano(n) if n else v


def dispositivos(ref: str) -> dict[str, list[str]]:
    """Artigos de uma referência legislativa, cada um com os dispositivos citados.

    Gramática do STJ: ART abre um artigo; PAR abre um parágrafo; INC é inciso (do parágrafo aberto,
    ou do caput); LET é alínea do inciso aberto. Tokens repetidos (INC:54 INC:55) são irmãos.
    Só a forma mais específica fica: '§ 3º, V' e não também '§ 3º'.
    """
    corpo = "\n".join(ref.split("\n")[1:])  # a 1ª linha é o cabeçalho da norma
    saida: dict[str, list[str]] = {}
    art = par = inc = None
    lista: list[str] = []

    def emitir(rotulo: str, pai: str | None):
        if pai and lista and lista[-1] == pai:
            lista[-1] = rotulo
        elif rotulo not in lista:
            lista.append(rotulo)

    for tipo, valor in RE_TOKEN.findall(corpo):
        if tipo == "ART":
            art = id_artigo(valor)
            par = inc = None
            if art:
                lista = saida.setdefault(art, [])
            continue
        if not art:
            continue
        if tipo == "PAR":
            par, inc = _rotulo_par(valor), None
            emitir(par, None)
        elif tipo == "INC":
            inc = _rotulo_inc(valor)
            rot = f"{par}, {inc}" if par else f"inc. {inc}"
            emitir(rot, par)
        elif tipo in ("LET", "ALI"):
            letra = valor.lower()[:1]
            base = (f"{par}, {inc}" if par else f"inc. {inc}") if inc else par
            rot = f"{base}, {letra}" if base else f"alínea {letra}"
            emitir(rot, base)
    return saida


def contar_artigos(refs: list[str]) -> int:
    """Quantos artigos o acórdão cita no total (todas as normas): mede o quanto ele é focado."""
    return sum(1 for r in refs for _ in re.finditer(r"\bART:0*[1-9]", r))


# ---------------------------------------------------------------- citações na ementa

# Nomes pelos quais as ementas chamam cada norma acompanhada (chave = slug do config.json).
# "outra" pega as normas que NÃO são acompanhadas, para não atribuir "art. 155 do CPP" ao CP.
# A ordem importa: na mesma posição vale a primeira alternativa.
NOMES = [
    ("cpc73", r"\bCPC\s*/\s*(?:19)?73\b|\bCPC-73\b|(?i:c[óo]digo\s+de\s+processo\s+civil\s+(?:de\s+)?(?:19)?73)"),
    ("cpc", r"\bN?CPC\b(?:\s*/\s*(?:20)?15\b)?|(?i:c[óo]digo\s+de\s+processo\s+civil)"),
    ("cc16", r"\bCC\s*/\s*(?:19)?16\b|(?i:c[óo]digo\s+civil\s+(?:de\s+)?1916)"),
    ("cc", r"\bCC\b(?:\s*/\s*(?:20)?02\b)?|(?i:c[óo]digo\s+civil)"),
    ("cdc", r"\bCDC\b|(?i:c[óo]digo\s+de\s+defesa\s+do\s+consumidor)|(?i:lei\s+n?\.?º?\s*8\.?078)"),
    ("outra", r"\b(?:CPP|CPPM|CPM|CTN|CTB|ECA|LINDB|RISTJ|RISTF|LEP|LC|ADCT|CBA|LRF|LIA)\b"
              r"|(?i:c[óo]digo\s+(?:de\s+processo\s+penal|penal\s+militar|tribut[áa]rio|de\s+tr[âa]nsito|eleitoral|florestal|comercial|de\s+[áa]guas))"),
    ("cp", r"\bCP\b|(?i:c[óo]digo\s+penal)"),
    ("cf", r"\bCF\b(?:\s*/\s*(?:19)?88\b)?|\bCRFB\b(?:\s*/\s*(?:19)?88\b)?"
           r"|(?i:constitui[çc][ãa]o\s+(?:federal|da\s+rep[úu]blica))|(?i:carta\s+(?:magna|constitucional|da\s+rep[úu]blica))"),
    ("clt", r"\bCLT\b|(?i:consolida[çc][ãa]o\s+das\s+leis\s+do\s+trabalho)"),
    ("outra", r"(?i:\blei\b|\bdecreto|\bestatuto\b|\bregimento\b|\bmedida\s+provis|\bresolu[çc][ãa]o\b|\bportaria\b|\bs[úu]mula)"),
]
RE_NOME = re.compile("|".join(f"(?P<n{i}>{p})" for i, (_, p) in enumerate(NOMES)))
RE_ART = re.compile(r"\b(?:arts?|artigos?)\b\.?\s*", re.I)
RE_FIM = re.compile(r"[;:()\"“”]|\.\s|\s-\s|\bdo\s+mesmo\b|\bdesta\b|\bdessa\b|\bdeste\b", re.I)
RE_NUM = re.compile(r"(\d{1,2}\.\d{3}|\d{1,4})\s*[º°]?\s*(?:-\s*([A-Z])\b)?")
RE_DISP = re.compile(r"(?:§|par[áa]grafo|inc(?:iso)?s?\b|al[íi]nea|caput|[IVXLC]+\b|[a-z]\b|\"[a-z]\")", re.I)
DISPOSITIVOS_CITADOS = re.compile(r"(?i)dispositivos?\s+(?:legais\s+)?relevantes?\s+citados?")


def _nome(m: re.Match) -> str:
    return NOMES[int(m.lastgroup[1:])][0]


def citacoes(ementa: str) -> list[tuple[str | None, str, int, int]]:
    """Citações de artigo na ementa (já com espaços normalizados).

    Devolve (lei, 'art-206', início, fim): lei é o slug ('cc'), 'outra' ou None quando a ementa não diz.
    """
    saida = []
    for m in RE_ART.finditer(ementa):
        ini = m.end()
        janela = ementa[ini: ini + 220]
        fim_m = RE_FIM.search(janela)
        nome_m = RE_NOME.search(janela)
        corte = min(fim_m.start() if fim_m else len(janela), nome_m.start() if nome_m else len(janela))
        trecho = janela[:corte]
        lei = None
        if nome_m and nome_m.start() == corte:
            lei = _nome(nome_m)
            fim = ini + nome_m.end()
        else:
            base = max(0, m.start() - 40)
            antes = list(RE_NOME.finditer(ementa[base: m.start()]))
            if antes and re.fullmatch(r"(?:\s*/\s*\d{2,4})?[\s,]*", ementa[base + antes[-1].end(): m.start()]):
                lei = _nome(antes[-1])
            fim = ini + len(trecho.rstrip(" ,"))
        arts = []
        par_aberto = False      # depois de "§ 3º": "e 4º" ainda é parágrafo
        pars_plural = False     # depois de "§§ 2º": "e 11" ainda é parágrafo
        for peca in re.split(r",|\s+e\s+|\s+E\s+|\s+ou\s+|\s+OU\s+", trecho):
            p = peca.strip()
            if not p:
                continue
            n = RE_NUM.match(p)
            resto = p[n.end():].strip() if n else ""
            # "1.022 do CPC", "85 sobre o proveito", "85." : o número vale e a lista acaba ali
            conector = bool(resto) and resto[0] not in "-§"
            if n:
                num = int(n.group(1).replace(".", ""))
                if pars_plural or (par_aberto and re.search(r"[º°]", p) and num < 20):
                    if conector:
                        break
                    continue
                if num == 0 or num > 4000:
                    break
                arts.append("art-" + str(num) + ("-" + n.group(2).lower() if n.group(2) else ""))
                par_aberto = pars_plural = False
                if conector:
                    break
            elif RE_DISP.match(p):
                par_aberto = p.startswith("§") or p.lower().startswith("par")
                pars_plural = p.startswith("§§")
            else:
                break
        for a in dict.fromkeys(arts):
            saida.append((lei, a, m.start(), fim))
    return saida


def _fronteiras(texto: str) -> list[int]:
    """Posições onde começa uma frase (depois de '. ' ou '; ' que não sejam abreviação)."""
    pos = [0]
    for m in re.finditer(r"[.;]\s+", texto):
        antes = texto[max(0, m.start() - 6): m.start()]
        if re.search(r"(?i)\b(?:arts?|n|nº|inc|incs|fls?|min|rel|al|p|pp|ex|cf|c|v|s|ss|art|dj|dje)$", antes):
            continue
        if re.search(r"\b[A-Z]$", antes):  # iniciais: "J. Silva"
            continue
        pos.append(m.end())
    return pos


def trecho(texto: str, ini: int, fim: int, limite: int = 300) -> tuple[str, list[int]]:
    """A frase que contém a citação (texto[ini:fim]), cortada em volta dela se for longa.

    Devolve (trecho, [início, fim] da citação dentro do trecho) para o site destacar.
    """
    fr = _fronteiras(texto)
    a = max([p for p in fr if p <= ini] or [0])
    seguintes = [p for p in fr if p > fim]
    b = (seguintes[0] if seguintes else len(texto))
    a = max(a, ini - limite // 2)
    b = min(b, max(fim + limite // 2, a + limite))
    prefixo = "…" if a > 0 and a not in fr else ""
    if prefixo:
        esp = texto.find(" ", a)
        a = esp + 1 if 0 <= esp < ini else a
    pedaco = texto[a:b].rstrip()
    sufixo = "…" if b < len(texto) and not re.search(r"[.;]$", pedaco) else ""
    if sufixo:
        esp = pedaco.rfind(" ")
        if esp > fim - a:
            pedaco = pedaco[:esp].rstrip(" ,")
    return prefixo + pedaco + sufixo, [ini - a + len(prefixo), fim - a + len(prefixo)]


RE_TESE = re.compile(r"(?i)\btese\s+(?:de\s+julgamento|jur[íi]dica|fixada|firmada)\s*:?\s*(.+?)(?=\b(?:dispositivos?\s+(?:legais\s+)?relevantes?|jurisprud[êe]ncia\s+relevante)\b|$)")


def tese(x: dict, ementa: str, limite: int = 320) -> str:
    t = re.sub(r"\s+", " ", x.get("teseJuridica") or "").strip()
    if not t:
        m = RE_TESE.search(ementa)
        t = m.group(1).strip() if m else ""
    t = t.strip(" \"“”")
    if len(t) > limite:
        corte = t.rfind(" ", 0, limite)
        t = t[: corte if corte > limite * 0.6 else limite].rstrip(" ,;.-") + "…"
    return t


# ---------------------------------------------------------------- relevância

def pontuar(onde: str | None, classe: str, orgao: str, tem_tema: bool, tem_tese: bool, n_artigos: int) -> float:
    """Nota de relevância do par (acórdão, artigo). Maior = mais útil para quem estuda o artigo.

    onde: "ementa" (o artigo é discutido no corpo da ementa), "lista" (só aparece em "Dispositivos
    relevantes citados") ou None (só nas referências que o STJ cataloga).
    """
    s = {"ementa": 4.0, "lista": 2.5}.get(onde or "", 0.0)
    if tem_tema:
        s += 2.0
    if tem_tese:
        s += 1.0
    s += 2.0 / max(1, n_artigos) ** 0.5           # acórdão que cita 1 artigo vale mais que um que cita 20
    if re.match(r"EDcl\b", classe or ""):
        s -= 1.0                                   # embargos de declaração raramente discutem o mérito
    elif re.match(r"(?:AgInt|AgRg)\b", classe or ""):
        s -= 0.3
    if re.search(r"(?i)se[çc][ãa]o|corte especial", orgao or ""):
        s += 0.7                                   # seções e Corte Especial uniformizam
    return round(s, 2)
