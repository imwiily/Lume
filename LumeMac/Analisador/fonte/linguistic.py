"""Primeiro conjunto de regras determinísticas. Nenhuma altera o manuscrito.

Padrões sintáticos conservadores ficam na narração. Pontuação, espaços e
interrogação também são revistos em falas e pensamentos, sem formalizar a voz.
Trechos de papéis diferentes nunca são concatenados.
"""
from dataclasses import asdict
import re
from .analysis import finding
from .segments import classify, spans

RULES = {
    "construcao_invalida": [
        (r"\balém[ \t]+de[ \t]+disso\b", "Construção inválida", "confirmed_error", .99,
         "A locução é ‘além disso’. Há uma preposição ‘de’ excedente nesta construção.", "além disso"),
    ],
    "pontuacao_duplicada": [
        (r",{2,}|;{2,}", "Pontuação duplicada", "confirmed_error", .98,
         "O mesmo sinal foi repetido. Confira a digitação; uma única ocorrência costuma ser suficiente.", None),
        (r"(?<!\.)\.{2}(?!\.)", "Dois pontos finais", "probable_error", .9,
         "Foram encontrados dois pontos finais seguidos. Confira se a intenção é um ponto final ou reticências (três pontos).", None),
    ],
    "que_tonico_interrogativo": [
        (r"\bque(?=[ \t]*[?!])", "Acento em ‘quê’ interrogativo", "probable_error", .95,
         "O ‘que’ está no fim de uma pergunta ou exclamação, posição em que costuma ser tônico: ‘quê’. Confira se a grafia sem acento foi intencional.", "quê"),
    ],
    "espacamento": [
        (r"(?<=\w) {2,}(?=\w)", "Espaço repetido", "probable_error", .9,
         "Há mais de um espaço entre palavras. Confira se o espaçamento é intencional.", " "),
        (r"(?<=\w) +(?=[,;])", "Espaço antes de pontuação", "probable_error", .9,
         "Há espaço antes de vírgula ou ponto e vírgula. Confira a digitação.", ""),
    ],
    "virgula_que_nao": [
        (r"\bque,[ \t]+não\b", "Vírgula após ‘que’", "probable_error", .85,
         "A vírgula parece separar ‘que’ da oração iniciada por ‘não’. Confira se há um inciso ou uma interrupção intencional antes de removê-la.", None),
    ],
}


def analyze(blocks, settings):
    labels = classify(blocks, settings)
    out = []
    for block, roles in zip(blocks, labels):
        for rule, patterns in RULES.items():
            if not settings["rules"][rule]:
                continue
            mechanical = rule in {"pontuacao_duplicada", "espacamento", "que_tonico_interrogativo"}
            allowed = ["narracao", "dialogo", "pensamento"] if mechanical else ["narracao"]
            for start, end, role in spans(roles, allowed):
                text = block.text[start:end]
                if role != "narracao" and not any(c.isalpha() for c in text):
                    continue
                for pattern, category, severity, score, reason, replacement in patterns:
                    for match in re.finditer(pattern, text, re.I):
                        # “que, não obstante o frio, ...” é um inciso possível.
                        if rule == "virgula_que_nao" and re.match(
                                r"\s*(?:obstante\b|só\b|apenas\b|,)", text[match.end():], re.I):
                            continue
                        suggestion = replacement
                        level = "probable_error" if role != "narracao" else severity
                        if rule == "que_tonico_interrogativo":
                            suggestion = replacement.upper() if match[0].isupper() else replacement.capitalize() if match[0][0].isupper() else replacement
                        if rule == "construcao_invalida" and match[0].isupper():
                            suggestion = suggestion.upper()
                        elif rule == "construcao_invalida" and match[0][0].isupper():
                            suggestion = suggestion[0].upper() + suggestion[1:]
                        elif rule == "pontuacao_duplicada" and match[0][0] in ",;":
                            suggestion = match[0][0]
                        elif rule == "virgula_que_nao":
                            suggestion = match[0].replace(",", "", 1)
                        item = asdict(finding(block, category, "Verificar", start + match.start(),
                                              start + match.end(), reason, "FONTE Linguístico · " + rule))
                        item.update(rule=rule, category_code=rule, severity=level,
                                    confidence="alta" if score >= .9 else "média",
                                    confidence_score=score, suggestion=suggestion)
                        out.append(item)
    return out
