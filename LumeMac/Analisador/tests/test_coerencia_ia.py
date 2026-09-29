"""Coerência com IA na etapa Coerência global, com modelo simulado (nada vai à API)."""
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import spacy

from fonte.pipeline import run
from fonte.reader import Block
from fonte.settings import validate

NLP = spacy.load("pt_core_news_sm", disable=["ner"])


class ModeloFalso:
    """Extrai “olhos <cor>” de cada parágrafo; o juiz confirma diferenças."""
    modelo = "falso:1b"

    def __init__(self, teto_chamadas=None):
        self.chamadas, self.teto_chamadas = [], teto_chamadas

    def verificar(self):
        pass

    def json(self, sistema, usuario, esquema, etapa):
        from coerencia.modelo import ErroModelo
        if self.teto_chamadas is not None and len(self.chamadas) >= self.teto_chamadas:
            raise ErroModelo("Teto de gasto atingido (teste).")
        self.chamadas.append({"etapa": etapa, "tokens_entrada": 10, "tokens_saida": 1, "custo_usd": 0.001})
        if etapa.startswith("juiz"):
            return {"contradicao": True, "confianca": "alta", "explicacao": "A cor dos olhos mudou sem explicação."}
        cena = usuario.split("\nCENA ", 1)[1]
        fatos = [{"entidade": "Lia", "tipo": "personagem", "aspecto": "cor dos olhos", "valor": cor,
                  "paragrafo": int(n), "trecho": f"olhos {cor}", "fonte": "narrador"}
                 for n, texto in re.findall(r"^\[§(\d+)\] (.*)$", cena, re.M) for cor in re.findall(r"olhos (\w+)", texto)]
        return {"fatos": fatos, "conflitos": []}


def blocos(segunda="Lia piscou os olhos castanhos."):
    return [Block(1, "Capítulo 1", "Capítulo 1", heading=True), Block(2, "Lia tinha olhos verdes.", "Capítulo 1"),
            Block(3, "Capítulo 2", "Capítulo 2", heading=True), Block(4, segunda, "Capítulo 2")]


class CoerenciaIATests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.pasta.cleanup()

    def rodar(self, textos=None, modelo=None):
        modelo = modelo or ModeloFalso()
        opcoes = dict(pasta=Path(self.pasta.name), documento="livro.docx", modelo="falso:1b", teto=1.0, esforco="medium")
        with patch("coerencia.modelo.criar_modelo", return_value=modelo):
            findings, warnings, meta = run(textos or blocos(), lambda: NLP, settings=validate({}), mode="editorial",
                                           coerencia=opcoes)
        return [f for f in findings if f.get("rule") == "coerencia_ia"], warnings, meta, modelo

    def test_contradiction_becomes_finding_with_both_excerpts_and_replaces_heuristics(self):
        achados, avisos, meta, _ = self.rodar()
        self.assertEqual(len(achados), 1)
        achado = achados[0]
        self.assertEqual((achado["module"], achado["severity"]), ("global_coherence", "possible_inconsistency"))
        self.assertEqual(achado["excerpt"], "olhos castanhos")
        self.assertEqual(achado["related"][0]["excerpt"], "olhos verdes")
        self.assertNotIn("fact_bank", meta)  # memória narrativa heurística não rodou
        self.assertEqual(meta["coerencia_ia"]["enviados"], 2)
        self.assertTrue(any("enviados à Anthropic" in a for a in avisos))

    def test_heuristic_memory_still_runs_without_ai(self):
        _, _, meta = run(blocos(), lambda: NLP, settings=validate({}), mode="editorial")
        self.assertIn("fact_bank", meta)
        self.assertNotIn("coerencia_ia", meta)

    def test_unchanged_text_costs_nothing_and_keeps_ids(self):
        primeira, *_ = self.rodar()
        segunda, _, meta, modelo = self.rodar()
        self.assertEqual(modelo.chamadas, [])
        self.assertEqual([a["id"] for a in primeira], [a["id"] for a in segunda])
        self.assertEqual(meta["coerencia_ia"]["enviados"], 0)

    def test_budget_stop_is_a_warning_not_a_failure(self):
        achados, avisos, meta, _ = self.rodar(modelo=ModeloFalso(teto_chamadas=1))
        self.assertTrue(meta["coerencia_ia"]["interrompida"])
        self.assertTrue(any("teto de gasto atingido" in a for a in avisos))
        self.assertEqual(achados, [])


class CoerenciaCLITests(unittest.TestCase):
    def documento(self, pasta):
        from docx import Document
        caminho = Path(pasta) / "t.docx"
        doc = Document()
        for texto in ["Capítulo 1", "Lia tinha olhos verdes.", "Capítulo 2", "Lia piscou os olhos castanhos."]:
            doc.add_paragraph(texto)
        doc.save(caminho)
        return caminho

    def test_estimate_prints_one_json_line_without_calling_the_api(self):
        from fonte.cli import main
        with tempfile.TemporaryDirectory() as pasta:
            saida = io.StringIO()
            with redirect_stdout(saida), patch("coerencia.modelo.Claude", side_effect=AssertionError("sem API")):
                codigo = main(["coerencia-estimar", str(self.documento(pasta)), "--coerencia-projeto", str(Path(pasta) / "p")])
            self.assertEqual(codigo, 0)
            linha = next(l for l in saida.getvalue().splitlines() if l.startswith("LUME_ESTIMATIVA "))
            dados = json.loads(linha.split(" ", 1)[1])
            self.assertEqual((dados["capitulos"], dados["a_enviar"]), (2, 2))
            self.assertGreater(dados["custo_estimado_usd"], 0)

    def test_ai_requires_project_folder_and_editorial_mode(self):
        from fonte.cli import main
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self.documento(pasta)
            self.assertEqual(main(["revisar", str(caminho), "--modo", "ambas", "--coerencia-ia",
                                   "--saida", str(Path(pasta) / "a")]), 2)
            self.assertEqual(main(["revisar", str(caminho), "--coerencia-ia", "--coerencia-projeto",
                                   str(Path(pasta) / "p"), "--saida", str(Path(pasta) / "b")]), 2)


if __name__ == "__main__":
    unittest.main()
