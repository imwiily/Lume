import unittest
from unittest.mock import Mock
import spacy
from fonte.reader import Block
from fonte.settings import validate
from fonte.pipeline import run


class ContextualEditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, blocks, **kwargs):
        options = validate({})
        options['rules'] = {r: r in {'dialogo_contextual', 'referente_contextual', 'gerundismo'} for r in options['rules']}
        options.update(kwargs)
        return run(blocks, lambda: self.nlp, settings=options, mode='editorial')[0]

    def test_planted_dialogue_cases(self):
        for text in ['— Você entendeu o que eu disse, Helena — a voz de Helena falhou de repente.',
                     '— Pode ser que saibam — disse Helena — Só fingem que não.']:
            with self.subTest(text=text):
                f, = self.scan([Block(1, text)])
                self.assertEqual(f['rule'], 'dialogo_contextual')
                self.assertEqual(f['module'], 'editorial')
                self.assertEqual(f['severity'], 'editorial_attention')
                self.assertIsNone(f['suggestion'])

    def test_action_reason_names_missing_punctuation_and_example(self):
        # A mensagem diz o que falta e onde, com um exemplo montado do próprio texto.
        f, = self.scan([Block(1, '— Você entendeu o que eu disse, Helena — O rosto de Helena ficou pálido.')])
        self.assertIn('falta pontuação para encerrar a fala antes do travessão', f['reason'])
        self.assertIn('“O rosto de Helena…”', f['reason'])
        self.assertIn('Ex.: “…Helena. — O rosto de Helena…”', f['reason'])
        self.assertNotIn('maiúscula', f['reason'])
        # Fala aberta e ação em minúscula: as duas correções.
        f, = self.scan([Block(1, '— Vamos embora, Helena — ela pegou a bolsa.')])
        self.assertIn('falta pontuação para encerrar a fala antes do travessão', f['reason'])
        self.assertIn('maiúscula', f['reason'])
        self.assertIn('Ex.: “…Helena. — Ela pegou a bolsa…”', f['reason'])
        # Fala já encerrada: só a maiúscula, com a pontuação original no exemplo.
        f, = self.scan([Block(1, '— Você viu? — as mãos dela tremeram.')])
        self.assertNotIn('falta pontuação', f['reason'])
        self.assertIn('Ex.: “…viu? — As mãos dela tremeram…”', f['reason'])
        # A ressalva sobre a lista de elocução continua, no fim.
        self.assertIn('a lista de verbos de fala do Lume é limitada.', f['reason'])
        self.assertTrue(f['reason'].endswith('Na gramática: pontuação de diálogo com travessão.'))

    def test_clitic_action_offsets_and_standalone_verb(self):
        # Regressão: is_alpha pulava o verbo e gerava início > fim.
        for action, marked in [('virou-se Helena.', 'virou-se'),
                               ('aproximou-se da porta.', 'aproximou-se'),
                               ('sentou-se ao lado.', 'sentou-se'),
                               ('ergueu-se.', 'ergueu-se')]:
            with self.subTest(action=action):
                text = '— Não vou — ' + action
                f, = self.scan([Block(9, text)])
                self.assertEqual(f['category_code'], 'narrative_action_after_speech')
                self.assertEqual(f['excerpt'], marked)
                self.assertEqual(text[f['start']:f['end']], marked)
                self.assertEqual(text[f['range']['start']:f['range']['end']], marked)
                self.assertLess(f['start'], f['end'])
        self.assertFalse(self.scan([Block(1, '— Não vou. — Virou-se Helena.')]))

    def test_valid_dialogue_and_disabled_dashes(self):
        for text in ['— Pode ser que saibam — disse Helena. — Só fingem que não.',
                     '— Eu acho — disse Helena — que eles sabem.',
                     '— Você sabe — disse Helena — Maria.',
                     '— Você sabe. — As mãos de Helena tremeram.',
                     '— Você sabe — respondeu Helena.']:
            with self.subTest(text=text):
                self.assertFalse(self.scan([Block(1, text)]))
        self.assertFalse(self.scan([Block(1, '— Você sabe — as mãos tremeram.')], dialogue_dashes=False))

    def test_gerundism_is_optional_attention(self):
        f, = self.scan([Block(1, 'Nós não vamos poder estar entregando o pedido hoje.')])
        self.assertEqual(f['rule'], 'gerundismo')
        self.assertEqual(f['severity'], 'editorial_attention')
        self.assertEqual(f['excerpt'], 'vamos poder estar entregando')
        self.assertFalse(self.scan([Block(1, 'Eu estava dizendo isso agora.')]))
        self.assertFalse(self.scan([Block(1, '— Vamos poder — disse ela — estar conferindo isso.')]))

    def test_ambiguous_object_and_context_evidence(self):
        for split in [True, False]:
            before = 'No chão havia pedaços de madeira, pedras e uma espada quebrada.'
            current = 'Ela pegou o objeto.'
            blocks = [Block(3, before), Block(8, current)] if split else [Block(3, before + ' ' + current)]
            f, = self.scan(blocks)
            self.assertEqual(f['rule'], 'referente_contextual')
            self.assertEqual(f['severity'], 'author_query')
            self.assertEqual(f['excerpt'], 'objeto')
            self.assertGreaterEqual(len(f['related']), 2)
            self.assertEqual(len(f['context']), len(blocks))
            self.assertEqual(f['text'][f['start']:f['end']], 'objeto')

    def test_does_not_use_future_or_other_chapter_as_antecedent(self):
        enumeration = 'Havia pedras e espadas.'
        for blocks in [
            [Block(1, 'Ela pegou o objeto.'), Block(2, enumeration)],
            [Block(1, enumeration, chapter='A'), Block(2, 'Ela pegou o objeto.', chapter='B')],
            [Block(1, enumeration), Block(2, 'Capítulo', heading=True), Block(3, 'Ela pegou o objeto.')],
            [Block(1, enumeration), Block(2, 'No dia seguinte, ela pegou o objeto.')],
            [Block(1, 'Havia uma espada.'), Block(2, 'Ela pegou o objeto.')],
        ]:
            with self.subTest(blocks=blocks): self.assertFalse(self.scan(blocks))

    def test_window_is_bounded_and_stops_at_scene_change(self):
        blocks = [Block(1, 'Helena chegou.'), Block(2, 'Nós vamos poder estar conferindo isso.'),
                  Block(3, 'Ela saiu.'), Block(4, 'No dia seguinte, voltou.'), Block(5, 'Fim.')]
        f, = self.scan(blocks)
        self.assertEqual([e['paragraph'] for e in f['context']], [1, 2, 3])
        self.assertTrue(f['scene_evidence']['participants'])

    def test_disable_all_preserves_no_model_loading(self):
        settings = validate({})
        settings['rules'] = {r: False for r in settings['rules']}
        loader = Mock(side_effect=AssertionError('Modelo desnecessário'))
        found, _, _ = run([Block(1, 'Vou estar dizendo isso.')], loader, settings=settings)
        self.assertFalse(found)
        loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class SpeechVerbMissedByModelTests(unittest.TestCase):
    """O modelo pequeno às vezes não vê o verbo de fala logo após o travessão."""
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    scan = ContextualEditorialTests.scan

    def test_speech_verb_before_gerund_or_second_clause(self):
        for text in ['— Já vou, senhora! — respondi, tropeçando enquanto subia a escada.',
                     '— Pode deixar, Baltasar — falei, procurando a chave, mas estava sem óculos.',
                     '— A reunião acabou e todos podem sair — terminou Laura.',
                     '— A reunião acabou e todos podem sair — terminou o diretor.',
                     '— As duas turmas serão avisadas e Ana voltará amanhã cedo — terminou Tadeu.']:
            with self.subTest(text=text):
                self.assertFalse(self.scan([Block(1, text)]))
        # Ação sem verbo de fala continua apontada.
        f, = self.scan([Block(1, '— Pode deixar — procurei a chave na bolsa, mas estava sem óculos.')])
        self.assertEqual(f['rule'], 'dialogo_contextual')
