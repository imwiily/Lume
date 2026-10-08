"""Deduplicação entre detectores (estabilização, Fase 6a).

Os mecanismos foram reunidos em `deduplicacao` sem mudar o comportamento. `CriterioAtual` fixa o
que cada um faz hoje, inclusive o que ainda não é correto (`LimitacoesRegistradas`: coincidência
de trecho basta, sem provar que o fenômeno é o mesmo); a Fase 6b muda isso de propósito.
O LanguageTool é simulado.
"""
import unittest
from unittest.mock import patch
from urllib.error import URLError

from fonte import deduplicacao, grammar, pipeline
from fonte.deduplicacao import (contido, gramatica_sob_languagetool, languagetool_sob_regras_linguisticas, mesmo_id,
                                relacao_que_repete_tempo_verbal, sobrepoe, tempo_verbal_sob_relacao)
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate

from tests.test_languagetool import Response, match


def ocorrencia(p, s, e, **campos):
    return {"paragraph": p, "start": s, "end": e, "category": "X", "source": "FONTE", **campos}


class Intervalos(unittest.TestCase):
    def test_overlap_and_containment(self):
        a = ocorrencia(1, 5, 10)
        self.assertTrue(sobrepoe(a, ocorrencia(1, 9, 12)))       # parcial
        self.assertFalse(sobrepoe(a, ocorrencia(1, 10, 12)))     # vizinhos, sem caractere comum
        self.assertFalse(sobrepoe(a, ocorrencia(2, 5, 10)))      # outro parágrafo
        self.assertTrue(contido(a, ocorrencia(1, 5, 10)))
        self.assertTrue(contido(a, ocorrencia(1, 0, 20)))
        self.assertFalse(contido(a, ocorrencia(1, 6, 20)))


class CriterioAtual(unittest.TestCase):
    def test_languagetool_under_fonte_linguistic_rule(self):
        fonte = [ocorrencia(1, 5, 10, rule="espacamento")]
        lt = [ocorrencia(1, 8, 12, source="LanguageTool local · X"), ocorrencia(1, 10, 12, source="LanguageTool local · Y")]
        self.assertEqual(languagetool_sob_regras_linguisticas(lt, fonte), [lt[1]])

    def test_grammar_under_languagetool_ignores_other_fonte_findings(self):
        anteriores = [ocorrencia(1, 0, 4, source="LanguageTool local · X"), ocorrencia(1, 20, 30, rule="espacamento")]
        gramatica = [ocorrencia(1, 2, 6, rule="crase"), ocorrencia(1, 22, 25, rule="crase")]
        self.assertEqual(gramatica_sob_languagetool(gramatica, anteriores), [gramatica[1]])

    def test_relation_that_repeats_the_tense_alert(self):
        tempo = [ocorrencia(1, 0, 5, category="Tempo verbal")]
        repete = ocorrencia(1, 10, 15, temporal_evidence={"target_form": "past"},
                            related=[{"paragraph": 1, "start": 0, "end": 5}])
        outra_forma = dict(repete, temporal_evidence={"target_form": "present"})
        outro_trecho = dict(repete, related=[{"paragraph": 1, "start": 0, "end": 4}])
        self.assertEqual(relacao_que_repete_tempo_verbal([repete, outra_forma, outro_trecho], tempo, "past"),
                         [outra_forma, outro_trecho])
        self.assertEqual(relacao_que_repete_tempo_verbal([repete], tempo, None), [repete])

    def test_tense_alert_inside_a_relation(self):
        tempo = [ocorrencia(1, 2, 4, category="Tempo verbal"), ocorrencia(1, 2, 9, category="Tempo verbal"),
                 ocorrencia(1, 2, 4, category="Estrutura da frase")]
        relacao = [ocorrencia(1, 0, 6)]
        self.assertEqual(tempo_verbal_sob_relacao(tempo, relacao), tempo[1:])

    def test_same_id_between_stages(self):
        a = ocorrencia(1, 0, 3, id="a")
        self.assertEqual(mesmo_id([dict(a), ocorrencia(1, 4, 5, id="b"), ocorrencia(1, 4, 5, id="b")], [a]),
                         [ocorrencia(1, 4, 5, id="b")])
        with self.assertRaises(ValueError):
            mesmo_id([dict(a, end=4)], [a])

    def test_observer_sees_each_discard_without_changing_the_result(self):
        vistos = []
        fonte = [ocorrencia(1, 5, 10)]
        lt = [ocorrencia(1, 5, 10, source="LanguageTool local · X")]
        with patch.object(deduplicacao, "observar", lambda m, item, causa: vistos.append((m, item, causa))):
            self.assertEqual(languagetool_sob_regras_linguisticas(lt, fonte), [])
        self.assertEqual(vistos, [("languagetool_sob_regras_linguisticas", lt[0], fonte)])


