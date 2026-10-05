"""Regras gramaticais com apoio sintático: positivos, controles e ambiguidades.

As frases são genéricas; trocar nomes e objetos não deve mudar o resultado.
"""
import unittest

import spacy

from fonte.grammar import analyze
from fonte.reader import Block
from fonte.settings import validate

NLP = spacy.load("pt_core_news_sm", disable=["ner"])


def run(*paragraphs, rules=None):
    settings = validate({})
    if rules is not None:
        settings["rules"] = {name: name in rules for name in settings["rules"]}
    blocks = [Block(i + 1, text) for i, text in enumerate(paragraphs)]
    return analyze(blocks, NLP, settings)


def excerpts(results, rule=None):
    return [f["text"][f["start"]:f["end"]] for f in results if rule is None or f["rule"] == rule]


class CraseTests(unittest.TestCase):
    def test_missing_crase_after_direct_object(self):
        for sentence, expected in [("Ela mostrou a carta a vizinha.", "a vizinha"),
                                   ("O rapaz devolveu o livro a professora.", "a professora"),
                                   ("Contamos tudo a diretora.", "a diretora")]:
            with self.subTest(sentence=sentence):
                found = run(sentence)
                self.assertIn(expected, excerpts(found, "crase"))
                self.assertTrue(next(f for f in found if f["rule"] == "crase")["suggestion"].startswith("à"))

    def test_nominalized_adjective_as_direct_object(self):
        self.assertIn("a vizinha", excerpts(run("Ele serviu dois pratos e entregou o maior a vizinha."), "crase"))

    def test_no_crase_before_names_pronouns_masculine_or_without_object(self):
        for sentence in ["Ela mostrou a carta a Joana.", "Ela contou a história a eles.",
                         "Ele entregou a chave ao vizinho.", "Ela mostrou a carta.",
                         "Ele entregou a chave e a carta.", "Ela mostrou a carta às vizinhas."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "crase"), [])

    def test_fixed_locutions_and_hours(self):
        self.assertIn("as pressas", excerpts(run("Saíram as pressas do prédio.")))
        self.assertIn("as", excerpts(run("O ônibus partiu as sete horas da manhã.")))
        self.assertIn("a", excerpts(run("A reunião começou a uma hora da tarde.")))
        self.assertIn("As vezes", excerpts(run("As vezes, ele esquecia o caminho.")))
        # Artigo legítimo: quantificador antes, ou duração.
        self.assertEqual(excerpts(run("Todas as vezes que chovia, a rua alagava.")), [])
        self.assertEqual(excerpts(run("Passou as duas horas lendo.")), [])
        self.assertEqual(excerpts(run("Durante as seis horas da manhã, ninguém apareceu.")), [])

    def test_crase_before_infinitive_or_masculine(self):
        self.assertIn("à correr", excerpts(run("Começou à correr pela praia.")))
        self.assertIn("à pé", excerpts(run("Voltaram à pé para a fazenda.")))
        self.assertEqual(excerpts(run("Voltaram à fazenda a pé.")), [])

    def test_prepositional_locution_before_feminine_noun(self):
        self.assertIn("a cidade", excerpts(run("O comboio seguia em direção a cidade.")))
        self.assertEqual(excerpts(run("O comboio seguia em direção a Lisboa.")), [])
        self.assertEqual(excerpts(run("Ficaram frente a frente.")), [])
        self.assertEqual(excerpts(run("Devido a falhas técnicas, o voo atrasou.")), [])


