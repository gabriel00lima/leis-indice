import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import construir  # noqa: E402
import extrator  # noqa: E402


def refs(texto, data="2020-01-01"):
    return [(p, n, a) for p, n, a, _i, _f in extrator.referencias_em(texto, int(data[:4]), data)]


class TestReferencias(unittest.TestCase):
    def test_formas_de_data(self):
        self.assertEqual(refs("Lei nº 8.078, de 11 de setembro de 1990"), [("lei", "8078", 1990)])
        self.assertEqual(refs("Lei nº 9.008, de 21/3/1995"), [("lei", "9008", 1995)])
        self.assertEqual(refs("Lei nº 8.078/90"), [("lei", "8078", 1990)])
        self.assertEqual(refs("Lei 13.105/2015"), [("lei", "13105", 2015)])
        self.assertEqual(refs("Lei Complementar nº 101, de 2000"), [("lcp", "101", 2000)])
        self.assertEqual(refs("Lei nº 11. 989, de 27/7/2009"), [("lei", "11989", 2009)])

    def test_tipos(self):
        self.assertEqual(refs("Decreto-Lei nº 2.848, de 7 de dezembro de 1940"), [("del", "2848", 1940)])
        self.assertEqual(refs("Decreto-lei n. 96 de 22 de dezembro de 1937"), [("del", "96", 1937)])
        self.assertEqual(refs("Decreto nº 1.234, de 1994"), [("dec", "1234", 1994)])
        self.assertEqual(refs("Decreto Legislativo nº 6, de 2020"), [("dlg", "6", 2020)])
        self.assertEqual(refs("Emenda Constitucional nº 45, de 2004"), [("emc", "45", 2004)])
        self.assertEqual(refs("Medida Provisória nº 2.200-2, de 24/8/2001"), [("mpv", "2200-2", 2001)])

    def test_constituicao_so_depois_de_1988(self):
        self.assertEqual(refs("art. 5º da Constituição Federal", "1990-01-01"), [("constituicao", "", 1988)])
        self.assertEqual(refs("art. 180 da Constituição Federal", "1937-12-22"), [])

    def test_codigos_por_nome(self):
        self.assertEqual(refs("nos termos do Código Civil", "2010-01-01"), [("lei", "10406", 2002)])
        self.assertEqual(refs("nos termos do Código Civil", "1990-01-01"), [("lei", "3071", 1916)])


class TestExtracao(unittest.TestCase):
    CORPO = """# Lei nº 9.999 de 01/01/2000

**Art. 1º** Esta Lei observa o art. 48 da Lei nº 8.078, de 11 de setembro de 1990.

**Art. 2º** Texto. *(Redação dada pela Lei nº 12.345, de 1/2/2011)*

**Art. 3º** O art. 5º da Lei nº 7.347, de 24 de julho de 1985, passa a vigorar com a seguinte redação:

**Art. 4º** *(Revogado pela Medida Provisória nº 1.000, de 2/3/2012, convertida na Lei nº 12.500, de 2012)*

**Art. 5º** Revogam-se a Lei nº 1.111, de 1950, e o art. 2º da Lei nº 2.222, de 1960.
"""

    def test_tipos_e_direcoes(self):
        r = extrator.extrair_referencias(self.CORPO, "2000-01-01")
        esperado = [
            ["entra", "lei", "12345", 2011, "altera", ["art. 2º"]],
            ["entra", "mpv", "1000", 2012, "revoga", ["art. 4º"]],
            ["sai", "lei", "1111", 1950, "revoga", []],
            ["sai", "lei", "12500", 2012, "cita", []],
            ["sai", "lei", "2222", 1960, "revoga", ["art. 2º"]],
            ["sai", "lei", "7347", 1985, "altera", ["art. 5º"]],
            ["sai", "lei", "8078", 1990, "cita", ["art. 48"]],
        ]
        self.assertEqual(r, esperado)

    def test_frontmatter(self):
        meta, corpo = extrator.metadados("x.md", '---\ntitulo: "Lei nº 1"\nrevogada: true\ndata: 2000-01-01\n---\n# T\n')
        self.assertEqual(meta["titulo"], "Lei nº 1")
        self.assertTrue(meta["revogada"])
        self.assertEqual(corpo, "# T\n")


