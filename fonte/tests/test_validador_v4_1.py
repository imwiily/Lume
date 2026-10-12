"""Validador V4.1 (experimental): dois julgamentos separados, antecedentes por relevância, vínculo das
evidências. Modelos simulados; nenhum teste chama a API e todo texto é sintético."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from fonte import validador_decisoes as vd
from fonte import validador_v3 as v3
from fonte import validador_v4 as v4
from fonte import validador_v4_1 as v41
from fonte.analysis import finding
from fonte.reader import Block

ALVO = "A equipe trouxe as caixas que estava no carro."


def livro():
    textos = [f"Parágrafo neutro número {n}, sobre a chuva e a estrada." for n in range(2, 60)]
    textos[1] = "Um grupo de viajantes parou junto ao rio. Eram apenas três, e o mais novo levava a bússola."   # §3
    textos[3] = ALVO                                                    # §5
    textos[5] = "Mais tarde, as caixas estavam arrumadas no galpão."    # §7 (na janela do §5)
    textos[10] = "— Nóis vai chegar cedo, patrão — disse o capataz."    # §12
    for n in range(14, 40):                                             # nomes recorrentes, perto do alerta distante
        textos[n - 2] = f"Parágrafo {n}: Taro chamou Miki, e Miki respondeu a Taro sobre a chuva."
    textos[43] = "— Taro… Joel… Onde estão vocês? — chamou Miki."       # §45: alvo da contradição
    return [Block(1, "Capítulo 1", "Capítulo 1", heading=True)] + [Block(i + 2, t, "Capítulo 1") for i, t in enumerate(textos)]


def alerta(blocos, numero, trecho, categoria="Concordância verbal", motivo="Hipótese do detector.", nth=0):
    b = next(x for x in blocos if x.number == numero)
    i = -1
    for _ in range(nth + 1):
        i = b.text.index(trecho, i + 1)
    return asdict(finding(b, categoria, "Verificar", i, i + len(trecho), motivo, "FONTE"))


def ids_do(usuario):
    return re.findall(r"\[ITEM (\w+)\]", usuario)


class Modelo:
    modelo = v41.MODELO

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


def base(ident, usuario, **campos):
    achado = re.search(rf"\[ITEM {ident}\].*?ocorrência (\d+) de", usuario, re.S)
    r = {"id": ident, "ocorrencia": int(achado.group(1)) if achado else 1, "existe": "nao", "natureza": "nenhuma",
         "certeza": "nao_se_aplica", "gravidade": "nenhuma", "justificativa_detector": "correta",
         "razao_literaria": "nao_se_aplica", "evidencia_suficiente": True, "explicacao": "Ok.", "evidencia": "",
         "evidencia_razao": "", "recomendacao": "", "problema_trecho": "", "problema_explicacao": "",
         "precisa_mais_contexto": False, "paragrafos_solicitados": [], "termos_solicitados": []}
    r.update(campos)
    return r


def modelo(mapa=None, fn=None):
    def resposta(usuario):
        if fn:
            r = fn(usuario)
            if r is not None:
                return r
        return {"avaliacoes": [base(i, usuario, **(mapa or {}).get(i, {})) for i in ids_do(usuario)]}
    return Modelo(resposta)


def rodar(b, f, dec, campos=None, fn=None, pasta=None, **kw):
    mapa = {f[0]["id"]: campos} if campos else None
    c = modelo(mapa, fn)
    ctx = TemporaryDirectory() if pasta is None else None
    try:
        r = v41.avaliar(b, f, dec, pasta=pasta or ctx.name, teto=5.0, cliente=c, **kw)
        return (*r, c)
    finally:
        if ctx:
            ctx.cleanup()


def um_item(decisao="Estilo do autor", trecho="estava", numero=5, categoria="Concordância verbal", motivo="Hipótese."):
    b = livro()
    f = alerta(b, numero, trecho, categoria, motivo)
    return b, [f], {f["id"]: decisao}


OBJETIVO = {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "media",
            "explicacao": "Plural com verbo no singular.", "evidencia": "as caixas que estava"}


class DoisJulgamentosTests(unittest.TestCase):
    def test_objective_error_with_unknown_literary_intention_keeps_the_technical_diagnosis(self):
        b, f, dec = um_item()
        r, _, resumo, _ = rodar(b, f, dec, dict(OBJETIVO, razao_literaria="nao_identificada"))
        x = r[f[0]["id"]]
        self.assertEqual(x["estado"], "revisao_recomendada")            # nem contestada, nem descartada
        self.assertEqual(x["problema_tecnico"], {"existe": "sim", "natureza": "objetivo", "certeza": "clara",
                                                  "gravidade": "media"})
        self.assertEqual((x["adequacao_decisao"], x["prioridade_revisao"]), ("indeterminada", "alta"))
        self.assertEqual(resumo["resultados"]["contestada"], 0)
        self.assertEqual(resumo["prioridade_das_revisoes"], {"baixa": 0, "media": 0, "alta": 1})
        self.assertEqual([e["sustenta"] for e in x["evidencias_verificadas"]], ["problema_tecnico"])

    def test_deviation_with_legitimate_literary_reason_is_kept_and_reason_is_verified(self):
        b = livro()
        f = [alerta(b, 12, "Nóis vai")]
        dec = {f[0]["id"]: "Estilo do autor"}
        r, _, _, c = rodar(b, f, dec, {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "baixa",
                                       "razao_literaria": "identificada", "evidencia": "Nóis vai chegar",
                                       "evidencia_razao": "— Nóis vai chegar cedo, patrão —"})
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], x["adequacao_decisao"], x["avaliacao"]["decisao_coerente"]), ("mantida", "adequada", "sim"))
        self.assertEqual(x["problema_tecnico"]["existe"], "sim")         # o problema técnico existe e é reconhecido
        self.assertIn("legitimidade", [e["sustenta"] for e in x["evidencias_verificadas"]])
        self.assertIn("Registro do alvo: fala de personagem", c.pedidos[0])
        # citação inexistente: não vale como razão; o diagnóstico técnico permanece
        r, _, resumo, _ = rodar(b, f, dec, {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "baixa",
                                            "razao_literaria": "identificada", "evidencia_razao": "razão inventada"})
        self.assertEqual((r[f[0]["id"]]["estado"], r[f[0]["id"]]["razao_literaria"]), ("revisao_recomendada", "nao_identificada"))
        self.assertEqual(resumo["descartes"]["evidencia_razao_inexistente"], 1)

    def test_style_label_on_objective_error_needs_concrete_contrary_evidence_not_lexical_overlap(self):
        b, f, dec = um_item()
        contrario = "Mais tarde, as caixas estavam arrumadas no galpão."          # §7: outra palavra, outro parágrafo
        r, _, _, _ = rodar(b, f, dec, dict(OBJETIVO, razao_literaria="indicio_contrario", evidencia_razao=contrario))
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], x["adequacao_decisao"]), ("contestada", "inadequada"))
        self.assertEqual({e["sustenta"] for e in x["evidencias_verificadas"]}, {"contestacao", "indicio_contrario"})
        # Nenhuma exigência de repetir a palavra: um indício sem palavra em comum também vale se for autêntico.
        r, _, _, _ = rodar(b, f, dec, dict(OBJETIVO, razao_literaria="indicio_contrario",
                                           evidencia_razao="Parágrafo neutro número 4, sobre a chuva e a estrada."))
        self.assertEqual(r[f[0]["id"]]["estado"], "contestada")
        # Indício inventado: não contesta e o problema segue como revisão.
        r, _, _, _ = rodar(b, f, dec, dict(OBJETIVO, razao_literaria="indicio_contrario", evidencia_razao="não existe"))
        self.assertEqual(r[f[0]["id"]]["estado"], "revisao_recomendada")

    def test_absence_of_a_visible_reason_never_contests_by_itself(self):
        b, f, dec = um_item("Intencional")
        r, _, resumo, _ = rodar(b, f, dec, dict(OBJETIVO, razao_literaria="nao_identificada"))
        self.assertEqual((r[f[0]["id"]]["estado"], resumo["resultados"]["contestada"]), ("revisao_recomendada", 0))

    def test_other_decisions_keep_their_meaning(self):
        casos = [("Aceito editorialmente", "sim", "mantida"), ("Erro confirmado", "sim", "mantida"),
                 ("Erro confirmado", "nao", "contestada"), ("Falso positivo", "sim", "contestada"),
                 ("Falso positivo", "nao", "mantida")]
        for decisao, existe, esperado in casos:
            b, f, dec = um_item(decisao)
            campos = dict(OBJETIVO, existe=existe)
            if existe == "nao":
                campos.update(natureza="nenhuma", certeza="nao_se_aplica", gravidade="nenhuma")
            r, _, _, _ = rodar(b, f, dec, campos)
            with self.subTest(decisao=decisao, existe=existe):
                self.assertEqual(r[f[0]["id"]]["estado"], esperado)

    def test_priority_is_categorical_and_depends_on_nature_certainty_and_severity(self):
        p = v41.prioridade
        self.assertEqual(p("objetivo", "clara", "media"), "alta")
        self.assertEqual(p("objetivo", "discutivel", "media"), "media")
        self.assertEqual(p("interpretativo", "clara", "media"), "media")
        self.assertEqual(p("interpretativo", "discutivel", "media"), "baixa")
        self.assertEqual(p("interpretativo", "discutivel", "alta"), "media")        # gravidade sobe um degrau
        self.assertEqual(p("objetivo", "clara", "baixa"), "media")                   # e desce um
        self.assertEqual(p("objetivo", "clara", "alta"), "alta")
        self.assertEqual(p("interpretativo", "discutivel", "baixa"), "baixa")

    def test_editorial_uncertainty_does_not_lose_the_technical_finding(self):
        b, f, dec = um_item()
        r, _, _, _ = rodar(b, f, dec, {"existe": "sim", "natureza": "interpretativo", "certeza": "discutivel",
                                       "gravidade": "baixa", "razao_literaria": "nao_identificada",
                                       "explicacao": "Alternância temporal que admite leitura de anterioridade.",
                                       "evidencia": "as caixas que estava"})
        x = r[f[0]["id"]]
        self.assertEqual((x["estado"], x["prioridade_revisao"]), ("revisao_recomendada", "baixa"))
        self.assertEqual(x["problema_tecnico"]["existe"], "sim")
        # só quando o modelo não consegue nem dizer se o problema existe é que o diagnóstico fica em aberto
        r, _, _, _ = rodar(b, f, dec, {"existe": "incerto", "evidencia_suficiente": False})
        self.assertEqual((r[f[0]["id"]]["estado"], r[f[0]["id"]]["problema_tecnico"]["existe"]), ("inconclusiva", "incerto"))


class AntecedentesTests(unittest.TestCase):
    def cenario(self):
        b = livro()
        f = alerta(b, 45, "Joel", "Contradição narrativa",
                   "O grupo tinha três pessoas, mas aqui aparece um quarto nome, Joel, que não bate com o grupo.")
        return b, f, {f["id"]: "Falso positivo"}

    def test_distant_antecedent_is_retrieved_by_relevance_not_proximity(self):
        b, f, dec = self.cenario()
        item = v41.preparar(b, [f], dec)[0][0]
        self.assertEqual([e.paragrafo for e in item["antecedentes"]][:1], [3])      # o §3, 42 parágrafos antes
        janela = {x.number for x in sum(vd._janela(b, item["_bloco"], 3), [])}
        # O mecanismo da V3/V4 (mais próximos primeiro) enche o teto com parágrafos que repetem o nome.
        antigo = v3.atender_pedido(item, {"paragrafos_solicitados": [], "termos_solicitados": ["Taro"]}, b, [], 1)
        self.assertNotIn(3, [e.paragrafo for e in antigo])
        novo = v41.recuperar_antecedentes(b, item, ["Taro"], janela, maximo=3)
        self.assertIn(3, [e.paragrafo for e in novo])                                # a hipótese do detector decide
        # Termos descritivos, sem nome algum, encontram o mesmo antecedente.
        self.assertEqual(v41.recuperar_antecedentes(b, item, ["três viajantes"], janela)[0].paragrafo, 3)

    def test_antecedent_reaches_the_model_and_distant_dependent_contradiction_is_judged_with_it(self):
        b, f, dec = self.cenario()

        def fn(usuario):
            ident = ids_do(usuario)[0]
            tem = "Eram apenas três" in usuario
            return {"avaliacoes": [base(ident, usuario, existe="sim" if tem else "incerto",
                                        natureza="interpretativo", certeza="clara" if tem else "nao_se_aplica",
                                        gravidade="alta", evidencia_suficiente=tem,
                                        explicacao="O grupo tem três; aparece um quarto nome.",
                                        evidencia="Joel")]}
        r, _, resumo, c = rodar([*b], [f], dec, fn=fn)
        x = r[f["id"]]
        self.assertEqual((len(c.pedidos), x["rodadas"], x["estado"]), (1, 1, "contestada"))   # sem chamada extra
        self.assertEqual(x["antecedentes"][0], 3)
        self.assertIn("Trechos adicionais buscados pelo Lume", c.pedidos[0])

    def test_items_of_other_categories_receive_no_automatic_antecedents(self):
        b, f, dec = um_item()
        item = v41.preparar(b, f, dec)[0][0]
        self.assertEqual(item["antecedentes"], [])
        e = v41.estimar(b, f, dec)
        self.assertEqual((e["itens_com_antecedentes_automaticos"], e["chamadas_obrigatorias_adicionais"]), (0, 0))

    def test_model_request_uses_relevance_and_runs_a_single_extra_round(self):
        b = livro()
        f = [alerta(b, 45, "Joel", "Referência ambígua", "Quem chama?")]
        dec = {f[0]["id"]: "Estilo do autor"}
        n = {"v": 0}

        def fn(usuario):
            n["v"] += 1
            ident = ids_do(usuario)[0]
            if n["v"] == 1:
                return {"avaliacoes": [base(ident, usuario, existe="incerto", evidencia_suficiente=False,
                                            precisa_mais_contexto=True, termos_solicitados=["viajantes"])]}
            return {"avaliacoes": [base(ident, usuario)]}
        r, _, resumo, c = rodar(b, f, dec, fn=fn)
        x = r[f[0]["id"]]
        self.assertEqual((x["rodadas"], len(c.pedidos), resumo["pediram_mais_contexto"]), (2, 2, 1))
        self.assertIn("Um grupo de viajantes", c.pedidos[1])
        self.assertEqual(x["pediu_mais_contexto"]["estado_primeira_rodada"], "inconclusiva")


class VinculoDasEvidenciasTests(unittest.TestCase):
    def duas(self):
        b = livro()
        texto = "O ponto principal era que ele segurava um remo. Ela olhou os remos que balançavam na água."
        b[6] = Block(7, texto, "Capítulo 1")
        i1, i2 = texto.index("era"), texto.index("balançavam")
        f = [asdict(finding(b[6], "Tempo verbal", "Verificar", i, j, "Hipótese.", "FONTE"))
             for i, j in ((i1, i1 + 3), (i2, i2 + 10))]
        return b, f, {x["id"]: "Estilo do autor" for x in f}

    def test_authentic_evidence_of_a_discarded_question_stays_in_the_record_marked(self):
        b, f, dec = self.duas()
        era, batiam = f
        mapa = {era["id"]: {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "media",
                            "razao_literaria": "indicio_contrario", "evidencia": "era que ele segurava",
                            "evidencia_razao": "Ela olhou os remos", "explicacao": "Escorregão.",
                            "problema_trecho": "balançavam na", "problema_explicacao": "Outro verbo."},
                batiam["id"]: {"existe": "sim", "natureza": "interpretativo", "certeza": "discutivel", "gravidade": "baixa",
                               "razao_literaria": "nao_identificada", "evidencia": "balançavam"}}
        c = modelo(mapa)
        with TemporaryDirectory() as pasta:
            r, _, resumo = v41.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=c)
        x = r[era["id"]]
        self.assertEqual(x["estado"], "contestada")
        self.assertIsNone(x["questao_independente"])                       # a questão não está mais ativa…
        self.assertEqual(x["questao_descartada"]["conflito_com"], batiam["id"])
        indep = [e for e in x["evidencias_verificadas"] if e["papel"] == "independente"]
        self.assertEqual(len(indep), 1)                                    # …mas a evidência continua rastreável
        self.assertEqual((indep[0]["situacao"], indep[0]["motivo"], indep[0]["vinculo_com"]),
                         ("descartada", "questao_em_conflito", batiam["id"]))
        ativas = [e for e in x["evidencias_verificadas"] if e["situacao"] == "ativa"]
        self.assertEqual({e["sustenta"] for e in ativas}, {"contestacao", "indicio_contrario"})
        self.assertTrue(all(e["sha256_paragrafo"] and e["paragrafo"] == 7 for e in x["evidencias_verificadas"]))

    def test_evidence_of_a_downgraded_contestation_is_marked_not_deleted(self):
        b, f, dec = self.duas()
        a, c2 = f
        # Dois alertas sobre o mesmo trecho com vereditos opostos: a contestação é rebaixada.
        dup = dict(a, id="outro" + a["id"][5:], category="Regência")
        dec2 = {a["id"]: "Estilo do autor", dup["id"]: "Estilo do autor"}
        mapa = {a["id"]: {"existe": "sim", "natureza": "objetivo", "certeza": "clara", "gravidade": "media",
                          "razao_literaria": "indicio_contrario", "evidencia": "era que ele",
                          "evidencia_razao": "Ela olhou os remos", "explicacao": "Erro."},
                dup["id"]: {"existe": "nao", "natureza": "nenhuma", "certeza": "nao_se_aplica", "gravidade": "nenhuma",
                            "justificativa_detector": "correta", "evidencia": ""}}
        with TemporaryDirectory() as pasta:
            r, _, resumo = v41.avaliar(b, [a, dup], dec2, pasta=pasta, teto=5, cliente=modelo(mapa))
        x = r[a["id"]]
        self.assertEqual((x["estado"], x["motivo_inconclusivo"]), ("inconclusiva", "conflito_entre_itens"))
        self.assertEqual({(e["sustenta"], e["situacao"], e["motivo"]) for e in x["evidencias_verificadas"]},
                         {("contestacao", "descartada", "contestacao_rebaixada"),
                          ("indicio_contrario", "descartada", "contestacao_rebaixada")})


class ContratoEPersistenciaTests(unittest.TestCase):
    def test_invalid_and_contradictory_responses_are_not_validations(self):
        b, f, dec = um_item()
        ident = f[0]["id"]
        quebras = {"campo": lambda u: {k: v for k, v in base(ident, u).items() if k != "natureza"},
                   "enum": lambda u: dict(base(ident, u), existe="talvez"),
                   "tipo": lambda u: dict(base(ident, u), evidencia_suficiente="sim")}
        for nome, q in quebras.items():
            with TemporaryDirectory() as pasta:
                c = Modelo(lambda u, q=q: {"avaliacoes": [q(u)]})
                r, _, resumo = v41.avaliar(b, f, dec, pasta=pasta, teto=5, cliente=c)
                with self.subTest(nome):
                    self.assertEqual((resumo["sem_resposta"], v41.planejar(b, f, dec, pasta)["situacoes"]), (1, {"nova": 1}))
        with TemporaryDirectory() as pasta:        # existe=nao com razão literária em decisão de preservação
            r, _, _, _ = rodar(b, f, dec, {"existe": "nao", "razao_literaria": "identificada"}, pasta=pasta)
            self.assertEqual((r[ident]["estado"], r[ident]["motivo"]), ("inconclusiva", "resposta_contraditoria"))

    def test_v4_results_are_neither_reused_nor_invalidated(self):
        b, f, dec = um_item()
        ident = f[0]["id"]
        with TemporaryDirectory() as pasta:
            v4.gravar(pasta, {ident: {"id": ident, "estado": "contestada", "estado_validacao": "analisada",
                                      "chave_conteudo": "x", "chave_configuracao": "y"}})
            antes = (Path(pasta) / v4.ARQUIVO).read_bytes()
            _, _, resumo, c = rodar(b, f, dec, pasta=pasta)
            self.assertEqual((resumo["reutilizadas_sem_custo"], len(c.pedidos)), (0, 1))   # contrato novo: nada reutilizado
            self.assertEqual((Path(pasta) / v4.ARQUIVO).read_bytes(), antes)               # V4 intacto
            self.assertTrue((Path(pasta) / v41.ARQUIVO).exists())
            self.assertEqual(v4.ler(pasta)[0][ident]["estado"], "contestada")              # ainda legível pela V4

    def test_reuse_and_selective_invalidation_follow_the_antecedent_by_number(self):
        b = livro()
        f = alerta(b, 45, "Joel", "Contradição narrativa", "O grupo tinha três pessoas, mas aparece um quarto nome.")
        dec = {f["id"]: "Falso positivo"}
        with TemporaryDirectory() as pasta:
            rodar(b, [f], dec, {"existe": "sim", "natureza": "interpretativo", "certeza": "clara", "gravidade": "alta",
                                "evidencia": "Joel", "explicacao": "Quarto nome."}, pasta=pasta)
            registro = v41.ler(pasta)[0][f["id"]]
            self.assertIn(3, registro["antecedentes"])
            _, _, resumo, c = rodar(b, [f], dec, pasta=pasta)
            self.assertEqual((len(c.pedidos), resumo["reutilizadas_sem_custo"]), (0, 1))
            longe = deepcopy(b)
            longe[50] = Block(52, "Texto qualquer, em outra parte do capítulo, sem relação com o alerta.", "Capítulo 1")
            self.assertEqual(v41.planejar(longe, [f], dec, pasta)["situacoes"], {"valida": 1})     # irrelevante: não invalida
            antecedente = deepcopy(b)
            antecedente[2] = Block(3, "Um grupo de viajantes parou. Eles eram quatro, agora.", "Capítulo 1")
            self.assertEqual(v41.planejar(antecedente, [f], dec, pasta)["situacoes"], {"desatualizada_conteudo": 1})
            with unittest.mock.patch.object(v41, "VERSAO_PROMPT", 2):
                plano = v41.planejar(b, [f], dec, pasta)
                self.assertEqual((plano["situacoes"], plano["a_analisar"]), ({"desatualizada_configuracao": 1}, []))

    def test_no_extra_mandatory_calls_and_economy_mechanisms_are_kept(self):
        b = livro()
        achados = [alerta(b, n, "neutro", "Regência") for n in (8, 10, 42, 50)]
        achados.append(alerta(b, 45, "Joel", "Contradição narrativa", "O grupo tinha três pessoas."))
        dec = {x["id"]: "Estilo do autor" for x in achados}
        e4 = v4.estimar(b, achados, dec)
        e41 = v41.estimar(b, achados, dec)
        self.assertEqual(e41["chamadas_primeira_rodada"], e4["chamadas_primeira_rodada"])      # mesmos lotes
        self.assertEqual(e41["chamadas_obrigatorias_adicionais"], 0)
        self.assertEqual(e41["limite_de_saida_por_pedido"], e4["limite_de_saida_por_pedido"])
        self.assertLessEqual(e41["tokens_entrada"] - e4["tokens_entrada"], 1200 / vd.CARACTERES_POR_TOKEN + 700)
        self.assertEqual(e41["itens_com_antecedentes_automaticos"], 1)
        # Sonnet único, pedidos agrupados, contexto compartilhado uma vez
        c = modelo()
        with TemporaryDirectory() as pasta:
            v41.avaliar(b, achados, dec, pasta=pasta, teto=5, cliente=c)
            modelos = {r["modelo_final"] for r in v41.ler(pasta)[0].values()}
        self.assertEqual(sum(len(ids_do(p)) for p in c.pedidos), 5)
        self.assertLess(len(c.pedidos), 5)
        self.assertEqual(modelos, {v41.MODELO})

    def test_decisions_manuscript_and_findings_are_untouched_and_state_has_no_paragraphs(self):
        b, f, dec = um_item()
        antes = (deepcopy(f), deepcopy(dec), [x.text for x in b])
        with TemporaryDirectory() as pasta:
            rodar(b, f, dec, dict(OBJETIVO, razao_literaria="nao_identificada"), pasta=pasta)
            conteudo = (Path(pasta) / v41.ARQUIVO).read_text(encoding="utf-8")
        self.assertEqual((f, dec, [x.text for x in b]), antes)
        self.assertNotIn(ALVO, conteudo)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
