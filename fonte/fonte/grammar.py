"""Concordância, crase, homófonos, regência e vírgula com apoio sintático.

Cada regra cobre uma classe gramatical e se abstém diante de leituras
alternativas plausíveis. Grafia (crase e homófonos) é revista também em falas;
concordância, regência e vírgula entre sujeito e verbo só na narração, para não
formalizar a voz de personagens. Nenhuma regra usa nomes ou frases de obras.
"""
from dataclasses import asdict
import re

from .analysis import finding, verbo_de_fala
from .lexicon import FINITE, NONVERB, flags
from .segments import classify

RULES = ("crase", "homofonos", "concordancia", "regencia", "virgula_sujeito_verbo")
SCOPES = {
    "crase": {"narracao", "dialogo", "pensamento"},
    "homofonos": {"narracao", "dialogo", "pensamento"},
    "concordancia": {"narracao"},
    "regencia": {"narracao"},
    "virgula_sujeito_verbo": {"narracao"},
}
NUMBERS = ("uma|um|duas|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quatorze|"
           "quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|"
           "setenta|oitenta|noventa|cem|\\d{1,4}")
TIME_UNITS = {"tempo", "ano", "anos", "mês", "meses", "semana", "semanas", "dia", "dias", "hora", "horas",
              "minuto", "minutos", "segundo", "segundos", "século", "séculos", "década", "décadas"}
QUANTIFIERS = {"pouco", "muito", "bastante", "algum", "alguns", "algumas", "vários", "várias", "tanto", "tantos"}
DATIVE = set("entregar dar contar dizer pedir mostrar oferecer enviar mandar explicar perguntar responder "
             "devolver emprestar levar trazer apresentar ensinar prometer agradecer comunicar revelar "
             "confessar escrever vender pagar doar sugerir recomendar relatar anunciar".split())
COMMON_GENDER = {"chefe", "jovem", "colega", "intérprete", "rival", "mártir", "cliente", "hóspede"}
LOCUTIONS = re.compile(r"\b(em direção|devido|graças|junto|frente|em frente|em relação|rumo|quanto|referente|"
                       r"em resposta|em homenagem|semelhante|igual|contrári[oa]|próxim[oa]|obediente|fiel)"
                       r"\s+(a)\s+(?=\w)", re.I)
STATIC = {"estar", "ficar", "morar", "viver", "residir", "hospedar", "trabalhar", "esconder", "guardar",
          "nascer", "dormir", "estudar", "situar", "localizar", "encontrar"}
COLLECTIVE = {"maioria", "parte", "metade", "grupo", "porção", "conjunto", "bando", "multidão", "resto",
              "total", "série", "número", "maior", "minoria", "quantidade", "pessoal", "gente", "turma"}
EACH = {"nenhum", "nenhuma", "cada", "qualquer", "ninguém"}
INVARIABLE = {"cinza", "rosa", "laranja", "vinho", "creme", "gelo", "salmão", "musgo", "oliva", "turquesa",
              "anil", "caqui", "abóbora", "simples", "reles", "grátis", "vermelho-escuro", "azul-marinho"}
INTRANSITIVE = {"ser", "estar", "ficar", "parecer", "permanecer", "continuar", "tornar", "virar", "chegar", "sair",
                "entrar", "voltar", "vir", "ir", "partir", "surgir", "aparecer", "nascer", "morrer", "cair", "correr",
                "sorrir", "rir", "acordar", "dormir", "existir", "acontecer", "restar", "sobrar", "faltar"}
NON_PLACE = {"hora", "horas", "tempo", "momento", "instante", "silêncio", "minuto", "minutos", "segundo",
             "segundos", "dia", "dias", "semana", "semanas", "mês", "meses", "ano", "anos", "lugar", "vez",
             "cima", "conclusão", "acordo", "consenso", "paz", "vão", "forma", "estado", "condição", "ponto",
             "meio", "fim", "começo", "início", "final", "noite", "manhã", "tarde", "madrugada",
             "época", "idade", "primeiro", "último", "prantos", "lágrimas"}


