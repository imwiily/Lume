"""LanguageTool pedido e indisponível (estabilização, Fase 6b, D4).

O FONTE segue sem o corretor, e o relatório diz que a análise foi parcial: qual componente faltou,
em que etapa e por quê. Nenhum alerta do corretor entra, nem os de antes da falha. Antes da 6b, a
análise era interrompida sem relatório. O LanguageTool é simulado.
"""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from fonte import cli
from fonte import languagetool as lt
from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate

from tests.test_languagetool import Response, match

TEXTO = "Ela parou,, e olhou  depois."


def rodar(respostas, languagetool=True, **extra):
    regras = {r: False for r in validate({})["rules"]}
    regras["pontuacao_duplicada"] = regras["espacamento"] = True
    with patch("fonte.languagetool.build_opener") as builder:
        builder.return_value.open.side_effect = respostas
        return run([Block(1, TEXTO), Block(2, "Outro parágrafo.")], lambda: None, settings=validate({"rules": regras}),
                   mode="linguistica", languagetool=languagetool, **extra)


class PipelineTests(unittest.TestCase):
    def test_server_down_keeps_fonte_and_marks_partial(self):
        def fora(request, timeout):
            raise URLError("recusado")
        achados, avisos, meta = rodar(fora)
        desligado, _, meta_desligado = rodar(None, languagetool=False)
        self.assertEqual([f["id"] for f in achados], [f["id"] for f in desligado])
        self.assertEqual(meta["languagetool_status"], "indisponivel")
        ausente, = meta["analise_parcial"]["ausente"]
        self.assertEqual((ausente["etapa"], ausente["componente"]), ("linguistic", "LanguageTool"))
        self.assertIn("não respondeu", ausente["motivo"])
        etapa = next(s for s in meta["stages"] if s["module"] == "linguistic")
        self.assertEqual((etapa["state"], etapa["ausente"]), ("completed", "LanguageTool"))
        self.assertTrue(any(a.startswith("Análise parcial: o corretor gramatical local") for a in avisos))
        self.assertNotIn("analise_parcial", meta_desligado)

    def test_failure_after_some_paragraphs_keeps_none_of_its_alerts(self):
        respostas = iter([Response([match(TEXTO, "olhou", "MORFOLOGIK_RULE_PT_BR", "misspelling", "TYPOS")])])

        def responde(request, timeout):
            try:
                return next(respostas)
            except StopIteration:
                raise URLError("caiu") from None
        achados, _, meta = rodar(responde)
        self.assertFalse(any(f["source"].startswith("LanguageTool") for f in achados))
        self.assertIn("analise_parcial", meta)

    def test_failure_to_start_is_passed_by_the_caller(self):
        def nao_chama(request, timeout):
            raise AssertionError("não deveria consultar o servidor")
        _, _, meta = rodar(nao_chama, languagetool_falha="O corretor gramatical embutido não iniciou.")
        self.assertEqual(meta["analise_parcial"]["ausente"][0]["motivo"], "O corretor gramatical embutido não iniciou.")

    def test_working_server_is_not_partial(self):
        _, _, meta = rodar(lambda request, timeout: Response([]))
        self.assertNotIn("analise_parcial", meta)
        self.assertNotIn("languagetool_status", meta)

    def test_invalid_port_is_still_a_configuration_error(self):
        with self.assertRaisesRegex(ValueError, "porta"):
            rodar(None, port=0)


class CommandLineTests(unittest.TestCase):
    def test_embedded_server_that_does_not_start_gives_a_partial_report(self):
        from docx import Document

        @contextmanager
        def nao_inicia():
            raise lt.LanguageToolIndisponivel("O corretor gramatical embutido não iniciou.")
            yield
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.docx"
            document = Document(); document.add_paragraph(TEXTO); document.save(path)
            config = Path(directory) / "busca.json"
            regras = {r: False for r in validate({})["rules"]}
            regras["pontuacao_duplicada"] = True
            config.write_text(json.dumps({"rules": regras}))
            saida = io.StringIO()
            with patch.object(lt, "available", return_value=True), patch.object(lt, "embedded", nao_inicia), \
                    patch("sys.stdout", saida):
                code = cli.main(["revisar", str(path), "--modo", "linguistica", "--languagetool", "--config", str(config),
                                 "--saida", str(Path(directory) / "out")])
            self.assertEqual(code, 0)
            report = json.loads((Path(directory) / "out/relatorio.json").read_text())
            meta = report["metadata"]
            # O relatório não diz que o corretor rodou: pedido, indisponível, sem origem.
            self.assertEqual((meta["languagetool"], meta["languagetool_pedido"], meta["languagetool_origem"],
                              meta["languagetool_status"]), (False, True, None, "indisponivel"))
            self.assertEqual(meta["analise_parcial"]["ausente"][0]["componente"], "LanguageTool")
            self.assertTrue(any(w.startswith("Análise parcial") for w in report["warnings"]))
            self.assertEqual([f["excerpt"] for f in report["findings"]], [",,"])
            self.assertIn("INDISPONÍVEL", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
