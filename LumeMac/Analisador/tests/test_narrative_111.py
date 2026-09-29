"""Regressão v0.11.1: resultados e contraprovas dos seis requisitos."""
import json
import unittest
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.semantic import key


class Narrative111Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, *texts):
        return run([Block(i+1, t) for i,t in enumerate(texts)], lambda:self.nlp, mode='editorial')

    def meta(self, *texts):
        return self.scan(*texts)[2]

    def test_explicit_speaker_orders(self):
        for text in ['— Não vou — disse Tomás.', '— Não vou — Tomás disse.', 'Tomás disse: — Não vou.', 'Tomás disse: “Não vou.”']:
            with self.subTest(text=text):
                m=self.meta(text);turn=m['scenes'][0]['dialogue_turns'][0]
                self.assertEqual(turn['speaker'],key('char','Tomás'))
                self.assertEqual(turn['speaker_basis'],'explicit')
                self.assertIn(turn['speaker'],m['fact_bank']['characters'])
                self.assertGreater(turn['speaker_confidence'],.9)

    def test_pronominal_speaker(self):
        m=self.meta('Íris entrou.', '— Não vou — disse ela.')
        s=m['scenes'][0]
        self.assertEqual(s['dialogue_turns'][0]['speaker'],key('char','Íris'))
        self.assertEqual(next(e for e in s['events'] if e['type']=='SPEAK')['subject'],key('char','Íris'))

    def test_speaker_ambiguity_and_action(self):
        for line in ['— Não vou — disse ela.', '— Não vou — Helena fechou a porta.']:
            m=self.meta('Íris encontrou Helena.',line)
            self.assertIsNone(m['scenes'][0]['dialogue_turns'][0]['speaker'])

    def test_alternation(self):
        m=self.meta('— Onde? — perguntou Íris.', '— Na torre — respondeu Tomás.', '— Quando?')
        t=m['scenes'][0]['dialogue_turns'][-1]
        self.assertEqual(t['speaker'],key('char','Íris'))
        self.assertEqual(t['speaker_basis'],'alternation')
        self.assertLess(t['speaker_confidence'],.8)

    def test_no_alternation_after_gap_or_third_person(self):
        for middle in ['Helena entrou.', '***']:
            m=self.meta('— Onde? — perguntou Íris.', '— Na torre — respondeu Tomás.',middle,'— Quando?')
            self.assertIsNone(m['scenes'][-1]['dialogue_turns'][-1]['speaker'])

    def test_no_later_speaker_leaks_into_first_turn(self):
        m=self.meta('— Não vou.', '— Por quê? — perguntou Tomás.')
        self.assertIsNone(m['scenes'][0]['dialogue_turns'][0]['speaker'])

    def test_reference_shared_subject_and_fact(self):
        m=self.meta('Íris entrou.', 'Ela concentrou magia e criou gelo.')
        e=next(e for e in m['fact_bank']['events'] if e['type']=='USE_ABILITY')
        f=next(f for f in m['fact_bank']['facts'] if f['relation']=='demonstrated_ability')
        self.assertEqual(e['subject'],key('char','Íris'))
        self.assertEqual(f['subject'],e['subject'])
        self.assertEqual(f['event_id'],e['id'])
        self.assertEqual(e['subject_basis'],'shared_subject')

    def test_subject_continuity(self):
        m=self.meta('Íris entrou.', 'Criou gelo.')
        e=m['fact_bank']['events'][-1]
        self.assertEqual(e['subject'],key('char','Íris'))
        self.assertEqual(e['subject_basis'],'subject_continuity')

    def test_subject_ambiguity(self):
        m=self.meta('Íris encontrou Helena.', 'Ela criou gelo.')
        self.assertIsNone(m['fact_bank']['events'][-1]['subject'])
        self.assertFalse([f for f in m['fact_bank']['facts'] if f['relation'] in {'ability', 'demonstrated_ability'}])

    def test_subject_cut(self):
        m=self.meta('Íris entrou.', '***', 'Criou gelo.')
        self.assertIsNone(m['fact_bank']['events'][-1]['subject'])
        self.assertFalse([f for f in m['fact_bank']['facts'] if f['relation'] in {'ability', 'demonstrated_ability'}])

    def test_future_antecedent(self):
        m=self.meta('Ela criou gelo. Íris entrou.')
        self.assertIsNone(m['fact_bank']['events'][0]['subject'])
        self.assertFalse([f for f in m['fact_bank']['facts'] if f['relation'] in {'ability', 'demonstrated_ability'}])

    def test_use_ability_not_duplicated(self):
        for text in ['Íris criou gelo.', 'Íris concentrou magia e criou gelo.', 'Íris concentrou sua magia e uma camada de gelo começou a se formar.']:
            with self.subTest(text=text):
                m=self.meta(text)
                uses=[e for e in m['fact_bank']['events'] if e['type']=='USE_ABILITY']
                self.assertEqual(len(uses),1)
                self.assertEqual(uses[0]['ability'],'gelo')
                facts=[f for f in m['fact_bank']['facts'] if f['relation']=='demonstrated_ability']
                self.assertEqual(len(facts),1)
                self.assertEqual(facts[0]['event_id'],uses[0]['id'])

    def test_fire_ice_two_facts_same_identity(self):
        for text in ['Ela concentrou magia e criou gelo.', 'Ela concentrou sua magia e uma camada de gelo começou a se formar.']:
            found,_,m=self.scan('Íris dominava apenas magia de fogo.',text)
            facts=m['fact_bank']['facts']
            self.assertEqual(len(facts),2)
            self.assertEqual([(f['relation'],f['value']) for f in facts],[('ability','fogo'),('demonstrated_ability','gelo')])
            self.assertEqual(facts[0]['scope'],'exclusive')
            self.assertEqual(facts[0]['subject'],facts[1]['subject'])
            self.assertEqual([f['category_code'] for f in found if f['module']=='global_coherence'],['ability_conflict'])

    def test_pronominal_exclusive(self):
        m=self.meta('Íris entrou.', 'Ela usava apenas fogo.', 'Ela criou gelo.')
        facts=[f for f in m['fact_bank']['facts'] if f['relation'] in {'ability', 'demonstrated_ability'}]
        self.assertEqual([(f['relation'],f['value']) for f in facts],[('ability','fogo'),('demonstrated_ability','gelo')])

    def test_guard_non_assertions(self):
        for text in ['Íris tentou criar gelo.', 'Íris queria criar gelo.', 'Íris poderia criar gelo.', 'Íris criará gelo.', 'Se Íris criou gelo, ninguém viu.', 'Íris não criou gelo.', 'Íris afirmou que criou gelo.', '— Íris criou gelo.', 'Íris disse: — Criei gelo.']:
            with self.subTest(text=text):
                self.assertFalse(self.meta(text)['fact_bank']['facts'])

    def test_multiple_actors_no_ability_transfer(self):
        m=self.meta('Íris concentrou magia e Helena criou gelo.')
        facts=m['fact_bank']['facts']
        self.assertEqual(len(facts),1)
        self.assertEqual(facts[0]['subject'],key('char','Helena'))

    def test_acquire_lose_location_and_death(self):
        m=self.meta('Íris entrou na torre.', 'Ela pegou uma chave.', 'Ela perdeu a chave.', 'Ela saiu da torre.', 'Ela morreu.')
        facts=[f for f in m['fact_bank']['facts'] if f['relation'] in {'location', 'possesses', 'left_location', 'life_state'} and not f.get('leave')]
        self.assertEqual([f['relation'] for f in facts],['location','possesses','possesses','left_location','life_state'])
        self.assertEqual(facts[1]['value'],facts[2]['value'])
        self.assertEqual(facts[2]['polarity'],'negative')
        self.assertEqual(m['narrative_diagnostics']['fact_conversion_rate'],1)

    def test_no_hypothetical_possession(self):
        for text in ['Íris não pegou uma chave.','Íris queria pegar uma chave.','Íris pegaria uma chave.']:
            self.assertFalse(self.meta(text)['fact_bank']['facts'])

    def test_owner_separation(self):
        found,_,m=self.scan('O dispositivo de Íris foi destruído.', 'O dispositivo de Tomás estava intacto.')
        self.assertEqual(len(m['fact_bank']['objects']),2)
        facts=m['fact_bank']['facts']
        self.assertEqual(len(facts),2)
        self.assertNotEqual(facts[0]['subject'],facts[1]['subject'])
        self.assertFalse([f for f in found if f['module']=='global_coherence'])

    def test_new_object_separation(self):
        m=self.meta('Íris pegou um dispositivo.', 'Tomás pegou outro dispositivo.')
        self.assertEqual(len(m['fact_bank']['objects']),2)
        facts=[f for f in m['fact_bank']['facts'] if f['relation']=='possesses']
        self.assertEqual(len(facts),2)
        self.assertNotEqual(facts[0]['value'],facts[1]['value'])

    def test_two_indefinite_introductions(self):
        m=self.meta('Íris pegou um dispositivo.', 'Tomás pegou um dispositivo.')
        self.assertEqual(len(m['fact_bank']['objects']),2)

    def test_ordinal_and_ambiguous_item(self):
        found,_,m=self.scan('Íris pegou um dispositivo.', 'Tomás pegou outro dispositivo.', 'O primeiro dispositivo quebrou.', 'O segundo dispositivo estava intacto.', 'O dispositivo foi destruído.')
        objects=list(m['fact_bank']['objects'])
        facts=m['fact_bank']['facts']
        destroyed=[f for f in facts if f['relation']=='object_state' and f['value']=='destroyed']
        self.assertEqual(len(destroyed),1)
        self.assertEqual(destroyed[0]['subject'],objects[0])
        intact=[f for f in facts if f['relation']=='object_state' and f['value']=='intact']
        self.assertEqual(len(intact),1)
        self.assertEqual(intact[0]['subject'],objects[1])
        self.assertEqual(m['scenes'][0]['objects'][-1]['identity_status'],'unresolved')
        self.assertFalse([f for f in found if f['module']=='global_coherence'])

    def test_same_item_keeps_state(self):
        found,_,m=self.scan('Íris pegou um pingente.', 'O pingente se partiu.', 'O pingente estava intacto.')
        self.assertEqual(len(m['fact_bank']['objects']),1)
        self.assertTrue(any(f['category_code']=='object_state_conflict' for f in found))

    def test_plural_does_not_create_single_item(self):
        m=self.meta('Íris pegou dois dispositivos.')
        self.assertFalse(m['fact_bank']['objects'])
        self.assertFalse(m['fact_bank']['facts'])

    def test_deterministic_and_evidence(self):
        texts=('🌿 Íris entrou.', 'Ela pegou um dispositivo.', 'Tomás pegou outro dispositivo.', '— Oi — disse Tomás.')
        m=self.meta(*texts);again=self.meta(*texts)
        self.assertEqual(m['fact_bank'],again['fact_bank'])
        joined='\n'.join(texts)
        for f in m['fact_bank']['facts']:
            proof=f['evidence'];r=proof['range']
            self.assertEqual(joined[r['start']:r['end']],proof['excerpt'])
            self.assertIn(f['event_id'],{e['id'] for e in m['fact_bank']['events']})
        json.dumps(m,ensure_ascii=False)

    def test_two_elements_two_events(self):
        m=self.meta('Íris criou gelo e produziu fogo.')
        self.assertEqual({f['value'] for f in m['fact_bank']['facts']},{'gelo','fogo'})
        self.assertEqual(len({f['event_id'] for f in m['fact_bank']['facts']}),2)

    def test_no_incidental_ability(self):
        m=self.meta('Íris concentrou magia enquanto gelo surgiu naturalmente.')
        self.assertFalse(m['fact_bank']['facts'])

    def test_feminine_object_state(self):
        m=self.meta('A espada estava intacta.', 'A espada se partiu.')
        self.assertEqual([f['value'] for f in m['fact_bank']['facts']],['intact','destroyed'])

    def test_clause_roles_do_not_leak(self):
        m=self.meta('Íris entrou e Tomás olhou para a torre.')
        self.assertFalse(any(f['relation']=='location' and f['subject']==key('char','Íris') for f in m['fact_bank']['facts']))
        m=self.meta('Íris criou gelo e Helena usou apenas fogo.')
        ice=next(f for f in m['fact_bank']['facts'] if f['value']=='gelo')
        self.assertEqual(ice['scope'],'asserted')

    def test_future_auxiliary_not_demonstrated(self):
        for text in ['Íris vai criar gelo.','Íris ia criar gelo.']:
            self.assertFalse(self.meta(text)['fact_bank']['facts'])
