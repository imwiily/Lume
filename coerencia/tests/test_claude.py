"""Cliente da API do Claude com um cliente falso: pedido, custo e recusas. Nada é enviado."""
from types import SimpleNamespace
import unittest

from coerencia.analise import ESQUEMA_JUIZ
from coerencia.modelo import Claude, ErroModelo, criar_modelo


def resposta(texto='{"contradicao": true, "confianca": "alta", "explicacao": "x"}', motivo="end_turn"):
    uso = SimpleNamespace(input_tokens=1000, cache_read_input_tokens=500, cache_creation_input_tokens=0, output_tokens=200)
    return SimpleNamespace(content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=texto)],
                           usage=uso, stop_reason=motivo, model="claude-opus-5-5", _request_id="req_teste")


class ClienteFalso:
    def __init__(self, devolver):
        self.pedidos = []
        criar = lambda **pedido: (self.pedidos.append(pedido), devolver)[1]
        self.messages = SimpleNamespace(create=criar)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=criar))


class ClaudeTests(unittest.TestCase):
    def test_request_uses_strict_schema_effort_fallback_and_cached_system(self):
        cliente = ClienteFalso(resposta())
        modelo = Claude("claude-opus-5-5", esforco="high", cliente=cliente)
        self.assertTrue(modelo.json("sistema", "usuario", ESQUEMA_JUIZ, "juiz 1")["contradicao"])
        pedido = cliente.pedidos[0]
        self.assertEqual(pedido["output_config"]["effort"], "high")
        self.assertIs(pedido["output_config"]["format"]["schema"]["additionalProperties"], False)
        self.assertEqual((pedido["fallbacks"], pedido["betas"]), ("default", ["server-side-fallback-2026-07-01"]))
        self.assertEqual(pedido["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("thinking", pedido)  # Opus 5.5: sempre adaptativo; o esforço controla a profundidade

    def test_usage_and_cost_are_recorded(self):
        modelo = Claude("claude-opus-5-5", cliente=ClienteFalso(resposta()))
        modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        chamada = modelo.chamadas[0]
        self.assertEqual((chamada["tokens_entrada"], chamada["tokens_cache"], chamada["tokens_saida"]), (1500, 500, 200))
        # 1000 × 4 + 500 × 0,20 + 200 × 20, por milhão
        self.assertAlmostEqual(chamada["custo_usd"], (4000 + 100 + 4000) / 1e6)

    def test_older_model_gets_plain_request(self):
        cliente = ClienteFalso(resposta())
        Claude("claude-haiku-4-5", cliente=cliente).json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertNotIn("fallbacks", cliente.pedidos[0])
        self.assertNotIn("effort", cliente.pedidos[0]["output_config"])

    def test_refusal_and_truncation_are_errors(self):
        for motivo in ("refusal", "max_tokens"):
            with self.subTest(motivo=motivo), self.assertRaises(ErroModelo):
                Claude("claude-opus-5-5", cliente=ClienteFalso(resposta(motivo=motivo))).json("s", "u", ESQUEMA_JUIZ, "juiz")

    def test_refusal_truncation_and_cap_have_their_own_classes(self):
        # O Auditor separa os casos pela classe; o texto continua o mesmo para o Projeto.
        from coerencia.modelo import Orcamento, Recusa, RespostaCortada, TetoAtingido
        for motivo, classe in (("refusal", Recusa), ("max_tokens", RespostaCortada)):
            with self.subTest(motivo=motivo), self.assertRaises(classe):
                Claude("claude-opus-5-5", cliente=ClienteFalso(resposta(motivo=motivo))).json("s", "u", ESQUEMA_JUIZ, "juiz")
        orcamento = Orcamento(0.001); orcamento.gasto = 0.002
        with self.assertRaisesRegex(TetoAtingido, "Teto"):
            Claude("claude-opus-5-5", cliente=ClienteFalso(resposta()), orcamento=orcamento).json("s", "u", ESQUEMA_JUIZ, "juiz")

    def test_reader_and_judge_split_and_share_calls(self):
        from coerencia.modelo import Dupla
        leitor_cliente, juiz_cliente = ClienteFalso(resposta()), ClienteFalso(resposta())
        dupla = Dupla(Claude("claude-sonnet-5-5", cliente=leitor_cliente), Claude("claude-opus-5-5", cliente=juiz_cliente))
        dupla.json("s", "u", ESQUEMA_JUIZ, "cena 1")
        dupla.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertEqual((len(leitor_cliente.pedidos), len(juiz_cliente.pedidos)), (1, 1))
        self.assertEqual(len(dupla.chamadas), 2)
        self.assertEqual(dupla.modelo, "claude-sonnet-5-5+claude-opus-5-5")

    def test_spending_cap_stops_before_next_call(self):
        from coerencia.modelo import Orcamento
        cliente = ClienteFalso(resposta())
        modelo = Claude("claude-opus-5-5", cliente=cliente, orcamento=Orcamento(0.005))
        modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")  # custa ~US$ 0,008
        with self.assertRaisesRegex(ErroModelo, "Teto"):
            modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 2")
        self.assertEqual(len(cliente.pedidos), 1)

    def test_model_name_selects_backend(self):
        self.assertEqual(type(criar_modelo("qwen3.5:9b")).__name__, "Ollama")


if __name__ == "__main__":
    unittest.main()
