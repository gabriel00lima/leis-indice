import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coletar as c  # noqa: E402

CHAVES = {"LEI:013105 ANO:2015": "cpc", "CFB:****** ANO:1988": "cf", "DEL:002848 ANO:1940": "cp"}
LEIS = [{"id": "x/cpc", "slug": "cpc"}, {"id": "constituicao", "slug": "cf"}, {"id": "x/cp", "slug": "cp"}]


def acordao(i, data, *refs, **extra):
    return {"id": str(i), "siglaClasse": "REsp", "numeroProcesso": "2260689", "numeroRegistro": "202504405393",
            "nomeOrgaoJulgador": "TERCEIRA TURMA", "ministroRelator": "NANCY ANDRIGHI", "dataDecisao": data,
            "ementa": f"DIREITO PROCESSUAL CIVIL.\n RECURSO ESPECIAL. CASO {i} " + "texto " * 100,
            "referenciasLegislativas": list(refs), **extra}


class Referencias(unittest.TestCase):
    def test_artigos(self):
        ref = "LEG:FED LEI:013105 ANO:2015\n *****  CPC-15    CÓDIGO DE PROCESSO CIVIL DE 2015\n         ART:00787 ART:00803 INC:00001 ART:01022 PAR:ÚNICO"
        self.assertEqual(c.artigos_da_referencia(ref), ["art-787", "art-803", "art-1022"])

    def test_artigo_com_letra_e_quebra(self):
        ref = "LEG:FED CFB:****** ANO:1988\n *****  CF-1988    CONSTITUIÇÃO FEDERAL DE 1988\n         ART:00005 INC:00061 ART:00093\n         INC:00009 ART:00103A"
        self.assertEqual(c.artigos_da_referencia(ref), ["art-5", "art-93", "art-103-a"])

    def test_letra_de_inciso_nao_vira_artigo(self):
        ref = "LEG:FED DEL:002848 ANO:1940\n *****  CP-40    CÓDIGO PENAL\n         ART:00059 ART:00065 INC:00003 LET:D"
        self.assertEqual(c.artigos_da_referencia(ref), ["art-59", "art-65"])

    def test_sem_artigo(self):
        self.assertEqual(c.artigos_da_referencia("LEG:FED LEI:014063 ANO:2020"), [])

    def test_norma(self):
        self.assertEqual(c.norma_da_referencia("LEG:FED LEI:013105 ANO:2015\n x", CHAVES), "cpc")
        self.assertEqual(c.norma_da_referencia("LEG:FED CFB:****** ANO:1988", CHAVES), "cf")
        self.assertIsNone(c.norma_da_referencia("LEG:FED LEI:005869 ANO:1973\n x", CHAVES))
        self.assertIsNone(c.norma_da_referencia("LEG:FED LEI:0131050 ANO:2015", CHAVES))


class Formatacao(unittest.TestCase):
    def test_titulo(self):
        self.assertEqual(c.titulo("RICARDO VILLAS BÔAS CUEVA"), "Ricardo Villas Bôas Cueva")
        self.assertEqual(c.titulo("TERCEIRA SEÇÃO DO TRIBUNAL"), "Terceira Seção do Tribunal")

    def test_resumo(self):
        d = c.resumo_decisao(acordao(1, "20260804"), 120)
        self.assertEqual(d["p"], "REsp 2.260.689")
        self.assertEqual(d["j"], "2026-08-04")
        self.assertTrue(d["e"].endswith("…") and len(d["e"]) <= 121)
        self.assertIn("202504405393", d["u"])


class Agregacao(unittest.TestCase):
    def test_contagem_recentes_e_blocos(self):
        regs = [
            acordao(1, "20250101", "LEG:FED LEI:013105 ANO:2015\n *****  CPC\n ART:00099 ART:01022"),
            acordao(2, "20260101", "LEG:FED LEI:013105 ANO:2015\n *****  CPC\n ART:01022"),
            acordao(3, "20240101", "LEG:FED LEI:013105 ANO:2015"),
            acordao(4, "20240101", "LEG:FED LEI:005869 ANO:1973\n ART:00001"),
            acordao(5, "20230101", "LEG:FED CFB:****** ANO:1988\n ***** CF\n ART:00005",
                    "LEG:FED LEI:013105 ANO:2015\n ***** CPC\n ART:01022"),
        ]
        ext = c.extrair(regs, CHAVES, 200)
        self.assertEqual([e["id"] for e in ext], ["1", "2", "3", "5"])
        ag = c.agregar(ext + ext[:1], LEIS, por_artigo=2)  # repetido conta uma vez
        cpc = ag["cpc"]["resumo"]
        self.assertEqual(cpc["total"], 4)
        self.assertEqual(cpc["artigos"], {"art-99": 1, "art-1022": 3})
        self.assertEqual(cpc["sem_artigo"], 1)
        self.assertEqual(cpc["periodo"], ["2023-01-01", "2026-01-01"])
        b10 = ag["cpc"]["blocos"][10]
        ids = [x["i"] for x in b10["artigos"]["art-1022"]]
        self.assertEqual(ids, ["2", "1"])  # o 2 cita só esse artigo (mais focado) e é mais recente
        self.assertEqual(set(b10["decisoes"]), set(ids))
        self.assertEqual([x["i"] for x in ag["cpc"]["blocos"][-1]["artigos"]["sem-artigo"]], ["3"])
        self.assertEqual(ag["cf"]["resumo"]["artigos"], {"art-5": 1})
        self.assertEqual(ag["cp"]["resumo"]["total"], 0)


class DataJud(unittest.TestCase):
    def test_chave_da_wiki(self):
        pagina = ('<p>utilize o formato "Authorization: APIKey [Chave Pública]" no cabeçalho.</p>'
                  '<p>APIKey atual:</p><pre><code>Authorization: APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==</code></pre>'
                  '<nav><a>Anterior</a><a>Termo</a></nav>')
        self.assertEqual(c.extrair_chave(pagina), "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==")
        self.assertIsNone(c.extrair_chave("<p>nada</p>"))

    def test_config_valido(self):
        cfg = c.carregar_config()
        slugs = [l["slug"] for l in cfg["leis"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for l in cfg["leis"]:
            self.assertRegex(l["stj"], r"^[A-Z]{3}:[0-9*]{6} ANO:\d{4}$")

    def test_indice(self):
        cfg = {"leis": [{"id": "x/cpc", "slug": "cpc", "nome": "CPC"}, {"id": "x/cc", "slug": "cc"}]}
        with tempfile.TemporaryDirectory() as t:
            s = Path(t)
            c.gravar_json(s / "stj" / "cpc.json", {"total": 3})
            c.gravar_json(s / "stj" / "_fonte.json", {"gerado_em": "2026-11-04T00:00:00Z"})
            c.gerar_indice(cfg, s)
            i = json.loads((s / "indice.json").read_text())
            self.assertEqual(i["leis"], {"x/cpc": {"nome": "CPC", "slug": "cpc", "stj": "stj/cpc.json", "total": 3}})
            antes = (s / "indice.json").read_text()
            c.gerar_indice(cfg, s)
            self.assertEqual((s / "indice.json").read_text(), antes)


if __name__ == "__main__":
    unittest.main()
