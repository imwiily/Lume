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


class TemporalStructureTests(unittest.TestCase):
    """Coordenação com locução e com outro sujeito, presente → passado, aspecto, condicionais e limites."""
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    temporal = LocalNarrativeStateTests.temporal
    one = LocalNarrativeStateTests.one

    def findings(self, *paragraphs):
        blocks = [Block(1, CONTEXTO)]
        for i, text in enumerate(paragraphs):
            block = Block(i + 2, text)
            block.heading = text.isupper()
            blocks.append(block)
        found, _, meta = run(blocks, lambda: self.nlp, tense="passado", mode="ambas")
        return [f for f in found if f["paragraph"] >= 2], meta

    def test_coordination_with_progressive_and_other_subject(self):
        # Locução no passado (“estava observando”) como âncora da coordenada no presente.
        f = self.one("vira", "O vigia estava observando o pátio, mas vira o rosto quando ouviu o apito.")
        self.assertEqual((f["relation"], f["confidence"]), ("coordinated_tense_mismatch", "alta"))
        # Adversativa com outro sujeito: mesma cena, confiança média.
        f = self.one("ficam", "Os ruídos ficam mais altos, mas ele ainda não conseguia entender nada.")
        self.assertEqual((f["relation"], f["confidence"], f["temporal_evidence"]["same_subject"]),
                         ("coordinated_tense_mismatch", "média", False))

    def test_present_then_past(self):
        for text, verb in [("Ela ergue a arma. O homem recuou.", "ergue"),
                           ("O trem continua deslizando pelos trilhos. Então bateu na barreira.", "continua")]:
            with self.subTest(text=text):
                f = self.one(verb, text)
                self.assertIn(f["relation"], {"past_present_past", "local_narrative_tense_shift"})

    def test_suggestion_follows_anchor_aspect(self):
        # Perfeito com perfeito (“caiu e se quebrou”), imperfeito com imperfeito; senão, nenhuma.
        self.assertEqual(self.one("quebra", "O vaso caiu e se quebra.")["suggestion"], "quebrou")
        self.assertEqual(self.one("vira", "O vigia estava observando o pátio, mas vira o rosto quando ouviu o apito.")["suggestion"], "virava")
        self.assertIsNone(self.one("corre", "Carlos atravessou a praça. As pessoas observavam em silêncio. "
                                            "Uma criança corre em sua direção.")["suggestion"])

    def test_conditional_mismatch(self):
        for text, verb in [("Se eu parar agora, morreria.", "morreria"),
                           ("Se ela chegasse cedo, conseguirá entrar.", "conseguirá"),
                           ("Se o guia não conseguisse abrir a porta, eu não consigo ajudar.", "consigo")]:
            with self.subTest(text=text):
                f = self.one(verb, text)
                self.assertEqual((f["relation"], f["severity"]), ("conditional_tense_mismatch", "probable_error"))
                self.assertIsNone(f["suggestion"])

    def test_conditional_controls(self):
        for text in ["Se chover amanhã, ficaremos em casa.", "Se eu pudesse escolher, viajaria amanhã.",
                     "Ele disse que, se chovesse, ficaria em casa.", "Se a porta abrir, entramos."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("relation") == "conditional_tense_mismatch"], found)

    def test_agreement_by_syntactic_head(self):
        for text in ["Nenhuma palavra conseguiram sair.", "Cada uma das crianças correram.",
                     "Uma das portas estavam abertas.", "A lista de nomes estavam sobre a mesa."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertTrue([f for f in found if f.get("rule") == "concordancia"])
        for text in ["Uma série de acontecimentos aconteceu naquela noite.", "Um dos que chegaram cedo ajudou.",
                     "As palavras não conseguiram sair.", "Cada criança correu."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("rule") == "concordancia"], found)

    def test_legitimate_presents_not_strong(self):
        for text in ["A água ferve em determinada temperatura.", "Meu irmão tem olhos verdes.",
                     "Ele explicou que a Terra gira ao redor do Sol.", "Por que eu penso nisso?"]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("confidence") == "alta"
                                  or f.get("relation") in SEQUENCIA | {"local_narrative_tense_shift"}], found)

    def test_structural_limits(self):
        # Separador e capítulo: o presente do novo capítulo não herda o passado anterior.
        found, _ = self.findings("Ele saiu de casa.", "***", "CAPÍTULO DOIS", "A chuva cai sobre a cidade.")
        self.assertFalse([f for f in found if f.get("relation") in SEQUENCIA | {"local_narrative_tense_shift"}], found)

    def test_proximal_demonstrative_is_narrator_comment(self):
        # ‘Esse/este’ no sujeito aponta para o agora do narrador: não é ação da cena.
        found, _ = self.findings("A aula começou tarde. Esse diretor me causa arrepios. O inspetor olhou para a turma.")
        self.assertFalse([f for f in found if f.get("confidence") == "alta"], found)
        f = self.one("abre", "A aula começou tarde. O diretor entrou na sala. Aquele homem abre a janela. Depois saiu.")
        self.assertEqual(f["relation"], "past_present_past")

    def test_hyphen_dialogue_stays_out_of_sequence(self):
        # Fala marcada com hífen, mesmo sem essa marcação configurada: não entra na sequência narrativa.
        found, _ = self.findings("O professor fechou o livro.", "- Assim você não precisa copiar nada.", "Ninguém respondeu.")
        self.assertFalse([f for f in found if f.get("relation") in SEQUENCIA | {"local_narrative_tense_shift"}], found)

    def test_agreement_guards(self):
        # Aposto entre vírgulas lido como sujeito e singular marcado como plural pelo modelo: sem alerta.
        for text in ["Se usassem a cabeça, a ferramenta mais simples, poderiam resolver.", "O olhar dela abaixou devagar."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("rule") == "concordancia"], found)

    def test_metadata_lists_active_relations(self):
        _, meta = self.findings("Ele saiu de casa.")
        self.assertTrue({"conditional_tense_mismatch", "coordinated_tense_mismatch", "past_present_past",
                         "same_subject_narrative_shift", "local_narrative_tense_shift"} <= set(meta["temporal_relations"]))


