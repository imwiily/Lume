"""Coerência 2.0 experimental: verificação local e casos sintéticos.

ATENÇÃO: todas as respostas do modelo aqui são SIMULADAS, escritas à mão como um bom auditor responderia.
Estes testes provam a infraestrutura (citações conferidas, rebaixamento, cobertura, cache, custo, imutabilidade).
Eles NÃO medem a capacidade do Claude nem a precisão editorial. Nenhuma chamada de rede é feita.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coerencia.leitura import ler_paragrafos
from coerencia.modelo import Claude, Orcamento, RespostaCortada
from coerencia2 import auditoria as aud


class ModeloSimulado:
    def __init__(self, resposta=None, erro=None, modelo="claude-sonnet-5-5"):
        self.resposta, self.erro, self.modelo, self.esforco = resposta, erro, modelo, "medium"
        self.chamadas, self.pedidos = [], []

    def json(self, sistema, usuario, esquema, etapa):
        self.pedidos.append(usuario)
        if self.erro:
            raise self.erro
        self.chamadas.append({"etapa": etapa, "modelo_usado": self.modelo, "custo_usd": 0.05})
        return deepcopy(self.resposta)


def ev(paragrafo, trecho, papel="ocorrencia"):
    return {"paragrafo": paragrafo, "trecho": trecho, "papel": papel}


def apontamento(categoria, evidencias, natureza="contradicao", prioridade="atencao", certeza="alta",
                relevancia="", intencional=False, explicacao="Os dois trechos não combinam."):
    return {"categoria": categoria, "natureza": natureza, "prioridade": prioridade, "certeza": certeza,
            "titulo": "t", "explicacao": explicacao, "evidencias": evidencias, "relevancia_da_lacuna": relevancia,
            "pode_ser_intencional": intencional, "leituras_alternativas": ""}


def resposta(apontamentos=(), descartados=()):
    return {"apontamentos": list(apontamentos), "fenomenos_descartados": list(descartados)}


def rodar(textos, simulado, **opcoes):
    return aud.auditar(ler_paragrafos(textos), simulado, titulo="Obra fictícia", **opcoes)


# Cada caso: parágrafos (ficção escrita para os testes) e a resposta simulada de um auditor cuidadoso.
CASO_1_CONTRADICAO = ["Capítulo 1", "Marcos tinha os olhos verdes, herança da mãe.", "O barco partiu ao amanhecer.",
                      "Capítulo 4", "Os olhos castanhos de Marcos acompanharam a chegada do barco."]
CASO_2_ESPACO = ["Capítulo 1", "Na manhã de terça, Lia ainda estava presa no vilarejo, sem estrada nem barco.",
                 "Capítulo 2", "Lia desembarcou no cais da capital e cumprimentou o tio, como se tivesse chegado havia dias."]
CASO_3_CAUSAL = ["Capítulo 1", "A ponte desabou durante a noite, levando a única estrada do vale.",
                 "Capítulo 2", "No dia seguinte, o caminhão de entregas chegou à praça como todas as manhãs."]
CASO_4_ESQUECIDO = ["Capítulo 1", "Nina prometeu ao menino febril que voltaria com o remédio antes do anoitecer.",
                    "Capítulo 2", "Nina passou a tarde ajustando o vestido para a festa da praça.",
                    "Capítulo 3", "A festa terminou com fogos e todos dançaram até tarde."]
CASO_5_CONHECIMENTO = ["Capítulo 1", "Beto escondeu o diário atrás do armário sem que ninguém o visse.",
                       "Capítulo 2", "Clara, recém-chegada da estação, perguntou a Beto por que o diário estava atrás do armário."]
CASO_6_MISTERIO = ["Capítulo 1", "O bilhete deixado na mesa não tinha assinatura, e ninguém descobriu quem o escrevera.",
                   "Epílogo", "Até hoje a autoria do bilhete permanece desconhecida."]
CASO_7_EXPLICADA = ["Capítulo 1", "Lúcio usava o cabelo comprido, preso por uma fita.",
                    "Capítulo 5", "Depois de seis meses no mar, Lúcio raspou a cabeça para aguentar o calor."]
CASO_8_SONHO = ["Capítulo 1", "Rosa sabia que o pai morrera no inverno anterior.",
                "Capítulo 2", "No sonho, o pai de Rosa abriu a porta da cozinha e lhe serviu café."]
CASO_9_CARGOS = ["Capítulo 1", "Henrique era o diretor do hospital da cidade.",
                 "Capítulo 3", "Henrique, professor da faculdade de medicina, abriu a aula com um silêncio longo."]
CASO_10_INACABADA = ["Capítulo 3", "A estrangeira deixou uma mala fechada no armário e partiu sem dizer para onde."]


class CasosSinteticos(unittest.TestCase):
    def test_1_contradicao_factual_entre_capitulos(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta([apontamento(
            "fato_incompativel", [ev(2, "tinha os olhos verdes", "anterior"), ev(5, "olhos castanhos de Marcos")])])))
        self.assertEqual(r["cobertura"]["tipo"], "global")
        (a,) = r["apontamentos"]
        self.assertEqual((a["situacao"], a["destino"], a["impeditivo"]), ("sustentada", "informacao", False))
        self.assertEqual([e["paragrafo"] for e in a["evidencias"]], [2, 5])
        self.assertEqual(a["evidencias"][1]["texto_original"], "olhos castanhos de Marcos")

    def test_2_transicao_espacial_sem_explicacao(self):
        r = rodar(CASO_2_ESPACO, ModeloSimulado(resposta([apontamento(
            "continuidade_espacial_temporal", [ev(2, "ainda estava presa no vilarejo"), ev(4, "desembarcou no cais da capital")],
            natureza="lacuna", certeza="media", intencional=True,
            relevancia="Lia estava sem estrada nem barco e aparece na capital sem que a viagem seja mostrada.")])))
        (a,) = r["apontamentos"]
        self.assertEqual((a["natureza"], a["situacao"]), ("lacuna", "sustentada"))
        self.assertIn("pode ser intencional", a["aviso"])
        self.assertTrue(a["pode_ser_intencional"])

    def test_3_quebra_causal(self):
        r = rodar(CASO_3_CAUSAL, ModeloSimulado(resposta([apontamento(
            "continuidade_causal", [ev(2, "ponte desabou durante a noite"), ev(4, "caminhão de entregas chegou à praça")],
            natureza="lacuna", certeza="media", relevancia="A única estrada do vale caiu e a entrega chega normalmente.")])))
        self.assertEqual(r["apontamentos"][0]["categoria"], "continuidade_causal")

    def test_4_consequencia_esquecida(self):
        r = rodar(CASO_4_ESQUECIDO, ModeloSimulado(resposta([apontamento(
            "evento_abandonado", [ev(2, "voltaria com o remédio antes do anoitecer")], natureza="lacuna", prioridade="sugestao",
            certeza="media", relevancia="O menino febril depende do remédio prometido e nunca mais aparece.",
            intencional=True)])))
        (a,) = r["apontamentos"]
        self.assertEqual((a["situacao"], a["prioridade"], a["destino"]), ("sustentada", "sugestao", "diagnostico"))

    def test_5_conhecimento_indevido(self):
        r = rodar(CASO_5_CONHECIMENTO, ModeloSimulado(resposta([apontamento(
            "conhecimento_do_personagem", [ev(2, "escondeu o diário atrás do armário", "anterior"),
                                           ev(4, "por que o diário estava atrás do armário")],
            natureza="lacuna", certeza="media", relevancia="Ninguém viu Beto esconder o diário e Clara acabou de chegar.")])))
        self.assertEqual(r["apontamentos"][0]["categoria"], "conhecimento_do_personagem")

    def test_6_misterio_nao_resolvido_nao_gera_erro(self):
        r = rodar(CASO_6_MISTERIO, ModeloSimulado(resposta(descartados=[
            {"tipo": "misterio", "paragrafo": 2, "resumo": "A autoria do bilhete é reservada pela narrativa."}])))
        self.assertEqual(r["apontamentos"], [])
        self.assertEqual(r["fenomenos_descartados_pelo_modelo"][0]["tipo"], "misterio")

    def test_6b_lacuna_sem_relevancia_vira_inconclusiva(self):
        r = rodar(CASO_6_MISTERIO, ModeloSimulado(resposta([apontamento(
            "clareza_contextual", [ev(2, "ninguém descobriu quem o escrevera")], natureza="lacuna", relevancia="")])))
        (a,) = r["apontamentos"]
        self.assertEqual((a["situacao"], a["destino"]), ("inconclusiva", "diagnostico"))

    def test_7_mudanca_explicada(self):
        r = rodar(CASO_7_EXPLICADA, ModeloSimulado(resposta(descartados=[
            {"tipo": "mudanca_explicada", "paragrafo": 4, "resumo": "O corte vem explicado pelo tempo no mar."}])))
        self.assertEqual(r["apontamentos"], [])

    def test_8_sonho_explica_a_aparente_contradicao(self):
        r = rodar(CASO_8_SONHO, ModeloSimulado(resposta(descartados=[
            {"tipo": "sonho_ou_lembranca", "paragrafo": 4, "resumo": "O pai aparece em sonho."}])))
        self.assertEqual(r["apontamentos"], [])
        self.assertEqual(r["cobertura"]["tipo"], "global")

    def test_9_cargos_diferentes_e_compativeis(self):
        r = rodar(CASO_9_CARGOS, ModeloSimulado(resposta(descartados=[
            {"tipo": "compativel", "paragrafo": 4, "resumo": "Diretor e professor podem coexistir."}])))
        self.assertEqual(r["apontamentos"], [])

    def test_10_obra_inacabada_e_informada_ao_modelo(self):
        modelo = ModeloSimulado(resposta(descartados=[{"tipo": "em_aberto", "paragrafo": 2, "resumo": "A mala segue em aberto."}]))
        r = rodar(CASO_10_INACABADA, modelo, inacabada=True)
        self.assertEqual(r["apontamentos"], [])
        self.assertTrue(r["obra_inacabada"])
        self.assertIn("OBRA INACABADA: sim", modelo.pedidos[0])


class Verificacao(unittest.TestCase):
    def test_citacao_inexistente_e_rejeitada(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta([apontamento(
            "fato_incompativel", [ev(2, "tinha os olhos azuis do pai"), ev(5, "olhos pretos de Marcos")])])))
        self.assertEqual(r["apontamentos"], [])
        self.assertEqual(r["rejeitados_pela_verificacao"][0]["motivo"], "sem_evidencia_verificavel")

    def test_evidencia_parcial_rebaixa_para_inconclusiva(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta([apontamento(
            "fato_incompativel", [ev(2, "tinha os olhos verdes"), ev(5, "olhos pretos de Marcos")])])))
        (a,) = r["apontamentos"]
        self.assertEqual((a["situacao"], a["destino"]), ("inconclusiva", "diagnostico"))
        self.assertEqual(a["evidencias_rejeitadas"][0]["motivo"], "trecho_inexistente")
        self.assertEqual(len(a["evidencias"]), 1)

    def test_trecho_ambiguo_e_rejeitado(self):
        textos = ["Capítulo 1", "Ele olhou o relógio e olhou o relógio de novo, sem entender a hora."]
        e = aud.verificar_evidencia(ler_paragrafos(textos), ev(2, "olhou o relógio"))
        self.assertEqual((e["valida"], e["motivo"]), (False, "ambigua"))

    def test_paragrafo_incorreto_nao_e_realocado(self):
        e = aud.verificar_evidencia(ler_paragrafos(CASO_1_CONTRADICAO), ev(3, "olhos castanhos de Marcos"))
        self.assertEqual((e["valida"], e["motivo"]), (False, "paragrafo_incorreto"))
        self.assertEqual(aud.verificar_evidencia(ler_paragrafos(CASO_1_CONTRADICAO), ev(99, "olhos verdes"))["motivo"],
                         "paragrafo_inexistente")
        self.assertEqual(aud.verificar_evidencia(ler_paragrafos(CASO_1_CONTRADICAO), ev(2, "olhos"))["motivo"], "trecho_curto")

    def test_localizacao_exata_tolera_aspas_caixa_e_espacos(self):
        textos = ["Capítulo 1", "Ela disse: “Não   volto  mais”, e saiu — sem olhar para trás."]
        e = aud.verificar_evidencia(ler_paragrafos(textos), ev(2, '"não volto mais"'))
        self.assertTrue(e["valida"])
        self.assertEqual(e["texto_original"], "“Não   volto  mais”")
        bloco = ler_paragrafos(textos)[1].texto
        self.assertEqual(bloco[e["inicio"]:e["fim"]], e["texto_original"])
        self.assertTrue(aud.verificar_evidencia(ler_paragrafos(textos), ev(2, "saiu - sem olhar para trás"))["valida"])

    def test_numeracao_com_saltos_do_fonte(self):
        # O FONTE numera todos os parágrafos do arquivo e pula os vazios: os números não são posições.
        from coerencia.leitura import Paragrafo
        ps = [Paragrafo(1, "Capítulo 1", "Capítulo 1", True), Paragrafo(2, "Marcos tinha os olhos verdes.", "Capítulo 1"),
              Paragrafo(5, "Os olhos castanhos de Marcos brilharam.", "Capítulo 1"), Paragrafo(6, "Fim.", "Capítulo 1")]
        e = aud.verificar_evidencia(ps, ev(5, "olhos castanhos de Marcos"))
        self.assertTrue(e["valida"])
        self.assertEqual(e["texto_original"], "olhos castanhos de Marcos")
        self.assertEqual(aud.verificar_evidencia(ps, ev(3, "olhos castanhos de Marcos"))["motivo"], "paragrafo_inexistente")
        self.assertEqual(aud.verificar_evidencia(ps, ev(4, "olhos castanhos de Marcos"))["motivo"], "paragrafo_inexistente")
        self.assertEqual(aud.verificar_evidencia(ps, ev(2, "olhos castanhos de Marcos"))["motivo"], "paragrafo_incorreto")

    def test_formato_invalido_e_descartado(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado({"apontamentos": [{"categoria": "inventada"}, "texto", None],
                                                      "fenomenos_descartados": []}))
        self.assertEqual(r["apontamentos"], [])
        self.assertEqual([x["motivo"] for x in r["rejeitados_pela_verificacao"]], ["formato_invalido"] * 3)

    def test_nada_e_impeditivo(self):
        itens = [apontamento("fato_incompativel", [ev(2, "tinha os olhos verdes"), ev(5, "olhos castanhos de Marcos")], certeza=c)
                 for c in ("alta", "baixa")]
        itens[1]["evidencias"] = [ev(5, "olhos castanhos de Marcos"), ev(2, "O barco partiu ao amanhecer")]
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta(itens)))
        self.assertTrue(r["apontamentos"])
        self.assertTrue(all(a["impeditivo"] is False and a["destino"] in ("informacao", "diagnostico") for a in r["apontamentos"]))


class Infraestrutura(unittest.TestCase):
    def test_ids_e_ordem_estaveis_com_resposta_embaralhada(self):
        a = apontamento("fato_incompativel", [ev(2, "tinha os olhos verdes"), ev(5, "olhos castanhos de Marcos")],
                        explicacao="Cor dos olhos diferente.")
        b = apontamento("continuidade_causal", [ev(3, "O barco partiu ao amanhecer"), ev(5, "chegada do barco")],
                        natureza="lacuna", prioridade="sugestao", relevancia="x", explicacao="Outra frase.")
        um = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta([a, b])))
        dois = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta([dict(b, explicacao="Texto diferente"), a, a])))
        self.assertEqual([x["id"] for x in um["apontamentos"]], [x["id"] for x in dois["apontamentos"]])
        self.assertEqual(len(dois["apontamentos"]), 2)          # duplicata removida

    def test_manuscrito_nao_e_alterado(self):
        paragrafos = ler_paragrafos(CASO_1_CONTRADICAO)
        antes, assinatura = deepcopy(paragrafos), aud.assinatura(paragrafos)
        aud.auditar(paragrafos, ModeloSimulado(resposta([apontamento(
            "fato_incompativel", [ev(2, "tinha os olhos verdes"), ev(5, "olhos castanhos de Marcos")])])))
        self.assertEqual(paragrafos, antes)
        self.assertEqual(aud.assinatura(paragrafos), assinatura)

    def test_acima_do_limite_nada_e_enviado_nem_anunciado_como_global(self):
        modelo = ModeloSimulado(resposta())
        r = aud.auditar(ler_paragrafos(["Capítulo 1", "palavra " * 200]), modelo, limite_caracteres=500)
        self.assertEqual((r["cobertura"]["tipo"], modelo.pedidos), ("nao_realizada", []))
        self.assertIn("não foi feita", r["cobertura"]["motivo"])
        self.assertNotIn("paragrafos_enviados", r["cobertura"])

    def test_resposta_cortada_e_cobertura_incompleta(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(erro=RespostaCortada("cortada")))
        self.assertEqual((r["cobertura"]["tipo"], r["apontamentos"]), ("incompleta", []))

    def test_cache_evita_segunda_chamada(self):
        with tempfile.TemporaryDirectory() as pasta:
            primeiro = ModeloSimulado(resposta([apontamento(
                "fato_incompativel", [ev(2, "tinha os olhos verdes"), ev(5, "olhos castanhos de Marcos")])]))
            a = rodar(CASO_1_CONTRADICAO, primeiro, pasta=pasta)
            segundo = ModeloSimulado(resposta())
            b = rodar(CASO_1_CONTRADICAO, segundo, pasta=pasta)
            self.assertEqual((segundo.pedidos, b["do_cache"], b["custo_usd"]), ([], True, 0.0))
            self.assertEqual([x["id"] for x in a["apontamentos"]], [x["id"] for x in b["apontamentos"]])
            alterado = ModeloSimulado(resposta())
            rodar(CASO_1_CONTRADICAO[:-1] + ["Os olhos azuis de Marcos."], alterado, pasta=pasta)
            self.assertEqual(len(alterado.pedidos), 1)           # texto mudou: cache não vale

    def test_janela_considera_pedido_inteiro_e_saida_reservada(self):
        # Poucos caracteres de texto, mas o pedido estimado não cabe na janela: nada é enviado.
        modelo = ModeloSimulado(resposta())
        ps = ler_paragrafos(["Capítulo 1"] + ["Ele foi." for _ in range(400)])
        r = aud.auditar(ps, modelo, janela_tokens=aud.MAX_TOKENS + 3000)
        self.assertEqual((r["cobertura"]["tipo"], modelo.pedidos), ("nao_realizada", []))
        self.assertIn("janela", r["cobertura"]["motivo"])
        e = aud.estimar(ps, janela_tokens=aud.MAX_TOKENS + 3000)
        self.assertEqual((e["cabe_em_uma_leitura"], e["custo_maximo_usd"]), (False, None))

    def test_cache_invalida_com_instrucoes_esquema_modelo_esforco_e_texto(self):
        from unittest import mock
        ps = ler_paragrafos(CASO_1_CONTRADICAO)
        base = aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", False)
        self.assertEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", False))
        self.assertNotEqual(base, aud._chave_cache(ps, "claude-opus-5-5", "medium", "t", False))
        self.assertNotEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "high", "t", False))
        self.assertNotEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", True))
        with mock.patch.object(aud, "SISTEMA", aud.SISTEMA + " Nova regra."):
            self.assertNotEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", False))
        with mock.patch.object(aud, "ESQUEMA", {**aud.ESQUEMA, "required": ["apontamentos"]}):
            self.assertNotEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", False))
        for campo in ("VERSAO_PROMPT", "VERSAO_RESULTADO"):
            with mock.patch.object(aud, campo, "outra"):
                self.assertNotEqual(base, aud._chave_cache(ps, "claude-sonnet-5-5", "medium", "t", False))

    def test_reserva_maxima_nao_e_o_gasto_esperado(self):
        e = aud.estimar(ler_paragrafos(CASO_1_CONTRADICAO))
        self.assertLess(e["custo_esperado_usd"], e["custo_maximo_usd"])
        self.assertLess(e["custo_maximo_usd"], e["custo_maximo_com_retomada_usd"])

    def test_estimativa_sem_rede(self):
        e = aud.estimar(ler_paragrafos(CASO_1_CONTRADICAO))
        self.assertTrue(e["cabe_em_uma_leitura"])
        self.assertGreater(e["custo_maximo_usd"], e["custo_esperado_usd"])
        grande = aud.estimar(ler_paragrafos(["Capítulo 1", "x " * 5000]), limite_caracteres=100)
        self.assertEqual((grande["cabe_em_uma_leitura"], grande["custo_maximo_usd"]), (False, None))


class ClienteClaude(unittest.TestCase):
    """Usa o cliente real do Coerencia com a API substituída: pedido, modelo que respondeu e teto."""

    @staticmethod
    def api(texto, modelo="claude-sonnet-5-5"):
        uso = SimpleNamespace(input_tokens=2000, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=800)
        r = SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], usage=uso, stop_reason="end_turn",
                            model=modelo, _request_id="req_teste")
        pedidos = []
        criar = lambda **p: (pedidos.append(p), r)[1]
        return SimpleNamespace(messages=SimpleNamespace(create=criar), beta=SimpleNamespace(messages=SimpleNamespace(create=criar))), pedidos

    def test_pedido_modelo_esforco_e_modelo_que_respondeu(self):
        import json
        api, pedidos = self.api(json.dumps(resposta()), modelo="claude-opus-5")      # retomada automática respondeu
        cliente = Claude("claude-sonnet-5-5", esforco="medium", cliente=api, orcamento=Orcamento(5.0))
        r = rodar(CASO_1_CONTRADICAO, cliente)
        p = pedidos[0]
        self.assertEqual((p["model"], p["output_config"]["effort"]), ("claude-sonnet-5-5", "medium"))
        self.assertIs(p["output_config"]["format"]["schema"]["additionalProperties"], False)
        self.assertIn("[§2] Marcos tinha os olhos verdes", p["messages"][0]["content"])
        self.assertEqual((r["modelo_solicitado"], r["modelos_que_responderam"]), ("claude-sonnet-5-5", ["claude-opus-5"]))
        self.assertGreater(r["custo_usd"], 0)

    def test_uso_de_tokens_e_registrado_como_medido(self):
        import json
        uso = SimpleNamespace(input_tokens=1000, cache_read_input_tokens=500, cache_creation_input_tokens=300, output_tokens=200)
        resp = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(resposta()))], usage=uso,
                               stop_reason="end_turn", model="claude-sonnet-5-5", _request_id="req_x")
        criar = lambda **p: resp
        api = SimpleNamespace(messages=SimpleNamespace(create=criar), beta=SimpleNamespace(messages=SimpleNamespace(create=criar)))
        with tempfile.TemporaryDirectory() as pasta:
            r = rodar(CASO_1_CONTRADICAO, Claude("claude-sonnet-5-5", cliente=api), pasta=pasta)
            u = r["uso"]
            self.assertEqual((u["fonte"], u["tokens_entrada_total"], u["tokens_cache_leitura"], u["tokens_cache_criacao"],
                              u["tokens_entrada_sem_cache"], u["tokens_saida"]), ("api", 1800, 500, 300, 1000, 200))
            self.assertEqual((u["modelos"], u["chamadas"][0]["pedido"], u["custo_usd"]), (["claude-sonnet-5-5"], "req_x", r["custo_usd"]))
            segundo = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta()), pasta=pasta)     # cache: nada medido agora
            self.assertEqual((segundo["uso"]["fonte"], segundo["uso"]["tokens_saida"]), ("nenhuma_chamada", 0))
            self.assertEqual(segundo["uso_da_resposta_em_cache"]["tokens_saida"], 200)

    def test_uso_nao_informado_fica_desconhecido_e_resultado_antigo_e_compativel(self):
        r = rodar(CASO_1_CONTRADICAO, ModeloSimulado(resposta()))           # o simulado só informa modelo e custo
        self.assertEqual((r["uso"]["fonte"], r["uso"]["tokens_saida"], r["uso"]["tokens_entrada_total"]), ("nao_registrado", None, None))
        antigo = {"custo_usd": 0.11934, "modelos_que_responderam": ["claude-sonnet-5-5"]}   # resultado sem o campo `uso`
        u = aud.uso_do_resultado(antigo)
        self.assertEqual((u["fonte"], u["tokens_saida"], u["tokens_cache_leitura"], u["custo_usd"]),
                         ("nao_registrado", None, None, 0.11934))
        self.assertEqual(u["modelos"], ["claude-sonnet-5-5"])

    def test_teto_baixo_impede_o_envio(self):
        api, pedidos = self.api("{}")
        r = rodar(CASO_1_CONTRADICAO, Claude("claude-sonnet-5-5", cliente=api, orcamento=Orcamento(0.0001)))
        self.assertEqual((pedidos, r["cobertura"]["tipo"]), ([], "nao_realizada"))
        self.assertIn("TetoAtingido", r["cobertura"]["motivo"])


class LimiteDeSaida(unittest.TestCase):
    """`max_tokens` configurável por execução, só no cliente experimental."""

    @staticmethod
    def api(texto='{"apontamentos": [], "fenomenos_descartados": []}', motivo="end_turn", saida=500):
        uso = SimpleNamespace(input_tokens=1000, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=saida)
        r = SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], usage=uso, stop_reason=motivo,
                            model="claude-sonnet-5-5", _request_id="req_t")
        pedidos = []
        criar = lambda **p: (pedidos.append(p), r)[1]
        return SimpleNamespace(messages=SimpleNamespace(create=criar),
                               beta=SimpleNamespace(messages=SimpleNamespace(create=criar))), pedidos

    def test_padrao_16000_e_alternativos_vao_na_requisicao_e_no_resultado(self):
        import coerencia.modelo as compartilhado
        from coerencia2.uma_requisicao import UmaRequisicao
        for valor in (None, 24000, 32000):
            with self.subTest(max_tokens=valor):
                api, pedidos = self.api()
                opcoes = {} if valor is None else {"max_tokens": valor}
                r = rodar(CASO_1_CONTRADICAO, UmaRequisicao("claude-sonnet-5-5", cliente=api, orcamento=Orcamento(5.0), **opcoes))
                esperado = valor or 16000
                self.assertEqual((pedidos[0]["max_tokens"], r["max_tokens"]), (esperado, esperado))
                self.assertEqual(compartilhado.MAX_TOKENS, 16000)            # o módulo compartilhado não fica alterado

    def test_valor_invalido_e_recusado(self):
        from coerencia2.uma_requisicao import UmaRequisicao
        for ruim in (0, 999, 64001, "24000", True):
            with self.subTest(ruim=ruim), self.assertRaises(ValueError):
                UmaRequisicao("claude-sonnet-5-5", cliente=object(), max_tokens=ruim)

    def test_reserva_cresce_com_o_limite_e_o_orcamento_bloqueia_antes_do_envio(self):
        from coerencia2.uma_requisicao import UmaRequisicao
        ps = ler_paragrafos(CASO_1_CONTRADICAO)
        reservas = {m: aud.estimar(ps, max_tokens=m)["custo_maximo_usd"] for m in (16000, 24000, 32000)}
        self.assertLess(reservas[16000], reservas[24000])
        self.assertLess(reservas[24000], reservas[32000])
        self.assertAlmostEqual(reservas[32000] - reservas[16000], 16000 * 10 / 1e6, places=3)   # Sonnet: US$ 10 por milhão
        # a estimativa e o cliente usam a mesma conta
        api, pedidos = self.api()
        cliente = UmaRequisicao("claude-sonnet-5-5", cliente=api, orcamento=Orcamento(reservas[32000] - 0.01), max_tokens=32000)
        r = rodar(CASO_1_CONTRADICAO, cliente)
        self.assertEqual((pedidos, r["cobertura"]["tipo"]), ([], "nao_realizada"))
        self.assertIn("TetoAtingido", r["cobertura"]["motivo"])
        api, pedidos = self.api()
        ok = UmaRequisicao("claude-sonnet-5-5", cliente=api, orcamento=Orcamento(reservas[32000] + 0.01), max_tokens=32000)
        self.assertEqual(rodar(CASO_1_CONTRADICAO, ok)["cobertura"]["tipo"], "global")

    def test_janela_considera_o_limite_configurado(self):
        ps = ler_paragrafos(CASO_1_CONTRADICAO)
        e = aud.estimar(ps, janela_tokens=20000, max_tokens=24000)
        self.assertEqual((e["cabe_em_uma_leitura"], e["custo_maximo_usd"]), (False, None))
        self.assertIn("24000", e["motivo_se_nao_cabe"])
        self.assertTrue(aud.estimar(ps, janela_tokens=40000, max_tokens=24000)["cabe_em_uma_leitura"])

    def test_cache_invalida_com_outro_limite_e_preserva_o_padrao(self):
        ps = ler_paragrafos(CASO_1_CONTRADICAO)
        chave = lambda *a: aud._chave_cache(ps, "claude-sonnet-5-5", "high", "t", False, *a)
        self.assertEqual(chave(), chave(16000))                  # caches anteriores continuam valendo
        self.assertNotEqual(chave(16000), chave(24000))
        self.assertNotEqual(chave(24000), chave(32000))

    def test_resposta_truncada_nao_e_analise_global_e_nao_repete(self):
        from coerencia2.uma_requisicao import UmaRequisicao
        api, pedidos = self.api(texto='{"apontamentos": [{"categoria"', motivo="max_tokens", saida=24000)
        with tempfile.TemporaryDirectory() as pasta:
            r = rodar(CASO_1_CONTRADICAO, UmaRequisicao("claude-sonnet-5-5", esforco="high", cliente=api,
                                                        orcamento=Orcamento(5.0), max_tokens=24000), pasta=pasta)
            self.assertEqual(len(pedidos), 1)
            self.assertEqual((r["cobertura"]["tipo"], r["apontamentos"], r["max_tokens"]), ("incompleta", [], 24000))
            self.assertNotIn("paragrafos_enviados", r["cobertura"])
            self.assertEqual((r["uso"]["tokens_saida"], r["esforco"]), (24000, "high"))
            self.assertFalse((Path(pasta) / "cache-global.json").exists())     # nada aproveitável a guardar

    def test_resultado_anterior_sem_max_tokens_e_desconhecido(self):
        self.assertIsNone(aud.max_tokens_do_resultado({"custo_usd": 0.1}))
        self.assertEqual(aud.max_tokens_do_resultado({"max_tokens": 24000}), 24000)

    def test_sdk_aceita_limite_alto_sem_streaming_com_a_configuracao_do_cliente(self):
        import anthropic
        import httpx2 as httpx
        corpo = {"id": "m", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "stop_reason": "end_turn",
                 "content": [{"type": "text", "text": '{"apontamentos": [], "fenomenos_descartados": []}'}],
                 "usage": {"input_tokens": 10, "output_tokens": 5}}
        vistos = []

        def responder(req):
            import json as _json
            vistos.append(_json.loads(req.content)["max_tokens"])
            return httpx.Response(200, json=corpo)
        sdk = anthropic.Anthropic(api_key="chave-de-teste", timeout=600, max_retries=0,       # como o `Claude` o constrói
                                  http_client=httpx.Client(transport=httpx.MockTransport(responder)))
        from coerencia2.uma_requisicao import UmaRequisicao
        r = rodar(CASO_1_CONTRADICAO, UmaRequisicao("claude-sonnet-5-5", cliente=sdk, orcamento=Orcamento(5.0), max_tokens=32000))
        self.assertEqual((vistos, r["cobertura"]["tipo"]), ([32000], "global"))


class UmaRequisicaoTests(unittest.TestCase):
    def test_sem_repeticao_sem_verificacao_e_sem_retomada_no_servidor(self):
        import anthropic
        import httpx
        from coerencia2.uma_requisicao import UmaRequisicao
        chamadas = []

        def criar(**pedido):
            chamadas.append(pedido)
            req = httpx.Request("POST", "https://api.exemplo/v1/messages")
            raise anthropic.RateLimitError("limite", response=httpx.Response(429, request=req), body=None)
        api = SimpleNamespace(messages=SimpleNamespace(create=criar), beta=SimpleNamespace(messages=SimpleNamespace(create=criar)),
                              models=SimpleNamespace(retrieve=lambda *a: chamadas.append("verificar")))
        cliente = UmaRequisicao("claude-sonnet-5-5", esforco="medium", cliente=api, orcamento=Orcamento(5.0))
        cliente.verificar()
        r = rodar(CASO_1_CONTRADICAO, cliente)
        self.assertEqual(len(chamadas), 1)                           # uma requisição; sem `retrieve`; sem 2ª tentativa
        self.assertEqual(cliente.requisicoes, 1)
        self.assertNotIn("fallbacks", chamadas[0])
        self.assertNotIn("betas", chamadas[0])
        self.assertEqual((chamadas[0]["model"], chamadas[0]["output_config"]["effort"]), ("claude-sonnet-5-5", "medium"))
        self.assertEqual(r["cobertura"]["tipo"], "nao_realizada")
        self.assertIn("RateLimitError", r["cobertura"]["motivo"])

    def test_uma_requisicao_bem_sucedida_registra_uso(self):
        import json
        from coerencia2.uma_requisicao import UmaRequisicao
        api, pedidos = ClienteClaude.api(json.dumps(resposta()))
        r = rodar(CASO_1_CONTRADICAO, UmaRequisicao("claude-sonnet-5-5", cliente=api, orcamento=Orcamento(5.0)))
        self.assertEqual((len(pedidos), r["cobertura"]["tipo"], r["uso"]["tokens_saida"]), (1, "global", 800))


if __name__ == "__main__":
    unittest.main()
