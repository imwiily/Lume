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

# Palavras que atraem o pronome átono para antes do verbo (próclise).
ATRAEM_PRONOME = {"não", "nunca", "jamais", "já", "também", "que", "quem", "quando", "se", "onde", "como",
                  "porque", "eu", "tu", "ele", "ela", "nós", "eles", "elas", "você", "vocês"}

# Relativos que abrem oração (também usados por `analysis`).
RELATIVOS = {"que", "onde", "cujo", "cuja", "cujos", "cujas"}


# Classes gramaticais que nunca são o verbo da frase, mesmo com uma leitura finita no léxico.
GRAMATICAIS_NAO_VERBAIS = {"ADP", "SCONJ", "CCONJ", "ADV", "NUM", "DET", "PRON", "INTJ", "PUNCT"}
# O que segue um verbo que abre a frase: o complemento (infinitivo, objeto, pronome) ou uma
# subordinada. Um nome no início da frase segue com preposição, adjetivo, conjunção ou advérbio.
CONTINUAM_VERBO = {"VERB", "AUX", "DET", "PRON", "SCONJ"}
# Sinais que abrem uma fala ou citação: o que vem depois começa uma frase.
ABERTURAS_DE_FALA = {"«", "“", "\"", "—", "–", ":", "-"}


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
    # Preposição regida pela forma (“no vão de uma sacada”) prova nome ou infinitivo, mesmo que o
    # léxico não traga essa leitura. Artigo e cópula só provam se o léxico admite leitura nominal ou
    # não finita; sem ela, são erro da árvore (“Uma nova era começa”: ‘era’ como cópula de ‘começa’).
    if any(c.dep_ == 'case' for c in token.children):
        return True
    if value & (NONVERB | NONFINITE) and any(c.dep_ == 'cop' or (c.dep_ == 'det' and not possible_clitic(c))
                                             for c in token.children):
        return True
    # Cópula que é certamente verbo (“A despensa estava vazia”) faz da forma um predicativo, mesmo
    # sem leitura nominal no léxico. A falsa cópula de “Uma nova era começa” não é verbo certo.
    if any(c.dep_ == 'cop' and c.i < token.i and certamente_verbo(c) for c in token.children):
        return True
    # Forma dependente sem sujeito próprio lê-se como nome, a menos que governe complemento verbal
    # (objeto ou oração): nome não toma objeto (“é divertida e vale a pena”). Infinitivo também toma
    # (“crime achar dinheiro”): a isenção só vale sem leitura não finita no léxico.
    governs_complement = not value & NONFINITE and any(c.dep_ in {'obj', 'iobj', 'ccomp', 'xcomp'}
                                                        for c in token.children)
    if value & NONVERB and token.dep_ != 'ROOT':
        if not has_subject and not governs_complement:
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
    # Evidência sintática forte, mesmo com etiqueta nominal do modelo: a forma rege um infinitivo
    # (“Preciso falar-lhe”) ou ocupa o lugar do verbo entre sujeito e complemento (“A garra segura
    # o menino”). Não vale depois de cópula (“É preciso sair”), artigo ou preposição.
    if value & FINITE and (rege_infinitivo(token) or entre_sujeito_e_complemento(token)):
        return True
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
        # O modelo vê um nome precedido de determinante (“A vida é longa”): o léxico sozinho não basta,
        # porque pode faltar nele a leitura nominal da forma.
        if token.pos_ in {'NOUN', 'PROPN', 'ADJ'} and token.i > 0 and token.doc[token.i - 1].pos_ == 'DET':
            # Exceto o pronome átono depois de palavra que o atrai (“não a sentia”, “que a sacudisse”):
            # aí ‘o/a’ é clítico do verbo, não artigo.
            clitic, before = token.doc[token.i - 1], token.doc[token.i - 2] if token.i > 1 else None
            if not (clitic.lower_ in {'o', 'a', 'os', 'as'} and before is not None
                    and before.lower_ in ATRAEM_PRONOME):
                return False
        # Só recupera sem o modelo se não houver leitura nominal ou não finita.
        if value & NONVERB and not value & NONFINITE and token.i > 0:
            previous = token.doc[token.i-1]
            if previous.text.casefold() in {'eu','tu','ele','ela','nós','vós','eles','elas','você','vocês'}:
                return True
        return not value & (NONVERB | NONFINITE)
    # Fora do léxico, aceita o modelo para evitar alertas de estrutura excessivos.
    return model_finite(token)


