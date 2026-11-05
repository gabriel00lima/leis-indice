import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coletar as c  # noqa: E402
import precisao as P  # noqa: E402

CHAVES = {"LEI:013105 ANO:2015": "cpc", "LEI:010406 ANO:2002": "cc", "CFB:****** ANO:1988": "cf",
          "DEL:002848 ANO:1940": "cp"}


class Dispositivos(unittest.TestCase):
    def test_gramatica(self):
        ref = ("LEG:FED CFB:****** ANO:1988\n *****  CF-1988\n         ART:00005 INC:00054 INC:00055 ART:00037 PAR:00006\n"
               "         ART:00175 ART:00105 INC:00003 LET:A LET:C ART:00001 PAR:ÚNICO")
        self.assertEqual(P.dispositivos(ref), {
            "art-5": ["inc. LIV", "inc. LV"], "art-37": ["§ 6º"], "art-175": [],
            "art-105": ["inc. III, a", "inc. III, c"], "art-1": ["parágrafo único"]})

    def test_paragrafo_com_inciso_e_artigo_com_letra(self):
        ref = "LEG:FED DEL:002848 ANO:1940\n *****  CP-40\n         ART:00168 ART:0168A PAR:00001 INC:00001 PAR:00002 ART:00206 PAR:00003 INC:00005"
        self.assertEqual(P.dispositivos(ref), {"art-168": [], "art-168-a": ["§ 1º, I", "§ 2º"], "art-206": ["§ 3º, V"]})

    def test_contar_artigos(self):
        self.assertEqual(P.contar_artigos(["LEG\n ART:00001 ART:00002 INC:00001", "LEG\n ART:00010", "LEG:FED LEI:1"]), 3)


class Citacoes(unittest.TestCase):
    def cit(self, t):
        return [(l, a) for l, a, *_ in P.citacoes(t)]

    def test_lista_e_lei_depois(self):
        self.assertEqual(self.cit("NÃO OCORRÊNCIA. ARTS. 1.022 E 489 DO CPC. FORMA MERCANTIL (ART. 917 DO CPC/1973 E ART. 551, § 2º, DO CPC)."),
                         [("cpc", "art-1022"), ("cpc", "art-489"), ("cpc73", "art-917"), ("cpc", "art-551")])

    def test_lei_antes_e_paragrafos_plurais(self):
        self.assertEqual(self.cit("Dispositivos relevantes citados: CC, arts. 205 e 206, § 5º, I; CPC, art. 85, §§ 2º e 11."),
                         [("cc", "art-205"), ("cc", "art-206"), ("cpc", "art-85")])

    def test_outras_normas_nao_viram_acompanhadas(self):
        self.assertEqual(self.cit("o caput do artigo 48 da Lei nº 8.245/1991; furto (art. 155 do CPP) e art. 155, § 4º, I, do CP"),
                         [("outra", "art-48"), ("outra", "art-155"), ("cp", "art-155")])

    def test_nomes_por_extenso(self):
        self.assertEqual(self.cit("violação do art. 2º do Código de Defesa do Consumidor; art. 5º, LV, da Constituição Federal; art. 103-A da CF"),
                         [("cdc", "art-2"), ("cf", "art-5"), ("cf", "art-103-a")])

    def test_trecho(self):
        t = ("PROCESSUAL CIVIL. RECURSO ESPECIAL. 1. A pretensão de reparação civil prescreve em três anos "
             "(art. 206, § 3º, V, do Código Civil), conforme a jurisprudência desta Corte. 2. Recurso desprovido.")
        _, _, ini, fim = P.citacoes(t)[0]
        x, h = P.trecho(t, ini, fim)
        self.assertTrue(x.startswith("A pretensão"))
        self.assertTrue(x.endswith("desta Corte."))
        self.assertEqual(x[h[0]:h[1]], "art. 206, § 3º, V, do Código Civil")

    def test_tese(self):
        e = 'IV. DISPOSITIVO E TESE 6. Recurso desprovido. Tese de julgamento: "1. A cláusula é válida." Dispositivos relevantes citados: CC, art. 757.'
        self.assertEqual(P.tese({}, e), "1. A cláusula é válida.")
        self.assertEqual(P.tese({"teseJuridica": "Tese do repetitivo."}, e), "Tese do repetitivo.")


