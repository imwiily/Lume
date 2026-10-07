"""Política de destino editorial (plano `encerramento-editorial`).

Confere as regras do autor: dados reais prevalecem sobre o rótulo de confiança; o limiar de
observação é de não-interrupção; impeditivo exige precisão ≥ 90% em ≥ 20 decisões, natureza
objetiva e severidade de erro, as três juntas.
"""
import unittest
from unittest.mock import patch

import spacy

from fonte import politica as pol
from fonte.contracts import check_destination
from fonte.pipeline import run
from fonte.reader import Block

POLITICA = {
    "versao": 99,
    "limiares": {"minimo_decisoes": 20, "impeditivo_precisao": 0.9, "observacao_precisao": 0.5},
    "natureza_objetiva": ["crase", "pontuacao_duplicada"],
    "medicoes": {
        "crase|média": {"decisoes": 40, "precisao": 0.95},
        "pontuacao_duplicada|alta": {"decisoes": 19, "precisao": 1.0},
        "concordancia|média": {"decisoes": 30, "precisao": 0.89},
        "narrative_tense|média": {"decisoes": 400, "precisao": 0.95},
        "palavra_proxima|baixa": {"decisoes": 40, "precisao": 0.49},
        "dialogo_contextual|baixa": {"decisoes": 30, "precisao": 0.9},
        "audit_crase|média": {"decisoes": 25, "precisao": 0.96},
    },
    "auditoria": {"destino_inicial": {"audit_concordancia": "informacao"}, "padrao": "diagnostico"},
}


def alerta(regra, confianca, severidade="probable_error", fonte="Regras FONTE"):
    return {"rule": regra, "confidence": confianca, "severity": severidade, "source": fonte}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(pol, "politica", lambda: POLITICA)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def resultado(self, item):
        mesa, diagnostico = pol.aplicar([item])
        return item["destino"], item["impeditivo"]

    def test_all_three_conditions_make_a_blocking_class(self):
        self.assertEqual(self.resultado(alerta("crase", "média")), ("pendencia", True))

    def test_high_precision_alone_never_blocks(self):
        # Editorial com 95%, objetiva com 89%, objetiva com 100% em 19 decisões, objetiva sem severidade de erro.
        for item in (alerta("narrative_tense", "média"), alerta("concordancia", "média"),
                     alerta("pontuacao_duplicada", "alta"), alerta("crase", "média", "editorial_attention")):
            with self.subTest(item=item):
                self.assertEqual(self.resultado(item), ("pendencia", False))

    def test_low_measured_precision_leaves_the_queue(self):
        self.assertEqual(self.resultado(alerta("palavra_proxima", "baixa")), ("informacao", False))

    def test_measured_data_prevail_over_the_confidence_label(self):
        # Rótulo ‘baixa’, mas 90% de erro real em 30 decisões: continua na fila.
        self.assertEqual(self.resultado(alerta("dialogo_contextual", "baixa")), ("pendencia", False))

    def test_without_enough_data_the_label_decides(self):
        self.assertEqual(self.resultado(alerta("gerundismo", "baixa")), ("informacao", False))
        self.assertEqual(self.resultado(alerta("gerundismo", "média")), ("pendencia", False))

    def test_languagetool_classes_split_spelling_and_grammar(self):
        self.assertEqual(pol.classe(alerta(None, "alta", fonte="LanguageTool local · MORFOLOGIK_RULE_PT_BR")),
                         "languagetool:ortografia")
        self.assertEqual(pol.classe(alerta(None, "média", fonte="LanguageTool local · CRASE_CONFUSION")),
                         "languagetool:gramatica")

    def test_audit_routing(self):
        def achado(categoria, confianca):
            return {"rule": "auditoria_ia", "category_code": f"audit_{categoria}", "confidence": confianca,
                    "severity": "probable_error", "source": "Auditoria · IA (Claude)"}
        self.assertEqual(self.resultado(achado("concordancia", "baixa")), ("diagnostico", False))
        self.assertEqual(self.resultado(achado("concordancia", "média")), ("informacao", False))
        self.assertEqual(self.resultado(achado("referencia", "média")), ("diagnostico", False))
        # Promoção só por dados medidos, e mesmo assim nunca impeditiva por conta própria.
        self.assertEqual(self.resultado(achado("crase", "média")), ("pendencia", False))
        self.assertEqual(self.resultado(achado("crase", "baixa")), ("diagnostico", False))

    def test_contract_rejects_inconsistent_destination(self):
        check_destination({"destino": "pendencia", "impeditivo": True, "severity": "probable_error"})
        for item in ({"destino": "informacao", "impeditivo": True, "severity": "probable_error"},
                     {"destino": "pendencia", "impeditivo": True, "severity": "editorial_attention"},
                     {"destino": "outro", "impeditivo": False}, {"destino": "pendencia", "impeditivo": 0}):
            with self.subTest(item=item), self.assertRaises(ValueError):
                check_destination(item)


class ShippedPolicyTests(unittest.TestCase):
    """A política v1 distribuída segue as decisões do autor de 07/10/2026."""

    def test_v1_has_no_blocking_class_yet(self):
        dados = pol.politica()
        objetivas = set(dados["natureza_objetiva"])
        bloqueantes = [chave for chave, m in dados["medicoes"].items()
                       if chave.split("|")[0] in objetivas and m["decisoes"] >= 20 and m["precisao"] >= .9]
        self.assertEqual(bloqueantes, [])

    def test_principles_are_written_in_the_policy(self):
        texto = " ".join(pol.politica()["principios"])
        for trecho in ("evidência auxiliar", "não é afirmação de que a regra é confiável", "não-interrupção"):
            self.assertIn(trecho, texto)


class PipelineDestinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def test_every_finding_has_a_destination_and_ids_are_unchanged(self):
        blocos = [Block(1, "A manhã começou fria. Ela abre a janela e saiu sem casaco.")]
        found, _, meta = run(blocos, lambda: self.nlp, tense="passado", mode="ambas")
        self.assertTrue(found)
        for f in found:
            check_destination(f)
        self.assertEqual(meta["politica_versao"], pol.politica()["versao"])
        self.assertEqual(sum(meta["destinos"].values()), len(found) + len(meta["diagnostico"]))
        def sem_politica(itens):
            for item in itens:
                item.update(destino="pendencia", impeditivo=False)
            return itens, []
        with patch.object(pol, "aplicar", sem_politica):
            antes, _, _ = run(blocos, lambda: self.nlp, tense="passado", mode="ambas")
        self.assertEqual([f["id"] for f in antes], [f["id"] for f in found])


if __name__ == "__main__":
    unittest.main()
