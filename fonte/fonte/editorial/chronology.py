import re
from ..analysis import explicar
from .common import alert, evidence, nearby

NUMBERS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3,
           "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}
N = r"(?:\d{1,2}|" + "|".join(NUMBERS) + r")"
RANGE = re.compile(r"\bamanhã\s+(?:nem|e)\s+(?:n?os?\s+)?(" + N + r")\s+dias?\s+seguintes\b", re.I)
TERM = re.compile(r"\b(?:suspens[oa]|suspensão|afastad[oa])\s+(?:por|de)\s+(" + N + r")\s+dias?\b", re.I)
DELAY = re.compile(r"\badiad[oa]\b[^.!?\n]{0,100}\b(?:para|pra)\s+amanhã\b", re.I)
EXTRA = re.compile(r"\bmais\s+(" + N + r")\s+dias?\b", re.I)

def number(text):
    return int(text) if text.isdigit() else NUMBERS[text.casefold()]

def analyze(blocks):
    out = []
    for i, block in enumerate(blocks):
        if block.heading:
            continue
        candidates = [block, *nearby(blocks, i)]
        for match in RANGE.finditer(block.text):
            duration = number(match[1]) + 1
            for other in candidates:
                term = TERM.search(other.text)
                if term and number(term[1]) != duration:
                    out.append(alert(block, "duracao_suspensao", "Possível inconsistência temporal", match.start(), match.end(),
                        explicar(f"Aqui são amanhã e mais {duration-1} dias, {duration} no total. O trecho relacionado fala em "
                                 f"{number(term[1])} dias. Confira se os dois falam da mesma pessoa, do mesmo castigo e da "
                                 "mesma contagem (dias corridos ou de aula).", "continuidade de prazos"),
                        "alta", [evidence(other, term.start(), term.end())]))
                    break
        for match in DELAY.finditer(block.text):
            for other in candidates:
                extra = EXTRA.search(other.text)
                if extra and number(extra[1]) > 1:
                    out.append(alert(block, "adiamento_amanha", "Possível inconsistência temporal", match.start(), match.end(),
                        explicar(f"O adiamento é para amanhã, mas logo perto se fala em mais {number(extra[1])} dias. Se a "
                                 "atividade seria hoje, o ganho é de um dia só. Confira a data original e se os trechos "
                                 "falam do mesmo evento.", "continuidade de prazos"),
                        "média", [evidence(other, extra.start(), extra.end())]))
                    break
    return out
