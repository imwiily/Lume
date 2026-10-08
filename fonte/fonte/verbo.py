"""Núcleo de identificação verbal do FONTE (estabilização, Fase 2a).

Três operações com responsabilidades diferentes, que não se reduzem a uma função binária:

1. `certamente_verbo`: identificação positiva. É certamente uma forma verbal finita? Modelo e
   léxico de acordo, com filtros para homógrafos em contexto nominal. Usada quando um alerta
   afirma algo *sobre* um verbo (tempo, correlação, concordância de auxiliares…).
2. `pode_ser_verbo`: identificação conservadora. Pode ser uma forma verbal finita? Basta uma
   fonte com apoio. Usada antes de afirmar que um trecho *não tem* verbo: na dúvida, abstém-se.
3. `ha_forma_verbal`: verificação de presença. Há aqui uma forma verbal conjugada (pelo modelo) ou
   uma forma que o léxico só conhece como verbo? Usada como guarda (“não alertar se houver verbo
   antes”).

Ingredientes compartilhados: `model_finite` (leitura do modelo, com ‘Fin’ ou modo),
`conjugado_pelo_modelo` (só ‘Fin’, quando a regra precisa também do número e da pessoa do
modelo), `so_verbo_no_lexico`, `nominal_context` e `after_article`.

O tempo do verbo (`indicative_tense`) mora aqui por depender da identificação; será unificado na
Fase 3. Nenhuma função deste módulo usa nomes ou frases de obras.
"""
import re

from .lexicon import FINITE, FUTURE, NONFINITE, NONVERB, PAST, PRESENT, VERBAL_DEPS, flags

# Relativos que abrem oração (também usados por `analysis`).
RELATIVOS = {"que", "onde", "cujo", "cuja", "cujos", "cujas"}


def conjugado_pelo_modelo(token):
    """O modelo marca verbo ou auxiliar com forma finita (‘Fin’). Sem o léxico: serve às regras
    que também usam o número e a pessoa do modelo (concordância, vírgula entre sujeito e verbo)."""
    return token.pos_ in {"VERB", "AUX"} and "Fin" in token.morph.get("VerbForm")


def so_verbo_no_lexico(token):
    """O léxico só conhece a forma como verbo finito: sem leitura nominal nem não finita."""
    value = flags(token.text)
    return bool(value & FINITE) and not value & (NONVERB | NONFINITE)


def model_finite(token):
    return (token.pos_ in {'VERB', 'AUX'}
            and ('Fin' in token.morph.get('VerbForm') or bool(token.morph.get('Mood'))))


def nominal_context(token, value):
    """Em homógrafos, exige apoio sintático para sustentar a leitura verbal."""
    has_subject = any(c.dep_.startswith(('nsubj', 'csubj')) for c in token.children)
    exclusive_finite = bool(value & FINITE and not value & (NONVERB | NONFINITE))
    def possible_clitic(child):
        return (child.text.casefold() in {'o', 'a', 'os', 'as'}
                and child.i == token.i - 1
                and (exclusive_finite or has_subject))
    if any(c.dep_ in {'case', 'cop'}
           or (c.dep_ == 'det' and not possible_clitic(c)) for c in token.children):
        return True
    if value & NONVERB and token.dep_ != 'ROOT':
        if not has_subject:
            return True
    # Adjetivo posposto (“a noite inteira”): o substantivo anterior não é o
    # sujeito desta forma e concorda com ela como adjetivo (minúscula, mesmo
    # gênero e número), mesmo quando o modelo a marca como verbo principal.
    if value & NONVERB and token.i > 0 and token.text[:1].islower():
        previous = token.doc[token.i - 1]
        # O modelo às vezes toma o substantivo como sujeito e liga a forma a outro verbo
        # sem conjunção, subordinante nem pontuação (“passou a tarde inteira discutindo”):
        # essa leitura verbal não tem apoio sintático.
        head = token.head
        solta = (token.dep_ in {'conj', 'advcl', 'parataxis', 'xcomp', 'ccomp'} and head.i < previous.i
                 and not any(c.dep_ in {'cc', 'mark'} for c in token.children)
                 and not any(t.is_punct for t in token.doc[head.i + 1:token.i]))
        if previous.pos_ == 'NOUN' and (solta or not (previous.head == token and previous.dep_.startswith('nsubj'))):
            word = token.lower_
            plural = word.endswith('s')
            gender = previous.morph.get('Gender')
            endings = ('a', 'as') if 'Fem' in gender else ('o', 'os') if 'Masc' in gender else ()
            if (plural == ('Plur' in previous.morph.get('Number'))
                    and word.endswith(endings + ('e', 'es'))):
                return True
    return False


# Determinantes que só antecedem nome (“uma era de ouro”, “nessa era”). Ficam de fora os que
# também são pronomes sujeito (“Essa era a última carroça”, “A minha era maior”) e ‘a’ e ‘o’,
# também oblíquos (“a viu”); as contrações com preposição nunca são sujeito.
NOMINAL_DETERMINERS = {'um', 'uma', 'uns', 'umas', 'num', 'numa', 'nuns', 'numas',
                       'nessa', 'nesse', 'nesta', 'neste', 'naquela', 'naquele',
                       'dessa', 'desse', 'desta', 'deste', 'daquela', 'daquele',
                       'da', 'do', 'na', 'no', 'pela', 'pelo'}


# Depois de “todo o” ou de preposição + artigo (“de o”, “com a”) só cabe nome ou infinitivo.
TOTALIZERS = {'todo', 'toda', 'todos', 'todas'}


