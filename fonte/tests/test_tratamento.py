"""Regra `tratamento` retirada em 07/10/2026 por decisão do autor.

Ela nasceu de um caso isolado e não apontou nada em textos reais. A chave continua aceita nas
configurações salvas, sem efeito, como as demais regras retiradas.
"""
import unittest

import spacy

from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import RULES, RETIRED_RULES, validate


class RetiredTreatmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def test_saved_settings_with_the_key_still_open(self):
        for valor in (True, False):
            with self.subTest(valor=valor):
                self.assertNotIn("tratamento", validate({"rules": {"tratamento": valor}})["rules"])
        self.assertIn("tratamento", RETIRED_RULES)
        self.assertNotIn("tratamento", RULES)

    def test_no_alert_even_when_the_saved_settings_turn_it_on(self):
        found, _, _ = run([Block(1, "— Você tinhas razão desde o começo — disse ela.")], lambda: self.nlp,
                          settings=validate({"rules": {"tratamento": True}}), tense="passado", mode="ambas")
        self.assertFalse(any(f.get("rule") == "tratamento" or f["category"] == "Tratamento" for f in found))


if __name__ == "__main__":
    unittest.main()
