"""Regressões da etapa 1: cobertura real, proteção de voz e contrato modular."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from docx import Document
from fonte.cli import main
from fonte.contracts import Manuscript, standardize
from fonte.linguistic import analyze, RULES as LINGUISTIC_RULES
from fonte.pipeline import run, STAGES
from fonte.reader import Block
from fonte.settings import validate, LEGACY_RULES, NEW_RULES


def selected(*names):
    settings = validate({})
    settings['rules'] = {r: r in names for r in settings['rules']}
    return settings


class DeterministicTests(unittest.TestCase):
    def scan(self, text, **kwargs):
        return analyze([Block(1, text, **kwargs)], validate({}))

    def test_hns_alem_de_disso(self):
        f, = self.scan('Não restava nada além de disso.')
        self.assertEqual(f['severity'], 'confirmed_error')
        self.assertEqual(f['suggestion'], 'além disso')
        self.assertEqual(f['text'][f['start']:f['end']], 'além de disso')

    def test_hns_two_periods_has_no_single_forced_solution(self):
        f, = self.scan('Esses humanos.. São tão estranhos.')
        self.assertEqual(f['severity'], 'probable_error')
        self.assertIsNone(f['suggestion'])

    def test_hns_que_nao(self):
        f, = self.scan('Ele tinha um sorriso, que, não era normal.')
        self.assertEqual(f['rule'], 'virgula_que_nao')
        self.assertEqual(f['suggestion'], 'que não')
        self.assertEqual(f['severity'], 'probable_error')

    def test_que_parenthetical_exceptions(self):
        for text in ['O homem que, não obstante o frio, saiu cedo.',
                     'Ele disse que, não, aquilo não era verdade.',
                     'Ele disse que, não só por mim, iria voltar.']:
            with self.subTest(text=text):
                self.assertFalse(self.scan(text))

    def test_valid_expressive_and_colloquial_text(self):
        for text in ['Além disso, os cabelos caíam sobre o rosto.',
                     'Talvez os cabelos caiam sobre o rosto.',
                     'Ele esperou... Depois saiu…', 'O quê?! Não!! Será??',
                     '— Tô aqui, cê vem pro jantar, primo?',
                     'Apenas você, Clara.', 'Ontem caminhamos até lá.']:
            with self.subTest(text=text):
                self.assertFalse(self.scan(text))

    def test_quotes_thoughts_preserve_voice_but_check_punctuation(self):
        for text in ['— Nada além de disso,,', '“Nada além de disso,,”', '«Nada além de disso,,»']:
            with self.subTest(text=text):
                findings = self.scan(text)
                self.assertEqual([f['rule'] for f in findings], ['pontuacao_duplicada'])
                self.assertEqual(findings[0]['severity'], 'probable_error')
        text = 'Nada além de disso,, '
        self.assertEqual([f['rule'] for f in self.scan(text, italic=[(0, len(text))])], ['pontuacao_duplicada'])
        self.assertFalse(self.scan(text, heading=True))

    def test_narrative_incise_still_checked(self):
        f, = self.scan('— Tô aqui — ele disse,, sem olhar. — E cê?')
        self.assertEqual(f['rule'], 'pontuacao_duplicada')

    def test_no_phrase_assembled_across_quotes_or_lines(self):
        for text in ['Nada além de “disso”.', 'Nada além de\ndisso.',
                     'Havia algo além “de” disso.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_spacing_and_suggestions(self):
        for text, replacement in [('Ele  saiu.', ' '), ('Ele saiu , sim.', ''), ('Ele,, saiu.', ',')]:
            f, = self.scan(text)
            self.assertEqual(f['suggestion'], replacement)

    def test_indentation_not_treated_as_word_spacing(self):
        self.assertFalse(self.scan('  Ele saiu.\n    Depois voltou.'))

    def test_rules_can_be_disabled(self):
        self.assertFalse(analyze([Block(1, 'Nada além de disso,, que, não  era normal.')], selected()))


class PipelineTests(unittest.TestCase):
    def test_immutable_snapshot_including_nested_ranges(self):
        source = Block(3, 'Olá 🌿', italic=[(0, 3)])
        manuscript = Manuscript.capture([source])
        source.italic.append((4, 5))
        source.text = 'mudança externa'
        self.assertEqual(manuscript.blocks[0].italic, ((0, 3),))
        self.assertEqual(manuscript.text, 'Olá 🌿')
        with self.assertRaises(FrozenInstanceError):
            manuscript.blocks[0].text = 'alterado'

    def test_unicode_global_ranges_with_headings_and_noncontiguous_numbers(self):
        blocks = [Block(2, 'Capítulo 1', heading=True),
                  Block(7, '🌿 Cafe\u0301. Nada além de disso.'),
                  Block(11, 'Ele,, saiu.')]
        original = deepcopy(blocks)
        loader = Mock(side_effect=AssertionError('Modelo não é necessário'))
        findings, _, meta = run(blocks, loader, settings=selected(*LINGUISTIC_RULES))
        text = '\n'.join(b.text for b in blocks)
        self.assertEqual(len(findings), 2)
        for f in findings:
            self.assertEqual(text[f['range']['start']:f['range']['end']], f['excerpt'])
            self.assertEqual(f['text'][f['start']:f['end']], f['excerpt'])
            self.assertEqual(f['module'], 'linguistic')
            self.assertEqual(f['message'], f['reason'])
        self.assertEqual(blocks, original)
        self.assertEqual(meta['text_index']['length'], len(text))
        loader.assert_not_called()

    def test_strict_order_and_truthful_audit(self):
        events = []
        blocks = [Block(1, 'Nada além de disso. Era melhor eu me preparar melhor. Lívia chegou. Lívia saiu. Lívya voltou.')]
        settings = selected('construcao_invalida', 'estrutura', 'palavra_proxima', 'variacao_nome')
        with patch('fonte.search.analyze', return_value=([], [], {'tempo': 'não analisado'})):
            findings, _, meta = run(blocks, Mock(), settings=settings, progress=events.append)
        expected = []
        for module, _ in STAGES[:-1]:
            expected.extend([(module, 'running'), (module, 'completed')])
        expected.append(('audit', 'not_implemented'))
        self.assertEqual([(x['module'], x['state']) for x in events], expected)
        self.assertEqual(sum(s['finding_count'] for s in meta['stages']), len(findings))
        self.assertEqual({f['module'] for f in findings}, {'linguistic', 'editorial', 'global_coherence'})
        self.assertFalse(any(f['module'] == 'audit' for f in findings))

    def test_failure_stops_following_stages(self):
        events = []
        with patch('fonte.linguistic.analyze', side_effect=RuntimeError('falha de teste')):
            with self.assertRaises(RuntimeError):
                run([Block(1, 'Nada além de disso.')], Mock(), progress=events.append)
        self.assertEqual([(x['module'], x['state']) for x in events],
                         [('linguistic', 'running'), ('linguistic', 'failed')])

    def test_legacy_ids_preserved(self):
        from fonte.editorial import analyze as legacy
        blocks = [Block(1, 'Era melhor eu me preparar melhor.')]
        settings = selected('palavra_proxima')
        old, _ = legacy(blocks, settings=settings)
        new, _, _ = run(blocks, Mock(), settings=settings)
        self.assertEqual([f['id'] for f in old], [f['id'] for f in new])

    def test_legacy_settings_migration_preserves_all_disabled(self):
        settings = validate({'rules': {r: False for r in LEGACY_RULES}})
        loader = Mock(side_effect=AssertionError('Modelo não é necessário'))
        findings, _, meta = run([Block(1, 'Nada além de disso,,')], loader, settings=settings)
        self.assertEqual(findings, [])
        self.assertTrue(all(s['state'] == 'skipped' for s in meta['stages'][:-1]))
        self.assertFalse(any(settings['rules'].values()))
        self.assertTrue(validate({'rules': {r: True for r in LEGACY_RULES}})['rules']['construcao_invalida'])

    def test_invalid_offsets_rejected(self):
        blocks = [Block(1, 'Nada além de disso.')]
        raw = analyze(blocks, validate({}))
        raw[0]['end'] = 1000
        with self.assertRaises(ValueError): standardize(raw, 'linguistic', Manuscript.capture(blocks))

    def test_invalid_occurrence_is_dropped_alone_when_asked(self):
        blocks = [Block(1, 'Nada além de disso,,')]
        raw = analyze(blocks, validate({}))
        self.assertGreaterEqual(len(raw), 2)
        broken = deepcopy(raw)
        broken[0]['start'], broken[0]['end'] = 8, 7  # trecho invertido
        rejected = []
        kept = standardize(broken, 'linguistic', Manuscript.capture(blocks), rejected=rejected)
        self.assertEqual([f['id'] for f in kept], [f['id'] for f in raw[1:]])
        self.assertEqual([(r['paragraph'], r['start'], r['end']) for r in rejected], [(1, 8, 7)])
        # Evidência fora do parágrafo também descarta só aquela ocorrência.
        broken = deepcopy(raw)
        broken[1]['evidence'] = [dict(paragraph=1, text=blocks[0].text, start=0, end=999, document='atual')]
        rejected = []
        kept = standardize(broken, 'linguistic', Manuscript.capture(blocks), rejected=rejected)
        self.assertEqual(len(kept), len(raw) - 1)
        self.assertEqual(len(rejected), 1)

    def test_pipeline_keeps_the_stage_when_one_occurrence_is_invalid(self):
        blocks = [Block(1, 'Nada além de disso,,')]
        def faulty(blocks, options):
            out = analyze(blocks, options)
            out[0] = dict(out[0], start=8, end=7)
            return out
        expected = len(analyze(blocks, validate({}))) - 1
        with patch('fonte.linguistic.analyze', side_effect=faulty):
            findings, warnings, meta = run(blocks, Mock(), settings=selected(*LINGUISTIC_RULES), mode='linguistica')
        self.assertEqual(len([f for f in findings if f['module'] == 'linguistic']), expected)
        self.assertEqual(meta['stages'][0]['state'], 'completed')
        self.assertEqual(len(meta['ocorrencias_descartadas']), 1)
        self.assertTrue(any('descartado' in w for w in warnings))

    def test_consecutive_is_executed_once(self):
        findings, _, _ = run([Block(1, 'Ele foi foi até a rua.')], Mock(), settings=selected('palavra_consecutiva'))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['module'], 'linguistic')

    def test_original_comparison_works_with_immutable_blocks(self):
        from fonte.editorial import analyze as legacy
        old = [Block(1, 'A médica se aproximou. A assistente trouxe os exames e os laudos. Ela explicou tudo.')]
        new = [Block(1, 'A médica se aproximou. Ela explicou tudo.')]
        settings = selected('pronome_apos_corte')
        expected, _ = legacy(new, old, settings)
        found, _, _ = run(new, Mock(), original=old, settings=settings)
        self.assertEqual([f['id'] for f in expected], [f['id'] for f in found])

    def test_cli_preserves_bytes_and_publishes_only_after_completion(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td); path = folder / "Livro d'Água 🌿.docx"
            document = Document(); document.add_paragraph('🌿 Cafe\u0301. Nada além de disso.'); document.save(path)
            original = path.read_bytes()
            config = folder / 'config.json'
            config.write_text(json.dumps(selected(*LINGUISTIC_RULES)))
            output = folder / 'saída'
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(['revisar', str(path), '--saida', str(output), '--config', str(config)])
            self.assertEqual(code, 0)
            report = json.loads((output / 'relatorio.json').read_text())
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(report['findings'][0]['excerpt'], 'além de disso')
            events = [json.loads(x.removeprefix('LUME_PROGRESS ')) for x in stdout.getvalue().splitlines() if x.startswith('LUME_PROGRESS ')]
            self.assertEqual(events[-1]['state'], 'not_implemented')
            self.assertEqual(report['metadata']['stages'][-1]['state'], 'not_implemented')
            failed_output = folder / 'falha'
            with patch('fonte.pipeline.standardize', side_effect=RuntimeError('simulada')), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main(['revisar', str(path), '--saida', str(failed_output), '--config', str(config)])
            self.assertEqual(code, 2)
            self.assertFalse(failed_output.exists())
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
