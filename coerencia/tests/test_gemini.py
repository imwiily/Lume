"""Cliente do Gemini com transporte falso: pedido, custo, teto, pesquisa e falhas. Nada é enviado."""
import json
import os
import unittest
from unittest.mock import patch

from coerencia import modelo as m
from coerencia.analise import ESQUEMA_JUIZ
from coerencia.modelo import Gemini, ErroModelo, Orcamento, Recusa, RespostaCortada, TetoAtingido, criar_modelo

USO = {"total_input_tokens": 1000, "total_cached_tokens": 400, "total_output_tokens": 200, "total_thought_tokens": 300}


def interacao(texto='{"contradicao": true, "confianca": "alta", "explicacao": "x"}', status="completed", uso=USO, extra=()):
    passos = [*extra, {"type": "model_output", "content": [{"type": "text", "text": texto}]}] if texto is not None else []
    return {"id": "int_1", "model": "gemini-3.8-flash", "status": status, "steps": passos, "usage": uso}


class Transporte:
    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def __call__(self, metodo, caminho, corpo=None):
        self.pedidos.append((metodo, caminho, corpo))
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def cliente(*respostas, **opcoes):
    c = Gemini(transporte=Transporte(*respostas), **opcoes)
    c.espera = lambda _: None
    return c


