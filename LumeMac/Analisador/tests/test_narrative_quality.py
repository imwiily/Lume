"""Critérios positivos e contraprovas da memória v0.11."""
import unittest
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.semantic import key


class NarrativeQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, *texts):
        return run([Block(i+1, t) for i,t in enumerate(texts)], lambda:self.nlp, mode='editorial')[2]

    def test_geography(self):
        for text in ['Valena é uma cidade.', 'Os telhados de Valena brilhavam.']:
            m=self.scan(text)
            self.assertIn(key('loc','Valena'),m['fact_bank']['locations'])
            self.assertNotIn(key('char','Valena'),m['fact_bank']['characters'])

    def test_noise_and_destination(self):
        m=self.scan('Íris você precisa vê-los.', 'Tomás caminhou em direção à torre.', 'Três anos atrás chovia.')
        self.assertFalse(any(p['name'] in {'Íris você','vê-los','anos'} for p in m['fact_bank']['characters'].values()))
        self.assertNotIn(key('loc','direção'),m['fact_bank']['locations'])
        self.assertNotIn(key('obj','ano'),m['fact_bank']['objects'])

    def test_simple_reference(self):
        m=self.scan('Íris entrou.', 'Ela olhou para a torre.')
        s=m['scenes'][0]
        self.assertEqual(s['references'][0]['reference'],key('char','Íris'))
        self.assertEqual(s['events'][-1]['subject'],key('char','Íris'))

    def test_ambiguous_and_scene_reset(self):
        for texts in [('Íris encontrou Helena.','Ela entrou.'), ('Íris entrou.','***','Ela entrou.')]:
            m=self.scan(*texts)
            self.assertIsNone(m['scenes'][-1]['references'][-1]['reference'])

    def test_speaker(self):
        m=self.scan('— Por quê? — perguntou Tomás.')
        self.assertEqual(m['scenes'][0]['dialogue_turns'][0]['speaker'],key('char','Tomás'))

    def test_abilities(self):
        for phrase in ['Íris concentrou magia e criou gelo.', 'Íris concentrou sua magia e uma camada de gelo começou a se formar.']:
            m=self.scan('Íris dominava apenas magia de fogo.',phrase)
            facts=m['fact_bank']['facts']
            self.assertTrue(any(f['relation']=='ability' and f['scope']=='exclusive' for f in facts))
            self.assertTrue(any(f['relation']=='demonstrated_ability' and f['value']=='gelo' for f in facts))
            self.assertTrue(any(e['type']=='USE_ABILITY' for e in m['fact_bank']['events']))

    def test_no_hypothetical_ability(self):
        for text in ['Se Íris criou gelo, ninguém viu.','Íris não criou gelo.','— Íris criou gelo.']:
            self.assertFalse(self.scan(text)['fact_bank']['facts'])

    def test_states(self):
        m=self.scan('O pingente estava intacto.','O pingente se partiu.','O pingente estava intacto.')
        facts=m['fact_bank']['facts']
        self.assertEqual([f['value'] for f in facts],['intact','destroyed','intact'])
        self.assertEqual(len({f['subject'] for f in facts}),1)

    def test_negative_fact(self):
        m=self.scan('Íris nunca havia conseguido produzir nenhum outro elemento.')
        f=m['fact_bank']['facts'][0]
        self.assertEqual((f['polarity'],f['value']),('negative','other_elements'))

    def test_metrics_and_offsets(self):
        texts=['🌿 Íris entrou na sala.','Ela criou gelo.']
        m=self.scan(*texts)
        self.assertIsNone(m['narrative_diagnostics']['entity_precision'])
        for f in m['fact_bank']['facts']:
            e=f['evidence'];r=e['range']
            self.assertEqual('\n'.join(texts)[r['start']:r['end']],e['excerpt'])
        self.assertEqual(m,self.scan(*texts) | {'stages':m['stages']})
