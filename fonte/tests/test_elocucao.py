"""Verbos de fala, pensamento e percepção (estabilização, Fase 5).

Uma só fonte (`elocucao`) com perfis nomeados. Cada consumidor usa o seu perfil, que reproduz a
lista antiga sem ampliar nem unir. `ListasAntigas` fixa o conteúdo de antes da Fase 5;
`PorConsumidor` mostra o que cada regra reconhece, com positivos e negativos de elocução,
pensamento, percepção e verbos que pedem “que”.
"""
import unittest

import spacy

from fonte import analysis, elocucao, grammar, languagetool, temporal
from fonte.editorial import context
from fonte.elocucao import (ATESTA, CATEGORIAS, COMENTARIO_DO_NARRADOR, CONTEXTO, ELOCUCAO, INCISO, NARRADOR_ANUNCIA,
                            PEDEM_QUE, PENSAMENTO, PERCEPCAO, RELATO, forma_de_fala, pede_completiva, verbo_de_fala)


class ListasAntigas(unittest.TestCase):
    """Conteúdo das listas antes da Fase 5 (analysis.SPEECH, grammar.COMPLEMENT_VERBS, temporal.REPORTING,
    temporal.NARRATOR_THAT, NARRATOR_TELLS e a lista de “poder” + infinitivo)."""

    def test_profiles_keep_the_old_lists(self):
        self.assertEqual(INCISO, set(
            "dizer informar perguntar responder murmurar gritar sussurrar comentar retrucar afirmar falar exclamar "
            "replicar declarar indagar confessar explicar acrescentar argumentar insistir ordenar pedir protestar avisar "
            "pensar refletir ponderar admitir lembrar concluir continuar completar interromper balbuciar resmungar "
            "cochichar implorar vociferar anunciar observar sugerir repetir garantir negar confirmar questionar reclamar "
            "ironizar brincar saudar chamar ler recitar citar ditar cantar declamar terminar".split()))
        self.assertEqual(set(f for formas in elocucao.INCISO_IRREGULARES.values() for f in formas),
                         {"disse", "disseram", "diz", "dizem", "dizia", "diziam", "dirá", "pediu", "pediram", "pede", "pedia"})
        self.assertEqual(PEDEM_QUE, ("prometer", "jurar", "avisar", "contar", "achar", "saber", "acreditar", "garantir",
                                     "sentir", "perceber", "imaginar", "esperar", "temer", "lembrar", "esquecer",
                                     "decidir", "admitir"))
        self.assertEqual(RELATO, {"dizer", "explicar", "contar", "afirmar", "saber", "aprender", "ensinar", "descobrir",
                                  "lembrar", "perceber", "entender", "ler", "ouvir", "achar", "pensar", "acreditar",
                                  "notar", "garantir"})
        self.assertEqual(temporal.NARRATOR_THAT, {"acho", "sinto", "sei", "creio", "acredito", "confesso", "admito",
                                                  "imagino", "espero", "lembro", "garanto", "juro", "suponho", "quero",
                                                  "penso", "reconheço"})
        self.assertEqual(temporal.NARRATOR_TELLS.pattern,
                         r"vou\s+(?:\w+\s+)?(?:contar|narrar|relatar|explicar|falar|dizer|começar|descrever|"
                         r"mostrar|resumir|apresentar)\b")
        self.assertEqual(ATESTA, {"confirmar", "afirmar", "garantir", "dizer", "atestar"})

    def test_every_profile_verb_has_one_category(self):
        perfis = [INCISO, PEDEM_QUE, RELATO, COMENTARIO_DO_NARRADOR, NARRADOR_ANUNCIA, ATESTA]
        todos = set().union(*map(set, perfis))
        self.assertEqual(todos, set(CATEGORIAS))
        self.assertEqual(set(CATEGORIAS.values()), {ELOCUCAO, PENSAMENTO, PERCEPCAO, CONTEXTO})

    def test_profiles_mix_categories_as_before(self):
        # Diferenças legítimas (e registradas): o inciso aceita pensamento, “observar” e verbos que só
        # são fala no contexto; os que pedem “que” incluem percepção (“sentir”, “perceber”).
        def categorias(perfil):
            return {c: sorted(v for v in perfil if CATEGORIAS[v] == c) for c in (PENSAMENTO, PERCEPCAO, CONTEXTO)}
        self.assertEqual(categorias(INCISO), {
            PENSAMENTO: ["lembrar", "pensar", "ponderar", "refletir"], PERCEPCAO: ["observar"],
            CONTEXTO: ["brincar", "cantar", "chamar", "completar", "continuar", "interromper", "ler", "terminar"]})
        self.assertEqual(categorias(PEDEM_QUE)[PERCEPCAO], ["perceber", "sentir"])
        self.assertEqual(categorias(RELATO)[PERCEPCAO], ["notar", "ouvir", "perceber"])


class PorConsumidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def token(self, frase, palavra):
        return next(t for t in self.nlp(frase) if t.text == palavra)

    def test_speech_tag_profile(self):
        # Pontuação de diálogo, diálogo contextual, pronome reto, vírgula sujeito-verbo.
        for frase, palavra, esperado in [
                ("— Vamos — disse ela.", "disse", True),           # elocução
                ("— Vamos — perguntou ela.", "perguntou", True),
                ("— Vamos — pensou ela.", "pensou", True),          # pensamento
                ("— Vamos — continuou ela.", "continuou", True),    # só pelo contexto
                ("— Vamos — ouviu ela.", "ouviu", False),           # percepção
                ("— Vamos — viu ela.", "viu", False),
                ("— Vamos — achou ela.", "achou", False),           # pede “que”, não é inciso
                ("— Vamos — sentiu ela.", "sentiu", False),
                ("— Vamos — abriu a porta.", "abriu", False)]:      # ação
            with self.subTest(palavra=palavra):
                self.assertEqual(verbo_de_fala(self.token(frase, palavra)), esperado)

    def test_speech_tag_by_written_form(self):
        # Diálogo contextual (verbo logo após o travessão) e crase do LanguageTool: só a forma escrita.
        # “dissera”, “falara” e “disse-me”: mais-que-perfeito e ênclise, reconhecidos desde a Fase 7b.
        for forma in ["disse", "Perguntei", "respondemos", "murmurava", "pensou", "pediu", "dirá", "dizendo",
                      "dissera", "falara", "disse-me", "dissera-lhe"]:
            with self.subTest(forma=forma):
                self.assertTrue(forma_de_fala(forma))
        for forma in ["ouviu", "viu", "achou", "sentiu", "abriu", "leu", "dissesse"]:
            with self.subTest(forma=forma):
                self.assertFalse(forma_de_fala(forma))

    def test_short_stem_needs_the_lemma(self):
        # “ler” tem radical curto: só o lema do modelo o reconhece, não a forma.
        self.assertFalse(forma_de_fala("leu"))
        self.assertTrue(verbo_de_fala(self.token("— Pronto — leu ela.", "leu")))

    def test_verbs_that_take_que_after_ellipsis(self):
        # Frase cortada: “prometi… Que voltaria” (inciso ou `PEDEM_QUE`).
        for forma in ["prometi", "jurou", "achava", "senti", "percebeu", "disse", "pensei"]:
            with self.subTest(forma=forma):
                self.assertTrue(pede_completiva(forma))
        for forma in ["ouvi", "vi", "notou", "abri", "saí"]:
            with self.subTest(forma=forma):
                self.assertFalse(pede_completiva(forma))

    def test_reported_content_profile(self):
        # Tempo verbal: verdade geral e discurso indireto, pelo lema.
        for lema in ["dizer", "saber", "ouvir", "notar", "pensar"]:
            self.assertIn(lema, RELATO)
        for lema in ["sentir", "ver", "perguntar", "murmurar"]:
            self.assertNotIn(lema, RELATO)

    def test_narrator_comment_and_announcement(self):
        for frase, palavra, esperado in [("Acho que vai chover.", "Acho", True),
                                         ("Sinto que devo partir.", "Sinto", True),
                                         ("Vejo que você chegou.", "Vejo", False),
                                         ("Sinto o frio na pele.", "Sinto", False),
                                         ("Vou contar como foi.", "Vou", True),
                                         ("Vou até a porta.", "Vou", False)]:
            with self.subTest(frase=frase):
                self.assertEqual(temporal.narrator_frame(self.token(frase, palavra)), esperado)


class FonteUnica(unittest.TestCase):
    def test_old_duplicates_are_gone(self):
        for modulo, nome in [(analysis, "SPEECH"), (analysis, "IRREGULARES_DE_FALA"), (analysis, "TERMINACOES"),
                             (analysis, "forma_de_fala"), (grammar, "COMPLEMENT_VERBS"), (grammar, "complement_verb"),
                             (grammar, "verb_de_fala_form"), (temporal, "REPORTING")]:
            with self.subTest(nome=nome):
                self.assertFalse(hasattr(modulo, nome))

    def test_consumers_use_the_core(self):
        self.assertIs(analysis.verbo_de_fala, elocucao.verbo_de_fala)
        self.assertIs(grammar.verbo_de_fala, elocucao.verbo_de_fala)
        self.assertIs(grammar.pede_completiva_confirmada, elocucao.pede_completiva_confirmada)
        self.assertIs(context.verbo_de_fala_confirmado, elocucao.verbo_de_fala_confirmado)
        self.assertIs(context.verbo_de_fala, elocucao.verbo_de_fala)
        self.assertIs(context.forma_de_fala, elocucao.forma_de_fala)
        self.assertIs(languagetool.forma_de_fala, elocucao.forma_de_fala)
        self.assertIs(temporal.RELATO, elocucao.RELATO)
        self.assertIs(temporal.TERMINACOES, elocucao.TERMINACOES)


if __name__ == "__main__":
    unittest.main()
