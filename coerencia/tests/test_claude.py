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


class Haiku55Tests(unittest.TestCase):
    """Experimento: claude-haiku-5-5 (nada é enviado; cliente falso)."""
    MODELO = "claude-haiku-5-5"

    def resposta(self, entrada=1000, cache=0, criacao=0, saida=200, modelo="claude-haiku-5-5", **kw):
        r = resposta(**kw)
        r.usage = SimpleNamespace(input_tokens=entrada, cache_read_input_tokens=cache,
                                  cache_creation_input_tokens=criacao, output_tokens=saida)
        r.model = modelo
        return r

    def test_request_has_effort_but_no_fallback_beta_or_sampling(self):
        cliente = ClienteFalso(self.resposta())
        Claude(self.MODELO, esforco="high", cliente=cliente).json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        pedido = cliente.pedidos[0]
        self.assertEqual((pedido["model"], pedido["output_config"]["effort"]), (self.MODELO, "high"))
        for campo in ("fallbacks", "betas", "temperature", "top_p", "top_k", "thinking"):
            self.assertNotIn(campo, pedido)
        self.assertIs(pedido["output_config"]["format"]["schema"]["additionalProperties"], False)

    def test_uses_plain_messages_endpoint(self):
        cliente = ClienteFalso(self.resposta())
        cliente.beta.messages.create = lambda **_: self.fail("Haiku 5.5 não usa o endpoint beta")
        Claude(self.MODELO, cliente=cliente).json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertEqual(len(cliente.pedidos), 1)

    def test_price_tier_switches_above_100k_prompt_tokens(self):
        modelo = Claude(self.MODELO, cliente=ClienteFalso(self.resposta()))
        self.assertEqual(modelo.tarifa(100_000), (0.10, 0.125, 0.01, 0.50))
        self.assertEqual(modelo.tarifa(100_001), (0.50, 0.625, 0.05, 2.50))

    def test_cost_counts_cache_read_and_creation_and_tier(self):
        # 50k normais + 30k lidos do cache + 10k criados + 2k de saída; total 90k: faixa curta.
        curta = Claude(self.MODELO, cliente=ClienteFalso(self.resposta(50_000, 30_000, 10_000, 2_000)))
        curta.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        c = curta.chamadas[0]
        self.assertEqual((c["tokens_entrada"], c["tokens_cache"], c["tokens_cache_criacao"]), (90_000, 30_000, 10_000))
        self.assertAlmostEqual(c["custo_usd"], (50_000 * .10 + 30_000 * .01 + 10_000 * .125 + 2_000 * .50) / 1e6)
        # 120k no total: faixa longa para tudo.
        longa = Claude(self.MODELO, cliente=ClienteFalso(self.resposta(80_000, 30_000, 10_000, 2_000)))
        longa.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertAlmostEqual(longa.chamadas[0]["custo_usd"],
                               (80_000 * .50 + 30_000 * .05 + 10_000 * .625 + 2_000 * 2.50) / 1e6)

    def test_other_model_answering_is_an_error_not_a_silent_fallback(self):
        modelo = Claude(self.MODELO, cliente=ClienteFalso(self.resposta(modelo="claude-sonnet-5-5")))
        with self.assertRaisesRegex(ErroModelo, "Sem substituição silenciosa"):
            modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertEqual(modelo.chamadas[0]["modelo_usado"], "claude-sonnet-5-5")  # o gasto fica registrado

    def test_empty_invalid_and_refused_answers_are_errors(self):
        for texto in ("", "não é json"):
            with self.subTest(texto=texto), self.assertRaises(ErroModelo):
                Claude(self.MODELO, cliente=ClienteFalso(self.resposta(texto=texto))).json("s", "u", ESQUEMA_JUIZ, "j")
        from coerencia.modelo import Recusa, RespostaCortada
        for motivo, classe in (("refusal", Recusa), ("max_tokens", RespostaCortada)):
            with self.subTest(motivo=motivo), self.assertRaises(classe):
                Claude(self.MODELO, cliente=ClienteFalso(self.resposta(motivo=motivo))).json("s", "u", ESQUEMA_JUIZ, "j")

    def test_api_errors_become_modelo_errors(self):
        import anthropic
        import httpx
        resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))

        class Limitado:
            messages = SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(
                anthropic.RateLimitError("limite", response=resp, body=None)))
        with self.assertRaisesRegex(ErroModelo, "Limite de uso"):
            Claude(self.MODELO, cliente=Limitado()).json("s", "u", ESQUEMA_JUIZ, "juiz 1")

    def test_cap_accounts_for_worst_case_of_the_call_itself(self):
        from coerencia.modelo import Orcamento, TetoAtingido
        cliente = ClienteFalso(self.resposta())
        modelo = Claude(self.MODELO, cliente=cliente, orcamento=Orcamento(0.005))
        # max_tokens 16000 × US$ 0,50/M = US$ 0,008 > teto, mesmo com gasto zero.
        with self.assertRaises(TetoAtingido):
            modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertEqual(cliente.pedidos, [])

    def test_estimate_does_not_create_client(self):
        from unittest.mock import patch
        from coerencia.leitura import Paragrafo
        from coerencia.projeto import Projeto
        import tempfile
        with patch("anthropic.Anthropic", side_effect=AssertionError("cliente criado")):
            with tempfile.TemporaryDirectory() as pasta:
                texto = [Paragrafo(1, "Capítulo 1", "Capítulo 1", True), Paragrafo(2, "A casa era azul.", "Capítulo 1", False)]
                self.assertIn("a_enviar", Projeto(pasta).estimar(texto, self.MODELO))

    def test_existing_models_keep_their_requests_and_cost(self):
        cliente = ClienteFalso(self.resposta(modelo="claude-opus-5-5"))
        modelo = Claude("claude-opus-5-5", cliente=cliente)
        modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        self.assertEqual(cliente.pedidos[0]["fallbacks"], "default")
        self.assertAlmostEqual(modelo.chamadas[0]["custo_usd"], (1000 * 4 + 0 + 200 * 20) / 1e6)


