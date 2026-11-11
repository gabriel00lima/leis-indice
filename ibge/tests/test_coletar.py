import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coletar  # noqa: E402

UF_SP = {"id": 35, "sigla": "SP", "nome": "São Paulo", "regiao": {"id": 3, "sigla": "SE", "nome": "Sudeste"}}
UF_MT = {"id": 51, "sigla": "MT", "nome": "Mato Grosso", "regiao": {"id": 5, "sigla": "CO", "nome": "Centro-Oeste"}}


class TestColetar(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(coletar.slug("São João d'Aliança"), "sao-joao-d-alianca")
        self.assertEqual(coletar.slug("  Embu-Guaçu "), "embu-guacu")

    def test_estados(self):
        e = coletar.normalizar_estados([UF_SP, UF_MT])
        self.assertEqual([x["sigla"] for x in e], ["MT", "SP"])
        self.assertEqual(e[1]["capital"], 3550308)
        self.assertEqual(e[1]["regiao"], {"codigo": 3, "sigla": "SE", "nome": "Sudeste"})

    def test_municipios_nivelado_sem_duplicatas(self):
        bruto = [
            {"municipio-id": 3550308, "municipio-nome": "São Paulo", "UF-sigla": "SP"},
            {"municipio-id": 3550308, "municipio-nome": "São Paulo", "UF-sigla": "SP"},
            {"municipio-id": 3500105, "municipio-nome": "Adamantina", "UF-sigla": "SP"},
        ]
        self.assertEqual(coletar.normalizar_municipios(bruto), [
            [3500105, "Adamantina", "SP", "adamantina", 0],
            [3550308, "São Paulo", "SP", "sao-paulo", 1],
        ])

    def test_municipios_aninhado_microrregiao_nula(self):
        bruto = [
            {"id": 5101837, "nome": "Boa Esperança do Norte", "microrregiao": None,
             "regiao-imediata": {"regiao-intermediaria": {"UF": UF_MT}}},
            {"id": 3550308, "nome": "São Paulo",
             "microrregiao": {"mesorregiao": {"UF": UF_SP}}},
        ]
        ufs = [l[2] for l in coletar.normalizar_municipios(bruto)]
        self.assertEqual(ufs, ["MT", "SP"])

    def test_espelho_csv(self):
        e, m = coletar.do_espelho(
            "\ufeffcodigo_uf,uf,nome,latitude,longitude,regiao\n35,SP,São Paulo,-22,-48,Sudeste\n",
            "codigo_ibge,nome,latitude,longitude,capital,codigo_uf\n3550308,São Paulo,-23,-46,1,35\n",
        )
        self.assertEqual(coletar.normalizar_estados(e)[0]["regiao"], {"codigo": 3, "sigla": "SE", "nome": "Sudeste"})
        self.assertEqual(coletar.normalizar_municipios(m), [[3550308, "São Paulo", "SP", "sao-paulo", 1]])

    def test_validar_rejeita_resposta_incompleta(self):
        with self.assertRaises(SystemExit):
            coletar.validar(coletar.normalizar_estados([UF_SP]), [])

    def test_gravar_idempotente(self):
        estados = coletar.normalizar_estados([UF_SP])
        mun = [[3550308, "São Paulo", "SP", "sao-paulo", 1]]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.assertTrue(coletar.gravar(p, estados, mun))
            antes = (p / "index.json").read_text()
            self.assertFalse(coletar.gravar(p, coletar.normalizar_estados([UF_SP]), mun))
            self.assertEqual((p / "index.json").read_text(), antes)
            m = json.loads((p / "municipios.json").read_text())
            self.assertEqual(m["campos"][:3], ["codigo", "nome", "uf"])
            self.assertEqual(json.loads((p / "estados.json").read_text())[0]["municipios"], 1)


if __name__ == "__main__":
    unittest.main()
