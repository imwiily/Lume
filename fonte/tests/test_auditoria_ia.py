"""Auditoria final com IA: etapa do pipeline, com o auditor simulado (nenhum teste chama a API)."""
from dataclasses import asdict
import unittest
from unittest.mock import Mock, patch

from fonte.analysis import finding
from fonte.pipeline import run, STAGES
from fonte.reader import Block
from fonte.settings import validate


def selected(*names):
    settings = validate({})
    settings['rules'] = {r: r in names for r in settings['rules']}
    return settings


BLOCKS = [Block(1, 'Nada além de disso. A equipe trouxe as caixas que estava no carro.')]
SETTINGS = selected('construcao_invalida')


def achado(block, trecho):
    inicio = block.text.index(trecho)
    item = asdict(finding(block, 'Concordância', 'Verificar', inicio, inicio + len(trecho),
                          'Sujeito no plural com verbo no singular.', 'Auditoria · IA (Claude)'))
    item.update(rule='auditoria_ia', category_code='audit_agreement', severity='editorial_attention',
                confidence='média', confidence_score=.6, suggestion='estavam', suggestion_kind='possible')
    return item


class AuditStageTests(unittest.TestCase):
    def run_pipeline(self, auditoria=None, auditar=None):
        events = []
        if auditar is None:
            found = run(BLOCKS, Mock(), settings=SETTINGS, progress=events.append, auditoria=auditoria)
        else:
            with patch('fonte.auditoria_ia.auditar', side_effect=auditar):
                found = run(BLOCKS, Mock(), settings=SETTINGS, progress=events.append, auditoria=auditoria)
        return (*found, events)

    def test_audit_off_is_skipped_and_not_announced_as_missing(self):
        findings, warnings, meta, events = self.run_pipeline()
        stage = meta['stages'][-1]
        self.assertEqual((stage['module'], stage['state'], stage['coverage']), ('audit', 'skipped', 'partial'))
        self.assertEqual(events[-1]['state'], 'skipped')
        self.assertFalse(any('ainda não implementada' in w for w in warnings))
        self.assertNotIn('auditoria_ia', meta)
        self.assertFalse(any(f['module'] == 'audit' for f in findings))

    def test_audit_receives_previous_findings_and_only_adds(self):
        recebidos = {}

        def auditar(blocks, anteriores, avancar=None, **opcoes):
            recebidos.update(anteriores=[dict(f) for f in anteriores], opcoes=opcoes)
            # O auditor não consegue mudar o que as etapas anteriores emitiram.
            anteriores[0]['reason'] = 'alterado'
            anteriores.clear()
            return [achado(blocks[0], 'estava')], ['Auditoria final com IA: aviso simulado.'], {'enviados': 1}

        findings, warnings, meta, events = self.run_pipeline({'modelo': 'simulado'}, auditar)
        anteriores = [f for f in findings if f['module'] != 'audit']
        self.assertEqual(len(recebidos['anteriores']), len(anteriores))
        self.assertEqual({f['id'] for f in recebidos['anteriores']}, {f['id'] for f in anteriores})
        self.assertNotIn('alterado', [f['reason'] for f in findings])
        self.assertEqual(recebidos['opcoes'], {'modelo': 'simulado'})
        auditados = [f for f in findings if f['module'] == 'audit']
        self.assertEqual([f['excerpt'] for f in auditados], ['estava'])
        self.assertEqual(meta['stages'][-1]['state'], 'completed')
        self.assertEqual(meta['stages'][-1]['finding_count'], 1)
        self.assertEqual(meta['auditoria_ia'], {'enviados': 1})
        self.assertIn('Auditoria final com IA: aviso simulado.', warnings)
        self.assertEqual([(e['module'], e['state']) for e in events][-2:], [('audit', 'running'), ('audit', 'completed')])

    def test_audit_failure_keeps_the_report(self):
        # Decisão 5: erro da API marca só a auditoria como interrompida; as outras etapas ficam.
        def auditar(*_, **__):
            raise ValueError('Auditoria final com IA: sem conexão com a API da Anthropic.')

        findings, warnings, meta, events = self.run_pipeline({'modelo': 'simulado'}, auditar)
        self.assertEqual(meta['stages'][-1]['state'], 'failed')
        self.assertEqual([s['state'] for s in meta['stages'][:-1]].count('failed'), 0)
        self.assertTrue(findings)
        self.assertFalse(any(f['module'] == 'audit' for f in findings))
        self.assertTrue(any('sem conexão' in w and 'demais etapas' in w for w in warnings))
        self.assertEqual(events[-1]['state'], 'failed')

    def test_audit_interruption_is_not_swallowed(self):
        def auditar(*_, **__):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.run_pipeline({'modelo': 'simulado'}, auditar)

    def test_stage_order_is_unchanged(self):
        self.assertEqual(STAGES[-1], ('audit', 'Auditoria final'))


if __name__ == '__main__':
    unittest.main()