def after_article(token):
    """Precedido de artigo que vem depois de “todo” ou de preposição (“todo o barulho”, “com a mão”)."""
    if token.i < 2:
        return False
    article, before = token.doc[token.i - 1], token.doc[token.i - 2]
    return (article.text.casefold() in {'o', 'a', 'os', 'as'}
            and (before.text.casefold() in TOTALIZERS or before.pos_ == 'ADP'))


def certamente_verbo(token):
    """Identificação positiva: é certamente uma forma verbal finita?"""
    value = flags(token.text)
    if value and not value & FINITE:
        return False
    if after_article(token):
        return False
    if token.i > 0 and token.doc[token.i - 1].text.casefold() in NOMINAL_DETERMINERS and value & NONVERB:
        return False
    # “Uma nova era começa”, “uma longa era de paz”: determinante + adjetivo + nome, seguido de
    # verbo ou de ‘de’. Em “A velha era bonita” a forma continua verbo.
    if value & NONVERB and token.i > 1 and token.i + 1 < len(token.doc):
        before, adjective, after = token.doc[token.i - 2], token.doc[token.i - 1], token.doc[token.i + 1]
        if (before.text.casefold() in NOMINAL_DETERMINERS and adjective.pos_ == 'ADJ'
                and (re.fullmatch(r'd[oae]s?', after.text.casefold())
                     or (after.pos_ in {'VERB', 'AUX'} and flags(after.text) & FINITE))):
            return False
    if value & FINITE:
        if model_finite(token):
            # Cópulas/auxiliares herdam o sujeito do predicado; não são adjetivos. Vale
            # pela relação sintática, não só pela etiqueta: o modelo marca a cópula
            # como VERB (“Não era como uma ponte…”), e a cópula nunca é a raiz nem tem
            # sujeito próprio, o que a faria parecer substantivo em nominal_context.
            return token.pos_ == 'AUX' or token.dep_ in VERBAL_DEPS or not nominal_context(token, value)
        # Sem morfologia do modelo (“Era como uma porta…” etiquetado como ADV), a forma
        # finita do léxico ligada como cópula ou auxiliar é verbo: duas fontes concordam.
        if token.dep_ in VERBAL_DEPS:
            return True
        # Só recupera sem o modelo se não houver leitura nominal ou não finita.
        if value & NONVERB and not value & NONFINITE and token.i > 0:
            previous = token.doc[token.i-1]
            if previous.text.casefold() in {'eu','tu','ele','ela','nós','vós','eles','elas','você','vocês'}:
                return True
        return not value & (NONVERB | NONFINITE)
    # Fora do léxico, aceita o modelo para evitar alertas de estrutura excessivos.
    return model_finite(token)


def indicative_tense(token):
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


def pode_ser_verbo(token):
    """Identificação conservadora: pode ser uma forma verbal finita?

    Validação independente antes de afirmar que um segmento não tem verbo finito.

    `certamente_verbo` decide pela análise sintática, que erra em homógrafos e em verbos ligados como
    complemento. Aqui basta uma fonte com apoio: o modelo e o léxico concordarem na forma finita
    (“por onde pousa”); o léxico só conhecer a forma como verbo finito (“havia”, “estão”); ou a
    forma, finita no léxico, ocupar a posição do verbo logo depois do grupo nominal que abre a
    frase (“A garra segura o menino”). Com discordância entre as fontes, a frase não é dada como
    sem verbo.
    """
    if certamente_verbo(token):
        return True
    lex = flags(token.text)
    if not token.is_alpha or not lex & FINITE or after_article(token):
        return False
    if model_finite(token) or not lex & (NONVERB | NONFINITE):
        return True
    from .temporal import sole_verb
    return sole_verb(token) or posicao_de_verbo(token)


# Entre o relativo e o verbo da relativa cabem negação, clíticos e pronome sujeito.
ANTES_DO_VERBO = {"não", "nunca", "já", "se", "me", "te", "lhe", "lhes", "nos", "vos", "ele", "ela", "eles", "elas"}
GRAMATICAIS = {"DET", "PRON", "ADP", "ADV", "CCONJ", "SCONJ", "NUM", "PUNCT"}


def posicao_de_verbo(token):
    """Homógrafo nome/verbo, só no presente pelo léxico, num lugar que pede verbo: logo depois de
    um relativo (a relativa “por onde pousa” precisa de verbo) ou entre um nome e o início do
    complemento, concordando em número com esse nome (“… seu braço causa coceira”)."""
    lex = flags(token.text)
    if not lex & PRESENT or lex & (PAST | FUTURE | NONFINITE) or token.pos_ in GRAMATICAIS:
        return False
    doc = token.doc
    walk = token.i - 1
    while walk >= token.sent.start and doc[walk].lower_ in ANTES_DO_VERBO:
        walk -= 1
    if walk >= token.sent.start and doc[walk].lower_ in RELATIVOS | {"quem"}:
        return True
    if token.i == token.sent.start or token.i + 1 >= token.sent.end:
        return False
    previous, following = doc[token.i - 1], doc[token.i + 1]
    if previous.pos_ not in {"NOUN", "PROPN"} or following.pos_ not in {"DET", "NOUN", "PRON"}:
        return False
    plural = "Plur" in previous.morph.get("Number")
    return token.lower_.endswith("m") if plural else not token.lower_.endswith(("m", "s"))


def ha_forma_verbal(token):
    """Verificação de presença: verbo conjugado pelo modelo ou, quando ele erra a classe, pelo léxico
    (forma só verbal, sem leitura nominal): “É porque…”, “a fila só crescia”."""
    if conjugado_pelo_modelo(token):
        return True
    value = flags(token.text)
    return bool(value & FINITE and not value & NONVERB)
