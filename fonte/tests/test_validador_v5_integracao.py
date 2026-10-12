"""Integração supervisionada da V5 (Fase 1, backend): seleção, versão, estimativa, execução, resultados e CLI.
Transporte simulado; nenhum teste usa a rede e todo texto é sintético."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fonte import cli
from fonte import validador_v4 as v4
from fonte import validador_v5 as v5
from fonte import validador_v5_integracao as vi
import test_validador_v4_1 as T
import test_validador_v5 as T5

SHA = "a" * 64
OUTRA = "b" * 64
CHAVE = "sk-teste-NAO-PODE-APARECER-9876543210"


def livro():
    return T.livro()


def alerta(b, n, decisao, **extra):
    f = T.alerta(b, n, "neutro", "Regência", "Hipótese do detector.")
    f.setdefault("context", [])
    f.update(extra)
    return f


def evid(n):
    return f"Parágrafo neutro número {n}"


# campos de resposta que produzem cada estado da V5
MANTIDA = lambda n: {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "media",
                     "explicacao": "Desvio objetivo.", "evidencia": evid(n)}
CONTESTADA = MANTIDA
REVISAO = lambda n: {"existe": "sim", "natureza": "interpretativo", "certeza": "discutivel", "gravidade": "baixa",
                     "razao_literaria": "nao_identificada", "explicacao": "Oscilação discutível.", "evidencia": evid(n)}
INADEQUADO = lambda n: {"existe": "nao", "natureza": "nenhuma", "certeza": "nao_se_aplica", "gravidade": "nenhuma",
                        "justificativa_detector": "incorreta", "explicacao": "A forma está correta.", "evidencia": evid(n)}
INCONCLUSIVA = lambda n: {"existe": "incerto", "natureza": "interpretativo", "certeza": "discutivel",
                          "gravidade": "baixa", "evidencia_suficiente": False, "explicacao": "Não decide."}


def cenario():
    b = livro()
    spec = {8: ("Aceito editorialmente", MANTIDA), 10: ("Falso positivo", CONTESTADA), 42: ("Estilo do autor", REVISAO),
            50: ("Falso positivo", INADEQUADO), 56: ("Estilo do autor", INCONCLUSIVA)}
    f = [alerta(b, n, d) for n, (d, _) in spec.items()]
    dec = {x["id"]: spec[x["paragraph"]][0] for x in f}
    mapa = {x["id"]: spec[x["paragraph"]][1](x["paragraph"]) for x in f}
    return b, f, dec, mapa


def run(b, f, dec, ids, pasta, mapa=None, transporte=None, sha=SHA, sha_rel=SHA, **kw):
    t = transporte or T5.Transporte(fn=T5.por_entrada(mapa))
    r = vi.executar(b, f, dec, ids, sha, sha_rel, pasta, transporte=t, **kw)
    return r, t


def posts(t):
    return [c for c in t.chamadas if c[0] == "POST"]


class SelecaoEVersaoTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.mapa = cenario()
        self.ids = [x["id"] for x in self.f]

    def test_only_listed_eligible_ids_are_selected_and_the_rest_is_explained(self):
        dec = dict(self.dec)
        dec[self.ids[0]] = "Pendente"
        dec[self.ids[1]] = "Corrigido"
        aceitas, excl = vi.selecionar(self.f, dec, [self.ids[0], self.ids[1], self.ids[2], "inexistente", self.ids[2]])
        self.assertEqual(list(aceitas), [self.ids[2]])
        self.assertEqual({(e["id"], e["motivo"]) for e in excl},
                         {(self.ids[0], "decisao_nao_elegivel"), (self.ids[1], "decisao_nao_elegivel"),
                          ("inexistente", "id_fora_do_relatorio")})

    def test_empty_oversized_and_invalid_limits_are_refused_never_completed_automatically(self):
        for ids, maximo, codigo in (([], 40, "selecao_vazia"), (self.ids, 3, "itens_demais"), (self.ids, 61, "limite_invalido"),
                                    (self.ids, 0, "limite_invalido")):
            with self.assertRaises(vi.ErroIntegracao) as e:
                vi.selecionar(self.f, self.dec, ids, maximo)
            self.assertEqual(e.exception.codigo, codigo)

    def test_manuscript_version_must_match_or_have_the_recorded_context(self):
        aceitas = {self.ids[0]: self.dec[self.ids[0]]}
        niv, fora = vi.verificar_versao(self.b, self.f, aceitas, SHA, SHA)
        self.assertEqual((niv, fora), ({self.ids[0]: "versao_confere"}, []))
        niv, fora = vi.verificar_versao(self.b, self.f, aceitas, OUTRA, SHA)
        self.assertEqual((niv, fora), ({}, [{"id": self.ids[0], "motivo": "versao_do_manuscrito_diferente"}]))
        # relatório sem SHA nunca vale como versão exata
        self.assertEqual(vi.verificar_versao(self.b, self.f, aceitas, SHA, None)[0], {})
        f = dict(self.f[0])
        n = f["paragraph"]
        por = {x.number: x.text for x in self.b}
        f["context"] = [{"paragraph": n - 1, "text": por[n - 1]}, {"paragraph": n + 1, "text": por[n + 1]}]
        niv, fora = vi.verificar_versao(self.b, [f], aceitas, OUTRA, SHA, permitir_parcial=True)
        self.assertEqual(niv, {self.ids[0]: "contexto_parcial"})
        f["context"] = [{"paragraph": n - 1, "text": "texto que não existe mais"}]
        niv, fora = vi.verificar_versao(self.b, [f], aceitas, OUTRA, SHA, permitir_parcial=True)
        self.assertEqual((niv, fora), ({}, [{"id": self.ids[0], "motivo": "contexto_nao_verificavel"}]))


class EstimativaTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.mapa = cenario()
        self.ids = [x["id"] for x in self.f]

    def test_estimate_needs_no_network_and_writes_nothing(self):
        with TemporaryDirectory() as raiz:
            pasta = Path(raiz) / "novo"
            e = vi.estimar(self.b, self.f, self.dec, self.ids, SHA, SHA, pasta)
            self.assertFalse(pasta.exists())
        self.assertEqual((e["provedor"], e["modelo"], e["esforco"]), ("openai", v5.MODELO, "medium"))
        self.assertEqual((e["aceitas"], len(e["a_enviar"]), e["reutilizadas_sem_custo"]), (5, 5, 0))
        self.assertGreater(e["custo_maximo_usd"], e["custo_esperado_usd"])
        self.assertGreaterEqual(e["teto_usd"], e["teto_minimo_usd"])
        self.assertTrue(e["cabe_no_teto"])
        self.assertFalse(e["segunda_rodada"]["autorizada"])
        self.assertEqual((e["teto_padrao_usd"], e["teto_maximo_usd"]), (1.0, 5.0))
        self.assertNotIn("Parágrafo neutro número", json.dumps(e, ensure_ascii=False))     # sem texto do manuscrito

    def test_ceiling_limits_and_insufficient_ceiling_are_reported(self):
        for teto in (0, -1, 5.01):
            with self.assertRaises(vi.ErroIntegracao) as e:
                vi.estimar(self.b, self.f, self.dec, self.ids, SHA, SHA, None, teto=teto)
            self.assertEqual(e.exception.codigo, "teto_invalido")
        e = vi.estimar(self.b, self.f, self.dec, self.ids, SHA, SHA, None, teto=0.01)
        self.assertFalse(e["cabe_no_teto"])
        self.assertTrue(vi.estimar(self.b, self.f, self.dec, self.ids, SHA, SHA, None, teto=5.0)["cabe_no_teto"])

    def test_estimate_excludes_different_version_and_reports_levels(self):
        e = vi.estimar(self.b, self.f, self.dec, self.ids, OUTRA, SHA, None)
        self.assertEqual((e["aceitas"], e["versao_manuscrito"], len(e["excluidos"])), (0, "diferente", 5))
        self.assertEqual(e["a_enviar"], [])
        self.assertEqual(e["custo_maximo_usd"], 0.0)


class ExecucaoTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.mapa = cenario()
        self.ids = [x["id"] for x in self.f]
        self.por_par = {x["paragraph"]: x["id"] for x in self.f}

    def test_the_five_v5_states_are_presented_separately_and_without_calling_every_contest_an_error(self):
        with TemporaryDirectory() as pasta:
            r, t = run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            res = vi.resultados(self.b, self.f, self.dec, pasta)
        self.assertEqual((r["analisadas_agora"], r["decisoes_alteradas"]), (5, False))
        self.assertGreaterEqual(len(posts(t)), 1)
        por = {x["paragrafo"]: x for x in res["itens"]}
        self.assertEqual({n: por[n]["resultado"] for n in por},
                         {8: "mantida", 10: "contestada", 42: "revisao_recomendada", 50: "apontamento_inadequado", 56: "inconclusiva"})
        for x in res["itens"]:
            self.assertTrue(x["vale_para_o_texto_e_decisao_atuais"])
            self.assertIs(x["sugestao_aplicada_ao_manuscrito"], False)
            self.assertIn("não é confirmação humana", x["aviso"])
            for chave in ("decisao_humana_anterior", "existencia_segundo_a_ia", "adequacao_da_decisao_segundo_a_ia",
                          "resultado", "evidencias_verificadas", "incertezas_e_limitacoes"):
                self.assertIn(chave, x)
            self.assertNotIn("erro", x["rotulo_do_resultado"].lower())
        c = por[10]       # Falso positivo contestado: a IA vê problema onde o autor viu falso positivo
        self.assertEqual((c["decisao_humana_anterior"], c["existencia_segundo_a_ia"]["existe"],
                          c["adequacao_da_decisao_segundo_a_ia"]), ("Falso positivo", "sim", "inadequada"))
        self.assertIn("existe um problema onde você marcou falso positivo", c["significado_da_discordancia"])
        self.assertIsNone(por[8]["significado_da_discordancia"])
        i = por[56]       # inconclusiva: incerteza explícita, sem afirmar problema
        self.assertEqual(i["existencia_segundo_a_ia"]["existe"], "incerto")
        self.assertTrue(any("existe = incerto" in s for s in i["incertezas_e_limitacoes"]))
        self.assertTrue(any("Nenhuma evidência verificada" in s for s in i["incertezas_e_limitacoes"]))
        self.assertIsNone(i["significado_da_discordancia"])

    def test_contest_of_a_confirmed_error_means_the_ia_sees_no_problem_not_a_new_error(self):
        b, f, dec, mapa = cenario()
        ident = self.por_par[8]
        dec[ident] = "Erro confirmado"
        mapa[ident] = INADEQUADO(8)
        mapa[ident]["justificativa_detector"] = "parcial"
        with TemporaryDirectory() as pasta:
            run(b, f, dec, [ident], pasta, mapa)
            x = vi.resultados(b, f, dec, pasta)["itens"][0]
        self.assertEqual((x["resultado"], x["existencia_segundo_a_ia"]["existe"]), ("contestada", "nao"))
        self.assertIn("o problema que você reconheceu não existe", x["significado_da_discordancia"])
        self.assertNotIn("Problema técnico identificado", x["existencia_segundo_a_ia"]["rotulo"])

    def test_only_selected_decisions_run_and_unselected_stay_untouched(self):
        sel = [self.por_par[8], self.por_par[10]]
        with TemporaryDirectory() as pasta:
            r, t = run(self.b, self.f, self.dec, sel, pasta, self.mapa)
            ids_enviados = {i for c in posts(t) for i in T.ids_do(c[2]["input"])}
            estado = json.loads((Path(pasta) / v5.ARQUIVO).read_text(encoding="utf-8"))
        self.assertEqual((ids_enviados, set(estado["itens"])), (set(sel), set(sel)))
        self.assertEqual(r["v5"]["elegiveis"], 2)

    def test_incompatible_version_sends_nothing(self):
        with TemporaryDirectory() as pasta:
            r, t = run(self.b, self.f, self.dec, self.ids, pasta, self.mapa, sha=OUTRA)
            self.assertEqual((r["analisadas_agora"], posts(t), r["v5"]), (0, [], None))
            self.assertEqual(len(r["excluidos"]), 5)
            self.assertFalse((Path(pasta) / v5.ARQUIVO).exists())

    def test_second_round_is_off_by_default_registered_as_pending_and_runs_only_when_authorized(self):
        ident = self.por_par[56]
        mapa = dict(self.mapa)
        mapa[ident] = dict(INCONCLUSIVA(56), precisa_mais_contexto=True, paragrafos_solicitados=[9], termos_solicitados=["chuva"])
        with TemporaryDirectory() as pasta:
            r, t = run(self.b, self.f, self.dec, [ident], pasta, mapa)
            self.assertEqual((len(posts(t)), r["pendencias_de_contexto"], r["segunda_rodada_autorizada"]), (1, 1, False))
            x = vi.resultados(self.b, self.f, self.dec, pasta)["itens"][0]
            self.assertEqual(x["pendencia_de_contexto"]["paragrafos"], [9])
            self.assertTrue(any("segunda rodada não foi autorizada" in s for s in x["incertezas_e_limitacoes"]))
        with TemporaryDirectory() as pasta:
            r, t = run(self.b, self.f, self.dec, [ident], pasta, mapa, autorizar_contexto=True)
            self.assertEqual((len(posts(t)), r["pendencias_de_contexto"]), (2, 0))
            self.assertEqual(vi.resultados(self.b, self.f, self.dec, pasta)["itens"][0]["pendencia_de_contexto"], None)

    def test_valid_results_are_reused_without_calls_and_selective_invalidation_follows_text_and_decision(self):
        with TemporaryDirectory() as pasta:
            run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            r, t = run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            self.assertEqual((r["analisadas_agora"], posts(t)), (0, []))
            self.assertEqual(r["v5"]["reutilizadas_sem_custo"], 5)
            dec = dict(self.dec)
            dec[self.por_par[10]] = "Estilo do autor"          # a decisão mudou: o resultado antigo não vale
            res = vi.resultados(self.b, self.f, dec, pasta)
            situ = {x["paragrafo"]: x["situacao"] for x in res["itens"]}
            self.assertEqual(situ[10], "desatualizada_conteudo")
            self.assertTrue(all(v == "valida" for k, v in situ.items() if k != 10))
            self.assertEqual(res["desatualizadas"], 1)
            r, t = run(self.b, self.f, dec, self.ids, pasta, self.mapa)       # reanálise só do que mudou
            self.assertEqual((r["analisadas_agora"], len(posts(t))), (0, 0))   # desatualizada não é reenviada sozinha

    def test_explicit_reanalysis_keeps_history_and_resends_only_that_item(self):
        alvo = self.por_par[8]
        with TemporaryDirectory() as pasta:
            run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            antes = json.loads((Path(pasta) / v5.ARQUIVO).read_text(encoding="utf-8"))["itens"][alvo]
            r, t = run(self.b, self.f, self.dec, self.ids, pasta, self.mapa, reanalisar=[alvo])
            self.assertEqual((r["reanalisados"], r["analisadas_agora"]), ([alvo], 1))
            self.assertEqual({i for c in posts(t) for i in T.ids_do(c[2]["input"])}, {alvo})
            hist = json.loads((Path(pasta) / vi.HISTORICO).read_text(encoding="utf-8"))["registros"]
            self.assertEqual([h["registro"] for h in hist], [antes])

    def test_ceiling_blocks_before_sending_and_partial_stop_is_resumable(self):
        from coerencia.modelo import TetoAtingido
        with TemporaryDirectory() as pasta:
            t = T5.Transporte(fn=T5.por_entrada(self.mapa))
            with self.assertRaises(vi.ErroIntegracao) as e:
                vi.executar(self.b, self.f, self.dec, self.ids, SHA, SHA, pasta, teto=0.01, transporte=t)
            self.assertEqual(e.exception.codigo, "teto_insuficiente")
            self.assertEqual(posts(t), [])
        with TemporaryDirectory() as pasta, mock.patch.object(v4, "LOTE", (1, 9000)):
            n = {"v": 0}

            def fn(corpo):
                n["v"] += 1
                if n["v"] == 3:
                    raise TetoAtingido("Teto de gasto atingido.")
                return T5.por_entrada(self.mapa)(corpo)
            r, t = run(self.b, self.f, self.dec, self.ids, pasta, transporte=T5.Transporte(fn=fn))
            self.assertTrue(r["v5"]["interrompida"])
            self.assertEqual((r["v5"]["analisadas_agora"], r["v5"]["sem_resposta"]), (2, 3))
            r2, _ = run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            self.assertEqual((r2["v5"]["reutilizadas_sem_custo"], r2["v5"]["analisadas_agora"]), (2, 3))

    def test_cancellation_leaves_no_processing_record_and_keeps_finished_results(self):
        with TemporaryDirectory() as pasta, mock.patch.object(v4, "LOTE", (1, 9000)):
            n = {"v": 0}

            def fn(corpo):
                n["v"] += 1
                if n["v"] == 3:
                    raise KeyboardInterrupt
                return T5.por_entrada(self.mapa)(corpo)
            with self.assertRaises(KeyboardInterrupt):
                run(self.b, self.f, self.dec, self.ids, pasta, transporte=T5.Transporte(fn=fn))
            estado = json.loads((Path(pasta) / v5.ARQUIVO).read_text(encoding="utf-8"))["itens"]
            self.assertEqual(len(estado), 2)
            self.assertFalse(any(x.get("estado_validacao") == "em_processamento" for x in estado.values()))
            self.assertFalse(v5.ocupada(pasta))

    def test_duplicate_execution_is_refused_while_the_lock_is_held(self):
        with TemporaryDirectory() as pasta:
            with v5.trava(pasta):
                with self.assertRaises(vi.ErroIntegracao) as e:
                    run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            self.assertEqual(e.exception.codigo, "em_andamento")

    def test_missing_key_stops_before_any_network_but_estimate_works(self):
        with TemporaryDirectory() as pasta, mock.patch.object(v5, "chave_da_api", return_value=None):
            with self.assertRaises(vi.ErroIntegracao) as e:
                vi.executar(self.b, self.f, self.dec, self.ids, SHA, SHA, pasta)
            self.assertEqual(e.exception.codigo, "chave_ausente")
            self.assertTrue(vi.estimar(self.b, self.f, self.dec, self.ids, SHA, SHA, pasta)["aceitas"])

    def test_v2_and_v4_state_are_isolated_and_decisions_manuscript_findings_untouched(self):
        dec0, f0, b0 = json.dumps(self.dec, sort_keys=True), json.dumps(self.f, sort_keys=True), [(x.number, x.text) for x in self.b]
        with TemporaryDirectory() as pasta:
            outros = {"validacao-decisoes.json": b'{"v2": true}', "validacoes-v4.json": b'{"v4": true}',
                      "validacoes-v4-1.json": b'{"v41": true}'}
            for nome, dados in outros.items():
                (Path(pasta) / nome).write_bytes(dados)
            run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            vi.resultados(self.b, self.f, self.dec, pasta)
            self.assertEqual({n: (Path(pasta) / n).read_bytes() for n in outros}, outros)
            criados = {p.name for p in Path(pasta).iterdir()} - set(outros)
            self.assertLessEqual(criados, {v5.ARQUIVO, v5.TRAVA, vi.LATERAL})
        self.assertEqual((json.dumps(self.dec, sort_keys=True), json.dumps(self.f, sort_keys=True),
                          [(x.number, x.text) for x in self.b]), (dec0, f0, b0))

    def test_unreadable_or_incompatible_state_is_reported_and_not_trusted(self):
        with TemporaryDirectory() as pasta:
            (Path(pasta) / v5.ARQUIVO).write_text(json.dumps({"v4_1": 1, "itens": {"x": {}}}), encoding="utf-8")
            res = vi.resultados(self.b, self.f, self.dec, pasta)
            self.assertEqual((res["itens"], bool(res["aviso_de_leitura"])), ([], True))

    def test_configuration_change_marks_results_outdated_without_reprocessing(self):
        with TemporaryDirectory() as pasta:
            run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            with mock.patch.object(v5, "configuracao", return_value={"mudou": True}):
                res = vi.resultados(self.b, self.f, self.dec, pasta)
        self.assertTrue(all(x["situacao"] == "desatualizada_configuracao" for x in res["itens"]))

    def test_state_has_no_paragraph_text_and_the_key_never_appears(self):
        with TemporaryDirectory() as pasta:
            run(self.b, self.f, self.dec, self.ids, pasta, self.mapa)
            todo = "".join(p.read_text(encoding="utf-8") for p in Path(pasta).iterdir() if p.suffix == ".json")
            relatorio = json.dumps(vi.resultados(self.b, self.f, self.dec, pasta), ensure_ascii=False)
        for bloco in self.b:
            if len(bloco.text) > 40:
                self.assertNotIn(bloco.text, todo)
        self.assertNotIn(CHAVE, todo + relatorio)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.mapa = cenario()
        self.ids = [x["id"] for x in self.f]
        self.tmp = TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.arq = raiz / "livro.docx"
        self.arq.write_bytes(b"conteudo qualquer")
        import hashlib
        self.sha = hashlib.sha256(self.arq.read_bytes()).hexdigest()
        self.rel = raiz / "relatorio.json"
        self.rel.write_text(json.dumps({"sha256": self.sha, "findings": self.f}), encoding="utf-8")
        self.decf = raiz / "decisoes.json"
        self.decf.write_text(json.dumps({"decisions": self.dec}), encoding="utf-8")
        self.pasta = raiz / "proj"

    def tearDown(self):
        self.tmp.cleanup()

    def chamar(self, comando, *extra, ids=None):
        argv = [comando, str(self.arq), "--relatorio", str(self.rel), "--decisoes", str(self.decf), "--projeto", str(self.pasta)]
        if ids is not False:
            argv += ["--ids", *(ids if ids is not None else self.ids)]
        saida = io.StringIO()
        with mock.patch.object(cli, "read_manuscript", return_value=(self.b, [])), contextlib.redirect_stdout(saida):
            codigo = cli.main(argv + list(extra))
        linhas = saida.getvalue().splitlines()
        return codigo, linhas

    def linha(self, linhas, prefixo):
        return json.loads(next(l for l in linhas if l.startswith(prefixo + " "))[len(prefixo) + 1:])

    def test_estimate_command_prints_one_json_line_and_creates_nothing(self):
        codigo, linhas = self.chamar("validar-decisoes-v5-estimar")
        self.assertEqual(codigo, 0)
        e = self.linha(linhas, "LUME_ESTIMATIVA_VALIDADOR_V5")
        self.assertEqual((e["aceitas"], e["modelo"], e["segunda_rodada"]["autorizada"]), (5, v5.MODELO, False))
        self.assertFalse(self.pasta.exists())

    def test_errors_use_stable_codes_and_exit_code_2(self):
        for extra, ids, codigo in (([], False, "selecao_vazia"), (["--teto", "9"], None, "teto_invalido"),
                                   (["--max-itens", "2"], None, "itens_demais")):
            c, linhas = self.chamar("validar-decisoes-v5-estimar", *extra, ids=ids)
            self.assertEqual(c, 2)
            self.assertEqual(self.linha(linhas, "LUME_VALIDADOR_V5_ERRO")["codigo"], codigo)

    def test_execute_then_results_through_the_cli_with_a_simulated_transport(self):
        t = T5.Transporte(fn=T5.por_entrada(self.mapa))
        with mock.patch.object(v5, "chave_da_api", return_value=CHAVE), \
                mock.patch.object(v5, "transporte_http", return_value=t) as th:
            codigo, linhas = self.chamar("validar-decisoes-v5", "--teto", "1.0")
        self.assertEqual(codigo, 0, linhas)
        self.assertEqual(th.call_args[0][0], CHAVE)          # a chave só vai ao transporte
        r = self.linha(linhas, "LUME_VALIDACAO_V5")
        self.assertEqual((r["analisadas_agora"], r["decisoes_alteradas"]), (5, False))
        self.assertTrue(any(l.startswith("LUME_VALIDADOR_V5_PROGRESSO ") for l in linhas))
        self.assertNotIn(CHAVE, "\n".join(linhas) + (self.pasta / v5.ARQUIVO).read_text(encoding="utf-8"))
        codigo, linhas = self.chamar("validar-decisoes-v5-resultados", ids=False)
        res = self.linha(linhas, "LUME_RESULTADOS_V5")
        self.assertEqual((codigo, len(res["itens"]), res["contagem"]["contestada"]), (0, 5, 1))

    def test_missing_key_is_a_clean_error_line(self):
        with mock.patch.object(v5, "chave_da_api", return_value=None):
            codigo, linhas = self.chamar("validar-decisoes-v5")
        self.assertEqual((codigo, self.linha(linhas, "LUME_VALIDADOR_V5_ERRO")["codigo"]), (2, "chave_ausente"))

    def test_sigterm_is_a_clean_cancellation(self):
        anterior = signal.getsignal(signal.SIGTERM)

        def matar(*a, **k):
            os.kill(os.getpid(), signal.SIGTERM)
            import time
            time.sleep(2)
        try:
            with mock.patch.object(vi, "executar", side_effect=matar):
                codigo, _ = self.chamar("validar-decisoes-v5")
        finally:
            signal.signal(signal.SIGTERM, anterior)
        self.assertEqual(codigo, 130)

    def test_v2_commands_are_unchanged(self):
        for nome in ("validar-decisoes", "validar-decisoes-estimar"):
            self.assertIn(nome, cli.parser().parse_args([nome, str(self.arq), "--relatorio", str(self.rel),
                                                         "--decisoes", str(self.decf), "--projeto", str(self.pasta)]).command)


class RevalidarTests(unittest.TestCase):
    def test_outdated_results_are_analysed_again_only_when_asked(self):
        b, f, dec, mapa = cenario()
        ids = [x["id"] for x in f]
        alvo = ids[1]
        with TemporaryDirectory() as pasta:
            run(b, f, dec, ids, pasta, mapa)
            dec2 = dict(dec)
            dec2[alvo] = "Intencional" if dec[alvo] != "Intencional" else "Estilo do autor"   # resultado fica desatualizado
            e0 = vi.estimar(b, f, dec2, ids, SHA, SHA, pasta)
            self.assertEqual(e0["a_enviar"], [])
            r0, t0 = run(b, f, dec2, ids, pasta, mapa)
            self.assertEqual((r0["analisadas_agora"], posts(t0)), (0, []))
            e1 = vi.estimar(b, f, dec2, ids, SHA, SHA, pasta, revalidar=[alvo, "intruso"])
            self.assertEqual([x["id"] for x in e1["a_enviar"]], [alvo])
            self.assertGreater(e1["custo_maximo_usd"], 0)
            previa = vi.previa(b, f, dec2, ids, SHA, SHA, pasta, revalidar=[alvo])
            self.assertEqual([i for p in previa["pedidos"] for i in p["itens"]], [alvo])
            r1, t1 = run(b, f, dec2, ids, pasta, mapa, revalidar=[alvo])
            self.assertEqual(r1["analisadas_agora"], 1)
            self.assertEqual({i for c in posts(t1) for i in T.ids_do(c[2]["input"])}, {alvo})
            res = vi.resultados(b, f, dec2, pasta)
            self.assertTrue(all(x["vale_para_o_texto_e_decisao_atuais"] for x in res["itens"]))

    def test_edited_manuscript_needs_the_partial_context_option(self):
        b, f, dec, mapa = cenario()
        ids = [x["id"] for x in f]
        por = {x.number: x.text for x in b}
        for x in f:
            n = x["paragraph"]
            x["context"] = [{"paragraph": n - 1, "text": por[n - 1]}, {"paragraph": n + 1, "text": por[n + 1]}]
        e = vi.estimar(b, f, dec, ids, OUTRA, SHA, None)
        self.assertEqual((e["aceitas"], len(e["excluidos"])), (0, len(ids)))
        e = vi.estimar(b, f, dec, ids, OUTRA, SHA, None, permitir_parcial=True)
        self.assertEqual((e["aceitas"], e["verificacao"]), (len(ids), {"contexto_parcial": len(ids)}))


class PreviaETransporteSimuladoTests(unittest.TestCase):
    def test_preview_is_exactly_what_the_backend_sends(self):
        b, f, dec, mapa = cenario()
        ids = [x["id"] for x in f]
        with TemporaryDirectory() as pasta:
            previa = vi.previa(b, f, dec, ids, SHA, SHA, pasta)
            self.assertFalse(Path(pasta, v5.ARQUIVO).exists())
            _, t = run(b, f, dec, ids, pasta, mapa)
        enviados = [c[2]["input"] for c in t.chamadas if c[0] == "POST"]
        self.assertEqual([p["texto"] for p in previa["pedidos"]], enviados)
        self.assertEqual(sorted(i for p in previa["pedidos"] for i in p["itens"]), sorted(ids))
        self.assertFalse(previa["segunda_rodada_autorizada"])

    def test_preview_excludes_reused_and_incompatible_items(self):
        b, f, dec, mapa = cenario()
        ids = [x["id"] for x in f]
        with TemporaryDirectory() as pasta:
            run(b, f, dec, ids[:2], pasta, mapa)
            previa = vi.previa(b, f, dec, ids, SHA, SHA, pasta)
            self.assertEqual(sorted(i for p in previa["pedidos"] for i in p["itens"]), sorted(ids[2:]))
            self.assertEqual(vi.previa(b, f, dec, ids, OUTRA, SHA, pasta)["pedidos"], [])

    def test_simulated_transport_runs_the_whole_cli_without_network_or_key(self):
        b, f, dec, mapa = cenario()
        ids = [x["id"] for x in f]
        with TemporaryDirectory() as raiz:
            arquivo = Path(raiz) / "simulado.json"
            entradas = {i: T.base(i, "[ITEM %s] ocorrência 1 de 1" % i, **mapa[i]) | {"relacoes": []} for i in ids}
            arquivo.write_text(json.dumps({"avaliacoes": entradas}), encoding="utf-8")
            enviar = vi.transporte_simulado(arquivo)
            self.assertEqual(enviar("GET", "/v1/models/x")[0], 200)
            texto = "\n".join(f"[ITEM {i}] x" for i in ids[:2])
            status, dados, _ = enviar("POST", "/v1/responses", {"input": texto})
            corpo = json.loads(dados["output"][1]["content"][0]["text"])
            self.assertEqual((status, [e["id"] for e in corpo["avaliacoes"]]), (200, ids[:2]))


class IsolamentoDaV5Tests(unittest.TestCase):
    def test_integration_adds_no_prompt_schema_or_inference_of_its_own(self):
        from fonte import validador_v4_1 as v41
        self.assertIs(v5.SISTEMA, v41.SISTEMA)
        self.assertFalse(hasattr(vi, "SISTEMA") or hasattr(vi, "ESQUEMA"))
        import inspect
        fonte = inspect.getsource(vi)
        self.assertNotIn("def julgar", fonte)
        self.assertIn("rodada_extra=bool(autorizar_contexto)", fonte)


if __name__ == "__main__":
    unittest.main()
