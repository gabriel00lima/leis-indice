import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import senado  # noqa: E402
import coletar  # noqa: E402

# Trechos reais da resposta de /dadosabertos/legislacao/urn (nov/2026), reduzidos.
RESPOSTA = {"DetalheDocumento": {"documentos": {"documento": [{
    "id": "549954",
    "identificacao": {"normaNome": "Lei nº 9.504 de 30/09/1997",
                      "apelido": "LEI-9504-1997-09-30 , Lei Eleitoral (1997)"},
    "publicacoes": {"publicacao": {"tipo": "PUB", "data": "01/10/1997",
                                   "dispositivo": "Publicação Original [Diário Oficial da União de 01/10/1997]"}},
    "vides": {"vide": [
        {"nomeNormaPosterior": "Lei nº 8.656 de 21/05/1993", "datAssinatura": "21/05/1993",
         "comentario": "Declaração de Alteração Permanente",
         "itens": {"item": {"dispositivo": "Art. 57 ", "comentario": "Alteração"}}},
        {"nomeNormaPosterior": "Decreto nº 861 de 09/07/1993", "datAssinatura": "09/07/1993",
         "comentario": "Declaração de Legislação Correlata", "itens": ""},
        {"nomeNormaPosterior": "Acórdão da Ação Direta de Inconstitucionalidade nº 4.451 de 21/06/2018",
         "datAssinatura": "21/06/2018", "comentario": "Declaração de Alteração Permanente",
         "itens": {"item": [
             {"dispositivo": "Art. 45, caput, Inciso 2 ", "comentario": "Declaração de Inconstitucionalidade"},
             {"dispositivo": "Art. 45, § 4 ", "comentario": "Declaração de Inconstitucionalidade"}]}},
        {"nomeNormaPosterior": "Acórdão da Ação Direta de Inconstitucionalidade nº 5.889 de 06/06/2018",
         "datAssinatura": "06/06/2018", "comentario": "Declaração de Alteração Permanente",
         "itens": {"item": [{"dispositivo": "Art. 59-A, caput ", "comentario": "Suspensão Temporária"}]}},
        {"nomeNormaPosterior": "Acórdão da Ação Direta de Inconstitucionalidade nº 5.794 de 29/06/2018",
         "datAssinatura": "29/06/2018", "comentario": "Declaração de Constitucionalidade", "itens": ""},
        {"nomeNormaPosterior": "Resolução do Senado Federal nº 19 de 17/06/1974", "datAssinatura": "17/06/1974",
         "comentario": "Declaração de Alteração Permanente",
         "itens": {"item": [{"dispositivo": "Art. 789, § 1 ", "comentario": "Suspensão de Execução por Inconstitucionalidade"}]}},
        {"nomeNormaPosterior": "Medida Provisória nº 333 de 06/07/1993", "datAssinatura": "06/07/1993",
         "comentario": "Declaração de Alteração Provisória",
         "itens": {"item": [{"dispositivo": "Art. 57, Parágrafo Único ", "comentario": "Acréscimo"},
                            {"dispositivo": "Art. 60 ", "comentario": "Suspensão Temporária"}]}},
    ]},
}]}}}


