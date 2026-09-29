"""Projeto incremental com modelo simulado: o que é enviado, cache e pendências."""
import re
import tempfile
import unittest

from coerencia.leitura import ler_paragrafos
from coerencia.projeto import Projeto, capitulos


class LeitorFalso:
    """Extrai “olhos <cor>” de cada parágrafo; o juiz confirma toda diferença."""
    modelo = "falso:1b"

    def __init__(self):
        self.chamadas, self.cenas_lidas = [], []

    def json(self, sistema, usuario, esquema, etapa):
        self.chamadas.append({"etapa": etapa, "tokens_entrada": 100, "tokens_saida": 10})
        if etapa.startswith("juiz"):
            return {"contradicao": True, "confianca": "alta", "explicacao": "cor dos olhos mudou"}
        cena = usuario.split("\nCENA ", 1)[1]
        self.cenas_lidas.append(cena.split("\n", 1)[0])
        fatos = []
        for numero, texto in re.findall(r"^\[§(\d+)\] (.*)$", cena, re.M):
            for cor in re.findall(r"olhos (\w+)", texto):
                fatos.append({"entidade": "Lia", "tipo": "personagem", "aspecto": "cor dos olhos", "valor": cor,
                              "paragrafo": int(numero), "trecho": f"olhos {cor}", "fonte": "narrador"})
        return {"fatos": fatos, "conflitos": []}


def livro(cap1, cap2, cap3="Lia saiu de casa."):
    return ler_paragrafos(["Capítulo 1", *cap1, "Capítulo 2", *cap2, "Capítulo 3", cap3])


class ProjetoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.silencio = lambda *_: None

    def tearDown(self):
        self.pasta.cleanup()

    def rodar(self, paragrafos, modelo=None):
        modelo = modelo or LeitorFalso()
        rodada = Projeto(self.pasta.name).atualizar("livro.docx", paragrafos, modelo, registrar=self.silencio)
        return rodada, modelo, Projeto(self.pasta.name)

    def test_first_run_reads_everything_and_opens_pending(self):
        rodada, modelo, projeto = self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        self.assertEqual((rodada["enviados"], rodada["capitulos"]), (3, 3))
        self.assertEqual([p["status"] for p in projeto.pendencias], ["aberta"])
        situacoes = {c["titulo"]: c["situacao"] for c in projeto.estado["capitulos"].values()}
        self.assertEqual(situacoes, {"Capítulo 1": "com_pendencias", "Capítulo 2": "com_pendencias",
                                     "Capítulo 3": "sem_pendencias"})

    def test_unchanged_book_costs_nothing(self):
        texto = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."])
        self.rodar(texto)
        rodada, modelo, projeto = self.rodar(texto)
        self.assertEqual(modelo.chamadas, [])
        self.assertEqual((rodada["enviados"], rodada["tokens_gastos"]), (0, 0))
        self.assertGreater(rodada["tokens_poupados_estimados"], 0)
        self.assertEqual(len(projeto.pendencias), 1)

    def test_only_changed_chapter_is_sent_and_other_facts_still_count(self):
        self.rodar(livro(["Lia tinha olhos verdes."], ["Lia sorriu."]))
        rodada, modelo, projeto = self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        self.assertEqual(rodada["enviados"], 1)
        self.assertTrue(all(c.startswith("1 ") for c in modelo.cenas_lidas))  # só a 1ª cena do capítulo alterado
        self.assertEqual(len(projeto.pendencias), 1)  # comparou com o fato guardado do capítulo 1

    def test_inserting_paragraphs_does_not_misalign_other_chapters(self):
        self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        rodada, _, projeto = self.rodar(livro(["Era cedo.", "Chovia.", "Lia tinha olhos verdes."],
                                              ["Lia piscou os olhos castanhos."]))
        self.assertEqual(rodada["enviados"], 1)
        caps = {c.id: c for c in capitulos(livro(["Era cedo.", "Chovia.", "Lia tinha olhos verdes."],
                                                 ["Lia piscou os olhos castanhos."]))}
        pendencia = projeto.pendencias[0]
        for lado in ("a", "b"):
            cap = caps[pendencia[lado]["capitulo"]]
            self.assertIn(pendencia[lado]["trecho"], cap.paragrafos[pendencia[lado]["rel"]].texto)

    def test_fixing_the_text_closes_the_pending_item(self):
        self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        _, _, projeto = self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos verdes."]))
        self.assertEqual(projeto.pendencias[0]["status"], "resolvida_por_edicao")
        self.assertTrue(all(c["situacao"] == "sem_pendencias" for c in projeto.estado["capitulos"].values()))

    def test_intentional_decision_is_kept_when_the_pair_is_judged_again(self):
        self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        Projeto(self.pasta.name).decidir("C001", "intencional")
        _, modelo, projeto = self.rodar(livro(["Lia tinha olhos verdes.", "Fazia frio."], ["Lia piscou os olhos castanhos."]))
        self.assertTrue(any(c["etapa"].startswith("juiz") for c in modelo.chamadas))  # contexto mudou
        self.assertEqual([p["status"] for p in projeto.pendencias], ["intencional"])

    def test_invalid_decision_is_rejected(self):
        self.rodar(livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."]))
        with self.assertRaises(ValueError):
            Projeto(self.pasta.name).decidir("C999", "corrigida")
        with self.assertRaises(ValueError):
            Projeto(self.pasta.name).decidir("C001", "talvez")


if __name__ == "__main__":
    unittest.main()


class RelatorioTests(unittest.TestCase):
    def test_project_report_highlights_both_excerpts(self):
        from coerencia.relatorio import de_projeto
        with tempfile.TemporaryDirectory() as pasta:
            paragrafos = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos <b>."])
            Projeto(pasta).atualizar("livro.docx", paragrafos, LeitorFalso(), registrar=lambda *_: None)
            html = de_projeto(Projeto(pasta), capitulos(paragrafos), pasta)
            self.assertIn("C001", html)
            self.assertIn("<mark>olhos verdes</mark>", html)
            self.assertIn("<mark>olhos castanhos</mark> &lt;b&gt;.", html)  # texto do livro é escapado
            self.assertIn("coerencia decidir C001", html)

    def test_single_report_and_empty_state(self):
        from coerencia.relatorio import avulso, destacar
        self.assertEqual(destacar("Ela disse “olá”, Ana.", "disse olá"), "Ela <mark>disse “olá</mark>”, Ana.")
        self.assertIn("Nenhuma contradição", avulso("t.docx", "m", [], [], 0))


class TetoTests(unittest.TestCase):
    def test_budget_stop_keeps_paid_chapters_and_resumes_judging(self):
        from coerencia.modelo import ErroModelo

        class LeitorComTeto(LeitorFalso):
            def __init__(self, limite):
                super().__init__()
                self.limite = limite

            def json(self, sistema, usuario, esquema, etapa):
                if len(self.chamadas) >= self.limite:
                    raise ErroModelo("Teto de gasto atingido (teste).")
                return super().json(sistema, usuario, esquema, etapa)

        texto = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."])
        with tempfile.TemporaryDirectory() as pasta:
            primeira = Projeto(pasta).atualizar("livro.docx", texto, LeitorComTeto(2), registrar=lambda *_: None)
            self.assertEqual((primeira["enviados"], primeira["a_enviar"]), (2, 3))
            self.assertTrue(primeira["interrompida"])
            self.assertEqual(Projeto(pasta).pendencias, [])  # juiz não chegou a rodar
            segundo = LeitorFalso()
            Projeto(pasta).atualizar("livro.docx", texto, segundo, registrar=lambda *_: None)
            lidas = [c["etapa"] for c in segundo.chamadas if c["etapa"].startswith("cena")]
            self.assertEqual(len(lidas), 1)  # só o capítulo que faltava
            self.assertEqual([p["status"] for p in Projeto(pasta).pendencias], ["aberta"])  # par retomado
            self.assertFalse(any(c.get("reavaliar") for c in Projeto(pasta).estado["capitulos"].values()))


class EstimativaTests(unittest.TestCase):
    def test_estimate_counts_only_changed_chapters_without_calling_the_model(self):
        texto = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."])
        with tempfile.TemporaryDirectory() as pasta:
            antes = Projeto(pasta).estimar(texto, "claude-sonnet-5-5")
            self.assertEqual(antes["a_enviar"], 3)
            self.assertGreater(antes["custo_estimado_usd"], 0)
            Projeto(pasta).atualizar("livro.docx", texto, LeitorFalso(), registrar=lambda *_: None)
            depois = Projeto(pasta).estimar(texto, "falso:1b")
            self.assertEqual((depois["a_enviar"], depois["caracteres"]), (0, 0))
            alterado = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos verdes."])
            self.assertEqual(Projeto(pasta).estimar(alterado, "falso:1b")["titulos_a_enviar"], ["Capítulo 2"])


class AndamentoTests(unittest.TestCase):
    def test_progress_counts_scenes_of_chapters_sent(self):
        texto = livro(["Lia tinha olhos verdes."], ["Lia piscou os olhos castanhos."])
        with tempfile.TemporaryDirectory() as pasta:
            passos = []
            Projeto(pasta).atualizar("livro.docx", texto, LeitorFalso(), registrar=lambda *_: None,
                                     avancar=lambda f, t: passos.append((f, t)))
            self.assertEqual(passos, [(1, 3), (2, 3), (3, 3)])
