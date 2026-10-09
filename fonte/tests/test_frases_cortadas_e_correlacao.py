"""Classes de erro que escapavam às regras locais (casos escritos do zero).

Correlação de tempos com o subjuntivo, frase cortada, parágrafo sem pontuação final, maiúscula
depois de reticências, ‘ao invés de’, ‘embora’ + nome, concordância com sujeito elíptico, vírgula
depois de sujeito com relativa, grafia oscilante de um termo da obra e passado só verbal ligado
como complemento. Cada classe tem casos que não devem alertar.
"""
import unittest
from unittest.mock import patch

import spacy

from fonte import lexicon
from fonte.pipeline import run
from fonte.reader import Block

PRESENTE = "A manhã começa fria. Ninguém sai de casa cedo. O vento sopra forte sobre o telhado."


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def findings(self, *texts, tense="presente"):
        blocks = [Block(1, PRESENTE)] + [Block(i + 2, t) for i, t in enumerate(texts)]
        found, _, _ = run(blocks, lambda: self.nlp, tense=tense, mode="ambas")
        return [f for f in found if f["paragraph"] >= 2]

    def codes(self, *texts, code, tense="presente"):
        return [(f["text"][f["start"]:f["end"]], f.get("suggestion")) for f in self.findings(*texts, tense=tense)
                if f.get("category_code") == code]


class CorrelationTests(Base):
    def test_imperfect_subjunctive_with_present_main_clause(self):
        for text, verb, severity in [
            ("Antes que ela terminasse a pergunta, o vizinho fecha a porta.", "terminasse", "probable_error"),
            ("Antes que Caio terminasse a pergunta, o porteiro fecha o portão.", "terminasse", "probable_error"),
            # Verbo principal que o modelo etiqueta como adjetivo.
            ("Antes que Bia alcançasse a cerca, o cachorro late duas vezes.", "alcançasse", "probable_error"),
            ("Mal se enxerga a estrada, se não fosse pelos faróis.", "fosse", "probable_error"),
            ("Rui continua sorrindo, embora a notícia fosse péssima.", "fosse", "editorial_attention"),
            ("Embora as duas irmãs estivessem ali, o garçom ignora a mesa.", "estivessem", "editorial_attention"),
        ]:
            with self.subTest(text=text):
                found = [f for f in self.findings(text) if f.get("category_code") == "correlacao_tempos"]
                self.assertEqual([f["text"][f["start"]:f["end"]] for f in found], [verb])
                self.assertEqual(found[0]["severity"], severity)
                self.assertIsNone(found[0]["suggestion"])

    def test_conditional_message_names_the_right_correlations(self):
        # Depois de ‘se’ não existe presente do subjuntivo: a mensagem não pode sugeri-lo.
        f, = [f for f in self.findings("Mal se enxerga a estrada, se não fosse pelos faróis.")
              if f.get("category_code") == "correlacao_tempos"]
        self.assertIn("futuro do pretérito", f["reason"])
        self.assertIn("futuro do subjuntivo", f["reason"])
        self.assertNotIn("presente do subjuntivo", f["reason"])
        f, = [f for f in self.findings("Antes que ela terminasse a pergunta, o vizinho fecha a porta.")
              if f.get("category_code") == "correlacao_tempos"]
        self.assertIn("presente do subjuntivo", f["reason"])

    def test_correlated_tenses_do_not_alert(self):
        for text in ["Antes que ela termine a pergunta, o vizinho fecha a porta.",
                     "Antes que ela terminasse a pergunta, o vizinho fechou a porta.",
                     "Embora seja tarde, ela continua no quintal.",
                     "Se chovesse, ficaríamos em casa.",
                     "Mal se enxerga a estrada, se não for pelos faróis.",
                     "Mal se enxergaria a estrada, se não fosse pelos faróis.",
                     "Antes que a vela apagasse…",
                     # ‘Como se’ pede sempre o imperfeito do subjuntivo.
                     "Ela fala tudo com calma, como se estivesse comentando o clima.",
                     "Tom me trata como se eu fosse criança.",
                     # A condicional se liga ao futuro do pretérito vizinho, não à oração de fora.
                     "Ana se vê numa sala que, se soubesse antes, nunca teria aberto.",
                     # Fala no presente seguida de narração no passado: a subordinada é da narração.
                     "— Pode deixar comigo — interrompi, antes que ele pudesse terminar.",
                     # ‘Disse’ termina em -sse, mas é pretérito perfeito do indicativo.
                     "— Eu ajudo, mesmo que a prova seja difícil — disse Lara, sorrindo."]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="correlacao_tempos"), [])


