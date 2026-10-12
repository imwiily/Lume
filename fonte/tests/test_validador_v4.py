"""Validador V4 (experimental): Sonnet avalia; Python só confere integridade; trava persistente por apontamento.
Modelos simulados; nenhum teste chama a API e todo texto é sintético."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock

from fonte import validador_decisoes as vd
from fonte import validador_v4 as v4
from fonte.analysis import finding
from fonte.reader import Block

ALVO = "A equipe trouxe as caixas que estava no carro."
PADRAO = "Mais tarde, as caixas estavam arrumadas no galpão."
LONGE = "Depois, as caixas estavam todas abertas no pátio."
FALA = "— Nóis vai chegar cedo, patrão — disse o capataz."


def livro():
    textos = [f"Parágrafo neutro número {n}, sobre a chuva e a estrada." for n in range(2, 40)]
    textos[3] = ALVO                              # §5
    textos[5] = PADRAO                            # §7: mesma palavra, forma padrão, dentro da janela do §5
    textos[28] = LONGE                            # §30: idem, mas fora da janela (só chega por pedido de contexto)
    textos[10] = FALA                             # §12
    return [Block(1, "Capítulo 1", "Capítulo 1", heading=True)] + [Block(i + 2, t, "Capítulo 1") for i, t in enumerate(textos)]


def alerta(blocos, numero, trecho, categoria="Concordância verbal", motivo="Hipótese do detector.", nth=0):
    b = next(x for x in blocos if x.number == numero)
    i = -1
    for _ in range(nth + 1):
        i = b.text.index(trecho, i + 1)
    return asdict(finding(b, categoria, "Verificar", i, i + len(trecho), motivo, "FONTE"))


def cenario(decisao="Estilo do autor"):
    b = livro()
    f = alerta(b, 5, "estava")
    return b, [f], {f["id"]: decisao}


def ids_do(usuario):
    return re.findall(r"\[ITEM (\w+)\]", usuario)


class Modelo:
    modelo = v4.MODELO

    def __init__(self, resposta):
        self.resposta, self.pedidos, self.chamadas = resposta, [], []

    def json(self, sistema, usuario, esquema, etapa):
        self.pedidos.append(usuario)
        saida = self.resposta(usuario)
        if isinstance(saida, BaseException):
            raise saida
        self.chamadas.append({"etapa": etapa, "custo_usd": 0.03, "tokens_entrada": 1000, "tokens_cache": 100,
                              "tokens_saida": 200, "modelo_usado": self.modelo, "pedido": f"req_{len(self.chamadas)}",
                              "segundos": 1.0})
        return saida


def resposta_base(ident, usuario, **campos):
    achado = re.search(rf"\[ITEM {ident}\].*?ocorrência (\d+) de", usuario, re.S)
    ordem = int(achado.group(1)) if achado else 1
    base = {"id": ident, "ocorrencia": ordem, "procede": "nao", "justificativa_detector": "correta",
            "legitimidade": "nao_se_aplica", "evidencia_suficiente": True, "explicacao": "Ok.", "evidencia": "",
            "evidencia_estilistica": "", "evidencia_ausencia": "", "recomendacao": "", "problema_trecho": "",
            "problema_explicacao": "", "precisa_mais_contexto": False, "paragrafos_solicitados": [],
            "termos_solicitados": []}
    base.update(campos)
    return base


def sonnet(mapa=None, fn=None):
    def resposta(usuario):
        if fn:
            r = fn(usuario)
            if r is not None:
                return r
        return {"avaliacoes": [resposta_base(i, usuario, **(mapa or {}).get(i, {})) for i in ids_do(usuario)]}
    return resposta


def rodar(b, f, dec, campos=None, fn=None, pasta=None, teto=5.0, **kw):
    cliente = Modelo(sonnet(({f[0]["id"]: campos} if campos else {}), fn))
    ctx = TemporaryDirectory() if pasta is None else None
    try:
        r = v4.avaliar(b, f, dec, pasta=pasta or ctx.name, teto=teto, cliente=cliente, **kw)
        return (*r, cliente)
    finally:
        if ctx:
            ctx.cleanup()


CONTESTA = {"procede": "sim", "legitimidade": "ausente", "explicacao": "Plural com verbo no singular.",
            "evidencia": "as caixas que estava", "evidencia_ausencia": "as caixas estavam arrumadas",
            "recomendacao": "Usar “estavam”."}


class FiscalizacaoTests(unittest.TestCase):
    def test_exact_evidence_gets_paragraph_position_and_hash_computed_by_lume(self):
        b, f, dec = cenario()
        r, _, resumo, _ = rodar(b, f, dec, CONTESTA)
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], resumo["resultados"]["contestada"]), ("contestada", 1))
        alvo = next(e for e in x["evidencias_verificadas"] if e["papel"] == "alvo")
        self.assertEqual((alvo["paragrafo"], alvo["trecho"]), (5, "as caixas que estava"))
        self.assertEqual(alvo["inicio"], ALVO.index("as caixas que estava"))
        self.assertEqual(alvo["sha256_paragrafo"], v4._hash_texto(ALVO))
        ausencia = next(e for e in x["evidencias_verificadas"] if e["papel"] == "ausencia")
        self.assertEqual((ausencia["paragrafo"], ausencia["inicio"]), (7, PADRAO.index("as caixas estavam arrumadas")))
        self.assertEqual(x["integridade"]["paragrafo_sha256"], v4._hash_texto(ALVO))

    def test_repeated_words_mark_the_right_occurrence_and_never_alter_the_text(self):
        b = livro()
        texto = "O ponto principal era que ele segurava um remo. Ela espera, e ela era repleta de cracas."
        b[6] = Block(7, texto, "Capítulo 1")
        i1, i2 = texto.index("era"), texto.rindex("era")
        f = [asdict(finding(b[6], "Tempo verbal", "Verificar", i, i + 3, "Hipótese.", "FONTE")) for i in (i1, i2)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        cliente = Modelo(sonnet({f[1]["id"]: {"procede": "sim", "legitimidade": "ausente", "explicacao": "Passado.",
                                              "evidencia": "ponto principal era que",     # OUTRA ocorrência
                                              "evidencia_ausencia": "ela era repleta"}}))
        with TemporaryDirectory() as pasta:
            r, _, resumo = v4.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=cliente)
        self.assertEqual((r[f[1]["id"]]["estado"], r[f[1]["id"]]["motivo"]), ("inconclusiva", "evidencia_de_outra_ocorrencia"))
        pedido = cliente.pedidos[0]
        self.assertIn("ocorrência 1 de 2", pedido)
        self.assertIn("ocorrência 2 de 2", pedido)
        marca = re.search(r"Marca do alvo: entre (\S+) e (\S+) ", pedido).groups()
        for linha in re.findall(r"^§7 (.*)$", pedido, re.M):
            if marca[0] in linha:
                limpo = linha.replace(marca[0], "").replace(marca[1], "")
                self.assertEqual(limpo, texto)                               # o texto original é intacto
        self.assertEqual(b[6].text, texto)

    def test_ordinal_echo_mismatch_cannot_support_a_contestation(self):
        b, f, dec = cenario()
        r, _, _, _ = rodar(b, f, dec, dict(CONTESTA, ocorrencia=2))
        self.assertEqual((r[f[0]["id"]]["estado"], r[f[0]["id"]]["motivo"]), ("inconclusiva", "ocorrencia_divergente"))

    def test_invented_evidence_is_downgraded(self):
        b, f, dec = cenario()
        r, _, _, _ = rodar(b, f, dec, dict(CONTESTA, evidencia="frase que não existe"))
        self.assertEqual((r[f[0]["id"]]["estado"], r[f[0]["id"]]["motivo"]), ("inconclusiva", "evidencia_inexistente"))
        r, _, resumo, _ = rodar(b, f, dec, {"procede": "sim", "legitimidade": "presente", "evidencia_estilistica": "razão inventada"})
        self.assertEqual(r[f[0]["id"]]["estado"], "revisao_recomendada")        # legitimidade não comprovada
        self.assertEqual(resumo["descartes"]["evidencia_estilistica_inexistente"], 1)

    def test_objective_error_with_wrong_decision_is_contested_without_absence_proof(self):
        b, f, dec = cenario("Falso positivo")
        r, _, _, _ = rodar(b, f, dec, {"procede": "sim", "legitimidade": "nao_se_aplica", "explicacao": "Erro real.",
                                       "evidencia": "as caixas que estava", "recomendacao": "Corrigir."})
        self.assertEqual(r[f[0]["id"]]["estado"], "contestada")

    def test_legitimate_literary_choice_is_kept_and_its_reason_is_verified(self):
        b = livro()
        f = [alerta(b, 12, "Nóis vai")]
        dec = {f[0]["id"]: "Estilo do autor"}
        r, _, resumo, c = rodar(b, f, dec, {"procede": "sim", "legitimidade": "presente", "explicacao": "Fala dialetal.",
                                            "evidencia_estilistica": "— Nóis vai chegar cedo, patrão —"})
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], resumo["resultados"]["contestada"]), ("mantida", 0))
        self.assertEqual(x["avaliacao"]["procede"], "sim")                       # o apontamento procede
        self.assertEqual(x["avaliacao"]["decisao_coerente"], "sim")              # e a decisão segue coerente
        self.assertEqual(x["avaliacao"]["registro"], "dialogo")
        self.assertIn("Registro do alvo: fala de personagem", c.pedidos[0])
        self.assertEqual([e["papel"] for e in x["evidencias_verificadas"]], ["estilistica"])

    def test_undetermined_intention_is_review_recommended_not_contested(self):
        b, f, dec = cenario()
        r, _, resumo, _ = rodar(b, f, dec, {"procede": "sim", "legitimidade": "incerta", "explicacao": "Pode ser voz."})
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], x["motivo"], resumo["resultados"]["contestada"]),
                         ("revisao_recomendada", "intencao_indeterminada", 0))

    def test_neutral_sentence_from_another_paragraph_is_not_proof_of_absence(self):
        b, f, dec = cenario()
        r, _, resumo, _ = rodar(b, f, dec, dict(CONTESTA, evidencia_ausencia="Parágrafo neutro número 3, sobre a chuva e a estrada."))
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], x["motivo"]), ("revisao_recomendada", "prova_de_ausencia_sem_pertinencia"))
        self.assertEqual(resumo["resultados"]["contestada"], 0)
        # sem prova de ausência, ou com a própria evidência do alvo, também não contesta
        for apoio, motivo in (("", "prova_de_ausencia_ausente"), ("as caixas que estava", "prova_de_ausencia_inexistente")):
            r, _, _, _ = rodar(b, f, dec, dict(CONTESTA, evidencia_ausencia=apoio))
            self.assertEqual((r[f[0]["id"]]["estado"], r[f[0]["id"]]["motivo"]), ("revisao_recomendada", motivo))
        self.assertTrue(v4.pertinente("as caixas estavam arrumadas", "estava"))
        self.assertFalse(v4.pertinente("As duas ficam em silêncio por segundos.", "estava"))

    def test_controlled_context_request_brings_distant_proof_and_it_is_verified(self):
        b, f, dec = cenario()
        ident = f[0]["id"]

        def fn(usuario):
            if "Trechos adicionais buscados" not in usuario:      # 1ª rodada: pede o termo; ainda sem prova
                return {"avaliacoes": [resposta_base(ident, usuario, procede="sim", legitimidade="incerta",
                                                     precisa_mais_contexto=True, termos_solicitados=["estavam"])]}
            return {"avaliacoes": [resposta_base(ident, usuario, **dict(CONTESTA, evidencia_ausencia="as caixas estavam todas abertas"))]}
        with TemporaryDirectory() as pasta:
            cliente = Modelo(sonnet(fn=fn))
            # a janela já contém uma ocorrência próxima: a busca por termo devolve o parágrafo distante
            b2 = deepcopy(b)
            b2[5] = Block(6, "Texto neutro sem a palavra procurada.", "Capítulo 1")
            b2[6] = Block(7, "Outro texto neutro sem a palavra procurada.", "Capítulo 1")
            f2 = [alerta(b2, 5, "estava")]
            r, _, resumo = v4.avaliar(b2, f2, {f2[0]["id"]: "Estilo do autor"}, pasta=pasta, teto=5, cliente=cliente)
        x = r[f2[0]["id"]]
        self.assertEqual((x["rodadas"], x["estado"], len(cliente.pedidos)), (2, "contestada", 2))
        self.assertTrue(x["contexto_alterou_conclusao"])
        self.assertEqual(x["pediu_mais_contexto"]["estado_primeira_rodada"], "revisao_recomendada")
        ausencia = next(e for e in x["evidencias_verificadas"] if e["papel"] == "ausencia")
        self.assertEqual((ausencia["paragrafo"], ausencia["origem"]), (30, "adicional"))
        self.assertEqual(resumo["contexto_alterou_conclusao"], 1)

    def test_detector_reason_wrong_and_independent_problem(self):
        b, f, dec = cenario("Falso positivo")
        r, _, _, _ = rodar(b, f, dec, {"procede": "nao", "justificativa_detector": "incorreta", "explicacao": "Não é erro.",
                                       "problema_trecho": "trouxe as caixas", "problema_explicacao": "Outra questão."})
        x = r[f[0]["id"]]
        self.assertEqual(x["estado"], "apontamento_inadequado")
        self.assertEqual(x["questao_independente"]["trecho"], "trouxe as caixas")
        r, _, resumo, _ = rodar(b, f, dec, {"procede": "nao", "justificativa_detector": "incorreta",
                                            "problema_trecho": "estava", "problema_explicacao": "É o próprio alvo."})
        self.assertIsNone(r[f[0]["id"]]["questao_independente"])
        self.assertEqual(resumo["descartes"]["problema_sobre_o_alvo"], 1)

    def test_decision_meanings_are_respected(self):
        b = livro()
        base = {"justificativa_detector": "correta", "explicacao": "Há um desvio.", "evidencia": "Ela chegou cedo"}
        b[7] = Block(8, "Ela chegou cedo.", "Capítulo 1")
        f = [alerta(b, 8, "chegou", "Regência")]
        casos = [("Aceito editorialmente", "sim", "ausente", "mantida"), ("Erro confirmado", "sim", "ausente", "mantida"),
                 ("Erro confirmado", "nao", "nao_se_aplica", "contestada"), ("Falso positivo", "sim", "ausente", "contestada"),
                 ("Falso positivo", "nao", "nao_se_aplica", "mantida"), ("Estilo do autor", "sim", "presente", "revisao_recomendada")]
        for decisao, procede, leg, esperado in casos:
            r, _, _, _ = rodar(b, f, {f[0]["id"]: decisao}, dict(base, procede=procede, legitimidade=leg))
            with self.subTest(decisao=decisao, procede=procede, leg=leg):
                self.assertEqual(r[f[0]["id"]]["estado"], esperado)

    def test_invalid_model_responses_are_never_stored_as_validations(self):
        b, f, dec = cenario()
        ident = f[0]["id"]
        validas = lambda u: resposta_base(ident, u)
        quebras = {
            "campo_ausente": lambda u: {k: v for k, v in validas(u).items() if k != "legitimidade"},
            "enumeracao": lambda u: dict(validas(u), procede="talvez"),
            "tipo": lambda u: dict(validas(u), evidencia_suficiente="sim"),
        }
        for nome, quebra in quebras.items():
            with TemporaryDirectory() as pasta:
                cliente = Modelo(lambda u, q=quebra: {"avaliacoes": [q(u)]})
                r, _, resumo = v4.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=cliente)
                with self.subTest(nome):
                    self.assertNotIn(ident, {i for i, x in r.items() if x.get("estado_validacao") == "analisada"})
                    self.assertEqual(resumo["sem_resposta"], 1)
                    self.assertEqual(v4.planejar(b, f, dec, pasta)["situacoes"], {"nova": 1})   # continua pendente
        with TemporaryDirectory() as pasta:     # id desconhecido, duplicata contraditória, procede=nao + ausente
            def u(usuario):
                return {"avaliacoes": [resposta_base("inventado", usuario),
                                       resposta_base(ident, usuario, procede="nao", legitimidade="ausente"),
                                       resposta_base(ident, usuario)]}
            cliente = Modelo(u)
            r, _, resumo = v4.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=cliente)
            self.assertEqual(resumo["descartes"]["id_desconhecido"], 1)
            self.assertEqual(resumo["descartes"]["resposta_contraditoria_duplicada"], 1)
            self.assertEqual(resumo["sem_resposta"], 1)
        with TemporaryDirectory() as pasta:     # procede=nao com legitimidade=ausente: contraditória dentro da resposta
            r, _, resumo, _ = rodar(b, f, dec, {"procede": "nao", "legitimidade": "ausente"}, pasta=pasta)
            self.assertEqual((r[ident]["estado"], r[ident]["motivo"]), ("inconclusiva", "resposta_contraditoria"))


class TravaPersistenteTests(unittest.TestCase):
    def test_completed_validation_is_reused_without_a_new_call(self):
        b, f, dec = cenario()
        with TemporaryDirectory() as pasta:
            r1, _, _, c1 = rodar(b, f, dec, CONTESTA, pasta=pasta)
            r2, avisos, resumo, c2 = rodar(b, f, dec, CONTESTA, pasta=pasta)
            self.assertEqual((len(c1.pedidos), len(c2.pedidos)), (1, 0))
            self.assertEqual((resumo["reutilizadas_sem_custo"], resumo["custo_usd"], resumo["pedidos"]), (1, 0.0, 0))
            self.assertEqual(r2[f[0]["id"]]["estado"], "contestada")
            e = v4.estimar(b, f, dec, pasta)
            self.assertEqual((e["a_analisar"], e["reutilizadas_sem_custo"], e["custo_esperado_usd"], e["chamadas_primeira_rodada"]),
                             (0, 1, 0.0, 0))

    def test_inconclusive_results_are_preserved_and_not_paid_again(self):
        b, f, dec = cenario()
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, {"procede": "incerto", "evidencia_suficiente": False}, pasta=pasta)
            _, _, resumo, c = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((len(c.pedidos), resumo["reutilizadas_sem_custo"]), (0, 1))
            plano = v4.planejar(b, f, dec, pasta)
            self.assertEqual(plano["itens"][f[0]["id"]]["estado_ui"], "inconclusiva")

    def test_selective_invalidation_flags_stale_without_reprocessing(self):
        b, f, dec = cenario()
        ident = f[0]["id"]
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, CONTESTA, pasta=pasta)
            longe = deepcopy(b)
            longe[30] = Block(31, "Texto totalmente diferente, bem longe do alerta.", "Capítulo 1")     # fora da janela
            self.assertEqual(v4.planejar(longe, f, dec, pasta)["situacoes"], {"valida": 1})            # nada invalidado
            perto = deepcopy(b)
            perto[5] = Block(6, "Parágrafo vizinho alterado pelo autor.", "Capítulo 1")                 # dentro da janela
            plano = v4.planejar(perto, f, dec, pasta)
            self.assertEqual(plano["itens"][ident], {"situacao": "desatualizada_conteudo", "analisar": False,
                                                     "estado_ui": "desatualizada"})
            _, _, resumo, c = rodar(perto, f, dec, pasta=pasta)                    # executar não reprocessa sozinho
            self.assertEqual((len(c.pedidos), resumo["desatualizadas"]), (0, 1))
            e = v4.estimar(perto, f, dec, pasta)
            self.assertEqual((e["a_analisar"], e["desatualizadas_nao_reprocessadas"]), (0, 1))
            # Revalidação manual, pedida pelo autor, analisa só esse apontamento.
            e2 = v4.estimar(perto, f, dec, pasta, revalidar=[ident])
            self.assertEqual((e2["a_analisar"], e2["chamadas_primeira_rodada"]), (1, 1))
            r, _, resumo, c = rodar(perto, f, dec, CONTESTA, pasta=pasta, revalidar=[ident])
            self.assertEqual((len(c.pedidos), resumo["analisadas_agora"]), (1, 1))
            self.assertEqual(v4.planejar(perto, f, dec, pasta)["situacoes"], {"valida": 1})
            # Decisão humana alterada → desatualizada, sem reprocesso automático.
            plano = v4.planejar(perto, f, {ident: "Intencional"}, pasta)
            self.assertEqual(plano["situacoes"], {"desatualizada_conteudo": 1})

    def test_model_or_prompt_update_never_triggers_paid_reprocessing(self):
        b, f, dec = cenario()
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, CONTESTA, pasta=pasta)
            with mock.patch.object(v4, "VERSAO_PROMPT", 2):
                plano = v4.planejar(b, f, dec, pasta)
                self.assertEqual(plano["situacoes"], {"desatualizada_configuracao": 1})
                self.assertEqual(plano["a_analisar"], [])
                _, _, _, c = rodar(b, f, dec, pasta=pasta)
                self.assertEqual(c.pedidos, [])
            plano = v4.planejar(b, f, dec, pasta, modelo="claude-sonnet-5-6")
            self.assertEqual(plano["situacoes"], {"desatualizada_configuracao": 1})

    def test_duplicate_execution_is_blocked_before_any_call(self):
        b, f, dec = cenario()
        with TemporaryDirectory() as pasta:
            with v4.trava(pasta):
                self.assertTrue(v4.ocupada(pasta))
                cliente = Modelo(sonnet())
                with self.assertRaises(v4.ValidacaoEmAndamento):
                    v4.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=cliente)
                self.assertEqual(cliente.pedidos, [])
                with self.assertRaises(v4.ValidacaoEmAndamento):
                    with v4.trava(pasta):
                        pass
            self.assertFalse(v4.ocupada(pasta))        # a trava some sozinha ao terminar

    def test_cancellation_keeps_finished_batches_and_leaves_no_phantom_result(self):
        b = livro()
        f = [alerta(b, n, "neutro", "Regência") for n in (8, 20, 25)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        with TemporaryDirectory() as pasta, mock.patch.object(v4, "LOTE", (1, 9000)):
            n = {"v": 0}

            def fn(usuario):
                n["v"] += 1
                return KeyboardInterrupt() if n["v"] == 2 else None
            with self.assertRaises(KeyboardInterrupt):
                v4.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=Modelo(sonnet(fn=fn)))
            guardado, _ = v4.ler(pasta)
            self.assertEqual([x["estado_validacao"] for x in guardado.values()], ["analisada"])   # sem "em processamento"
            self.assertFalse(v4.ocupada(pasta))
            _, _, resumo, c = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((resumo["reutilizadas_sem_custo"], resumo["analisadas_agora"], len(c.pedidos)), (1, 2, 2))

    def test_leftover_of_a_dead_run_is_not_a_result(self):
        b, f, dec = cenario()
        ident = f[0]["id"]
        with TemporaryDirectory() as pasta:
            v4.gravar(pasta, {ident: {"id": ident, "estado_validacao": "em_processamento", "estado": "contestada",
                                      "chave_conteudo": "x", "chave_configuracao": "y"}})
            self.assertEqual(v4.planejar(b, f, dec, pasta)["itens"][ident]["estado_ui"], "nao_analisada")
            _, _, resumo, c = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((resumo["analisadas_agora"], len(c.pedidos)), (1, 1))

    def test_budget_stop_is_partial_and_resumable(self):
        from coerencia.modelo import TetoAtingido
        b = livro()
        f = [alerta(b, n, "neutro", "Regência") for n in (8, 20, 25)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        with TemporaryDirectory() as pasta, mock.patch.object(v4, "LOTE", (1, 9000)):
            n = {"v": 0}

            def fn(usuario):
                n["v"] += 1
                return TetoAtingido("Teto de gasto atingido.") if n["v"] == 2 else None
            _, avisos, resumo, _ = rodar(b, f, dec, fn=fn, pasta=pasta)
            self.assertTrue(resumo["interrompida"])
            self.assertEqual((resumo["analisadas_agora"], resumo["sem_resposta"]), (1, 2))
            self.assertTrue(any("execução parcial" in a for a in avisos))
            self.assertEqual(v4.planejar(b, f, dec, pasta)["situacoes"], {"valida": 1, "nova": 2})
            _, _, resumo2, _ = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((resumo2["reutilizadas_sem_custo"], resumo2["analisadas_agora"]), (1, 2))

    def test_v3_results_are_never_used_as_v4_validations(self):
        b, f, dec = cenario()
        ident = f[0]["id"]
        with TemporaryDirectory() as pasta:
            (Path(pasta) / "validacao-v3-A.json").write_text(json.dumps(
                {"versao": 1, "v3": 1, "grupo": "A", "itens": {ident: {"id": ident, "estado": "contestada", "chave": "x"}}}),
                encoding="utf-8")
            antes = (Path(pasta) / "validacao-v3-A.json").read_bytes()
            _, _, resumo, c = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((resumo["reutilizadas_sem_custo"], len(c.pedidos)), (0, 1))
            self.assertEqual((Path(pasta) / "validacao-v3-A.json").read_bytes(), antes)     # preservado

    def test_no_previous_verdict_reaches_the_model(self):
        b, f, dec = cenario()
        _, _, _, c = rodar(b, f, dec)
        for proibido in ("Haiku", "Opus", "V1", "V2", "V3", "contestad", "veredito", "inconclusiv"):
            self.assertNotIn(proibido, c.pedidos[0], proibido)
        self.assertIn("Hipótese do detector (não é um fato", c.pedidos[0])


class EconomiaTests(unittest.TestCase):
    def test_shared_context_paragraphs_are_sent_once_per_batch(self):
        b = livro()
        f = [alerta(b, n, "neutro", "Regência") for n in (20, 21, 22)]      # janelas ±3 quase iguais
        dec = {x["id"]: "Estilo do autor" for x in f}
        itens = v4.preparar(b, f, dec)[0]
        grupos = v4.lotes(itens, b)
        self.assertEqual([len(g) for g in grupos], [3])
        texto, autorizado = v4.pedido(grupos[0], b)
        for numero in (18, 19, 23, 24, 25):
            self.assertEqual(len(re.findall(rf"^§{numero} ", texto, re.M)), 1, numero)
        # cada item recebeu o que lhe pertence
        self.assertIn((17, b[16].text, "contexto"), autorizado[f[0]["id"]])
        ingenuo = sum(len(vd._janela(b, i["_bloco"], 3)[0]) + len(vd._janela(b, i["_bloco"], 3)[1]) + 1 for i in grupos[0])
        enviados = len(re.findall(r"^§\d+ ", texto, re.M))
        self.assertLess(enviados, ingenuo)

    def test_output_limit_follows_the_contract_and_is_restored(self):
        from coerencia import modelo as m
        from coerencia.modelo import Claude, Orcamento
        capturado = []

        def criar(**pedido):
            capturado.append(pedido["max_tokens"])
            ident = re.search(r"\[ITEM (\w+)\]", pedido["messages"][0]["content"]).group(1)
            texto = json.dumps({"avaliacoes": [resposta_base(ident, pedido["messages"][0]["content"])]})
            uso = SimpleNamespace(input_tokens=1000, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=100)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], usage=uso, stop_reason="end_turn",
                                   model="claude-sonnet-5-5", _request_id="req_t")
        falso = SimpleNamespace(messages=SimpleNamespace(create=criar), beta=SimpleNamespace(messages=SimpleNamespace(create=criar)))
        b, f, dec = cenario()
        antes = m.MAX_TOKENS
        with TemporaryDirectory() as pasta:
            cliente = Claude(v4.MODELO, cliente=falso, orcamento=Orcamento(5.0))
            v4.avaliar(b, f, dec, pasta=pasta, teto=5.0, cliente=cliente)
        self.assertEqual(capturado, [v4.SAIDA_FIXA + v4.SAIDA_POR_ITEM])
        self.assertLess(capturado[0], antes)
        self.assertEqual(m.MAX_TOKENS, antes)                                   # restaurado

    def test_estimate_counts_calls_tokens_and_budget_floor(self):
        b = livro()
        f = [alerta(b, n, "neutro", "Regência") for n in (8, 20, 25, 33)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        e = v4.estimar(b, f, dec)
        self.assertEqual((e["a_analisar"], e["chamadas_primeira_rodada"]), (4, 2))
        self.assertLessEqual(e["custo_minimo_usd"], e["custo_esperado_usd"])
        self.assertLessEqual(e["custo_esperado_usd"], e["custo_maximo_usd"])
        self.assertGreater(e["teto_minimo_usd"], e["pior_chamada_usd"])
        # O limite de saída reduz o pior caso reservado: bem abaixo do que 16.000 tokens custariam.
        self.assertLess(e["pior_chamada_usd"], 0.4)
        self.assertEqual(e["limite_de_saida_por_pedido"], [v4.SAIDA_FIXA + 3 * v4.SAIDA_POR_ITEM, v4.SAIDA_FIXA + v4.SAIDA_POR_ITEM])


class ContratoDaInterfaceTests(unittest.TestCase):
    def test_ui_states_and_counts_before_any_execution(self):
        b = livro()
        f = [alerta(b, n, "neutro", "Regência") for n in (8, 20, 25)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        self.assertEqual(set(v4.ESTADOS_UI), {"nao_analisada", "analisada", "contestada", "revisao_recomendada",
                                              "inconclusiva", "desatualizada", "em_processamento"})
        with TemporaryDirectory() as pasta:
            plano = v4.planejar(b, f, dec, pasta)
            self.assertEqual((len(plano["a_analisar"]), plano["reutilizadas"]), (3, 0))
            self.assertEqual({v["estado_ui"] for v in plano["itens"].values()}, {"nao_analisada"})
            _, _, _, _ = rodar(b, f, dec, pasta=pasta)
            plano = v4.planejar(b, f, dec, pasta)
            self.assertEqual({v["estado_ui"] for v in plano["itens"].values()}, {"analisada"})
            self.assertEqual((len(plano["a_analisar"]), plano["reutilizadas"]), (0, 3))
            with v4.trava(pasta):
                registros, _ = v4.ler(pasta)
                ident = f[0]["id"]
                registros[ident]["estado_validacao"] = "em_processamento"
                self.assertEqual(v4.estado_ui(registros[ident], None, ativo=True), "em_processamento")
            self.assertEqual(v4.estado_ui(None), "nao_analisada")
            self.assertEqual(v4.estado_ui({"estado": "contestada", "estado_validacao": "analisada"}), "contestada")
            self.assertEqual(v4.estado_ui({"estado": "revisao_recomendada"}), "revisao_recomendada")

    def test_human_decisions_findings_and_manuscript_are_untouched(self):
        b, f, dec = cenario()
        antes = (deepcopy(f), deepcopy(dec), [x.text for x in b])
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, CONTESTA, pasta=pasta)
            self.assertEqual(sorted(p.name for p in Path(pasta).iterdir()), sorted([v4.TRAVA, v4.ARQUIVO]))
        self.assertEqual((f, dec, [x.text for x in b]), antes)

    def test_state_file_holds_ids_hashes_and_numbers_not_the_manuscript(self):
        b, f, dec = cenario()
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, dict(CONTESTA, evidencia_estilistica=""), pasta=pasta)
            conteudo = (Path(pasta) / v4.ARQUIVO).read_text(encoding="utf-8")
            registro = json.loads(conteudo)["itens"][f[0]["id"]]
        for campo in ("chave_conteudo", "chave_configuracao", "configuracao", "consumo", "integridade", "modelo_final",
                      "evidencias_verificadas", "estado_validacao", "avaliado_em"):
            self.assertIn(campo, registro)
        self.assertEqual(registro["configuracao"]["modelo"], v4.MODELO)
        self.assertNotIn(ALVO, conteudo)           # o parágrafo inteiro nunca é gravado


if __name__ == "__main__":
    unittest.main()
