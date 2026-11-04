import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coletar  # noqa: E402
import ementa as em  # noqa: E402


def alteradas(texto, data="2023-05-01"):
    return em.normas_alteradas(texto, data)


class TestEmenta(unittest.TestCase):
    def test_altera_simples(self):
        self.assertEqual(
            alteradas("Altera a Lei nº 8.078, de 11 de setembro de 1990 (Código de Defesa do Consumidor), "
                      "para dispor sobre a Lei nº 9.099, de 1995."),
            [("lei", "8078", 1990, "altera")])

    def test_plural_e_revoga(self):
        self.assertEqual(
            alteradas("Altera as Leis nºs 8.078, de 11 de setembro de 1990, e 9.099, de 26 de setembro de 1995, "
                      "e revoga o Decreto-Lei nº 2.848, de 1940."),
            [("lei", "8078", 1990, "altera"), ("lei", "9099", 1995, "altera"), ("del", "2848", 1940, "revoga")])

    def test_artigos_e_constituicao(self):
        self.assertEqual(alteradas("Altera os arts. 5º e 6º da Lei nº 8.069, de 13 de julho de 1990."),
                         [("lei", "8069", 1990, "altera")])
        self.assertEqual(alteradas("Dá nova redação ao art. 14 da Constituição Federal."),
                         [("constituicao", "", 1988, "altera")])
        self.assertEqual(alteradas("Acrescenta parágrafo ao art. 121 do Decreto-Lei nº 2.848, de 7 de dezembro de 1940 - Código Penal."),
                         [("del", "2848", 1940, "altera")])

    def test_so_cita(self):
        self.assertEqual(alteradas("Dispõe sobre a criação de fundo, nos termos da Lei nº 8.666, de 1993."), [])
        self.assertEqual(alteradas(""), [])

    def test_situacao(self):
        self.assertTrue(em.em_tramitacao("Aguardando Parecer do Relator na Comissão de Saúde (CSAUDE)"))
        self.assertTrue(em.em_tramitacao("Pronta para Pauta no Plenário (PLEN)"))
        self.assertTrue(em.em_tramitacao("Aguardando Apreciação pelo Senado Federal"))
        for s in ("Arquivada", "Transformado em Norma Jurídica", "Retirado pelo(a) Autor(a)",
                  "Aguardando Remessa ao Arquivo", "Tramitação Finalizada", "Perdeu a Eficácia", "Vetado totalmente", "", None):
            self.assertFalse(em.em_tramitacao(s), s)

    def test_norma_gerada(self):
        self.assertEqual(em.norma_gerada("urn:lex:br:federal:lei:2019-09-20;13874"), ("lei", "13874", 2019))
        self.assertEqual(em.norma_gerada("urn:lex:br:federal:lei.complementar:2000-05-04;101"), ("lcp", "101", 2000))
        self.assertEqual(em.norma_gerada(None, "Transformado na Lei Ordinária 13.874/2019"), ("lei", "13874", 2019))
        self.assertIsNone(em.norma_gerada("", "Aguardando Parecer"))


class TestColeta(unittest.TestCase):
    def test_ponta_a_ponta(self):
        with tempfile.TemporaryDirectory() as t:
            data, cache = Path(t) / "data", Path(t) / "cache"
            (data / "index").mkdir(parents=True)
            cache.mkdir()
            ids = ["federal/leis-ordinarias/1990/lei-8078-1990-09-11",
                   "federal/leis-ordinarias/2019/lei-13874-2019-09-20"]
            (data / "index" / "leis-ordinarias.json").write_text(json.dumps([{"id": i} for i in ids]))
            (data / "index" / "constituicao.json").write_text(json.dumps([{"id": "constituicao"}]))
            resolver, conhecidos = coletar.carregar_resolvedor(data)
            props = [
                {"id": 1, "siglaTipo": "PL", "numero": 10, "ano": 2023, "dataApresentacao": "2023-02-01T10:00",
                 "ementa": "Altera a Lei nº 8.078, de 11 de setembro de 1990, para tratar de X.",
                 "ultimoStatus": {"descricaoSituacao": "Aguardando Parecer do Relator", "dataHora": "2024-03-01T10:00"}},
                {"id": 2, "siglaTipo": "PL", "numero": 11, "ano": 2023, "dataApresentacao": "2023-02-02",
                 "ementa": "Altera a Lei nº 8.078, de 1990.", "ultimoStatus": {"descricaoSituacao": "Arquivada"}},
                {"id": 3, "siglaTipo": "MPV", "numero": 881, "ano": 2019, "dataApresentacao": "2019-04-30",
                 "ementa": "Institui a Declaração de Direitos de Liberdade Econômica.",
                 "urnFinal": "urn:lex:br:federal:lei:2019-09-20;13874",
                 "ultimoStatus": {"descricaoSituacao": "Transformado em Norma Jurídica"}},
                {"id": 4, "siglaTipo": "REQ", "numero": 1, "ano": 2023, "ementa": "Altera a Lei nº 8.078, de 1990."},
                {"id": 5, "siglaTipo": "PEC", "numero": 2, "ano": 2023, "dataApresentacao": "2023-03-01",
                 "ementa": "Altera o art. 5º da Constituição Federal.",
                 "ultimoStatus_descricaoSituacao": "Pronta para Pauta no Plenário (PLEN)"},
            ]
            itens = coletar.resumir_ano(props, resolver)
            self.assertEqual([i["id"] for i in itens], [1, 2, 3, 5])
            (cache / "2023.json").write_text(json.dumps({"ano": 2023, "baixado_em": "x", "itens": itens}))
            resumo = coletar.montar_saida(cache, data, conhecidos)
            self.assertEqual(resumo["normas_com_projetos"], 2)
            cdc = json.loads((data / "camara/normas" / (ids[0] + ".json")).read_text())
            self.assertEqual([p["sigla"] for p in cdc["tramitando"]], ["PL 10/2023"])
            self.assertEqual(cdc["encerrados"], 1)
            lle = json.loads((data / "camara/normas" / (ids[1] + ".json")).read_text())
            self.assertEqual(lle["origem"][0]["sigla"], "MPV 881/2019")
            self.assertTrue((data / "camara/normas/constituicao.json").exists())
            # Norma que deixou de ter projetos perde o arquivo.
            (cache / "2023.json").write_text(json.dumps({"ano": 2023, "baixado_em": "x", "itens": []}))
            coletar.montar_saida(cache, data, conhecidos)
            self.assertFalse((data / "camara/normas" / (ids[0] + ".json")).exists())

    def test_escolher_anos(self):
        with tempfile.TemporaryDirectory() as t:
            cache = Path(t)
            for a in range(coletar.PRIMEIRO_ANO, 2027):
                (cache / f"{a}.json").write_text(json.dumps({"baixado_em": f"2026-01-{a % 28 + 1:02d}"}))
            (cache / "1990.json").unlink()
            anos = coletar.escolher_anos(cache, 2026, 3, False)
            self.assertEqual(anos[:3], [1990, 2026, 2025])
            self.assertEqual(len(anos), 6)


if __name__ == "__main__":
    unittest.main()
