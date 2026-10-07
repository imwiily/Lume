"""Narração no passado com outro plano temporal e marcas que não são narração.

Classes vistas num texto de terceiros, reescritas do zero com outras palavras e nomes:
fala que começa numa linha do meio do parágrafo, o narrador em primeira pessoa que fala de si
no presente (“Sou o caçula”, “sinto que…”, “vou contar…”), listas de nomes e rótulos com
número (“Equipe 2 …”, “Parte 3”) e o nome ‘era’ depois de determinante e adjetivo. Cada classe
tem também casos que continuam alertando.
"""
import unittest

import spacy

from fonte.pipeline import run
from fonte.reader import Block
from fonte.segments import classify
from fonte.settings import validate

PASSADO = "A manhã começou fria. Ninguém saiu de casa cedo. O vento soprou forte sobre o telhado."
TEMPORAIS = {"Tempo verbal", "Coerência temporal entre orações"}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def findings(self, *paragraphs):
        blocks = [Block(1, PASSADO)] + [Block(i + 2, p) for i, p in enumerate(paragraphs)]
        found, _, _ = run(blocks, lambda: self.nlp, tense="passado", mode="ambas")
        return [f for f in found if f["paragraph"] >= 2]

    def marked(self, findings, categories=TEMPORAIS):
        return [f["text"][f["start"]:f["end"]] for f in findings if f["category"] in categories]


class MidParagraphSpeechTests(Base):
    """Fala que abre uma linha do meio do parágrafo (quebra de linha) é fala, não narração."""

    def roles(self, text):
        labels, = classify([Block(1, text)], validate({}))
        return labels

    def test_line_opened_by_dash_is_speech(self):
        for dash in ("—", "-"):
            for nome in ("Marta", "Otávio"):
                text = f"{nome} largou a mochila no chão.\n{dash} Preciso de água agora {dash} pediu, sem fôlego."
                with self.subTest(dash=dash, nome=nome):
                    labels = self.roles(text)
                    self.assertEqual(labels[text.index("Preciso")], "dialogo")
                    self.assertEqual(labels[text.index("pediu")], "narracao")
                    self.assertNotIn("Preciso", self.marked(self.findings(text)))

    def test_open_speech_continues_on_the_line_that_closes_it(self):
        for nome in ("Leandro", "Cecília"):
            text = (f"- Vamos descansar aqui. A trilha é longa.\n\nAlém disso, ninguém sabe o que existe "
                    f"adiante - disse {nome}, sentando-se.")
            with self.subTest(nome=nome):
                labels = self.roles(text)
                self.assertEqual(labels[text.index("existe")], "dialogo")
                self.assertEqual(labels[text.index("disse")], "narracao")
                self.assertEqual(self.marked(self.findings(text)), [])

    def test_speech_without_closing_does_not_swallow_the_next_line(self):
        text = "— Vamos embora.\nA porta abre devagar."
        self.assertEqual(self.roles(text)[text.index("abre")], "narracao")

    def test_narration_line_after_speech_line_is_still_narration(self):
        text = "— Vamos embora — disse ele.\nA porta abre devagar."
        labels = self.roles(text)
        self.assertEqual(labels[text.index("Vamos")], "dialogo")
        self.assertEqual(labels[text.index("abre")], "narracao")
        self.assertIn("abre", self.marked(self.findings(text)))

    def test_compound_word_hyphen_mid_line_is_not_a_dash(self):
        text = "O hóspede chegou.\nO bem-vindo sorriso dela acalma todos."
        labels = self.roles(text)
        self.assertEqual(labels[text.index("acalma")], "narracao")


class NarratorPresentTests(Base):
    """O narrador em primeira pessoa fala de si no presente: outro plano, não desvio da cena."""

    def test_narrator_frame_is_not_a_tense_error(self):
        for text, verbo in [("Eu me chamo Teodoro e vou contar o que aconteceu naquele inverno.", "chamo"),
                            ("Me chamo Lívia, e vou relatar a viagem mais estranha da minha vida.", "vou"),
                            ("Sou o caçula de quatro irmãos.", "Sou"),
                            ("Aquele inverno mudou quem eu sou.", "sou"),
                            ("Sou paulista, e a mudança foi difícil para todos.", "Sou"),
                            ("Por isso, sinto que devo isso a eles.", "sinto"),
                            ("Acho que ninguém acreditaria nessa parte.", "Acho"),
                            ("Confesso que tive medo naquela noite.", "Confesso")]:
            with self.subTest(text=text):
                self.assertNotIn(verbo, self.marked(self.findings(text)))

    def test_actions_of_the_scene_in_first_person_still_alert(self):
        for text, verbo in [("Abro a janela e saí correndo.", "Abro"),
                            ("Sinto o frio da água nas pernas e recuei.", "Sinto"),
                            ("Sou atingido por uma pedra e caí.", "Sou"),
                            ("Acho a chave embaixo do tapete e entrei.", "Acho"),
                            ("Sou empurrado contra a parede e caí.", "Sou"),
                            ("Vou até a porta e bati com força.", "Vou"),
                            ("Quando o barco atracou, sinto que algo estava errado.", "sinto")]:
            with self.subTest(text=text):
                self.assertIn(verbo, self.marked(self.findings(text)))

    def test_third_person_is_unchanged(self):
        self.assertIn("acha", self.marked(self.findings("Ela acha que ninguém viu e saiu.")))


class ListAndLabelTests(Base):
    """Listas de nomes e rótulos numerados não são frases da narração."""

    def test_list_of_names_has_no_tense_or_final_punctuation_alert(self):
        for text in ("Equipe 2 Bruna Caio Davi Elisa", "Turma B Renato Sílvia Tomás", "Bloco 12 Norte Sul"):
            with self.subTest(text=text):
                found = self.findings("A diretora leu a divisão em voz alta.", text)
                self.assertEqual([f["category"] for f in found if f["paragraph"] == 3], [])

    def test_numbered_label_is_not_a_verb(self):
        found = self.findings("Parte 3", "Ela voltou para casa.")
        self.assertEqual(self.marked(found), [])

    def test_sentences_without_final_punctuation_still_alert(self):
        found = self.findings("Ela abriu o armário e pegou o casaco antes de sair")
        self.assertIn("Pontuação final ausente", [f["category"] for f in found])


class NounEraTests(Base):
    """‘Uma nova era começa’: nome, não o verbo ser no imperfeito."""

    PRESENTE = "A manhã começa fria. Ninguém sai de casa cedo. O vento sopra forte sobre o telhado."

    def marked_present(self, text):
        found, _, _ = run([Block(1, self.PRESENTE), Block(2, text)], lambda: self.nlp, tense="presente", mode="ambas")
        return [f["text"][f["start"]:f["end"]] for f in found if f["paragraph"] == 2 and f["category"] in TEMPORAIS]

    def test_era_as_noun_before_a_verb(self):
        for text in ("Uma nova era começa para a cidade.", "Uma longa era termina hoje."):
            with self.subTest(text=text):
                self.assertEqual(self.marked_present(text), [])

    def test_era_as_verb_still_alerts(self):
        for text in ("A velha era bonita e sorri para todos.", "A menina era alta e corre muito."):
            with self.subTest(text=text):
                self.assertIn("era", self.marked_present(text))


if __name__ == "__main__":
    unittest.main()