class TestResolvedor(unittest.TestCase):
    def test_numeracao_reiniciada_e_externo(self):
        r = construir.Resolvedor([
            "federal/leis-complementares/1962/lcp-1-1962-07-17.md",
            "federal/leis-complementares/1967/lcp-1-1967-11-09.md",
            "federal/medidas-provisorias/2001/mpv-2200-2-2001-08-24.md",
        ])
        self.assertEqual(r.resolver("lcp", "1", 1962, "2000-01-01"), "federal/leis-complementares/1962/lcp-1-1962-07-17")
        self.assertEqual(r.resolver("lcp", "1", None, "1965-01-01"), "federal/leis-complementares/1962/lcp-1-1962-07-17")
        self.assertEqual(r.resolver("lcp", "1", None, "1970-01-01"), "federal/leis-complementares/1967/lcp-1-1967-11-09")
        self.assertEqual(r.resolver("mpv", "2200-2", 2001, ""), "federal/medidas-provisorias/2001/mpv-2200-2-2001-08-24")
        self.assertEqual(r.resolver("mpv", "2200", None, ""), "federal/medidas-provisorias/2001/mpv-2200-2-2001-08-24")
        self.assertEqual(r.resolver("lei", "5", 1999, ""), "externo:lei-5-1999")


def _git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


class TestConstrucaoIncremental(unittest.TestCase):
    def _lei(self, d, caminho, titulo, data, corpo):
        p = Path(d) / caminho
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'---\ntitulo: "{titulo}"\ntipo: "Lei Ordinária"\nnumero: "1"\ndata: {data}\n'
                     f'ementa: "E"\nrevogada: false\nurn: "u"\n---\n# {titulo}\n\n{corpo}\n', encoding="utf-8")

    def test_incremental(self):
        with tempfile.TemporaryDirectory() as tmp:
            fonte, saida = Path(tmp, "fonte"), Path(tmp, "data")
            fonte.mkdir()
            _git(fonte, "init", "-q")
            _git(fonte, "config", "user.email", "t@t")
            _git(fonte, "config", "user.name", "t")
            a = "federal/leis-ordinarias/1990/lei-100-1990-01-01.md"
            b = "federal/leis-ordinarias/1991/lei-200-1991-01-01.md"
            self._lei(fonte, a, "Lei nº 100", "1990-01-01", "**Art. 1º** Texto.")
            self._lei(fonte, b, "Lei nº 200", "1991-01-01", "**Art. 1º** Altera a Lei nº 100, de 1990.")
            _git(fonte, "add", ".")
            _git(fonte, "commit", "-qm", "1")

            r1 = construir.construir(fonte, saida)
            self.assertTrue(r1["completo"])
            self.assertEqual(r1["normas"], 2)
            links = json.loads((saida / "arestas.json").read_text())["links"]
            manifesto = json.loads((saida / "links.json").read_text())
            self.assertIn({"arquivo": "adjacencia/leis-ordinarias.json", "pasta": "leis-ordinarias"}, manifesto["shards"])
            self.assertEqual([(l["de"][-15:], l["para"][-15:], l["tipo"]) for l in links],
                             [("lei-200-1991-01-01"[-15:], "lei-100-1990-01-01"[-15:], "cita")])

            r2 = construir.construir(fonte, saida)
            self.assertEqual((r2["processados"], r2["mudou"]), (0, False))

            # nova lei que revoga a 100; a 200 é removida
            c = "federal/leis-ordinarias/1992/lei-300-1992-01-01.md"
            self._lei(fonte, c, "Lei nº 300", "1992-01-01", "**Art. 2º** Revoga-se a Lei nº 100, de 1990.")
            _git(fonte, "rm", "-q", b)
            _git(fonte, "add", ".")
            _git(fonte, "commit", "-qm", "2")
            r3 = construir.construir(fonte, saida)
            self.assertEqual((r3["processados"], r3["removidos"], r3["normas"]), (1, 1, 2))
            adj = json.loads((saida / "adjacencia" / "leis-ordinarias.json").read_text())
            self.assertEqual(adj[a[:-3]]["revogada_por"], [c[:-3]])
            self.assertEqual(adj[a[:-3]]["citada_por"], [])


if __name__ == "__main__":
    unittest.main()
