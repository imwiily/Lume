"""Pronomes perto de trechos cortados em relação ao original (`pronome_apos_corte`). A regra de
proximidade de referentes foi retirada na Fase 7b (exemplo isolado). Não resolve correferência."""
from difflib import SequenceMatcher
import re
from ..analysis import explicar
from .common import WORDS, alert, evidence, normalized

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
                explicar(f"Em relação ao original, saíram pelo menos {(b-a)-(d-c)} palavras pouco antes deste pronome. "
                         "Confira se o corte tirou aquilo a que ele se refere. A comparação pode se confundir com "
                         "trechos repetidos.", "referência após corte"),
                "baixa", [evidence(p, document="original") for p in removed[:3]]))
            emitted.add((block.number, start))
            break
    return out
