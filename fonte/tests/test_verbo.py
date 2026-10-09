"""Núcleo de identificação verbal (estabilização, Fase 2a).

As três operações respondem a perguntas diferentes e não se reduzem a uma função binária:
`certamente_verbo` (identificação positiva), `pode_ser_verbo` (identificação conservadora) e
`ha_forma_verbal` (verificação de presença). As discordâncias abaixo existem de propósito.

Fase 2b (08/10/2026): “segura” e “causa” passam a ser confirmados pela posição entre sujeito e
complemento, e o futuro do subjuntivo igual ao infinitivo passa a “pode ser verbo”. Os testes por
classe ficam em `VerbClassTests`, com contraexemplos.
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

    def test_verb_between_subject_and_complement_is_confirmed(self):
        # Homógrafo nome/verbo que o modelo lê como adjetivo, entre sujeito e complemento (Fase 2b).
        # Na Fase 2a, era só “pode ser verbo”.
        for frase, palavra in [("A garra segura o menino com força.", "segura"),
                               ("O seu braço causa coceira.", "causa")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (True, True, False))

    def test_future_subjunctive_is_possible_but_not_certain(self):
        # Futuro do subjuntivo igual ao infinitivo: pode ser verbo (Fase 2b; antes, não), sem confirmação.
        t = self.token("Quando ele cantar, todos param.", "cantar")
        self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (False, True, True))

    def test_all_three_agree_on_clear_verbs(self):
        for frase, palavra in [("Ela abre a janela.", "abre"), ("A fila só crescia.", "crescia"),
                               ("É porque choveu.", "choveu")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)), (True, True, True))


class VerbClassTests(unittest.TestCase):
    """Classes estruturais da Fase 2b, com frases inventadas e contraexemplos."""

    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def ops(self, frase, palavra):
        t = next(t for t in self.nlp(frase) if t.text == palavra)
        return certamente_verbo(t), pode_ser_verbo(t), ha_forma_verbal(t)

    def test_clause_opener_admits_finite_reading(self):
        # Futuro do subjuntivo depois de subordinante ou relativo: pode ser verbo.
        for frase, palavra in [("Se você partir cedo, avise a família.", "partir"),
                               ("Quando a chuva parar, saímos.", "parar")]:
            with self.subTest(palavra=palavra):
                self.assertTrue(self.ops(frase, palavra)[1])
        # Depois de preposição é infinitivo.
        self.assertFalse(self.ops("Gosto de cantar à noite.", "cantar")[1])

    def test_sentence_opening_with_complement(self):
        for frase, palavra in [("Canto quando estou só.", "Canto"), ("— Preciso falar com você.", "Preciso")]:
            with self.subTest(palavra=palavra):
                self.assertTrue(self.ops(frase, palavra)[1])
        # Nome no início de frase com verbo: segue preposição ou advérbio, não complemento verbal.
        # (Frase nominal sem nenhum verbo, como “Grito no corredor.”, já era “pode ser” pelo critério
        # anterior do verbo único da frase; é ambígua e fica fora destes testes.)
        for frase, palavra in [("Passo a passo, ela subiu.", "Passo"), ("Morro abaixo, o carro descia.", "Morro")]:
            with self.subTest(palavra=palavra):
                self.assertFalse(self.ops(frase, palavra)[1])

    def test_strong_evidence_confirms_verbs_misread_as_nouns(self):
        self.assertTrue(self.ops("Venho explicar tudo amanhã.", "Venho")[0])
        self.assertTrue(self.ops("Uma nova era começa.", "começa")[0])
        # Adjetivo depois de cópula, seguido de infinitivo: não é verbo.
        self.assertFalse(self.ops("É preciso sair agora.", "preciso")[0])
        # Adjetivo posposto que concorda com o nome, sem determinante no complemento.
        self.assertFalse(self.ops("Estudei a tarde inteira sozinha.", "inteira")[0])

    def test_noun_after_determiner_is_not_certain(self):
        self.assertFalse(self.ops("A vida é longa.", "vida")[0])
        self.assertFalse(self.ops("Ela parou no vão da porta.", "vão")[0])
        # Clítico depois de palavra que o atrai: o verbo continua confirmado.
        self.assertTrue(self.ops("Ela não a viu na festa.", "viu")[0])

    def test_lexicon_vetoes_presence_of_non_verbs(self):
        for frase, palavra in [("Oh! que susto.", "Oh"), ("Perdão, meu senhor.", "Perdão")]:
            with self.subTest(palavra=palavra):
                self.assertFalse(self.ops(frase, palavra)[2])
        self.assertTrue(self.ops("É porque choveu.", "choveu")[2])


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
