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
    narrative_role: str = 'body'


@dataclass(frozen=True)
class Manuscript:
    blocks: tuple
    offsets: tuple
    text: str

    @classmethod
    def capture(cls, blocks):
        frozen = tuple(FrozenBlock(b.number, b.text, b.chapter, b.heading,
                                   tuple(tuple(x) for x in b.italic), getattr(b, 'narrative_role', 'body')) for b in blocks)
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


DESTINATIONS = ("diagnostico", "informacao", "pendencia")


def check_destination(item):
    """Destino e impedimento da política: impeditivo só numa pendência de severidade de erro."""
    if item.get("destino") not in DESTINATIONS or type(item.get("impeditivo")) is not bool:
        raise ValueError("Destino editorial inválido.")
    if item["impeditivo"] and (item["destino"] != "pendencia"
                               or item.get("severity") not in ("confirmed_error", "probable_error")):
        raise ValueError("Impeditivo exige pendência com severidade de erro.")


class InvalidOccurrence(ValueError):
    """Ocorrência cujo trecho ou evidência não corresponde ao manuscrito capturado."""


def standardize(items, module, manuscript, rejected=None):
    """Mantém IDs e campos antigos para preservar decisões e leitores v1.

    Ocorrência com trecho ou evidência fora do manuscrito interrompe a etapa, salvo quando
    `rejected` é uma lista: então ela é descartada sozinha e descrita ali, e as demais seguem.
    Nenhum alerta aponta trecho inexistente em nenhum dos dois casos."""
    locations = {b.number: (b, offset) for b, offset in zip(manuscript.blocks, manuscript.offsets)}
    result = []
    categories = {"Tempo verbal": "narrative_tense", "Estrutura da frase": "sentence_structure",
                  "Pontuação de diálogo": "dialogue_punctuation", "Palavra repetida": "repetition",
                  "Ortografia e gramática": "grammar"}
    for raw in items:
        try:
            item = occurrence(raw, module, manuscript, locations, categories)
        except InvalidOccurrence as error:
            if rejected is None:
                raise
            rejected.append({"module": module, "rule": raw.get("rule", raw.get("category")),
                             "paragraph": raw.get("paragraph"), "start": raw.get("start"),
                             "end": raw.get("end"), "reason": str(error)})
            continue
        result.append(item)
    return result


def occurrence(raw, module, manuscript, locations, categories):
    """Uma ocorrência no formato do relatório; InvalidOccurrence se não corresponder ao texto."""
    item = dict(raw)
    block, offset = locations[item["paragraph"]]
    start, end = item["start"], item["end"]
    if (type(start) is not int or type(end) is not int or
            not 0 <= start < end <= len(block.text) or item["text"] != block.text):
        raise InvalidOccurrence("Ocorrência incompatível com o manuscrito original "
                                f"(módulo {module}, regra {item.get('rule', item['category'])}, "
                                f"parágrafo {block.number}, intervalo {start}:{end}, "
                                f"comprimento {len(block.text)}).")
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
    def enrich(proof):
        proof = dict(proof)
        if proof.get("document", "atual") == "atual" and proof.get("paragraph") in locations:
            source, base = locations[proof["paragraph"]]
            lo, hi = proof["start"], proof["end"]
            if not 0 <= lo <= hi <= len(source.text) or proof["text"] != source.text:
                raise InvalidOccurrence("Evidência incompatível com o manuscrito original "
                                        f"(parágrafo {proof['paragraph']}, intervalo {lo}:{hi}).")
            proof.update(type="text_evidence", range={"start": base+lo, "end": base+hi},
                         excerpt=source.text[lo:hi])
        return proof
    for field in ("related", "context", "evidence"):
        if field in item:
            item[field] = [enrich(proof) for proof in item[field]]
    item.setdefault("evidence", [enrich(dict(paragraph=block.number, chapter=block.chapter,
                        text=block.text, start=start, end=end, document="atual")), *item.get("related", [])])
    if manuscript.text[item["range"]["start"]:item["range"]["end"]] != item["excerpt"]:
        raise ValueError("Offsets globais divergentes.")
    return item