def infinitivo(token):
    """Infinitivo pela morfologia do modelo ou, se ele não a dá, pela terminação em -r (com ou sem
    clítico) de uma forma que o léxico admite como não finita. Particípio e gerúndio não contam, nem
    palavra em maiúscula (número romano, título)."""
    if not token.text[:1].islower():
        return False
    if "Inf" in token.morph.get("VerbForm"):
        return True
    return (token.pos_ in {"VERB", "AUX"} and "Fin" not in token.morph.get("VerbForm")
            and bool(flags(token.text) & NONFINITE) and token.lower_.split("-")[0].endswith("r"))


def rege_infinitivo(token):
    """Forma que não é palavra gramatical nem infinitivo, seguida imediatamente de infinitivo, sem
    verbo, artigo nem preposição antes dela (“Venho explicar-te”, “não te deixes vencer”). Não vale
    depois de cópula (“É preciso sair”)."""
    doc = token.doc
    if token.i + 1 >= len(doc) or token.pos_ in GRAMATICAIS_NAO_VERBAIS or infinitivo(token):
        return False
    previous = doc[token.i - 1] if token.i > token.sent.start else None
    return infinitivo(doc[token.i + 1]) and (previous is None or previous.pos_ not in {"VERB", "AUX", "DET", "ADP"})


def entre_sujeito_e_complemento(token):
    """Forma do presente, em minúscula, entre um sintagma nominal completo (determinante + nome) e
    um complemento que começa por determinante ou nome, concordando em número com o nome (“O braço
    causa coceira”). Adjetivo posposto segue com relativo, clítico, conjunção ou preposição (“a
    tristeza profunda que…”), e não entra."""
    doc = token.doc
    value = flags(token.text)
    if (not value & PRESENT or value & (PAST | FUTURE | NONFINITE) or token.i < 2 or not token.text[:1].islower()
            or token.pos_ in GRAMATICAIS_NAO_VERBAIS or token.i + 1 >= token.sent.end):
        return False
    noun, det, following = doc[token.i - 1], doc[token.i - 2], doc[token.i + 1]
    # Complemento: determinante ou nome; o léxico corrige o modelo só quando ele marcou como verbo
    # uma palavra que o léxico conhece apenas como não verbal (“causa coceira”).
    following_value = flags(following.text)
    by_model = following.pos_ in {"DET", "NOUN"}
    by_lexicon = following.pos_ in {"VERB", "AUX"} and following_value & NONVERB and not following_value & FINITE
    if noun.pos_ not in {"NOUN", "PROPN"} or det.pos_ != "DET" or not (by_model or by_lexicon):
        return False
    # Sem determinante abrindo o complemento, a forma que concorda com o nome como um adjetivo
    # (“a tarde inteira sozinha”) é adjetivo posposto, não verbo (“a garra segura o menino” tem ‘o’).
    if following.pos_ != "DET":
        gender, number = noun.morph.get("Gender"), noun.morph.get("Number")
        endings = ("a", "as") if "Fem" in gender else ("o", "os") if "Masc" in gender else ()
        if endings and token.lower_.endswith(endings) and token.lower_.endswith("s") == ("Plur" in number):
            return False
    plural = "Plur" in noun.morph.get("Number")
    return token.lower_.endswith("m") if plural else not token.lower_.endswith(("m", "s"))


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
    return sole_verb(token) or posicao_de_verbo(token) or abre_oracao(token) or abre_frase(token)


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


