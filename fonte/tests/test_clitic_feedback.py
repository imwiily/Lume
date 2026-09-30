import unittest
import spacy
from spacy.tokens import Doc
from fonte.analysis import analyze
from fonte.lexicon import flags, finite
from fonte.reader import Block


class CliticFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp=spacy.load('pt_core_news_sm',disable=['ner'])

    def test_feedback_cutucava_has_finite_verb(self):
        text='Enquanto Davi observava a cena, os vizinhos o olhavam, sem entender o motivo da pausa repentina; o padeiro o cutucava de leve.'
        self.assertEqual(analyze([Block(86,text)],self.nlp,'passado')[0],[])

    def test_unseen_objects_and_verbs(self):
        for text in ['A professora a observava com atenção.',
                     'O guarda os acompanhava pelo corredor.',
                     'A menina as procurava na gaveta.',
                     'O professor o cutucou de leve.']:
            with self.subTest(text=text):
                self.assertEqual(analyze([Block(1,text)],self.nlp,'passado')[0],[])

    def test_present_with_object_still_flagged(self):
        text='O guarda caminhava pelo corredor quando alguém o intercepta.'
        findings=analyze([Block(1,text)],self.nlp,'passado')[0]
        self.assertTrue(any(f['category']=='Tempo verbal' and text[f['start']:f['end']]=='intercepta' for f in findings))

    def test_mislabelled_article_on_nominal_homograph_not_accepted(self):
        # Simula o engano oposto: "canto" nominal classificado como verbo.
        doc=Doc(self.nlp.vocab,words=['O','canto','dos','pássaros','.'],
                pos=['DET','VERB','ADP','NOUN','PUNCT'],
                heads=[1,1,3,1,1],deps=['det','ROOT','case','nmod','punct'],
                morphs=['','Mood=Ind|Tense=Pres|VerbForm=Fin','','',''])
        self.assertFalse(finite(doc[1]))

    def test_nominal_fragment_remains_exploratory(self):
        text='Do outro lado, um grupo de turistas.'
        findings=analyze([Block(1,text)],self.nlp,'passado')[0]
        self.assertTrue(any(f['category']=='Estrutura da frase' for f in findings))


if __name__=='__main__':
    unittest.main()