class LimitacoesRegistradas(unittest.TestCase):
    """Comportamento atual que a Fase 6b reavalia: o trecho basta, o fenômeno não é comparado."""

    def test_different_phenomena_on_the_same_span_are_still_merged(self):
        # Pontuação do FONTE e ortografia do LanguageTool que tocam o mesmo trecho: o LT cai.
        fonte = [ocorrencia(1, 0, 8, rule="pontuacao_duplicada")]
        lt = [ocorrencia(1, 7, 12, source="LanguageTool local · MORFOLOGIK_RULE_PT_BR")]
        self.assertEqual(languagetool_sob_regras_linguisticas(lt, fonte), [])

    def test_precedence_is_inverted_between_stages(self):
        # Etapa linguística: o FONTE vence; morfossintática: o LanguageTool vence.
        lt = ocorrencia(1, 0, 5, source="LanguageTool local · X")
        fonte = ocorrencia(1, 0, 5, rule="crase")
        self.assertEqual(languagetool_sob_regras_linguisticas([lt], [fonte]), [])
        self.assertEqual(gramatica_sob_languagetool([fonte], [lt]), [])


class Pipeline(unittest.TestCase):
    """Etapa linguística com o LanguageTool simulado (sem modelo de linguagem)."""
    TEXTO = "Ela parou,, e olhou."

    def rodar(self, respostas, languagetool=True):
        regras = {r: False for r in validate({})["rules"]}
        regras["pontuacao_duplicada"] = True
        with patch("fonte.languagetool.build_opener") as builder:
            builder.return_value.open.side_effect = respostas
            achados, avisos, _ = run([Block(1, self.TEXTO)], lambda: None, settings=validate({"rules": regras}),
                                     mode="linguistica", languagetool=languagetool)
        return achados, avisos

    def test_two_sources_one_span(self):
        mesmo = match(self.TEXTO, ",,", "DOUBLE_PUNCTUATION", "typographical", "PUNCTUATION")
        outro = match(self.TEXTO, "olhou", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")
        achados, _ = self.rodar(lambda request, timeout: Response([mesmo, outro]))
        self.assertEqual([(f["excerpt"], f["source"].split(" · ")[0]) for f in achados],
                         [(",,", "FONTE Linguístico"), ("olhou", "LanguageTool local")])

    def test_languagetool_off_keeps_fonte_alone(self):
        ligado, _ = self.rodar(lambda request, timeout: Response([]))
        desligado, avisos = self.rodar(None, languagetool=False)
        self.assertEqual([f["id"] for f in ligado], [f["id"] for f in desligado])
        self.assertTrue(any("sem o corretor gramatical local" in a for a in avisos))

    def test_languagetool_unavailable_stops_the_analysis(self):
        # Comportamento atual: com o LT pedido e fora do ar, não há relatório parcial.
        def fora(request, timeout):
            raise URLError("recusado")
        with self.assertRaisesRegex(ValueError, "LanguageTool local"):
            self.rodar(fora)


class FonteUnica(unittest.TestCase):
    def test_grammar_no_longer_deduplicates(self):
        import inspect
        self.assertNotIn("skip", inspect.signature(grammar.analyze).parameters)
        self.assertIs(pipeline.deduplicacao, deduplicacao)


if __name__ == "__main__":
    unittest.main()
