"""Núcleo de identificação verbal (estabilização, Fase 2a).

As três operações respondem a perguntas diferentes e não se reduzem a uma função binária:
`certamente_verbo` (identificação positiva), `pode_ser_verbo` (identificação conservadora) e
`ha_forma_verbal` (verificação de presença). Estes testes caracterizam o comportamento herdado,
sem melhorá-lo: as discordâncias abaixo existem de propósito.
"""
import unittest

import spacy

from fonte import analysis, grammar, lexicon, temporal, verbo
from fonte.verbo import certamente_verbo, ha_forma_verbal, pode_ser_verbo

FRASES = ["A garra segura o menino com força.", "Por onde pousa a ave, nada cresce.", "É porque choveu.",
          "A fila só crescia.", "Quando ele cantar, todos param.", "Ela abre a janela.",
          "O seu braço causa coceira.", "Uma nova era começa."]


class VerbCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def token(self, frase, palavra):
        return next(t for t in self.nlp(frase) if t.text == palavra)

    def test_certain_implies_possible(self):
        # A identificação conservadora começa pela positiva: o que é certamente verbo pode ser verbo.
        for frase in FRASES:
            for t in self.nlp(frase):
                with self.subTest(frase=frase, palavra=t.text):
                    self.assertTrue(not certamente_verbo(t) or pode_ser_verbo(t))

    def test_possible_but_not_certain_in_verb_position(self):
        # Homógrafo nome/verbo na posição do verbo: basta para não dizer “sem verbo”, não para alertar.
        for frase, palavra in [("A garra segura o menino com força.", "segura"),
                               ("O seu braço causa coceira.", "causa")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (False, True, False))

    def test_presence_without_certainty(self):
        # Forma que o léxico conhece também como não finita (“cantar”): há forma verbal, mas não é
        # certamente um verbo finito.
        t = self.token("Quando ele cantar, todos param.", "cantar")
        self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (False, False, True))

    def test_all_three_agree_on_clear_verbs(self):
        for frase, palavra in [("Ela abre a janela.", "abre"), ("A fila só crescia.", "crescia"),
                               ("É porque choveu.", "choveu")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (True, True, True))


class SingleDefinitionTests(unittest.TestCase):
    """Cada operação tem uma definição só, no núcleo; os módulos usam o núcleo."""

    def test_old_duplicates_are_gone(self):
        self.assertFalse(hasattr(analysis, "verbo_finito_possivel"))
        self.assertFalse(hasattr(grammar, "verbal"))
        self.assertFalse(hasattr(lexicon, "finite"))
        self.assertFalse(hasattr(lexicon, "model_finite"))

    def test_modules_use_the_core(self):
        self.assertIs(analysis.pode_ser_verbo, verbo.pode_ser_verbo)
        self.assertIs(analysis.certamente_verbo, verbo.certamente_verbo)
        self.assertIs(grammar.ha_forma_verbal, verbo.ha_forma_verbal)
        self.assertIs(temporal.certamente_verbo, verbo.certamente_verbo)


if __name__ == "__main__":
    unittest.main()
