"""Núcleo de classificação de tempo e modo verbal do FONTE (estabilização, Fase 3).

Responsabilidades separadas, cada uma numa função:

- **morfologia** (só a forma e o léxico): terminações do condicional (`TERMINACAO_CONDICIONAL`) e do
  imperfeito do subjuntivo (`TERMINACAO_IMPERFEITO_SUBJUNTIVO`), `imperfeito`,
  `mais_que_perfeito_composto` (locução ter/haver + particípio);
- **modo**: `imperfeito_do_subjuntivo` (terminação sem leitura no indicativo); o modo do modelo é
  lido dentro das classificações;
- **forma finita ou não finita**: fica no núcleo verbal (`verbo.py`), que este módulo usa;
- **classificação estrita** (alvo de alerta), em duas políticas distintas e intencionais:
  - `tempo_estrito`: modelo e léxico de acordo; exige o indicativo do modelo para passado e
    presente, separa condicional e futuro, devolve “ambíguo” quando o léxico admite os dois;
    usada pelas relações temporais;
  - `tempo_narrativo`: rótulos da narração (“passado”/“presente”) para a regra de tempo verbal e
    a contagem do tempo predominante; aceita o passado só pelo léxico, mas exige o indicativo do
    modelo para o presente (separa o imperativo);
- **recuperação** (âncora, nunca prova sozinha): `tempo_recuperado` (eventos da sequência,
  quando o modelo erra a classe), `passado_so_no_lexico` (passado na narração no presente),
  `para_como_verbo` e `verbo_unico_da_frase`.

A relação temporal entre orações e o plano temporal da narrativa ficam em `temporal.py`, que
consome estas funções; nada aqui decide se há incoerência. Nenhuma função usa nomes ou frases de
obras.
"""
import re

from .lexicon import FINITE, FUTURE, NONFINITE, NONVERB, PAST, PRESENT, flags
from .verbo import certamente_verbo, model_finite, so_verbo_no_lexico

