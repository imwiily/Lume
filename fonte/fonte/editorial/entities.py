from collections import defaultdict
import re
from .repetition import STOP
from ..analysis import explicar
from .common import WORDS, alert, evidence
from ..lexicon import CLITIC, flags


def one_edit(a, b):
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), len(a))
    return a[i:] == b[i+1:]


def analyze(blocks, ignored_names=()):
    ignored={x.casefold() for x in ignored_names}
    occurrences = defaultdict(list)
    for block in blocks:
        if block.heading:
            continue
        for token in WORDS.finditer(block.text):
            word = token[0]
            if (len(word) >= 4 and word[0].isupper() and not word.isupper()
                    and word.casefold() not in STOP and word.casefold() not in ignored and not flags(word)
                    and not re.fullmatch(r"h+[aeiou]*m*", word.casefold())
                    and len(set(word.casefold())) > 2
                    and not re.search(r"(.)\1{2}", word.casefold())):
                occurrences[word].append((block, token))
    # Agrupamento por primeira letra e tamanho evita comparação quadrática global.
    buckets = defaultdict(list)
    for word in sorted(occurrences):
        buckets[(word[0].casefold(), len(word))].append(word)
    out, used = [], set()
    for word in sorted(occurrences):
        for length in range(len(word)-1, len(word)+2):
            for other in buckets[(word[0].casefold(), length)]:
                pair = tuple(sorted((word, other)))
                if pair in used or not one_edit(word.casefold(), other.casefold()):
                    continue
                used.add(pair)
                if max(len(occurrences[word]), len(occurrences[other])) < 2:
                    continue
                block, token = occurrences[word][0]
                old, match = occurrences[other][0]
                out.append(alert(block, "variacao_nome", "Possível variação de nome", token.start(), token.end(),
                    explicar(f"“{word}” ({len(occurrences[word])} vezes) e “{other}” ({len(occurrences[other])} vezes) "
                             "se escrevem quase igual. Podem ser nomes diferentes; confira se é o mesmo nome escrito de "
                             "dois jeitos.", "variação de grafia de nome"),
                    "média", [evidence(old, match.start(), match.end())]))
    return out + capitalization(blocks, ignored)


TERMS = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
SENTENCE_OPENERS = ".!?…:;—–\"“”«»‘’("


def capitalization(blocks, ignored=()):
    """O mesmo termo da obra com e sem maiúscula no meio da frase (“um yokai” e “o Yokai”, “a
    Mulher-Corvo” e “a mulher-corvo”). Só termos fora do léxico comum ou compostos com hífen:
    palavras comuns mudam de sentido com a maiúscula (“o Sol”, “o sol”)."""
    forms = defaultdict(lambda: defaultdict(list))
    for block in blocks:
        if block.heading:
            continue
        for match in TERMS.finditer(block.text):
            word = match[0]
            before = block.text[:match.start()].rstrip()
            if not before or before[-1] in SENTENCE_OPENERS or word.isupper() or len(word) < 3:
                continue
            key = word.casefold()
            # Palavra comum do léxico; com hífen, só se o hífen for de pronome enclítico (“disse-me”):
            # composto com hífen (“Mulher-Corvo”) pode ser termo da obra.
            if key in ignored or (flags(word) and ("-" not in word or CLITIC.search(word))):
                continue
            forms[key][word[0].isupper()].append((block, match))
    out = []
    for key, by_case in sorted(forms.items()):
        if not (by_case[True] and by_case[False]):
            continue
        (upper_block, upper), (lower_block, lower) = by_case[True][0], by_case[False][0]
        out.append(alert(lower_block, "variacao_nome", "Grafia oscilante", lower.start(), lower.end(),
            explicar(f"“{upper[0]}” ({len(by_case[True])} vezes) e “{lower[0]}” ({len(by_case[False])} vezes) aparecem "
                     "com e sem letra maiúscula no meio da frase. Confira se o termo deveria ser escrito sempre do "
                     "mesmo jeito.", "grafia oscilante"),
            "média", [evidence(upper_block, upper.start(), upper.end())]))
    return out
