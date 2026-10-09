"""Concordância, crase, homófonos, regência, vírgula, correlação de tempos,
frase cortada e locuções, com apoio sintático.

Cada regra cobre uma classe gramatical e se abstém diante de leituras
alternativas plausíveis. Grafia (crase e homófonos), correlação de tempos e frase
cortada são revistas também em falas; concordância, regência, vírgula entre sujeito
e verbo e locuções só na narração, para não
formalizar a voz de personagens. Nenhuma regra usa nomes ou frases de obras.
"""
from dataclasses import asdict
import re

from .analysis import explicar, finding, lista_ou_rotulo
from .elocucao import pede_completiva_confirmada, verbo_de_fala
from .lexicon import FINITE, NONVERB, flags
from .verbo import certamente_verbo, conjugado_pelo_modelo, ha_forma_verbal, so_verbo_no_lexico
from .tempo import TERMINACAO_CONDICIONAL, imperfeito_do_subjuntivo
from .segments import classify, termina_em_travessao

PORQUE_PERGUNTA = explicar("Em pergunta, escreve-se separado: ‘Por que você saiu?’. Junto (‘porque’) é para responder "
                           "ou explicar: ‘Saí porque choveu’.", "por que / porque")
MAS_MAIS = explicar("Aqui a palavra indica oposição, como ‘porém’, então é ‘mas’. ‘Mais’ é de quantidade: ‘mais café’.",
                    "mas / mais")
RULES = ("crase", "homofonos", "concordancia", "regencia", "virgula_sujeito_verbo",
         "correlacao_tempos", "frase_cortada", "locucoes")
