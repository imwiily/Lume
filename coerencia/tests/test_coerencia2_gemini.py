"""Coerência 2.0 com o Gemini: uma única requisição, teto, estimativa e uso. Transporte falso; nada é enviado."""
import unittest

from coerencia.leitura import Paragrafo
from coerencia.modelo import ErroModelo, Orcamento, TetoAtingido
from coerencia2 import auditoria as aud
from coerencia2.uma_requisicao import UmaRequisicaoGemini, criar_uma_requisicao
from test_gemini import Transporte, interacao

PARAGRAFOS = [Paragrafo(1, "Capítulo 1", "Capítulo 1", True),
              Paragrafo(2, "A ponte caiu na noite anterior e ninguém passou.", "Capítulo 1", False),
              Paragrafo(3, "No dia seguinte o caminhão de entregas chegou pela ponte.", "Capítulo 1", False)]
RESPOSTA = {"apontamentos": [], "fenomenos_descartados": []}


def gemini(*respostas, **opcoes):
    c = UmaRequisicaoGemini(transporte=Transporte(*respostas), max_tokens=opcoes.pop("max_tokens", 8000), **opcoes)
    c.espera = lambda _: None
    return c


class Coerencia2GeminiTests(unittest.TestCase):
    def test_factory_picks_provider_and_estimate_is_local(self):
        self.assertIsInstance(criar_uma_requisicao("gemini-3.8-flash", "medium", 8000, so_tarifa=True), UmaRequisicaoGemini)
        e = aud.estimar(PARAGRAFOS, "gemini-3.8-flash", "medium", max_tokens=8000)
        self.assertEqual(e["provedor"], "google")
        self.assertTrue(e["cabe_em_uma_leitura"])
        self.assertGreater(e["custo_maximo_usd"], 0)
        self.assertEqual(aud.estimar(PARAGRAFOS, "claude-sonnet-5-5", max_tokens=8000)["provedor"], "anthropic")

    def test_one_request_only_even_when_rate_limited(self):
        c = gemini((429, {}), (200, interacao(__import__("json").dumps(RESPOSTA))))
        with self.assertRaises(ErroModelo):
            c.json("s", "u", aud.ESQUEMA, "global")
        self.assertEqual(len(c.transporte.pedidos), 1)
        with self.assertRaisesRegex(ErroModelo, "nova tentativa bloqueada"):
            c.json("s", "u", aud.ESQUEMA, "global")
        self.assertEqual(len(c.transporte.pedidos), 1)

    def test_max_tokens_goes_in_the_request_and_is_validated(self):
        c = gemini((200, interacao(__import__("json").dumps(RESPOSTA))), max_tokens=12000)
        c.json("s", "u", aud.ESQUEMA, "global")
        self.assertEqual(c.transporte.pedidos[0][2]["generation_config"]["max_output_tokens"], 12000)
        with self.assertRaises(ValueError):
            gemini(max_tokens=10)

    def test_audit_runs_records_usage_and_never_raises_on_cap(self):
        c = gemini((200, interacao(__import__("json").dumps(RESPOSTA))), orcamento=Orcamento(5.0))
        r = aud.auditar(PARAGRAFOS, c)
        self.assertEqual((r["chamadas"], r["modelo_solicitado"]), (1, "gemini-3.8-flash"))
        self.assertEqual(r["uso"]["tokens_entrada_sem_cache"], 600)  # 1000 de entrada − 400 em cache
        self.assertGreater(r["custo_usd"], 0)
        barrado = gemini(orcamento=Orcamento(0.0))
        aud.auditar(PARAGRAFOS, barrado)
        self.assertEqual(barrado.transporte.pedidos, [])


if __name__ == "__main__":
    unittest.main()
