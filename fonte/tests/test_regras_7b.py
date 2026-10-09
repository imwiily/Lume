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


class VerbosDeFala(unittest.TestCase):
    """Formas que faltavam ao perfil do inciso (ênclise, mais-que-perfeito) e o radical que não vale
    contra o lema de outro verbo onde o verbo de fala é condição do alerta."""

    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def rodar(self, texto, *regras, modo="ambas"):
        from fonte.pipeline import run
        from fonte.settings import validate
        ligadas = {r: r in regras for r in validate({})["rules"]}
        achados, _, _ = run(blocos(texto), lambda: self.nlp, settings=validate({"rules": ligadas}), tense="passado",
                            mode=modo)
        return [(f["category"], f["excerpt"]) for f in achados]

    def test_enclitic_and_pluperfect_speech_tags_are_not_actions(self):
        for texto in ["— Vamos embora — disse-me ela.", "— Vamos embora — dissera ela.", "— Vamos embora — falara ela."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.rodar(texto, "dialogo_contextual"), [])
        self.assertTrue(self.rodar("— Vamos embora — abriu a porta.", "dialogo_contextual"))

    def test_quoted_speech_with_enclitic_tag(self):
        self.assertEqual(self.rodar("“Volto amanhã”, disse-me ela à saída.", "pontuacao_dialogo"), [])

    def test_que_after_ellipsis_needs_a_verb_that_asks_for_que(self):
        self.assertEqual(self.rodar("Ela prometeu… Que voltaria antes do inverno.", "frase_cortada"),
                         [("Maiúscula após reticências", "Que")])
        # “sentou” é de sentar; o radical de “sentir” não vale contra o lema do modelo.
        self.assertEqual(self.rodar("Ela sentou… Que a noite passasse logo, pensava.", "frase_cortada"), [])


class AspasComoNarracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def dialogo(self, texto, **opcoes):
        from fonte.pipeline import run
        from fonte.settings import validate
        regras = {r: r == "pontuacao_dialogo" for r in validate({})["rules"]}
        achados, _, _ = run(blocos(texto), lambda: self.nlp, settings=validate({"rules": regras, **opcoes}), tense="passado")
        return [f["excerpt"] for f in achados if f["category"] == "Pontuação de diálogo"]

    def test_quotes_as_speech_keep_the_check(self):
        texto = "“Já volto”, ela abriu a porta e saiu."
        self.assertTrue(self.dialogo(texto))
        self.assertTrue(self.dialogo(texto, quotes_role="pensamento"))

    def test_quotes_as_narration_have_no_speech_tag_to_check(self):
        self.assertEqual(self.dialogo("“Já volto”, ela abriu a porta e saiu.", quotes_role="narracao"), [])


class RegrasFrageis(unittest.TestCase):
    """Restrições da Fase 7b em regras sem decisões suficientes, cada uma por uma classe linguística."""

    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def linguisticas(self, texto, regra):
        from fonte.linguistic import analyze
        from fonte.settings import validate
        regras = {r: r == regra for r in validate({})["rules"]}
        return [f["text"][f["start"]:f["end"]].strip() for f in analyze(blocos(texto), validate({"rules": regras}))]

    def test_vocative_vs_inverted_subject_question(self):
        self.assertEqual(self.linguisticas("Marta você vem amanhã?", "vocativo"), ["Marta"])
        self.assertEqual(self.linguisticas("Bento não faça isso.", "vocativo"), ["Bento"])
        for texto in ["Quer você dar uma volta pela praça?", "Pode você esperar um instante?"]:
            with self.subTest(texto=texto):
                self.assertEqual(self.linguisticas(texto, "vocativo"), [])

    def test_lowercase_after_interjection(self):
        for texto in ["Ah! tu pensavas que eu esqueceria.", "Oh! você chegou cedo."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.linguisticas(texto, "capitalizacao_contextual"), [])
        self.assertEqual(self.linguisticas("Você vem? ele perguntou baixinho.", "capitalizacao_contextual"), ["ele"])
        self.assertEqual(self.linguisticas("Que susto! ela disse depois.", "capitalizacao_contextual"), ["ela"])

    def test_que_nao_after_conclusive_connective(self):
        for texto in ["A chuva não parou, pelo que, não havendo barco, ficamos.",
                      "Estava tudo pronto, de modo que, não restando nada, saímos."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.linguisticas(texto, "virgula_que_nao"), [])
        self.assertEqual(self.linguisticas("Ela disse que, não iria à festa.", "virgula_que_nao"), ["que, não"])

    def concordancias(self, texto):
        from fonte.grammar import analyze
        from fonte.settings import validate
        regras = {r: r == "concordancia" for r in validate({})["rules"]}
        return [f["text"][f["start"]:f["end"]] for f in analyze(blocos(texto), self.nlp, validate({"rules": regras}))
                if f["category"] == "Concordância nominal"]

    def test_compound_colour_is_invariable(self):
        for texto in ["O casaco tinha botões azul claro e golas largas.", "Vestia camisas verde garrafa no inverno."]:
            with self.subTest(texto=texto):
                self.assertEqual(self.concordancias(texto), [])
        # Cor simples continua variando: “sapatos vermelho” segue apontado.
        self.assertEqual(self.concordancias("Ela usava sapatos vermelho."), ["sapatos vermelho"])
        self.assertEqual(self.concordancias("Os quadros antigo ficaram no porão."), ["quadros antigo"])

    def test_enclitic_verb_is_not_a_work_term(self):
        from fonte.editorial.entities import capitalization
        termos = [f["text"][f["start"]:f["end"]] for f in capitalization(blocos(
            "Ele chegou e, Disse-me o guarda, a porta abriu.", "Depois, disse-me ela, tudo mudou."))]
        self.assertEqual(termos, [])
        compostos = [f["text"][f["start"]:f["end"]] for f in capitalization(blocos(
            "Ele viu a Mulher-Corvo no telhado.", "Contaram que a mulher-corvo voltou."))]
        self.assertEqual(compostos, ["mulher-corvo"])
