"""Evidências com offsets Python; confiança é qualitativa, não probabilidade."""
from dataclasses import asdict
import re
import hashlib
import json
from ..analysis import finding

WORDS = re.compile(r"[^\W\d_]+", re.UNICODE)

def evidence(block, start=0, end=None, document="atual"):
    return dict(paragraph=block.number, chapter=block.chapter, text=block.text,
                start=start, end=len(block.text) if end is None else end, document=document)

def alert(block, rule, category, start, end, reason, confidence="baixa", related=()):
    result = asdict(finding(block, category, "Verificar" if confidence == "alta" else "Explorar",
                            start, end, reason, "FONTE Editorial · " + rule))
    result.update(layer="editorial", rule=rule, confidence=confidence, related=list(related))
    # Evidências diferentes (inclusive outro original) não herdam uma decisão antiga.
    identity = result["id"] + json.dumps(list(related), ensure_ascii=False, sort_keys=True)
    result["id"] = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return result

def normalized(text):
    return " ".join(WORDS.findall(text.casefold()))

def nearby(blocks, index, distance=8):
    chapter = blocks[index].chapter
    for other in blocks[index+1:index+1+distance]:
        if other.heading or other.chapter != chapter:
            break
        # Não cruza marcadores explícitos de outra cena/dia.
        if re.match(r"\s*(?:no dia seguinte|dias depois|na manhã seguinte|\*{3}|—{3})", other.text, re.I):
            break
        yield other
