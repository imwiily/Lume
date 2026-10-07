"""Comparação de relatórios alerta a alerta: identidade, destino e classe, sem trechos na saída."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import comparar_relatorios as comparar


def alerta(ident, destino='pendencia', rule=None, texto='Trecho particular do livro.'):
    return {'id': ident, 'destino': destino, 'impeditivo': False, 'rule': rule, 'category': 'Tempo verbal',
            'category_code': 'narrative_tense', 'severity': 'editorial_attention', 'confidence': 'média',
            'source': 'Regras FONTE', 'reason': 'x', 'text': texto, 'start': 0, 'end': 6}


class ComparacaoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = Path(self.pasta.name)

    def tearDown(self):
        self.pasta.cleanup()

    def relatorio(self, lado, nome, alertas):
        caminho = self.raiz / lado / nome / 'relatorio.json'
        caminho.parent.mkdir(parents=True)
        caminho.write_text(json.dumps({'findings': alertas}))

    def test_destination_change_and_lost_ids_fail(self):
        self.relatorio('a', 'livro', [alerta('1'), alerta('2')])
        self.relatorio('b', 'livro', [alerta('1', destino='informacao'), alerta('3')])
        r = comparar.comparar(self.raiz / 'a/livro/relatorio.json', self.raiz / 'b/livro/relatorio.json')
        self.assertEqual((r['saíram'], r['entraram'], r['mudancas_editoriais']), (['2'], ['3'], {'destino': 1}))
        self.assertEqual(comparar.main([str(self.raiz / 'a'), str(self.raiz / 'b'), '--exigir-identico']), 1)

    def test_output_has_no_excerpts(self):
        self.relatorio('a', 'livro', [alerta('1')])
        self.relatorio('b', 'livro', [alerta('2')])
        saida = self.raiz / 'saida'
        comparar.main([str(self.raiz / 'a'), str(self.raiz / 'b'), '--saida', str(saida)])
        self.assertNotIn('Trecho particular', (saida / 'comparacao.json').read_text())


if __name__ == '__main__':
    unittest.main()
