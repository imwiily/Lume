"""Verbo finito, fronteiras de oração e planos temporais (narração no presente).

Classes de falso positivo vistas em relatórios reais, reescritas do zero com outras palavras:
verbo finito que o modelo etiqueta como nome ou complemento, verbos de orações diferentes lidos
como auxiliares do mesmo predicado, passado de anterioridade numa narração no presente, âncora
dentro de relativa, imperfeito modal, aspas de destaque, nomes da obra e subordinada isolada.
Cada classe tem também casos que continuam alertando.
"""
import unittest
from unittest.mock import patch

import spacy

from fonte import languagetool as lt
from fonte.pipeline import run
from fonte.reader import Block

PRESENTE = "A manhã começa fria. Ninguém sai de casa cedo. O vento sopra forte sobre o telhado."
PASSADO = "A manhã começou fria. Ninguém saiu de casa cedo. O vento soprou forte sobre o telhado."
TEMPORAIS = {"Tempo verbal", "Coerência temporal entre orações"}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.load("pt_core_news_sm", disable=["ner"])

    def findings(self, text, tense="presente"):
        context = PRESENTE if tense == "presente" else PASSADO
        found, _, meta = run([Block(1, context), Block(2, text)], lambda: self.nlp, tense=tense, mode="ambas")
        self.meta = meta
        return [f for f in found if f["paragraph"] == 2]

    def marked(self, findings, categories):
        return [(f["category"], f["text"][f["start"]:f["end"]]) for f in findings if f["category"] in categories]


