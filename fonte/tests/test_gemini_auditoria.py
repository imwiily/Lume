"""Auditoria final com o Gemini: identidade do cache por modelo, reaproveitamento e estimativa. Nada é enviado."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fonte.settings import validate
from test_auditoria_ia import ModeloFalso, SemChamadas, item, livro


class GeminiFalso(ModeloFalso):
    modelo = 'gemini-3.8-flash'


class AuditoriaGeminiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.temp.name) / 'projeto'

    def tearDown(self):
        self.temp.cleanup()

    def auditar(self, modelo):
        from fonte.auditoria_ia import auditar
        return auditar(livro(), [], tempo='passado', configuracao=validate({}), cliente=modelo, pasta=self.pasta)

    def test_finding_is_labeled_gemini_and_stays_a_suspicion(self):
        achados, avisos, _ = self.auditar(GeminiFalso({'ocorrencias': [item(2, 'estava')]}))
        self.assertEqual(achados[0]['source'], 'Auditoria · IA (Gemini)')
        self.assertEqual((achados[0]['severity'], achados[0]['confidence']), ('editorial_attention', 'média'))
        self.assertTrue(any('ao Google' in a and 'Anthropic' not in a for a in avisos))

    def test_invented_excerpt_from_gemini_is_discarded(self):
        achados, _, resumo = self.auditar(GeminiFalso({'ocorrencias': [item(2, 'trecho que não existe')]}))
        self.assertEqual((achados, resumo['descartes']), ([], {'trecho_inexistente': 1}))

    def test_same_text_is_reused_without_a_call_and_models_do_not_mix(self):
        self.auditar(GeminiFalso())
        _, _, repetido = self.auditar(SemChamadasGemini())
        self.assertEqual((repetido['enviados'], repetido['reaproveitados']), (0, 2))
        # O resultado do Gemini não vale para o Claude: o mesmo texto com outro modelo é enviado de novo.
        claude = ModeloFalso()
        _, _, outro = self.auditar(claude)
        self.assertEqual((outro['enviados'], outro['reaproveitados']), (2, 0))

    def test_estimate_is_local_conservative_and_uses_google_prices(self):
        from fonte.auditoria_ia import estimar
        with patch('coerencia.modelo.criar_modelo', side_effect=AssertionError('sem rede')), \
             patch('coerencia.modelo.Gemini', side_effect=AssertionError('sem rede')):
            gemini = estimar(livro(), self.pasta, modelo='gemini-3.8-flash')
        self.assertEqual((gemini['provedor'], gemini['a_enviar']), ('google', 2))
        self.assertGreater(gemini['custo_estimado_usd'], 0)
        self.assertIn('conservadora', gemini['calibracao'])
        self.assertEqual(estimar(livro(), self.pasta)['provedor'], 'anthropic')
        with self.assertRaisesRegex(ValueError, 'preço'):
            estimar(livro(), self.pasta, modelo='gemini-desconhecido')


class PesquisaTests(unittest.TestCase):
    class Cliente:
        modelo = 'gemini-3.8-flash'

        def __init__(self):
            self.pedidos = []

        def verificar(self):
            pass

        def pesquisar(self, sistema, pergunta, etapa):
            self.pedidos.append(pergunta)
            return {'resposta': 'ok', 'consultas': ['q'], 'fontes': [], 'buscas': 1, 'custo_usd': .02}

    def test_estimate_is_local_and_includes_search_worst_case(self):
        from fonte import pesquisa_gemini as p
        with patch('coerencia.modelo.criar_modelo', side_effect=AssertionError('sem rede')):
            e = p.estimar('Quando se usa crase antes de pronome?')
        self.assertGreater(e['custo_maximo_usd'], 5 * .014)

    def test_one_call_per_request_and_only_gemini(self):
        from fonte import pesquisa_gemini as p
        c = self.Cliente()
        r = p.pesquisar('  Quando   se usa crase? ', cliente=c)
        self.assertEqual((c.pedidos, r['pergunta'], r['provedor']), (['Quando se usa crase?'], 'Quando se usa crase?', 'google'))
        with self.assertRaises(ValueError):
            p.pesquisar('x', modelo='claude-opus-5-5', cliente=c)
        with self.assertRaises(ValueError):
            p.pesquisar('x' * 401, cliente=c)
        self.assertEqual(len(c.pedidos), 1)

    def test_review_has_no_search_option_and_search_command_estimates_without_api(self):
        import io, json
        from contextlib import redirect_stdout
        from fonte.cli import main, parser
        self.assertNotIn('--pesquisa', parser().parse_args(['revisar', 'x.docx']).__dict__)
        saida = io.StringIO()
        with redirect_stdout(saida), patch('coerencia.modelo.criar_modelo', side_effect=AssertionError('sem API')):
            self.assertEqual(main(['pesquisar-fundamento', '--pergunta', 'Crase antes de verbo?', '--estimar']), 0)
        self.assertTrue(saida.getvalue().startswith('LUME_PESQUISA_ESTIMATIVA '))


class SemChamadasGemini(SemChamadas):
    modelo = 'gemini-3.8-flash'


if __name__ == '__main__':
    unittest.main()