class TestConversao(unittest.TestCase):
    def setUp(self):
        self.r = senado.converter(RESPOSTA, lambda k: "federal/leis-ordinarias/1993/lei-8656-1993-05-21"
                                  if k == ("lei", "8656", "1993-05-21") else None)

    def test_utilidades(self):
        self.assertEqual(senado.lista(""), [])
        self.assertEqual(senado.lista({"a": 1}), [{"a": 1}])
        self.assertEqual(senado.data_iso("21/05/1993"), "1993-05-21")
        self.assertEqual(senado.artigo_do_dispositivo("Art. 394-A, caput, Inciso 2 "), "394-a")
        self.assertEqual(senado.artigo_do_dispositivo("Anexo I"), None)
        self.assertEqual(senado.chave_norma("Decreto-Lei nº 5.452 de 01/05/1943"), ("del", "5452", "1943-05-01"))
        self.assertEqual(senado.decisao_stf("Acórdão da Ação Direta de Inconstitucionalidade nº 5.938 de 29/05/2019"),
                         {"classe": "ADI", "numero": "5938"})

    def test_cabecalho(self):
        self.assertEqual(self.r["nome"], "Lei nº 9.504 de 30/09/1997")
        self.assertEqual(self.r["apelidos"], ["Lei Eleitoral (1997)"])
        self.assertEqual(self.r["publicacoes"][0]["data"], "1997-10-01")

    def test_alteracoes(self):
        nomes = [a["nome"] for a in self.r["alteracoes"]]
        self.assertEqual(nomes, ["Lei nº 8.656 de 21/05/1993", "Medida Provisória nº 333 de 06/07/1993",
                                 "Decreto nº 861 de 09/07/1993"])  # em ordem de data
        lei = self.r["alteracoes"][0]
        self.assertEqual(lei["id"], "federal/leis-ordinarias/1993/lei-8656-1993-05-21")
        self.assertEqual(lei["dispositivos"], [{"dispositivo": "Art. 57", "art": "57", "acao": "alterou"}])
        # suspensão vinda de MP não é controle de constitucionalidade
        mp = self.r["alteracoes"][1]
        self.assertEqual([d["acao"] for d in mp["dispositivos"]], ["acrescentou", "suspensão temporária"])

    def test_controle(self):
        c = {x["nome"]: x for x in self.r["controle"]}
        adi = c["Acórdão da Ação Direta de Inconstitucionalidade nº 4.451 de 21/06/2018"]
        self.assertEqual(adi["decisao"], {"classe": "ADI", "numero": "4451"})
        self.assertEqual({d["efeito"] for d in adi["dispositivos"]}, {"inconstitucional"})
        susp = c["Acórdão da Ação Direta de Inconstitucionalidade nº 5.889 de 06/06/2018"]
        self.assertEqual(susp["dispositivos"][0]["efeito"], "suspenso")
        self.assertEqual(susp["dispositivos"][0]["art"], "59-a")
        const = c["Acórdão da Ação Direta de Inconstitucionalidade nº 5.794 de 29/06/2018"]
        self.assertEqual(const["dispositivos"], [])
        res = c["Resolução do Senado Federal nº 19 de 17/06/1974"]
        self.assertEqual(res["dispositivos"][0]["efeito"], "inconstitucional")
        self.assertNotIn("decisao", res)

    def test_resumo(self):
        r = senado.resumo(self.r)
        self.assertEqual(r["inconstitucionais"], 4)
        self.assertEqual(r["artigos_afetados"], ["45", "59-a", "789"])

    def test_nao_encontrada(self):
        self.assertIsNone(senado.converter({"DetalheDocumento": {"documentos": ""}}))


class TestOrdem(unittest.TestCase):
    def test_ordem(self):
        normas = [{"id": "a", "sha": "1", "peso": 1}, {"id": "b", "sha": "2", "peso": 9},
                  {"id": "c", "sha": "3", "peso": 0}, {"id": "d", "sha": "4", "peso": 0},
                  {"id": "e", "sha": "5", "peso": 0}]
        estado = {"c": {"em": "2026-11-01", "sha": "x"}, "d": {"em": "2026-01-01", "sha": "4"},
                  "e": {"em": "2026-11-01", "sha": "5"}}
        fila = coletar.ordem_de_coleta(normas, estado, date(2026, 11, 4))
        self.assertEqual([n["id"] for n in fila], ["b", "a", "c", "d"])


class TestResumoArquivo(unittest.TestCase):
    def test_adi_json(self):
        with tempfile.TemporaryDirectory() as d:
            coletar.gravar_resumo_adi(Path(d), {"x": {"em": "2026-11-04", "inc": 2, "arts": ["5"]},
                                                 "y": {"em": "2026-11-04", "inc": 0}})
            self.assertEqual(json.loads((Path(d) / "adi.json").read_text()),
                             {"x": {"inconstitucionais": 2, "artigos": ["5"]}})


if __name__ == "__main__":
    unittest.main()
