"""Contrato Python/Swift do Validador V5: as linhas que o backend emite precisam ter a mesma estrutura do fixture
sintético que `tests/ValidatorV5Check.swift` decodifica. Detecta deriva de campos sem rodar o Swift."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fonte import validador_v5_integracao as vi
import test_validador_v5 as T5
import test_validador_v5_integracao as TI

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "validador-v5-protocolo.json"
MAPEAMENTOS = {"verificacao", "contagem", "resultados"}      # dicionários de contagem: chaves variam


def forma(valor, nome=""):
    if isinstance(valor, dict):
        if nome in MAPEAMENTOS:
            return "mapa"
        return {k: forma(v, k) for k, v in sorted(valor.items())}
    if isinstance(valor, list):
        return [forma(valor[0], nome)] if valor else []
    return None if valor is None else type(valor).__name__


def compatível(a, b):
    """None em um dos lados vale como "opcional/ausente neste exemplo"; listas vazias, idem."""
    if a is None or b is None or a == [] or b == []:
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(compatível(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return compatível(a[0], b[0])
    return a == b or {a, b} <= {"int", "float"}


class ContratoSwiftTests(unittest.TestCase):
    def test_backend_lines_keep_the_structure_the_swift_check_decodes(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        b, f, dec, mapa = TI.cenario()
        ids = [x["id"] for x in f]
        with TemporaryDirectory() as pasta:
            atual = {"estimate": vi.estimar(b, f, dec, ids, TI.SHA, TI.SHA, pasta)}
            t = T5.Transporte(fn=T5.por_entrada(mapa))
            atual["finished"] = vi.executar(b, f, dec, ids, TI.SHA, TI.SHA, pasta, transporte=t)
            atual["results"] = vi.resultados(b, f, dec, pasta)
        atual["finished"].pop("avisos", None)
        for nome in ("estimate", "finished", "results"):
            esperado, obtido = forma(fixture[nome]), forma(json.loads(json.dumps(atual[nome], default=str)))
            # `arquivo`, `avisos` e `mensagem` são opcionais no exemplo
            for opcional in ("arquivo", "avisos", "mensagem"):
                if isinstance(esperado, dict): esperado.pop(opcional, None)
                if isinstance(obtido, dict): obtido.pop(opcional, None)
            self.assertTrue(compatível(esperado, obtido), f"{nome}: {esperado} != {obtido}")
        self.assertEqual(set(fixture["failure"]), {"codigo", "mensagem"})
        self.assertEqual(set(fixture["progress"]), {"etapa", "feitos", "total"})

    def test_fixture_is_synthetic_and_carries_no_secret_or_real_path(self):
        texto = FIXTURE.read_text(encoding="utf-8")
        self.assertNotIn("sk-", texto)
        self.assertNotIn("/Users/", texto)
        self.assertNotIn("Library/Application Support", texto)


if __name__ == "__main__":
    unittest.main()
