"""Variações sintéticas e contraprovas; não estimam precisão em obras reais."""
from copy import deepcopy
import unittest
from unittest.mock import Mock
import spacy

from fonte.linguistic import analyze as mechanical
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate, LEGACY_RULES
from fonte.temporal import analyze
from fonte.tempo import tempo_estrito as form


def options(*rules):
    value = validate({})
    value['rules'] = {r: r in rules for r in value['rules']}
    return value


class TemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, text, settings=None, tense='passado', **kwargs):
        return analyze([Block(1, text, **kwargs)], self.nlp,
                       settings or options('coerencia_temporal', 'acentuacao_contextual'), tense)

    def test_reference_conditional_future(self):
        f, = self.scan('Ele iria propor um plano que irá ser muito caro.')
        self.assertEqual(f['relation'], 'conditional_future')
        self.assertEqual(f['severity'], 'probable_error')
        self.assertEqual(f['suggestion'], 'seria')
        self.assertEqual(f['text'][f['start']:f['end']], 'irá ser')
        self.assertEqual(f['temporal_evidence']['anchor'], 'iria')

    def test_conditional_generalizes_verbs_and_subjects(self):
        cases = [
            ('Ela compraria uma casa que terá um jardim.', 'teria'),
            ('Eu aceitaria um cargo que exigirá dedicação.', 'exigiria'),
            ('O artesão fabricaria um vaso que receberá pinturas.', 'receberia'),
            ('Nós construiríamos uma ponte que ligará as margens.', 'ligaria'),
            ('O escritor criaria um personagem que viverá no campo.', 'viveria'),
        ]
        for text, suggestion in cases:
            with self.subTest(text=text):
                f, = self.scan(text)
                self.assertEqual(f['relation'], 'conditional_future')
                self.assertEqual(f['suggestion'], suggestion)

    def test_replacing_character_names_does_not_change_rule(self):
        for subject in ['Marina', 'Otávio', 'A médica', 'O professor']:
            with self.subTest(subject=subject):
                f, = self.scan(subject + ' compraria uma casa que terá um jardim.')
                self.assertEqual(f['relation'], 'conditional_future')

    def test_conditional_lexical_ending_recovers_model_mistag(self):
        token = self.nlp('Nós construiríamos uma ponte.')[1]
        self.assertEqual(form(token), 'conditional')

    def test_consistent_conditional_preserved(self):
        for text in ['O sobrinho venderia o carro que ninguém compraria.',
                     'Ela compraria uma casa que teria um jardim.',
                     'Nós construiríamos uma ponte que ligaria as margens.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_explicit_separate_future_anchor_preserved(self):
        for text in ['Ela compraria uma casa que terá um jardim no próximo ano.',
                     'Ele aceitaria um emprego que começará amanhã.',
                     'Ele compraria a casa. Ela terá um jardim.',
                     'Ele compraria a casa; ela terá um jardim.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_simultaneous_present_with_different_vocabulary(self):
        for text, suggestion in [
            ('Ela trabalhava enquanto as crianças brincam no quintal.', 'brincavam'),
            ('A enfermeira explicava o procedimento enquanto os alunos anotam.', 'anotavam'),
            ('O guarda observava a entrada enquanto os turistas conversam.', 'conversavam'),
        ]:
            with self.subTest(text=text):
                f, = self.scan(text)
                self.assertEqual(f['relation'], 'simultaneous_present')
                self.assertEqual(f['suggestion'], suggestion)

    def test_consistent_simultaneity_preserved(self):
        for text in ['Ela trabalhava enquanto as crianças brincavam no quintal.',
                     'Ela trabalha enquanto as crianças brincam no quintal.',
                     'Enquanto as crianças brincavam, ela trabalhava.',
                     'Quando chegamos, ele abriu a porta.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_homograph_never_becomes_confirmed_or_probable_error(self):
        for text in ['Disse ela enquanto seguimos até a praça.',
                     'O guia esperou enquanto atravessamos a ponte.',
                     'Ela chorou enquanto nós cantamos.']:
            with self.subTest(text=text):
                f, = self.scan(text)
                self.assertEqual(f['relation'], 'ambiguous_simultaneity')
                self.assertEqual(f['severity'], 'editorial_attention')
                self.assertIsNone(f['suggestion'])
                self.assertIn('pretérito perfeito', f['reason'])

    def test_explicit_bounded_perfect_interval_preserved(self):
        self.assertFalse(self.scan('Ele discursou enquanto permanecemos na sala por duas horas.'))

    def test_while_contrast_preserved(self):
        self.assertFalse(self.scan('Ele gostava de poesia, enquanto ela prefere romances.'))

    def test_nested_coordination_and_simple_coordination(self):
        # Estado no presente coordenado a um passado: a implementação continua a mesma (atenção
        # editorial), mas a relação está desativada desde a Fase 7b e não é emitida na análise.
        for text in ['Parecia estar ligado normalmente e não está desligado.',
                     'O objeto parecia intacto e está quebrado.']:
            with self.subTest(text=text):
                f, = analyze([Block(1, text)], self.nlp, options('coerencia_temporal', 'acentuacao_contextual'),
                             'passado', desativadas=())
                self.assertEqual(f['relation'], 'coordinated_past_present')
                self.assertEqual(f['severity'], 'editorial_attention')
                self.assertEqual(self.scan(text), [])
        # Duas ações do mesmo sujeito em tempos diferentes: desde a sequência temporal, provável
        # erro com confiança alta (antes, atenção editorial como os estados acima).
        f, = self.scan('O assistente abriu a mala e retira o equipamento.')
        self.assertEqual((f['relation'], f['severity'], f['confidence']),
                         ('coordinated_tense_mismatch', 'probable_error', 'alta'))

    def test_resultative_and_explicit_present_preserved(self):
        for text in ['A ponte parecia sólida e agora está interditada.',
                     'Ele estudou e sabe a resposta.',
                     'Ela nasceu em 1990 e mora no Brasil.',
                     'Ele trabalhava ali e hoje está aposentado.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_general_truth_and_legitimate_reported_future(self):
        for text in ['O cientista explicou que a água ferve a cem graus.',
                     'Ela lembrou que a Terra gira em torno do Sol.',
                     'O rapaz disse que voltará amanhã.',
                     'Ela estava certa de que o preço irá subir.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_syntax_disagreement_abstains_without_fabricating_relation(self):
        # O modelo 3.8.0 interpreta “gira” como adjetivo. Omissão conhecida,
        # registrada na documentação; não substituímos a análise por proximidade.
        self.assertFalse(self.scan('O motor vibrava enquanto a peça gira.'))

    def test_hiatum_accent_generalizes_across_verbs(self):
        for text, suggestion in [
            ('As folhas secas caiam sobre o banco.', 'caíam'),
            ('Os estudantes saiam cedo.', 'saíam'),
            ('Os operários construiam casas.', 'construíam'),
            ('As crianças distribuiam brinquedos.', 'distribuíam'),
            ('As lembranças atraiam os visitantes.', 'atraíam'),
            ('A chuva caia lentamente.', 'caía'),
        ]:
            with self.subTest(text=text):
                f, = self.scan(text)
                self.assertEqual(f['rule'], 'acentuacao_contextual')
                self.assertEqual(f['suggestion'], suggestion)
                self.assertEqual(f['severity'], 'probable_error')

    def test_subjunctive_and_imperative_preserved(self):
        for text in ['Espero que as folhas caiam no chão.',
                     'Talvez os estudantes saiam cedo.',
                     'Que os operários construam casas.',
                     'Caiam no chão!', 'Vocês caiam no chão.',
                     'Embora as folhas caiam, a árvore vive.',
                     'Caso as crianças saiam, avise.',
                     'Se os papéis caiam ou não, ele não sabia.']:
            with self.subTest(text=text):
                self.assertFalse([f for f in self.scan(text) if f['rule'] == 'acentuacao_contextual'])

    def test_accent_rule_requires_past_reference(self):
        for tense in ['auto', 'inconclusivo', 'presente']:
            with self.subTest(tense=tense): self.assertFalse(self.scan('Os cabelos caiam sobre o rosto.', tense=tense))

    def test_correct_accents_and_decomposed_unicode_preserved(self):
        for text in ['Os estudantes saíam cedo.', 'A chuva caía lentamente.',
                     'Os cabelos cai\u0301am sobre o rosto.']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_dialogue_and_thoughts_not_forced_into_narrative_tense(self):
        for text in ['— Ela compraria uma casa que terá um jardim.',
                     '“Ela compraria uma casa que terá um jardim.”']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))
        text = 'Ela compraria uma casa que terá um jardim.'
        self.assertFalse(self.scan(text, italic=[(0, len(text))]))

    def test_dialogue_scope_can_be_explicitly_enabled(self):
        settings = options('coerencia_temporal'); settings['tense_scopes'] = ['dialogo']
        f, = self.scan('— Ela compraria uma casa que terá um jardim.', settings)
        self.assertEqual(f['relation'], 'conditional_future')

    def test_no_temporal_link_across_separate_utterances(self):
        text = '— Ela compraria uma casa — disse ele. — Que terá um jardim.'
        settings = options('coerencia_temporal'); settings['tense_scopes'] = ['narracao', 'dialogo']
        self.assertFalse(self.scan(text, settings))

    def test_unicode_ranges_preservation_and_evidence(self):
        blocks = [Block(2, 'Capítulo 1', heading=True),
                  Block(8, '🌿 Cafe\u0301. Ela compraria uma casa que terá um jardim.')]
        before = deepcopy(blocks)
        found, _, meta = run(blocks, lambda: self.nlp, settings=options('coerencia_temporal'), tense='passado')
        f, = found
        text = '\n'.join(b.text for b in blocks)
        self.assertEqual(f['excerpt'], 'terá')
        self.assertEqual(text[f['range']['start']:f['range']['end']], 'terá')
        self.assertEqual(f['module'], 'morphosyntactic')
        related, = f['related']
        self.assertEqual(related['text'][related['start']:related['end']], 'compraria')
        self.assertEqual(blocks, before)

    def test_specific_temporal_alert_replaces_generic_same_verb(self):
        found, _, _ = run([Block(1, 'O assistente abriu a mala e retira o equipamento.')], lambda: self.nlp,
                          settings=options('tempo_verbal', 'coerencia_temporal'), tense='passado')
        matching = [f for f in found if f['excerpt'] == 'retira']
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['rule'], 'coerencia_temporal')
        # Com a relação desativada (Fase 7b), o mesmo verbo fica só com o alerta genérico, uma vez.
        found, _, _ = run([Block(1, 'Parecia estar ligado normalmente e não está desligado.')], lambda: self.nlp,
                          settings=options('tempo_verbal', 'coerencia_temporal'), tense='passado')
        self.assertEqual([(f['excerpt'], f['rule']) for f in found], [('está', 'tempo_verbal')])

    def test_disabled_rules_and_modes_do_not_load_model(self):
        loader = Mock(side_effect=AssertionError('Não carregar o modelo'))
        found, _, _ = run([Block(1, 'Ela compraria uma casa que terá um jardim.')], loader, settings=options())
        self.assertFalse(found); loader.assert_not_called()
        found, _, _ = run([Block(1, 'Ela compraria uma casa que terá um jardim.')], loader,
                          settings=options('coerencia_temporal'), mode='editorial')
        self.assertFalse(found); loader.assert_not_called()

    def test_temporal_stage_counts_and_rule_filter(self):
        found, _, meta = run([Block(1, 'Os operários construiam casas.')], lambda: self.nlp,
                             settings=options('acentuacao_contextual'), tense='passado')
        self.assertEqual(len(found), 1)
        self.assertEqual(meta['stages'][1]['finding_count'], 1)
        self.assertEqual(meta['tempo'], 'passado')
        settings = options('coerencia_temporal'); settings['tense_scopes'] = []
        loader = Mock(side_effect=AssertionError('Escopo vazio'))
        _, _, meta = run([Block(1, 'Texto.')], loader, settings=settings)
        self.assertEqual(meta['stages'][1]['state'], 'skipped')


class DialogueMechanicsTests(unittest.TestCase):
    def scan(self, text):
        return mechanical([Block(1, text)], validate({}))

    def test_terminal_que_in_varied_questions(self):
        for text in ['O que? É sério?', '— Por que?', 'Você trouxe o que?!', '“Pra que?”', 'QUE?!']:
            with self.subTest(text=text):
                f, = self.scan(text)
                self.assertEqual(f['rule'], 'que_tonico_interrogativo')
                self.assertIn(f['suggestion'], ['quê', 'QUÊ'])

    def test_que_not_terminal_and_accented_are_preserved(self):
        for text in ['O que você trouxe?', 'Por que ela saiu?', 'O quê?', 'Por quê?', '“que” é uma palavra.', '“..”']:
            with self.subTest(text=text): self.assertFalse(self.scan(text))

    def test_dialogue_punctuation_and_voice(self):
        f, = self.scan('— Tô aqui.. Cê vem pro jantar, primo?')
        self.assertEqual(f['rule'], 'pontuacao_duplicada')
        self.assertEqual(f['severity'], 'probable_error')
        self.assertIsNone(f['suggestion'])
        self.assertFalse(self.scan('— Tô aqui... Cê vem pro jantar, primo?'))

    def test_new_rules_disabled_in_old_all_off_configurations(self):
        settings = validate({'rules': {r: False for r in LEGACY_RULES}})
        self.assertFalse(mechanical([Block(1, '— O que? Não..')], settings))


if __name__ == '__main__':
    unittest.main()


PRESENTE = ['A feirante arruma as laranjas e conta as moedas.', 'O vento empurra a lona da barraca.',
            'Um menino pede uma fruta e espera calado.', 'A feirante sorri e entrega a sacola.',
            'O caminhão do gelo chega atrasado.', 'O motorista desce e reclama do trânsito.',
            'A fila cresce perto da banca de peixe.', 'Alguém derruba uma caixa de tomates.',
            'O dono da banca xinga baixinho e recolhe tudo.', 'A chuva começa e todos procuram abrigo.']
PASSADO = [frase.replace('arruma', 'arrumou').replace('conta', 'contou').replace('empurra', 'empurrou')
           .replace('pede', 'pediu').replace('espera', 'esperou').replace('sorri', 'sorriu')
           .replace('entrega', 'entregou').replace('chega', 'chegou').replace('desce', 'desceu')
           .replace('reclama', 'reclamou').replace('cresce', 'cresceu').replace('derruba', 'derrubou')
           .replace('xinga', 'xingou').replace('recolhe', 'recolheu').replace('começa', 'começou')
           .replace('procuram', 'procuraram') for frase in PRESENTE]


class TenseChoiceTests(unittest.TestCase):
    """Contagem de verbos da narração que contradiz o tempo escolhido: só aviso, sem mudar alertas."""

    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def meta(self, frases, tense, settings=None, vezes=3):
        blocks = [Block(i + 1, frase) for i, frase in enumerate(frases * vezes)]
        _, warnings, meta = run(blocks, lambda: self.nlp, settings=settings or options('tempo_verbal'),
                                tense=tense, mode='linguistica')
        return meta, [w for w in warnings if 'verbos' in w and 'escolhido' in w]

    def test_present_book_analysed_as_past(self):
        meta, avisos = self.meta(PRESENTE, 'passado')
        contradito = meta['tempo_contradito']
        self.assertEqual((contradito['escolhido'], contradito['predominante']), ('passado', 'presente'))
        self.assertGreaterEqual(contradito['presente'], 20)
        self.assertEqual(contradito['presente'] + contradito['passado'],
                         meta['contagem_verbos'].get('presente', 0) + meta['contagem_verbos'].get('passado', 0))
        aviso, = avisos
        self.assertIn('Presente', aviso)

    def test_past_book_analysed_as_present(self):
        meta, avisos = self.meta(PASSADO, 'presente')
        self.assertEqual(meta['tempo_contradito']['predominante'], 'passado')
        self.assertEqual(len(avisos), 1)

    def test_matching_choice_has_no_warning(self):
        for frases, tense in [(PRESENTE, 'presente'), (PASSADO, 'passado')]:
            with self.subTest(tense=tense):
                meta, avisos = self.meta(frases, tense)
                self.assertNotIn('tempo_contradito', meta)
                self.assertEqual(avisos, [])

    def test_short_text_and_mixed_narration_have_no_warning(self):
        # Poucos verbos não sustentam a conclusão; narração mista não tem tempo predominante claro.
        for frases, vezes in [(PRESENTE[:3], 1), (PRESENTE[:5] + PASSADO[5:], 3)]:
            with self.subTest(frases=frases[0], vezes=vezes):
                meta, avisos = self.meta(frases, 'passado', vezes=vezes)
                self.assertNotIn('tempo_contradito', meta)
                self.assertEqual(avisos, [])

    def test_dialogue_in_scope_or_rule_off_has_no_warning(self):
        # Falas no presente distorcem a contagem; sem a regra de tempo verbal não há contagem.
        com_falas = options('tempo_verbal'); com_falas['tense_scopes'] = ['narracao', 'dialogo']
        for settings in [com_falas, options('estrutura')]:
            with self.subTest(settings=settings['tense_scopes']):
                meta, avisos = self.meta(PRESENTE, 'passado', settings=settings)
                self.assertNotIn('tempo_contradito', meta)
                self.assertEqual(avisos, [])