def item(block, rule, category, start, end, reason, severity, score, suggestion=None):
    value = asdict(finding(block, category, "Verificar", start, end, reason, "FONTE Morfossintático · " + rule))
    value.update(rule=rule, category_code=rule, severity=severity,
                 confidence="alta" if score >= .9 else "média" if score >= .6 else "baixa",
                 confidence_score=score, suggestion=suggestion,
                 suggestion_kind="required" if severity == "confirmed_error" else "possible")
    return value


def cased(model, replacement):
    return replacement[0].upper() + replacement[1:] if model[:1].isupper() else replacement


class Lemmas:
    """No início da frase, o modelo pequeno pode marcar o verbo como nome
    próprio. Uma segunda leitura em minúscula, só da palavra confirmada como
    verbo finito pelo léxico, recupera o lema sem alterar o texto."""
    nlp = None
    cache = {}


def verbal(token):
    """Verbo conjugado pelo modelo ou, quando ele erra a classe, pelo léxico
    (forma só verbal, sem leitura nominal): “É porque…”, “a fila só crescia”."""
    if token.pos_ in {"VERB", "AUX"} and "Fin" in token.morph.get("VerbForm"):
        return True
    value = flags(token.text)
    return bool(value & FINITE and not value & NONVERB)


def verb_lemma(token):
    if token.pos_ in {"VERB", "AUX"}:
        return token.lemma_.casefold()
    if token.i != token.sent.start or token.pos_ != "PROPN" or Lemmas.nlp is None:
        return None
    value = flags(token.text)
    if not value & FINITE or value & NONVERB:
        return None
    key = token.lower_
    if key not in Lemmas.cache:
        Lemmas.cache[key] = Lemmas.nlp(key)[0].lemma_.casefold()
    return Lemmas.cache[key]