class HomophoneTests(unittest.TestCase):
    def test_por_que_in_direct_question(self):
        self.assertIn("Porque", excerpts(run("— Porque ninguém respondeu? — perguntou o guarda.")))
        self.assertIn("Porque", excerpts(run("Porque a janela estava aberta?")))
        self.assertEqual(excerpts(run("— Porque ninguém respondeu — disse o guarda.")), [])
        self.assertEqual(excerpts(run("Ficou em casa porque chovia.")), [])
        # Depois de vocativo, ainda é pergunta direta; depois de oração, é causa.
        self.assertIn("porque", excerpts(run("— Mãe, porque ninguém avisou? — perguntou ele.")))
        self.assertIn("porque", excerpts(run("— Senhor, e porque o trem parou? — perguntou ela.")))
        self.assertEqual(excerpts(run("— Você saiu cedo porque estava cansado? — perguntou ela."), "homofonos"), [])
        self.assertEqual(excerpts(run("— Não diga isso! É porque você acordou agora, viu? — disse ela."), "homofonos"), [])

    def test_ha_for_elapsed_time(self):
        self.assertIn("a pouco tempo", excerpts(run("O ônibus passou a pouco tempo.")))
        self.assertIn("a dez anos", excerpts(run("A fábrica fechou a dez anos.")))
        self.assertIn("a mais de uma semana", excerpts(run("A loja estava fechada a mais de uma semana.")))
        self.assertIn("a cerca de dois meses", excerpts(run("Ele partiu a cerca de dois meses.")))
        self.assertEqual(excerpts(run("A cidade ficava a mais de dois dias de viagem."), "homofonos"), [])
        for sentence in ["Daqui a pouco tempo o ônibus passa.", "A vila ficava a dois dias de viagem.",
                         "Estava a poucos metros da porta.", "Eles se veem de dois a três dias por semana."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "homofonos"), [])

    def test_onde_aonde(self):
        self.assertIn("Aonde", excerpts(run("— Aonde você mora? — perguntou ela.")))
        self.assertEqual(excerpts(run("— Aonde você vai? — perguntou ela.")), [])
        self.assertEqual(excerpts(run("— Onde você mora? — perguntou ela.")), [])

    def test_mal_mau_mas_mais_and_spelled_locutions(self):
        self.assertIn("mau-educado", excerpts(run("Era um sujeito mau-educado.")))
        self.assertIn("mal", excerpts(run("Foi um mal negócio.")))
        self.assertEqual(excerpts(run("Ele é um mau aluno e dormiu mal.")), [])
        self.assertEqual(excerpts(run("Tinha medo de mau-olhado.")), [])
        self.assertIn("mais", excerpts(run("Tentou abrir a porta, mais não conseguiu.")))
        self.assertEqual(excerpts(run("Tentou abrir a porta, mais uma vez.")), [])
        self.assertIn("mais", excerpts(run("Ela correu o quanto pôde, mais a chuva não parava.")))
        self.assertIn("mais", excerpts(run("Ele respondia o mais rápido que podia, mais a fila no balcão só crescia.")))
        for sentence in ["Vieram os três, mais o motorista, para o jantar.",
                         "Comprou pão, mais a manteiga que faltava.",
                         "Chegaram os dois, mais a mãe trazendo um bolo."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "homofonos"), [])
        self.assertIn("de baixo", excerpts(run("Guardou a caixa de baixo da mesa.")))
        self.assertEqual(excerpts(run("Olhou o prédio de baixo para cima.")), [])
        self.assertIn("em baixo", excerpts(run("Quando chegou lá em baixo, a porta estava aberta.")))
        self.assertIn("em baixo", excerpts(run("Deixou tudo em baixo.")))
        self.assertEqual(excerpts(run("Falou em baixo tom."), "homofonos"), [])


