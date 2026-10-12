"""Validador V5 (experimental, API da OpenAI): cliente, contrato, orçamento, persistência isolada e privacidade.
Transporte simulado; nenhum teste usa a rede e todo texto é sintético."""
from copy import deepcopy
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fonte import validador_v4 as v4
from fonte import validador_v4_1 as v41
from fonte import validador_v5 as v5
import test_validador_v4_1 as T

CHAVE = "sk-teste-NAO-PODE-APARECER-0123456789"


def resposta(corpo, uso=None, status="completed", modelo=v5.MODELO, ident="resp_1", saida_extra=None, motivo=None):
    uso = uso or {"input_tokens": 3000, "input_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 500},
                  "output_tokens": 800, "output_tokens_details": {"reasoning_tokens": 300}}
    itens = [{"type": "reasoning", "id": "rs_1", "summary": []}]
    itens.append({"type": "message", "content": saida_extra or [{"type": "output_text", "text": json.dumps(corpo)}]})
    d = {"id": ident, "model": modelo, "status": status, "output": itens, "usage": uso}
    if motivo:
        d["incomplete_details"] = {"reason": motivo}
    return 200, d, {"x-request-id": "req_hdr"}


class Transporte:
    def __init__(self, *respostas, fn=None):
        self.respostas, self.fn, self.chamadas = list(respostas), fn, []

    def __call__(self, metodo, caminho, corpo=None):
        self.chamadas.append((metodo, caminho, deepcopy(corpo)))
        if metodo == "GET":
            return 200, {"id": v5.MODELO}, {}
        if self.fn:
            return self.fn(corpo)
        return self.respostas.pop(0) if self.respostas else resposta({"avaliacoes": []})


def avaliacoes(corpo_usuario, mapa=None):
    return {"avaliacoes": [T.base(i, corpo_usuario, **(mapa or {}).get(i, {})) for i in T.ids_do(corpo_usuario)]}


def por_entrada(mapa=None, uso=None):
    return lambda corpo: resposta(avaliacoes(corpo["input"], mapa), uso)