SCOPES = {
    "crase": {"narracao", "dialogo", "pensamento"},
    "homofonos": {"narracao", "dialogo", "pensamento"},
    "concordancia": {"narracao"},
    "regencia": {"narracao"},
    "virgula_sujeito_verbo": {"narracao"},
    # Correlação entre orações e frases cortadas valem também em falas: não são registro, são estrutura.
    "correlacao_tempos": {"narracao", "dialogo", "pensamento"},
    "frase_cortada": {"narracao", "dialogo", "pensamento"},
    "locucoes": {"narracao"},
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
# Destinatário expresso antes do “a”: contração com o artigo ou pronome átono dativo.
DESTINATARIO = {"ao", "aos", "às", "lhe", "lhes", "me", "te", "nos", "vos"}
PRONOMES_PREPOSICIONADOS = {"comigo", "contigo", "consigo", "conosco", "convosco"}
COMMON_GENDER = {"chefe", "jovem", "colega", "intérprete", "rival", "mártir", "cliente", "hóspede"}
LOCUTIONS = re.compile(r"\b(em direção|devido|graças|junto|frente|em frente|em relação|rumo|quanto|referente|"
                       r"em resposta|em homenagem|semelhante|igual|contrári[oa]|próxim[oa]|obediente|fiel)"
                       r"\s+(a)\s+(?=\w)", re.I)
STATIC = {"estar", "ficar", "morar", "viver", "residir", "hospedar", "trabalhar", "esconder", "guardar",
          "nascer", "dormir", "estudar", "situar", "localizar", "encontrar"}
COLLECTIVE = {"maioria", "parte", "metade", "grupo", "porção", "conjunto", "bando", "multidão", "resto",
              "total", "série", "número", "maior", "minoria", "quantidade", "pessoal", "gente", "turma",
              # Quantificadores partitivos (“um monte de pássaros pousaram”): as duas concordâncias.
              "monte", "montão", "punhado", "infinidade", "dezena", "centena", "milhar", "milhão"}
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


def item(block, rule, category, start, end, reason, severity, score, suggestion=None, priority="Verificar"):
    value = asdict(finding(block, category, priority, start, end, reason, "FONTE Morfossintático · " + rule))
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
                 explicar(f"Esta expressão leva acento no ‘a’ (crase): ‘{replacement}’.", "crase em locução adverbial feminina"),
                 cased(match[0], replacement))
    for match in re.finditer(r"\bas vezes\b(?!\s+(?:que|em)\b)", text, re.I):
        before = text[:match.start()].split()
        if before and re.sub(r"\W", "", before[-1].casefold()) in {
                "todas", "poucas", "muitas", "várias", "algumas", "das", "nas", "pelas", "quantas",
                "raras", "duas", "três", "tantas", "mesmas", "outras", "demais"}:
            continue
        emit("crase", "Crase em locução", match.start(), match.end(), "probable_error", .85,
             explicar("No sentido de ‘de vez em quando’, escreve-se com acento: ‘às vezes’. Sem acento, ‘as vezes’ "
                      "quer dizer ‘as ocasiões’.", "crase na locução ‘às vezes’"),
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
             explicar("Com hora marcada, o ‘a’ leva acento: ‘às seis horas’, ‘à uma hora’.", "crase antes de horas"),
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
                 explicar("Antes de verbo (‘a correr’) ou de palavra masculina (‘a pé’), o ‘a’ não leva acento.",
                          "crase indevida"),
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
            # Destinatário já expresso (“contou ao filho a história”, “pagou-lhe a quantia”): o ‘a’ seguinte
            # é artigo do objeto direto, não a preposição do destinatário.
            if (any(t.lower_ in DESTINATARIO for t in between)
                    or re.search(r"-(?:lhes?|me|te|nos|vos)\b", text[verb.idx:token.idx], re.I)):
                continue
            # Objeto pode ser adjetivo substantivado: “entregou o maior a tia”. Pronome preposicionado
            # (“trazia comigo a ideia”) não é objeto direto.
            nominal = any((t.pos_ in {"NOUN", "PRON"} and t.lower_ not in PRONOMES_PREPOSICIONADOS)
                          or (t.pos_ in {"ADJ", "NUM"} and t.i > 0 and doc[t.i - 1].pos_ == "DET")
                          for t in between)
            if not nominal or any(
                    t.lower_ in {"à", "para", "e", "ou"} or (t.lower_ == "a" and t.pos_ == "ADP")
                    or t.is_punct for t in between):
                continue
            emit("crase", "Crase ausente", token.idx, nxt.idx + len(nxt.text), "probable_error", .75,
                 explicar(f"Aqui ‘{nxt.text}’ é quem recebe a ação de ‘{verb.text}’ (como em ‘entregou o livro à irmã’). "
                          f"O ‘a’ que indica para quem se junta ao ‘a’ antes da palavra feminina: ‘à {nxt.text}’.",
                          "crase com objeto indireto feminino"),
                 cased(token.text, "à") + text[token.idx + 1:nxt.idx + len(nxt.text)])
    for match in LOCUTIONS.finditer(text):
        word = next((t for t in doc if t.idx >= match.end()), None)
        if (word is None or word.pos_ != "NOUN" or "Fem" not in word.morph.get("Gender")
                or "Plur" in word.morph.get("Number") or word.lower_ == match[1].split()[-1].casefold()):
            continue
        emit("crase", "Crase ausente", match.start(2), word.idx + len(word.text), "probable_error", .85,
             explicar(f"Depois de ‘{match[1]}’ vem um ‘a’; antes de palavra feminina, ele se junta ao ‘a’ dela: "
                      f"‘à {word.text}’.", "crase em locução prepositiva"),
             "à" + text[match.end(2):word.idx + len(word.text)])


def homophones(block, doc, emit):
    text = block.text
    # Pergunta de confirmação no fim (“…, hein?”, “…, né?”) não torna a explicação uma pergunta direta.
    etiqueta = re.compile(r",\s*(?:hein|né|viu|sabe|entende|entendeu|certo|ok|tá|não é|não)\s*\?", re.I)
    for match in re.finditer(r"(?:^|(?<=[—–.!?…]\s)|(?<=[—–]))\s*\b(Porque)\b([^.!?…]*\?)", text):
        if etiqueta.search(match[2]):
            continue
        emit("homofonos", "Por que / porque", match.start(1), match.end(1), "probable_error", .9,
             PORQUE_PERGUNTA, "Por que")
    for match in re.finditer(r"\bporque(?=\s*\?)", text, re.I):
        emit("homofonos", "Por que / porque", match.start(), match.end(), "probable_error", .85,
             explicar("No fim da pergunta, escreve-se separado e com acento: ‘Você saiu por quê?’.", "por quê"),
             cased(match[0], "por quê"))
    for match in re.finditer(r",\s+(mais)\s+(?=(?:não|nunca|ninguém|nada|ele|ela|eles|elas|eu|nós|você|vocês|isso|aquilo|logo|então|também|agora|quando|sem)\b)", text, re.I):
        emit("homofonos", "Mas / mais", match.start(1), match.end(1), "probable_error", .85,
             MAS_MAIS, cased(match[1], "mas"))
    for match in re.finditer(r"\bmau[- ](\w+?(?:ad|id)[oa]s?)\b", text, re.I):
        if match[1].casefold() in {"olhado"}:
            continue
        emit("homofonos", "Mal / mau", match.start(), match.end(), "probable_error", .9,
             explicar("Antes de palavras como ‘educado’ ou ‘feito’, usa-se ‘mal’, o contrário de ‘bem’ (‘mal-educado’). "
                      "‘Mau’ é o contrário de ‘bom’.", "mal / mau"),
             cased(match[0], "mal") + match[0][3:])
    for match in re.finditer(r"\b(de|em) baixo(?=\s+d[aoe]s?\b)", text, re.I):
        joined = "debaixo" if match[1].casefold() == "de" else "embaixo"
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             explicar(f"Neste sentido de lugar, escreve-se junto: ‘{joined}’.", "advérbio de lugar"), cased(match[0], joined))
    # Advérbio sozinho (“lá em baixo,”); “em baixo tom” segue como adjetivo.
    for match in re.finditer(r"\bem baixo(?=\s*(?:[.,;:!?…—–]|$))", text, re.I):
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             explicar("Neste sentido de lugar, escreve-se junto: ‘embaixo’.", "advérbio de lugar"), cased(match[0], "embaixo"))
    for match in re.finditer(r"\bencima(?=\s+d[aoe]s?\b)", text, re.I):
        emit("homofonos", "Grafia de locução", match.start(), match.end(), "probable_error", .9,
             explicar("Escreve-se separado: ‘em cima’.", "locução ‘em cima’"), cased(match[0], "em cima"))
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
                     explicar("Para tempo que já passou, usa-se ‘há’ (‘saiu há pouco tempo’), ou ‘havia’ numa história "
                              "contada no passado. ‘A’ é para tempo que ainda vai chegar (‘daqui a pouco’) ou para distância.",
                              "há / a (verbo haver)"),
                     cased(token.text, "há") + text[token.idx + 1:unit.idx + len(unit.text)])
        # “Mãe, porque ninguém avisou?”: sem verbo antes, só vocativo ou conjunção,
        # ainda é pergunta direta. Depois de uma oração (“saiu porque…?”) é causa.
        # O léxico confirma verbos que o modelo não marca no início da frase (“É porque…”).
        if (token.text == "porque" and "?" in doc.text[token.idx:token.sent.end_char]
                and not etiqueta.search(doc.text[token.idx:token.sent.end_char])
                and not any(ha_forma_verbal(t) for t in doc[token.sent.start:token.i])):
            emit("homofonos", "Por que / porque", token.idx, token.idx + len(token.text), "probable_error", .85,
                 PORQUE_PERGUNTA, "por que")
        # “…, mais a fila não parava”: há verbo conjugado no mesmo trecho, antes
        # de pontuação ou ‘que’; na soma (“os três, mais o motorista, …”) não há.
        if (token.lower_ == "mais" and token.i > 0 and doc[token.i - 1].text == "," and nxt is not None
                and nxt.lower_ in {"o", "a", "os", "as"}):
            clause = []
            for t in doc[token.i + 1:token.sent.end]:
                if t.is_punct or t.lower_ in {"que", "qual", "quem", "onde"}:
                    break
                clause.append(t)
            if any(ha_forma_verbal(t) for t in clause[2:]):
                emit("homofonos", "Mas / mais", token.idx, token.idx + len(token.text), "probable_error", .8,
                     MAS_MAIS, cased(token.text, "mas"))
        # “Aonde ele está?” → “Onde”: ‘aonde’ exige verbo de movimento.
        if token.lower_ == "aonde":
            verb = next((t for t in doc[token.i + 1:token.sent.end] if t.pos_ in {"VERB", "AUX"}), None)
            if verb is not None and verb.lemma_.casefold() in STATIC:
                emit("homofonos", "Onde / aonde", token.idx, token.idx + len(token.text), "probable_error", .85,
                     explicar(f"‘Aonde’ é para destino, com verbos de movimento (‘aonde você vai?’). ‘{verb.text}’ não "
                              "indica movimento, então a forma é ‘onde’.", "onde / aonde"),
                     cased(token.text, "onde"))
        # “um mal vizinho” → “mau”: adjetivo diante de substantivo.
        if (token.lower_ == "mal" and nxt is not None and nxt.pos_ == "NOUN" and token.i > 0
                and doc[token.i - 1].lower_ in {"um", "o", "seu", "meu", "teu", "nosso", "esse", "este", "aquele", "tão", "muito", "que"}
                and nxt.lower_ not in {"estar"}):
            emit("homofonos", "Mal / mau", token.idx, token.idx + len(token.text), "probable_error", .8,
                 explicar("Antes de um nome, usa-se ‘mau’, o contrário de ‘bom’ (‘um mau vizinho’). ‘Mal’ é o contrário "
                          "de ‘bem’.", "mal / mau"),
                 cased(token.text, "mau"))