class OrcamentoGlobalTests(unittest.TestCase):
    """Orçamento acumulado entre execuções e contabilidade completa de cache (experimento)."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.pasta = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.pasta.name) / "orcamento.json"

    def tearDown(self):
        self.pasta.cleanup()

    def uso(self, modelo, entrada=1000, cache=0, criacao=0, saida=100):
        r = resposta()
        r.usage = SimpleNamespace(input_tokens=entrada, cache_read_input_tokens=cache,
                                  cache_creation_input_tokens=criacao, output_tokens=saida)
        r.model = modelo
        return r

    def test_sonnet_and_opus_cost_include_cache_write_only_under_global_budget(self):
        from coerencia.modelo import OrcamentoGlobal
        for modelo, normal, escrita, leitura, saida in (("claude-sonnet-5-5", 2, 2.5, .10, 10), ("claude-opus-5-5", 4, 5, .20, 20)):
            with self.subTest(modelo=modelo):
                r = self.uso(modelo, 1000, 500, 300, 100)
                estavel = Claude(modelo, cliente=ClienteFalso(r))
                estavel.json("s", "u", ESQUEMA_JUIZ, "j")
                antigo = estavel.chamadas[0]["custo_usd"]
                glob = Claude(modelo, cliente=ClienteFalso(r), orcamento=OrcamentoGlobal(1, self.arquivo, .5))
                glob.json("s", "u", ESQUEMA_JUIZ, "j")
                esperado = (1000 * normal + 500 * leitura + 300 * escrita + 100 * saida) / 1e6
                self.assertAlmostEqual(glob.chamadas[0]["custo_usd"], esperado)
                self.assertNotAlmostEqual(antigo, esperado)  # sem orçamento global: cálculo estável intacto

    def test_ledger_is_shared_and_blocks_next_call_without_sending(self):
        from coerencia.modelo import OrcamentoGlobal, TetoAtingido
        c1 = ClienteFalso(self.uso("claude-haiku-5-5"))
        Claude("claude-haiku-5-5", cliente=c1, orcamento=OrcamentoGlobal(1, self.arquivo, .5)).json("s", "u", ESQUEMA_JUIZ, "j")
        gasto = OrcamentoGlobal(1, self.arquivo, .5).gasto_global()
        self.assertGreater(gasto, 0)
        # Outra "execução" com limite que mal cobre o gasto: o pior caso (16000 × 0,50/M) não cabe.
        c2 = ClienteFalso(self.uso("claude-haiku-5-5"))
        with self.assertRaisesRegex(TetoAtingido, "Nada foi enviado"):
            Claude("claude-haiku-5-5", cliente=c2,
                   orcamento=OrcamentoGlobal(1, self.arquivo, gasto + .001)).json("s", "u", ESQUEMA_JUIZ, "j")
        self.assertEqual(c2.pedidos, [])
        registro = OrcamentoGlobal(1, self.arquivo, .5)._ler()["chamadas"][0]
        self.assertEqual((registro["modelo_pedido"], registro["modelo_usado"]), ("claude-haiku-5-5", "claude-haiku-5-5"))

    def test_local_cap_still_applies_and_worst_case_does_not_block_it(self):
        from coerencia.modelo import OrcamentoGlobal, TetoAtingido
        cliente = ClienteFalso(self.uso("claude-opus-5-5"))
        orc = OrcamentoGlobal(0.0001, self.arquivo, 5)
        modelo = Claude("claude-opus-5-5", cliente=cliente, orcamento=orc)
        modelo.json("s", "u", ESQUEMA_JUIZ, "j")  # pior caso (US$ 0,32) cabe nos US$ 5 globais; teto local ainda não batido
        with self.assertRaisesRegex(TetoAtingido, "execução"):
            modelo.json("s", "u", ESQUEMA_JUIZ, "j")


if __name__ == "__main__":
    unittest.main()
