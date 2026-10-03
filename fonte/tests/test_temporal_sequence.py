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


class LocalNarrativeStateTests(unittest.TestCase):
    """Estado temporal local da cena: presente que quebra uma cadeia no passado, sem exigir passado depois."""
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def temporal(self, *paragraphs):
        blocks = [Block(1, CONTEXTO)] + [Block(i + 2, p) for i, p in enumerate(paragraphs)]
        found, _, _ = run(blocks, lambda: self.nlp, tense="passado", mode="ambas")
        return [f for f in found if f["paragraph"] >= 2
                and f["category"] in {"Tempo verbal", "Coerência temporal entre orações"}]

    def one(self, verb, *paragraphs):
        found = [f for f in self.temporal(*paragraphs) if f["text"][f["start"]:f["end"]] == verb]
        self.assertEqual(len(found), 1, f"{paragraphs}: {[(f['text'][f['start']:f['end']], f.get('relation')) for f in self.temporal(*paragraphs)]}")
        return found[0]

    def test_same_subject_at_end_of_sequence(self):
        # Presente no fim da sequência, sujeito explícito ou elíptico, sem passado depois.
        for text, verb in [("O rapaz entrou na cozinha. Abriu a geladeira. Pega uma garrafa.", "Pega"),
                           ("A mulher correu até a porta. Tentou abrir. Puxa a maçaneta novamente.", "Puxa"),
                           ("Teresa desceu do ônibus. Ela atravessou a rua. Olhou para os lados. Levanta a mão.", "Levanta")]:
            with self.subTest(text=text):
                f = self.one(verb, text)
                self.assertEqual((f["relation"], f["confidence"]), ("same_subject_narrative_shift", "alta"))
                evidence = f["temporal_evidence"]
                self.assertEqual((evidence["local_state"], evidence["same_subject"], evidence["function"]),
                                 ("past", True, "narrative_event"))
                self.assertGreaterEqual(len(evidence["previous_narrative_verbs"]), 2)

    def test_first_person_capitalized_verb_keeps_original_reading(self):
        # A segunda leitura em minúscula só entra quando a original falha: aqui a original acerta e a
        # minúscula perde o verbo; no segundo caso é o contrário.
        for sentence in ["Fico alguns instantes em silêncio.", "Fico alguns minutos parado na porta."]:
            with self.subTest(sentence=sentence):
                f = self.one("Fico", f"Enfim descansei. {sentence} Voltei para casa.")
                self.assertEqual((f["relation"], f["confidence"]), ("past_present_past", "alta"))
                self.assertIn("‘Voltei’", f["reason"])

    def test_scene_shift_with_other_subject(self):
        # O sujeito muda, a cena continua no passado: confiança média, não alta.
        for text, verb in [("O carro derrapou. Bateu na barreira. Fumaça começa a sair do motor.", "começa"),
                           ("O soldado recuou alguns metros. Seus companheiros permaneceram imóveis. Uma flecha atravessa o campo.", "atravessa"),
                           ("O rapaz fechou a janela. A chuva continuou do lado de fora. Pequenas gotas escorrem pelo vidro.", "escorrem"),
                           ("O impacto derrubou os objetos da estante. Alguns livros ainda caem pelo chão.", "caem")]:
            with self.subTest(text=text):
                f = self.one(verb, text)
                self.assertEqual((f["relation"], f["confidence"]), ("local_narrative_tense_shift", "média"))
                self.assertFalse(f["temporal_evidence"]["same_subject"])

    def test_across_paragraph_boundary(self):
        f = self.one("Observa", "Ela colocou os documentos na mesa. Afastou a cadeira.", "Observa os papéis por alguns segundos.")
        self.assertIn(f["relation"], {"same_subject_narrative_shift", "local_narrative_tense_shift"})
        # Um só passado antes, no parágrafo anterior: sujeito elíptico continua a ação; confiança média.
        f = self.one("Observa", "Ela colocou os documentos na mesa.", "Observa os papéis por alguns segundos.")
        self.assertEqual((f["relation"], f["confidence"]), ("same_subject_narrative_shift", "média"))
        # Dois presentes coordenados no novo parágrafo: os dois são quebras (não é mudança deliberada).
        found = {f["text"][f["start"]:f["end"]]: f.get("relation") for f in
                 self.temporal("O inspetor examinou o corredor e voltou para a sala.", "Abre a gaveta da escrivaninha e observa o conteúdo.")}
        self.assertIn(found.get("Abre"), {"same_subject_narrative_shift", "local_narrative_tense_shift"})

    def test_scene_break_resets_state(self):
        # Separador de cena e título interrompem o estado local: sem alerta de sequência.
        for paragraphs in [("O guarda fechou o portão. Apagou a lanterna.", "* * *", "Pega o casaco no armário."),
                           ("O guarda fechou o portão. Apagou a lanterna.", "— Vamos embora — disse alguém.", "— Já vou.",
                            "Pega o casaco no armário.")]:
            with self.subTest(paragraphs=paragraphs):
                found = [f for f in self.temporal(*paragraphs) if f["text"][f["start"]:f["end"]] == "Pega"]
                self.assertFalse([f for f in found if f.get("relation") in SEQUENCIA | {"local_narrative_tense_shift"}], found)

    def test_legitimate_presents_after_past_scene(self):
        for text in ["O guarda fechou o portão. Apagou a lanterna. O ferro conduz eletricidade.",
                     "O guarda fechou o portão. Apagou a lanterna. A Terra gira ao redor do Sol.",
                     "O guarda fechou o portão. Apagou a lanterna. Meu irmão tem vinte anos.",
                     "O guarda fechou o portão. Apagou a lanterna. Por que eu penso assim?",
                     "O guarda fechou o portão. Ele explicou que a empresa funciona durante a semana.",
                     "O guarda fechou o portão. Apagou a lanterna. A casa é antiga, mas continua bem conservada.",
                     "O guarda fechou o portão. Abriu o livro e releu a frase: “A coragem nasce do medo.”",
                     "O guarda fechou o portão. Explicou que crianças aprendem rapidamente novos idiomas.",
                     # Memória do narrador no presente: estado mental, não ação da cena.
                     "A tia costurava aos domingos. Eu quase não lembro o rosto do bisavô."]:
            with self.subTest(text=text):
                found = self.temporal(text)
                self.assertFalse([f for f in found if f.get("confidence") == "alta"
                                  or f.get("relation") == "local_narrative_tense_shift"], found)

    def test_precedence_one_alert_per_verb(self):
        # Coordenação e passado-presente-passado prevalecem; nenhum verbo recebe dois alertas.
        for text, verb, relation in [("Ela pega a chave e abriu o portão. Depois saiu. Desceu a rua.", "pega", "coordinated_tense_mismatch"),
                                     ("Pedro abriu o armário. Entrou no quarto. Procura a chave. Depois fechou a porta.", "Procura", "past_present_past")]:
            with self.subTest(text=text):
                found = [f for f in self.temporal(text) if f["text"][f["start"]:f["end"]] == verb]
                self.assertEqual([f["relation"] for f in found], [relation])
