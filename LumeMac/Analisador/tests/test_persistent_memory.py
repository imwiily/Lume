"""Robustez semântica: evidência, contraprovas e continuidade entre cenas."""
import unittest
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.semantic import key


class PersistentMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, *texts):
        findings, _, meta = run([Block(i+1,t) for i,t in enumerate(texts)], lambda:self.nlp, mode='editorial')
        return meta['fact_bank'], meta, [f for f in findings if f['module'] == 'global_coherence']

    def test_single_generic_participant_is_local(self):
        for description in ['Um aluno', 'Uma garota', 'Os garotos', 'O professor', 'Um homem']:
            with self.subTest(description=description):
                b,m,_ = self.scan(description + ' entrou na sala.')
                self.assertFalse(b['characters'])
                self.assertTrue(b['local_participants'])
                self.assertTrue(m['scenes'][0]['entered_entities'])
                self.assertFalse(any(f['persistence'] == 'persistent' for f in b['facts']))

    def test_recurring_speaker_is_promoted(self):
        b,_,_=self.scan('O professor entrou.', '“Bom dia”, disse ele.')
        self.assertEqual(len(b['characters']),1)
        self.assertEqual(next(iter(b['characters'].values()))['promotion_basis'], 'recurring_relevant_participant')

    def test_description_can_resume_named_person(self):
        b,m,_=self.scan('João entrou.', 'Ele pegou a chave.', 'O rapaz guardou a chave.')
        self.assertEqual(set(b['characters']), {key('char','João')})
        self.assertEqual(next(e for e in b['events'] if e['action']=='guardar')['subject'], key('char','João'))

    def test_description_with_two_candidates_stays_separate(self):
        b,_,_=self.scan('João encontrou Pedro.', 'O rapaz guardou a chave.')
        e=next(e for e in b['events'] if e['action']=='guardar')
        self.assertNotIn(e['subject'], {key('char','João'),key('char','Pedro')})

    def test_person_patient_and_physical_object_roles(self):
        b,_,_=self.scan('Helena encontrou Pedro.', 'Helena releu a carta.')
        meet=next(e for e in b['events'] if e['action']=='encontrar')
        read=next(e for e in b['events'] if e['action']=='reler')
        self.assertEqual(meet['semantic_roles']['AGENT'],key('char','Helena'))
        self.assertEqual(meet['semantic_roles']['PATIENT'],key('char','Pedro'))
        self.assertIsNone(meet['semantic_roles']['OBJECT'])
        self.assertEqual(read['semantic_roles']['AGENT'],key('char','Helena'))
        self.assertIn(read['semantic_roles']['OBJECT'],b['objects'])
        self.assertFalse(any(f['relation']=='met' and f['subject']==f['value'] for f in b['facts']))

    def test_original_transfer_promotes_all_sides(self):
        b,_,_=self.scan('João entregou a chave a Pedro.')
        e=next(e for e in b['events'] if e['action']=='entregar')
        self.assertEqual(e['semantic_roles']['RECIPIENT'],key('char','Pedro'))
        facts=[f for f in b['facts'] if f['event_id']==e['id']]
        self.assertEqual({(f['subject'],f['relation'],f['polarity']) for f in facts},
                         {(e['object'],'holder','positive'),(key('char','João'),'possesses','negative'),(key('char','Pedro'),'possesses','positive')})
        self.assertIn(e['object'],b['characters'][key('char','Pedro')]['possessions'])
        self.assertEqual(len(b['facts']),len({f['id'] for f in b['facts']}))

    def test_discovery_and_negative_knowledge_persist(self):
        b,_,_=self.scan('João não sabia do acidente.', '***', 'João descobriu o acidente.')
        facts=[f for f in b['facts'] if f['relation']=='knows']
        self.assertEqual([(f['value'],f['polarity']) for f in facts],[('acidente','negative'),('acidente','positive')])
        self.assertTrue(all(f['event_id'].startswith('event_') for f in facts))
        character=b['characters'][key('char','João')]
        self.assertEqual(len(character['knowledge_history']),2)
        self.assertEqual(character['knowledge_state']['acidente']['polarity'],'positive')

    def test_no_knowledge_invented_before_discovery(self):
        b,_,_=self.scan('João descobriu a verdade.')
        self.assertEqual([(f['value'],f['polarity']) for f in b['facts'] if f['relation']=='knows'],[('verdade','positive')])

    def test_hypothetical_discovery_does_not_persist(self):
        for text in ['Talvez João descobriu a verdade.', 'João queria descobrir a verdade.', '“João descobriu a verdade”, disse Maria.']:
            with self.subTest(text=text):
                b,_,_=self.scan(text)
                self.assertFalse(any(f['relation']=='knows' and f['scope']=='asserted' for f in b['facts']))

    def test_healing_patient_not_agent(self):
        b,_,_=self.scan('João curou Pedro.')
        self.assertEqual({f['subject'] for f in b['facts'] if f['relation'] in {'mobility','physical_state'}},{key('char','Pedro')})

    def test_physical_state_crosses_scene(self):
        b,_,findings=self.scan('João machucou a perna.', '***', 'João chutou a bola.')
        self.assertTrue(any(f['relation']=='physical_state' and f['value']=='leg_injured' for f in b['facts']))
        self.assertTrue(any(f.get('category_code')=='character_state_conflict' for f in findings))
        self.assertFalse(any(f['severity']=='confirmed_error' for f in findings))

    def test_explicit_recovery_explains_action(self):
        _,_,findings=self.scan('João machucou a perna.', '***', 'Maria curou João.', 'João chutou a bola.')
        self.assertFalse(any(f.get('category_code')=='character_state_conflict' for f in findings))

    def test_static_physical_states(self):
        for text,value in [('João estava com a perna quebrada.','leg_disabled'),('João estava inconsciente.','unconscious'),('João sangrava.','bleeding')]:
            with self.subTest(text=text):
                b,_,_=self.scan(text)
                self.assertTrue(any(f['relation']=='physical_state' and f['value']==value and f['subject']==key('char','João') for f in b['facts']))

    def test_object_identity_across_scenes_needs_evidence(self):
        for reference,count in [('a carta',2),('a mesma carta',1)]:
            b,_,findings=self.scan('João destruiu a carta.', '***', 'João releu '+reference+'.')
            self.assertEqual(len([o for o in b['objects'].values() if o['name']=='carta']),count)
            self.assertEqual(any(f.get('category_code')=='object_state_conflict' for f in findings),count==1)

    def test_qualified_site_is_stable_across_scenes(self):
        b,_,_=self.scan('A porta da escola estava fechada.', '***', 'João abriu a porta da escola.')
        self.assertEqual(len(b['objects']),1)

    def test_found_is_not_possession(self):
        b,_,_=self.scan('João encontrou a carta.')
        self.assertTrue(any(f['relation']=='found' for f in b['facts']))
        self.assertFalse(any(f['relation']=='possesses' for f in b['facts']))

    def test_time_cardinals_and_simple_offsets(self):
        b,_,_=self.scan('Às oito e dez, João descobriu a verdade.', 'Duas horas depois, João pegou a chave.')
        knowledge=next(f for f in b['facts'] if f['relation']=='knows')
        possession=next(f for f in b['facts'] if f['relation']=='possesses')
        self.assertEqual(knowledge['valid_from']['minute'],490)
        self.assertEqual(possession['valid_from']['minute'],610)
        b,_,_=self.scan('Às vinte e uma horas, João pegou a chave.')
        self.assertEqual(next(f for f in b['facts'] if f['relation']=='possesses')['valid_from']['minute'],1260)

    def test_confidence_and_provenance(self):
        texts=['🌿 João entrou.', 'Ele pegou a chave.', 'João entregou a chave a Pedro.']
        b,_,_=self.scan(*texts)
        events={e['id']:e for e in b['events']}
        for f in b['facts']:
            self.assertIn(f['event_id'],events)
            self.assertLessEqual(f['fact_confidence'],events[f['event_id']]['event_confidence'])
            self.assertLessEqual(f['fact_confidence'],f['confidence_chain']['entity'])
            self.assertEqual('\n'.join(texts)[f['evidence']['range']['start']:f['evidence']['range']['end']],f['evidence']['excerpt'])
            self.assertIn('chapter',f)
            self.assertIn('time',f)

    def test_metrics_count_original_knowledge_as_eligible(self):
        _,m,_=self.scan('João descobriu a verdade.')
        d=m['narrative_diagnostics']
        self.assertEqual(d['eligible_event_count'],1)
        self.assertEqual(d['eligible_fact_conversion_rate'],1)
        self.assertEqual(d['persistent_fact_count'],1)
        self.assertIsNone(d['canonical_character_precision'])

    def test_nested_report_does_not_cancel_negative_knowledge(self):
        b,_,_=self.scan('Eu não sabia daquilo que Maria me disse.')
        self.assertTrue(any(f['relation']=='knows' and f['polarity']=='negative' for f in b['facts']))
        b,_,_=self.scan('João disse que Maria não sabia do acidente.')
        self.assertFalse(any(f['relation']=='knows' and f['scope']=='asserted' for f in b['facts']))

    def test_inference_levels_are_distinct(self):
        for text,level in [('João estava com a perna quebrada.','explicit'),('João mancava e evitava apoiar a perna.','strong_inference'),('João parecia sentir dor.','weak_inference')]:
            b,_,_=self.scan(text)
            self.assertTrue(any(f['relation']=='physical_state' and f['inference_level']==level for f in b['facts']),text)

    def test_reference_focus_survives_repeated_mentions(self):
        b,m,_=self.scan('João entrou.', *['Ele olhou para a sala.']*30, 'Ele pegou a chave.')
        self.assertEqual({r['reference'] for r in m['scenes'][0]['references']},{key('char','João')})
        self.assertTrue(any(f['subject']==key('char','João') and f['relation']=='possesses' for f in b['facts']))
