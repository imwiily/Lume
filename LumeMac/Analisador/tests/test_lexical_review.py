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
        for text in ['Abaixei os olhos, tentando não chamar atenção.',
                     'Olhei para o relógio da parede.',
                     'Confirmei que sim com um aceno.',
                     'Ouvi passos vindo de fora.',
                     'Bati o punho no balcão, irritado.',
                     'Eu pus o copo em cima do mapa.',
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
        for text in ['Saí da biblioteca pelo portão gigantesco da Biblioteca Central de Vale Alto.',
                     '— A prova começará no ginásio — disse ele enquanto caminhávamos até lá.',
                     'Finalmente, depois daquela prova, todo mundo iria me notar. Passávamos pelo corredor do térreo. Nada.']:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text),[])

    def test_unseen_imperfect_plural(self):
        for text in ['Nós esperávamos o ônibus perto da praça.',
                     'Elas aguardavam a resposta da professora.']:
            self.assertEqual(self.scan(text),[])

    def test_clitic_past(self):
        for text in ['Esforcei-me bastante para alcançar a prateleira.',
                     'Posicionei-me, segurando o remo com firmeza.',
                     'Aproximei-me da porta e respirei fundo.']:
            self.assert_no_category(text,'Tempo verbal')

    def test_ambiguous_present_past_not_guessed(self):
        for text in ['Nós passamos pelo pátio até a cozinha.',
                     'Nós saímos do prédio da prefeitura.',
                     'Nós vendemos as roupas na feira.']:
            self.assert_no_category(text,'Tempo verbal')

    def test_adjectives_and_pronouns_are_not_finite(self):
        for text in ['O vizinho havia passado praticamente a tarde inteira discutindo com o carteiro.',
                     'Eu já estava sentado, lendo no meu quarto, quando escutei um estalo.',
                     '— O quê? — disse Otávio, surpreso.',
                     'Ela estava aqui comigo.']:
            self.assertEqual(self.scan(text),[])

    def test_vão_noun_vs_auxiliary(self):
        self.assert_no_category('Todo o esforço acabou sendo em vão.','Tempo verbal')
        self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan('Ah, não, eles vão acabar comigo.')))

    def test_copulas_are_finite(self):
        for text in ['— Não, pode entrar. — Era aquela vizinha de antes.',
                     'Não era um sorriso normal.',
                     'Essa era minha única esperança.',
                     'Eles são iguais aos da Beatriz.']:
            self.assert_no_category(text,'Estrutura da frase')

    def test_copulas_present_still_alert(self):
        for text in ['Ela está aqui comigo.', 'Será que são os meus protótipos?',
                     'A cidade é tão linda à noite.']:
            self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan(text)),text)

    def test_real_tense_candidates_preserved(self):
        for text in ['Continuei andando. As luzes dos estabelecimentos iluminam as ruas.',
                     'Ela começou a me ajudar. Mas não consigo.',
                     'Olhei para ele. Seus cabelos grisalhos caem sobre a testa.',
                     'O menino abriu a porta e observa a rua.']:
            self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan(text)),text)

    def test_real_fragments_remain_candidates(self):
        for text in ['Um pedaço de papel seu rasgado.',
                     'Uma velha cadeira de madeira no canto da sala.',
                     'O canto dos pássaros na janela.']:
            self.assertTrue(any(f['category']=='Estrutura da frase' for f in self.scan(text)),text)

    def test_general_present_remains_editorial_decision(self):
        self.assertTrue(any(f['category']=='Tempo verbal' for f in self.scan('Certas magias não precisam ser pronunciadas.')))


if __name__ == '__main__':
    unittest.main()
