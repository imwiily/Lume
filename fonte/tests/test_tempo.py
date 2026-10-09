"""Núcleo de classificação de tempo e modo (estabilização, Fase 3).

Duas políticas estritas diferentes de propósito (`tempo_estrito` para as relações temporais,
`tempo_narrativo` para a regra de tempo verbal) e uma recuperação (`tempo_recuperado`) que serve de
âncora quando o modelo erra a classe. Os casos têm ambiguidades reais: homógrafos nome/verbo,
presente e perfeito iguais, mais-que-perfeito igual ao presente, modo do modelo.
`LimitacoesRegistradas` guarda comportamentos atuais que não são corretos e ficam para uma fase
com mudança de comportamento; corrigi-los deve mudar esses testes de propósito.
"""
import unittest

import spacy

from fonte import grammar, temporal, tempo, verbo
from fonte.tempo import (imperfeito, imperfeito_do_subjuntivo, mais_que_perfeito_composto, modo_do_imperfeito,
                         passado_so_no_lexico, tempo_estrito, tempo_narrativo, tempo_recuperado)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def token(self, frase, palavra):
        return next(t for t in self.nlp(frase) if t.text == palavra)


class StrictVersusRecoveryTests(Base):
    def test_clear_indicative_forms_agree(self):
        for frase, palavra, estrito, narrativo in [("Ele abre a porta.", "abre", "present", "presente"),
                                                   ("Ele abriu a porta.", "abriu", "past", "passado"),
                                                   ("Ninguém sabia o que fazer.", "sabia", "past", "passado")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((tempo_estrito(t), tempo_recuperado(t), tempo_narrativo(t)),
                                 (estrito, estrito, narrativo))

    def test_recovery_reads_verb_the_model_called_adjective(self):
        # “segura”: o modelo diz adjetivo; a estrita não classifica, a recuperação dá presente.
        t = self.token("Ela segura a mochila e sai.", "segura")
        self.assertEqual((tempo_estrito(t), tempo_recuperado(t)), (None, "present"))

    def test_present_and_preterite_homographs(self):
        # “vira”: presente de virar ou mais-que-perfeito de ver. A estrita não decide; a recuperação
        # usa o lema (-ar) e dá presente.
        t = self.token("Ele vira a esquina devagar.", "vira")
        self.assertEqual((tempo_estrito(t), tempo_recuperado(t)), ("ambiguous_past_present", "present"))
        # 1ª do plural igual no presente e no perfeito: ambígua na estrita; passado só como âncora.
        t = self.token("Passamos a tarde na praia.", "Passamos")
        self.assertEqual((tempo_estrito(t), tempo_recuperado(t), tempo_narrativo(t)),
                         ("ambiguous_past_present", "past", None))

    def test_narrative_policy_accepts_lexical_past_without_model_mood(self):
        # A política narrativa aceita o passado pelo léxico; a estrita exige o indicativo do modelo.
        for frase, palavra in [("Conheci-o numa festa.", "Conheci-o"), ("Era tarde quando voltou.", "Era")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((tempo_estrito(t), tempo_narrativo(t)), (None, "passado"))

    def test_conditional_and_subjunctive_are_not_indicative_tenses(self):
        t = self.token("Nós construiríamos uma casa.", "construiríamos")
        self.assertEqual((tempo_estrito(t), tempo_narrativo(t)), ("conditional", None))
        for frase, palavra in [("Se ele fosse rico, viajaria.", "fosse"), ("Quando ele cantar, todos param.", "cantar")]:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual((tempo_estrito(t), tempo_recuperado(t), tempo_narrativo(t)), (None, None, None))


class MorphologyTests(Base):
    def test_imperfect_subjunctive_excludes_indicative_readings(self):
        self.assertTrue(imperfeito_do_subjuntivo(self.token("Se ele fosse rico, viajaria.", "fosse")))
        # “disse”: pretérito perfeito, mesma terminação, leitura no indicativo.
        self.assertFalse(imperfeito_do_subjuntivo(self.token("Ele disse que viria.", "disse")))

    def test_imperfect_mood_is_separated_by_the_lexicon(self):
        # Corrigido na Fase 7b (antes, em LimitacoesRegistradas: condicional e subjuntivo passavam
        # como imperfeito). A terminação sozinha não decide: “queria” e “ia” são imperfeito do
        # indicativo, “faria” não.
        casos = [("Ela cantava baixinho.", "cantava", "indicativo"), ("Ele queria sair cedo.", "queria", "indicativo"),
                 ("Ela ia ao mercado.", "ia", "indicativo"), ("Era tarde.", "Era", "indicativo"),
                 ("Ele faria tudo de novo.", "faria", "condicional"),
                 ("Nós construiríamos uma casa.", "construiríamos", "condicional"),
                 ("Ela deveria voltar.", "deveria", "condicional"),
                 ("Se ele fosse rico, viajaria.", "fosse", "subjuntivo"),
                 ("Pediu que ela cantasse.", "cantasse", "subjuntivo")]
        for frase, palavra, modo in casos:
            with self.subTest(palavra=palavra):
                t = self.token(frase, palavra)
                self.assertEqual(modo_do_imperfeito(t), modo)
                self.assertEqual(imperfeito(t), modo == "indicativo")

    def test_unknown_form_with_imperfect_ending_stays_ambiguous(self):
        t = self.token("O grifo zurlava no alto.", "zurlava")
        self.assertEqual((modo_do_imperfeito(t), imperfeito(t)), ("ambiguo", True))

    def test_compound_pluperfect(self):
        self.assertTrue(mais_que_perfeito_composto(self.token("Ela tinha esquecido a chave.", "tinha")))
        self.assertFalse(mais_que_perfeito_composto(self.token("Ela tinha uma chave.", "tinha")))

    def test_lexical_past_recovery_for_present_narration(self):
        self.assertTrue(passado_so_no_lexico(self.token("Ele abriu a porta.", "abriu")))
        self.assertFalse(passado_so_no_lexico(self.token("Ele abre a porta.", "abre")))


class LimitacoesRegistradas(Base):
    """Comportamentos atuais registrados na Fase 3, sem correção (exigem mudança de comportamento)."""

    def test_recovery_ignores_mood(self):
        # Subjuntivo ou imperativo que o modelo marca como tal ainda sai “presente” na recuperação.
        for frase, palavra in [("Fale com ela agora.", "Fale"), ("Vamos embora.", "Vamos")]:
            with self.subTest(palavra=palavra):
                self.assertEqual(tempo_recuperado(self.token(frase, palavra)), "present")


class SingleDefinitionTests(unittest.TestCase):
    def test_old_duplicates_are_gone(self):
        for modulo, nome in [(temporal, "form"), (temporal, "event_tense"), (temporal, "sole_verb"),
                             (temporal, "IMPERFECT_SUBJUNCTIVE"), (temporal, "CONDITIONAL_ENDING"),
                             (grammar, "imperfect_subjunctive"), (grammar, "CONDITIONAL"),
                             (grammar, "IMPERFECT_SUBJUNCTIVE"), (verbo, "indicative_tense")]:
            with self.subTest(nome=nome):
                self.assertFalse(hasattr(modulo, nome))

    def test_modules_use_the_core(self):
        self.assertIs(temporal.tempo_estrito, tempo.tempo_estrito)
        self.assertIs(temporal.tempo_recuperado, tempo.tempo_recuperado)
        self.assertIs(grammar.imperfeito_do_subjuntivo, tempo.imperfeito_do_subjuntivo)
        self.assertIs(grammar.TERMINACAO_CONDICIONAL, tempo.TERMINACAO_CONDICIONAL)


if __name__ == "__main__":
    unittest.main()