class TruncatedSentenceTests(Base):
    def test_sentence_ending_in_word_that_needs_continuation(self):
        for text, word in [("Ela guarda as moedas no bolso e conta cada.", "cada"),
                           ("O menino corre até a casa da.", "da"),
                           ("Lia procura o envelope embaixo do.", "do")]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="frase_cortada"), [(word, None)])

    def test_complete_sentences(self):
        for text in ["As maçãs custam dois reais cada.", "O carro para.", "Ela conta até três e entra.",
                     "— Eu vou para…", "Ninguém sabe de onde."]:
            with self.subTest(text=text):
                self.assertEqual([c for c in self.codes(text, code="frase_cortada") if c[1] is None], [])

    def test_paragraph_without_final_punctuation(self):
        found = self.codes("A chuva cai sem parar sobre o telhado", "Ela fecha a janela.", code="frase_cortada")
        self.assertEqual(found, [("telhado", "telhado.")])
        for text in ["Capítulo 3", "Revisão de texto", "Pão, leite e café", "Ela pensa:", "— Espera, eu ia dizer que…",
                     "A porta range —"]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="frase_cortada"), [])

    def test_capital_que_after_ellipsis_continues_the_clause(self):
        self.assertEqual(self.codes("— Eu prometi… Que voltaria antes do fim do mês.", code="frase_cortada"),
                         [("Que", "que")])
        for text in ["— Eu prometi… Que bobagem a minha.", "— Ele saiu… Volta amanhã.",
                     "— A chave… Que chave você quer?"]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="frase_cortada"), [])


class LocutionTests(Base):
    def test_ao_inves_de(self):
        self.assertEqual(self.codes("Ao invés de pegar o ônibus, ela vai a pé.", code="locucoes"),
                         [("Ao invés", "Em vez")])
        self.assertEqual(self.codes("Em vez de pegar o ônibus, ela vai a pé.", code="locucoes"), [])

    def test_embora_needs_a_clause(self):
        for text in ["Embora o frio, ela sai sem casaco.", "Embora a chuva, Tito sai sem guarda-chuva."]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="locucoes"), [("Embora", None)])
        for text in ["Embora faça frio, ela sai.", "Embora cansada, ela sai.", "Embora a chuva caia, ela sai.",
                     "Apesar do frio, ela sai."]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="locucoes"), [])


class ElidedSubjectAgreementTests(Base):
    def test_plural_predicative_without_subject(self):
        found = self.codes("Os dois guardas chegam à porta.", "Parece tão nervosos e cansados.", code="concordancia")
        self.assertEqual(found, [("Parece", "Parecem")])
        # Predicativo que o modelo lê como particípio, na mesma linha de outra frase.
        found = self.codes("Os dois irmãos entram na sala. Parece tão cansados e sujos.", code="concordancia")
        self.assertEqual(found, [("Parece", "Parecem")])
        for text in ["Parece tão nervosa e cansada.", "Parecem nervosos.", "Os guardas parecem nervosos.",
                     "Parece estranho o barulho dos carros."]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="concordancia"), [])


class RelativeSubjectCommaTests(Base):
    def test_single_comma_after_restrictive_relative(self):
        for text in ["Com muito cuidado, a moça que cuidou do jardim no verão, rega as flores.",
                     "Sem pressa, o velho que consertou o relógio ontem, guarda as ferramentas."]:
            with self.subTest(text=text):
                self.assertEqual([c for c, _ in self.codes(text, code="virgula_sujeito_verbo")], [","])
        for text in ["Com muito cuidado, a moça, que cuidou do jardim no verão, rega as flores.",
                     "Com muito cuidado, a moça rega as flores.",
                     "Os livros que comprei ontem, guardei na estante.",
                     "A moça que cuidou do jardim, disse ele, mudou de cidade."]:
            with self.subTest(text=text):
                self.assertEqual(self.codes(text, code="virgula_sujeito_verbo"), [])


class CapitalizationTests(Base):
    def test_same_term_with_and_without_capital(self):
        for upper, lower in [("Kelvari", "kelvari"), ("Mulher-Corvo", "mulher-corvo")]:
            with self.subTest(term=upper):
                found = [f for f in self.findings(f"Ninguém viu o {upper} voltar.", f"Dizem que um {lower} ronda a mata.")
                         if f.get("rule") == "variacao_nome"]
                self.assertEqual([f["text"][f["start"]:f["end"]] for f in found], [lower])
                self.assertEqual(f"{found[0]['related'][0]['text'][found[0]['related'][0]['start']:found[0]['related'][0]['end']]}", upper)

    def test_common_words_and_sentence_openers_do_not_alert(self):
        for texts in [("Ela olha o Sol no fim da tarde.", "O sol esquenta o quintal."),
                      ("Kelvari aparece na trilha.", "Dizem que um kelvari ronda a mata.")]:
            with self.subTest(texts=texts):
                self.assertEqual([f for f in self.findings(*texts) if f.get("rule") == "variacao_nome"], [])


