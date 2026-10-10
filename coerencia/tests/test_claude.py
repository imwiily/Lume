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
        # Antes (1.7) o teto só olhava o gasto acumulado: a chamada saía mesmo que o pior caso
        # a estourasse. Agora o saldo precisa cobrir o pior caso de cada chamada.
        from coerencia.modelo import Orcamento, TetoAtingido
        cliente = ClienteFalso(resposta())
        modelo = Claude("claude-opus-5-5", cliente=cliente, orcamento=Orcamento(0.80))
        modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 1")  # pior caso ~US$ 0,72; custou ~US$ 0,008
        modelo.orcamento.gasto = 0.40
        with self.assertRaisesRegex(TetoAtingido, "Teto"):
            modelo.json("s", "u", ESQUEMA_JUIZ, "juiz 2")
        self.assertEqual(len(cliente.pedidos), 1)

    def test_model_name_selects_backend(self):
        self.assertEqual(type(criar_modelo("qwen3.5:9b")).__name__, "Ollama")


class FalhaFalsa:
    """Cliente cuja sequência de respostas mistura sucessos e exceções do SDK."""
    def __init__(self, *saidas):
        self.saidas, self.pedidos = list(saidas), []
        criar = self._criar
        self.messages = SimpleNamespace(create=criar)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=criar))

    def _criar(self, **pedido):
        self.pedidos.append(pedido)
        saida = self.saidas.pop(0)
        if isinstance(saida, Exception):
            raise saida
        return saida


def resposta_com(modelo="claude-sonnet-5-5", entrada=1000, leitura=0, escrita=0, saida=200, **extra):
    uso = SimpleNamespace(input_tokens=entrada, cache_read_input_tokens=leitura, cache_creation_input_tokens=escrita,
                          output_tokens=saida, **extra)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"contradicao": false}')], usage=uso,
                           stop_reason="end_turn", model=modelo, _request_id="req_teste")


def erro_http(classe, codigo):
    import httpx
    pedido = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return classe("falha", response=httpx.Response(codigo, request=pedido), body=None)