class AgreementTests(unittest.TestCase):
    def test_plural_subject_singular_verb(self):
        for sentence in ["Os vizinhos estava preocupados.", "As janelas ainda estava abertas.",
                         "Os meninos corria pelo pátio."]:
            with self.subTest(sentence=sentence):
                self.assertTrue(excerpts(run(sentence), "concordancia"))

    def test_existential_haver_in_plural(self):
        for sentence in ["Na praça haviam até crianças correndo.", "Houveram muitos problemas na viagem."]:
            with self.subTest(sentence=sentence):
                self.assertTrue(excerpts(run(sentence), "concordancia"))
        # Auxiliar de tempo composto e perífrase com ‘de’ concordam com o sujeito.
        for sentence in ["Eles haviam saído cedo.", "Os meninos haviam de voltar.", "Elas haviam já terminado."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "concordancia"), [])

    def test_each_or_none_with_plural_verb(self):
        self.assertTrue(excerpts(run("Nenhum deles sabiam a resposta."), "concordancia"))

    def test_agreement_controls(self):
        for sentence in ["A maioria dos alunos chegou cedo.", "Os vizinhos estavam preocupados.",
                         "Chegaram os convidados.", "Na mesa estava um copo e um prato.",
                         "Os livros, os cadernos e as canetas estavam na mochila.",
                         "Havia muitas pessoas na praça.", "Os olhos cinza brilhavam.",
                         "As provas é o que importa."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "concordancia"), [])

    def test_nominal_agreement(self):
        self.assertTrue(excerpts(run("Trazia duas sacolas cheia de frutas."), "concordancia"))
        self.assertTrue(excerpts(run("As portas estavam fechada."), "concordancia"))
        self.assertEqual(excerpts(run("Trazia duas sacolas cheias de frutas."), "concordancia"), [])

    def test_object_of_previous_verb_is_not_taken_as_subject(self):
        # Sem vírgula entre as ações, o modelo pode ler o objeto como sujeito.
        for sentence in ["Ele largou a mala correu para fora.", "Ela abriu as janelas saiu correndo."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "concordancia"), [])

    def test_adjective_after_prepositional_phrase_may_refer_to_subject(self):
        for sentence in ["O menino estava atrás de uma estante com caixas ofegante.",
                         "Ana esperava entre as malas cansada."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "concordancia"), [])

    def test_proper_name_misread_as_plural_is_not_flagged(self):
        # O modelo pode marcar um nome próprio como substantivo plural; plural
        # em português termina em -s.
        for sentence in ["Laura acendeu o lampião e começou a ler.", "Marina sentou-se no chão.",
                         "Otávio chegou cedo. Laura já estava esperando."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "concordancia"), [])

    def test_inverted_predicative_keeps_a_valid_span(self):
        # Predicativo antes do sujeito: o trecho vai do primeiro ao último termo, nunca com o início
        # depois do fim (o contrato recusa o relatório inteiro). Árvore montada à mão: o modelo
        # pequeno só produz essa leitura em frases longas.
        from spacy.tokens import Doc
        from fonte.grammar import agreement
        text = "Estavam apagada luzes."
        doc = Doc(NLP.vocab, words=["Estavam", "apagada", "luzes", "."], spaces=[True, True, False, False],
                  pos=["AUX", "ADJ", "NOUN", "PUNCT"], deps=["cop", "ROOT", "nsubj", "punct"], heads=[1, 1, 1, 1],
                  morphs=["Number=Plur|Person=3|VerbForm=Fin", "Gender=Fem|Number=Sing", "Gender=Fem|Number=Plur", ""])
        spans = []
        agreement(Block(1, text), doc, lambda rule, category, start, end, *rest, **kw: spans.append((start, end)))
        self.assertEqual(spans, [(text.index("apagada"), text.index("luzes") + len("luzes"))])

    def test_agreement_is_not_applied_inside_dialogue(self):
        self.assertEqual(excerpts(run("— Os menino chegou cedo — disse ela."), "concordancia"), [])


