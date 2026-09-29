"""Contrato aditivo ao relatório v1 e índice estável do texto extraído.

range usa pontos de código Unicode sobre os parágrafos não vazios, unidos por
um único LF. Não é uma posição no XML do DOCX nem uma posição UTF-16.
"""
from dataclasses import dataclass
import hashlib

MODULES = ("linguistic", "morphosyntactic", "editorial", "global_coherence", "audit")
SEVERITIES = ("confirmed_error", "probable_error", "editorial_attention",
              "possible_inconsistency", "author_query")


@dataclass(frozen=True)
class FrozenBlock:
    number: int
    text: str
    chapter: str
    heading: bool
    italic: tuple


@dataclass(frozen=True)
class Manuscript:
    blocks: tuple
    offsets: tuple
    text: str

    @classmethod
    def capture(cls, blocks):
        frozen = tuple(FrozenBlock(b.number, b.text, b.chapter, b.heading,
                                   tuple(tuple(x) for x in b.italic)) for b in blocks)
        if len({b.number for b in frozen}) != len(frozen):
            raise ValueError("Parágrafos com identificadores duplicados.")
        offsets, cursor = [], 0
        for block in frozen:
            offsets.append(cursor)
            cursor += len(block.text) + 1
        return cls(frozen, tuple(offsets), "\n".join(b.text for b in frozen))

    def index(self):
        return {
            "unit": "unicode_codepoint", "separator": "\n",
            "scope": "nonempty_body_paragraphs_and_tables",
            "length": len(self.text),
            "sha256": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "paragraphs": [{"paragraph": b.number, "start": offset,
                            "end": offset + len(b.text)}
                           for b, offset in zip(self.blocks, self.offsets)],
        }


def standardize(items, module, manuscript):
    """Mantém IDs e campos antigos para preservar decisões e leitores v1."""
    locations = {b.number: (b, offset) for b, offset in zip(manuscript.blocks, manuscript.offsets)}
    result = []
    categories = {"Tempo verbal": "narrative_tense", "Estrutura da frase": "sentence_structure",
                  "Pontuação de diálogo": "dialogue_punctuation", "Palavra repetida": "repetition",
                  "Ortografia e gramática": "grammar"}
    for raw in items:
        item = dict(raw)
        block, offset = locations[item["paragraph"]]
        start, end = item["start"], item["end"]
        if (type(start) is not int or type(end) is not int or
                not 0 <= start < end <= len(block.text) or item["text"] != block.text):
            raise ValueError("Ocorrência incompatível com o manuscrito original.")
        severity = item.get("severity", "editorial_attention")
        if item.get("rule") in ("duracao_suspensao", "adiamento_amanha"):
            severity = "possible_inconsistency"
        elif item.get("rule") in ("referente_proximidade", "pronome_apos_corte"):
            severity = "author_query"
        elif item["source"].startswith("LanguageTool"):
            severity = "probable_error"
        confidence = item.get("confidence", "média")
        score = item.get("confidence_score", {"alta": .9, "média": .65, "baixa": .4}[confidence])
        if module not in MODULES or severity not in SEVERITIES or not 0 <= score <= 1:
            raise ValueError("Classificação de ocorrência inválida.")
        item.update(module=module, severity=severity, confidence=confidence,
                    confidence_score=score,
                    category_code=item.get("category_code", item.get("rule", categories.get(item["category"], "editorial_review"))),
                    range={"start": offset + start, "end": offset + end},
                    excerpt=block.text[start:end], message=item["reason"])
        item.setdefault("layer", "linguistica" if module in ("linguistic", "morphosyntactic") else "editorial")
        item.setdefault("suggestion", None)
        if manuscript.text[item["range"]["start"]:item["range"]["end"]] != item["excerpt"]:
            raise ValueError("Offsets globais divergentes.")
        result.append(item)
    return result
