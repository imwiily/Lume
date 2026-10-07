"""Integridade do corpus de avaliação cega e da contagem de acertos."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import avaliar_deteccao as bench

CATEGORIES = {'ortografia', 'acentuacao', 'concordancia_verbal', 'concordancia_nominal', 'crase',
              'regencia', 'homofonos', 'verbo_impessoal', 'pontuacao', 'pontuacao_mecanica',
              'repeticao', 'tempo_verbal', 'contradicao', 'residuo_edicao', 'estrutura_frase',
              'continuidade_local'}


def finding(paragraph, start, end, related=(), module='linguistic'):
    return {'paragraph': paragraph, 'start': start, 'end': end, 'text': '', 'category': 'x',
            'excerpt': '', 'related': list(related), 'module': module}


class CorpusTests(unittest.TestCase):
    def test_every_annotation_is_found_in_its_paragraph(self):
        texts = bench.load(['desenvolvimento', 'validacao'])
        self.assertEqual(len({t['id'] for t in texts}), len(texts))
        for text in texts:
            for annotation in text['erros']:
                self.assertIn(annotation['categoria'], CATEGORIES, text['id'])
                self.assertIn(annotation['camada'], bench.LAYERS, text['id'])
            for annotation in text['erros'] + text.get('aceitaveis', []):
                bench.locate(text, annotation)
                # Trecho repetido no parágrafo exige `n` explícito.
                paragraph = text['paragrafos'][annotation['p'] - 1]
                if 'n' not in annotation:
                    self.assertEqual(len(bench.occurrences(paragraph, annotation['trecho'])), 1,
                                     f"{text['id']} §{annotation['p']}: {annotation['trecho']!r} ambíguo")
            if text.get('controle'):
                self.assertEqual(text['erros'], [], text['id'])

    def test_sets_do_not_share_texts(self):
        development = {t['id'] for t in bench.load(['desenvolvimento'])}
        validation = {t['id'] for t in bench.load(['validacao'])}
        self.assertFalse(development & validation)
        self.assertTrue(all(i.startswith('val-') for i in validation))


class ScoreTests(unittest.TestCase):
    text = {'id': 't', 'conjunto': 'desenvolvimento', 'paragrafos': ['Ela disse que que sim. Tá bom.'],
            'erros': [{'p': 1, 'trecho': 'que que', 'categoria': 'repeticao', 'camada': 'linguistica'}],
            'aceitaveis': [{'p': 1, 'trecho': 'Tá'}]}

    def test_overlap_counts_hit_and_classifies_other_findings(self):
        result = bench.score(self.text, [finding(1, 14, 17), finding(1, 23, 25), finding(1, 0, 3)])
        self.assertTrue(result['erros'][0]['encontrado'])
        self.assertEqual((result['verdadeiras'], result['neutras'], len(result['alarmes_falsos'])), (1, 1, 1))

    def test_excerpt_matches_whole_words_only(self):
        text = {'id': 't', 'paragrafos': ['Tinha acontecido; chamou a a filha.']}
        self.assertEqual(bench.locate(text, {'p': 1, 'trecho': 'a a'}), (1, 25, 28))

    def test_adjacent_span_is_not_a_hit(self):
        result = bench.score(self.text, [finding(1, 17, 18)])
        self.assertFalse(result['erros'][0]['encontrado'])

    def test_related_evidence_can_anchor_a_hit(self):
        result = bench.score(self.text, [finding(1, 0, 3, [{'paragraph': 1, 'start': 10, 'end': 13}])])
        self.assertTrue(result['erros'][0]['encontrado'])

    def test_other_paragraph_is_not_a_hit(self):
        self.assertFalse(bench.score(self.text, [finding(2, 10, 17)])['erros'][0]['encontrado'])

    def test_summary_keeps_denominators(self):
        summary = bench.summarize([bench.score(self.text, [])])
        self.assertEqual(summary['por_camada']['linguistica'], {'esperados': 1, 'encontrados': 0})


class AuditScoreTests(unittest.TestCase):
    """A Auditoria final é medida à parte: o que só ela encontra e o que ela aponta à toa."""
    text = {'id': 't', 'conjunto': 'desenvolvimento',
            'paragrafos': ['Ela disse que que sim. Tá bom.', 'As caixas estava ali.'],
            'erros': [{'p': 1, 'trecho': 'que que', 'categoria': 'repeticao', 'camada': 'linguistica'},
                      {'p': 2, 'trecho': 'estava', 'categoria': 'concordancia_verbal', 'camada': 'linguistica'}],
            'aceitaveis': [{'p': 1, 'trecho': 'Tá'}]}

    def test_audit_findings_are_split_by_what_the_rules_missed(self):
        findings = [finding(1, 10, 17),                       # regra acha a repetição
                    finding(1, 14, 17, module='audit'),       # auditoria repete o mesmo erro
                    finding(2, 10, 16, module='audit'),       # só a auditoria acha a concordância
                    finding(1, 23, 25, module='audit'),       # trecho aceitável
                    finding(2, 0, 2, module='audit')]         # alarme falso
        result = bench.score(self.text, findings)
        self.assertEqual([(e['encontrado'], e['encontrado_regras']) for e in result['erros']],
                         [(True, True), (True, False)])
        auditoria = result['auditoria']
        self.assertEqual((auditoria['achados'], auditoria['sobre_erros_perdidos'], auditoria['sobre_erros_ja_apontados'],
                          auditoria['neutros'], len(auditoria['alarmes_falsos'])), (4, 1, 1, 1, 1))

    def test_summary_counts_audit_and_cost(self):
        result = bench.score(self.text, [finding(2, 10, 16, module='audit')])
        result['custo_auditoria'] = 0.05
        summary = bench.summarize([result, bench.score(self.text, [])])
        self.assertEqual(summary['auditoria'], {'achados': 1, 'erros_so_auditoria': 1, 'erros_perdidos_pelas_regras': 4,
                                                'sobre_erros_ja_apontados': 0, 'neutros': 0, 'alarmes_falsos': 0,
                                                'diagnostico': 0, 'custo_usd': 0.05})
        self.assertIn('Auditoria final', bench.table(summary))

    def test_audit_diagnostics_are_measured_but_not_shown(self):
        diagnostico = [dict(finding(2, 10, 16, module='audit'), destino='diagnostico')]
        result = bench.score(self.text, [], diagnostico)
        self.assertEqual((result['auditoria']['achados'], result['auditoria']['diagnostico']), (1, 1))
        self.assertEqual(result['ocorrencias'], 0)  # fora da mesa: não conta como ocorrência mostrada

    def test_without_audit_summary_has_no_audit_section(self):
        summary = bench.summarize([bench.score(self.text, [finding(1, 10, 17)])])
        self.assertNotIn('auditoria', summary)
        self.assertNotIn('Auditoria final', bench.table(summary))

    def test_total_budget_stops_before_next_text(self):
        self.assertTrue(bench.within_budget(spent=0.5, per_text=0.2, total=1.0))
        self.assertFalse(bench.within_budget(spent=0.85, per_text=0.2, total=1.0))


if __name__ == '__main__':
    unittest.main()


class PrecisionSummaryTests(unittest.TestCase):
    def test_precision_and_false_alarms_per_10k_words_come_first(self):
        results = [{'erros': [], 'ocorrencias': 4, 'verdadeiras': 3, 'neutras': 0, 'controle': False,
                     'alarmes_falsos': [{}], 'palavras': 2000, 'auditoria': {}}]
        summary = bench.summarize(results)
        self.assertEqual((summary['precisao'], summary['alarmes_falsos_por_10k_palavras']), (.75, 5.0))
        self.assertTrue(bench.table(summary).startswith('Precisão das pendências'))

    def test_observations_leave_the_queue_precision(self):
        results = [{'erros': [], 'ocorrencias': 4, 'verdadeiras': 3, 'neutras': 0, 'controle': False,
                     'alarmes_falsos': [{}], 'palavras': 2000, 'auditoria': {},
                     'pendencias_verdadeiras': 3, 'pendencias_alarmes_falsos': 0}]
        summary = bench.summarize(results)
        self.assertEqual((summary['precisao'], summary['precisao_pendencias']), (.75, 1.0))