class FiniteAfterArticleTests(Base):
    def test_lexicon_only_verb_after_todo_o_is_a_noun(self):
        # Simula a lacuna do léxico: uma palavra listada só como verbo finito, usada como nome.
        word = "xumbaço"
        table = dict(lexicon.data())
        table[word] = lexicon.FINITE | lexicon.PRESENT
        with patch.object(lexicon, "data", return_value=table):
            found = [f for f in self.findings("Ela não parece paciente. Com um estalo de dedos, todo o xumbaço.")
                     if f["category"] == "Estrutura da frase"]
        self.assertEqual(len(found), 1)

    def test_past_only_form_attached_as_complement_still_has_tense(self):
        found = self.codes("No fundo de uma havia um bilhete rasgado.", code="narrative_tense")
        self.assertEqual(found, [("havia", None)])


if __name__ == "__main__":
    unittest.main()


class ExplanationFormatTests(Base):
    """Toda explicação das regras do FONTE: linguagem simples e, numa linha final, o nome gramatical."""

    def test_every_rule_explanation_ends_with_the_grammar_term(self):
        import json
        from pathlib import Path
        texts = []
        for name in ("desenvolvimento", "validacao"):
            corpus = json.loads((Path(__file__).parent / f"corpus/deteccao/{name}.json").read_text(encoding="utf-8"))
            texts.extend(corpus["textos"])
        checked = 0
        for text in texts:
            blocks = [Block(i + 1, p, heading=p.startswith("Capítulo")) for i, p in enumerate(text["paragrafos"])]
            found, _, _ = run(blocks, lambda: self.nlp, tense=text["tempo"], mode="ambas")
            for f in found:
                if f["source"].startswith("LanguageTool") or f.get("rule") in {"auditoria_ia", "coerencia_ia"}:
                    continue
                checked += 1
                with self.subTest(text=text["id"], rule=f.get("rule") or f["category"]):
                    simple, _, term = f["reason"].partition("\n\nNa gramática: ")
                    self.assertTrue(simple and term.endswith("."), f["reason"])
        self.assertGreater(checked, 30)


class LanguageToolSuggestionTests(unittest.TestCase):
    def check(self, text, word, rule, issue, category, replacements):
        import json
        from urllib.parse import unquote_plus
        from fonte import languagetool as lt

        offset = len(text[:text.index(word)].encode("utf-16-le")) // 2
        found = {"offset": offset, "length": len(word.encode("utf-16-le")) // 2, "message": "Possível erro.",
                 "replacements": [{"value": r} for r in replacements],
                 "rule": {"id": rule, "issueType": issue, "category": {"id": category}}}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return json.dumps({"matches": [found]}).encode()

        with patch("fonte.languagetool.build_opener") as builder:
            builder.return_value.open.side_effect = lambda request, timeout: Response()
            return lt.check([Block(1, text)])[0]

    def test_distant_spelling_suggestion_lowers_confidence(self):
        f, = self.check("Ele saca um blaster e aponta.", "blaster", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS", ["plaster"])
        self.assertEqual(f["confidence"], "alta")  # uma letra de distância: digitação provável
        f, = self.check("Ele saca um zapper e aponta.", "zapper", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS", ["papel"])
        self.assertEqual(f["confidence"], "baixa")
        self.assertIn("itálico", f["reason"])
        f, = self.check("Ontme ele saiu.", "Ontme", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS", ["Ontem"])
        self.assertEqual(f["confidence"], "alta")  # letras trocadas de lugar contam como uma
        f, = self.check("Derrepente ele saiu.", "Derrepente", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS", ["De repente"])
        self.assertEqual(f["confidence"], "alta")

    def test_gerund_is_not_the_auxiliary(self):
        self.assertEqual(self.check("Ela nota que os passos do lobo correndo cessam.", "correndo cessam",
                                    "AUXILIARY_VERB_INFINITIVE", "grammar", "GRAMMAR", ["correndo cessar"]), [])
        self.assertEqual(len(self.check("Ele pode corre amanhã.", "pode corre", "AUXILIARY_VERB_INFINITIVE",
                                        "grammar", "GRAMMAR", ["pode correr"])), 1)