class GeminiTests(unittest.TestCase):
    def test_request_is_stored_false_structured_and_without_search(self):
        c = cliente((200, interacao()), esforco="xhigh")
        self.assertTrue(c.json("sistema", "usuario", ESQUEMA_JUIZ, "juiz 1")["contradicao"])
        metodo, caminho, corpo = c.transporte.pedidos[0]
        self.assertEqual((metodo, caminho), ("POST", "/v1beta/interactions"))
        self.assertIs(corpo["store"], False)
        self.assertNotIn("tools", corpo)  # pesquisa desligada por padrão
        self.assertEqual(corpo["system_instruction"], "sistema")
        self.assertEqual(corpo["generation_config"]["thinking_level"], "high")
        self.assertEqual(corpo["response_format"]["mime_type"], "application/json")
        self.assertIs(corpo["response_format"]["schema"]["additionalProperties"], False)

    def test_usage_and_cost_come_from_returned_usage(self):
        c = cliente((200, interacao()))
        c.json("s", "u", ESQUEMA_JUIZ, "juiz 1")
        x = c.chamadas[0]
        self.assertEqual((x["tokens_entrada"], x["tokens_cache"], x["tokens_saida"], x["tokens_raciocinio"]), (1000, 400, 200, 300))
        # 600 × 1,50 + 400 × 0,15 + (200 + 300) × 7,50, por milhão; sem preço promocional nem tarifa da Anthropic
        self.assertAlmostEqual(x["custo_usd"], (600 * 1.5 + 400 * .15 + 500 * 7.5) / 1e6, places=6)

    def test_invalid_json_cut_refusal_and_auth_are_safe_errors(self):
        with self.assertRaises(ErroModelo):
            cliente((200, interacao("{não é json"))).json("s", "u", ESQUEMA_JUIZ, "e")
        with self.assertRaises(RespostaCortada):
            cliente((200, interacao(status="incomplete"))).json("s", "u", ESQUEMA_JUIZ, "e")
        with self.assertRaises(Recusa):
            cliente((200, interacao(None))).json("s", "u", ESQUEMA_JUIZ, "e")
        with self.assertRaises(ErroModelo) as erro:
            cliente((403, {})).json("s", "u", ESQUEMA_JUIZ, "e")
        self.assertIn("inválida", str(erro.exception))

    def test_budget_blocks_before_sending(self):
        c = cliente(orcamento=Orcamento(0.0))
        with self.assertRaises(TetoAtingido):
            c.json("s", "u", ESQUEMA_JUIZ, "e")
        self.assertEqual(c.transporte.pedidos, [])

    def test_timeout_is_never_retried_and_counts_worst_case(self):
        c = cliente(TimeoutError("t"), (200, interacao()), orcamento=Orcamento(5.0))
        with self.assertRaises(ErroModelo):
            c.json("s", "u", ESQUEMA_JUIZ, "e")
        self.assertEqual(len(c.transporte.pedidos), 1)
        self.assertTrue(c.chamadas[0]["presumido"])
        self.assertGreater(c.orcamento.gasto, 0.1)

    def test_server_error_is_not_retried_but_rate_limit_is(self):
        c = cliente((503, {}), (200, interacao()))
        with self.assertRaises(ErroModelo):
            c.json("s", "u", ESQUEMA_JUIZ, "e")
        self.assertEqual(len(c.transporte.pedidos), 1)
        c = cliente((429, {}), (200, interacao()))
        self.assertTrue(c.json("s", "u", ESQUEMA_JUIZ, "e"))
        self.assertEqual(len(c.transporte.pedidos), 2)

    def test_search_is_separate_cites_only_real_sources_and_bills_queries(self):
        resposta = interacao("A regra é X.", uso=dict(USO, grounding_tool_count=[{"type": "google_search", "count": 2}]), extra=[
            {"type": "google_search_call", "arguments": {"queries": ["regra de crase", "crase antes de verbo"]}}])
        resposta["steps"][-1]["content"][0]["annotations"] = [
            {"type": "url_citation", "url": "https://exemplo.org/a", "title": "A"},
            {"type": "url_citation", "url": "https://exemplo.org/a", "title": "A"}]
        c = cliente((200, resposta))
        saida = c.pesquisar("sistema", "Quando se usa crase?", "pesquisa")
        self.assertEqual(c.transporte.pedidos[0][2]["tools"], [{"type": "google_search"}])
        self.assertEqual(saida["consultas"], ["regra de crase", "crase antes de verbo"])
        self.assertEqual(saida["fontes"], [{"titulo": "A", "url": "https://exemplo.org/a"}])
        self.assertEqual(saida["buscas"], 2)
        self.assertAlmostEqual(saida["custo_usd"], (600 * 1.5 + 400 * .15 + 500 * 7.5) / 1e6 + 2 * .014, places=6)

    def test_search_with_unknown_usage_is_never_free(self):
        c = cliente((200, interacao("x")))
        saida = c.pesquisar("s", "pergunta", "pesquisa")
        self.assertEqual(saida["buscas"], m.BUSCAS_MAXIMAS)
        self.assertEqual(saida["fontes"], [])  # nada de referência inventada
        self.assertTrue(c.chamadas[0]["buscas_presumidas"])

    def test_search_reserves_worst_case_in_the_cap(self):
        c = cliente(orcamento=Orcamento(.05))  # cobre o texto, não as 5 consultas (US$ 0,07)
        with self.assertRaises(TetoAtingido):
            c.pesquisar("s", "pergunta", "pesquisa")
        self.assertEqual(c.transporte.pedidos, [])

    def test_key_is_gemini_only_and_missing_key_stops(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "g-chave", "ANTHROPIC_API_KEY": "a-chave"}):
            self.assertEqual(m.chave_gemini(), "g-chave")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "a-chave"}, clear=True), patch.object(m.subprocess, "run", side_effect=OSError):
            self.assertIsNone(m.chave_gemini())
            with self.assertRaises(ErroModelo):
                Gemini()

    def test_factory_selects_provider_by_model_name(self):
        with patch.object(m, "chave_gemini", return_value="g"):
            self.assertIsInstance(criar_modelo("gemini-3.8-flash", teto=1.0), Gemini)
        self.assertEqual(m.tarifa("gemini-3.8-flash"), (1.5, 1.5, .15, 7.5))
        self.assertEqual(m.tarifa("claude-opus-5-5")[:1], (4.0,))  # a tabela da Anthropic continua igual

    def test_verify_does_not_spend_tokens(self):
        c = cliente((200, {"name": "models/gemini-3.8-flash"}))
        c.verificar()
        self.assertEqual(c.transporte.pedidos[0][0], "GET")
        with self.assertRaises(ErroModelo):
            cliente((404, {})).verificar()


if __name__ == "__main__":
    unittest.main()