class OrcamentoTests(unittest.TestCase):
    """Teto de gasto: pior caso antes de enviar, cache, modelo que respondeu e falhas. Sem API."""

    def claude(self, cliente, teto, modelo="claude-sonnet-5-5"):
        from coerencia.modelo import Orcamento
        m = Claude(modelo, cliente=cliente, orcamento=Orcamento(teto))
        m.espera = lambda segundos: None
        return m

    def pior(self, modelo="claude-sonnet-5-5"):
        return Claude(modelo, cliente=ClienteFalso(None)).custo_maximo("s", "u", ESQUEMA_JUIZ, 16000)

    def test_worst_case_above_balance_sends_nothing(self):
        from coerencia.modelo import TetoAtingido
        cliente = ClienteFalso(resposta_com())
        modelo = self.claude(cliente, teto=self.pior() - 0.001)
        with self.assertRaisesRegex(TetoAtingido, "pior caso"):
            modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertEqual((cliente.pedidos, modelo.orcamento.gasto), ([], 0.0))

    def test_within_budget_and_exact_balance_are_sent(self):
        for folga in (1.0, 0.0):
            with self.subTest(folga=folga):
                cliente = ClienteFalso(resposta_com())
                modelo = self.claude(cliente, teto=self.pior() + folga)
                modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
                self.assertEqual(len(cliente.pedidos), 1)
                self.assertAlmostEqual(modelo.orcamento.gasto, (1000 * 2 + 200 * 10) / 1e6)

    def test_cache_write_read_input_and_output_have_their_own_prices(self):
        modelo = Claude("claude-opus-5-5", cliente=ClienteFalso(resposta_com("claude-opus-5-5", 100, 2000, 3000, 50)))
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        c = modelo.chamadas[0]
        self.assertEqual((c["tokens_entrada"], c["tokens_cache"], c["tokens_cache_criacao"]), (5100, 2000, 3000))
        # 100 × 4 + 3000 × 5 (1,25 × entrada) + 2000 × 0,20 + 50 × 20, por milhão
        self.assertAlmostEqual(c["custo_usd"], (400 + 15000 + 400 + 1000) / 1e6)

    def test_official_rates_sonnet_5_5_opus_5_5_and_fallback_targets(self):
        from coerencia.modelo import tarifa
        # (entrada, escrita de cache 5 min, leitura de cache, saída) por milhão — página de preços de 10/10/2026
        self.assertEqual(tarifa("claude-sonnet-5-5"), (2.00, 2.50, 0.10, 10.00))
        self.assertEqual(tarifa("claude-sonnet-5"), (2.00, 2.50, 0.20, 10.00))  # Sonnet 5 não é Sonnet 5.5
        self.assertEqual(tarifa("claude-opus-5-5"), (4.00, 5.00, 0.20, 20.00))
        self.assertEqual(tarifa("claude-opus-5"), (5.00, 6.25, 0.50, 25.00))
        self.assertEqual(tarifa("claude-opus-4-8"), (5.00, 6.25, 0.50, 25.00))
        self.assertEqual(tarifa("claude-fable-5-1"), (10.00, 12.50, 0.25, 50.00))
        self.assertEqual(tarifa("claude-sonnet-5-5-20260928"), tarifa("claude-sonnet-5-5"))  # id datado
        # Modelo desconhecido: maior preço de cada coluna, nunca zero.
        self.assertEqual(tarifa("claude-futuro-9"), (10.00, 12.50, 1.00, 50.00))

    def test_sonnet_5_5_cache_read_is_ten_cents(self):
        modelo = Claude("claude-sonnet-5-5", cliente=ClienteFalso(resposta_com(entrada=100, leitura=10000, escrita=2000, saida=50)))
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        # 100 × 2 + 2000 × 2,50 + 10000 × 0,10 + 50 × 10, por milhão
        self.assertAlmostEqual(modelo.chamadas[0]["custo_usd"], (200 + 5000 + 1000 + 500) / 1e6)

    def test_reserve_covers_declined_first_attempt_plus_most_expensive_fallback(self):
        tentativa = lambda t, saida: (t * saida) / 1e6
        # Texto mínimo: ~10 tokens de entrada; as duas tentativas somam 16000 de saída cada.
        for modelo, primeira in (("claude-sonnet-5-5", 10.0), ("claude-opus-5-5", 20.0)):
            with self.subTest(modelo=modelo):
                pior = Claude(modelo, cliente=ClienteFalso(None)).custo_maximo("", "", {}, 16000)
                minimo = 16000 * (primeira + 25.0) / 1e6  # saída original + saída no destino (US$ 25)
                self.assertGreaterEqual(pior, minimo)
                self.assertLess(pior, minimo + 0.001)  # só a entrada estimada a mais
        sem_retomada = Claude("claude-haiku-4-5", cliente=ClienteFalso(None)).custo_maximo("", "", {}, 16000)
        self.assertLess(sem_retomada, 16000 * 5 / 1e6 + 0.001)

    def test_fallback_bills_declined_attempt_once_and_final_attempt_is_not_duplicated(self):
        recusada = SimpleNamespace(type="message", model="claude-sonnet-5-5", input_tokens=1000, output_tokens=300,
                                   cache_read_input_tokens=0, cache_creation_input_tokens=0)
        final = SimpleNamespace(type="fallback_message", model="claude-opus-5", input_tokens=1000, output_tokens=100,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)
        # O uso de nível superior descreve só a tentativa final, que também consta em `iterations`.
        modelo = Claude("claude-sonnet-5-5", cliente=ClienteFalso(
            resposta_com("claude-opus-5", 1000, saida=100, iterations=[recusada, final])))
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        esperado = (1000 * 2 + 300 * 10) / 1e6 + (1000 * 5 + 100 * 25) / 1e6
        self.assertAlmostEqual(modelo.chamadas[0]["custo_usd"], esperado)
        # Sem `iterations` (resposta comum), vale só o uso final.
        simples = Claude("claude-sonnet-5-5", cliente=ClienteFalso(resposta_com("claude-opus-5", 1000, saida=100)))
        simples.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertAlmostEqual(simples.chamadas[0]["custo_usd"], (1000 * 5 + 100 * 25) / 1e6)

    def test_insufficient_reserve_says_not_sent_and_gives_minimum(self):
        from coerencia.modelo import TetoAtingido
        cliente = ClienteFalso(resposta_com())
        modelo = self.claude(cliente, teto=0.10)
        with self.assertRaises(TetoAtingido) as contexto:
            modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        erro = contexto.exception
        self.assertEqual(cliente.pedidos, [])
        self.assertIn("NÃO foi enviada", str(erro))
        self.assertAlmostEqual(erro.minimo, self.pior())
        self.assertIn(f"{erro.minimo:.2f}", str(erro))

    def test_cost_follows_model_that_answered_and_unknown_model_is_never_free(self):
        pedido = Claude("claude-sonnet-5-5", cliente=ClienteFalso(resposta_com("claude-opus-5", 1000, saida=100)))
        pedido.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertAlmostEqual(pedido.chamadas[0]["custo_usd"], (1000 * 5 + 100 * 25) / 1e6)  # não a tarifa do Sonnet
        desconhecido = Claude("claude-sonnet-5-5", cliente=ClienteFalso(resposta_com("claude-modelo-novo", 1000, saida=100)))
        desconhecido.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertGreater(desconhecido.chamadas[0]["custo_usd"], 0)

    def test_worst_case_reserves_the_most_expensive_fallback(self):
        # Sonnet 5.5 aceita retomada automática: reserva-se a tarifa de saída do destino mais caro.
        self.assertGreater(self.pior("claude-sonnet-5-5"), 16000 * (10 + 25) / 1e6)
        self.assertLess(self.pior("claude-haiku-4-5"), 16000 * 5 / 1e6 + 0.01)  # sem retomada: a própria tarifa

    def test_itemized_attempts_are_summed_at_their_own_model_rate(self):
        tentativas = [SimpleNamespace(model="claude-opus-5-5", input_tokens=1000, output_tokens=0,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0),
                      SimpleNamespace(model="claude-opus-5", input_tokens=1000, output_tokens=100,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0)]
        modelo = Claude("claude-opus-5-5", cliente=ClienteFalso(
            resposta_com("claude-opus-5", 1000, saida=100, iterations=tentativas)))
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertAlmostEqual(modelo.chamadas[0]["custo_usd"], (1000 * 4 + 1000 * 5 + 100 * 25) / 1e6)  # a recusada (Opus 5.5) + a final, sem repetir

    def test_successive_calls_accumulate_until_the_balance_runs_out(self):
        from coerencia.modelo import TetoAtingido
        cliente = ClienteFalso(resposta_com())
        modelo = self.claude(cliente, teto=self.pior() + 0.003)  # cabe a primeira (US$ 0,0044); a segunda, não
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        with self.assertRaises(TetoAtingido):
            modelo.json("s", "u", ESQUEMA_JUIZ, "e2")
        self.assertEqual(len(cliente.pedidos), 1)

    def test_retry_of_unbilled_failures_does_not_charge_and_rechecks(self):
        import anthropic
        cliente = FalhaFalsa(erro_http(anthropic.RateLimitError, 429), erro_http(anthropic.InternalServerError, 529),
                             resposta_com())
        modelo = self.claude(cliente, teto=1.0)
        modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertEqual((len(cliente.pedidos), len(modelo.chamadas)), (3, 1))
        self.assertAlmostEqual(modelo.orcamento.gasto, (1000 * 2 + 200 * 10) / 1e6)

    def test_persistent_failure_stops_after_bounded_attempts_without_charge(self):
        import anthropic
        from coerencia.modelo import ErroModelo
        cliente = FalhaFalsa(*[erro_http(anthropic.InternalServerError, 500)] * 5)
        modelo = self.claude(cliente, teto=1.0)
        with self.assertRaises(ErroModelo):
            modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertEqual((len(cliente.pedidos), modelo.orcamento.gasto), (3, 0.0))

    def test_timeout_may_have_been_billed_so_the_worst_case_is_charged_once(self):
        import anthropic
        import httpx
        from coerencia.modelo import ErroModelo, TetoAtingido
        tempo = anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        cliente = FalhaFalsa(tempo, resposta_com())
        modelo = self.claude(cliente, teto=self.pior() * 1.5)
        with self.assertRaises(ErroModelo):
            modelo.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertEqual(len(cliente.pedidos), 1)  # sem repetição automática
        self.assertAlmostEqual(modelo.orcamento.gasto, self.pior())
        self.assertTrue(modelo.chamadas[0]["presumido"])
        with self.assertRaises(TetoAtingido):  # o resto do teto já não cobre outro pior caso
            modelo.json("s", "u", ESQUEMA_JUIZ, "e2")

    def test_ai_features_share_a_cap_only_through_one_criar_modelo(self):
        # Leitor e juiz de uma mesma execução dividem o teto; Coerência e Auditoria final criam
        # modelos próprios, cada um com o teto declarado para ele (semântica de 1.7, preservada).
        from unittest.mock import patch
        with patch("coerencia.modelo.chave_do_keychain", return_value="chave-de-teste"):
            dupla = criar_modelo("claude-sonnet-5-5", juiz="claude-opus-5-5", teto=0.30)
            outro = criar_modelo("claude-sonnet-5-5", teto=0.30)
        self.assertIs(dupla.leitor.orcamento, dupla.juiz.orcamento)
        self.assertIsNot(dupla.leitor.orcamento, outro.orcamento)

    def test_invalid_or_zero_cap_is_not_unlimited(self):
        from coerencia.modelo import TetoAtingido
        from unittest.mock import patch
        with patch("coerencia.modelo.chave_do_keychain", return_value="chave-de-teste"):
            zero = criar_modelo("claude-sonnet-5-5", teto=0.0)
            for invalido in (-1.0, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    criar_modelo("claude-sonnet-5-5", teto=invalido)
        zero.cliente = ClienteFalso(resposta_com())
        with self.assertRaises(TetoAtingido):
            zero.json("s", "u", ESQUEMA_JUIZ, "e1")
        self.assertEqual(zero.cliente.pedidos, [])

    def test_old_call_records_without_cache_creation_still_priced(self):
        modelo = Claude("claude-opus-5-5", cliente=ClienteFalso(None))
        antigo = {"tokens_entrada": 1500, "tokens_cache": 500, "tokens_saida": 200}  # registro da 1.7
        self.assertAlmostEqual(modelo.custo(antigo), (1000 * 4 + 500 * 0.2 + 200 * 20) / 1e6)

    def test_measured_tokens_tighten_the_character_estimate(self):
        modelo = Claude("claude-sonnet-5-5", cliente=ClienteFalso(resposta_com(entrada=5000)))
        antes = modelo.custo_maximo("x" * 4000, "", ESQUEMA_JUIZ, 1000)
        modelo.json("x" * 4000, "", ESQUEMA_JUIZ, "e1")  # 4000+ caracteres medidos em 5000 tokens (0,8 por token)
        self.assertGreater(modelo.custo_maximo("x" * 4000, "", ESQUEMA_JUIZ, 1000), antes)


if __name__ == "__main__":
    unittest.main()
