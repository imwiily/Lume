"""Estabilização, Fase 7b: restrições e correções de regras com alarme falso demonstrado.

Cada classe tem positivos (o erro continua apontado), negativos (a construção legítima deixa de
ser) e ambiguidades. Os textos são escritos do zero, com outras palavras e outros nomes.
"""
import unittest

from fonte.reader import Block


def blocos(*textos):
    return [Block(i + 1, t) for i, t in enumerate(textos)]


class PalavraDobrada(unittest.TestCase):
    def dobras(self, texto):
        from fonte.editorial.repetition import analyze
        return [f["text"][f["start"]:f["end"]] for f in analyze(blocos(texto)) if f["rule"] == "palavra_consecutiva"]

    def test_typos_are_still_flagged(self):
        for texto, esperado in [("Ela guardou o o caderno na gaveta.", "o o"),
                                ("Voltamos para para a cidade.", "para para"),
                                ("A estrada era longa a a noite fria.", "a a"),
                                ("Disse que se se ele vier, saímos.", "se se")]:
            with self.subTest(texto=texto):
                self.assertEqual(self.dobras(texto), [esperado])

    def test_enclitic_pronoun_before_homograph_article_or_preposition(self):
        # Pronome ligado ao verbo pelo hífen + artigo ou preposição de mesma forma.
        for texto in ["Encontrou-a a poucos metros da praça.", "Mandou-o o tio para longe.",
                      "Deixei-as as duas na estação.", "Levou-os os primos até a feira."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.dobras(texto), [])

    def test_conjunction_se_before_pronoun_se_needs_a_verb(self):
        for texto in ["Perguntou se se podia entrar.", "Não sei se se lhes contou a verdade.",
                      "Veremos se se não arrependem."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.dobras(texto), [])
        # Sem verbo logo depois, o segundo “se” não é pronome: é dobra.
        self.assertEqual(self.dobras("Fique se se a chuva parar."), ["se se"])

    def test_single_letter_abbreviations(self):
        self.assertEqual(self.dobras("Assinado: R. e E. Duarte, em nome da firma."), [])


if __name__ == "__main__":
    unittest.main()
