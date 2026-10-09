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
        options['rules'] = {r: r == 'dialogo_contextual' for r in options['rules']}
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

    def test_window_is_bounded_and_stops_at_scene_change(self):
        # Antes da Fase 7b, com um alerta de gerundismo (retirado); agora, com ação depois da fala.
        blocks = [Block(1, 'Helena chegou.'), Block(2, '— Vamos embora — ela abriu a porta.'),
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


class RegrasRetiradas(unittest.TestCase):
    """Gerundismo e “o objeto” depois de enumeração foram retirados na Fase 7b (registro; exemplo
    isolado). As chaves continuam aceitas nas configurações e não produzem alertas."""

    def test_retired_contextual_rules_emit_nothing(self):
        settings = validate({'rules': {'gerundismo': True, 'referente_contextual': True}})
        self.assertNotIn('gerundismo', settings['rules'])
        nlp = spacy.load('pt_core_news_sm', disable=['ner'])
        found, _, _ = run([Block(1, 'No chão havia pedras e uma espada.'), Block(2, 'Ela pegou o objeto.'),
                           Block(3, 'Nós não vamos poder estar entregando o pedido hoje.')], lambda: nlp,
                          settings=settings, mode='editorial')
        self.assertFalse({'gerundismo', 'referente_contextual'} & {f['rule'] for f in found})


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
