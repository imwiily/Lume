"""Corpus A: situações neutras, contraprovas e substituições de entidades."""
import unittest
import json
from pathlib import Path
import spacy
from fonte.pipeline import run
from fonte.reader import Block
from fonte.semantic import key
from fonte.settings import DEFAULT
from copy import deepcopy


CORPUS = json.loads((Path(__file__).parent / 'corpus' / 'generic.json').read_text())


class GenericFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, *texts, settings=None):
        return run([Block(i+1, t) for i,t in enumerate(texts)], lambda:self.nlp, mode='editorial', settings=settings)

    def check(self, texts, category=None, severity='possible_inconsistency'):
        findings, _, meta = self.scan(*texts)
        findings = [f for f in findings if f.get('rule') == 'coerencia_generica']
        if category:
            self.assertIn(category, [f.get('category_code') for f in findings], meta['fact_bank']['facts'])
            self.assertEqual(next(f['severity'] for f in findings if f['category_code'] == category), severity)
        else:
            self.assertEqual(findings, [])
        for f in findings:
            self.assertNotEqual(f['severity'], 'confirmed_error')
            self.assertGreaterEqual(len(f['evidence']), 2)
        return meta

    def test_required_positive_corpus(self):
        cases = [(c['id'], c['text'], c['category']) for c in CORPUS if c['category']]
        for ident, texts, code in cases:
            with self.subTest(case=ident):
                self.check(texts, code, 'author_query' if code == 'scene_presence' else 'possible_inconsistency')

    def test_required_negative_corpus(self):
        cases = [(c['id'], c['text']) for c in CORPUS if not c['category']]
        for ident, texts in cases:
            with self.subTest(case=ident): self.check(texts)

    def test_generic_substitutions(self):
        for person in ['Maria', 'Roberto', 'Beatriz']:
            with self.subTest(person=person):
                self.check([f'{person} tinha 32 anos.', f'Dias depois, {person} completou 29 anos.'], 'age_conflict')
        for obj in ['chave', 'carta', 'envelope', 'celular']:
            article = 'a' if obj in {'chave', 'carta'} else 'o'
            with self.subTest(object=obj):
                self.check([f'Ana deixou {article} {obj} na mesa.', f'Ana tirou {article} {obj} do bolso.'], 'object_continuity')

    def test_secondary_positive_corpus(self):
        cases = [
            (['Lucas entregou o envelope a Marina.', 'Depois, Lucas abriu o envelope sem que Marina o devolvesse.'], 'possession_conflict', 'possible_inconsistency'),
            (['Henrique morreu naquela noite.', 'Na manhã seguinte, Henrique entrou no restaurante.'], 'life_state_conflict', 'possible_inconsistency'),
            (['Lívia tinha os cabelos curtos.', 'Poucas horas depois, seus longos cabelos caíam pelas costas.'], 'physical_attribute_conflict', 'possible_inconsistency'),
            (['Eduardo trabalhava como professor desde a faculdade.', 'Eduardo nunca havia trabalhado com ensino.'], 'background_conflict', 'possible_inconsistency'),
            (['Marina nunca havia conhecido Ricardo.', 'Marina se lembrou da viagem que fizera com Ricardo cinco anos antes.'], 'negative_fact_conflict', 'possible_inconsistency'),
            (['Pedro chegou depois de Ana.', 'Ana encontrou Pedro esperando por ela quando chegou.'], 'event_order_conflict', 'possible_inconsistency'),
            (['A porta estava fechada.', 'A porta estava aberta.'], 'state_transition', 'editorial_attention'),
            (['A viagem levaria três horas.', 'Saíram às oito e chegaram às nove.'], 'duration_conflict', 'editorial_attention'),
            (['A perna direita de André estava engessada e ele não conseguia apoiá-la.', 'Pouco depois, André correu escada acima.'], 'character_state_conflict', 'possible_inconsistency'),
            (['Às oito horas, Marcos estava no hospital.', 'Às oito e cinco, Marcos abriu uma reunião no escritório, cinquenta quilômetros distante.'], 'location_conflict', 'possible_inconsistency'),
            (['Miguel trancou a porta por dentro.', 'Sem tocar na fechadura, Clara entrou.'], 'locked_access', 'author_query'),
            (['O médico apresentou-se como Eduardo.', '— Meu nome é Ricardo — disse o mesmo homem.'], 'identity_conflict', 'author_query'),
        ]
        for texts, code, severity in cases:
            with self.subTest(code=code): self.check(texts, code, severity)

    def test_controls(self):
        cases = [
            ['João tinha 32 anos.', 'Maria tinha 29 anos.'],
            ['A carta foi destruída no fogo.', 'Ana leu outra carta.'],
            ['A carta foi destruída no fogo.', 'Ana restaurou a carta.', 'Ana leu a carta.'],
            ['Ana deixou a chave na mesa.', 'Ana pegou a chave.', 'Ana tirou a chave do bolso.'],
            ['Lucas entregou o envelope a Marina.', 'Marina devolveu o envelope a Lucas.', 'Lucas abriu o envelope.'],
            ['Helena entrou sozinha na sala.', 'Pedro entrou na sala.', 'Pedro respondeu de dentro da sala.'],
            ['Helena entrou sozinha na sala.', '***', 'Pedro respondeu de dentro da sala.'],
            ['Hoje é sexta-feira.', 'No dia seguinte, sábado, Ana voltou.'],
            ['João tinha 32 anos.', 'Talvez João tivesse 29 anos.'],
            ['João tinha 32 anos.', '— João tinha 29 anos — disse Maria.'],
            ['Ana não destruiu a carta.', 'Ana leu a carta.'],
            ['Paulo nunca mencionava irmãos.', 'Sua irmã Marta chegou.'],
            ['Henrique morreu naquela noite.', 'Ana sonhou que Henrique entrou.'],
            ['Às oito, Marcos estava no hospital.', 'Às nove, Marcos chegou ao escritório.'],
            ['Miguel trancou a porta.', 'Clara destrancou a porta.', 'Clara entrou.'],
        ]
        for texts in cases:
            with self.subTest(texts=texts): self.check(texts)

    def test_distinct_phones(self):
        meta = self.check(['Ela guardou o celular do trabalho na bolsa.', 'O celular pessoal continuava sobre a mesa.'])
        phones = [o for o in meta['fact_bank']['objects'].values() if o['name'].startswith('celular')]
        self.assertEqual(len(phones), 2)

    def test_negative_knowledge_and_meet(self):
        meta=self.check(['João nunca conheceu Maria.', 'Carlos não soube do acidente na terça-feira.'])
        facts = meta['fact_bank']['facts']
        for relation in ['met', 'knows']:
            matches=[f for f in facts if f['relation']==relation]
            self.assertTrue(matches)
            self.assertTrue(all(f['polarity']=='negative' for f in matches))

    def test_disable(self):
        settings=deepcopy(DEFAULT);settings['rules']['coerencia_generica']=False
        findings,_,_=self.scan('João tinha 32 anos.', 'João completou 29 anos.',settings=settings)
        self.assertFalse(any(f.get('rule')=='coerencia_generica' for f in findings))

    def test_fact_contract(self):
        meta=self.check(['Carlos soube do acidente na terça-feira.'])
        fact=next(f for f in meta['fact_bank']['facts'] if f['relation']=='knows')
        self.assertEqual(fact['valid_from']['weekday'],1)
        self.assertIn('valid_until',fact)
        self.assertEqual(fact['fact_type'],'KNOWLEDGE_FACT')
        self.assertIn(fact['id'],meta['fact_bank']['characters'][key('char','Carlos')]['known_facts'])

    def test_temporal_and_scope_controls(self):
        cases = [
            ['João tinha 32 anos.', 'Alguns dias depois, João completou 33 anos.'],
            ['João tinha 32 anos.', 'Se João tinha 29 anos, a conta estava errada.'],
            ['João tinha 32 anos.', 'João não tinha 29 anos.'],
            ['Às oito, Marcos estava no hospital.', 'Marcos chegou ao escritório.'],
            ['Carlos soube do acidente na terça-feira.', 'Na segunda-feira da semana seguinte, Carlos contou a Pedro sobre o acidente.'],
            ['Carlos soube do acidente na segunda-feira.', 'Carlos soube do acidente na terça-feira.', 'Na segunda-feira, Carlos contou a Pedro sobre o acidente.'],
            ['Carlos soube do acidente na terça-feira.', 'Na segunda-feira, Carlos contou a Pedro sobre o incêndio.'],
            ['Carlos não soube do acidente na terça-feira.', 'Na segunda-feira, Carlos contou a Pedro sobre o acidente.'],
            ['Ana deixou a chave na mesa.', 'Beatriz encontrou Ana.', 'Ela tirou a chave do bolso.'],
        ]
        for texts in cases:
            with self.subTest(texts=texts): self.check(texts)

    def test_evidence_and_event_integrity(self):
        texts=['João tinha 32 anos.', 'João completou 29 anos.', 'A porta estava fechada.', 'Ana abriu a porta.', 'A porta estava aberta.']
        _,_,meta=self.scan(*texts)
        joined='\n'.join(texts)
        facts=meta['fact_bank']['facts'];events=meta['fact_bank']['events']
        self.assertEqual(len({f['id'] for f in facts}), len(facts))
        self.assertEqual(len({e['id'] for e in events}), len(events))
        for f in facts:
            proof=f['evidence'];span=proof['range']
            self.assertEqual(joined[span['start']:span['end']], proof['excerpt'])
            self.assertIn(f['event_id'], {e['id'] for e in events})
        self.assertEqual(facts,[f for s in meta['scenes'] for f in s['facts']])
        closed=next(f for f in facts if f['relation']=='door_state' and f['value']=='closed')
        self.assertIsNotNone(closed['valid_until'])

    def test_negation_variants(self):
        for negative in ['não', 'nunca', 'jamais']:
            meta=self.check([f'João {negative} conheceu Maria.'])
            facts=[f for f in meta['fact_bank']['facts'] if f['relation']=='met']
            self.assertTrue(facts)
            self.assertEqual(facts[0]['polarity'],'negative')

    def test_cross_entity_and_relation_variants(self):
        self.check(['Maria era filha única.', 'Seu irmão Roberto chegou naquela tarde.'], 'relationship_conflict')
        self.check(['Carlos só recebeu a notícia da morte de Helena na terça-feira.', 'Na segunda-feira, Carlos contou a Pedro que Helena havia morrido.'], 'premature_knowledge')
        self.check(['Às oito, Beatriz estava na escola.', 'Às oito e cinco, Beatriz abriu uma reunião no hospital, cinquenta quilômetros distante.'], 'location_conflict')

    def test_genre_contexts(self):
        contexts = {
            'romance': 'A festa de casamento começava.',
            'drama': 'A família aguardava uma resposta.',
            'suspense': 'O silêncio aumentava a tensão.',
            'juvenil': 'As aulas terminavam naquele mês.',
            'histórico': 'A cidade preparava a chegada do rei.',
            'fantasia': 'O castelo ficava além da floresta.',
            'ficção científica': 'A estação orbitava o planeta.',
            'policial': 'A investigação continuava naquela tarde.',
        }
        for genre, context in contexts.items():
            with self.subTest(genre=genre):
                self.check([context, 'Ana tinha 32 anos.', 'Ana completou 29 anos.'], 'age_conflict')

    def test_negation_does_not_match_word_prefix(self):
        self.check(['João tinha 32 anos.', 'Uma semana depois, João tinha 29 anos.'], 'age_conflict')