def crase(block, doc, emit):
    text = block.text
    fixed = [
        (r"\bas pressas\b", "às pressas"), (r"\bas escondidas\b", "às escondidas"),
        (r"\bas avessas\b", "às avessas"), (r"\ba toa\b", "à toa"), (r"\ba beça\b", "à beça"),
    ]
    for pattern, replacement in fixed:
        for match in re.finditer(pattern, text, re.I):
            emit("crase", "Crase em locução", match.start(), match.end(), "probable_error", .9,
                 f"Locução adverbial feminina que leva acento grave: ‘{replacement}’.",
                 cased(match[0], replacement))
    for match in re.finditer(r"\bas vezes\b(?!\s+(?:que|em)\b)", text, re.I):
        before = text[:match.start()].split()
        if before and re.sub(r"\W", "", before[-1].casefold()) in {
                "todas", "poucas", "muitas", "várias", "algumas", "das", "nas", "pelas", "quantas",
                "raras", "duas", "três", "tantas", "mesmas", "outras", "demais"}:
            continue
        emit("crase", "Crase em locução", match.start(), match.end(), "probable_error", .85,
             "Na locução adverbial de frequência, usa-se ‘às vezes’. Sem acento, ‘as vezes’ é artigo e substantivo.",
             cased(match[0], "às vezes"))
    # Hora marcada: “chegou as seis horas da manhã” → “às seis”.
    hour = re.compile(r"\b(as|a)\s+(" + NUMBERS + r")(?:\s+horas?)?(?:\s+e\s+\w+)?"
                      r"(?=\s+(?:horas?\s+)?(?:da manhã|da tarde|da noite|da madrugada|em ponto)\b)", re.I)
    for match in hour.finditer(text):
        if match[1].casefold() == "a" and match[2].casefold() != "uma":
            continue
        before = text[:match.start()].split()
        if before and re.sub(r"\W", "", before[-1].casefold()) in {"todas", "durante", "por", "das", "nas", "pelas", "as", "entre"}:
            continue
        emit("crase", "Crase antes de horas", match.start(), match.end(1), "probable_error", .9,
             "Na indicação de hora marcada, a preposição ‘a’ se funde ao artigo: ‘às seis horas’, ‘à uma hora’.",
             cased(match[1], "à" if match[1].casefold() == "a" else "às"))
    for token in doc:
        low = token.lower_
        nxt = doc[token.i + 1] if token.i + 1 < len(doc) else None
        if nxt is None:
            continue
        # Crase antes de verbo no infinitivo ou de palavra masculina fixa.
        if low == "à" and ("Inf" in nxt.morph.get("VerbForm") and nxt.lower_.endswith("r")
                           or nxt.lower_ in {"pé", "cavalo", "bordo", "prazo", "respeito", "lápis"}):
            emit("crase", "Crase indevida", token.idx, nxt.idx + len(nxt.text), "probable_error", .9,
                 "Não há crase antes de verbo no infinitivo nem de palavra masculina: use ‘a’.",
                 cased(token.text, "a") + text[token.idx + 1:nxt.idx + len(nxt.text)])
        # “entregou o presente a irmã”: objeto direto já expresso, destinatário feminino com artigo.
        if low == "a" and nxt.pos_ == "NOUN" and "Plur" not in nxt.morph.get("Number") and (
                "Fem" in nxt.morph.get("Gender") or nxt.lower_ in COMMON_GENDER
                or nxt.lower_.endswith(("nte", "ista"))):
            previous = doc[token.i - 1] if token.i else None
            if previous is None or previous.pos_ not in {"NOUN", "PRON", "ADJ"} or previous.lower_ in {"que", "a", "o"}:
                continue
            verb = next((t for t in reversed(doc[token.sent.start:token.i])
                         if t.pos_ in {"VERB", "AUX"} or t.is_punct or verb_lemma(t)), None)
            if verb is None or verb.is_punct or verb_lemma(verb) not in DATIVE:
                continue
            between = doc[verb.i + 1:token.i]
            # Objeto pode ser adjetivo substantivado: “entregou o maior a tia”.
            nominal = any(t.pos_ in {"NOUN", "PRON"} or (t.pos_ in {"ADJ", "NUM"} and t.i > 0 and doc[t.i - 1].pos_ == "DET")
                          for t in between)
            if not nominal or any(
                    t.lower_ in {"à", "para", "e", "ou"} or (t.lower_ == "a" and t.pos_ == "ADP")
                    or t.is_punct for t in between):
                continue
            emit("crase", "Crase ausente", token.idx, nxt.idx + len(nxt.text), "probable_error", .75,
                 f"O verbo ‘{verb.text}’ já tem objeto direto; o destinatário feminino recebe a preposição ‘a’ somada ao artigo: ‘à {nxt.text}’.",
                 cased(token.text, "à") + text[token.idx + 1:nxt.idx + len(nxt.text)])
    for match in LOCUTIONS.finditer(text):
        word = next((t for t in doc if t.idx >= match.end()), None)
        if (word is None or word.pos_ != "NOUN" or "Fem" not in word.morph.get("Gender")
                or "Plur" in word.morph.get("Number") or word.lower_ == match[1].split()[-1].casefold()):
            continue
        emit("crase", "Crase ausente", match.start(2), word.idx + len(word.text), "probable_error", .85,
             f"A locução ‘{match[1]} a’ pede preposição; diante de palavra feminina com artigo, use ‘à {word.text}’.",
             "à" + text[match.end(2):word.idx + len(word.text)])


