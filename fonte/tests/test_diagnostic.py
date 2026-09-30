"""Regressão dos trechos do diagnóstico; não mede precisão em obras reais."""
from copy import deepcopy
import unittest
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate


class DiagnosticRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, text, settings=None):
        return run([Block(1, text)], lambda: self.nlp,
                   settings=settings or validate({}), tense='passado')[0]

    def test_known_linguistic_cases(self):
        cases = [
            ('LUME-LING-001', 'Íris você não deveria estar aqui.', 'vocativo', 'Íris,'),
            ('LUME-LING-002', 'Íris não faça isso.', 'vocativo', 'Íris,'),
            ('LUME-LING-003', 'a velha torre, que, não estava mais abandonada.', 'virgula_que_nao', 'que não'),
            ('LUME-LING-004', '— O que?', 'que_tonico_interrogativo', 'quê'),
            ('LUME-LING-005', 'Não restava nada além de disso.', 'construcao_invalida', 'além disso'),
            ('LUME-LING-006', 'Esses homens.. São muito estranhos.', 'pontuacao_duplicada', None),
            ('LUME-LING-007', 'Ela  chegou.', 'espacamento', ' '),
            ('LUME-LING-008', 'Quem veio? você sabe?', 'capitalizacao_contextual', ' Você'),
        ]
        for case, text, rule, suggestion in cases:
            with self.subTest(id=case):
                findings = [f for f in self.scan(text) if f.get('rule') == rule]
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]['module'], 'linguistic')
                self.assertEqual(findings[0]['suggestion'], suggestion)
                self.assertIn(findings[0]['suggestion_kind'], ['possible', 'required'])

    def test_known_temporal_cases(self):
        cases = [
            ('LUME-TEMP-001', 'Tomás iria propor um plano que não irá dar nada certo.', 'conditional_future'),
            ('LUME-TEMP-002', '— Desde nunca — respondeu ele enquanto caminhamos em direção à torre.', 'ambiguous_simultaneity'),
            ('LUME-TEMP-003', '— Ele parece machucado — disse Íris enquanto se aproxima dele.', 'simultaneous_present'),
        ]
        for case, text, relation in cases:
            with self.subTest(id=case):
                self.assertTrue(any(f.get('relation') == relation for f in self.scan(text)))
        self.assertTrue(any(f.get('suggestion') == 'caíam' for f in self.scan('A chuva caiam lentamente.')))

    def test_temporal_negative_controls_in_complete_pipeline(self):
        cases = [
            'Tomás sofreu um acidente e está no hospital.',
            'Eu vi tudo e posso garantir isso.',
            'Tomás havia quebrado o braço na semana anterior e está completamente bem agora.',
            'Você só queria me impedir de vir, não é?',
            'Ela caiu e está ferida.',
            'O rapaz adoeceu e está em casa.',
        ]
        for i, text in enumerate(cases, 1):
            for prefix in ['', '— ', '“']:
                with self.subTest(id=f'LUME-TEMP-NEG-{i:03}', prefix=prefix):
                    settings = validate({'tense_scopes': ['narracao', 'dialogo', 'pensamento']})
                    findings = self.scan(prefix + text + ('”' if prefix == '“' else ''), settings)
                    self.assertFalse([f for f in findings if f['category_code'] in {'temporal_consistency', 'narrative_tense'}])

    def test_all_document_time_markers(self):
        for marker in ['agora', 'hoje', 'atualmente', 'neste momento', 'ainda', 'desde então', 'neste instante', 'no momento']:
            with self.subTest(marker=marker):
                findings = self.scan(f'O objeto parecia intacto e está quebrado {marker}.')
                self.assertFalse([f for f in findings if f['category_code'] in {'temporal_consistency', 'narrative_tense'}])

    def test_preserves_real_action_changes(self):
        for text in ['O assistente abriu a mala e retira o equipamento.',
                     'Ele saiu ontem e retira o equipamento.',
                     'Ela trabalhava enquanto as crianças brincam no quintal.']:
            with self.subTest(text=text):
                self.assertTrue(any(f['category_code'] == 'temporal_consistency' for f in self.scan(text)))

    def test_contracted_suggestion_offsets_and_deduplication(self):
        text = '🌿 Cafe\u0301. Tomás iria propor um plano que irá ser muito caro.'
        blocks = [Block(3, 'Capítulo 1', heading=True), Block(8, text)]
        before = deepcopy(blocks)
        found, _, _ = run(blocks, lambda: self.nlp, tense='passado')
        f, = [f for f in found if f.get('relation') == 'conditional_future']
        self.assertEqual(f['excerpt'], 'irá ser')
        self.assertEqual(f['suggestion'], 'seria')
        self.assertEqual(text[:f['start']] + f['suggestion'] + text[f['end']:],
                         text.replace('irá ser', 'seria'))
        joined = '\n'.join(b.text for b in blocks)
        self.assertEqual(joined[f['range']['start']:f['range']['end']], 'irá ser')
        self.assertFalse([g for g in found if g['category_code'] == 'narrative_tense' and g['start'] == f['start']])
        self.assertEqual(blocks, before)

    def test_vocatives_generalize_and_preserve_subjects(self):
        for name in ['Marina', 'Otávio', 'João Pedro', 'I\u0301ris']:
            for template in ['{} você deveria voltar.', '— {} não faça isso.', '“{} não toque nisso.”']:
                with self.subTest(name=name, template=template):
                    self.assertTrue(any(f.get('rule') == 'vocativo' for f in self.scan(template.format(name))))
        for text in ['Íris, você não deveria estar aqui.', 'Íris não fez isso.', 'Helena saiu.',
                     'Talvez você consiga.', 'Hoje você decide.', 'Se você quiser.',
                     'Quem veio? Você sabe?', '— Pare! disse ele.', 'Ela disse... você sabe.']:
            with self.subTest(text=text):
                self.assertFalse([f for f in self.scan(text) if f.get('rule') in {'vocativo', 'capitalizacao_contextual'}])

    def test_new_rules_respect_settings_and_headings(self):
        settings = validate({'rules': {'vocativo': False, 'capitalizacao_contextual': False}})
        self.assertFalse([f for f in self.scan('Íris você veio? você sabe?', settings)
                          if f.get('rule') in {'vocativo', 'capitalizacao_contextual'}])
        found, _, _ = run([Block(1, 'Íris você veio?', heading=True)], lambda: self.nlp)
        self.assertFalse(found)


if __name__ == '__main__':
    unittest.main()