class RegencyAndCommaTests(unittest.TestCase):
    def test_regency_is_attention_not_error(self):
        found = [f for f in run("O navio chegou no porto ao meio-dia.") if f["rule"] == "regencia"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "editorial_attention")
        self.assertEqual(excerpts(run("O navio chegou na hora certa."), "regencia"), [])
        self.assertTrue(excerpts(run("O chefe pediu para que todos saíssem."), "regencia"))

    def test_chegar_em_is_register_note_without_correction(self):
        # Uso brasileiro corrente: nota de registro, nunca troca automática.
        for sentence in ["Meu tio chegava em casa sempre cansado.", "A carta chegou na secretaria ontem."]:
            with self.subTest(sentence=sentence):
                found, = [f for f in run(sentence) if f["rule"] == "regencia"]
                self.assertEqual(found["severity"], "editorial_attention")
                self.assertEqual(found["priority"], "Explorar")
                self.assertIsNone(found["suggestion"])
                self.assertIn("amplamente usadas", found["reason"])
                self.assertIn("registro normativo mais formal", found["reason"])
                self.assertNotIn("Na norma culta", found["reason"])

    def test_subject_pronoun_as_object(self):
        found = [f for f in run("O vizinho ajudou ela a descer as malas.") if f["rule"] == "regencia"]
        self.assertEqual([f["text"][f["start"]:f["end"]] for f in found], ["ajudou ela"])
        self.assertEqual(found[0]["severity"], "editorial_attention")
        self.assertTrue(excerpts(run("Pedro encontrou eles na praça."), "regencia"))
        for sentence in ["O vizinho disse que ela desceu.", "Ontem ela saiu cedo.", "Ele viu que eles chegaram.",
                         "— Eu vi ela ontem — disse o menino.", "Ajudou ela e o irmão pediram desculpas.",
                         "— Vamos? — perguntou ela, olhando o céu.", "— Tenho — respondeu ela.",
                         "Nesse momento chegou ela.", "Era ela quem estava na porta."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "regencia"), [])

    def test_comma_between_subject_and_verb(self):
        self.assertTrue(excerpts(run("Os moradores mais antigos do bairro, protestaram contra a obra."), "virgula_sujeito_verbo"))
        self.assertTrue(excerpts(run("O único barulho, foi o do vento."), "virgula_sujeito_verbo"))
        # Vocativos e interjeições antes da vírgula não são sujeitos.
        for sentence in ["Os moradores, assustados, protestaram.", "Os moradores protestaram, e a obra parou.",
                         "Ana, que morava ali, protestou.", "Senhor Almeida, está atrasado?",
                         "Perfeito, agora funciona.", "Hum, vai logo.", "Doutora, chegou o resultado."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "virgula_sujeito_verbo"), [])

    def test_disabled_rules_do_not_run(self):
        self.assertEqual(run("Saíram as pressas.", rules=[]), [])


