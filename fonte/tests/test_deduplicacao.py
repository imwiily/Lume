"""Deduplicação entre detectores (estabilização, Fases 6a e 6b).

FONTE × LanguageTool (6b): só o mesmo fenômeno (mesma família) com a mesma correção vira uma
ocorrência; trecho em comum não basta. Tempo verbal × coerência temporal e o mesmo ID entre etapas
seguem a Fase 6a. O LanguageTool é simulado.
"""
import unittest
from unittest.mock import patch
from urllib.error import URLError

from fonte import deduplicacao, grammar, pipeline
from fonte.deduplicacao import (consolidar, contido, equivalentes, mesmo_id, relacao_que_repete_tempo_verbal, sobrepoe,
                                tempo_verbal_sob_relacao)
from fonte.pipeline import run
from fonte.politica import aplicar
from fonte.reader import Block
from fonte.settings import validate

from tests.test_languagetool import Response, match


def ocorrencia(p, s, e, **campos):
    return {"paragraph": p, "start": s, "end": e, "category": "X", "source": "FONTE", **campos}


TEXTO = "Ele começou à mexer na caixa e ela parou,, depois saiu , mas voltou para para casa."


def alerta(trecho, origem, sugestao=None, **campos):
    """Ocorrência no formato do relatório, no `TEXTO`. `origem` em maiúsculas é uma regra do
    LanguageTool; em minúsculas, uma regra do FONTE."""
    inicio = TEXTO.index(trecho)
    lt = origem.isupper()
    item = {"id": f"{origem}:{inicio}", "paragraph": 1, "start": inicio, "end": inicio + len(trecho), "text": TEXTO,
            "category": "Ortografia e gramática" if lt else "X", "suggestion": sugestao, "module": "linguistic",
            "source": f"LanguageTool local · {origem}" if lt else f"FONTE · {origem}",
            "rule": "languagetool" if lt else origem, "confidence": "média"}
    item.update(campos)
    return item


class Intervalos(unittest.TestCase):
    def test_overlap_and_containment(self):
        a = ocorrencia(1, 5, 10)
        self.assertTrue(sobrepoe(a, ocorrencia(1, 9, 12)))       # parcial
        self.assertFalse(sobrepoe(a, ocorrencia(1, 10, 12)))     # vizinhos, sem caractere comum
        self.assertFalse(sobrepoe(a, ocorrencia(2, 5, 10)))      # outro parágrafo
        self.assertTrue(contido(a, ocorrencia(1, 5, 10)))
        self.assertTrue(contido(a, ocorrencia(1, 0, 20)))
        self.assertFalse(contido(a, ocorrencia(1, 6, 20)))


class Equivalencia(unittest.TestCase):
    def test_same_phenomenon_same_correction_partial_overlap(self):
        # Crase: o LT aponta um trecho maior; a correção do parágrafo é a mesma.
        self.assertTrue(equivalentes(alerta("à mexer", "crase", "a mexer"),
                                     alerta("começou à mexer", "CRASE_CONFUSION", "começou a mexer")))
        # Espaço antes de vírgula: trechos diferentes, mesmo texto corrigido.
        self.assertTrue(equivalentes(alerta(" ,", "espacamento", ","),
                                     alerta("saiu ,", "SPACE_BEFORE_PUNCTUATION2", "saiu,")))

    def test_repeated_word_has_an_implicit_correction(self):
        self.assertTrue(equivalentes(alerta("para para", "palavra_consecutiva"),
                                     alerta("para para", "PORTUGUESE_WORD_REPEAT_RULE", "para")))

    def test_same_span_different_phenomena_stay_apart(self):
        # Mesmo trecho e mesma correção, mas famílias diferentes (palavra dobrada × contração).
        self.assertFalse(equivalentes(alerta("para para", "palavra_consecutiva"),
                                      alerta("para para", "CONTRACOES_OBRIGATORIAS", "para")))
        # Regra do LT fora das famílias.
        self.assertFalse(equivalentes(alerta("à mexer", "crase", "a mexer"), alerta("à mexer", "OUTRA_REGRA", "a mexer")))

    def test_same_family_needs_a_compatible_correction(self):
        fonte = alerta("à mexer", "crase", "a mexer")
        self.assertFalse(equivalentes(fonte, alerta("à mexer", "CRASE_CONFUSION", "à mexê")))   # outra correção
        self.assertFalse(equivalentes(fonte, alerta("à mexer", "CRASE_CONFUSION")))             # sem correção
        # Sem correção do FONTE (como em “Dois pontos finais”, que pode ser reticências): os dois ficam.
        self.assertFalse(equivalentes(alerta(",,", "pontuacao_duplicada"), alerta(",,", "DOUBLE_PUNCTUATION", ",")))
        self.assertTrue(equivalentes(alerta(",,", "pontuacao_duplicada", ","), alerta(",,", "DOUBLE_PUNCTUATION", ",")))

    def test_no_common_character_is_never_a_duplicate(self):
        self.assertFalse(equivalentes(alerta("para para", "palavra_consecutiva"),
                                      alerta("voltou", "PORTUGUESE_WORD_REPEAT_RULE", "voltou")))


