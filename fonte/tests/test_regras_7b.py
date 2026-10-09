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


class FraseCortadaReticencias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def cortadas(self, texto):
        from fonte.grammar import analyze
        from fonte.settings import validate
        regras = {r: False for r in validate({})["rules"]}
        regras["frase_cortada"] = True
        return [(f["category"], f["text"][f["start"]:f["end"]])
                for f in analyze(blocos(texto), self.nlp, validate({"rules": regras}))]

    def test_three_dots_are_an_ellipsis_like_the_single_character(self):
        for texto in ["— A ponte fica perto da...", "— A ponte fica perto da…", "O barco seguiu na direção de..."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.cortadas(texto), [])

    def test_sentence_cut_before_a_full_stop_is_still_flagged(self):
        self.assertEqual(self.cortadas("O barco seguiu na direção de. Depois parou."), [("Frase cortada", "de")])

    def test_capital_que_after_three_dots_is_still_checked(self):
        self.assertEqual(self.cortadas("Eu prometi... Que voltaria antes do inverno."), [("Maiúscula após reticências", "Que")])


class CraseDativa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def crases(self, texto):
        from fonte.grammar import analyze
        from fonte.settings import validate
        regras = {r: False for r in validate({})["rules"]}
        regras["crase"] = True
        return [f["text"][f["start"]:f["end"]] for f in analyze(blocos(texto), self.nlp, validate({"rules": regras}))
                if f["category"] == "Crase ausente"]

    def test_feminine_recipient_after_direct_object_is_still_flagged(self):
        for texto, esperado in [("Ela entregou o pacote a vizinha.", "a vizinha"),
                                ("O rapaz mostrou o mapa a professora.", "a professora")]:
            with self.subTest(texto=texto):
                self.assertEqual(self.crases(texto), [esperado])

    def test_recipient_already_expressed_means_direct_object(self):
        for texto in ["Ela contou ao neto a lenda do rio.", "O pai mostrou aos filhos a fazenda inteira.",
                      "Ele entregou-lhe a encomenda.", "Mostrei-lhes a cidade antiga."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.crases(texto), [])

    def test_prepositional_pronoun_is_not_the_direct_object(self):
        self.assertEqual(self.crases("Ele levou consigo a lanterna."), [])