class DetectorDebugTests(unittest.TestCase):
    """Causas reais de falsos negativos e do falso positivo de marcador discursivo."""
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    temporal = LocalNarrativeStateTests.temporal
    one = LocalNarrativeStateTests.one
    findings = TemporalStructureTests.findings

    def relation(self, verb, *paragraphs):
        return self.one(verb, *paragraphs)["relation"]

    def test_required_patterns(self):
        cases = [(("Ela segura a caixa e saiu da sala.",), "segura", {"coordinated_tense_mismatch"}),
                 (("Ele entrou. Sentou. Abre o livro.",), "Abre", SEQUENCIA | {"local_narrative_tense_shift"}),
                 (("Ela levanta a mão. O homem recuou.",), "levanta", SEQUENCIA | {"local_narrative_tense_shift"}),
                 (("O objeto continua girando. Então parou.",), "continua", SEQUENCIA | {"local_narrative_tense_shift"}),
                 (("Ele fechou a porta.", "Caminha até o carro."), "Caminha", SEQUENCIA | {"local_narrative_tense_shift"}),
                 (("O carro bateu. Os passageiros ficaram imóveis. Uma pessoa abre a porta.",), "abre",
                  {"local_narrative_tense_shift"}),
                 (("A máquina continua funcionando. Depois desligou.",), "continua", SEQUENCIA | {"local_narrative_tense_shift"})]
        for paragraphs, verb, relations in cases:
            with self.subTest(paragraphs=paragraphs):
                self.assertIn(self.relation(verb, *paragraphs), relations)

    def test_parse_failure_uses_surface_fallback(self):
        # O modelo lê “segura” como adjetivo de “Mariana”: o fallback superficial dá confiança média.
        f = self.one("segura", "Mariana segura a bolsa e saiu da sala.")
        self.assertEqual((f["relation"], f["confidence"], f["temporal_evidence"].get("surface")),
                         ("coordinated_tense_mismatch", "média", True))

    def test_discourse_markers_are_not_temporal(self):
        for text in ["Ok. Aquilo era estranho.", "Certo. Ele havia entendido.", "Tá. Aquilo era estranho.",
                     "Soldados? Guardas? Não importa. Todos corriam para a saída.",
                     "O cão correu pelo pátio. Deu uma volta. Ficou em volta dele.",
                     "Tá bom. Ele havia entendido.", "Beleza. Tudo bem. Ninguém respondeu."]:
            with self.subTest(text=text):
                self.assertEqual(self.temporal(text), [])

    def test_no_strong_alert_for_legitimate_presents(self):
        for text in ["Ele explicou que o gelo derrete com calor.", "A casa é antiga.", "Por que eu faço isso?",
                     "Se eu parar, vou cair."]:
            with self.subTest(text=text):
                self.assertFalse([f for f in self.temporal(text) if f.get("confidence") in {"alta", "média"}])

    def test_short_dialogue_keeps_the_scene(self):
        # Fala intercalada curta não zera o estado; fragmentos sem verbo não consomem a janela.
        self.assertIn(self.relation("Levanto", "Abri a porta do quarto. Olhei em volta.", "— Tem alguém aí?",
                                    "Levanto a lanterna devagar."), SEQUENCIA | {"local_narrative_tense_shift"})
        self.assertIn(self.relation("Fico", "Olhei para as mãos. Nenhum arranhão. Nenhuma marca. Nada.",
                                    "Fico olhando para elas."), SEQUENCIA | {"local_narrative_tense_shift"})

    def test_subordinate_and_nominal_time_words_do_not_free_the_main_verb(self):
        # “desde que” pertence à subordinada; “de hoje” modifica o nome.
        for text, verb in [("O guia fechou o mapa. Pela segunda vez desde que chegamos, ele tropeça na pedra.", "tropeça"),
                           ("O guia fechou o mapa. Olhou o céu. A nuvem me faz lembrar da prova de hoje.", "faz")]:
            with self.subTest(text=text):
                self.assertTrue([f for f in self.temporal(text) if f["text"][f["start"]:f["end"]] == verb
                                 and f.get("confidence") in {"média", "alta"}])

    def test_evidence_is_never_empty(self):
        for paragraphs in [("Ela levanta a mão. O homem recuou.",), ("Ele entrou. Sentou. Abre o livro.",)]:
            with self.subTest(paragraphs=paragraphs):
                for f in self.temporal(*paragraphs):
                    if f.get("relation") in SEQUENCIA | {"local_narrative_tense_shift"}:
                        ev = f["temporal_evidence"]
                        self.assertTrue(ev["previous_narrative_verbs"] or ev.get("following_narrative_verbs"), ev)
                        self.assertIn(ev["local_state"], {"past", "mixed", "unknown"})
                        self.assertTrue(ev["local_tense_score"])

    def test_conditionals_and_modality(self):
        self.assertEqual(self.relation("cairia", "Se eu parar, cairia."), "conditional_tense_mismatch")
        self.assertEqual(self.relation("sobraria", "Se isso acertar o alvo, não sobraria nada."), "conditional_tense_mismatch")
        for text in ["Se eu parasse, cairia.", "Se eu parar, vou cair.", "Talvez ele chegue amanhã.",
                     "Talvez, se tivesse tempo, ele ajudaria."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("relation") in {"conditional_tense_mismatch", "modal_mood_mismatch"}])
        f = self.one("funcionaria", "Talvez essa estratégia funcionaria.")
        self.assertEqual((f["relation"], f["confidence"], f["suggestion"]), ("modal_mood_mismatch", "média", None))

    def test_fallback_and_modality_controls(self):
        # Verbo antes de ‘para’ não é sujeito; ‘talvez’ não alcança a comparativa (“do que deveria”).
        for text in ["Desci para o porão e acendi a luz.",
                     "Fechei a janela. Talvez com mais força do que deveria."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("relation") in {"coordinated_tense_mismatch", "modal_mood_mismatch"}], found)

    def test_appositive_vocative(self):
        for text, suggestion in [("Pedro meu amigo venha aqui.", "Pedro, meu amigo,"), ("Maria querida espere.", "Maria, querida,")]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertEqual([f["suggestion"] for f in found if f.get("rule") == "vocativo"], [suggestion])
        for text in ["Pedro abriu a porta.", "Maria Clara saiu cedo.", "João Pedro venha aqui.", "Pedro meu amigo chegou cedo."]:
            with self.subTest(text=text):
                found, _ = self.findings(text)
                self.assertFalse([f for f in found if f.get("rule") == "vocativo" and "meu" in (f.get("suggestion") or "")])

    def test_trace_records_discard_reasons(self):
        from fonte import temporal
        from fonte.settings import validate
        trace = []
        temporal.analyze([Block(1, CONTEXTO), Block(2, "Tá. A casa é antiga. Por que eu faço isso?")], self.nlp,
                         validate({}), "passado", trace=trace)
        reasons = {t["discard_reason"] for t in trace}
        self.assertTrue({"função discourse_marker", "função state", "função thought"} <= reasons, reasons)
