"""Coerência 2.0 no motor do Lume: estimativa, ocorrências v1, política e despacho. Cliente simulado; sem API."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fonte import coerencia2_ia as c2
from fonte import politica
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate

BLOCOS = [Block(1, 'Capítulo 1', 'Capítulo 1', heading=True),
          Block(2, 'A ponte caiu na noite anterior e ninguém passou por ela.', 'Capítulo 1'),
          Block(3, 'No dia seguinte o caminhão de entregas chegou pela ponte velha.', 'Capítulo 1')]


def apontamento(trecho_a='A ponte caiu na noite anterior', trecho_b='o caminhão de entregas chegou pela ponte'):
    return {"categoria": "continuidade_causal", "natureza": "contradicao", "prioridade": "atencao", "certeza": "alta",
            "titulo": "Ponte", "explicacao": "A ponte caiu e depois é usada.", "pode_ser_intencional": False,
            "leituras_alternativas": "Pode haver outro caminho.", "relevancia_da_lacuna": "",
            "evidencias": [{"paragrafo": 2, "trecho": trecho_a, "papel": "anterior"},
                           {"paragrafo": 3, "trecho": trecho_b, "papel": "posterior"}]}


class ClienteFalso:
    esforco, max_tokens = "medium", 16000

    def __init__(self, modelo, *respostas):
        self.modelo, self.respostas, self.chamadas, self.pedidos = modelo, list(respostas), [], 0

    def json(self, sistema, usuario, esquema, etapa):
        self.pedidos += 1
        self.chamadas.append({"etapa": etapa, "custo_usd": 0.02, "tokens_entrada": 100, "tokens_cache": 0,
                              "tokens_cache_criacao": 0, "tokens_saida": 50, "modelo_usado": self.modelo})
        return self.respostas.pop(0)


class Coerencia2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.temp.name) / 'coerencia'

    def tearDown(self):
        self.temp.cleanup()

    def analisar(self, cliente, modelo='claude-sonnet-5-5', blocos=BLOCOS):
        with patch('coerencia2.uma_requisicao.criar_uma_requisicao', return_value=cliente):
            return c2.analisar(blocos, self.pasta, 'livro', modelo, 1.0)

    def test_estimate_is_local_has_the_v1_shape_and_respects_cache(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('sem rede')):
            antes = c2.estimar(BLOCOS, self.pasta)
        self.assertEqual((antes['versao'], antes['a_enviar'], antes['capitulos']), (2, 1, 1))
        self.assertGreater(antes['custo_maximo_usd'], antes['custo_estimado_usd'] - 1e-9)
        self.analisar(ClienteFalso('claude-sonnet-5-5', {"apontamentos": [], "fenomenos_descartados": []}))
        depois = c2.estimar(BLOCOS, self.pasta)
        self.assertEqual((depois['a_enviar'], depois['custo_maximo_usd'], depois['do_cache']), (0, 0.0, True))
        self.assertEqual(c2.estimar(BLOCOS, self.pasta, 'gemini-3.8-flash')['a_enviar'], 1)  # outro modelo: cache próprio

    def test_verified_pointing_becomes_information_never_pending_or_blocking(self):
        cliente = ClienteFalso('gemini-3.8-flash', {"apontamentos": [apontamento()], "fenomenos_descartados": []})
        ocorrencias, avisos, rodada = self.analisar(cliente, 'gemini-3.8-flash')
        item, = ocorrencias
        self.assertEqual((item['rule'], item['paragraph'], item['source']), ('coerencia2_ia', 3, 'Coerencia 2.0 · IA (Gemini)'))
        self.assertEqual(item['related'][0]['paragraph'], 2)
        self.assertEqual(BLOCOS[2].text[item['start']:item['end']], 'o caminhão de entregas chegou pela ponte')
        mesa, diagnostico = politica.aplicar(ocorrencias)
        self.assertEqual((item['destino'], item['impeditivo']), ('informacao', False))
        self.assertTrue(mesa and not diagnostico)
        self.assertEqual((rodada['versao'], rodada['enviados'], cliente.pedidos), (2, 1, 1))
        self.assertTrue(any('nunca erros confirmados' in a for a in avisos))

    def test_invented_citation_is_dropped_and_manuscript_is_untouched(self):
        textos = [b.text for b in BLOCOS]
        inventado = apontamento(trecho_a='frase que não existe aqui', trecho_b='outra frase que também não existe')
        ocorrencias, _, rodada = self.analisar(ClienteFalso('claude-sonnet-5-5', {"apontamentos": [inventado], "fenomenos_descartados": []}))
        self.assertEqual((ocorrencias, rodada['rejeitados']), ([], 1))
        self.assertEqual([b.text for b in BLOCOS], textos)

    def test_partial_evidence_goes_to_diagnostic_not_to_the_desk(self):
        parcial = apontamento(trecho_b='frase que não existe no texto')
        ocorrencias, _, _ = self.analisar(ClienteFalso('claude-sonnet-5-5', {"apontamentos": [parcial], "fenomenos_descartados": []}))
        mesa, diagnostico = politica.aplicar(ocorrencias)
        self.assertEqual((len(mesa), len(diagnostico), ocorrencias[0]['coerencia2']['situacao']), (0, 1, 'inconclusiva'))

    def test_same_text_is_not_sent_twice(self):
        resposta = {"apontamentos": [apontamento()], "fenomenos_descartados": []}
        primeiro, _, _ = self.analisar(ClienteFalso('claude-sonnet-5-5', resposta))
        segundo_cliente = ClienteFalso('claude-sonnet-5-5')
        segundo, _, rodada = self.analisar(segundo_cliente)
        self.assertEqual((segundo_cliente.pedidos, rodada['enviados'], rodada['do_cache']), (0, 0, True))
        self.assertEqual([i['id'] for i in segundo], [i['id'] for i in primeiro])

    def test_too_long_manuscript_sends_nothing_and_says_so(self):
        longo = [Block(1, 'Capítulo 1', 'Capítulo 1', heading=True), Block(2, 'palavra ' * 50000, 'Capítulo 1')]
        cliente = ClienteFalso('claude-sonnet-5-5')
        ocorrencias, avisos, rodada = self.analisar(cliente, blocos=longo)
        self.assertEqual((ocorrencias, cliente.pedidos, rodada['cobertura']), ([], 0, 'nao_realizada'))
        self.assertTrue(any('não foi concluída' in a for a in avisos))

    def test_pipeline_dispatches_by_version_and_default_is_1x(self):
        opcoes = validate({})
        opcoes['rules'] = {r: False for r in opcoes['rules']}
        base = dict(pasta=self.pasta, documento='livro', modelo='claude-sonnet-5-5', teto=1.0, esforco='medium')
        with patch('fonte.coerencia2_ia.analisar', return_value=([], [], {'versao': 2})) as v2, \
             patch('fonte.coerencia_ia.analisar', return_value=([], [], {'versao': 1})) as v1:
            _, _, meta = run(BLOCOS, __import__('unittest.mock').mock.Mock(), settings=opcoes, mode='editorial', coerencia=dict(base, versao=2))
            self.assertEqual((v2.call_count, v1.call_count, meta['coerencia_ia']['versao']), (1, 0, 2))
            self.assertNotIn('versao', v2.call_args.kwargs)
            run(BLOCOS, __import__('unittest.mock').mock.Mock(), settings=opcoes, mode='editorial', coerencia=dict(base))
            self.assertEqual((v2.call_count, v1.call_count), (1, 1))

    def test_cli_estimate_selects_version_without_the_api(self):
        from docx import Document
        from fonte.cli import main
        caminho = Path(self.temp.name) / 't.docx'
        doc = Document()
        for texto in ['Capítulo 1', 'Lia tinha olhos verdes e não saiu de casa.']:
            doc.add_paragraph(texto)
        doc.save(caminho)
        for versao, esperado in (('2', 2), ('1', None)):
            saida = io.StringIO()
            with redirect_stdout(saida), patch('urllib.request.urlopen', side_effect=AssertionError('sem rede')), \
                 patch('coerencia.modelo.criar_modelo', side_effect=AssertionError('sem API')):
                main(['coerencia-estimar', str(caminho), '--coerencia-projeto', str(self.pasta), '--coerencia-versao', versao])
            linha, = [l for l in saida.getvalue().splitlines() if l.startswith('LUME_ESTIMATIVA ')]
            self.assertEqual(json.loads(linha.split(' ', 1)[1]).get('versao'), esperado)


if __name__ == '__main__':
    unittest.main()