def homophones(block, doc, emit):
    text = block.text
    # Pergunta de confirmação no fim (“…, hein?”, “…, né?”) não torna a explicação uma pergunta direta.
    etiqueta = re.compile(r",\s*(?:hein|né|viu|sabe|entende|entendeu|certo|ok|tá|não é|não)\s*\?", re.I)
    for match in re.finditer(r"(?:^|(?<=[—–.!?…]\s)|(?<=[—–]))\s*\b(Porque)\b([^.!?…]*\?)", text):
        if etiqueta.search(match[2]):
            continue
        emit("homofonos", "Por que / porque", match.start(1), match.end(1), "probable_error", .9,
             "Em pergunta direta, usa-se ‘por que’ (separado); ‘porque’ junto introduz explicação ou causa.",
             "Por que")
    for match in re.finditer(r"\bporque(?=\s*\?)", text, re.I):
        emit("homofonos", "Por que / porque", match.start(), match.end(), "probable_error", .85,
             "No fim de pergunta, a forma é ‘por quê’, separada e acentuada.", cased(match[0], "por quê"))
    for match in re.finditer(r",\s+(mais)\s+(?=(?:não|nunca|ninguém|nada|ele|ela|eles|elas|eu|nós|você|vocês|isso|aquilo|logo|então|também|agora|quando|sem)\b)", text, re.I):
        emit("homofonos", "Mas / mais", match.start(1), match.end(1), "probable_error", .85,
             "Após a vírgula, a palavra introduz oposição: a conjunção é ‘mas’. ‘Mais’ indica quantidade ou intensidade.",
             cased(match[1], "mas"))
    for match in re.finditer(r"\bmau[- ](\w+?(?:ad|id)[oa]s?)\b", text, re.I):
        if match[1].casefold() in {"olhado"}:
            continue
        emit("homofonos", "Mal / mau", match.start(), match.end(), "probable_error", .9,
             "Antes de particípio ou adjetivo formado dele, usa-se o advérbio ‘mal’ (oposto de ‘bem’); ‘mau’ é adjetivo (oposto de ‘bom’).",
             cased(match[0], "mal") + match[0][3:])
    for match in re.finditer(r"\b(de|em) baixo(?=\s+d[aoe]s?\b)", text, re.I):
        joined = "debaixo" if match[1].casefold() == "de" else "embaixo"
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             f"Como advérbio de lugar seguido de ‘de’, escreve-se junto: ‘{joined}’.", cased(match[0], joined))
    # Advérbio sozinho (“lá em baixo,”); “em baixo tom” segue como adjetivo.
    for match in re.finditer(r"\bem baixo(?=\s*(?:[.,;:!?…—–]|$))", text, re.I):
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             "Como advérbio de lugar, escreve-se junto: ‘embaixo’.", cased(match[0], "embaixo"))
    for match in re.finditer(r"\bencima(?=\s+d[aoe]s?\b)", text, re.I):
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             "A locução se escreve separada: ‘em cima’.", cased(match[0], "em cima"))
    for token in doc:
        nxt = doc[token.i + 1] if token.i + 1 < len(doc) else None
        # “Saiu a pouco tempo” → “há”: tempo decorrido depois de verbo.
        if token.lower_ == "a" and nxt is not None and token.i > 0:
            unit = None
            # Aproximação antes da quantidade: “a mais de uma semana”, “a cerca de dois meses”.
            first = token.i + 1
            if doc[first].lower_ in {"mais", "menos", "cerca"} and first + 1 < len(doc) and doc[first + 1].lower_ == "de":
                first += 2
            elif doc[first].lower_ in {"quase", "uns", "umas"}:
                first += 1
            quantity = doc[first] if first < len(doc) else None
            if quantity is not None and (quantity.lower_ in QUANTIFIERS or re.fullmatch(NUMBERS, quantity.lower_) or quantity.like_num):
                probe = first + 1
                while probe < len(doc) and (doc[probe].like_num or re.fullmatch(NUMBERS + "|e", doc[probe].lower_)):
                    probe += 1
                unit = doc[probe] if probe < len(doc) else None
            previous = doc[token.i - 1]
            after = doc[unit.i + 1] if unit is not None and unit.i + 1 < len(doc) else None
            if (unit is not None and unit.lower_ in TIME_UNITS
                    and (previous.pos_ in {"VERB", "AUX"} or "Part" in previous.morph.get("VerbForm"))
                    and previous.lower_ not in {"daqui", "dali", "daí", "faltava", "faltam", "falta", "chegar", "voltar"}
                    and (after is None or after.lower_ not in {"de", "da", "do", "das", "dos", "daqui", "depois", "mais", "antes", "atrás"})):
                emit("homofonos", "Há / a", token.idx, unit.idx + len(unit.text), "probable_error", .85,
                     "Para tempo já decorrido, usa-se o verbo ‘haver’: ‘há’ (ou ‘havia’, em narração no passado). ‘A’ indica tempo futuro ou distância.",
                     cased(token.text, "há") + text[token.idx + 1:unit.idx + len(unit.text)])
        # “Mãe, porque ninguém avisou?”: sem verbo antes, só vocativo ou conjunção,
        # ainda é pergunta direta. Depois de uma oração (“saiu porque…?”) é causa.
        # O léxico confirma verbos que o modelo não marca no início da frase (“É porque…”).
        if (token.text == "porque" and "?" in doc.text[token.idx:token.sent.end_char]
                and not etiqueta.search(doc.text[token.idx:token.sent.end_char])
                and not any(verbal(t) for t in doc[token.sent.start:token.i])):
            emit("homofonos", "Por que / porque", token.idx, token.idx + len(token.text), "probable_error", .85,
                 "Em pergunta direta, usa-se ‘por que’ (separado); ‘porque’ junto introduz explicação ou causa.",
                 "por que")
        # “…, mais a fila não parava”: há verbo conjugado no mesmo trecho, antes
        # de pontuação ou ‘que’; na soma (“os três, mais o motorista, …”) não há.
        if (token.lower_ == "mais" and token.i > 0 and doc[token.i - 1].text == "," and nxt is not None
                and nxt.lower_ in {"o", "a", "os", "as"}):
            clause = []
            for t in doc[token.i + 1:token.sent.end]:
                if t.is_punct or t.lower_ in {"que", "qual", "quem", "onde"}:
                    break
                clause.append(t)
            if any(verbal(t) for t in clause[2:]):
                emit("homofonos", "Mas / mais", token.idx, token.idx + len(token.text), "probable_error", .8,
                     "Após a vírgula, a palavra introduz oposição: a conjunção é ‘mas’. ‘Mais’ indica quantidade ou intensidade.",
                     cased(token.text, "mas"))
        # “Aonde ele está?” → “Onde”: ‘aonde’ exige verbo de movimento.
        if token.lower_ == "aonde":
            verb = next((t for t in doc[token.i + 1:token.sent.end] if t.pos_ in {"VERB", "AUX"}), None)
            if verb is not None and verb.lemma_.casefold() in STATIC:
                emit("homofonos", "Onde / aonde", token.idx, token.idx + len(token.text), "probable_error", .85,
                     f"‘Aonde’ indica destino, com verbos de movimento; com ‘{verb.text}’, use ‘onde’.",
                     cased(token.text, "onde"))
        # “um mal vizinho” → “mau”: adjetivo diante de substantivo.
        if (token.lower_ == "mal" and nxt is not None and nxt.pos_ == "NOUN" and token.i > 0
                and doc[token.i - 1].lower_ in {"um", "o", "seu", "meu", "teu", "nosso", "esse", "este", "aquele", "tão", "muito", "que"}
                and nxt.lower_ not in {"estar"}):
            emit("homofonos", "Mal / mau", token.idx, token.idx + len(token.text), "probable_error", .8,
                 "Antes de substantivo, o adjetivo é ‘mau’ (oposto de ‘bom’); ‘mal’ é advérbio ou substantivo.",
                 cased(token.text, "mau"))


