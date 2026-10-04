"""Primeiro conjunto de regras determinísticas. Nenhuma altera o manuscrito.

Padrões sintáticos conservadores ficam na narração. Pontuação, espaços e
interrogação também são revistos em falas e pensamentos, sem formalizar a voz.
Trechos de papéis diferentes nunca são concatenados.
"""
from dataclasses import asdict
import re
from .analysis import finding
from .lexicon import FINITE, FUTURE, NONVERB, PAST, flags
from .segments import classify, spans

RULES = {
    "vocativo": [],
    "capitalizacao_contextual": [
        (r"(?<=[?!])[ \t]+(eu|tu|ele|ela|nós|vós|eles|elas|você|vocês)\b", "Inicial após pergunta ou exclamação", "probable_error", .85,
         "Após a pergunta ou exclamação, o pronome parece iniciar uma nova frase. Confira se a continuação é independente antes de usar maiúscula.", None),
    ],
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

# Chamamento inicial + pronome de tratamento ou proibição curta. Não tenta
# decidir casos ambíguos como “Helena saiu” nem usa nomes de uma obra.
NAME = r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ\u0300-\u036f]+"
VOCATIVE = re.compile(r"(?:^|[.!?][ \t]+)[ \t]*(?P<name>" + NAME +
                     r"(?:[ \t]+" + NAME + r"){0,2})(?=[ \t]+(?:vocês?\b|tu\b|não[ \t]+(?:faça|façam|diga|digam|vá|vão|venha|venham|toque|toquem|entre|entrem|saia|saiam|olhe|olhem)\b))")
INTRODUCERS = set("mas e ou nem porém pois contudo todavia aliás senão hoje amanhã ontem agora atualmente talvez assim então aqui ali lá depois antes sempre nunca ainda quando enquanto como onde aonde donde porque pois porém contudo entretanto portanto logo caso se embora somente apenas até sim não bem ora ei olá oi quem qual quais quanto quanta quantos quantas que".split())
# Resposta ou cumprimento seguido de chamamento: “Não senhora.”, “Bom dia Clara!”.
# O vocativo é pronome de tratamento, parentesco ou nome, antes de pontuação.
ADDRESS = re.compile(r"(?:^|(?<=[—–.!?…])\s*|(?<=[—–]))\s*(?P<lead>Sim|Não|Obrigad[oa]|Olá|Oi|Bom dia|Boa tarde|Boa noite|Adeus|Tchau)"
                     r"(?P<gap>[ \t]+)(?P<name>senhor(?:a|es|as)?|moç[oa]|mãe|pai|vovó|vovô|doutor(?:a)?|professor(?:a)?|"
                     r"chefe|mestre|madame|querid[oa]|amor|filh[oa]|(?:dona|seu)[ \t]+" + NAME + r"|" + NAME + r")"
                     r"(?=[ \t]*(?:[.!?…,—–]|$))")


# Nome inicial + aposto de afeto (“meu amigo”, “querida”) + verbo, sem vírgulas: vocativo com aposto.
APPOSITIVE_VOCATIVE = re.compile(r"(?:^|(?<=[.!?…])[ \t]+)(?P<name>" + NAME + r")[ \t]+(?P<apposto>(?:meu|minha|meus|minhas)[ \t]+"
                                 r"[a-zà-öø-ÿ]+|querid[oa]s?|amad[oa]s?)[ \t]+(?P<verbo>[a-zà-öø-ÿ]+)\b")


def vocatives(block, start, text):
    for match in APPOSITIVE_VOCATIVE.finditer(text):
        verbo, nome = flags(match['verbo']), flags(match['name'])
        # O verbo só pode ser forma verbal finita que não é passado nem futuro (“venha”, “espere”); o nome, nunca verbo.
        if not (verbo & FINITE and not verbo & (NONVERB | PAST | FUTURE)) or nome & FINITE:
            continue
        yield vocative_item(block, start + match.start('name'), start + match.end('apposto'),
                            f"{match['name']}, {match['apposto']},",
                            "O nome inicial e o aposto que o qualifica parecem chamar o interlocutor antes de um pedido. "
                            "Se forem vocativo, separe-os por vírgulas; confira se não são o sujeito da frase.")
    for match in VOCATIVE.finditer(text):
        name = match['name']
        primeira = name.split()[0]
        if primeira.casefold() in INTRODUCERS:
            continue
        # “Achei você”: uma forma que o léxico só conhece como verbo não é chamamento.
        valor = flags(primeira)
        if valor & FINITE and not valor & NONVERB:
            continue
        yield vocative_item(block, start + match.start('name'), start + match.end('name'), name + ",",
                            "O nome inicial parece chamar o interlocutor, antes de um pronome de tratamento ou de uma proibição. Se for vocativo, separe-o por vírgula; confira se não é o sujeito da frase.")
    for match in ADDRESS.finditer(text):
        yield vocative_item(block, start + match.start('lead'), start + match.end('name'),
                            match['lead'] + ", " + match['name'],
                            "Depois de resposta ou cumprimento, o chamamento ao interlocutor é vocativo e se separa por vírgula.")


def vocative_item(block, start, end, suggestion, reason):
    item = asdict(finding(block, "Possível vocativo sem vírgula", "Verificar", start, end, reason,
                          "FONTE Linguístico · vocativo"))
    item.update(rule="vocativo", category_code="vocativo", severity="probable_error",
                confidence="média", confidence_score=.85, suggestion=suggestion,
                suggestion_kind="possible")
    return item


def analyze(blocks, settings):
    labels = classify(blocks, settings)
    out = []
    for block, roles in zip(blocks, labels):
        for rule, patterns in RULES.items():
            if not settings["rules"][rule]:
                continue
            mechanical = rule in {"pontuacao_duplicada", "espacamento", "que_tonico_interrogativo", "vocativo", "capitalizacao_contextual"}
            allowed = ["narracao", "dialogo", "pensamento"] if mechanical else ["narracao"]
            for start, end, role in spans(roles, allowed):
                text = block.text[start:end]
                if role != "narracao" and not any(c.isalpha() for c in text):
                    continue
                if rule == "vocativo":
                    out.extend(vocatives(block, start, text))
                for pattern, category, severity, score, reason, replacement in patterns:
                    for match in re.finditer(pattern, text, 0 if rule == "capitalizacao_contextual" else re.I):
                        # “que, não obstante o frio, ...” é um inciso possível.
                        if rule == "virgula_que_nao" and re.match(
                                r"\s*(?:obstante\b|só\b|apenas\b|,)", text[match.end():], re.I):
                            continue
                        suggestion = replacement
                        if rule == "capitalizacao_contextual":
                            suggestion = match[0].replace(match[1], match[1].capitalize(), 1)
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
                                    confidence_score=score, suggestion=suggestion,
                                    suggestion_kind="required" if level == "confirmed_error" else "possible")
                        out.append(item)
    return out
