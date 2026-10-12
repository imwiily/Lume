"""Preparação do teste de repetibilidade do Opus direto: análise de estabilidade e execução de uma
rodada com cliente simulado. Nenhuma chamada à API; textos sintéticos."""
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from fonte import validador_v3 as v3
import test_validador_v3 as T

ALVO = Path(__file__).resolve().parents[2] / "scripts" / "repetibilidade_opus.py"
spec = importlib.util.spec_from_file_location("repetibilidade_opus", ALVO)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def reg(estado, procede="sim", coerente="nao", editorial="ausente"):
    return {"estado": estado, "avaliacao": {"procede": procede, "decisao_coerente": coerente,
                                            "justificativa_editorial": editorial}}


class EstabilidadeTests(unittest.TestCase):
    def test_distinguishes_stable_label_only_and_interpretive_changes(self):
        r1 = {"a": reg("contestada"), "b": reg("apontamento_inadequado", "nao", "sim", "nao_se_aplica"),
              "c": reg("inconclusiva", "sim", "incerto", "incerta"), "d": reg("mantida", "nao", "sim", "nao_se_aplica")}
        r2 = {"a": reg("contestada"), "b": reg("mantida", "nao", "sim", "nao_se_aplica"),            # só rótulo
              "c": reg("contestada"),                                                                # interpretação
              "d": reg("mantida", "nao", "sim", "nao_se_aplica")}
        r3 = {"a": reg("contestada"), "b": reg("apontamento_inadequado", "nao", "sim", "nao_se_aplica"),
              "c": reg("inconclusiva", "sim", "incerto", "incerta"), "d": reg("mantida", "nao", "sim", "nao_se_aplica")}
        itens, resumo = R.estabilidade([r1, r2, r3])
        self.assertEqual([itens[k]["tipo"] for k in "abcd"], ["estavel", "so_rotulo", "interpretacao", "estavel"])
        self.assertEqual((resumo["estaveis"], resumo["so_rotulo"], resumo["interpretacao"]), (2, 1, 1))
        self.assertTrue(itens["c"]["cruza_contestacao"])
        self.assertFalse(itens["b"]["cruza_contestacao"])           # rótulo B↔C não cruza a contestação
        self.assertEqual(itens["c"]["concordancia"], .667)

    def test_missing_item_in_a_round_counts_as_unstable(self):
        itens, resumo = R.estabilidade([{"a": reg("contestada")}, {}])
        self.assertEqual(itens["a"]["tipo"], "interpretacao")
        self.assertEqual(resumo["estaveis"], 0)


class RodadaTests(unittest.TestCase):
    def cliente(self):
        return T.Modelo(v3.OPUS, T.opus())

    def test_round_writes_isolated_folder_with_raw_calls_and_no_manuscript_text(self):
        b, achados, dec = T.cenario()
        with TemporaryDirectory() as base:
            c = self.cliente()
            c.chamadas = []
            r, _, resumo = R.rodar_rodada(b, list(achados.values()), dec, 1, base, 2.0, cliente=c,
                                          meta={"documento": "x.docx"})
            pasta = Path(base) / "r1"
            self.assertEqual((resumo["avaliadas"], resumo["pedidos"]), (3, 1))
            brutas = json.loads((pasta / "chamadas-brutas-r1.json").read_text(encoding="utf-8"))
            self.assertEqual(len(brutas), 1)
            self.assertEqual(set(brutas[0]), {"etapa", "pedido", "modelo_usado", "tokens_entrada", "tokens_cache",
                                              "tokens_cache_criacao", "tokens_saida", "segundos", "custo_usd", "presumido"})
            conteudo = "".join(p.read_text(encoding="utf-8") for p in pasta.iterdir())
            for bloco in b:
                self.assertNotIn(bloco.text, conteudo)
            with self.assertRaises(ValueError):             # nada é sobrescrito
                R.rodar_rodada(b, list(achados.values()), dec, 1, base, 2.0, cliente=self.cliente())
            with self.assertRaises(ValueError):
                R.rodar_rodada(b, list(achados.values()), dec, 2, base, 0, cliente=self.cliente())

    def test_order_and_batch_size_change_only_the_grouping_and_are_restored(self):
        b, achados, dec = T.cenario()
        original = dict(v3.LOTE)
        with TemporaryDirectory() as base:
            c1, c2 = self.cliente(), self.cliente()
            R.rodar_rodada(b, list(achados.values()), dec, 1, base, 2.0, cliente=c1, lote=1)
            R.rodar_rodada(b, list(achados.values()), dec, 2, base, 2.0, cliente=c2, ordem="invertida")
            self.assertEqual(len(c1.pedidos), 3)                                   # um item por pedido
            self.assertEqual(sum(len(re.findall(r"\[ITEM ", p)) for p in c2.pedidos), 3)
            primeiro_id = re.findall(r"\[ITEM (\w+)\]", c2.pedidos[0])[0]
            self.assertEqual(primeiro_id, list(achados.values())[-1]["id"])        # ordem invertida
            rodadas = R.ler_rodadas(base)
            self.assertEqual([n for n, _ in rodadas], ["r1", "r2"])
            itens, resumo = R.estabilidade([x for _, x in rodadas])
            self.assertEqual(resumo["itens"], 3)
        self.assertEqual(v3.LOTE, original)                                        # o módulo não ficou alterado


if __name__ == "__main__":
    unittest.main()
