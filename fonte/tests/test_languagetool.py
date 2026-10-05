"""Integração com o LanguageTool local: filtros, falas e ciclo do servidor embutido.

O servidor é simulado; estes testes não medem a qualidade das regras do LanguageTool.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fonte import languagetool as lt
from fonte.reader import Block


class Response:
    def __init__(self, matches):
        self.body = json.dumps({"matches": matches}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


def match(text, word, rule_id, issue="grammar", category="GRAMMAR", replacements=()):
    offset = len(text[:text.index(word)].encode("utf-16-le")) // 2
    return {"offset": offset, "length": len(word.encode("utf-16-le")) // 2, "message": "Confira.",
            "replacements": [{"value": r} for r in replacements],
            "rule": {"id": rule_id, "issueType": issue, "category": {"id": category}}}


def check(blocks, answers):
    """`answers` associa o texto do parágrafo às ocorrências devolvidas pelo servidor."""
    sent = []

    def respond(request, timeout):
        text = dict(x.split("=", 1) for x in request.data.decode().split("&"))["text"]
        from urllib.parse import unquote_plus
        text = unquote_plus(text)
        sent.append(text)
        return Response(answers.get(text, []))

    with patch("fonte.languagetool.build_opener") as builder:
        builder.return_value.open.side_effect = respond
        results, _ = lt.check(blocks)
    return results, sent


class FilterTests(unittest.TestCase):
    def test_dialogue_text_is_sent_and_checked(self):
        text = "— Voce viu? — perguntou ela."
        results, sent = check([Block(1, text)], {text: [match(text, "Voce", "PT_VOCE", "misspelling", "TYPOS", ["Você"])]})
        self.assertEqual(sent, [text])
        self.assertEqual([(r["text"][r["start"]:r["end"]], r["suggestion"]) for r in results], [("Voce", "Você")])

    def test_speech_tag_after_dash_is_not_sentence_start(self):
        text = "— Vamos? — perguntou ela. isso não."
        answers = {text: [match(text, "perguntou", "UPPERCASE_SENTENCE_START", "typographical", "CASING"),
                          match(text, "isso", "UPPERCASE_SENTENCE_START", "typographical", "CASING")]}
        results, _ = check([Block(1, text)], answers)
        self.assertEqual([r["text"][r["start"]:r["end"]] for r in results], ["isso"])

    def test_proper_names_are_not_spelling_errors(self):
        first, second = "Iolanda chegou.", "Depois, Iolanda saiu com Xarb."
        answers = {first: [match(first, "Iolanda", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")],
                   second: [match(second, "Xarb", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")]}
        results, _ = check([Block(1, first), Block(2, second)], answers)
        # ‘Iolanda’ aparece no meio de frase; ‘Xarb’ também. Nenhum é apontado.
        self.assertEqual(results, [])

    def test_sentence_initial_only_word_is_still_checked(self):
        text = "Ontem choveu. Derrepente parou."
        results, _ = check([Block(1, text)], {text: [match(text, "Derrepente", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")]})
        self.assertEqual(len(results), 1)

    def test_style_and_register_are_ignored(self):
        text = "— Tá indo pra casa? — perguntou."
        answers = {text: [match(text, "pra", "FORMAL_PRA_PARA", "style", "FORMAL"),
                          match(text, "Tá", "X", "register", "COLLOQUIALISMS")]}
        self.assertEqual(check([Block(1, text)], answers)[0], [])

    def test_italic_spelling_is_protected_but_grammar_is_not(self):
        text = "Ele pensou: weltschmerz demais as coisa."
        block = Block(1, text, italic=[(text.index("weltschmerz"), text.index("weltschmerz") + 11)])
        answers = {text: [match(text, "weltschmerz", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS"),
                          match(text, "as coisa", "AGREEMENT", "grammar", "GRAMMAR")]}
        results, _ = check([block], answers)
        self.assertEqual([r["text"][r["start"]:r["end"]] for r in results], ["as coisa"])

    def test_headings_are_not_sent(self):
        _, sent = check([Block(1, "Capítulo 1", heading=True), Block(2, "Texto.")], {})
        self.assertEqual(sent, ["Texto."])


class EmbeddedServerTests(unittest.TestCase):
    def test_home_requires_server_jar(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"FONTE_LANGUAGETOOL": directory}):
            with patch.object(lt, "__file__", str(Path(directory) / "x/fonte/languagetool.py")):
                self.assertIsNone(lt.home())
                (Path(directory) / lt.SERVER_JAR).write_text("")
                self.assertEqual(lt.home(), Path(directory))

    def test_bundled_java_is_preferred(self):
        with tempfile.TemporaryDirectory() as directory:
            java = Path(directory) / "jre/bin/java"
            java.parent.mkdir(parents=True)
            java.write_text("#!/bin/sh\n")
            java.chmod(0o755)
            self.assertEqual(lt.java(Path(directory)), java)

    def test_frozen_engine_does_not_use_system_java(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(lt.sys, "frozen", True, create=True):
            self.assertIsNone(lt.java(Path(directory)))

    def test_missing_embedded_checker_is_reported(self):
        with patch.object(lt, "home", return_value=None):
            with self.assertRaisesRegex(ValueError, "não foi encontrado"):
                with lt.embedded():
                    pass

    def test_server_that_exits_is_reported_and_port_is_local(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / lt.SERVER_JAR).write_text("")
            fake = root / "jre/bin/java"
            fake.parent.mkdir(parents=True)
            fake.write_text("#!/bin/sh\necho falha simulada >&2\nexit 3\n")
            fake.chmod(0o755)
            with patch.object(lt, "home", return_value=root):
                with self.assertRaisesRegex(ValueError, "falha simulada"):
                    with lt.embedded(timeout=10):
                        pass
        port = lt.free_port()
        self.assertTrue(1024 < port < 65536)


class CommandLineTests(unittest.TestCase):
    def test_explicit_port_uses_external_server_even_with_embedded_available(self):
        from fonte import cli
        from docx import Document
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.docx"
            document = Document(); document.add_paragraph("Texto simples."); document.save(path)
            calls = {}

            def fake_run(blocks, loader, **kwargs):
                calls.update(kwargs)
                return [], [], {}
            with patch.object(lt, "available", return_value=True), \
                    patch.object(lt, "embedded", side_effect=AssertionError("não deveria iniciar")), \
                    patch.object(cli, "run_pipeline", side_effect=fake_run):
                code = cli.main(["revisar", str(path), "--languagetool", "--porta-lt", "8099",
                                 "--saida", str(Path(directory) / "out")])
            self.assertEqual(code, 0)
            self.assertEqual((calls["languagetool"], calls["port"]), (True, 8099))
            report = json.loads((Path(directory) / "out/relatorio.json").read_text())
            self.assertEqual(report["metadata"]["languagetool_origem"], "externo")


if __name__ == "__main__":
    unittest.main()


class ProgressoTests(unittest.TestCase):
    def test_pipeline_reports_paragraph_progress_during_the_stage(self):
        from fonte.pipeline import run
        from fonte.settings import RULES, validate
        blocks = [Block(i + 1, f"Parágrafo número {i + 1}.") for i in range(30)]
        eventos = []
        with patch("fonte.languagetool.build_opener") as builder:
            builder.return_value.open.side_effect = lambda request, timeout: Response([])
            run(blocks, lambda: None, settings=validate({"rules": {r: False for r in RULES}}), mode="linguistica", languagetool=True,
                progress=eventos.append)
        andamento = [(e["done"], e["total"], e["unit"]) for e in eventos if e.get("module") == "linguistic" and "done" in e]
        self.assertTrue(andamento)
        self.assertEqual(andamento[-1], (30, 30, "parágrafos"))
        self.assertEqual([d for d, *_ in andamento], sorted(d for d, *_ in andamento))
        self.assertTrue(all(e["state"] == "running" for e in eventos if "done" in e))


class FiltrosManuscritoTests(unittest.TestCase):
    """Filtros genéricos para alarmes vistos num manuscrito real."""

    def test_proper_name_after_comma_is_not_lowercased(self):
        texto = "— Tenha cuidado, Lívia!"
        outro = "Depois, Lívia saiu."
        resultados, _ = check([Block(1, texto), Block(2, outro)],
                              {texto: [match(texto, "Lívia", "UPPERCASE_AFTER_COMMA", "typographical", "CASING", ["lívia"])]})
        self.assertEqual(resultados, [])

    def test_onomatopoeia_interjections_and_cut_words_are_not_spelling_errors(self):
        casos = ["— Humm, está bem.", "— Hm? O que foi?", "Fwoosh!", "BOOOOM!", "— Haaaa! Toma!", "— Isso é proí…"]
        palavras = ["Humm", "Hm", "Fwoosh", "BOOOOM", "Haaaa", "proí"]
        respostas = {t: [match(t, w, "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")] for t, w in zip(casos, palavras)}
        resultados, _ = check([Block(i + 1, t) for i, t in enumerate(casos)], respostas)
        self.assertEqual(resultados, [])
        # Erro comum continua apontado.
        texto = "Ele forçei a porta."
        resultados, _ = check([Block(1, texto)], {texto: [match(texto, "forçei", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")]})
        self.assertEqual(len(resultados), 1)

    def test_inverted_subject_after_speech_verb_needs_no_crase(self):
        texto = "— Não vi nada — respondeu a vizinha."
        resultados, _ = check([Block(1, texto)], {texto: [match(texto, "respondeu a", "CRASE_CONFUSION", "grammar", "CONFUSED_WORDS")]})
        self.assertEqual(resultados, [])

    def test_style_suggestions_on_dialogue_punctuation_are_ignored(self):
        texto = "— Até amanhã. — …Mais ou menos."
        respostas = {texto: [match(texto, "amanhã.", "INTERJECTIONS_PUNTUATION", "grammar", "PUNCTUATION"),
                             match(texto, "Mais", "SENTENCE_WHITESPACE", "whitespace", "TYPOGRAPHY")]}
        self.assertEqual(check([Block(1, texto)], respostas)[0], [])


class FiltrosSegundoRelatorioTests(unittest.TestCase):
    """Falsos positivos marcados pelo autor em relatórios reais (29/09/2026), generalizados."""

    def test_repeated_capitalized_unknown_word_is_a_name(self):
        textos = ["“Taluma.”", "Taluma estreitou os olhos."]
        respostas = {t: [match(t, "Taluma", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")] for t in textos}
        self.assertEqual(check([Block(1, textos[0]), Block(2, textos[1])], respostas)[0], [])
        # Uma única ocorrência, ou a mesma forma também em minúscula, continua apontada.
        texto = "Ontme ele saiu cedo."
        self.assertEqual(len(check([Block(1, texto)], {texto: [match(texto, "Ontme", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")]})[0]), 1)
        textos = ["Trmbém saiu.", "Trmbém voltou.", "Ele trmbém ficou."]
        respostas = {t: [match(t, t.split()[0] if t[0] == "T" else "trmbém", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")] for t in textos}
        self.assertEqual(len(check([Block(i + 1, t) for i, t in enumerate(textos)], respostas)[0]), 3)

    def test_capital_after_colon_is_kept(self):
        texto = "— Primeira apresentação: Lara, da turma do fundo, e depois Tomé."
        respostas = {texto: [match(texto, ": Lara", "UPPERCASE_AFTER_COMMA", "typographical", "CASING", [": lara"])]}
        self.assertEqual(check([Block(1, texto)], respostas)[0], [])
        texto = "Ele chegou, Depois saiu."
        respostas = {texto: [match(texto, ", Depois", "UPPERCASE_AFTER_COMMA", "typographical", "CASING", [", depois"])]}
        self.assertEqual(len(check([Block(1, texto)], respostas)[0]), 1)

    def test_participle_after_todos_is_not_a_noun(self):
        for texto, trecho in [("— Quero todos sentados antes do sinal.", "todos sentados"),
                              ("Queria todas sentadas antes do sinal.", "todas sentadas")]:
            with self.subTest(texto=texto):
                respostas = {texto: [match(texto, trecho, "TODOS_FOLLOWED_BY_NOUN_PLURAL")]}
                self.assertEqual(check([Block(1, texto)], respostas)[0], [])
        texto = "Todos alunos saíram cedo."
        respostas = {texto: [match(texto, "Todos alunos", "TODOS_FOLLOWED_BY_NOUN_PLURAL")]}
        self.assertEqual(len(check([Block(1, texto)], respostas)[0]), 1)

    def test_verb_before_gerund_is_not_a_paronym(self):
        texto = "A chuva continua caindo sobre o telhado."
        respostas = {texto: [match(texto, "continua", "LP_PARONYMS", replacements=["contínua"])]}
        self.assertEqual(check([Block(1, texto)], respostas)[0], [])
        texto = "Foi uma vigília continua."
        respostas = {texto: [match(texto, "continua", "LP_PARONYMS", replacements=["contínua"])]}
        self.assertEqual(len(check([Block(1, texto)], respostas)[0]), 1)

    def test_onomatopoeia_reduplication_is_not_a_repeated_word(self):
        texto = "— Au au, quieto aí, ninguém vai te machucar."
        respostas = {texto: [match(texto, "Au au", "PORTUGUESE_WORD_REPEAT_RULE", "duplication", "TYPOS")]}
        self.assertEqual(check([Block(1, texto)], respostas)[0], [])
        texto = "Ele saiu saiu de casa."
        respostas = {texto: [match(texto, "saiu saiu", "PORTUGUESE_WORD_REPEAT_RULE", "duplication", "TYPOS")]}
        self.assertEqual(len(check([Block(1, texto)], respostas)[0]), 1)

    def test_alem_de_as_complement_is_not_the_connector(self):
        # ‘nada além disso’ = ‘nada mais do que isso’: ‘além de’ completa o pronome ou o sintagma.
        for texto, marcado in [("Não sobrou nada além disso.", "nada além disso"),
                               ("Eu não queria nada além disso.", "nada além disso"),
                               ("Ninguém sabia nada além disso.", "nada além disso"),
                               ("Não encontrei ninguém além dele.", "ninguém além dele"),
                               ("Não restou coisa alguma além daquilo.", "alguma além daquilo"),
                               ("Não precisava de coisa alguma além daquilo.", "alguma além daquilo"),
                               ("Ela não comprou nenhum caderno além desse.", "caderno além desse"),
                               ("O menino queria tudo além disso.", "tudo além disso"),
                               ("Não restava nada mais além disso.", "mais além disso")]:
            with self.subTest(texto=texto):
                respostas = {texto: [match(texto, marcado, "VERB_COMMA_CONJUNCTION", "uncategorized", "PUNCTUATION",
                                           [marcado.replace(" além", ", além")])]}
                self.assertEqual(check([Block(1, texto)], respostas)[0], [])

    def test_alem_disso_connector_without_commas_still_alerts(self):
        # Conector (= ademais) sem vírgulas: depois de conjunção, de adjetivo ou no início da frase,
        # inclusive quando a frase anterior termina em ‘nada’.
        for texto, marcado, sugestao in [("Ele estava cansado e além disso precisava dormir.", "e além disso", "e, além disso"),
                                         ("Ele estava cansado além disso precisava dormir.", "cansado além disso", "cansado, além disso"),
                                         ("A tarefa era difícil e além disso faltava tempo.", "e além disso", "e, além disso"),
                                         ("Não sobrou nada. Além disso estava escuro.", "Além disso", "Além disso,")]:
            with self.subTest(texto=texto):
                encontrado = match(texto, marcado, "VERB_COMMA_CONJUNCTION", "uncategorized", "PUNCTUATION", [sugestao])
                encontrado["message"] = ("Esta locução deve ser separada por vírgulas, e só deve ser utilizada no "
                                         "início duma frase para efeitos de estilo.")
                r, = check([Block(1, texto)], {texto: [encontrado]})[0]
                self.assertEqual((r["text"][r["start"]:r["end"]], r["suggestion"]), (marcado, sugestao))
                # A afirmação de que o conector só cabe no início da frase é falsa e sai da mensagem.
                self.assertNotIn("início duma frase", r["reason"])
                self.assertIn("conector", r["reason"])
                self.assertIn("integra a oração", r["reason"])

    def test_alem_after_pronoun_with_following_clause_is_ambiguous(self):
        # “nada além disso precisava…”: complemento ou conector sem vírgula; na dúvida, sem alerta.
        texto = "O guarda não viu nada além disso precisava descansar."
        respostas = {texto: [match(texto, "nada além disso", "VERB_COMMA_CONJUNCTION", "uncategorized", "PUNCTUATION")]}
        self.assertEqual(check([Block(1, texto)], respostas)[0], [])

    def test_connector_message_keeps_correct_text(self):
        # Mensagem sem a afirmação falsa passa como veio do LanguageTool.
        texto = "Não sobrou nada. Além disso estava escuro."
        encontrado = match(texto, "Além disso", "VERB_COMMA_CONJUNCTION", "uncategorized", "PUNCTUATION", ["Além disso,"])
        encontrado["message"] = "Esta locução deve ser separada por vírgulas."
        r, = check([Block(1, texto)], {texto: [encontrado]})[0]
        self.assertEqual(r["reason"], "Esta locução deve ser separada por vírgulas.")

    def test_agora_sim_needs_no_commas(self):
        for texto in ["— Agora sim, dá para ouvir a banda.", "Agora sim eu entendi o recado."]:
            with self.subTest(texto=texto):
                respostas = {texto: [match(texto, "Agora sim", "VERB_COMMA_CONJUNCTION", "grammar", "PUNCTUATION")]}
                self.assertEqual(check([Block(1, texto)], respostas)[0], [])