class ClienteTests(unittest.TestCase):
    def test_request_follows_the_responses_contract_and_carries_no_secret(self):
        t = Transporte(resposta({"x": 1}))
        c = v5.OpenAI(transporte=t)
        self.assertEqual(c.json("sistema", "usuario", v5.ESQUEMA, "etapa", max_saida=14000), {"x": 1})
        metodo, caminho, corpo = t.chamadas[0]
        self.assertEqual((metodo, caminho), ("POST", "/v1/responses"))
        self.assertEqual((corpo["model"], corpo["reasoning"], corpo["max_output_tokens"], corpo["store"]),
                         ("gpt-6.1-sol", {"effort": "medium"}, 14000, False))
        formato = corpo["text"]["format"]
        self.assertEqual((formato["type"], formato["strict"]), ("json_schema", True))
        self.assertNotIn("temperature", corpo)
        self.assertEqual((corpo["instructions"], corpo["input"]), ("sistema", "usuario"))
        self.assertNotIn("sk-", json.dumps(corpo))

        def fechado(no):
            if isinstance(no, dict):
                if no.get("type") == "object":
                    self.assertIs(no["additionalProperties"], False)
                    self.assertEqual(set(no["required"]), set(no["properties"]))
                for v in no.values():
                    fechado(v)
            elif isinstance(no, list):
                for v in no:
                    fechado(v)
        fechado(formato["schema"])

    def test_editorial_contract_is_the_v4_1_one(self):
        self.assertIs(v5.SISTEMA, v41.SISTEMA)

        def sem_fechamento(no):
            if isinstance(no, dict):
                return {k: sem_fechamento(v) for k, v in no.items() if k != "additionalProperties"}
            return [sem_fechamento(v) for v in no] if isinstance(no, list) else no
        self.assertEqual(sem_fechamento(v5.ESQUEMA), sem_fechamento(v41.ESQUEMA))
        self.assertEqual(v5.configuracao()["contrato_editorial"], f"v4.1:{v41.VERSAO_PROMPT}.{v41.VERSAO_CONTRATO}")

    def test_usage_is_recorded_separately_and_cost_follows_the_price_table(self):
        t = Transporte(resposta({"x": 1}))
        c = v5.OpenAI(transporte=t)
        c.json("s", "u", v5.ESQUEMA, "etapa")
        x = c.chamadas[0]
        self.assertEqual((x["tokens_entrada"], x["tokens_cache"], x["tokens_cache_escrita"], x["tokens_saida"],
                          x["tokens_raciocinio"]), (3000, 1000, 500, 800, 300))
        esperado = (1500 * 2.00 + 500 * 2.50 + 1000 * 0.10 + 800 * 10.00) / 1e6
        self.assertAlmostEqual(x["custo_usd"], round(esperado, 6))
        self.assertEqual((x["modelo_usado"], x["pedido"]), ("gpt-6.1-sol", "resp_1"))

    def test_refusal_truncation_failure_and_bad_credentials(self):
        from coerencia.modelo import ErroModelo, Recusa, RespostaCortada
        recusa = resposta(None, saida_extra=[{"type": "refusal", "refusal": "Não posso."}])
        with self.assertRaises(Recusa):
            v5.OpenAI(transporte=Transporte(recusa)).json("s", "u", v5.ESQUEMA, "e")
        cortada = resposta(None, status="incomplete", motivo="max_output_tokens", saida_extra=[])
        c = v5.OpenAI(transporte=Transporte(cortada))
        with self.assertRaises(RespostaCortada):
            c.json("s", "u", v5.ESQUEMA, "e")
        self.assertGreater(c.chamadas[0]["custo_usd"], 0)          # o raciocínio gasto é cobrado mesmo assim
        with self.assertRaises(ErroModelo):
            v5.OpenAI(transporte=Transporte(resposta(None, status="failed"))).json("s", "u", v5.ESQUEMA, "e")
        with self.assertRaises(ErroModelo) as erro:
            v5.OpenAI(transporte=Transporte((401, {"error": {"message": f"Incorrect API key {CHAVE}"}}, {}))).json(
                "s", "u", v5.ESQUEMA, "e")
        self.assertNotIn(CHAVE, str(erro.exception))
        with self.assertRaises(ErroModelo):
            v5.OpenAI(transporte=Transporte((200, {"id": "r", "model": "m", "status": "completed",
                                                   "output": [{"type": "message", "content": [
                                                       {"type": "output_text", "text": "não é json"}]}], "usage": {}}, {}))
                      ).json("s", "u", v5.ESQUEMA, "e")

    def test_mandatory_budget_blocks_before_sending_and_counts_every_attempt(self):
        from coerencia.modelo import Orcamento, TetoAtingido
        t = Transporte(resposta({"x": 1}))
        c = v5.OpenAI(transporte=t, orcamento=Orcamento(0.001))
        with self.assertRaises(TetoAtingido):
            c.json("s" * 100, "u" * 100, v5.ESQUEMA, "e", max_saida=14000)
        self.assertEqual(t.chamadas, [])                        # nada saiu
        # 429 duas vezes e depois sucesso: cada tentativa confere o teto de novo
        t2 = Transporte((429, {}, {}), (429, {}, {}), resposta({"x": 1}))
        c2 = v5.OpenAI(transporte=t2, orcamento=Orcamento(5.0))
        c2.espera = lambda s: None
        self.assertEqual(c2.json("s", "u", v5.ESQUEMA, "e"), {"x": 1})
        self.assertEqual(len([x for x in t2.chamadas if x[0] == "POST"]), 3)
        self.assertEqual(len(c2.chamadas), 1)                    # só a que respondeu foi cobrada
        t3 = Transporte((503, {}, {}), (503, {}, {}), (503, {}, {}))
        c3 = v5.OpenAI(transporte=t3)
        c3.espera = lambda s: None
        from coerencia.modelo import ErroModelo
        with self.assertRaises(ErroModelo):
            c3.json("s", "u", v5.ESQUEMA, "e")

    def test_timeout_is_charged_at_worst_case(self):
        from coerencia.modelo import ErroModelo, Orcamento

        def estoura(corpo):
            raise TimeoutError("x")
        o = Orcamento(5.0)
        c = v5.OpenAI(transporte=Transporte(fn=estoura), orcamento=o)
        with self.assertRaises(ErroModelo):
            c.json("s", "u", v5.ESQUEMA, "e")
        self.assertTrue(c.chamadas[0]["presumido"])
        self.assertGreater(o.gasto, 0)

    def test_missing_key_never_reaches_the_network(self):
        from coerencia.modelo import ErroModelo
        with mock.patch.object(v5, "chave_da_api", return_value=None), self.assertRaises(ErroModelo):
            v5.OpenAI()


