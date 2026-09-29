"""Testes sem modelo real: leitura, verificação de trechos, memória, retomada e placar."""
import json
from pathlib import Path
import tempfile
import unittest

from coerencia.analise import Analise, chave, trecho_valido
from coerencia.cli import RAIZ, carregar_caso, casa
from coerencia.leitura import cenas, ler_paragrafos
from coerencia.modelo import Ollama

TEXTO = ["Capítulo 1", "Lia tinha olhos verdes e um anel de prata.", "Ela saiu cedo.",
         "Capítulo 2", "No jantar, Lia piscou os olhos castanhos para o irmão."]


class FakeModel:
    modelo = "falso:1b"

    def __init__(self, respostas, juiz=True):
        self.respostas, self.juiz, self.pedidos = list(respostas), juiz, []

    def json(self, sistema, usuario, esquema, etapa):
        self.pedidos.append((etapa, usuario))
        if etapa.startswith("juiz"):
            return {"contradicao": self.juiz, "confianca": "alta", "explicacao": "cores diferentes"}
        return self.respostas.pop(0)


def fato(entidade, aspecto, valor, paragrafo, trecho, fonte="narrador"):
    return {"entidade": entidade, "tipo": "personagem", "aspecto": aspecto, "valor": valor,
            "paragrafo": paragrafo, "trecho": trecho, "fonte": fonte}


class LeituraTests(unittest.TestCase):
    def test_numbering_and_scenes_follow_chapters(self):
        paragrafos = ler_paragrafos(TEXTO)
        self.assertEqual([p.numero for p in paragrafos], [1, 2, 3, 4, 5])
        partes = cenas(paragrafos)
        self.assertEqual([(c.inicio, c.fim) for c in partes], [(2, 3), (5, 5)])

    def test_long_chapter_is_split_by_size(self):
        paragrafos = ler_paragrafos(["Capítulo 1"] + ["palavra " * 60] * 6)
        self.assertGreater(len(cenas(paragrafos, maximo=1000)), 1)

    def test_excerpt_must_exist_in_the_given_paragraph(self):
        paragrafos = ler_paragrafos(TEXTO)
        self.assertTrue(trecho_valido(paragrafos, 2, "olhos  VERDES"))
        self.assertFalse(trecho_valido(paragrafos, 3, "olhos verdes"))
        self.assertFalse(trecho_valido(paragrafos, 99, "olhos verdes"))
        self.assertEqual(chave("O  Anel "), "anel")


class AnaliseTests(unittest.TestCase):
    def respostas(self):
        return [
            {"fatos": [fato("Lia", "cor dos olhos", "verdes", 2, "olhos verdes"),
                       fato("Lia", "idade", "trinta", 2, "tinha trinta anos")],  # trecho inventado
             "conflitos": []},
            {"fatos": [fato("Lia", "Cor dos olhos", "castanhos", 5, "olhos castanhos")], "conflitos": []},
        ]

    def test_invented_excerpts_are_discarded_and_pairs_are_judged(self):
        with tempfile.TemporaryDirectory() as pasta:
            paragrafos = ler_paragrafos(TEXTO)
            modelo = FakeModel(self.respostas())
            analise = Analise(paragrafos, cenas(paragrafos), modelo, pasta, registrar=lambda *_: None)
            analise.extrair()
            self.assertEqual(len(analise.memoria), 2)
            self.assertEqual(analise.descartes[0]["trecho"], "tinha trinta anos")
            contradicoes = analise.julgar()
            self.assertEqual([(c["a"]["paragrafo"], c["b"]["paragrafo"]) for c in contradicoes], [(2, 5)])
            self.assertTrue((Path(pasta) / "cenas/002.json").exists())
            # A cena 2 recebeu o fato conhecido da cena 1 no pedido.
            self.assertIn("cor dos olhos: verdes", modelo.pedidos[1][1])

    def test_scenes_are_reused_when_resuming(self):
        with tempfile.TemporaryDirectory() as pasta:
            paragrafos = ler_paragrafos(TEXTO)
            Analise(paragrafos, cenas(paragrafos), FakeModel(self.respostas()), pasta, lambda *_: None).extrair()
            segundo = FakeModel([])
            analise = Analise(paragrafos, cenas(paragrafos), segundo, pasta, lambda *_: None)
            analise.extrair()
            self.assertEqual(segundo.pedidos, [])
            self.assertEqual(len(analise.memoria), 2)

    def test_judge_can_reject_and_suggested_conflicts_need_real_excerpts(self):
        with tempfile.TemporaryDirectory() as pasta:
            paragrafos = ler_paragrafos(TEXTO)
            respostas = [{"fatos": [], "conflitos": []},
                         {"fatos": [], "conflitos": [
                             {"paragrafo": 5, "trecho": "olhos castanhos", "paragrafo_anterior": 2,
                              "trecho_anterior": "olhos verdes", "explicacao": "cor"},
                             {"paragrafo": 5, "trecho": "olhos azuis", "paragrafo_anterior": 2,
                              "trecho_anterior": "olhos verdes", "explicacao": "inventado"}]}]
            analise = Analise(paragrafos, cenas(paragrafos), FakeModel(respostas, juiz=False), pasta, lambda *_: None)
            analise.extrair()
            self.assertEqual(len(analise.sugestoes), 1)
            self.assertEqual(analise.julgar(), [])


class PlacarTests(unittest.TestCase):
    def deteccao(self, pa, ta, pb, tb):
        return {"a": {"paragrafo": pa, "trecho": ta}, "b": {"paragrafo": pb, "trecho": tb}}

    def test_pair_of_paragraphs_or_same_paragraph_excerpt(self):
        gabarito = {"p": 19, "contra": 7, "trecho": "capa vermelha"}
        self.assertTrue(casa(self.deteccao(7, "capa verde", 19, "caderno de capa vermelha"), gabarito))
        self.assertTrue(casa(self.deteccao(3, "outro", 19, "capa vermelha"), gabarito))
        self.assertFalse(casa(self.deteccao(3, "outro", 19, "não estava mais"), gabarito))
        self.assertFalse(casa(self.deteccao(7, "capa verde", 18, "capa"), gabarito))
        mesmo = {"p": 20, "contra": 20, "trecho": "cinco anos mais velha"}
        self.assertTrue(casa(self.deteccao(20, "irmã mais nova", 20, "cinco anos mais velha"), mesmo))

    def test_annotations_exist_in_the_texts(self):
        casos = json.loads((RAIZ / "avaliacao/casos.json").read_text(encoding="utf-8"))["casos"]
        cache = {}
        for caso in casos:
            paragrafos = carregar_caso(caso, cache)
            for g in caso["contradicoes"]:
                with self.subTest(caso=caso["id"], trecho=g["trecho"]):
                    self.assertTrue(trecho_valido(paragrafos, g["p"], g["trecho"]))
                    self.assertLessEqual(g["contra"], g["p"])


class ModeloTests(unittest.TestCase):
    def test_only_local_addresses_are_accepted(self):
        with self.assertRaises(ValueError):
            Ollama("x", endereco="https://exemplo.com")
        Ollama("x", endereco="http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