class FiniteVerbValidationTests(Base):
    """“Sem verbo finito” só quando nenhuma fonte reconhece um verbo finito na frase."""

    def structure(self, text, tense="presente"):
        return [f for f in self.findings(text, tense) if f["category"] == "Estrutura da frase"]

    def test_finite_verb_missed_by_the_parser_blocks_the_alert(self):
        for text in [
            # Homógrafo etiquetado como nome depois de sujeito com gerúndio; o verbo da relativa também conta.
            "Uma pequena vespa rondando seu braço causa coceira na pele por onde pousa.",
            # Homógrafo etiquetado como adjetivo logo depois do sujeito.
            "Aquela garra segura com firmeza a menina pelo queixo, girando devagar.",
            "A garra segura o menino.",
            # Forma só finita no léxico, ligada pelo modelo como complemento de preposição.
            "No fundo de uma havia um bilhete rasgado.",
            "Dentro do armário havia um casaco.",
            "O vizinho parece cansado.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.structure(text), [])

    def test_rejected_alert_does_not_silence_other_rules(self):
        # Sem o falso “sem verbo finito”, a palavra repetida da mesma frase continua apontada.
        found = self.findings("Aquela garra segura com firmeza a a menina pelo queixo.")
        self.assertEqual(self.marked(found, {"Estrutura da frase", "Palavra repetida"}), [("Palavra repetida", "a a")])

    def test_real_nominal_fragment_stays_low_priority_and_neutral(self):
        for text in ["Um bando de crianças com chapéus de papel.", "Até mesmo o modo esquisito de ela sorrir.",
                     "As unhas raspando devagar a madeira velha da porta."]:
            with self.subTest(text=text):
                for f in self.structure(text):
                    self.assertEqual((f["severity"], f["confidence"]), ("editorial_attention", "baixa"))
                    self.assertIn("pode", f["reason"])
                    self.assertIn("oração completa era pretendida", f["reason"])
                    self.assertNotIn("erro", f["reason"].casefold())

    def test_opposition_and_enumeration_favor_deliberate_fragment(self):
        for text in ["Por outro lado, uma saída lenta e barulhenta.",
                     "Por um lado, a estrada longa e deserta.",
                     "Pedras soltas, galhos secos, lama por todo o caminho."]:
            with self.subTest(text=text):
                self.assertEqual(self.structure(text), [])
                self.assertEqual(self.meta["fragmentos_sem_verbo"].get("likely_literary_fragment"), 1)

    def test_incomplete_fragments_still_alert(self):
        # Subordinante sem verbo nenhum continua uma oração incompleta, com confiança média.
        f, = self.structure("Enquanto todos na sala, depois do jantar longo.", "passado")
        self.assertEqual(f.get("confidence"), "média")
        self.assertIn("incompleta", f["reason"])


class ClauseBoundaryTests(Base):
    def residues(self, text):
        return [f["text"][f["start"]:f["end"]] for f in self.findings(text) if f["category"] == "Resíduo de edição"]

    def test_relative_clause_verb_is_not_an_auxiliary_of_the_main_predicate(self):
        for text in ["O porão em que estão é uma geladeira.", "O túnel em que estamos é um labirinto.",
                     "O quarto onde estão é um caos.", "A cabana em que estão é uma ruína."]:
            with self.subTest(text=text):
                self.assertEqual(self.residues(text), [])

    def test_adjacent_finite_auxiliaries_in_one_clause_still_alert(self):
        for text, marked in [("Eu tinha havia percebido.", "tinha havia"), ("Ele estava é correndo pela rua.", "estava é")]:
            with self.subTest(text=text):
                self.assertEqual(self.residues(text), [marked])


class PresentNarrationPlanesTests(Base):
    """Narração no presente: passado de anterioridade em oração dependente não é mudança de plano."""

    def temporal(self, text):
        return self.marked(self.findings(text, "presente"), TEMPORAIS)

    def test_anteriority_in_dependent_clauses(self):
        for text in [
            "Ela guarda o caderno que tinha esquecido no ônibus.",   # mais-que-perfeito em relativa
            "Ele toca a marca que havia ganhado na infância.",
            "Ela recorda o rapaz que encontrou na festa.",           # perfeito em relativa
            "Rita descobre que foi na cozinha que deixou as chaves.",  # completiva e clivada
            "Ela avista um rosto que jamais pensou que reveria.",
            "Ela entende que ele não ligou porque tinha perdido o telefone.",  # completiva + causal
            "Bruno sorri quando lembra do dia em que venceu a corrida.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.temporal(text), [])

    def test_imperfect_in_dependent_clause_stays_visible_with_low_confidence(self):
        # Estado anterior (legítimo) ou ação simultânea à cena (pediria o presente): a estrutura não decide.
        for text, verb in [("A moça que estava ali é minha prima.", "estava"),
                           ("A fazenda onde trabalhavam parece vazia.", "trabalhavam"),
                           ("Ela observa a vela que tremia no canto.", "tremia")]:
            with self.subTest(text=text):
                found = [f for f in self.findings(text) if f["category"] in TEMPORAIS]
                self.assertEqual([f["text"][f["start"]:f["end"]] for f in found], [verb])
                self.assertEqual(found[0]["confidence"], "baixa")
                self.assertIn("imperfeito", found[0]["reason"])

    def test_main_line_verb_misattached_by_the_parser_still_alerts(self):
        # Verbo finito coordenado a um infinitivo ou a um subjuntivo, ou pendurado num adjetivo:
        # pertence à linha principal.
        for text, verb in [("Ela se abaixa para pegar a moeda, mas não encontrou nada.", "encontrou"),
                           ("Ele sente como se alguém o seguisse, e realmente seguia.", "seguia")]:
            with self.subTest(text=text):
                found = [f for f in self.findings(text) if f["category"] in TEMPORAIS]
                hit = [f for f in found if f["text"][f["start"]:f["end"]] == verb]
                self.assertEqual(len(hit), 1, found)
                self.assertNotEqual(hit[0]["confidence"], "baixa")

    def test_relative_clause_is_not_compared_with_the_next_main_verb(self):
        for text in ["Ele recorda a briga que havia tido e percebe o erro.",
                     "A menina se lembra do susto que havia passado e percebe que foi por isso que perdeu a voz."]:
            with self.subTest(text=text):
                self.assertEqual(self.temporal(text), [])

    def test_modal_imperfect_is_not_narrative_past(self):
        # ‘Devia’ + infinitivo ≈ ‘deveria’: expectativa, sem alerta.
        self.assertEqual(self.temporal("As pedras soltas deviam atrapalhar a escalada, mas é justamente o pânico que o faz subir."), [])
        # ‘Podia’ + infinitivo divide-se entre ‘poderia’ e capacidade no passado: só confiança baixa.
        found = [f for f in self.findings("O mapa podia indicar outra rota, mas ela confia no próprio instinto.")
                 if f["category"] in TEMPORAIS]
        self.assertTrue(all(f["confidence"] == "baixa" for f in found), found)
        self.assertNotIn("confia", [f["text"][f["start"]:f["end"]] for f in found])

    def test_real_shifts_in_the_main_line_still_alert(self):
        for text, verb in [("Ela abre a janela e correu até a porta.", "correu"),
                           ("Ele senta na cadeira e pediu um café.", "pediu"),
                           ("Ela abriu a caixa que ganhou do avô.", "abriu"),
                           # Verbo principal que o modelo pendura no sujeito nominal continua na linha principal.
                           ("O menino correu até o portão.", "correu"),
                           ("Alguns livros caíram da estante.", "caíram"),
                           # Imperfeito sem infinitivo é passado da cena, não modalidade.
                           ("O cachorro latia, mas ela ignora o barulho.", "latia")]:
            with self.subTest(text=text):
                self.assertIn(("Tempo verbal", verb), self.temporal(text))

    def test_one_alert_per_tense_shift(self):
        # O passado é o desvio numa narração no presente; o presente coordenado não ganha outro alerta.
        self.assertEqual(self.temporal("Ele abriu a porta e olha para fora."), [("Tempo verbal", "abriu")])

    def test_past_narration_is_unchanged(self):
        found = self.marked(self.findings("Ela abriu a porta e olha para fora.", "passado"), TEMPORAIS)
        self.assertIn("olha", [verb for _, verb in found])


class QuotedEmphasisTests(Base):
    def dialogue(self, text):
        return [f for f in self.findings(text, "passado") if f["category"] == "Pontuação de diálogo"]

    def test_emphasis_quotes_are_not_speech(self):
        for text in ["Ele escolheu o caminho ‘mais curto’, mas se perdeu na trilha.",
                     "Era uma resposta “genial”, mas ninguém concordou com ela.",
                     "A tal ‘solução definitiva’, porém, durou dois dias."]:
            with self.subTest(text=text):
                self.assertEqual(self.dialogue(text), [])

    def test_speech_in_quotes_still_checked(self):
        for text in ["“Vou buscar a lanterna”, abriu a gaveta e saiu.", "“Corre”, empurrou o irmão para fora."]:
            with self.subTest(text=text):
                self.assertEqual(len(self.dialogue(text)), 1)


class IncompleteSubordinateTests(Base):
    def structure(self, text, tense="presente"):
        return [f for f in self.findings(text, tense) if f["category"] == "Estrutura da frase"]

    def test_isolated_subordinate_clause(self):
        for text, opener in [("Quando ela chega ao portão.", "Quando"), ("Quando as luzes se apagam.", "Quando"),
                             ("Assim que a chuva passa.", "Assim que"), ("Embora ninguém responda.", "Embora"),
                             ("Quando chegou ao quarto depois de falar com todos.", "Quando")]:
            with self.subTest(text=text):
                tense = "passado" if "chegou" in text else "presente"
                f, = self.structure(text, tense)
                self.assertEqual(f["category_code"], "incomplete_subordinate_clause")
                self.assertEqual(f["confidence"], "baixa")
                self.assertIn(f"iniciado por ‘{opener}’", f["reason"])
                self.assertNotIn("não tem verbo finito", f["reason"])

    def test_subordinate_with_main_clause_or_adverbial_locution(self):
        for text in ["Quando ela chega ao portão, o cachorro late.", "Enquanto isso, a chuva cai sem parar.",
                     "Assim que a chuva passa, eles saem.", "Se ela quiser, pode ficar."]:
            with self.subTest(text=text):
                self.assertEqual(self.structure(text), [])


def match(text, word, replacements=()):
    offset = len(text[:text.index(word)].encode("utf-16-le")) // 2
    return {"offset": offset, "length": len(word.encode("utf-16-le")) // 2, "message": "Possível erro de ortografia.",
            "replacements": [{"value": r} for r in replacements],
            "rule": {"id": "MORFOLOGIK_RULE_PT_BR", "issueType": "misspelling", "category": {"id": "TYPOS"}}}


class Response:
    def __init__(self, matches):
        import json
        self.body = json.dumps({"matches": matches}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        import json
        return self.body


def spelling(blocks, answers, settings=None):
    from urllib.parse import unquote_plus

    def respond(request, timeout):
        text = unquote_plus(dict(x.split("=", 1) for x in request.data.decode().split("&"))["text"])
        return Response(answers.get(text, []))

    with patch("fonte.languagetool.build_opener") as builder:
        builder.return_value.open.side_effect = respond
        return lt.check(blocks, settings=settings)[0]


class FictionalVocabularyTests(unittest.TestCase):
    def test_plural_of_a_recognized_name(self):
        first, second = "Um bando de Kirvane surge na estrada.", "Kirvanes atacam à noite."
        answers = {first: [match(first, "Kirvane", ["Carvana"])], second: [match(second, "Kirvanes", ["Caravanas"])]}
        self.assertEqual(spelling([Block(1, first), Block(2, second)], answers), [])

    def test_accepted_terms_of_the_work_cover_plural(self):
        text = "Ozzaris descem o rio."
        answers = {text: [match(text, "Ozzaris", ["Ossários"])]}
        self.assertEqual(spelling([Block(1, text)], answers, {"ignored_names": ["Ozzari"]}), [])
        self.assertEqual(len(spelling([Block(1, text)], answers)), 1)

    def test_credits_line_is_a_name(self):
        blocks = [Block(1, "Revisão"), Block(2, "Talvren Mox"), Block(3, "A chuva caiu cedo.")]
        answers = {"Talvren Mox": [match("Talvren Mox", "Talvren", ["Taverna"])]}
        self.assertEqual(spelling(blocks, answers), [])
        # Frase com pontuação não é linha de créditos: a grafia continua conferida.
        text = "Derrepente."
        self.assertEqual(len(spelling([Block(1, text)], {text: [match(text, "Derrepente", ["De repente"])]})), 1)

    def test_recurring_unknown_term_has_low_confidence(self):
        texts = ["o velho vurnak dormia.", "um vurnak atravessou a sala.", "Nenhum vurnak voltou."]
        answers = {t: [match(t, "vurnak", ["burnak"])] for t in texts}
        found = spelling([Block(i + 1, t) for i, t in enumerate(texts)], answers)
        self.assertEqual(len(found), 3)
        self.assertTrue(all(f["confidence"] == "baixa" for f in found), found)
        self.assertTrue(all("Nomes aceitos" in f["reason"] for f in found))
        # Uma só ocorrência mantém a confiança do corretor.
        text = "Ontme ele saiu cedo."
        f, = spelling([Block(1, text)], {text: [match(text, "Ontme", ["Ontem"])]})
        self.assertEqual(f["confidence"], "alta")


if __name__ == "__main__":
    unittest.main()