class ExecucaoTests(unittest.TestCase):
    def cenario(self):
        b = T.livro()
        f = [T.alerta(b, 5, "estava"), T.alerta(b, 45, "Joel", "Contradição narrativa", "O grupo tinha três pessoas.")]
        return b, f, {f[0]["id"]: "Estilo do autor", f[1]["id"]: "Falso positivo"}

    def rodar(self, b, f, dec, pasta, mapa=None, transporte=None, teto=5.0, **kw):
        t = transporte or Transporte(fn=por_entrada(mapa))
        r = v5.avaliar(b, f, dec, pasta=pasta, teto=teto, transporte=t, **kw)
        return (*r, t)

    def test_same_prompt_as_v4_1_and_no_previous_verdict_reaches_the_model(self):
        b, f, dec = self.cenario()
        itens41 = v41.preparar(b, f, dec)[0]
        esperado = [v4.pedido(l, b, {i["id"]: i["antecedentes"] for i in l if i.get("antecedentes")})[0]
                    for l in v4.lotes(itens41, b)]
        with TemporaryDirectory() as pasta:
            _, _, _, t = self.rodar(b, f, dec, pasta)
        enviados = [c[2]["input"] for c in t.chamadas if c[0] == "POST"]
        self.assertEqual(enviados, esperado)                       # texto idêntico ao que a V4.1 envia
        tudo = json.dumps([c[2] for c in t.chamadas if c[0] == "POST"], ensure_ascii=False)
        for proibido in ("Sonnet", "Opus", "Haiku", "Claude", "Anthropic", "V3", "V4", "V4.1", "veredito"):
            self.assertNotIn(proibido, tudo, proibido)
        self.assertEqual({c[2]["instructions"] for c in t.chamadas if c[0] == "POST"}, {v41.SISTEMA})

    def test_output_limit_follows_the_contract_and_incomplete_batches_are_split(self):
        b, f, dec = self.cenario()
        limites = []

        def fn(corpo):
            limites.append(corpo["max_output_tokens"])
            if len(T.ids_do(corpo["input"])) > 1:                  # o raciocínio esgota o limite do lote
                return resposta(None, status="incomplete", motivo="max_output_tokens", saida_extra=[])
            return resposta(avaliacoes(corpo["input"]))
        with TemporaryDirectory() as pasta:
            r, _, resumo, t = self.rodar(b, f, dec, pasta, transporte=Transporte(fn=fn))
        self.assertEqual(limites, [v5.limite_de_saida(2), v5.limite_de_saida(1), v5.limite_de_saida(1)])
        self.assertEqual((resumo["analisadas_agora"], resumo["sem_resposta"]), (2, 0))

    def test_reasoning_cache_and_cost_are_aggregated_separately(self):
        b, f, dec = self.cenario()
        with TemporaryDirectory() as pasta:
            _, _, resumo, _ = self.rodar(b, f, dec, pasta)
            estado = json.loads((Path(pasta) / v5.ARQUIVO).read_text(encoding="utf-8"))
        self.assertEqual((resumo["tokens_entrada"], resumo["tokens_cache"], resumo["tokens_cache_escrita"],
                          resumo["tokens_saida"], resumo["tokens_raciocinio"]), (3000, 1000, 500, 800, 300))
        self.assertEqual(resumo["modelos_servidos"], ["gpt-6.1-sol"])
        self.assertAlmostEqual(resumo["custo_usd"], 0.01235, places=5)   # (1500·2 + 500·2,5 + 1000·0,1 + 800·10) / 1e6
        self.assertEqual(estado["meta"]["pedidos"][0]["tokens_raciocinio"], 300)
        self.assertEqual(estado["meta"]["pedidos"][0]["limite_de_saida"], v5.limite_de_saida(2))

    def test_persistence_is_isolated_from_v4_and_v4_1_and_reused_without_calls(self):
        b, f, dec = self.cenario()
        ident = f[0]["id"]
        with TemporaryDirectory() as pasta:
            v4.gravar(pasta, {ident: {"id": ident, "estado": "contestada", "estado_validacao": "analisada",
                                      "chave_conteudo": "x", "chave_configuracao": "y"}})
            v41.gravar(pasta, {ident: {"id": ident, "estado": "mantida", "estado_validacao": "analisada",
                                       "chave_conteudo": "x", "chave_configuracao": "y"}})
            antes = [(Path(pasta) / n).read_bytes() for n in (v4.ARQUIVO, v41.ARQUIVO)]
            _, _, r1, t1 = self.rodar(b, f, dec, pasta)
            self.assertEqual((r1["reutilizadas_sem_custo"], len([c for c in t1.chamadas if c[0] == "POST"])), (0, 1))
            self.assertEqual([(Path(pasta) / n).read_bytes() for n in (v4.ARQUIVO, v41.ARQUIVO)], antes)
            _, _, r2, t2 = self.rodar(b, f, dec, pasta)
            self.assertEqual((r2["reutilizadas_sem_custo"], [c for c in t2.chamadas if c[0] == "POST"]), (2, []))
            plano = v5.planejar(b, f, dec, pasta, modelo=v5.MODELO, esforco="high")
            self.assertEqual(plano["situacoes"], {"desatualizada_configuracao": 2})   # esforço mudou: sem reprocesso
            with v5.trava(pasta):
                with self.assertRaises(v4.ValidacaoEmAndamento):
                    v5.avaliar(b, f, dec, pasta=pasta, teto=1, transporte=Transporte())

    def test_budget_stop_is_partial_and_resumable(self):
        from coerencia.modelo import TetoAtingido
        b = T.livro()
        f = [T.alerta(b, n, "neutro", "Regência") for n in (8, 10, 50)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        with TemporaryDirectory() as pasta, mock.patch.object(v4, "LOTE", (1, 9000)):
            n = {"v": 0}

            def fn(corpo):
                n["v"] += 1
                if n["v"] == 2:
                    raise_ = TetoAtingido("Teto de gasto atingido.")
                    raise raise_
                return resposta(avaliacoes(corpo["input"]))
            _, avisos, resumo, _ = self.rodar(b, f, dec, pasta, transporte=Transporte(fn=fn))
            self.assertTrue(resumo["interrompida"])
            self.assertEqual((resumo["analisadas_agora"], resumo["sem_resposta"]), (1, 2))
            _, _, r2, _ = self.rodar(b, f, dec, pasta)
            self.assertEqual((r2["reutilizadas_sem_custo"], r2["analisadas_agora"]), (1, 2))

    def test_estimate_scenarios_and_budget_floor_need_no_network(self):
        b = T.livro()
        f = [T.alerta(b, n, "neutro", "Regência") for n in (8, 10, 42, 50)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        e = v5.estimar(b, f, dec)
        cen = list(e["custo_por_cenario_de_raciocinio_usd"].values())
        self.assertEqual(cen, sorted(cen))
        self.assertLessEqual(cen[-1], e["custo_maximo_primeira_rodada_usd"])
        self.assertGreater(e["teto_minimo_usd"], e["pior_chamada_usd"])
        self.assertEqual(e["chamadas_primeira_rodada"], len(e["limite_de_saida_por_pedido"]))
        self.assertEqual(e["precos_usd_por_milhao"]["saida"], 10.0)

    def test_manuscript_privacy_in_state_logs_and_requests(self):
        b, f, dec = self.cenario()
        with TemporaryDirectory() as pasta:
            _, avisos, resumo, t = self.rodar(b, f, dec, pasta, meta={"documento": "manuscrito.docx"})
            arquivos = "".join(p.read_text(encoding="utf-8") for p in Path(pasta).iterdir() if p.suffix == ".json")
        for bloco in b:
            if len(bloco.text) > 30:
                self.assertNotIn(bloco.text, arquivos)             # nenhum parágrafo no estado nem no registro
        saida = json.dumps(resumo, ensure_ascii=False) + "\n".join(avisos)
        self.assertNotIn(T.ALVO, saida)
        for _, _, corpo in [c for c in t.chamadas if c[0] == "POST"]:
            self.assertIs(corpo["store"], False)                   # a resposta não é retida
            texto = json.dumps(corpo, ensure_ascii=False)
            self.assertNotIn("manuscrito.docx", texto)             # nome do arquivo nunca vai ao modelo
            self.assertNotIn(str(Path.home()), texto)              # nem caminhos pessoais
            self.assertNotIn(CHAVE, texto)

    def test_decisions_manuscript_and_findings_are_untouched(self):
        b, f, dec = self.cenario()
        antes = (deepcopy(f), deepcopy(dec), [x.text for x in b])
        with TemporaryDirectory() as pasta:
            self.rodar(b, f, dec, pasta)
        self.assertEqual((f, dec, [x.text for x in b]), antes)


if __name__ == "__main__":
    unittest.main()
