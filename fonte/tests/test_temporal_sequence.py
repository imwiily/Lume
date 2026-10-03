"""Sequência temporal entre verbos, orações e frases próximas (estado narrativo local).

O alvo é o evento narrativo no presente dentro de uma cadeia de ações no passado; presentes
legítimos (verdade geral, estado, pensamento) não recebem confiança alta.
"""
import unittest

import spacy

from fonte.pipeline import run
from fonte.reader import Block

# Contexto neutro no passado antes do trecho avaliado, como num capítulo narrado no passado.
CONTEXTO = "A manhã começou fria. Ninguém saiu de casa cedo. O vento soprou forte sobre o telhado."
SEQUENCIA = {"past_present_past", "coordinated_tense_mismatch", "same_subject_narrative_shift"}


class SequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def findings(self, text):
        found, _, _ = run([Block(1, CONTEXTO), Block(2, text)], lambda: self.nlp, tense="passado", mode="ambas")
        return [f for f in found if f["paragraph"] == 2]

    def temporal(self, text):
        return [f for f in self.findings(text) if f["category"] in {"Tempo verbal", "Coerência temporal entre orações"}]

    def assert_high(self, text, verb, relations=SEQUENCIA):
        found = [f for f in self.temporal(text) if f["text"][f["start"]:f["end"]] == verb]
        self.assertEqual(len(found), 1, f"{text}: {[(f['category'], f.get('relation')) for f in self.temporal(text)]}")
        f, = found
        self.assertIn(f.get("relation"), relations)
        self.assertEqual((f["confidence"], f["severity"]), ("alta", "probable_error"))
        self.assertTrue(f["related"], "O alerta aponta os verbos no passado que formam a sequência.")

    def test_past_present_past(self):
        for text, verb in [("Pedro abriu o armário. Procura durante alguns segundos. Depois fechou a porta.", "Procura"),
                           ("Lúcia abriu a mala. Procura durante alguns minutos. Depois fechou o zíper.", "Procura"),
                           ("Ele fechou a porta. Caminha até a janela. Depois voltou para a mesa.", "Caminha"),
                           # Narrador em 1ª pessoa: a pessoa não torna o presente um comentário.
                           ("Abri a porta do quarto. Procuro o interruptor na parede. Depois acendi a luz.", "Procuro")]:
            with self.subTest(text=text):
                self.assert_high(text, verb, {"past_present_past"})

    def test_coordinated_mismatch_either_direction(self):
        for text, verb in [("Ela pega a chave e abriu o portão.", "pega"),
                           ("O guarda levanta a espada e atacou.", "levanta"),
                           ("Ela segura a mochila e saiu da sala.", "segura"),
                           ("O pescador puxou a rede e solta o peixe.", "solta"),
                           ("Peguei a caneta e assino o documento.", "assino")]:
            with self.subTest(text=text):
                self.assert_high(text, verb, {"coordinated_tense_mismatch"})

    def test_same_subject_shift(self):
        for text, verb in [("Marcos segurou o pacote. Caminhou até a mesa. Então coloca o objeto sobre ela.", "coloca"),
                           ("Carlos correu pelo corredor. Abriu a porta. Olhou para trás. Então atravessa a sala.", "atravessa")]:
            with self.subTest(text=text):
                self.assert_high(text, verb)

    def test_legitimate_presents_are_not_high(self):
        for text in ["O gelo derrete quando a temperatura aumenta.",
                     "Minha irmã tem cabelos castanhos.",
                     "Por que eu faço isso?",
                     "A cidade é pequena, mas muito movimentada.",
                     "Ele explicou que a Terra gira ao redor do Sol.",
                     "Meu pai é professor de história.",
                     "Aquele lugar parece estranho."]:
            with self.subTest(text=text):
                found = self.temporal(text)
                self.assertFalse([f for f in found if f.get("confidence") == "alta"], found)
                self.assertTrue(all(f.get("confidence") == "baixa" for f in found),
                                [(f["text"][f["start"]:f["end"]], f.get("confidence")) for f in found])

    def test_ambiguous_cases_are_medium_or_low(self):
        # Presente isolado, sujeito explícito diferente: possível mudança de plano, sem estrutura forte.
        found = self.temporal("A tarde passou devagar. Ela olha pela janela.")
        self.assertTrue(found)
        self.assertTrue(all(f.get("confidence") in {"média", "baixa"} for f in found))
        # Dêixis ambígua (‘há dez minutos’ no passado): confiança baixa.
        found = self.temporal("Ele olhou para o relógio. Há dez minutos, estava esperando pela ligação.")
        self.assertTrue(all(f.get("confidence") == "baixa" for f in found), found)

    def test_transient_state_and_progressive_keep_medium(self):
        # ‘estar’ (estado passageiro, progressivo) e ‘parecer’ + infinitivo narram: não são rebaixados.
        for text, verb in [("Ele saiu da sala. A luz está acesa no corredor.", "está"),
                           ("Ela correu até a ponte. O barco está afundando devagar.", "está"),
                           ("Ele fechou os olhos. Um brilho parece envolver as mãos dele.", "parece")]:
            with self.subTest(text=text):
                found = [f for f in self.temporal(text) if f["text"][f["start"]:f["end"]] == verb]
                self.assertTrue(found)
                self.assertTrue(all(f.get("confidence") in {"média", "alta"} for f in found), found)

    def test_dialogue_present_is_ignored(self):
        # Fala marcada por travessão no início do parágrafo (o papel de fala vem das marcações).
        text = "— Eu procuro a chave — disse ele, e depois fechou a janela."
        self.assertFalse([f for f in self.temporal(text) if f["text"][f["start"]:f["end"]] == "procuro"])


class EditResidueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    findings = SequenceTests.findings

    def residues(self, text):
        return [f["text"][f["start"]:f["end"]] for f in self.findings(text) if f["category"] == "Resíduo de edição"]

    def test_two_finite_auxiliaries(self):
        for text, marked in [("Eu tinha havia percebido.", "tinha havia"),
                             ("Nós fomos estávamos seguindo.", "fomos estávamos"),
                             ("A porta tinha estava fechada desde cedo.", "tinha estava")]:
            with self.subTest(text=text):
                self.assertEqual(self.residues(text), [marked])

    def test_legitimate_auxiliary_chains(self):
        for text in ["Ele tinha sido chamado.", "Ela vai ter que sair.", "Nós estávamos sendo seguidos.",
                     "Ele foi foi chamado.", "Eles tinham ido embora."]:
            with self.subTest(text=text):
                self.assertEqual(self.residues(text), [])


class AttractionAgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    findings = SequenceTests.findings

    def agreement(self, text):
        return [f["text"][f["start"]:f["end"]] for f in self.findings(text) if f.get("rule") == "concordancia"]

    def test_singular_head_with_plural_complement(self):
        for text in ["Nenhuma das respostas estavam correta.", "A lista de objetos estavam sobre a mesa.",
                     "A caixa de ferramentas ficaram no carro."]:
            with self.subTest(text=text):
                self.assertTrue(self.agreement(text))

    def test_agreement_controls(self):
        for text in ["A maioria dos alunos chegaram cedo.", "O grupo de alunos chegaram cedo.",
                     "Um punhado de moedas rolaram pelo chão.",
                     "A lista de objetos estava sobre a mesa.", "As listas de objetos estavam sobre a mesa.",
                     "Nenhuma das respostas estava correta."]:
            with self.subTest(text=text):
                self.assertEqual(self.agreement(text), [])
