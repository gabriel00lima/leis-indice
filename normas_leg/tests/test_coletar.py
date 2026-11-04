import json, sys, unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coletar as c  # noqa: E402

U = "urn:lex:br:federal:constituicao:1988-10-05;1988"
T = "https://normas.leg.br/tipo-de-dispositivo/?urn=urn:lex:br:federal:tipo.dispositivo:"


def no(frag, tipo, texto=None, nome=None, filhos=None, versoes=None):
    we = versoes or {"legislationDate": "1988-10-05", "text": texto, "name": nome}
    d = {"legislationIdentifier": f"{U}!{frag}", "legislationType": {"@id": T + tipo}, "workExample": we}
    if filhos:
        d["hasPart"] = filhos
    return d


ARVORE = {
    "@type": "Legislation", "legislationIdentifier": U, "headline": "Constituição", "dateModified": "2026-10-16",
    "hasPart": {"hasPart": [
        no("preambulo", "preambulo", 'Preâmbulo <lx:p xmlns="x">Nós, representantes</lx:p>'),
        no("articulacao", "articulacao", filhos=[
            no("tit1", "titulo", "Dos Princípios Fundamentais", "TÍTULO I", filhos=[
                no("art1", "artigo", nome="Art. 1º", filhos=[
                    no("art1_cpt", "caput", "A República <span xlink:href='x'>Federativa</span>:", filhos=[
                        no("art1_cpt_inc1", "inciso", "a soberania;", "I –")]),
                    no("art1_par1u", "paragrafo", "Todo o poder emana do povo.", "Parágrafo único.")]),
                no("art103-2,emc-45-2004-12-08", "artigo", nome="Art. 103-B.", filhos=[
                    no("art103-2_cpt,emc-45-2004-12-08", "caput", versoes=[
                        {"legislationDate": "2004-12-08", "text": "Texto antigo."},
                        {"legislationDate": "2009-11-11", "text": "Texto novo."}])]),
            ])]),
    ]},
}


class TestColetor(unittest.TestCase):
    def test_id_artigo(self):
        self.assertEqual(c.id_artigo("art5"), "art-5")
        self.assertEqual(c.id_artigo("art103-2,emc-45-2004-12-08"), "art-103-b")
        self.assertEqual(c.id_artigo("art1196"), "art-1196")
        self.assertIsNone(c.id_artigo("art5_cpt"))
        self.assertIsNone(c.id_artigo("tit1"))

    def test_resumir(self):
        r = c.resumir(ARVORE, com_texto=True)
        self.assertEqual(r["artigos"], {"art-1": "art1", "art-103-b": "art103-2,emc-45-2004-12-08"})
        md = r["texto_md"]
        self.assertIn("## TÍTULO I — Dos Princípios Fundamentais", md)
        self.assertIn("**Art. 1º** A República Federativa:", md)
        self.assertIn("I – a soberania;", md)
        self.assertIn("Parágrafo único. Todo o poder emana do povo.", md)
        self.assertIn("**Art. 103-B.** Texto novo.", md)   # versão mais recente
        self.assertNotIn("Texto antigo", md)
        self.assertTrue(md.startswith("Nós, representantes"))
        self.assertNotIn("texto_md", c.resumir(ARVORE, com_texto=False))

    def test_sem_estrutura(self):
        self.assertIsNone(c.resumir({"@type": "Legislation", "encoding": []}, True))

    def test_escapar(self):
        self.assertEqual(c.escapar_md("1. item"), r"1\. item")
        self.assertEqual(c.escapar_md("- traço"), r"\- traço")

    def test_fila(self):
        ref = datetime(2026, 11, 4, tzinfo=timezone.utc)
        indice = {"a": "u", "b": "u", "c": "u", "d": "u"}
        estado = {"b": {"v": c.VERSAO, "em": "2026-11-03T00:00:00+00:00"},
                  "c": {"v": c.VERSAO, "em": "2026-01-01T00:00:00+00:00"},
                  "d": {"v": c.VERSAO, "em": "2026-11-03T00:00:00+00:00"}}
        # d é prioridade mas foi vista ontem; b nova não; a nunca vista; c vencida.
        self.assertEqual(c.fila(indice, estado, ["d", "x"], set(), ref), ["a", "c"])
        self.assertEqual(c.fila(indice, {}, ["d"], {"b"}, ref)[:2], ["d", "b"])


if __name__ == "__main__":
    unittest.main()
