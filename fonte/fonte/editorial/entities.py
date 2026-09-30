from collections import defaultdict
import re
from .repetition import STOP
from .common import WORDS, alert, evidence
from ..lexicon import flags


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
                    f"“{word}” ({len(occurrences[word])} ocorrências) e “{other}” ({len(occurrences[other])}) têm grafias próximas. Podem ser nomes distintos. Confirme a grafia com o autor; nenhuma variante foi escolhida automaticamente.",
                    "média", [evidence(old, match.start(), match.end())]))
    return out
