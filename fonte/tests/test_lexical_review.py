"""Casos do feedback e contraprovas independentes para a confirmação lexical."""
import unittest
import spacy
from fonte.analysis import analyze
from fonte.reader import Block


class LexicalReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load('pt_core_news_sm', disable=['ner'])

    def scan(self, text):
        return analyze([Block(1,text)],self.nlp,'passado')[0]

    def assert_no_category(self, text, category):
        self.assertFalse([f for f in self.scan(text) if f['category']==category], text)

    def test_feedback_first_person_complete(self):
        for text in ['Encolhi os ombros, evitando qualquer comentário.',
                     'Conferi o calendário da cozinha.',
                     'Respondi que não com um gesto.',
                     'Ouvi passos vindo de fora.',
                     'Bati o punho no balcão, irritado.',
                     'Eu pus a chaleira no fogão.',
                     'Abri a janela lentamente.']:
            with self.subTest(text=text):
                self.assert_no_category(text,'Estrutura da frase')

    def test_unseen_first_person_complete(self):
        for text in ['Fechei a gaveta antes de sair.',
                     'Escrevi uma carta para meu irmão.',
                     'Comprei os ingredientes para o jantar.',
                     'Abandonei o barco na margem do rio.']:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text),[])

    def test_feedback_wrong_confirmations(self):
        for text in ['Saí do mercado pela porta estreita da Feira Municipal de Pedra Branca.',
                     '— O ensaio começará no teatro — avisou ela enquanto atravessávamos a praça.',
                     'Enfim, depois da apresentação, a vizinhança inteira iria me cumprimentar. Cruzávamos a rua do mercado. Nada.']:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text),[])

    def test_unseen_imperfect_plural(self):
        for text in ['Nós esperávamos o ônibus perto da praça.',
                     'Elas aguardavam a resposta da professora.']:
            self.assertEqual(self.scan(text),[])

    def test_clitic_past(self):
        for text in ['Esforcei-me bastante para alcançar a prateleira.',
                     'Acomodei-me, apoiando a bengala no chão.',
                     'Aproximei-me da porta e respirei fundo.']:
            self.assert_no_category(text,'Tempo verbal')

    def test_ambiguous_present_past_not_guessed(self):
        for text in ['Nós passamos pelo pátio até a cozinha.',
                     'Nós saímos da estação de trem.',
                     'Nós vendemos as roupas na feira.']:
            self.assert_no_category(text,'Tempo verbal')

    def test_adjectives_and_pronouns_are_not_finite(self):
        for text in ['O vizinho havia passado praticamente a tarde inteira discutindo com o carteiro.',
                     'Eu já estava na cozinha, cortando cebolas, quando ouvi a campainha.',
                     '— O quê? — disse Otávio, surpreso.',
                     'Ela estava aqui com a irmã.']:
            self.assertEqual(self.scan(text),[])

    def test_vão_noun_vs_auxiliary(self):
        self.assert_no_category('Toda a pressa foi em vão.','Tempo verbal')
        self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan('Ih, eles vão rir de mim.')))

    def test_copulas_are_finite(self):
        for text in ['— Claro, fique à vontade. — Era o mesmo carteiro de ontem.',
                     'Não era um barulho comum.',
                     'Essa era a última carroça da feira.',
                     'Os botões são iguais aos do casaco.']:
            self.assert_no_category(text,'Estrutura da frase')

    def test_copulas_present_still_alert(self):
        for text in ['Ela está aqui com a irmã.', 'Será que são as minhas luvas?',
                     'O porto é tão bonito no inverno.']:
            self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan(text)),text)

    def test_real_tense_candidates_preserved(self):
        for text in ['Continuei remando. As gaivotas sobrevoam o barco.',
                     'Ele tentou me acalmar. Mas não consigo.',
                     'Olhei para ele. Seus cabelos grisalhos caem sobre a testa.',
                     'O menino abriu a porta e observa a rua.']:
            self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan(text)),text)

    def test_real_fragments_remain_candidates(self):
        for text in ['Um pedaço de papel seu rasgado.',
                     'Uma velha cadeira de madeira no canto da sala.',
                     'O canto dos pássaros na janela.']:
            self.assertTrue(any(f['category']=='Estrutura da frase' for f in self.scan(text)),text)

    def test_general_present_remains_editorial_decision(self):
        self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan('Certas receitas não precisam ser medidas.')))


if __name__ == '__main__':
    unittest.main()
