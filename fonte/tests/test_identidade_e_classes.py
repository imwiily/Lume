"""Estabilização, Fase 1: identidade, regra e classe estatística são três coisas distintas.

- identidade (`id`): não muda quando o alerta ganha `rule`;
- regra (`rule`): todo alerta tem uma;
- classe estatística (`classe`): a mesma de antes, para não perder as medições da política.
Também: `residuo_edicao` separado de `estrutura`, herdando o valor dela em configurações antigas.
"""
import unittest
from unittest.mock import patch

import spacy

from fonte import languagetool as lt
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate

PASSADO = "A manhã começou fria. Ninguém saiu de casa cedo."


class RuleAndClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def run_text(self, text, settings=None):
        found, _, _ = run([Block(1, PASSADO), Block(2, text)], lambda: self.nlp, tense="passado", mode="ambas",
                          settings=validate(settings or {}))
        return [f for f in found if f["paragraph"] == 2]

    def test_every_finding_has_rule_and_the_previous_statistical_class(self):
        expected = {"Tempo verbal": ("tempo_verbal", "narrative_tense"),
                    "Resíduo de edição": ("residuo_edicao", "editorial_review")}
        found = self.run_text("Ela tinha havia percebido o barulho.") + self.run_text("O vento sopra forte lá fora.")
        seen = {}
        for f in found:
            self.assertTrue(f.get("rule") and f.get("classe"), f["category"])
            if f["category"] in expected:
                seen[f["category"]] = (f["rule"], f["classe"])
        self.assertEqual(seen, expected)

    def test_structure_keeps_its_two_classes(self):
        found = self.run_text("Quando as luzes da casa se apagaram depois do jantar.")
        classes = {f["classe"] for f in found if f["rule"] == "estrutura"}
        self.assertTrue(classes <= {"sentence_structure", "incomplete_subordinate_clause"}, classes)

    def test_editing_residue_follows_structure_in_old_settings(self):
        texto = "Ela tinha havia percebido o barulho."
        def residue(settings):
            return [f for f in self.run_text(texto, settings) if f["rule"] == "residuo_edicao"]
        self.assertTrue(residue({}))
        self.assertFalse(residue({"rules": {"estrutura": False}}))           # configuração antiga
        self.assertTrue(residue({"rules": {"estrutura": False, "residuo_edicao": True}}))
        self.assertFalse(residue({"rules": {"residuo_edicao": False}}))


class LanguageToolRuleTests(unittest.TestCase):
    def test_languagetool_findings_have_rule_and_keep_category_code(self):
        import json
        text = "A jenela abriu."
        found = {"offset": 2, "length": 6, "message": "Possível erro.", "replacements": [{"value": "janela"}],
                 "rule": {"id": "MORFOLOGIK_RULE_PT_BR", "issueType": "misspelling", "category": {"id": "TYPOS"}}}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return json.dumps({"matches": [found]}).encode()

        with patch("fonte.languagetool.build_opener") as builder:
            builder.return_value.open.return_value = Response()
            (item,), _ = lt.check([Block(1, text)])
        self.assertEqual((item["rule"], item["category_code"]), ("languagetool", "grammar"))
        from fonte.politica import classe
        self.assertEqual(classe(item), "languagetool:ortografia")


if __name__ == "__main__":
    unittest.main()
