"""Testes do registro de novidades (indice/novidades.py) e dos feeds RSS (site/feeds.py)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "indice"))
sys.path.insert(0, str(RAIZ / "site"))
import feeds  # noqa: E402
import novidades  # noqa: E402

AMB = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}

CDC = "federal/leis-ordinarias/1990/lei-8078-1990-09-11"
ALTERA = "federal/leis-ordinarias/2021/lei-14181-2021-07-01"
MP = "federal/medidas-provisorias/2026/mpv-1393-2026-09-25"


def git(pasta, *args):
    return subprocess.run(["git", "-C", str(pasta), *args], check=True, capture_output=True, text=True, env=AMB).stdout


def texto(arts):
    return "---\ntitulo: \"Lei\"\n---\n# Lei\n\n" + "".join(f"**Art. {n}º** {t}\n\n" for n, t in arts)


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fonte, self.repo = self.tmp / "fonte", self.tmp / "repo"
        for p in (self.fonte, self.repo):
            p.mkdir()
            git(p, "init", "-q")

    def blob(self, conteudo):
        return subprocess.run(["git", "-C", str(self.fonte), "hash-object", "-w", "--stdin"], input=conteudo,
                              check=True, capture_output=True, text=True).stdout.strip()

    def gravar_cache(self, shas):
        cache = self.repo / "data" / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "leis-ordinarias.json").write_text(json.dumps({c: [s, []] for c, s in shas.items()}))

    def test_eventos(self):
        v1 = self.blob(texto([(1, "a"), (2, "b")]))
        v2 = self.blob(texto([(1, "a mudou"), (3, "c")]))
        outra = self.blob(texto([(1, "x")]))
        nova = self.blob(texto([(1, "y")]))
        self.gravar_cache({CDC + ".md": v1, "federal/leis-ordinarias/1991/lei-1-1991-01-01.md": outra})
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "antes")
        self.gravar_cache({CDC + ".md": v2, "federal/leis-ordinarias/2026/lei-2-2026-01-01.md": nova})

        r = novidades.registrar(self.fonte, self.repo / "data", self.repo, hoje="2026-11-04")
        self.assertEqual((r["texto"], r["nova"], r["removida"]), (1, 1, 1))
        evs = json.loads((self.repo / "data" / "novidades.json").read_text())["eventos"]
        texto_ev = next(e for e in evs if e["evento"] == "texto")
        self.assertEqual(texto_ev["id"], CDC)
        self.assertEqual(texto_ev["mudanca"]["alterados"], ["Art. 1º"])
        self.assertEqual(texto_ev["mudanca"]["incluidos"], ["Art. 3º"])
        self.assertEqual(texto_ev["mudanca"]["removidos"], ["Art. 2º"])

        # Rodar de novo sem commit no meio não duplica: o registro antigo é preservado
        # e os eventos do dia se repetem só se o cache mudar de novo.
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "depois")
        r = novidades.registrar(self.fonte, self.repo / "data", self.repo, hoje="2026-11-05")
        self.assertEqual(r["novos"], 0)
        self.assertEqual(r["total"], 3)

    def test_primeira_execucao_nao_registra(self):
        self.gravar_cache({CDC + ".md": self.blob("x")})
        r = novidades.registrar(self.fonte, self.repo / "data", self.repo, hoje="2026-11-04")
        self.assertEqual(r["novos"], 0)

    def test_registro_antigo_expira(self):
        data = self.repo / "data"
        data.mkdir()
        novidades.escrever_registro(data / "novidades.json",
                                    [{"em": "2020-01-01", "id": CDC, "evento": "texto"}], "")
        self.gravar_cache({CDC + ".md": self.blob("x")})
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "c")
        r = novidades.registrar(self.fonte, data, self.repo, hoje="2026-11-04")
        self.assertEqual(r["total"], 0)


class TestFeeds(unittest.TestCase):
    def montar(self, eventos=(), monitor=()):
        site = Path(tempfile.mkdtemp())
        data = site / "data"
        (data / "index").mkdir(parents=True)
        (data / "adjacencia").mkdir()
        normas = [
            {"id": CDC, "titulo": "Lei nº 8.078 de 11/09/1990", "tipo": "Lei Ordinária", "data": "1990-09-11",
             "ementa": "Dispõe sobre a proteção do consumidor.", "revogada": False},
            {"id": ALTERA, "titulo": "Lei nº 14.181 de 01/07/2021", "tipo": "Lei Ordinária", "data": "2021-07-01",
             "ementa": "Superendividamento.", "revogada": False},
        ]
        (data / "index" / "leis-ordinarias.json").write_text(json.dumps(normas))
        (data / "adjacencia" / "leis-ordinarias.json").write_text(json.dumps({
            CDC: {"alterada_por": [ALTERA, MP, "externo:lei-1-1900"], "revogada_por": [], "citada_por": [ALTERA]},
        }))
        (data / "index.json").write_text(json.dumps({"shards": [
            {"categoria": "leis-ordinarias", "arquivo": "index/leis-ordinarias.json",
             "adjacencia": "adjacencia/leis-ordinarias.json"}]}))
        (data / "arestas.json").write_text(json.dumps({"links": [
            {"de": ALTERA, "para": CDC, "tipo": "altera", "dispositivos": ["art. 54-A"]}]}))
        (data / "novidades.json").write_text(json.dumps({"eventos": list(eventos)}))
        mon = site / "monitor.json"
        mon.write_text(json.dumps(list(monitor)))
        feeds.main(["--site", str(site), "--url", "https://ex.org/s/", "--monitor", str(mon)])
        return site

    def itens(self, arq):
        raiz = ET.parse(arq).getroot()
        return [{c.tag: c.text for c in it} for it in raiz.iter("item")]

    def test_feed_da_norma(self):
        site = self.montar(eventos=[{"em": "2026-11-04", "id": CDC, "evento": "texto", "commit": "abc",
                                     "mudanca": {"incluidos": [], "alterados": ["Art. 49"], "removidos": []}}])
        itens = self.itens(site / "feed" / f"{CDC}.xml")
        titulos = [i["title"] for i in itens]
        # Mais novo primeiro; citação não entra; norma "externo:" (sem data) não entra.
        self.assertEqual(titulos, ["Texto atualizado no acervo", "Alterada por Medida Provisória nº 1.393/2026",
                                   "Alterada por Lei nº 14.181 de 01/07/2021"])
        self.assertIn("art. 49", itens[0]["description"])
        self.assertIn("art. 54-A", itens[2]["description"])
        self.assertEqual(itens[2]["link"], f"https://ex.org/s/lei/{ALTERA}")
        self.assertEqual(itens[1]["link"], f"https://ex.org/s/lei.html?id={MP}")
        # Norma sem alterações também tem feed (vazio), para poder ser seguida.
        self.assertEqual(self.itens(site / "feed" / f"{ALTERA}.xml"), [])
        geral = self.itens(site / "feed" / "novidades.xml")
        self.assertEqual(geral[0]["title"], "Texto atualizado: Lei nº 8.078 de 11/09/1990")

    def test_aviso_do_monitor_complementa_a_mudanca(self):
        site = self.montar(
            eventos=[{"em": "2026-11-04", "id": CDC, "evento": "texto"}],
            monitor=[{"em": "2026-11-05", "id": CDC, "titulo": "Mudança", "resumo": "- O prazo do **art. 49** mudou.",
                      "issue": "https://github.com/x/y/issues/1"}])
        item = self.itens(site / "feed" / f"{CDC}.xml")[0]
        self.assertIn("O prazo do art. 49 mudou.", item["description"])
        self.assertIn("issues/1", item["description"])
        self.assertEqual(sum(i["title"] == "Texto atualizado no acervo" for i in self.itens(site / "feed" / f"{CDC}.xml")), 1)

    def test_dia_com_muitas_mudancas_vira_um_item_no_feed_geral(self):
        evs = [{"em": "2026-11-04", "id": CDC, "evento": "texto"}] * feeds.AGRUPAR_A_PARTIR_DE
        site = self.montar(eventos=evs)
        geral = self.itens(site / "feed" / "novidades.xml")
        self.assertTrue(geral[0]["title"].startswith(f"{feeds.AGRUPAR_A_PARTIR_DE} normas"))


if __name__ == "__main__":
    unittest.main()
