"""Qualidade da cadeia: verificar fatos e papéis, não apenas alertas."""
import unittest
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.semantic import key


class FactQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, *texts):
        findings, _, meta = run([Block(i+1,t) for i,t in enumerate(texts)], lambda:self.nlp, mode='editorial')
        return meta['fact_bank'], [f for f in findings if f.get('rule')=='coerencia_generica'], meta

    def facts(self, bank, relation):
        return [f for f in bank['facts'] if f['relation']==relation]

    def test_age_is_not_quantity(self):
        for text in ['Ana tinha 32 cartas.', 'Ana completou 29 tarefas.', 'Ana tem 12 chaves.']:
            with self.subTest(text=text):
                self.assertFalse(self.facts(self.scan(text)[0],'age'))

    def test_attribute_belongs_to_relative_subject(self):
        bank, _, _ = self.scan('Ana encontrou João, que tinha 32 anos.')
        facts=self.facts(bank,'age')
        self.assertTrue(facts)
        self.assertEqual({f['subject'] for f in facts},{key('char','João')})

    def test_profession_copula(self):
        for name,job in [('João','professor'),('Maria','médica')]:
            bank,_,_=self.scan(f'{name} era {job}.')
            self.assertTrue(any(f['subject']==key('char',name) and f['value']==job for f in self.facts(bank,'profession')))

    def test_reported_age_not_world_fact(self):
        bank,_,_=self.scan('Ana disse que João tinha 32 anos.')
        self.assertFalse(self.facts(bank,'age'))

    def test_coordinated_attributes_keep_subjects(self):
        bank,_,_=self.scan('Ana tinha 32 anos e João tinha 29 anos.')
        self.assertEqual({(f['subject'],f['value']) for f in self.facts(bank,'age')}, {(key('char','Ana'),32),(key('char','João'),29)})

    def test_object_is_not_patient_actor(self):
        bank,_,_=self.scan('Marina foi ferida por Lucas.')
        injuries=self.facts(bank,'mobility')
        self.assertTrue(injuries)
        self.assertEqual({f['subject'] for f in injuries},{key('char','Marina')})
        self.assertFalse(any(e['type']=='INJURE' and e.get('subject')==key('char','Marina') for e in bank['events']))

    def test_passive_transfer(self):
        bank,_,_=self.scan('A chave foi entregue a Marina por Lucas.')
        holder=self.facts(bank,'holder')
        self.assertTrue(holder)
        self.assertEqual(holder[-1]['value'],key('char','Marina'))
        event=next(e for e in bank['events'] if e['id']==holder[-1]['event_id'])
        self.assertEqual(event['subject'],key('char','Lucas'))
        self.assertEqual(event['object'],holder[-1]['subject'])

    def test_location_mention_is_not_presence(self):
        bank,_,meta=self.scan('Ana olhou para o hospital.')
        self.assertFalse(self.facts(bank,'location'))
        self.assertNotIn(key('char','Ana'),meta['scenes'][0]['present_entities'])

    def test_ordered_object_transitions(self):
        bank,found,_=self.scan('Ana deixou a chave na mesa.', 'Ana pegou a chave e colocou a chave no bolso.', 'Ana tirou a chave do bolso.')
        locations=self.facts(bank,'object_location')
        # A retirada conserva bolso como origem, mas encerra essa localização.
        self.assertEqual([f['value'] for f in locations],['mesa','carried','bolso','carried'])
        self.assertEqual(locations[-1]['source_location'], 'bolso')
        self.assertEqual(locations[-2]['superseded_by'], locations[-1]['id'])
        self.assertFalse(found)

    def test_different_objects_in_one_sentence(self):
        bank,_,_=self.scan('Ana destruiu a carta e abriu a porta.')
        destroyed=[f for f in self.facts(bank,'object_state') if f['value']=='destroyed']
        self.assertEqual(len(destroyed),1)
        self.assertEqual(bank['objects'][destroyed[0]['subject']]['name'],'carta')
        self.assertFalse(any(f['subject']==destroyed[0]['subject'] for f in self.facts(bank,'door_state')))

    def test_static_object_location_is_compared(self):
        _,found,_=self.scan('A chave estava na mesa.', 'A chave estava no bolso.')
        self.assertIn('object_continuity',{f['category_code'] for f in found})

    def test_knowledge_inherited_topic(self):
        bank,found,_=self.scan('Carlos soube do acidente na terça-feira.', 'Na segunda-feira, contou a Pedro.')
        self.assertTrue(self.facts(bank,'tells'))
        self.assertIn('premature_knowledge',{f['category_code'] for f in found})

    def test_recipient_is_not_knower(self):
        bank,_,_=self.scan('Carlos contou a Pedro sobre o acidente na segunda-feira.')
        self.assertEqual({f['subject'] for f in self.facts(bank,'tells')},{key('char','Carlos')})
        self.assertFalse(any(f['subject']==key('char','Pedro') for f in self.facts(bank,'knows')))

    def test_knowledge_persists_across_relative_scene(self):
        _,found,_=self.scan('Na terça-feira, Carlos soube do acidente.', 'Dias depois, na segunda-feira, Carlos contou a Pedro sobre o acidente.')
        # "Dias depois" impede ordenar a segunda anterior à terça.
        self.assertFalse(any(f['category_code']=='premature_knowledge' for f in found))

    def test_knowledge_with_explicit_hours(self):
        _,found,_=self.scan('Às dez, Carlos soube do acidente.', 'Às nove, Carlos contou a Pedro sobre o acidente.')
        self.assertIn('premature_knowledge',{f['category_code'] for f in found})

    def test_action_without_entry(self):
        _,found,_=self.scan('Helena entrou sozinha na sala.', 'Pedro abriu a janela.')
        query=[f for f in found if f['category_code']=='scene_presence']
        self.assertTrue(query)
        self.assertTrue(all(f['severity']=='author_query' for f in query))

    def test_reappearance_after_exit(self):
        _,found,meta=self.scan('Pedro entrou na sala.', 'Pedro saiu da sala.', 'Pedro respondeu de dentro da sala.')
        self.assertIn('scene_presence',{f['category_code'] for f in found})
        self.assertIn(key('char','Pedro'),meta['scenes'][0]['present_entities'])

    def test_presence_controls(self):
        for texts in [
            ['Helena entrou sozinha na sala.','Pedro entrou na sala.','Pedro abriu a janela.'],
            ['Pedro entrou na sala.','Pedro saiu da sala.','Pedro entrou na sala.','Pedro respondeu de dentro da sala.'],
            ['Helena entrou sozinha na sala.','Helena lembrou de Pedro.'],
        ]:
            with self.subTest(texts=texts):
                self.assertFalse(any(f['category_code']=='scene_presence' for f in self.scan(*texts)[1]))

    def test_relation_requires_unambiguous_owner(self):
        bank,found,_=self.scan('Paulo era filho único.', 'Paulo encontrou Carlos.', 'Sua irmã Marta chegou.')
        self.assertFalse(self.facts(bank,'sibling'))
        self.assertFalse(any(f['category_code']=='relationship_conflict' for f in found))

    def test_family_relation_explicit_owner(self):
        _,found,_=self.scan('Paulo era filho único.', 'Marta era irmã de Paulo.')
        self.assertIn('relationship_conflict',{f['category_code'] for f in found})

    def test_historical_relation_not_overwritten(self):
        _,found,_=self.scan('Marina nunca conheceu Ricardo.', 'Marina conheceu Pedro.', 'Marina viajou com Ricardo.')
        self.assertIn('negative_fact_conflict',{f['category_code'] for f in found})

    def test_injury_belongs_to_patient(self):
        for texts,person in [(['Ana feriu João.'],'João'), (['Ana viu a perna engessada de João.'],'João'), (['João estava ferido.'],'João')]:
            with self.subTest(texts=texts):
                bank,_,_=self.scan(*texts)
                self.assertEqual({f['subject'] for f in self.facts(bank,'mobility')},{key('char',person)})

    def test_negation_scoped_to_clause(self):
        bank,_,_=self.scan('A porta estava fechada e Ana não abriu a porta.')
        states=self.facts(bank,'door_state')
        self.assertEqual([f['value'] for f in states],['closed'])

    def test_end_position_clock_knowledge(self):
        _,found,_=self.scan('Carlos soube do acidente às dez.', 'Carlos contou a Pedro sobre o acidente às nove.')
        self.assertIn('premature_knowledge',{f['category_code'] for f in found})

    def test_unknown_topic_is_not_invented(self):
        for texts in [['Carlos entrou.','Carlos contou a Pedro.'],['Carlos soube do acidente.','Carlos soube do incêndio.','Carlos contou a Pedro.']]:
            with self.subTest(texts=texts):
                self.assertFalse(self.facts(self.scan(*texts)[0],'tells'))

    def test_observation_is_not_state_change(self):
        bank,_,_=self.scan('A chave estava na mesa.', 'A chave estava no bolso.')
        self.assertTrue(all(not f.get('transition') for f in self.facts(bank,'object_location')))

    def test_actor_object_substitutions(self):
        for actor,receiver,obj in [('Ana','Pedro','chave'),('Beatriz','Lucas','carta'),('Maria','João','espada')]:
            bank,_,_=self.scan(f'A {obj} foi entregue a {receiver} por {actor}.')
            holder=self.facts(bank,'holder')[-1]
            event=next(e for e in bank['events'] if e['id']==holder['event_id'])
            self.assertEqual(event['subject'],key('char',actor))
            self.assertEqual(event['to_entity'],key('char',receiver))
            self.assertEqual(bank['objects'][event['object']]['base'] if 'base' in bank['objects'][event['object']] else bank['objects'][event['object']]['name'],obj)

    def test_facts_have_supported_entities(self):
        bank,found,meta=self.scan('Ana entrou sozinha na sala.', 'A chave estava na mesa.', 'Ana pegou a chave e colocou a chave no bolso.', 'Pedro abriu a janela.')
        ids=set(bank['characters'])|set(bank['objects'])|set(bank['locations'])|{s['id'] for s in meta['scenes']}
        self.assertTrue(all(f['subject'] in ids for f in bank['facts']))
        events={e['id']:e for e in bank['events']}
        for fact in bank['facts']:
            self.assertIn(fact['event_id'],events)
            self.assertTrue(0 <= fact['evidence']['start'] < fact['evidence']['end'])
        self.assertTrue(all(f['severity']!='confirmed_error' for f in found))

    def test_relative_profession_not_observer(self):
        bank,_,_=self.scan('Ana encontrou João, que trabalhava como professor.')
        self.assertEqual({f['subject'] for f in self.facts(bank,'profession')},{key('char','João')})

    def test_existing_fact_is_used_for_comparison(self):
        _,found,_=self.scan('A espada se partiu.', 'Ana usou a mesma espada.')
        self.assertIn('object_state_conflict',{f['category_code'] for f in found})

    def test_persistent_state_and_knowledge_references(self):
        bank,_,_=self.scan('Ana deixou a chave na mesa.', 'Ana pegou a chave e colocou a chave no bolso.', 'Carlos soube do acidente na terça-feira.')
        obj=next(e for e in bank['objects'].values() if e['name']=='chave')
        fact=next(f for f in bank['facts'] if f['id']==obj['current_state']['object_location'])
        self.assertEqual(fact['value'],'bolso')
        self.assertEqual(len(obj['state_history']),4)
        knowledge=bank['characters'][key('char','Carlos')]['knowledge_history']
        self.assertEqual(knowledge[0]['topic'],'acidente')
        self.assertEqual(knowledge[0]['valid_from']['weekday'],1)

    def test_same_clock_different_days_is_not_simultaneous(self):
        _,found,_=self.scan('Na segunda-feira, às oito, Ana estava no hospital.', 'Na terça-feira, às oito, Ana estava no escritório.')
        self.assertFalse(any(f['category_code']=='location_conflict' for f in found))

    def test_same_weekday_knowledge_compares_hours(self):
        _,found,_=self.scan('Na terça-feira, às dez, Carlos soube do acidente.', 'Na terça-feira, às nove, Carlos contou a Pedro sobre o acidente.')
        self.assertIn('premature_knowledge',{f['category_code'] for f in found})

    def test_invalid_clock_does_not_crash_or_order_facts(self):
        _,found,_=self.scan('Às 99:70, Carlos soube do acidente.', 'Às nove, Carlos contou a Pedro sobre o acidente.')
        self.assertFalse(any(f['category_code']=='premature_knowledge' for f in found))

    def test_hypothesis_scope_survives_coordination(self):
        for text in ['Talvez Ana pegou a chave e colocou a chave no bolso.', 'Em sonho, Ana pegou a chave e colocou a chave no bolso.', 'Se Ana pegou a chave e colocou a chave no bolso, ninguém viu.']:
            with self.subTest(text=text):
                bank,_,_=self.scan(text)
                self.assertFalse([f for f in bank['facts'] if f['relation'] in {'holder','object_location','possesses'}])

    def test_injury_state_does_not_invent_agent(self):
        bank,_,_=self.scan('João estava ferido.')
        self.assertFalse(any(e['type']=='INJURE' for e in bank['events']))
        self.assertTrue(self.facts(bank,'mobility'))
        bank,_,_=self.scan('Ana feriu João.')
        events=[e for e in bank['events'] if e['type']=='INJURE']
        self.assertTrue(events)
        self.assertTrue(all(e['subject']==key('char','Ana') and e['patient']==key('char','João') for e in events))
