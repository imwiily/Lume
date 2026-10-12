"""Pesquisa de fundamento linguístico com o Google Search (Gemini): uma pergunta abstrata por vez, só por escolha
explícita do editor sobre um apontamento. Nunca recebe o manuscrito nem trechos dele; não altera nada.
O resultado traz só as consultas e fontes que a API informou: referência não consultada nunca é inventada."""
from .coerencia_ia import _coerencia

MODELO = "gemini-3.8-flash"
MAX_PERGUNTA = 400
SISTEMA = ("Você responde dúvidas normativas do português do Brasil para um revisor. Pesquise fontes confiáveis "
           "(gramáticas, VOLP/ABL, Acordo Ortográfico, instituições de ensino) e responda em até 6 linhas, em "
           "linguagem simples, sem reescrever textos. Se as fontes divergirem ou não resolverem, diga isso.")


def validar(pergunta):
    pergunta = " ".join(str(pergunta).split())
    if not pergunta or len(pergunta) > MAX_PERGUNTA:
        raise ValueError(f"A pergunta precisa ter entre 1 e {MAX_PERGUNTA} caracteres.")
    return pergunta


def estimar(pergunta, modelo=MODELO):
    """Pior caso de uma pesquisa, sem chamar a API nem criar o cliente."""
    from coerencia.modelo import BUSCAS_MAXIMAS, BUSCA_GEMINI_USD, precos_gemini
    entrada, saida, _ = precos_gemini(modelo)
    pergunta = validar(pergunta)
    tokens = (len(SISTEMA) + len(pergunta)) / 2.0 + 1
    maximo = (tokens * entrada + 4000 * saida) / 1e6 + BUSCAS_MAXIMAS * BUSCA_GEMINI_USD
    return {"provedor": "google", "modelo": modelo, "pergunta": pergunta, "custo_maximo_usd": round(maximo, 4),
            "buscas_maximas": BUSCAS_MAXIMAS}


def pesquisar(pergunta, modelo=MODELO, teto=0.25, cliente=None):
    _, _, _, ErroModelo, criar_modelo = _coerencia()
    pergunta = validar(pergunta)
    if not modelo.startswith("gemini-"):
        raise ValueError("A pesquisa Google só existe nos modelos Gemini.")
    cliente = cliente or criar_modelo(modelo, teto=teto)
    try:
        cliente.verificar()
        saida = cliente.pesquisar(SISTEMA, pergunta, "pesquisa")
    except ErroModelo as erro:
        raise ValueError("Pesquisa Google: " + str(erro)) from erro
    return dict(saida, provedor="google", modelo=modelo, pergunta=pergunta, teto_usd=teto)
