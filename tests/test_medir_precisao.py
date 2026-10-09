"""Medição de precisão a partir de decisões: repetições entre versões, desfechos e saída sem trechos."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import medir_precisao as medir


def alerta(ident, texto, inicio, fim, regra='palavra_proxima', confianca='baixa', fonte='Regras FONTE'):
    return {'id': ident, 'text': texto, 'start': inicio, 'end': fim, 'rule': regra, 'confidence': confianca,
            'severity': 'editorial_attention', 'source': fonte, 'category': 'x'}


class MedicaoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.dados = Path(self.pasta.name)
        (self.dados / 'Decisoes').mkdir()

    def tearDown(self):
        self.pasta.cleanup()

    def relatorio(self, nome, documento, sha, alertas, decisoes):
        pasta = self.dados / 'Relatorios' / nome
        pasta.mkdir(parents=True)
        (pasta / 'relatorio.json').write_text(json.dumps({'document': documento, 'sha256': sha, 'findings': alertas}))
        (self.dados / 'Decisoes' / f'{sha}.json').write_text(json.dumps(
            {'schema_version': 1, 'document': documento, 'sha256': sha, 'decisions': decisoes}))

    def test_same_alert_in_two_versions_counts_once_with_the_latest_decision(self):
        texto = 'A lua clara iluminava a lua do lago.'
        self.relatorio('1', 'livro.pages', 'a' * 64, [alerta('x1', texto, 2, 5)], {'x1': 'Erro confirmado'})
        self.relatorio('2', 'livro.pages', 'b' * 64, [alerta('x2', texto, 2, 5)], {'x2': 'Estilo do autor'})
        resultado = medir.medir(self.dados)
        self.assertEqual(resultado['decisoes_unicas'], 1)
        c, = resultado['classes']
        self.assertEqual((c['decisoes'], c['erro'], c['estilo']), (1, 0, 1))

    def test_outcomes_pending_and_threshold(self):
        alertas = [alerta(f'e{i}', f'Frase número {i} com erro.', 0, 5, regra='crase', confianca='média')
                   for i in range(20)]
        decisoes = {f'e{i}': 'Erro confirmado' for i in range(17)}
        decisoes.update(e17='Corrigido', e18='Falso positivo', e19='Pendente')
        self.relatorio('1', 'livro.pages', 'c' * 64, alertas, decisoes)
        c, = medir.medir(self.dados)['classes']
        self.assertEqual((c['decisoes'], c['erro'], c['falso_positivo']), (19, 18, 1))
        self.assertFalse(c['medida'])  # 19 decisões: abaixo do mínimo
        self.assertFalse(c['atinge_limiar'])
        c, = medir.medir(self.dados, minimo=19)['classes']
        self.assertTrue(c['atinge_limiar'])  # 18/19 ≈ 95%

    def test_languagetool_spelling_and_grammar_are_separate_classes(self):
        texto = 'Ele viu a jenela e a porta.'
        self.relatorio('1', 'livro.pages', 'd' * 64,
                       [alerta('o', texto, 9, 15, regra=None, fonte='LanguageTool local · MORFOLOGIK_RULE_PT_BR'),
                        alerta('g', texto, 0, 3, regra=None, fonte='LanguageTool local · CRASE_CONFUSION')],
                       {'o': 'Falso positivo', 'g': 'Erro confirmado'})
        nomes = {c['classe'] for c in medir.medir(self.dados)['classes']}
        self.assertEqual(nomes, {'languagetool:ortografia', 'languagetool:gramatica'})

    def test_output_has_no_excerpts_or_book_names(self):
        texto = 'Trecho particular de um livro inédito.'
        self.relatorio('1', 'Meu Livro Secreto.pages', 'e' * 64, [alerta('p', texto, 0, 6)], {'p': 'Intencional'})
        saida = self.dados / 'saida'
        medir.main(['--dados', str(self.dados), '--saida', str(saida)])
        conteudo = (saida / 'precisao.json').read_text() + (saida / 'resumo.md').read_text()
        self.assertNotIn('Trecho', conteudo)
        self.assertNotIn('Secreto', conteudo)

    def test_languagetool_decisions_by_rule_and_original_category(self):
        texto = 'Ele viu a jenela,, e a porta.'
        lt = alerta('t', texto, 15, 17, regra='languagetool', confianca='média', fonte='LanguageTool local · DOUBLE_PUNCTUATION')
        lt['languagetool'] = {'regra': 'DOUBLE_PUNCTUATION', 'categoria': 'PUNCTUATION', 'tipo': 'typographical'}
        antigo = alerta('o', texto, 10, 16, regra=None, fonte='LanguageTool local · MORFOLOGIK_RULE_PT_BR')
        self.relatorio('1', 'livro.pages', 'e' * 64, [lt, antigo, alerta('f', texto, 0, 3, regra='crase')],
                       {'t': 'Erro confirmado', 'o': 'Falso positivo', 'f': 'Erro confirmado'})
        linhas = {(l['regra'], l['categoria'], l['classe']): (l['decisoes'], l['erro']) for l in medir.medir_languagetool(self.dados)}
        self.assertEqual(linhas, {('DOUBLE_PUNCTUATION', 'PUNCTUATION', 'languagetool:gramatica'): (1, 1),
                                  ('MORFOLOGIK_RULE_PT_BR', 'não registrada', 'languagetool:ortografia'): (1, 0)})


if __name__ == '__main__':
    unittest.main()


class SameClassKeyTests(unittest.TestCase):
    def test_script_and_policy_use_the_same_class(self):
        from fonte.politica import classe
        for item in (alerta('a', 'x', 0, 1), alerta('b', 'x', 0, 1, regra=None, fonte='LanguageTool local · MORFOLOGIK_RULE_PT_BR'),
                     alerta('c', 'x', 0, 1, regra=None, fonte='LanguageTool local · CRASE_CONFUSION'),
                     {'category_code': 'narrative_tense', 'category': 'Tempo verbal'}):
            self.assertEqual(medir.classe(item), classe(item))