def number(token):
    value = token.morph.get("Number")
    return value[0] if len(value) == 1 else None


HAVER_PLURAL = {"haviam", "houveram", "haverão", "haveriam", "hajam", "houvessem", "houverem"}


def singular(word):
    return {"haviam": "havia", "houveram": "houve", "haverão": "haverá", "haveriam": "haveria",
            "hajam": "haja", "houvessem": "houvesse", "houverem": "houver"}[word]


def partitive(head):
    """Complemento “de + plural” do núcleo (“a lista de nomes”, “uma das portas”), fora de “um dos que”."""
    for c in head.children:
        if (c.dep_ == "nmod" and number(c) == "Plur" and c.lower_.endswith("s")
                and any(k.dep_ == "case" and k.lower_ in {"de", "dos", "das"} for k in c.children)):
            following = c.doc[c.i + 1] if c.i + 1 < len(c.doc) else None
            return not (following is not None and following.lower_ == "que")
    return False


def agreement(block, doc, emit):
    elided_subject_plural(doc, emit)
    # “Haviam turistas”: no sentido de existir, ‘haver’ é impessoal. Como
    # auxiliar (“haviam saído”) ou em “haviam de voltar”, concorda com o sujeito.
    for verb in doc:
        if verb.lower_ not in HAVER_PLURAL:
            continue
        after = next((t for t in doc[verb.i + 1:verb.sent.end] if t.pos_ != "ADV"), None)
        if after is None or after.is_punct or "Part" in after.morph.get("VerbForm") or after.lower_ == "de":
            continue
        emit("concordancia", "Haver impessoal", verb.idx, verb.idx + len(verb.text), "probable_error", .85,
             explicar(f"Quando ‘haver’ quer dizer ‘existir’ ou ‘acontecer’, ele fica no singular, mesmo que venham "
                      f"várias coisas depois: ‘{cased(verb.text, singular(verb.lower_))}’.", "verbo haver impessoal"),
             cased(verb.text, singular(verb.lower_)))
    for verb in doc:
        if not conjugado_pelo_modelo(verb):
            continue
        head = verb.head if verb.dep_ in {"cop", "aux", "aux:pass"} else verb
        subject = next((c for c in head.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
        verb_number = number(verb)
        if subject is None or verb_number is None or subject.i > verb.i:
            continue
        if any(c.dep_ == "conj" for c in subject.children) or verb.lemma_.casefold() in {"haver", "fazer"}:
            continue
        # Plural da 3ª pessoa termina em -m ou -ão; o modelo às vezes marca o singular como plural.
        if verb_number == "Plur" and "3" in verb.morph.get("Person") and not verb.lower_.endswith(("m", "ão")):
            continue
        # Pontuação entre o sujeito e o verbo: aposto ou inciso lido como sujeito (“…, a dádiva de…, poderiam”).
        if any(t.is_punct for t in doc[max(t.i for t in subject.subtree) + 1:verb.i]):
            continue
        # “Abriu a porta saiu correndo”: um verbo finito antes, na mesma
        # oração, indica que o sintagma é objeto dele, não sujeito.
        left = min(t.i for t in subject.subtree)
        clause = []
        for t in reversed(doc[subject.sent.start:left]):
            if t.is_punct or t.pos_ in {"CCONJ", "SCONJ"} or t.lower_ == "que":
                break
            clause.append(t)
        if any(conjugado_pelo_modelo(t) for t in clause):
            continue
        # Plural em português termina em -s; um nome próprio marcado como plural não conta.
        if subject.pos_ == "NOUN" and number(subject) == "Plur" and subject.lower_.endswith("s") and verb_number == "Sing":
            if subject.lower_ in COLLECTIVE:
                continue
            # Com ‘ser’, o verbo pode concordar com o predicativo singular.
            if verb.lemma_.casefold() == "ser" and not (head.pos_ in {"ADJ", "VERB"} or number(head) == "Plur"):
                continue
            emit("concordancia", "Concordância verbal", subject.idx, verb.idx + len(verb.text), "probable_error", .75,
                 explicar(f"‘{subject.text}’ está no plural, mas a ação, ‘{verb.text}’, está no singular. Quando quem faz "
                          "a ação são vários, o verbo vai para o plural.", "concordância verbal"))
        # O modelo às vezes etiqueta ‘nenhuma’ como numeral (“Nenhuma das respostas…”). ‘Um/uma’ só
        # com partitivo (“uma das portas”), fora de “um dos que…”, que admite o plural.
        elif verb_number == "Plur" and subject.pos_ in {"DET", "PRON", "NUM"} and (
                subject.lower_ in EACH or (subject.lower_ in {"um", "uma"} and partitive(subject))):
            emit("concordancia", "Concordância verbal", subject.idx, verb.idx + len(verb.text), "probable_error", .75,
                 explicar(f"Com ‘{subject.text}’ (um só), o verbo fica no singular; ‘{verb.text}’ está no plural.",
                          "concordância verbal"))
        # Concordância por atração: núcleo singular com complemento “de + plural” e verbo no
        # plural (“a lista de objetos estavam”). Coletivos e partitivos (“a maioria dos alunos”)
        # admitem as duas concordâncias e ficam de fora.
        # Núcleo singular marcado (complemento “de + plural” ou determinante singular, como “nenhuma
        # palavra”) com verbo no plural. Concorda com o núcleo, não com o nome mais próximo.
        elif (subject.pos_ == "NOUN" and number(subject) == "Sing" and not subject.lower_.endswith("s")
              and verb_number == "Plur" and "3" in verb.morph.get("Person") and subject.lower_ not in COLLECTIVE
              and (partitive(subject) or any(c.dep_ == "det" and number(c) == "Sing" for c in subject.children))):
            emit("concordancia", "Concordância verbal", subject.idx, verb.idx + len(verb.text), "probable_error", .75,
                 explicar(f"Quem faz a ação é ‘{subject.text}’, no singular, mas ‘{verb.text}’ está no plural"
                          + (", talvez puxado pela palavra no plural que vem logo depois" if partitive(subject) else "")
                          + ". Confira.", "concordância verbal"))
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
            # Predicativo antes do sujeito (“Estavam apagada as luzes”): o trecho vai do primeiro termo ao último.
            first, last = sorted((noun, token), key=lambda t: t.i)
            emit("concordancia", "Concordância nominal", first.idx, last.idx + len(last.text), "probable_error", .75,
                 explicar(f"‘{token.text}’ está no singular, mas descreve ‘{noun.text}’, que está no plural.",
                          "concordância nominal"))


def regency(block, doc, emit):
    for token in doc:
        nxt = doc[token.i + 1] if token.i + 1 < len(doc) else None
        if nxt is None:
            continue
        if token.lemma_.casefold() == "chegar" and token.pos_ == "VERB" and nxt.lower_ in {"em", "no", "na", "nos", "nas", "num", "numa"}:
            noun = next((t for t in doc[nxt.i + 1:min(nxt.i + 4, len(doc))] if t.pos_ in {"NOUN", "PROPN"}), None)
            if noun is None or noun.lower_ in NON_PLACE or any(t.is_punct for t in doc[nxt.i:noun.i]):
                continue
            # Questão de registro, não erro: sem sugestão, para não trocar a voz do autor.
            emit("regencia", "Regência verbal", token.idx, nxt.idx + len(nxt.text), "editorial_attention", .6,
                 explicar("Na escrita mais formal, quem chega, chega ‘a’ algum lugar: ‘chegar à estação’. ‘Chegar em "
                          "casa’ é amplamente usado no Brasil; mude só se o texto pedir um registro normativo mais formal.",
                          "regência do verbo chegar"), priority="Explorar")
        # “Ajudou ela a descer” → “ajudou-a”. Incisos de fala (“perguntou ela”) e
        # verbos sem objeto (“chegou ela”) têm o pronome como sujeito posposto.
        if (nxt.lower_ in {"ele", "ela", "eles", "elas"} and nxt.dep_ == "obj" and nxt.head == token
                and token.pos_ == "VERB" and conjugado_pelo_modelo(token)
                and not verbo_de_fala(token) and token.lemma_.casefold() not in INTRANSITIVE
                and not termina_em_travessao(block.text[:token.idx])):
            clitic = {"ele": "o", "ela": "a", "eles": "os", "elas": "as"}[nxt.lower_]
            emit("regencia", "Pronome reto como objeto", token.idx, nxt.idx + len(nxt.text), "editorial_attention", .7,
                 explicar(f"Na escrita formal, ‘{token.text} {nxt.text}’ vira ‘{token.text}-{clitic}’ (ou ‘{clitic} "
                          f"{token.lower_}’). A forma com ‘{nxt.text}’ é comum na fala; mude só se quiser um tom mais formal.",
                          "pronome oblíquo como objeto direto"))
        if token.lemma_.casefold() == "pedir" and token.pos_ == "VERB" and nxt.lower_ == "para" \
                and token.i + 2 < len(doc) and doc[token.i + 2].lower_ == "que":
            emit("regencia", "Regência verbal", token.idx, doc[token.i + 2].idx + 3, "editorial_attention", .7,
                 explicar("Na escrita formal, usa-se ‘pediu que’, sem o ‘para’. ‘Pedir para que’ é comum na fala.",
                          "regência do verbo pedir"),
                 token.text + " que")


RELATIVE_OPENERS = {"que", "onde", "cujo", "cuja", "cujos", "cujas"}
def relative_subject_comma(doc, emit):
    """Sujeito com oração relativa restritiva fechado por uma vírgula sem abertura (“a moça que cuidou do
    jardim no verão, rega as flores”). Pela forma, porque a árvore costuma se perder nessas frases: o
    trecho começa com determinante (depois de vírgula ou no início da frase), tem relativo e verbo
    finito, e a vírgula vem logo antes de um verbo finito que concorda em número com o nome. Com
    vírgula antes do relativo (relativa explicativa) ou verbo de fala (inciso), não há alerta."""
    for sentence in doc.sents:
        tokens = list(sentence)
        for k, comma in enumerate(tokens):
            if comma.text != "," or k + 1 >= len(tokens):
                continue
            verb = tokens[k + 1]
            if not (certamente_verbo(verb) or (flags(verb.text) & FINITE and verb.pos_ in {"VERB", "AUX"})) or verbo_de_fala(verb):
                continue
            start = next((j + 1 for j in range(k - 1, -1, -1) if tokens[j].is_punct), 0)
            segment = tokens[start:k]
            rel = next((j for j, t in enumerate(segment) if t.lower_ in RELATIVE_OPENERS), None)
            if (rel is None or rel < 2 or segment[0].pos_ != "DET" or segment[0].lower_ in {"todo", "toda"}
                    or not any(certamente_verbo(t) for t in segment[rel + 1:])):
                continue
            noun = segment[rel - 1]
            plural = noun.lower_.endswith("s")
            if plural != verb.lower_.endswith(("m", "ão")):
                continue
            emit("virgula_sujeito_verbo", "Vírgula entre sujeito e verbo", comma.idx, comma.idx + 1, "probable_error", .7,
                 explicar(f"O trecho com ‘{segment[rel].text}’ faz parte de quem pratica a ação. A vírgula no fim dele "
                          "separa quem faz da ação, o que não se faz. Ou essa vírgula sai, ou entra outra também antes do "
                          f"‘{segment[rel].text}’.", "vírgula entre sujeito e verbo"), "")


LINKING_PLURAL = {"é": "são", "está": "estão", "fica": "ficam", "parece": "parecem", "continua": "continuam",
                  "permanece": "permanecem", "anda": "andam", "segue": "seguem"}


def elided_subject_plural(doc, emit):
    """Verbo de ligação no singular, abrindo a frase sem sujeito expresso, com predicativo no plural
    (“Parece tão nervosos.”): o sujeito elíptico é plural; o verbo concorda com ele."""
    for verb in doc:
        if verb.lower_ not in LINKING_PLURAL or verb.pos_ not in {"VERB", "AUX"}:
            continue
        head = verb.head if verb.dep_ in {"cop", "aux"} else verb
        if any(c.dep_.startswith("nsubj") for c in list(head.children) + list(verb.children)):
            continue
        if any(not t.is_punct and t.pos_ != "ADV" for t in doc[verb.sent.start:verb.i]):
            continue
        rest = [t for t in doc[verb.i + 1:verb.sent.end] if not t.is_punct]
        predicative = next((t for t in rest if t.pos_ != "ADV"), None)
        participle = predicative is not None and "Part" in predicative.morph.get("VerbForm")
        if (predicative is None or (predicative.pos_ != "ADJ" and not participle)
                or "Plur" not in predicative.morph.get("Number")
                or not predicative.lower_.endswith("s") or any(t.pos_ in {"NOUN", "PROPN", "PRON"} for t in rest)):
            continue
        plural = cased(verb.text, LINKING_PLURAL[verb.lower_])
        emit("concordancia", "Concordância verbal", verb.idx, verb.idx + len(verb.text), "probable_error", .7,
             explicar(f"‘{predicative.text}’ está no plural, então quem ‘{verb.lower_}’ são vários, mesmo sem aparecer "
                      f"na frase. O verbo vai para o plural: ‘{plural}’.", "concordância com sujeito oculto"), plural)


def subject_comma(block, doc, emit):
    for verb in doc:
        if not conjugado_pelo_modelo(verb):
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
        # Inciso de fala (“…, disse ele, …”): o verbo de fala não é o predicado do sujeito anterior.
        if verbo_de_fala(verb) and verb.i + 1 < len(doc) and doc[verb.i + 1].pos_ in {"PRON", "PROPN"}:
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
             explicar("Não se coloca uma vírgula sozinha entre quem faz a ação e a ação (‘O menino, correu’). Se houver "
                      "um comentário no meio, ele fica entre duas vírgulas.", "vírgula entre sujeito e verbo"), "")
    relative_subject_comma(doc, emit)


# Subordinantes que, com o imperfeito do subjuntivo, situam a oração no passado.
CORRELATIVES = ("antes que", "ainda que", "mesmo que", "a menos que", "desde que", "sem que", "embora", "caso",
                "se", "conquanto")


def present_main(sentence, exclude):
    """Verbo finito mais próximo da subordinada, fora dela, se estiver no presente do indicativo. O
    mais próximo, e não a raiz: numa frase com fala e narração, ou com outra oração no meio (“numa
    sala que, se soubesse antes, nunca teria aberto”), a subordinada se liga ao verbo vizinho."""
    from .tempo import tempo_recuperado
    from .lexicon import PAST, PRESENT
    first, last = min(exclude), max(exclude)

    def only_finite(t):
        # Forma só verbal no léxico, sem etiqueta nominal do modelo (combinação própria desta regra).
        return so_verbo_no_lexico(t) and t.pos_ not in {"NOUN", "PROPN", "PRON", "DET", "ADP", "CCONJ", "SCONJ", "NUM"}

    def crosses_dash(t):
        lo, hi = (t.i, first) if t.i < first else (last, t.i)
        return any(x.text in {"—", "–"} for x in sentence.doc[lo:hi])

    verbs = [t for t in sentence if t.i not in exclude and t.is_alpha and not crosses_dash(t)
             and (conjugado_pelo_modelo(t)
                  or tempo_recuperado(t) is not None or only_finite(t))]
    if not verbs:
        return None
    nearest = min(verbs, key=lambda t: first - t.i if t.i < first else t.i - last)
    value = flags(nearest.text)
    if only_finite(nearest) and nearest.pos_ not in {"VERB", "AUX"}:
        present = bool(value & PRESENT) and not value & PAST
    else:
        present = (("Ind" in nearest.morph.get("Mood") and "Pres" in nearest.morph.get("Tense"))
                   or tempo_recuperado(nearest) == "present")
    return nearest if present and not TERMINACAO_CONDICIONAL.search(nearest.lower_) else None




def correlation(block, doc, emit):
    """Subordinada com o imperfeito do subjuntivo (“antes que terminasse”, “embora fosse”, “se não
    fosse”) presa a uma oração principal no presente do indicativo (“…, uma mão toca”). Com a
    principal no presente, a correlação usual é o presente do subjuntivo (“antes que termine”); o
    imperfeito situa a subordinada no passado. ‘Antes que’ e ‘se’ quase sempre pedem a correlação;
    nos concessivos (‘embora’), um fato passado pode justificar o imperfeito."""
    for sentence in doc.sents:
        words = [t for t in sentence if not t.is_punct]
        lowered = [t.lower_ for t in words]
        for i, word in enumerate(words):
            phrase = next((p for p in CORRELATIVES if lowered[i:i + len(p.split())] == p.split()), None)
            # “Como se” pede sempre o imperfeito do subjuntivo (“diz como se estivesse”).
            if phrase is None or (phrase == "se" and i > 0 and lowered[i - 1] in {"como", "nem"}):
                continue
            after = words[i + len(phrase.split()):]
            verb = next((t for t in after[:6] if imperfeito_do_subjuntivo(t)), None)
            if verb is None or any(t.text in {",", ";", "—", "–"} for t in doc[word.i:verb.i]):
                continue
            # A subordinada vai até a próxima vírgula; a principal está fora dela.
            end = next((t.i for t in doc[verb.i:sentence.end] if t.text in {",", ";", "—"}), sentence.end)
            main = present_main(sentence, set(range(word.i, end)))
            if main is None:
                continue
            concessive = phrase in {"embora", "ainda que", "mesmo que", "conquanto"}
            if phrase == "se":
                # Depois de ‘se’ não há presente do subjuntivo: a condição vai ao futuro do subjuntivo
                # (“se não for”) ou, hipótese irreal, fica no imperfeito com a principal no futuro do pretérito.
                reason = explicar(
                    f"A frase mistura dois jeitos de dizer a mesma coisa: ‘{main.text}’ fala do agora, e ‘se … "
                    f"{verb.text}’ monta uma hipótese, que costuma vir com verbos como ‘seria’ ou ‘daria’. Costuma "
                    "combinar assim:\n  • hipótese: ‘seria difícil, se não fosse…’\n  • agora: ‘é difícil, se não for…’\n"
                    "Confira qual você quis dizer.",
                    "correlação de tempos; com ‘se’ + imperfeito do subjuntivo, a principal vai ao futuro do pretérito; "
                    "com a principal no presente, a condição vai ao futuro do subjuntivo")
            else:
                reason = (f"A ação principal, ‘{main.text}’, está no agora, mas ‘{verb.text}’ está numa forma que olha para "
                          f"o passado. Com a ação principal no agora, ‘{phrase}’ costuma vir com a forma do agora (como "
                          f"‘{phrase} seja’, ‘{phrase} termine’).")
                if concessive:
                    reason += " Se o fato aconteceu mesmo antes, a forma do passado está certa; confira."
                reason = explicar(reason, "correlação de tempos; principal no presente pede o presente do subjuntivo")
            emit("correlacao_tempos", "Correlação de tempos", verb.idx, verb.idx + len(verb.text),
                 "editorial_attention" if concessive else "probable_error", .6 if concessive else .75, reason)


# Palavras que não fecham uma frase: preposição simples ou contraída com artigo.
OPEN_ENDINGS = {"de", "em", "com", "sem", "do", "da", "dos", "das", "no", "na", "nos", "nas", "pelo", "pela",
                "pelos", "pelas", "ao", "aos", "num", "numa", "duma", "dum"}
FINAL_PUNCTUATION = tuple(".!?…:;—–-)\"”’»*")


def truncated(block, doc, emit):
    """Frase cortada: termina em preposição ou contração (“até a casa da.”), em ‘cada’ logo depois de
    verbo (“conta cada.”), ou o parágrafo não tem pontuação final. ‘Que’ maiúsculo depois de
    reticências no meio da fala (“Eu disse… Que deixaria”) continua a oração anterior."""
    text = block.text
    for sentence in doc.sents:
        words = [t for t in sentence if t.is_alpha]
        last = words[-1] if words else None
        closing = sentence.text.rstrip()[-1:]
        if last is None or closing not in {".", "!", "?"}:
            continue
        after = text[last.idx + len(last.text):].lstrip()
        if after[:1] not in {".", "!", "?"}:
            continue
        # Reticências em três pontos valem o mesmo que o caractere único “…”: interrupção deliberada.
        if after.startswith(".."):
            continue
        previous = doc[last.i - 1] if last.i > sentence.start else None
        if last.lower_ in OPEN_ENDINGS or (last.lower_ == "cada" and previous is not None
                                           and previous.pos_ in {"VERB", "AUX"}):
            emit("frase_cortada", "Frase cortada", last.idx, last.idx + len(last.text), "probable_error", .75,
                 explicar(f"A frase termina em ‘{last.text}’, que pede uma palavra depois. Confira se faltou alguma coisa.",
                          "frase incompleta"))
    stripped = text.rstrip()
    words = re.findall(r"[^\W\d_]+", stripped)
    if (len(words) >= 4 and stripped[-1:].isalnum() and not stripped.endswith(FINAL_PUNCTUATION)
            and any(certamente_verbo(t) for t in doc) and not lista_ou_rotulo(stripped)):
        last = re.search(r"[^\W\d_]+$", stripped)
        if last:
            emit("frase_cortada", "Pontuação final ausente", last.start(), last.end(), "probable_error", .8,
                 explicar("O parágrafo termina sem ponto.", "pontuação final"), last[0] + ".")
    for match in re.finditer(r"(?:…|\.\.\.)\s+(Que)\b", text):
        before = list(re.finditer(r"[^\W\d_]+(?:-[^\W\d_]+)*", text[:match.start()]))
        rest = re.split(r"[.!?…]", text[match.start(1):], maxsplit=1)[0]
        clause = doc.char_span(match.start(1), match.start(1) + len(rest), alignment_mode="contract")
        verb = doc.char_span(before[-1].start(), before[-1].end(), alignment_mode="expand") if before else None
        if (verb is not None and pede_completiva_confirmada(verb[0]) and clause is not None
                and any(certamente_verbo(t) for t in clause if t.i != clause.start)):
            emit("frase_cortada", "Maiúscula após reticências", match.start(1), match.end(1), "editorial_attention", .65,
                 explicar("As reticências fazem uma pausa, mas a frase continua: o ‘que’ completa o que veio antes (‘eu "
                          "prometi… que voltaria’), então fica com letra minúscula.", "maiúscula após reticências"), "que")


EMBORA_NOMINAL = re.compile(r"\b(embora)\s+(?:o|a|os|as|um|uma|uns|umas|esse|essa|este|esta|aquele|aquela|tal|toda|todo)\s", re.I)


def locutions(block, doc, emit):
    """‘Ao invés de’ (= ao contrário de) em lugar de ‘em vez de’ (= no lugar de); ‘embora’, que
    introduz oração, seguido só de um nome (“Embora a chuva, ela sai.”)."""
    text = block.text
    for match in re.finditer(r"\b(ao\s+invés)\s+d", text, re.I):
        emit("locucoes", "Locução", match.start(1), match.end(1), "editorial_attention", .6,
             explicar("‘Ao invés de’ quer dizer ‘ao contrário de’ e serve para coisas opostas (‘ao invés de subir, "
                      "desceu’). Para ‘no lugar de’, usa-se ‘em vez de’.", "ao invés de / em vez de"),
             cased(match[1], "em vez"))
    for match in EMBORA_NOMINAL.finditer(text):
        stop = re.search(r"[,;.!?…—]", text[match.end():])
        span = doc.char_span(match.end(), match.end() + (stop.start() if stop else len(text) - match.end()),
                             alignment_mode="contract")
        if span is None or any(certamente_verbo(t) or t.pos_ in {"VERB", "AUX"} for t in span):
            continue
        emit("locucoes", "Locução", match.start(1), match.end(1), "probable_error", .75,
             explicar("‘Embora’ pede um verbo depois (‘embora chovesse’). Antes de um nome sozinho, usa-se ‘apesar de’ "
                      "(‘apesar da chuva’).", "conjunção concessiva"))


CHECKS = (("crase", crase), ("homofonos", homophones), ("concordancia", agreement),
          ("regencia", regency), ("virgula_sujeito_verbo", subject_comma),
          ("correlacao_tempos", correlation), ("frase_cortada", truncated), ("locucoes", locutions))


def analyze(blocks, nlp, settings, docs=None):
    """Sem deduplicação com outras fontes: ela fica em `deduplicacao` (Fase 6a)."""
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

        def emit(rule, category, start, end, severity, score, reason, suggestion=None, priority="Verificar"):
            if labels[start] not in SCOPES[rule] or (start, end) in seen:
                return
            seen.add((start, end))
            out.append(item(block, rule, category, start, end, reason, severity, score, suggestion, priority))

        seen = set()
        for name, check in active:
            check(block, doc, emit)
    return out