# Palavras que abrem oração com verbo finito (subordinantes e relativos). Depois delas, uma forma
# que o léxico também admite como finita é o verbo da oração: “quando ele cantar”, “o que a
# alcançar” (futuro do subjuntivo igual ao infinitivo). Depois de preposição, seria infinitivo.
ABREM_ORACAO_FINITA = RELATIVOS | {"quem", "quanto", "quando", "se", "enquanto", "caso", "conforme", "como"}
# Entre a abertura e o verbo cabem sujeito, negação, clíticos e advérbios curtos. O clítico
# pode vir com etiqueta errada (“o que agora a alcançar”: ‘a’ lido como conjunção).
ENTRE_ABERTURA_E_VERBO = {"DET", "NOUN", "PROPN", "PRON", "ADV"}
CLITICOS = {"o", "a", "os", "as", "lo", "la", "los", "las", "no", "na", "nos", "nas"}


def abre_oracao(token):
    """Forma com leitura finita no léxico, núcleo de uma oração aberta por subordinante ou relativo.
    Só para a identificação conservadora: basta para não afirmar ausência de verbo."""
    doc = token.doc
    if (token.i == token.sent.start or token.pos_ in GRAMATICAIS_NAO_VERBAIS or doc[token.i - 1].pos_ == "ADP"
            # Nome com determinante logo antes (“que o marido”) é sujeito, não o verbo da oração.
            or (doc[token.i - 1].pos_ == "DET" and token.pos_ not in {"VERB", "AUX"})):
        return False
    walk, passos = token.i - 1, 0
    while (walk > token.sent.start and passos < 4 and doc[walk].lower_ not in ABREM_ORACAO_FINITA
           and (doc[walk].pos_ in ENTRE_ABERTURA_E_VERBO or doc[walk].lower_ in ANTES_DO_VERBO
                or (doc[walk].lower_ in CLITICOS and doc[walk].pos_ != "ADP"))):
        walk, passos = walk - 1, passos + 1
    # “Que posto queres?”, “que desabafo!”: o ‘que’ determinante do próprio nome não abre oração.
    return doc[walk].lower_ in ABREM_ORACAO_FINITA and doc[walk].dep_ != "det"



def abre_frase(token):
    """Forma com leitura finita no léxico que abre a frase, com maiúscula e sem determinante (não há
    nada antes dela), seguida do que costuma seguir um verbo: verbo com sujeito oculto é comum
    (“Preciso falar-lhe”, “Canto quando estou só”); nome sem determinante no início segue com
    preposição ou adjetivo (“Grito no corredor”). Só para a identificação conservadora."""
    doc = token.doc
    # Palavra com letras: verbo com clítico (“falar-lhe”) não é `is_alpha` no spaCy.
    def lexical(t):
        return any(c.isalpha() for c in t.text)
    first = next((t for t in token.sent if lexical(t)), None)
    # Começo de fala ou citação dentro da frase do modelo (“…: «Preciso falar-lhe»”).
    previous = next((t for t in reversed(doc[token.sent.start:token.i]) if not t.is_space), None)
    opens = token == first or (previous is not None and previous.text in ABERTURAS_DE_FALA)
    following = next((t for t in doc[token.i + 1:token.sent.end] if lexical(t)), None)
    if not (opens and token.text[:1].isupper() and token.pos_ not in GRAMATICAIS_NAO_VERBAIS and following is not None):
        return False
    # Verbo conjugado logo depois: a forma inicial é o sujeito dele (“Quaresma disse…”). Só um
    # infinitivo continua um verbo inicial (“Preciso falar-lhe”), mesmo lido como conjugado.
    if following.pos_ in {"VERB", "AUX"}:
        stem = following.lower_.split("-")[0]
        return infinitivo(following) or bool(flags(following.text) & NONFINITE and stem.endswith("r"))
    return following.pos_ in CONTINUAM_VERBO or following.lower_ in ABREM_ORACAO_FINITA


def ha_forma_verbal(token):
    """Verificação de presença: verbo conjugado pelo modelo ou, quando ele erra a classe, pelo léxico
    (forma só verbal, sem leitura nominal): “É porque…”, “a fila só crescia”."""
    value = flags(token.text)
    # O léxico conhece a palavra e nunca como verbo finito (“Oh”, “perdão”, “romance”): a etiqueta
    # verbal do modelo não basta. O mesmo veto da identificação positiva.
    if value and not value & FINITE:
        return False
    if conjugado_pelo_modelo(token):
        return True
    return bool(value & FINITE and not value & NONVERB)
