"""Segmentação entre fala e narração (estabilização, Fase 4).

Só estrutura: quem é fala, narração, pensamento ou sinal, na posição original. As duas leituras
(`classify`, atual; `narrative_masks`, antiga) usam as mesmas peças de `segments` e diferem de
propósito em pontos registrados no plano; `DiferencasPreservadas` mostra cada um.
"""
import unittest

from fonte.analysis import narrative_masks
from fonte.reader import Block
from fonte.segments import (abre_fala, classify, marcar_travessoes, percorrer_aspas, spans,
                            termina_em_travessao)
from fonte.settings import validate


def papeis(texto, **opcoes):
    """Trechos (texto, papel) de um parágrafo, sem os sinais."""
    bloco = Block(1, texto, italic=opcoes.pop("italic", []))
    labels, = classify([bloco], validate(opcoes))
    return [(texto[s:e].strip(), papel) for s, e, papel in spans(labels, {"narracao", "dialogo", "pensamento"})
            if texto[s:e].strip()]


class StructureTests(unittest.TestCase):
    def test_dash_speech_with_speech_tag_and_resumed_speech(self):
        self.assertEqual(papeis("— Vamos embora — disse ela. — Agora!"),
                         [("Vamos embora", "dialogo"), ("disse ela.", "narracao"), ("Agora!", "dialogo")])

    def test_action_after_speech_is_structure_only(self):
        # A segmentação não julga se “ela abriu a porta” deveria ser verbo de fala.
        self.assertEqual(papeis("— Vamos — ela abriu a porta."),
                         [("Vamos", "dialogo"), ("ela abriu a porta.", "narracao")])

    def test_quoted_speech_and_quote_roles(self):
        texto = "Ela disse “volto já” e saiu."
        self.assertEqual(papeis(texto), [("Ela disse", "narracao"), ("volto já", "dialogo"), ("e saiu.", "narracao")])
        self.assertEqual(papeis(texto, quotes_role="pensamento")[1], ("volto já", "pensamento"))
        self.assertEqual(papeis(texto, quotes_role="narracao"), [("Ela disse “volto já” e saiu.", "narracao")])

    def test_narration_before_and_after_dialogue_and_line_breaks(self):
        self.assertEqual(papeis("Ela entrou.\n— Preciso de água — pediu."),
                         [("Ela entrou.", "narracao"), ("Preciso de água", "dialogo"), ("pediu.", "narracao")])

    def test_two_speeches_in_one_paragraph(self):
        self.assertEqual([p for _, p in papeis("— Oi — disse ele. — Tchau.")], ["dialogo", "narracao", "dialogo"])

    def test_hyphen_dialogue_and_compound_words(self):
        self.assertEqual(papeis("- Vamos - disse ele."), [("Vamos", "dialogo"), ("disse ele.", "narracao")])
        self.assertEqual(papeis("O bem-vindo sorriso dela."), [("O bem-vindo sorriso dela.", "narracao")])

    def test_italic_thoughts_are_not_dialogue(self):
        texto = "Talvez chova, pensou."
        self.assertEqual(papeis(texto, italic=[(0, 13)])[0], ("Talvez chova,", "pensamento"))
        self.assertEqual(papeis(texto, italic=[(0, 13)], italic_thoughts=False), [(texto, "narracao")])

    def test_dashes_can_be_turned_off(self):
        self.assertEqual(papeis("— Vamos — disse.", dialogue_dashes=False), [("— Vamos — disse.", "narracao")])


class SharedPiecesTests(unittest.TestCase):
    def test_quote_walk_crosses_paragraphs_and_warns(self):
        blocos = [Block(1, "“Começa aqui"), Block(2, "e termina” depois.")]
        (m1, f1), (m2, f2) = percorrer_aspas(blocos, repete_abertura=False)[0]
        self.assertEqual((m1[0], m1[5], m2[0]), ("abre", "dentro", "dentro"))
        self.assertEqual(f2, [9])
        _, avisos = percorrer_aspas([Block(1, "“Sem fim")], repete_abertura=False)
        self.assertTrue(any("sem fechamento" in a for a in avisos))
        _, avisos = percorrer_aspas([Block(1, "“Aberta"), Block(2, "Capítulo 2", heading=True)], repete_abertura=False)
        self.assertTrue(any("antes do título" in a for a in avisos))

    def test_dash_marking_modes(self):
        texto = "— Fala — disse.\n- Outra - disse."
        atual = marcar_travessoes(texto, ["narracao"] * len(texto))
        antiga = marcar_travessoes(texto, ["narracao"] * len(texto), por_linha=False, hifen=False)
        self.assertEqual(atual[texto.index("Outra")], "dialogo")
        self.assertNotEqual(antiga[texto.index("Outra")], "dialogo")

    def test_local_checks(self):
        self.assertTrue(abre_fala("— Vamos."))
        self.assertTrue(abre_fala("—Vamos."))
        self.assertFalse(abre_fala("—Vamos.", exige_espaco=True))
        self.assertTrue(abre_fala("- Vamos.", exige_espaco=True))
        self.assertTrue(termina_em_travessao("— Vamos? — "))
        self.assertFalse(termina_em_travessao("Ela disse"))


class DiferencasPreservadas(unittest.TestCase):
    """Diferenças entre `classify` (atual) e `narrative_masks` (antiga), preservadas de propósito."""

    def mascara(self, blocos):
        return narrative_masks(blocos)[0]

    def test_hyphen_dialogue_only_in_the_current_reading(self):
        texto = "- Vamos - disse ele."
        self.assertEqual(papeis(texto)[0], ("Vamos", "dialogo"))
        self.assertIn("Vamos", self.mascara([Block(1, texto)])[0])  # antiga: narração visível

    def test_speech_on_a_later_line_only_in_the_current_reading(self):
        texto = "Ela entrou.\n— Fala — disse."
        self.assertIn(("Fala", "dialogo"), papeis(texto))
        self.assertIn("Fala", self.mascara([Block(1, texto)])[0])

    def test_quotes_always_speech_in_the_old_reading(self):
        texto = "Ela disse “volto já” e saiu."
        self.assertEqual(papeis(texto, quotes_role="narracao"), [(texto, "narracao")])
        self.assertNotIn("volto", self.mascara([Block(1, texto)])[0])

    def test_repeated_opening_quote_continues_speech_only_in_the_old_reading(self):
        blocos = [Block(1, '"Abre a fala'), Block(2, '"continua sem fechar')]
        atual = classify(blocos, validate({}))[1]
        self.assertEqual(atual[0], "separador")       # atual: a aspa fecha a fala anterior
        self.assertEqual(atual[5], "narracao")
        self.assertNotIn("continua", self.mascara(blocos)[1])  # antiga: a fala continua


if __name__ == "__main__":
    unittest.main()
