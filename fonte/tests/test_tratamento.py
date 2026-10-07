"""Tratamento misto: ‘você’ e verbo na forma de ‘tu’ no mesmo trecho.

Casos escritos do zero. A regra só olha um trecho (fala, pensamento ou narração); a mistura entre
falas diferentes do mesmo personagem exige saber quem fala e fica fora do alcance local.
"""
import unittest

import spacy

from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate


class TreatmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def marked(self, text, settings=None):
        found, _, _ = run([Block(1, text)], lambda: self.nlp, tense="passado", mode="ambas",
                          settings=validate(settings or {}))
        return [(f["text"][f["start"]:f["end"]], f["severity"]) for f in found if f.get("rule") == "tratamento"]

    def test_voce_with_second_person_verb(self):
        for nome in ("Rui", "Dalva"):
            for text, verbo in [(f"— Você tinhas razão desde o começo — disse {nome}.", "tinhas"),
                                ("— Você sabe que estás atrasado?", "estás"),
                                ("— Se você me chamas, eu venho.", "chamas"),
                                ("— Você não me ouve, nunca ouves ninguém.", "ouves")]:
                with self.subTest(text=text):
                    self.assertEqual(self.marked(text), [(verbo, "editorial_attention")])

    def test_explanation_is_plain(self):
        found, _, _ = run([Block(1, "— Você fizeste tudo sozinho.")], lambda: self.nlp, tense="passado", mode="ambas")
        reason = next(f["reason"] for f in found if f.get("rule") == "tratamento")
        self.assertTrue(reason.endswith("\n\nNa gramática: uniformidade de tratamento (tu / você)."))

    def test_nouns_contractions_and_one_treatment_are_not_marked(self):
        for text in ["— Você vê as casas e os dias passarem.", "— Você comprou as mesas e as cadeiras?",
                     "— Você tem um desses?", "— Obrigado pelas explicações. Você ajudou muito.",
                     "— Tu sabes que tens razão.", "— Você também gosta de batatas fritas?",
                     "Ela disse que você estava certo e que as coisas iam melhorar."]:
            with self.subTest(text=text):
                self.assertEqual(self.marked(text), [])

    def test_mixture_across_separate_speeches_is_not_judged(self):
        found, _, _ = run([Block(1, "— Você vem amanhã?"), Block(2, "— Tens certeza disso?")],
                          lambda: self.nlp, tense="passado", mode="ambas")
        self.assertFalse(any(f.get("rule") == "tratamento" for f in found))

    def test_rule_can_be_turned_off(self):
        self.assertEqual(self.marked("— Você tinhas razão.", {"rules": {"tratamento": False}}), [])


if __name__ == "__main__":
    unittest.main()
