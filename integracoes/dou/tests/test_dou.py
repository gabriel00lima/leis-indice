"""Testes da coleta do DOU com um ZIP sintético no formato da Imprensa Nacional."""

import datetime as dt
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import coletar  # noqa: E402
import conferir  # noqa: E402
from construir import Resolvedor  # noqa: E402


def xml(id_, tipo, identifica, ementa, texto, pub="DO1", data="12/03/2025"):
    return f"""<xml><article id="{id_}" idMateria="{id_}" pubName="{pub}" artType="{tipo}"
 pubDate="{data}" artCategory="Atos do Poder Legislativo" numberPage="1" editionNumber="48"
 pdfPage="http://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data={data}&amp;jornal=515&amp;pagina=1">
<body><Identifica><![CDATA[{identifica}]]></Identifica><Ementa><![CDATA[{ementa}]]></Ementa>
<Texto><![CDATA[{texto}]]></Texto></body></article></xml>"""


CAMINHOS = [
    "constituicao.md",
    "federal/leis-ordinarias/1990/lei-8078-1990-09-11.md",
    "federal/leis-ordinarias/2002/lei-10406-2002-01-10.md",
    "federal/leis-ordinarias/2025/lei-15100-2025-03-10.md",
    "federal/leis-ordinarias/1993/lei-8666-1993-06-21.md",
]


def zip_sintetico(destino: Path):
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("515_20250312_1.xml", xml(
            "1", "Lei", "LEI Nº 15.100, DE 10 DE MARÇO DE 2025",
            "Altera as Leis nºs 8.078, de 11 de setembro de 1990, e 10.406, de 10 de janeiro de 2002.",
            "<p>O PRESIDENTE DA REPÚBLICA Faço saber...</p>"
            "<p>Art. 3º Fica revogada a Lei nº 8.666, de 21 de junho de 1993.</p>"
            "<p>Art. 4º Observado o art. 5º da Constituição Federal.</p>"))
        z.writestr("515_20250312_2.xml", xml(
            "2", "Decreto", "DECRETO Nº 12.400, DE 11 DE MARÇO DE 2025",
            "", '<p class="ementa">Regulamenta a Lei nº 8.078, de 1990.</p><p>Art. 1º ...</p>'))
        z.writestr("515_20250312_3.xml", xml(
            "3", "Portaria", "PORTARIA Nº 10, DE 11 DE MARÇO DE 2025", "", "<p>x</p>"))
        z.writestr("515_20250312_4.xml", xml(
            "4", "Decreto", "DECRETOS DE 11 DE MARÇO DE 2025", "", "<p>Nomear Fulano</p>"))
        z.writestr("530_20250312_5.xml", xml(
            "5", "Lei", "LEI Nº 15.101, DE 10 DE MARÇO DE 2025", "", "<p>x</p>", pub="DO2"))


class TestIdentifica(unittest.TestCase):
    def test_tipos(self):
        self.assertEqual(coletar.identificar("LEI Nº 15.100, DE 10 DE MARÇO DE 2025"),
                         ("lei", "Lei", "15100", "2025-03-10"))
        self.assertEqual(coletar.identificar("LEI COMPLEMENTAR Nº 214, DE 16 DE JANEIRO DE 2025")[:3],
                         ("lcp", "Lei Complementar", "214"))
        self.assertEqual(coletar.identificar("MEDIDA PROVISÓRIA Nº 1.286, DE 31 DE DEZEMBRO DE 2024")[0], "mpv")
        self.assertEqual(coletar.identificar("EMENDA CONSTITUCIONAL Nº 135, DE 20 DE DEZEMBRO DE 2024")[0], "emc")
        self.assertEqual(coletar.identificar("DECRETO LEGISLATIVO Nº 5, DE 1º DE ABRIL DE 2025")[:3],
                         ("dlg", "Decreto Legislativo", "5"))
        self.assertIsNone(coletar.identificar("DECRETOS DE 11 DE MARÇO DE 2025"))
        self.assertIsNone(coletar.identificar("PORTARIA Nº 10, DE 11 DE MARÇO DE 2025"))

    def test_plural(self):
        refs = coletar.referencias("Altera as Leis nºs 8.078, de 11 de setembro de 1990, 9.503, de 1997, "
                                   "e 10.406, de 10 de janeiro de 2002.", "2025-03-10")
        self.assertEqual({(p, n, a) for p, n, a in refs},
                         {("lei", "8078", 1990), ("lei", "9503", 1997), ("lei", "10406", 2002)})


class TestColeta(unittest.TestCase):
    def test_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "S01032025.zip"
            zip_sintetico(z)
            existentes = {c[:-3] for c in CAMINHOS}
            atos = coletar.processar_zips([z], Resolvedor(CAMINHOS), existentes)
            self.assertEqual([a["id"] for a in atos], ["1", "2"])
            lei = next(a for a in atos if a["id"] == "1")
            self.assertEqual(lei["norma"], "federal/leis-ordinarias/2025/lei-15100-2025-03-10")
            self.assertEqual(lei["altera"], ["federal/leis-ordinarias/1990/lei-8078-1990-09-11",
                                             "federal/leis-ordinarias/2002/lei-10406-2002-01-10"])
            self.assertEqual(lei["revoga"], ["federal/leis-ordinarias/1993/lei-8666-1993-06-21"])
            self.assertEqual(lei["cita"], ["constituicao"])
            self.assertTrue(lei["url"].startswith("https://"))
            self.assertEqual(lei["data"], "2025-03-12")
            dec = next(a for a in atos if a["id"] == "2")
            self.assertEqual(dec["ementa"], "Regulamenta a Lei nº 8.078, de 1990.")
            self.assertIsNone(dec["norma"])
            self.assertEqual(dec["cita"], ["federal/leis-ordinarias/1990/lei-8078-1990-09-11"])

    def test_fluxo_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            z = tmp / "S01032025.zip"
            zip_sintetico(z)
            (tmp / "data" / "index").mkdir(parents=True)
            (tmp / "data" / "index" / "leis.json").write_text(json.dumps(
                [{"id": c[:-3], "path": c} for c in CAMINHOS if c != "constituicao.md"]))
            saida = tmp / "data" / "dou"
            coletar.main(["--saida", str(saida), "--zip", str(z), "--mes", "2025-03"])
            manifesto = json.loads((saida / "index.json").read_text())
            self.assertEqual(manifesto["total"], 2)
            self.assertEqual(manifesto["meses"][0]["mes"], "2025-03")
            por_norma = json.loads((saida / "por_norma.json").read_text())
            cdc = por_norma["federal/leis-ordinarias/1990/lei-8078-1990-09-11"]
            self.assertEqual([x["rel"] for x in cdc], ["altera"])
            gerado = manifesto["gerado_em"]
            coletar.main(["--saida", str(saida), "--zip", str(z), "--mes", "2025-03"])
            self.assertEqual(json.loads((saida / "index.json").read_text())["gerado_em"], gerado)

            mon = tmp / "monitor"
            mon.mkdir()
            (mon / "acompanhar.txt").write_text(
                "federal/leis-ordinarias/1990/lei-8078-1990-09-11.md  # CDC\n")
            (mon / "estado.json").write_text("{}")
            c = conferir.conferir(saida, mon, dt.date(2025, 4, 1), None)
            self.assertEqual(c["monitor"][0]["situacao"], "nao_verificado")
            self.assertEqual(len(c["monitor"][0]["atos"]), 1)
            # o decreto não tem arquivo no acervo (lista só do índice)
            self.assertEqual([a["ato"] for a in c["fora_do_acervo"]], ["2"])


if __name__ == "__main__":
    unittest.main()