class TenseFalseAlarmTests(unittest.TestCase):
    """Tempo verbal em narração no passado: adjetivo posposto e ‘há’ de abertura."""

    def tense(self, *paragraphs):
        from fonte.pipeline import run as pipeline
        blocks = [Block(i + 1, text) for i, text in enumerate(paragraphs)]
        findings = pipeline(blocks, lambda: NLP, settings=validate({}), tense="passado", mode="linguistica")[0]
        return [f["text"][f["start"]:f["end"]] for f in findings
                if f["category"] in {"Tempo verbal", "Coerência temporal entre orações"}]

    def test_postposed_adjective_is_not_a_present_verb(self):
        for sentence in ["Trabalhou a noite inteira sem parar.", "Passaram a semana inteira na estrada.",
                         "Trabalhei a noite inteira sozinho.", "Estudei a tarde inteira sozinha."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(self.tense(sentence), [])

    def test_capitalized_or_disagreeing_form_after_noun_keeps_verb_reading(self):
        # Parse com substantivo anterior que não é sujeito: só a leitura de
        # adjetivo concordante (minúscula, mesmo gênero e número) é nominal.
        from spacy.tokens import Doc
        from fonte.lexicon import flags, nominal_context

        def nominal(words, gender, index=2):
            morph = f"Gender={gender}|Number=Sing"
            doc = Doc(NLP.vocab, words=words, pos=["DET", "NOUN", "VERB"], heads=[1, 2, 2],
                      deps=["det", "obj", "ROOT"], morphs=[morph, morph, "Mood=Ind|VerbForm=Fin"])
            return nominal_context(doc[index], flags(doc[index].text))
        self.assertTrue(nominal(["a", "noite", "inteira"], "Fem"))
        self.assertFalse(nominal(["o", "grito", "Fala"], "Masc"))
        self.assertFalse(nominal(["o", "grito", "fala"], "Masc"))

    def test_real_present_verbs_are_still_reported(self):
        self.assertIn("fecha", self.tense("A porta fecha sozinha e ninguém percebeu."))
        self.assertIn("corre", self.tense("Ela abriu a porta e corre para a rua."))

    def test_opening_ha_is_idiomatic_but_ha_after_past_is_reported(self):
        self.assertEqual(self.tense("Há muito tempo, numa vila distante, vivia um pastor."), [])
        self.assertEqual(self.tense("Há cem anos, a ponte caiu."), [])
        # Na norma, o tempo decorrido acompanha o passado: ‘havia três anos’.
        self.assertIn("há", self.tense("Ele tinha partido há três anos."))


class DialogueTagTests(unittest.TestCase):
    def test_reading_aloud_is_a_speech_tag(self):
        from fonte.pipeline import run as pipeline
        for text in ["— Aqui diz para esperar — leu a enfermeira. — Depois, é só voltar.",
                     "— Nada será esquecido — recitou o menino."]:
            with self.subTest(text=text):
                findings = pipeline([Block(1, text)], lambda: NLP, settings=validate({}), mode="editorial")[0]
                self.assertFalse(any(f.get("category_code") == "narrative_action_after_speech" for f in findings))


class VocativeTests(unittest.TestCase):
    """Regra linguística (sem modelo); vale também em falas."""

    def vocatives(self, text):
        from fonte.linguistic import analyze as linguistic
        return [(f["text"][f["start"]:f["end"]], f["suggestion"])
                for f in linguistic([Block(1, text)], validate({})) if f["rule"] == "vocativo"]

    def test_answer_or_greeting_followed_by_address(self):
        self.assertEqual(self.vocatives("— Não senhora. Ele saiu."), [("Não senhora", "Não, senhora")])
        self.assertEqual(self.vocatives("— Sim senhor — respondeu."), [("Sim senhor", "Sim, senhor")])
        self.assertEqual(self.vocatives("— Bom dia Lívia! Tudo bem?"), [("Bom dia Lívia", "Bom dia, Lívia")])

    def test_controls(self):
        for text in ["— Não, senhora.", "— Não sei.", "— Obrigado pela ajuda.",
                     "— Aonde vocês vão? — gritou a vizinha.", "— Quem você procura? — disse ele."]:
            with self.subTest(text=text):
                self.assertEqual(self.vocatives(text), [])


if __name__ == "__main__":
    unittest.main()


class RevisaoAutorTests(unittest.TestCase):
    """Alarmes falsos vistos num manuscrito real, reproduzidos com frases neutras."""

    def test_speech_verbs_with_bad_lemmas_are_still_speech_tags(self):
        from fonte.pipeline import run as pipeline
        for text in ["— E aí, tudo certo? — perguntei para ele.", "— Pode ser, senhora — respondemos em coro.",
                     "— Pode deixar — falei, procurando a chave."]:
            with self.subTest(text=text):
                findings = pipeline([Block(1, text)], lambda: NLP, settings=validate({}), mode="editorial")[0]
                self.assertFalse(any(f.get("category_code") == "narrative_action_after_speech" for f in findings))
        findings = pipeline([Block(1, "— Você viu? — as mãos dela tremeram.")], lambda: NLP,
                            settings=validate({}), mode="editorial")[0]
        self.assertTrue(any(f.get("category_code") == "narrative_action_after_speech" for f in findings))

    def test_conjunction_or_verb_before_voce_is_not_a_vocative(self):
        vocativos = VocativeTests().vocatives
        for text in ["— Mas você voltará amanhã.", "— Achei você, finalmente!", "— E você, o que acha?"]:
            with self.subTest(text=text):
                self.assertEqual(vocativos(text), [])

    def test_explanation_with_tag_question_keeps_porque(self):
        self.assertEqual(excerpts(run("— Porque isso serve até para quem já sabe, hein?"), "homofonos"), [])
        self.assertEqual(excerpts(run("— Porque ele saiu cedo, né?"), "homofonos"), [])
        self.assertIn("Porque", excerpts(run("— Porque ele saiu tão cedo?")))

    def test_o_que_quer_que_is_not_a_tense_slip(self):
        self.assertEqual(TenseFalseAlarmTests().tense("Ele correu. O que quer que fosse aquilo, estava perto."), [])


class SegundoRelatorioGrammarTests(unittest.TestCase):
    def test_first_person_verb_after_exclamation_is_not_its_subject(self):
        for sentence in ["Que alegria, achei que o ônibus já tinha partido.",
                         "Que susto, achei que era o vigia."]:
            with self.subTest(sentence=sentence):
                self.assertEqual(excerpts(run(sentence), "virgula_sujeito_verbo"), [])
        self.assertTrue(excerpts(run("O único barulho, foi o do vento."), "virgula_sujeito_verbo"))
