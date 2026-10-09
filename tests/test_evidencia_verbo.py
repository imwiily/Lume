"""Ferramentas da evidência independente da Fase 2b: amostragem e avaliação do núcleo verbal."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import amostrar_verbos as amostrar
import avaliar_verbo as avaliar


class AmostragemTests(unittest.TestCase):
    def test_gutenberg_header_and_footer_are_removed(self):
        texto = "Licença\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nCorpo do livro.\n*** END OF THE PROJECT\nRodapé"
        self.assertEqual(amostrar.corpo(texto).strip(), "Corpo do livro.")

    def test_paragraphs_need_six_words_and_skip_all_caps_titles(self):
        texto = "CAPÍTULO PRIMEIRO DO LIVRO\n\nEla abriu a janela e olhou a rua.\n\nCurto demais."
        self.assertEqual(list(amostrar.paragrafos(texto)), ["Ela abriu a janela e olhou a rua."])


class AvaliacaoTests(unittest.TestCase):
    def resultado(self, esperado, certo, possivel, presenca, pos='VERB', ambiguo=False):
        return {'esperado': esperado, 'ambiguo': ambiguo, 'estrato': 'x', 'modelo': {'pos': pos},
                'ops': {'certamente_verbo': certo, 'pode_ser_verbo': possivel, 'ha_forma_verbal': presenca}}

    def test_metrics_separate_the_three_operations_and_situations(self):
        r = [self.resultado('finito', True, True, True),
             self.resultado('finito', False, True, False),                 # não confirmado
             self.resultado('finito', False, False, False, pos='NOUN'),    # modelo errou a classe
             self.resultado('nao_verbal', True, True, True, pos='AUX'),    # falso positivo
             self.resultado('nao_verbal', False, False, False),
             self.resultado('finito', False, False, False, ambiguo=True)]  # fora das métricas
        m = avaliar.metricas(r)
        self.assertEqual((m['itens'], m['ambiguos']), (6, 1))
        self.assertEqual(m['certamente_verbo']['precisao'], {'n': 2, 'valor': 0.5})
        self.assertEqual(m['pode_ser_verbo']['cobertura_finitos'], {'n': 3, 'valor': 0.667})
        self.assertEqual(m['situacao_dos_finitos'],
                         {'confirmado': 1, 'nao_confirmado': 1, 'classificado_incorretamente_pelo_modelo': 1})
        self.assertTrue(m['invariante_certo_implica_possivel'])

    def test_validation_refuses_individual_errors(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'v.json'
            caminho.write_text(json.dumps({'conjunto': 'validacao', 'itens': []}))
            with self.assertRaises(SystemExit):
                avaliar.main([str(caminho), '--erros'])


if __name__ == '__main__':
    unittest.main()
