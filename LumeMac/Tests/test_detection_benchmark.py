"""Integridade do corpus de avaliação cega e da contagem de acertos."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts'))
import avaliar_deteccao as bench

CATEGORIES = {'ortografia', 'acentuacao', 'concordancia_verbal', 'concordancia_nominal', 'crase',
              'regencia', 'homofonos', 'verbo_impessoal', 'pontuacao', 'pontuacao_mecanica',
              'repeticao', 'tempo_verbal', 'contradicao'}


def finding(paragraph, start, end, related=()):
    return {'paragraph': paragraph, 'start': start, 'end': end, 'text': '', 'category': 'x',
            'excerpt': '', 'related': list(related)}


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


if __name__ == '__main__':
    unittest.main()
