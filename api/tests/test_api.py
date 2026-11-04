"""Testes do gerador da API: python -m unittest discover -s api/tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar  # noqa: E402

CDC = "federal/leis-ordinarias/1990/lei-8078-1990-09-11"
LEI_SP = "estaduais/SP/leis-ordinarias/1990/lei-6544-1990-11-22"


def norma(id_, tipo, numero, data, **extra):
    e = {"id": id_, "path": id_ + ".md", "titulo": f"{tipo} nº {numero}", "tipo": tipo,
         "numero": numero, "data": data, "ementa": "Dispõe sobre " + "x" * 300, "revogada": False, "urn": ""}
    e.update(extra)
    return e


class TestGerar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.data, self.saida = raiz / "data", raiz / "api"
        (self.data / "index").mkdir(parents=True)
        (self.data / "adjacencia").mkdir()
        cf = {"id": "constituicao", "path": "constituicao.md", "titulo": "Constituição", "tipo": "Constituição",
              "numero": "", "data": "1988-10-05", "ementa": "", "revogada": False, "urn": ""}
        leis = [norma(CDC, "Lei Ordinária", "8078", "1990-09-11"),
                norma("federal/leis-ordinarias/1995/lei-9008-1995-03-21", "Lei Ordinária", "9008", "1995-03-21")]
        sp = [norma(LEI_SP, "Lei Ordinária", "6544", "1990-11-22")]
        self._json("index/constituicao.json", [cf])
        self._json("index/leis-ordinarias.json", leis)
        # parte no formato compacto {campos, linhas}, como uma parte estadual poderia vir
        campos = list(sp[0])
        self._json("index/sp-leis-ordinarias.json", {"campos": campos, "linhas": [[e[c] for c in campos] for e in sp]})
        self._json("index.json", {"versao": 1, "gerado_em": "2026-11-03T00:00:00+00:00", "total": 4,
                                  "shards": [
                                      {"arquivo": "index/constituicao.json", "adjacencia": "adjacencia/constituicao.json", "tipo": "Constituição"},
                                      {"arquivo": "index/leis-ordinarias.json", "adjacencia": "adjacencia/leis-ordinarias.json", "tipo": "Lei Ordinária"},
                                      {"arquivo": "index/sp-leis-ordinarias.json", "tipo": "Lei Ordinária"}],
                                  "links": {"arquivo": "links.json", "arestas": "arestas.json", "total": 3}})
        self._json("adjacencia/constituicao.json", {"constituicao": {"citada_por": [CDC]}})
        self._json("adjacencia/leis-ordinarias.json", {
            CDC: {"cita": ["constituicao", "externo:dec-1-1900"], "altera": [], "revoga": [], "citada_por": [],
                  "alterada_por": ["federal/leis-ordinarias/1995/lei-9008-1995-03-21"], "revogada_por": []}})
        self._json("links.json", {"versao": 1, "shards": [{"arquivo": "adjacencia/leis-ordinarias.json", "pasta": "leis-ordinarias"},
                                                          {"arquivo": "adjacencia/constituicao.json", "pasta": "constituicao"}]})
        self._json("arestas.json", {"versao": 1, "leis": {}, "links": [
            {"de": CDC, "para": "constituicao", "tipo": "cita", "dispositivos": ["art. 5º"]},
            {"de": "federal/leis-ordinarias/1995/lei-9008-1995-03-21", "para": CDC, "tipo": "altera", "dispositivos": ["art. 39"]},
            {"de": CDC, "para": "externo:dec-1-1900", "tipo": "cita", "dispositivos": []}]})
        self.indice = gerar.gerar(self.data, self.saida, "https://exemplo.org/")
        self.v1 = self.saida / "v1"

    def tearDown(self):
        self.tmp.cleanup()

    def _json(self, rel, obj):
        (self.data / rel).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def ler(self, rel):
        return json.loads((self.v1 / rel).read_text(encoding="utf-8"))

    def test_norma_com_ligacoes_e_dispositivos(self):
        d = self.ler(f"normas/{CDC}.json")
        self.assertEqual(d["numero"], "8078")
        self.assertEqual(d["jurisdicao"], {"esfera": "federal", "uf": None})
        self.assertEqual(d["lista"], "federal/leis-ordinarias")
        self.assertTrue(d["texto"]["markdown"].endswith(CDC + ".md"))
        self.assertEqual(d["paginas"]["lei"], f"https://exemplo.org/lei.html?id={CDC}")
        cita = {v["id"]: v for v in d["ligacoes"]["cita"]}
        self.assertEqual(cita["constituicao"]["dispositivos"], ["art. 5º"])
        self.assertEqual(cita["constituicao"]["api"], "normas/constituicao.json")
        self.assertFalse(cita["externo:dec-1-1900"]["indexada"])
        alt = d["ligacoes"]["alterada_por"][0]
        self.assertEqual(alt["dispositivos"], ["art. 39"])  # artigos desta norma (a alterada)
        self.assertEqual(d["totais"]["alterada_por"], 1)
        self.assertEqual(set(d["ligacoes"]), set(gerar.TIPOS_LIGACAO))

    def test_constituicao_e_norma_sem_ligacoes(self):
        cf = self.ler("normas/constituicao.json")
        self.assertEqual(cf["lista"], "constituicao")
        self.assertEqual(cf["ligacoes"]["citada_por"][0]["dispositivos"], ["art. 5º"])
        sem = self.ler("normas/federal/leis-ordinarias/1995/lei-9008-1995-03-21.json")
        self.assertEqual(sem["totais"]["cita"], 0)

    def test_estadual(self):
        d = self.ler(f"normas/{LEI_SP}.json")
        self.assertEqual(d["jurisdicao"], {"esfera": "estadual", "uf": "SP"})
        self.assertEqual(d["lista"], "estaduais/SP/leis-ordinarias")
        self.assertEqual(self.ler("ref/sp/lei/6544.json")["normas"][0]["id"], LEI_SP)
        self.assertEqual(self.ler("busca/sp.json")["total"], 1)
        self.assertEqual(self.indice["jurisdicoes"]["sp"]["uf"], "SP")
        self.assertEqual(self.indice["jurisdicoes"]["sp"]["busca"], "busca/sp.json")

    def test_listas_busca_ref_e_indice(self):
        lista = self.ler("listas/federal/leis-ordinarias.json")
        self.assertEqual(lista["total"], 2)
        linha = dict(zip(lista["campos"], lista["linhas"][0]))
        self.assertEqual(linha["id"], CDC)
        busca = self.ler("busca/federal.json")
        self.assertEqual(busca["total"], 3)
        ementa = dict(zip(busca["campos"], busca["linhas"][0]))["ementa"]
        self.assertLessEqual(len(ementa), gerar.EMENTA_BUSCA)
        self.assertEqual(self.ler("ref/federal/lei/8078.json")["normas"][0]["api"], f"normas/{CDC}.json")
        self.assertFalse((self.v1 / "ref/federal/constituicao").exists())  # sem número, sem ref
        self.assertEqual(self.indice["total"], 4)
        self.assertEqual(self.ler("index.json")["base"], "https://exemplo.org/api/v1/")
        for l in self.indice["listas"]:
            self.assertTrue((self.v1 / l["arquivo"]).exists())

    def test_ids_auxiliares(self):
        self.assertEqual(gerar.lista_de("federal/decretos-lei/1940/del-2848-1940-12-07"), "federal/decretos-lei")
        self.assertEqual(gerar.prefixo_de("federal/decretos-lei/1940/del-2848-1940-12-07"), "del")
        self.assertEqual(gerar.jurisdicao("municipais/SP/sao-paulo/x")["chave"], "sp-sao-paulo")
        self.assertEqual(gerar.numero_limpo("8.078"), "8078")


if __name__ == "__main__":
    unittest.main()
