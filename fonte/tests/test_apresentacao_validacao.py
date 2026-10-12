"""Apresentação local dos resultados do Validador (V5): só formata registros persistidos. Transporte simulado,
nenhuma chamada de rede, texto sintético."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fonte import apresentacao_validacao as ap
from fonte import validador_v5 as v5
import test_validador_v4_1 as T
import test_validador_v5 as T5

INCONCLUSIVO = {"existe": "incerto", "natureza": "interpretativo", "certeza": "discutivel", "gravidade": "baixa",
                "evidencia_suficiente": False, "explicacao": "Pode ser um erro, mas também uma escolha; o texto não decide."}


def rodar(decisao, campos, trecho="estava", categoria="Concordância verbal"):
    b, f, dec = T.um_item(decisao, trecho, 5, categoria, "Hipótese do detector.")
    mapa = {f[0]["id"]: campos}
    t = T5.Transporte(fn=T5.por_entrada(mapa))
    with TemporaryDirectory() as pasta:
        r, _, _ = v5.avaliar(b, f, dec, pasta=pasta, teto=5.0, transporte=t)
        bruto = (Path(pasta) / v5.ARQUIVO).read_bytes()
        depois = lambda: (Path(pasta) / v5.ARQUIVO).read_bytes()
        registro = r[f[0]["id"]]
        apresentado = ap.apresentar(registro, f[0])
        texto = ap.markdown(apresentado)
        return registro, f[0], apresentado, texto, bruto, depois()


class ApresentacaoTests(unittest.TestCase):
    def test_inconclusive_shows_the_uncertainty_and_never_claims_a_problem(self):
        registro, alerta, a, texto, _, _ = rodar("Estilo do autor", INCONCLUSIVO)
        self.assertEqual(registro["estado"], "inconclusiva")
        self.assertEqual(a["problema_tecnico"]["nivel"], "nao_estabelecido")
        self.assertIn("Inconclusiva", a["resultado"])
        self.assertIn("existe = incerto", texto)
        self.assertIn("não bastava para concluir (evidencia_suficiente = falso)", texto)
        self.assertIn("Problema técnico não estabelecido pelo modelo", texto)
        self.assertIn("nenhuma evidência verificada registrada", texto)
        self.assertIn("hipótese do detector (não confirmada)", texto)
        for proibido in ("identificado pelo modelo", "contestada", "reconhece o desvio", "Sugestão do modelo"):
            self.assertNotIn(proibido, texto)
        self.assertIn("permanece como está", texto)
        self.assertIsNone(a["sugestao_do_modelo"])

    def test_uncertainty_alone_never_claims_missing_context(self):
        campos = dict(INCONCLUSIVO, evidencia_suficiente=True)         # dúvida sobre o desvio, mas texto suficiente
        registro, _, a, texto, _, _ = rodar("Estilo do autor", campos)
        self.assertEqual(registro["estado"], "inconclusiva")
        self.assertIn("existe = incerto", texto)
        for proibido in ("não bastava", "contexto", "evidencia_suficiente"):
            self.assertNotIn(proibido, texto)

    def test_explanation_wording_does_not_change_the_label(self):
        campos = dict(INCONCLUSIVO, explicacao="Isto é claramente um erro confirmado de concordância.")
        _, _, a, texto, _, _ = rodar("Estilo do autor", campos)
        self.assertEqual(a["problema_tecnico"]["nivel"], "nao_estabelecido")
        self.assertNotIn("Problema técnico identificado", texto)
        self.assertIn("claramente um erro confirmado", texto)         # o texto do modelo é citado, não adotado

    def test_objective_error_is_still_presented_as_confirmed(self):
        _, _, a, texto, _, _ = rodar("Aceito editorialmente", T.OBJETIVO)
        self.assertEqual(a["problema_tecnico"]["nivel"], "identificado")
        self.assertIn("Problema técnico identificado pelo modelo, com certeza clara", texto)
        self.assertIn("não é confirmação humana", texto)
        self.assertIn("objetiva", texto)
        self.assertIn("as caixas que estava", texto)                  # evidência verificada
        self.assertNotIn("não estabelecido", texto)

    def test_contested_decision_is_shown_without_changing_the_decision_or_applying_anything(self):
        registro, _, a, texto, _, _ = rodar("Falso positivo", dict(T.OBJETIVO, recomendacao="as caixas que estavam"))
        self.assertEqual(registro["estado"], "contestada")
        self.assertIn("a decisão humana não foi alterada", a["resultado"])
        self.assertIn("nada é aplicado ao manuscrito", texto)
        self.assertIn("Decisão do revisor: Falso positivo", texto)

    def test_false_positive_does_not_become_a_problem(self):
        campos = {"existe": "nao", "natureza": "nenhuma", "certeza": "nao_se_aplica", "gravidade": "nenhuma",
                  "justificativa_detector": "incorreta", "explicacao": "A forma está correta."}
        registro, _, a, texto, _, _ = rodar("Falso positivo", campos)
        self.assertEqual(registro["estado"], "apontamento_inadequado")
        self.assertEqual(a["problema_tecnico"]["nivel"], "nao_identificado")
        self.assertIn("não identificado", texto)
        for proibido in ("Problema técnico identificado", "reconhece o desvio", "Desvio reconhecido"):
            self.assertNotIn(proibido, texto)

    def test_discutible_deviation_is_a_phenomenon_not_a_confirmed_error(self):
        campos = dict(T.OBJETIVO, certeza="discutivel", natureza="interpretativo")
        _, _, a, texto, _, _ = rodar("Aceito editorialmente", campos)
        self.assertEqual(a["problema_tecnico"]["nivel"], "discutivel")
        self.assertNotIn("Problema técnico identificado", texto)
        self.assertIn("discutível", texto)
        self.assertTrue(any("escolha entre as leituras é editorial" in h for h in a["depende_de_avaliacao_humana"]))

    def test_missing_data_is_marked_insufficient_never_invented(self):
        a = ap.apresentar({"id": "x", "estado": "inconclusiva"})
        texto = ap.markdown(a)
        self.assertEqual(a["problema_tecnico"]["nivel"], "nao_estabelecido")
        self.assertIn(ap.INSUFICIENTE, texto)
        self.assertEqual(a["por_que_nao_concluiu"], ap.INSUFICIENTE)
        for proibido in ("Problema técnico identificado", "o modelo identificou: O modelo considerou", "«"):
            self.assertNotIn(proibido, texto)
        self.assertEqual(a["fenomeno_investigado"], ap.INSUFICIENTE)       # sem o alerta do relatório

    def test_persisted_results_and_inputs_are_untouched(self):
        registro, alerta, _, _, antes, depois = rodar("Estilo do autor", INCONCLUSIVO)
        copia, copia_alerta = deepcopy(registro), deepcopy(alerta)
        ap.markdown(ap.apresentar(registro, alerta))
        self.assertEqual((registro, alerta), (copia, copia_alerta))
        self.assertEqual(antes, depois)
        self.assertEqual(json.loads(antes)["itens"][registro["id"]]["estado"], "inconclusiva")


if __name__ == "__main__":
    unittest.main()