class Consolidacao(unittest.TestCase):
    def test_principal_keeps_identity_and_records_the_absorbed(self):
        fonte = alerta("à mexer", "crase", "a mexer", confidence="alta", severity="probable_error",
                       module="morphosyntactic")
        lt = alerta("começou à mexer", "CRASE_CONFUSION", "começou a mexer", severity="probable_error")
        outro = alerta("parou", "MORFOLOGIK_RULE_PT_BR", "parou")
        resultado, por_etapa = consolidar([lt, outro, fonte])
        self.assertEqual([f["id"] for f in resultado], [outro["id"], fonte["id"]])
        self.assertEqual(por_etapa, {"linguistic": 1})
        principal = resultado[1]
        self.assertEqual(principal["detectores"], ["FONTE · crase", "LanguageTool local · CRASE_CONFUSION"])
        absorvido, = principal["absorvidos"]
        self.assertEqual((absorvido["id"], absorvido["classe"], absorvido["rule"], absorvido["familia"]),
                         (lt["id"], "languagetool:gramatica", "languagetool", "crase"))
        # Classe e regra da principal não mudam; a absorvida não entra nas medições.
        mesa, _ = aplicar(resultado)
        self.assertEqual([(f["classe"], f["rule"]) for f in mesa],
                         [("languagetool:ortografia", "languagetool"), ("crase", "crase")])

    def test_different_phenomena_keep_both(self):
        itens = [alerta("para para", "palavra_consecutiva"), alerta("para para", "CONTRACOES_OBRIGATORIAS", "para")]
        resultado, por_etapa = consolidar(list(itens))
        self.assertEqual(resultado, itens)
        self.assertEqual(por_etapa, {})
        self.assertNotIn("absorvidos", resultado[0])

    def test_observer_sees_each_absorption_without_changing_the_result(self):
        vistos = []
        fonte, lt = alerta(" ,", "espacamento", ","), alerta("saiu ,", "SPACE_BEFORE_PUNCTUATION2", "saiu,")
        with patch.object(deduplicacao, "observar", lambda m, item, causa: vistos.append((m, item["id"], causa[0]["id"]))):
            resultado, _ = consolidar([fonte, lt])
        self.assertEqual([f["id"] for f in resultado], [fonte["id"]])
        self.assertEqual(vistos, [("consolidar", lt["id"], fonte["id"])])


class TempoEMesmoId(unittest.TestCase):
    """Mecanismos da Fase 6a que continuam iguais."""

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


class Pipeline(unittest.TestCase):
    """Etapa linguística com o LanguageTool simulado (sem modelo de linguagem)."""
    TEXTO = "Ela parou,, e olhou  depois."

    def rodar(self, respostas, languagetool=True):
        regras = {r: False for r in validate({})["rules"]}
        regras["pontuacao_duplicada"] = regras["espacamento"] = True
        with patch("fonte.languagetool.build_opener") as builder:
            builder.return_value.open.side_effect = respostas
            return run([Block(1, self.TEXTO)], lambda: None, settings=validate({"rules": regras}),
                       mode="linguistica", languagetool=languagetool)

    def test_two_sources_one_phenomenon(self):
        mesmo = match(self.TEXTO, ",,", "DOUBLE_PUNCTUATION", "typographical", "PUNCTUATION", [","])
        outro = match(self.TEXTO, "olhou", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")
        achados, _, meta = self.rodar(lambda request, timeout: Response([mesmo, outro]))
        self.assertEqual([(f["excerpt"], f["source"].split(" · ")[0]) for f in achados],
                         [(",,", "FONTE Linguístico"), ("olhou", "LanguageTool local"), ("  ", "FONTE Linguístico")])
        self.assertEqual(achados[0]["absorvidos"][0]["source"], "LanguageTool local · DOUBLE_PUNCTUATION")
        self.assertEqual(meta["deduplicacao"]["absorvidos"], 1)
        self.assertEqual(next(s for s in meta["stages"] if s["module"] == "linguistic")["finding_count"], 3)

    def test_same_span_other_phenomenon_keeps_both(self):
        # Antes da 6b, o alerta do LT que tocasse um trecho do FONTE caía, qualquer que fosse o fenômeno.
        outro = match(self.TEXTO, "olhou  depois", "OUTRA_REGRA", "grammar", "GRAMMAR", ["olhou depois"])
        achados, _, meta = self.rodar(lambda request, timeout: Response([outro]))
        self.assertEqual(len(achados), 3)
        self.assertNotIn("deduplicacao", meta)

    def test_languagetool_on_and_off_keep_the_same_identity(self):
        mesmo = match(self.TEXTO, ",,", "DOUBLE_PUNCTUATION", "typographical", "PUNCTUATION", [","])
        ligado, _, _ = self.rodar(lambda request, timeout: Response([mesmo]))
        desligado, avisos, _ = self.rodar(None, languagetool=False)
        self.assertEqual([f["id"] for f in ligado], [f["id"] for f in desligado])
        self.assertTrue(any("sem o corretor gramatical local" in a for a in avisos))
        self.assertNotIn("absorvidos", desligado[0])

    def test_languagetool_unavailable_stops_the_analysis(self):
        # Comportamento atual: com o LT pedido e fora do ar, não há relatório parcial.
        def fora(request, timeout):
            raise URLError("recusado")
        with self.assertRaisesRegex(ValueError, "LanguageTool local"):
            self.rodar(fora)


class FonteUnica(unittest.TestCase):
    def test_no_overlap_only_mechanism_is_left(self):
        import inspect
        self.assertNotIn("skip", inspect.signature(grammar.analyze).parameters)
        self.assertIs(pipeline.deduplicacao, deduplicacao)
        for nome in ("languagetool_sob_regras_linguisticas", "gramatica_sob_languagetool"):
            self.assertFalse(hasattr(deduplicacao, nome))


if __name__ == "__main__":
    unittest.main()