# Morfologia.
TERMINACAO_CONDICIONAL = re.compile(r"r(?:ia|ias|íamos|íeis|iam)$")
TERMINACAO_IMPERFEITO_SUBJUNTIVO = re.compile(r"sse(?:s|m|mos|is)?$")
IMPERFECT_ENDING = re.compile(r"(?:ava|avas|ávamos|avam|ia|ias|íamos|iam)$")
IRREGULAR_IMPERFECT = {
    "ser": ("era", "eras", "era", "éramos", "éreis", "eram"),
    "ter": ("tinha", "tinhas", "tinha", "tínhamos", "tínheis", "tinham"),
    "vir": ("vinha", "vinhas", "vinha", "vínhamos", "vínheis", "vinham"),
    "pôr": ("punha", "punhas", "punha", "púnhamos", "púnheis", "punham"),
}
# Depois de ‘parar’ (verbo), não de ‘para’ (preposição): “o carro para no sinal”.
DEPOIS_DE_PARAR = {"de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "num", "numa"}


def imperfeito(token):
    """Imperfeito pelo modelo, pela terminação ou pelas formas irregulares (era, tinha, vinha, punha).
    Não separa o modo nem o condicional em “-íamos” (limitação registrada na Fase 3)."""
    return ("Imp" in token.morph.get("Tense") or bool(IMPERFECT_ENDING.search(token.lower_))
            or any(token.lower_ in forms for forms in IRREGULAR_IMPERFECT.values()))


def mais_que_perfeito_composto(token):
    """‘ter’/‘haver’ no imperfeito com particípio (“tinha esquecido”, “havia ganhado”)."""
    if token.lemma_.casefold() not in {"ter", "haver"} and token.lower_ not in {"tinha", "tinham", "havia", "haviam"}:
        return False
    nxt = next((t for t in token.doc[token.i + 1:token.i + 3] if t.lower_ not in {"já", "ainda", "nunca", "não"}), None)
    return nxt is not None and ("Part" in nxt.morph.get("VerbForm") or (token.dep_ == "aux" and token.head == nxt))


def imperfeito_do_subjuntivo(token):
    """Terminação do imperfeito do subjuntivo sem leitura no indicativo (“disse” é pretérito perfeito)."""
    value = flags(token.text)
    return (bool(TERMINACAO_IMPERFEITO_SUBJUNTIVO.search(token.lower_)) and bool(value & FINITE)
            and not value & (PAST | PRESENT | FUTURE))


def tempo_estrito(token):
    """A grafia sozinha nunca desempata presente/pretérito nem decide o modo."""
    if token.pos_ not in {"VERB", "AUX"} or not certamente_verbo(token) or not model_finite(token):
        return None
    value = flags(token.text)
    mood = token.morph.get("Mood")
    # O modelo pequeno pode marcar “construiríamos” como presente. A desinência
    # do condicional + ausência de leitura indicativa no léxico corrigem isso.
    conditional_ending = TERMINACAO_CONDICIONAL.search(token.text.casefold())
    if (value & FINITE and not value & (PAST | PRESENT | FUTURE)
            and ("Cnd" in mood or conditional_ending)):
        return "conditional"
    if "Sub" in mood or "Imp" in mood:
        return None
    if value & PAST and value & PRESENT:
        return "ambiguous_past_present"
    if "Ind" not in mood:
        return None
    if value & FUTURE and not value & (PAST | PRESENT):
        return "future"
    if value & PAST and not value & (PRESENT | FUTURE):
        return "past"
    if value & PRESENT and not value & (PAST | FUTURE):
        return "present"
    return None


def tempo_narrativo(token):
    """Rótulo da narração (“passado”/“presente”) para a regra de tempo verbal e a contagem do tempo
    predominante. Política distinta de `tempo_estrito`: aceita o passado só pelo léxico, mas exige o
    indicativo do modelo para o presente."""
    value = flags(token.text)
    if not certamente_verbo(token):
        return None
    # Uma forma como "passamos" admite ambos. Não escolhe o tempo pela grafia.
    if value & PAST and value & PRESENT:
        return None
    if value & PAST and not value & (PRESENT | FUTURE):
        return 'passado'
    if value & PRESENT and not value & (PAST | FUTURE):
        # Exige que o modelo também indique o indicativo para separar imperativo.
        if 'Ind' in token.morph.get('Mood') and model_finite(token):
            return 'presente'
    # Sem confirmação lexical não cria alerta temporal, mesmo que o modelo sugira.
    return None


def passado_so_no_lexico(token):
    """Recuperação para a narração no presente: forma que o léxico só conhece como pretérito
    finito (“havia”), com morfologia finita do modelo, mesmo quando a árvore a liga como
    complemento (“de uma havia um bilhete”)."""
    lex = flags(token.text)
    return bool(model_finite(token) and lex & FINITE and lex & PAST
                and not lex & (PRESENT | FUTURE | NONVERB | NONFINITE))


def para_como_verbo(token):
    """‘Para’ seguido de “no/na/de/em…” e precedido de nome ou pronome: verbo ‘parar’ no presente."""
    doc = token.doc
    return (token.lower_ == "para" and token.i + 1 < len(doc) and doc[token.i + 1].lower_ in DEPOIS_DE_PARAR
            and token.i > 0 and doc[token.i - 1].pos_ in {"NOUN", "PROPN", "PRON"})


def verbo_unico_da_frase(token):
    """Único candidato a verbo da frase, abrindo-a (sujeito elíptico: “Aponto para o mapa”) ou
    logo depois do grupo nominal que a abre (“O relógio da sala demora a bater”): a frase precisa
    de um verbo e só ele pode sê-lo, mesmo sem objeto e com leitura nominal no léxico. O grupo
    nominal vale pela forma, não pelo rótulo do modelo, que às vezes faz do nome a raiz e do verbo
    um adjetivo. Palavra sozinha na frase (“Nada.”) fica de fora: sem complemento, a leitura
    nominal prevalece."""
    lex = flags(token.text)
    if not token.is_alpha or not lex & PRESENT or lex & (PAST | FUTURE | NONFINITE):
        return False
    # Palavra gramatical que o léxico também lista como verbo (“Aquela”, “Apenas”, “Pelo”, “dele”).
    if token.pos_ in {"DET", "PRON", "ADP", "ADV", "CCONJ", "SCONJ", "NUM", "PUNCT"}:
        return False
    sent = token.sent
    first = next((t for t in sent if t.is_alpha), None)
    previous = token.doc[token.i - 1] if token.i > sent.start else None
    after_subject = (previous is not None and previous.pos_ in {"NOUN", "PROPN", "PRON"}
                     and all(t.pos_ in {"DET", "ADJ", "NUM"} for t in token.doc[sent.start:previous.i]))
    return ((token == first or after_subject)
            and any(t.is_alpha for t in token.doc[token.i + 1:sent.end])
            and not any(certamente_verbo(t) or tempo_estrito(t) for t in sent if t.i != token.i))


def tempo_recuperado(token):
    """Passado ou presente de um predicado finito, combinando modelo, léxico e sintaxe.

    O modelo às vezes etiqueta o verbo como adjetivo (“Ela segura a mochila”) ou como
    verbo sem morfologia (“e solta o peixe”). Com o léxico admitindo a forma finita, o
    modelo sem leitura não finita e um objeto ligado (particípio sem auxiliar não toma
    objeto), a leitura verbal é aceita. Formas ambíguas não decidem.
    """
    # Logo depois de preposição só cabe infinitivo ou nome (“em volta dele”, “de volta”).
    if token.i > 0 and token.doc[token.i - 1].pos_ == "ADP" and token.lower_ != "para":
        return None
    value = tempo_estrito(token)
    if value in {"past", "present"}:
        return value
    if para_como_verbo(token):
        return "present"
    word, lemma = token.text.casefold(), token.lemma_.casefold()
    # “vira” = presente de ‘virar’ ou mais-que-perfeito de ‘ver’: o lema do modelo decide. Com
    # lema em -ar cuja 3ª pessoa do presente é a própria palavra, é presente (o mais-que-perfeito
    # de ‘virar’ seria “virara”), mesmo que a etiqueta de tempo diga outra coisa.
    if (value == "ambiguous_past_present" and lemma.endswith("ar")
            and word in {lemma[:-2] + "a", lemma[:-2] + "am"}):
        return "present"
    # 1ª do plural igual no presente e no perfeito (“passamos”, “chegamos”, “saímos”): só é
    # analisada numa narração no passado, onde o perfeito é a leitura natural. Serve de âncora,
    # nunca de alvo.
    if value == "ambiguous_past_present" and re.search(r"(?:a|e|i|í)mos$", word):
        return "past"
    lex = flags(token.text)
    verb_form = token.morph.get("VerbForm")
    # Forma só verbal e finita no léxico (“Abri”, “Procuro”, “escorrem”): prevalece sobre a
    # etiqueta do modelo (nome, adjetivo ou até infinitivo). Só no início da frase, na raiz ou
    # no verbo pendurado na raiz nominal, onde o modelo erra; o léxico não lista todo substantivo.
    only_finite = so_verbo_no_lexico(token)
    if value is not None or not lex & FINITE or (verb_form and "Fin" not in verb_form and not only_finite):
        return None
    first = next((t for t in token.sent if t.is_alpha), None)
    exclusive = only_finite and (token == first or token.dep_ == "ROOT"
                                 or (token.dep_ == "acl" and token.head.dep_ == "ROOT"))
    if not exclusive and not verbo_unico_da_frase(token):
        if not any(c.dep_ in {"obj", "iobj"} for c in token.children):
            return None
        if not (certamente_verbo(token) or token.pos_ == "VERB"):
            return None
    if lex & PRESENT and not lex & (PAST | FUTURE):
        return "present"
    if lex & PAST and not lex & (PRESENT | FUTURE):
        return "past"
    return None
