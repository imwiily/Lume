"""Heurísticas deliberadamente estreitas; não resolvem correferência."""
from difflib import SequenceMatcher
import re
from .common import WORDS, alert, evidence, normalized

PRONOUN = re.compile(r"(?:^|[.!?…]\s+)(Eles|Elas|Isso|Aquilo)\b")
PLURAL = re.compile(r"\b(?:os|as|uns|umas|dois|duas|três|seus|suas|aqueles|aquelas)\s+[^\W\d_]+|\b[^\W\d_]+\s+e\s+[^\W\d_]+", re.I)


def analyze(blocks, original=None):
    out = []
    for i, block in enumerate(blocks):
        if block.heading:
            continue
        for match in PRONOUN.finditer(block.text):
            # Só a construção de proximidade, sem supor que todo pronome exige
            # antecedente textual. Não usa o final de um capítulo anterior.
            tail = block.text[match.end():]
            if match[1] not in ("Eles", "Elas") or not re.match(r"\s+(?:estavam|estão|ficaram)\s+(?:tão|muito|bem)\s+perto\b", tail, re.I):
                continue
            previous = []
            for old in reversed(blocks[max(0, i-3):i]):
                if old.heading or old.chapter != block.chapter:
                    break
                previous.insert(0, old)
            context = " ".join(b.text for b in previous) + " " + block.text[:match.start(1)]
            if not PLURAL.search(context):
                out.append(alert(block, "referente_proximidade", "Possível referência pouco clara", match.start(1), match.end(),
                    "O pronome plural descreve algo muito próximo, mas não foi encontrada uma indicação simples de antecedente plural nos três parágrafos anteriores. Pode haver um referente mais distante ou implícito. Identifique a quem o pronome se refere.",
                    "baixa", [evidence(b) for b in previous]))
    if original:
        out.extend(edit_scars(blocks, original))
    return out


def edit_scars(blocks, original):
    # Alinha palavras para tolerar parágrafos unidos/divididos na revisão.
    def tokens(items):
        result = []
        for block in items:
            for token in WORDS.finditer(block.text):
                result.append((token[0].casefold(), block, token.start(), token.end()))
        return result
    old, new = tokens(original), tokens(blocks)
    if len(old) + len(new) > 120_000:
        return []
    matcher = SequenceMatcher(None, [t[0] for t in old], [t[0] for t in new], autojunk=True)
    out, emitted = [], set()
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag not in ("delete", "replace") or b-a < 8 or (b-a) - (d-c) < 8:
            continue
        for j in range(d, min(d+35, len(new))):
            word, block, start, end = new[j]
            if block.heading:
                break
            if word not in {"eles", "elas", "isso", "aquilo"}:
                continue
            # Evita alertas repetidos para o mesmo pronome e cruzamento de capítulo.
            if (block.number, start) in emitted or (d < len(new) and block.chapter != new[d][1].chapter):
                continue
            removed = []
            for _, prior, _, _ in old[a:b]:
                if not removed or removed[-1].number != prior.number:
                    removed.append(prior)
            out.append(alert(block, "pronome_apos_corte", "Possível cicatriz de edição", start, end,
                f"Houve redução de pelo menos {(b-a)-(d-c)} palavras pouco antes deste pronome, em comparação com o original. Confira se o corte retirou seu referente. Proximidade não prova dependência; a comparação pode alinhar passagens repetidas incorretamente.",
                "baixa", [evidence(p, document="original") for p in removed[:3]]))
            emitted.add((block.number, start))
            break
    return out