def number(token):
    value = token.morph.get("Number")
    return value[0] if len(value) == 1 else None


HAVER_PLURAL = {"haviam", "houveram", "haverão", "haveriam", "hajam", "houvessem", "houverem"}


def singular(word):
    return {"haviam": "havia", "houveram": "houve", "haverão": "haverá", "haveriam": "haveria",
            "hajam": "haja", "houvessem": "houvesse", "houverem": "houver"}[word]


def agreement(block, doc, emit):
    # “Haviam turistas”: no sentido de existir, ‘haver’ é impessoal. Como
    # auxiliar (“haviam saído”) ou em “haviam de voltar”, concorda com o sujeito.
    for verb in doc:
        if verb.lower_ not in HAVER_PLURAL:
            continue
        after = next((t for t in doc[verb.i + 1:verb.sent.end] if t.pos_ != "ADV"), None)
        if after is None or after.is_punct or "Part" in after.morph.get("VerbForm") or after.lower_ == "de":
            continue
        emit("concordancia", "Haver impessoal", verb.idx, verb.idx + len(verb.text), "probable_error", .85,
             f"No sentido de ‘existir’ ou ‘acontecer’, ‘haver’ fica no singular: ‘{cased(verb.text, singular(verb.lower_))}’.",
             cased(verb.text, singular(verb.lower_)))
    for verb in doc:
        if verb.pos_ not in {"VERB", "AUX"} or "Fin" not in verb.morph.get("VerbForm"):
            continue
        head = verb.head if verb.dep_ in {"cop", "aux", "aux:pass"} else verb
        subject = next((c for c in head.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
        verb_number = number(verb)
        if subject is None or verb_number is None or subject.i > verb.i:
            continue
        if any(c.dep_ == "conj" for c in subject.children) or verb.lemma_.casefold() in {"haver", "fazer"}:
            continue
        # “Abriu a porta saiu correndo”: um verbo finito antes, na mesma
        # oração, indica que o sintagma é objeto dele, não sujeito.
        left = min(t.i for t in subject.subtree)
        clause = []
        for t in reversed(doc[subject.sent.start:left]):
            if t.is_punct or t.pos_ in {"CCONJ", "SCONJ"} or t.lower_ == "que":
                break
            clause.append(t)
        if any(t.pos_ in {"VERB", "AUX"} and "Fin" in t.morph.get("VerbForm") for t in clause):
            continue
        # Plural em português termina em -s; um nome próprio marcado como plural não conta.
        if subject.pos_ == "NOUN" and number(subject) == "Plur" and subject.lower_.endswith("s") and verb_number == "Sing":
            if subject.lower_ in COLLECTIVE:
                continue
            # Com ‘ser’, o verbo pode concordar com o predicativo singular.
            if verb.lemma_.casefold() == "ser" and not (head.pos_ in {"ADJ", "VERB"} or number(head) == "Plur"):
                continue
            emit("concordancia", "Concordância verbal", subject.idx, verb.idx + len(verb.text), "probable_error", .75,
                 f"O sujeito ‘{subject.text}’ está no plural, mas o verbo ‘{verb.text}’ está no singular.")
        elif subject.lower_ in EACH and verb_number == "Plur" and subject.pos_ in {"DET", "PRON"}:
            emit("concordancia", "Concordância verbal", subject.idx, verb.idx + len(verb.text), "probable_error", .75,
                 f"Com ‘{subject.text}’ como núcleo do sujeito, o verbo fica no singular; ‘{verb.text}’ está no plural.")
    for token in doc:
        if token.pos_ != "ADJ" or token.lower_ in INVARIABLE:
            continue
        noun = token.head
        # Adjetivo imediatamente posposto ao substantivo que qualifica. Dentro
        # de locução preposicionada (“com caixas ofegante”), pode se referir ao sujeito.
        if (token.dep_ == "amod" and noun.pos_ == "NOUN" and noun.i == token.i - 1
                and not any(c.dep_ == "case" for c in noun.children)):
            pass
        # Predicativo: “as luzes estavam apagada”.
        elif token.dep_ in {"ROOT", "conj"} and any(c.dep_ == "cop" for c in token.children):
            noun = next((c for c in token.children if c.dep_ == "nsubj" and c.pos_ == "NOUN"), None)
            copula = next(c for c in token.children if c.dep_ == "cop")
            if noun is None or any(c.dep_ == "conj" for c in noun.children) or number(copula) != number(noun):
                continue
        else:
            continue
        if (number(noun) == "Plur" and noun.lower_.endswith("s") and number(token) == "Sing"
                and not token.lower_.endswith("s")):
            emit("concordancia", "Concordância nominal", noun.idx, token.idx + len(token.text), "probable_error", .75,
                 f"O adjetivo ‘{token.text}’ está no singular, mas se refere a ‘{noun.text}’, no plural.")


def regency(block, doc, emit):
    for token in doc:
        nxt = doc[token.i + 1] if token.i + 1 < len(doc) else None
        if nxt is None:
            continue
        if token.lemma_.casefold() == "chegar" and token.pos_ == "VERB" and nxt.lower_ in {"em", "no", "na", "nos", "nas", "num", "numa"}:
            noun = next((t for t in doc[nxt.i + 1:min(nxt.i + 4, len(doc))] if t.pos_ in {"NOUN", "PROPN"}), None)
            if noun is None or noun.lower_ in NON_PLACE or any(t.is_punct for t in doc[nxt.i:noun.i]):
                continue
            emit("regencia", "Regência verbal", token.idx, nxt.idx + len(nxt.text), "editorial_attention", .6,
                 "Na norma culta, ‘chegar’ pede a preposição ‘a’ para o destino (‘chegou à estação’, ‘chegou a casa’). A forma com ‘em’ é comum no uso brasileiro; confira o registro desejado.")
        # “Ajudou ela a descer” → “ajudou-a”. Incisos de fala (“perguntou ela”) e
        # verbos sem objeto (“chegou ela”) têm o pronome como sujeito posposto.
        if (nxt.lower_ in {"ele", "ela", "eles", "elas"} and nxt.dep_ == "obj" and nxt.head == token
                and token.pos_ == "VERB" and "Fin" in token.morph.get("VerbForm")
                and not verbo_de_fala(token) and token.lemma_.casefold() not in INTRANSITIVE
                and not block.text[:token.idx].rstrip().endswith(("—", "–"))):
            clitic = {"ele": "o", "ela": "a", "eles": "os", "elas": "as"}[nxt.lower_]
            emit("regencia", "Pronome reto como objeto", token.idx, nxt.idx + len(nxt.text), "editorial_attention", .7,
                 f"Na norma culta, o objeto direto é o pronome oblíquo: ‘{token.text}-{clitic}’ (ou ‘{clitic} {token.lower_}’). "
                 "A forma com ‘ele/ela’ é comum no português brasileiro falado; confira o registro desejado.")
        if token.lemma_.casefold() == "pedir" and token.pos_ == "VERB" and nxt.lower_ == "para" \
                and token.i + 2 < len(doc) and doc[token.i + 2].lower_ == "que":
            emit("regencia", "Regência verbal", token.idx, doc[token.i + 2].idx + 3, "editorial_attention", .7,
                 "Na norma culta, pede-se algo a alguém: ‘pediu que’. ‘Pedir para que’ é comum na fala.",
                 token.text + " que")


def subject_comma(block, doc, emit):
    for verb in doc:
        if verb.pos_ not in {"VERB", "AUX"} or "Fin" not in verb.morph.get("VerbForm"):
            continue
        head = verb.head if verb.dep_ in {"cop", "aux", "aux:pass"} else verb
        subject = next((c for c in head.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
        # Só sintagma nominal com determinante: nomes, títulos e interjeições
        # antes da vírgula costumam ser vocativos (“Senhor Almeida, está…”).
        if (subject is None or subject.i > verb.i or subject.pos_ != "NOUN"
                or not any(c.dep_ in {"det", "nummod"} for c in subject.children)):
            continue
        # “Que alívio, pensei…”: verbo em 1.ª ou 2.ª pessoa não tem um nome como sujeito.
        if set(verb.morph.get("Person")) & {"1", "2"}:
            continue
        words = [t for t in subject.subtree if not t.is_punct]
        if not words:
            continue
        first, last = words[0].i, words[-1].i
        if last + 2 != verb.i or doc[last + 1].text != "," or first != subject.sent.start:
            continue
        if any(t.is_punct for t in doc[first:last + 1]):
            continue
        comma = doc[last + 1]
        emit("virgula_sujeito_verbo", "Vírgula entre sujeito e verbo", comma.idx, comma.idx + 1, "probable_error", .75,
             "Não se separa o sujeito do verbo por uma única vírgula. Se houver um inciso, ele precisa de vírgula também na abertura.",
             "")


CHECKS = (("crase", crase), ("homofonos", homophones), ("concordancia", agreement),
          ("regencia", regency), ("virgula_sujeito_verbo", subject_comma))


def analyze(blocks, nlp, settings, docs=None, skip=()):
    """`skip` recebe intervalos (parágrafo, início, fim) já apontados por outra fonte."""
    rules = settings["rules"]
    active = [(name, check) for name, check in CHECKS if rules.get(name)]
    if not active:
        return []
    roles = classify(blocks, settings)
    if Lemmas.nlp is not nlp:
        Lemmas.nlp, Lemmas.cache = nlp, {}
    docs = docs if docs is not None else list(nlp.pipe((b.text for b in blocks), batch_size=32))
    out, seen = [], set()
    for block, doc, labels in zip(blocks, docs, roles):
        if block.heading or not block.text.strip():
            continue

        def emit(rule, category, start, end, severity, score, reason, suggestion=None):
            if labels[start] not in SCOPES[rule] or (start, end) in seen:
                return
            if any(p == block.number and s < end and e > start for p, s, e in skip):
                return
            seen.add((start, end))
            out.append(item(block, rule, category, start, end, reason, severity, score, suggestion))

        seen = set()
        for name, check in active:
            check(block, doc, emit)
    return out
