import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from docx import Document
from fonte.reader import Block
from fonte.editorial import analyze
from fonte.cli import main


def blocks(*texts):
    return [Block(i+1, text, 'Capítulo 1') for i, text in enumerate(texts)]


class EditorialTests(unittest.TestCase):
    def rules(self, *texts):
        return {f['rule'] for f in analyze(blocks(*texts))[0]}

    def test_four_versus_three(self):
        self.assertIn('duracao_suspensao', self.rules('Não trabalha amanhã nem nos três dias seguintes.', 'O técnico foi afastado por três dias.'))

    def test_consistent_four_days(self):
        self.assertNotIn('duracao_suspensao', self.rules('Não trabalha amanhã nem nos três dias seguintes.', 'Você foi afastado por quatro dias.'))

    def test_numbers(self):
        self.assertIn('duracao_suspensao', self.rules('Não abre a loja amanhã e nos 2 dias seguintes. Está suspensa por 2 dias.'))

    def test_no_chapter_crossing(self):
        bs = blocks('Não trabalha amanhã nem nos três dias seguintes.', 'Capítulo 2', 'O técnico foi afastado por três dias.')
        bs[1].heading = True
        self.assertNotIn('duracao_suspensao', {f['rule'] for f in analyze(bs)[0]})

    def test_no_scene_crossing(self):
        self.assertNotIn('duracao_suspensao', self.rules('Não trabalha amanhã nem nos três dias seguintes.', 'No dia seguinte, retornou.', 'O técnico foi afastado por três dias.'))

    def test_tomorrow(self):
        self.assertIn('adiamento_amanha', self.rules('A entrega foi adiada para amanhã.', 'Ganhei mais dois dias para terminar o projeto.'))
        self.assertNotIn('adiamento_amanha', self.rules('A entrega foi adiada para amanhã.', 'Ganhei mais um dia para terminar o projeto.'))

    def test_unrelated_tomorrow(self):
        self.assertNotIn('adiamento_amanha', self.rules('Amanhã veremos o resultado.', 'Ganhei mais dois dias.'))

    def test_duplicate(self):
        self.assertIn('frase_duplicada', self.rules('Ele começou a me explicar o mapa da região.', 'Ele começou a me explicar o mapa da região.'))

    def test_short_dialogue_not_duplicate(self):
        self.assertNotIn('frase_duplicada', self.rules('Sim, senhor.', 'Sim, senhor.'))

    def test_repeated_word(self):
        self.assertIn('palavra_proxima', self.rules('Era melhor eu me preparar melhor.'))
        self.assertNotIn('palavra_proxima', self.rules('Não, não! Eu sabia que eu conseguiria.'))

    def test_names(self):
        self.assertIn('variacao_nome', self.rules('Lívia entrou. Lívia sorriu.', 'Lívya voltou.'))

    def test_pronouns_and_interjections_are_not_names(self):
        self.assertNotIn('variacao_nome', self.rules('Você voltou. Você entrou. Vocês saíram.', 'Haaa! Haaa! Haaaa!', 'Hamm. Hamm. Humm. Humm.'))

    def test_different_evidence_changes_identity(self):
        a = analyze(blocks('Não trabalha amanhã nem nos três dias seguintes.', 'Foi afastado por três dias.'))[0]
        b = analyze(blocks('Não trabalha amanhã nem nos três dias seguintes.', 'Foi afastado por dois dias.'))[0]
        self.assertNotEqual(a[0]['id'], b[0]['id'])

    def test_distinct_names(self):
        self.assertNotIn('variacao_nome', self.rules('Lívia entrou. Lívia sorriu.', 'Otávio voltou.'))

    def test_reference(self):
        self.assertIn('referente_proximidade', self.rules('A doutora se aproximou.', 'Eles estavam tão perto!'))
        self.assertNotIn('referente_proximidade', self.rules('Os olhos dela brilhavam.', 'Eles estavam tão perto!'))

    def test_cut_and_reference(self):
        original = blocks('A médica se aproximou. Seus olhos azuis brilhavam intensamente sob a luz branca da sala.', 'Eles estavam tão perto!')
        revised = blocks('A médica se aproximou.', 'Eles estavam tão perto!')
        findings, _ = analyze(revised, original)
        scars = [f for f in findings if f['rule'] == 'pronome_apos_corte']
        self.assertEqual(len(scars), 1)
        self.assertEqual(scars[0]['related'][0]['document'], 'original')
        self.assertFalse(any(f['rule'] == 'pronome_apos_corte' for f in analyze(original, original)[0]))

    def test_unicode_and_stable_ids(self):
        bs = blocks('🌿 Cafe\u0301. Era melhor eu me preparar melhor.', 'Não trabalha amanhã nem nos três dias seguintes.', 'Foi afastado por três dias.')
        findings, _ = analyze(bs)
        self.assertEqual(findings, analyze(bs)[0])
        self.assertEqual(len(findings), len({f['id'] for f in findings}))
        for f in findings:
            self.assertTrue(0 <= f['start'] < f['end'] <= len(f['text']))
            for e in f['related'] + f['context']:
                self.assertTrue(0 <= e['start'] <= e['end'] <= len(e['text']))

    def test_cli_editorial_no_model_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / "Livro d'água 🌿.docx"
            doc = Document()
            doc.add_paragraph('Era melhor eu me preparar melhor.')
            doc.save(path)
            before = path.read_bytes()
            output = folder / 'resultado'
            config = folder / 'busca.json'
            config.write_text(json.dumps({'rules': {
                'dialogo_contextual': False, 'referente_contextual': False, 'gerundismo': False,
                'memoria_narrativa': False, 'conflito_habilidade': False,
                'conflito_objeto': False, 'conflito_cronologia': False, 'coerencia_generica': False}}))
            args = ['revisar', str(path), '--modo', 'editorial', '--saida', str(output), '--config', str(config)]
            with patch('fonte.cli.load_model', side_effect=AssertionError('Editorial não deve carregar spaCy')):
                self.assertEqual(main(args), 0)
            report = json.loads((output / 'relatorio.json').read_text())
            self.assertEqual(report['metadata']['modo'], 'editorial')
            self.assertEqual(report['sha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual(path.read_bytes(), before)
            self.assertIn('palavra_proxima', {f['rule'] for f in report['findings']})
            self.assertEqual(main(args), 2)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_both_and_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            original, revised = folder/'original.docx', folder/'revisado.docx'
            doc = Document()
            doc.add_paragraph('A médica se aproximou. Seus olhos azuis brilhavam intensamente sob a luz branca da sala.')
            doc.add_paragraph('Eles estavam tão perto!')
            doc.save(original)
            doc.paragraphs[0].text = 'A médica se aproximou.'
            doc.save(revised)
            self.assertEqual(main(['revisar', str(revised), '--original', str(original), '--modo', 'ambas', '--saida', str(folder/'out')]), 0)
            report = json.loads((folder/'out/relatorio.json').read_text())
            self.assertEqual(report['metadata']['original_sha256'], hashlib.sha256(original.read_bytes()).hexdigest())
            self.assertTrue(any(f['rule'] == 'pronome_apos_corte' for f in report['findings']))

    def test_invalid_mode_combinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'test.docx'
            doc = Document(); doc.add_paragraph('Texto de teste.'); doc.save(path)
            self.assertEqual(main(['revisar', str(path), '--modo','editorial','--languagetool']), 2)
            self.assertEqual(main(['revisar', str(path), '--original', str(path)]), 2)

if __name__ == '__main__':
    unittest.main()


class ExpressiveRepetitionTests(unittest.TestCase):
    def rules(self, *texts):
        return {f['rule'] for f in analyze(blocks(*texts))[0]}

    def test_parallel_sentences_and_short_echo_are_expressive(self):
        for text in ['Ainda conseguia enxergar. Ainda conseguia correr.',
                     'Um passo. Depois, outro. E outro.',
                     'Mais um golpe. E outro golpe.']:
            with self.subTest(text=text):
                self.assertNotIn('palavra_proxima', self.rules(text))
        for text in ['Senti a chuva atravessar meu casaco. Meu casaco ficou encharcado.',
                     'Olhei para a janela. Depois olhei para a porta.']:
            with self.subTest(text=text):
                self.assertIn('palavra_proxima', self.rules(text))

    def test_onomatopoeia_reduplication_is_not_a_typo(self):
        from fonte.editorial.repetition import analyze as repetition

        def consecutive(text):
            return [f for f in repetition(blocks(text)) if f['rule'] == 'palavra_consecutiva']
        for text in ['— Au au, quieto aí, ninguém vai te machucar.', '— Blá blá, sempre a mesma história.']:
            with self.subTest(text=text):
                self.assertEqual(consecutive(text), [])
        self.assertTrue(consecutive('Ele saiu saiu de casa cedo.'))
