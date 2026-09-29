"""Contrato da memória narrativa, conflitos e contraprovas de escopo."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate
from fonte.semantic import RULES


class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, texts, enabled=RULES):
        blocks = [Block(i+1, t) if isinstance(t, str) else t for i,t in enumerate(texts)]
        options = validate({})
        options['rules'] = {r: r in enabled for r in options['rules']}
        before = deepcopy(blocks)
        result = run(blocks, lambda:self.nlp, settings=options, mode='editorial')
        self.assertEqual(blocks, before)
        return result

    def test_required_conflicts_and_shared_evidence(self):
        texts = ['Íris só usa fogo.', 'Íris criou gelo.', 'O pingente foi destruído.',
                 'O pingente intacto estava no bolso.', 'Adrian morreu em 18/09/2019.',
                 'Data atual: 17/09/2026.', 'Ontem fez sete anos.']
        found, _, meta = self.scan(texts)
        self.assertEqual([f['category_code'] for f in found], ['ability_conflict', 'object_state_conflict', 'chronology_conflict'])
        joined = '\n'.join(texts)
        for item in found:
            self.assertEqual(item['module'], 'global_coherence')
            self.assertEqual(item['severity'], 'possible_inconsistency')
            self.assertIsNone(item['suggestion'])
            self.assertGreaterEqual(len(item['evidence']), 2)
            for ev in item['evidence']:
                self.assertEqual(joined[ev['range']['start']:ev['range']['end']], ev['excerpt'])
        self.assertEqual(len([f for f in meta['fact_bank']['facts'] if not f['id'].startswith('fact_semantic_generic_')]), 7)
        self.assertEqual(meta['stages'][-1]['state'], 'not_implemented')
        json.dumps(meta, ensure_ascii=False)

    def test_ability_controls(self):
        cases = [
            ['Íris usa fogo.', 'Íris criou gelo.'],
            ['Íris só usa fogo.', 'Íris criou fogo.'],
            ['Íris só usa fogo.', 'Helena criou gelo.'],
            ['Íris só usa fogo.', 'Íris não criou gelo.'],
            ['Íris só usa fogo.', 'Se Íris criou gelo, ninguém viu.'],
            ['Íris só usa fogo.', '— Íris criou gelo.'],
            ['Íris só usa fogo.', '“Íris criou gelo.”'],
            ['Íris só usa fogo.', 'Íris aprendeu a usar gelo.', 'Íris criou gelo.'],
            ['Íris nunca conseguiu usar gelo.', 'Íris criou gelo.'],
            ['Íris criou gelo.', 'Íris só usa fogo.'],
        ]
        for texts in cases:
            with self.subTest(texts=texts): self.assertFalse(self.scan(texts)[0])

    def test_object_controls(self):
        for texts in [
            ['O pingente foi destruído.', 'O pingente foi restaurado.', 'O pingente estava intacto.'],
            ['O pingente não foi destruído.', 'O pingente estava intacto.'],
            ['O pingente vermelho foi destruído.', 'O pingente azul estava intacto.'],
            ['O pingente estava intacto.', 'O pingente foi destruído.'],
            ['— O pingente foi destruído.', 'O pingente estava intacto.'],
        ]:
            with self.subTest(texts=texts): self.assertFalse(self.scan(texts)[0])

    def test_chronology_controls(self):
        for texts in [
            ['Adrian morreu em 18/09/2019.', 'Hoje é 19/09/2026.', 'Ontem fez sete anos.'],
            ['Adrian morreu em 31/02/2019.', 'Hoje é 17/09/2026.', 'Ontem fez sete anos.'],
            ['Adrian morreu em 18/09/2019.', 'Ontem fez sete anos.'],
            ['Adrian morreu em 18/09/2019.', 'Helena morreu em 20/09/2019.', 'Hoje é 17/09/2026.', 'Ontem fez sete anos.'],
            ['Adrian morreu em 18/09/2019.', 'Hoje é 17/09/2026.', '***', 'Ontem fez sete anos.'],
        ]:
            with self.subTest(texts=texts): self.assertFalse(self.scan(texts)[0])

    def test_facts_cross_chapters_but_scene_dates_do_not(self):
        found, _, meta = self.scan([Block(2,'Íris só usa fogo.',chapter='Um'), Block(9,'Íris criou gelo.',chapter='Dois')])
        self.assertEqual(len(found), 1)
        self.assertEqual(len(meta['scenes']), 2)
        self.assertEqual(meta['scenes'][0]['end_paragraph'], 2)

    def test_speaker_action_objects_and_references(self):
        found, _, meta = self.scan(['— Você está bem? — perguntou Íris.',
                                   'Helena fechou a porta.', 'Ela pegou o objeto.'])
        scene = meta['scenes'][0]
        self.assertTrue(scene['dialogue_turns'][0]['speaker'])
        self.assertEqual(scene['dialogue_turns'][0]['speech_act'], 'question')
        self.assertTrue(any(p['role'] == 'actor' and p['name'] == 'Helena' for p in scene['participants']))
        self.assertTrue(scene['events'])
        self.assertTrue(scene['objects'])
        self.assertTrue(scene['references'])

    def test_required_dialogue_and_reference_cases(self):
        found, _, _ = self.scan(['— Não vou — Helena fechou a porta.'], ['dialogo_contextual'])
        self.assertEqual(found[0]['category_code'], 'narrative_action_after_speech')
        found, _, _ = self.scan(['No chão havia pedaços de madeira, pedras e uma espada quebrada.', 'Ela pegou o objeto.'], ['referente_contextual'])
        self.assertEqual(found[0]['category_code'], 'ambiguous_reference')

    def test_stable_identity_isolated_runs_and_disable(self):
        texts = ['Íris só usa fogo.', 'Íris criou gelo.']
        self.assertEqual(self.scan(texts)[0], self.scan(texts)[0])
        self.assertFalse(self.scan(['Íris criou gelo.'])[0])
        self.assertFalse(self.scan(texts, ['memoria_narrativa'])[0])
        options = validate({}); options['rules'] = {r:False for r in options['rules']}
        loader = Mock(side_effect=AssertionError('Não carregar NLP'))
        found, _, meta = run([Block(1,texts[0])], loader, settings=options)
        self.assertFalse(found)
        self.assertNotIn('fact_bank', meta)
        loader.assert_not_called()

    def test_unicode_nonconsecutive_offsets(self):
        blocks = [Block(2,'🌿 Introdução.',heading=True), Block(8,'Íris só usa fogo.'), Block(15,'Íris criou gelo.')]
        found, _, _ = self.scan(blocks)
        self.assertEqual(len(found), 1)
        joined = '\n'.join(b.text for b in blocks)
        for ev in found[0]['evidence']:
            self.assertEqual(joined[ev['range']['start']:ev['range']['end']], ev['excerpt'])


if __name__ == '__main__': unittest.main()