class Ligacao(unittest.TestCase):
    def acordao(self, ementa, *refs, **extra):
        return {"id": "1", "siglaClasse": "REsp", "numeroProcesso": "1", "nomeOrgaoJulgador": "TERCEIRA TURMA",
                "dataDecisao": "20260101", "ementa": ementa, "referenciasLegislativas": list(refs), **extra}

    def test_ementa_lista_e_passagem(self):
        x = self.acordao(
            "CIVIL. PRESCRIÇÃO. 1. Aplica-se o prazo do art. 206, § 3º, V, do CC. Dispositivos relevantes citados: CPC, art. 85.",
            "LEG:FED LEI:010406 ANO:2002\n ***** CC-02\n ART:00206 PAR:00003 INC:00005",
            "LEG:FED LEI:013105 ANO:2015\n ***** CPC-15\n ART:00085 ART:01029",
            "LEG:FED CFB:****** ANO:1988\n ***** CF\n ART:00105 INC:00003 LET:A")
        r = c.ligar_artigos(x, CHAVES)
        self.assertEqual(r["cc"]["art-206"]["w"], "ementa")
        self.assertEqual(r["cc"]["art-206"]["d"], ["§ 3º, V"])
        self.assertIn("art. 206, § 3º, V, do CC", r["cc"]["art-206"]["x"])
        self.assertEqual(r["cpc"]["art-85"]["w"], "lista")
        self.assertNotIn("w", r["cpc"]["art-1029"])
        self.assertNotIn("w", r["cf"]["art-105"])

    def test_trecho_do_corpo_vence_o_da_indexacao(self):
        x = self.acordao("CIVIL. PRESCRIÇÃO. ART. 206, § 5º, I, DO CC. RECURSO DESPROVIDO. 1. O prazo é o quinquenal do art. 206, § 5º, I, do Código Civil, contado do vencimento.",
                         "LEG:FED LEI:010406 ANO:2002\n ***** CC\n ART:00206 PAR:00005 INC:00001")
        r = c.ligar_artigos(x, CHAVES)["cc"]["art-206"]
        self.assertTrue(r["x"].startswith("O prazo é o quinquenal"))
        self.assertNotIn("_cab", r)

    def test_sem_lei_na_ementa_so_vale_se_o_numero_e_unico(self):
        refs = ("LEG:FED LEI:013105 ANO:2015\n ***** CPC\n ART:00085", "LEG:FED LEI:005869 ANO:1973\n ART:00020")
        r = c.ligar_artigos(self.acordao("Honorários. Incidência do art. 85 sobre o proveito econômico.", *refs), CHAVES)
        self.assertEqual(r["cpc"]["art-85"]["w"], "ementa")
        refs2 = refs + ("LEG:FED LEI:005869 ANO:1973\n ART:00085",)
        r = c.ligar_artigos(self.acordao("Honorários. Incidência do art. 85 sobre o proveito econômico.", *refs2), CHAVES)
        self.assertNotIn("w", r["cpc"]["art-85"])

    def test_relevancia_e_ementas_iguais(self):
        base = "LEG:FED LEI:010406 ANO:2002\n ***** CC\n ART:00206 PAR:00003 INC:00005"
        a = dict(self.acordao("CIVIL. Prazo do art. 206, § 3º, V, do CC. Recurso provido.", base), id="a", dataDecisao="20240101")
        b = dict(self.acordao("CIVIL. Outro tema qualquer. Recurso provido.", base + " ART:00927 ART:00186 ART:00944"),
                 id="b", dataDecisao="20260101")
        lote = [dict(self.acordao("PROCESSUAL. Repetitivo igual. Recurso provido.", base), id=f"r{i}", dataDecisao="20250101")
                for i in range(3)]
        ag = c.agregar(c.extrair([a, b, *lote], CHAVES, 200), [{"id": "x/cc", "slug": "cc"}], por_artigo=5)
        res = ag["cc"]["resumo"]
        self.assertEqual(res["artigos"]["art-206"], 5)
        self.assertEqual(res["na_ementa"], {"art-206": 1})
        self.assertEqual(res["dispositivos"]["art-206"], {"§ 3º, V": 5})
        itens = ag["cc"]["blocos"][2]["artigos"]["art-206"]
        self.assertEqual(itens[0]["i"], "a")                    # discute o artigo na ementa: primeiro, mesmo sendo mais antigo
        self.assertEqual(itens[0]["w"], "ementa")
        self.assertEqual(len(itens), 3)                         # a, o lote (1 representante) e b
        self.assertEqual([x.get("ig") for x in itens if x["i"].startswith("r")], [2])
        self.assertEqual(itens[-1]["i"], "b")                   # cita 4 artigos e não fala dele na ementa


if __name__ == "__main__":
    unittest.main()
