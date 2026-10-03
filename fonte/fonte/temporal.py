"""Relações temporais locais por dependências, morfologia e confirmação lexical.

Não infere a intenção narrativa nem impõe concordância temporal absoluta.
As regras não contêm nomes próprios, frases de manuscritos ou fatos de obras.
"""
from dataclasses import asdict
import re
import unicodedata

from .analysis import finding
from .editorial.common import evidence
from .lexicon import FINITE, PAST, PRESENT, FUTURE, NONFINITE, NONVERB, flags, finite, model_finite
from .segments import classify, spans

TIME_SHIFTS = {"hoje", "agora", "atualmente", "amanhã", "ontem", "outrora", "antigamente",
               "sempre", "geralmente", "habitualmente", "ainda", "desde", "depois", "atual"}
STATIVE = {"saber", "conhecer", "existir", "possuir", "pertencer", "entender", "compreender",
           "gostar", "preferir", "continuar", "permanecer", "valer", "significar"}
SUBJUNCTIVE_CUES = {"talvez", "quiçá", "oxalá", "tomara", "embora", "caso", "se", "que"}
IRREGULAR_IMPERFECT = {
    "ser": ("era", "eras", "era", "éramos", "éreis", "eram"),
    "ter": ("tinha", "tinhas", "tinha", "tínhamos", "tínheis", "tinham"),
    "vir": ("vinha", "vinhas", "vinha", "vínhamos", "vínheis", "vinham"),
    "pôr": ("punha", "punhas", "punha", "púnhamos", "púnheis", "punham"),
}


def form(token):
    """A grafia sozinha nunca desempata presente/pretérito nem decide o modo."""
    if token.pos_ not in {"VERB", "AUX"} or not finite(token) or not model_finite(token):
        return None
    value = flags(token.text)
    mood = token.morph.get("Mood")
    # O modelo pequeno pode marcar “construiríamos” como presente. A desinência
    # do condicional + ausência de leitura indicativa no léxico corrigem isso.
    conditional_ending = re.search(r"r(?:ia|ias|íamos|íeis|iam)$", token.text.casefold())
    if (value & FINITE and not value & (PAST | PRESENT | FUTURE)
            and ("Cnd" in mood or conditional_ending)):
        return "conditional"
    if "Sub" in mood or "Imp" in mood:
        return None
    if value & PAST and value & PRESENT:
        return "ambiguous_past_present"
    if "Ind" not in mood:
        return None
    if value & FUTURE and not value & (PAST | PRESENT):
        return "future"
    if value & PAST and not value & (PRESENT | FUTURE):
        return "past"
    if value & PRESENT and not value & (PAST | FUTURE):
        return "present"
    return None


def predicate(token):
    # Em “irá ser boa”, a cópula e o auxiliar pertencem ao predicado “boa”.
    if token.dep_ in {"aux", "aux:pass", "cop"}:
        return token.head
    return token


def nearest_anchor(root, groups, sentence):
    """Caminha na árvore sintática, sem aproximar verbos por distância textual."""
    current, path, visited = root, [], set()
    while current.i not in visited and current.head != current:
        visited.add(current.i)
        path.append(current.dep_)
        current = current.head
        if not sentence.start <= current.i < sentence.end:
            return None, path
        candidates = groups.get(current.i, [])
        if len(candidates) == 1:
            return candidates[0], path
        if len(candidates) > 1:
            return None, path  # Não escolhe um auxiliar finito arbitrariamente.
    return None, path


def explicit_shift(root):
    tokens = list(root.subtree)
    if any(t.lower_ in TIME_SHIFTS for t in tokens):
        return True
    text = " ".join(t.text for t in tokens)
    return bool(re.search(r"\b(?:[12]\d{3}|pr[oó]xim[oa]|atualmente|neste (?:momento|instante)|no momento)\b", text, re.I))


def legitimate_present(token):
    """Evidências locais compartilhadas pelas duas verificações temporais.

    Abstém-se diante de estados atuais plausíveis; não prova causalidade.
    Não libera ações no presente só porque aparecem depois de um passado.
    """
    if form(token) != "present":
        return False
    root = predicate(token)
    if explicit_shift(root):
        return True
    tail = token.doc.text[token.idx:token.sent.end_char]
    prefix = token.doc.text[token.sent.start_char:token.idx]
    if token.lower_ == "é" and re.search(r",\s*não\s*$", prefix) and re.fullmatch(r"é\s*\?\s*", tail):
        return True
    # “Há muito tempo, …”: tempo decorrido na voz do narrador, antes de
    # qualquer verbo no passado. Depois de um passado, a norma pede ‘havia’.
    if (token.lower_ == "há" and re.match(r"há\s+(?:muito|pouco|bastante|algum|alguns|algumas|\d+|[a-zà-ú]+)\s+"
                                          r"(?:tempo|anos?|séculos?|décadas?|meses|dias|semanas|gerações)\b", tail, re.I)
            and not any(form(t) in {"past", "ambiguous_past_present"} for t in token.sent if t.i < token.i)):
        return True
    if token.lemma_.casefold() in STATIVE:
        return True
    # “O que quer que fosse”: locução indefinida, não um verbo no presente da narração.
    if token.lower_ == "quer" and re.search(r"\bque\s*$", prefix, re.I) and re.match(r"quer\s+que\b", tail, re.I):
        return True
    if token.lemma_.casefold() == "poder" and any(
            c.dep_ == "xcomp" and c.lemma_.casefold() in {"confirmar", "afirmar", "garantir", "dizer", "atestar"}
            for c in token.children):
        return True
    # Estado posterior expresso por cópula, sem converter progressivos como
    # “está retirando” em estados. Exige um evento passado ligado na árvore.
    if token.lemma_.casefold() == "estar" and token.dep_ == "cop":
        groups = {}
        for candidate in token.sent:
            if form(candidate):
                groups.setdefault(predicate(candidate).i, []).append(candidate)
        anchor, path = nearest_anchor(root, groups, token.sent)
        if anchor is not None and form(anchor) == "past" and "conj" in path:
            return predicate(anchor).lemma_.casefold() in {
                "sofrer", "quebrar", "ferir", "machucar", "adoecer", "cair", "morrer",
                "nascer", "chegar", "perder", "ganhar", "terminar", "concluir", "aposentar"}
    return False


def bounded_interval(root):
    text = " ".join(t.text for t in root.subtree)
    return bool(re.search(r"\b(?:por|durante)\b.{0,45}\b(?:horas?|minutos?|segundos?|dias?|semanas?|anos?)\b", text, re.I))


def match_case(value, original):
    if original.isupper():
        return value.upper()
    return value[0].upper() + value[1:] if original[0].isupper() else value


def conditional_suggestion(token):
    word = unicodedata.normalize("NFC", token.text.casefold())
    for ending, replacement in [("remos", "ríamos"), ("reis", "ríeis"), ("rão", "riam"),
                                ("rei", "ria"), ("rás", "rias"), ("rá", "ria")]:
        if word.endswith(ending):
            proposal = word[:-len(ending)] + replacement
            value = flags(proposal)
            if value & FINITE and not value & (PAST | PRESENT | FUTURE):
                return match_case(proposal, token.text)
    return None


def imperfect_suggestion(token):
    person, number = token.morph.get("Person"), token.morph.get("Number")
    if len(person) != 1 or person[0] not in {"1", "2", "3"} or number not in (["Sing"], ["Plur"]):
        return None
    index = int(person[0]) - 1 + (3 if number == ["Plur"] else 0)
    lemma = token.lemma_.casefold()
    if lemma in IRREGULAR_IMPERFECT:
        proposal = IRREGULAR_IMPERFECT[lemma][index]
    elif lemma.endswith(("ar", "er", "ir")):
        endings = ("ava", "avas", "ava", "ávamos", "áveis", "avam") if lemma.endswith("ar") else (
            "ia", "ias", "ia", "íamos", "íeis", "iam")
        proposal = lemma[:-2] + endings[index]
    else:
        return None
    value = flags(proposal)
    return match_case(proposal, token.text) if value & PAST and not value & (PRESENT | FUTURE) else None


def temporal_alert(block, offset, anchor, target, subtype, reason, severity, confidence, suggestion=None, end_token=None):
    last = end_token if end_token is not None else target
    start, end = offset + target.idx, offset + last.idx + len(last.text)
    result = asdict(finding(block, "Coerência temporal entre orações", "Verificar", start, end,
                            reason, "FONTE Morfossintático · " + subtype))
    result.update(rule="coerencia_temporal", category_code="temporal_consistency", relation=subtype,
                  severity=severity, confidence="alta" if confidence >= .85 else "média" if confidence >= .6 else "baixa",
                  confidence_score=confidence, suggestion=suggestion, suggestion_kind="possible",
                  related=[evidence(block, offset + anchor.idx, offset + anchor.idx + len(anchor.text))],
                  temporal_evidence={"anchor": anchor.text, "anchor_form": form(anchor),
                                     "target": target.text, "target_form": form(target)})
    return result


def relations(block, offset, doc):
    out = []
    for sentence in doc.sents:
        groups = {}
        for token in sentence:
            if form(token):
                groups.setdefault(predicate(token).i, []).append(token)
        for target in sentence:
            target_form = form(target)
            if target_form not in {"future", "present", "ambiguous_past_present"}:
                continue
            root = predicate(target)
            anchor, path = nearest_anchor(root, groups, sentence)
            if anchor is None or explicit_shift(root) or legitimate_present(target):
                continue
            anchor_form = form(anchor)
            between = doc[min(anchor.i, target.i):max(anchor.i, target.i)].text
            if any(c in between for c in (";", ":", "\n")):
                continue
            if (anchor_form == "conditional" and target_form == "future"
                    and any(dep in {"acl:relcl", "ccomp"} for dep in path)):
                proposal = conditional_suggestion(target)
                last = target
                # Contrai somente a perífrase contígua e sintaticamente ligada.
                # O intervalo precisa incluir “ser”, para não propor “seria ser”.
                if target.lemma_ == "ir" and target.i + 1 < sentence.end:
                    following = doc[target.i + 1]
                    if following.lower_ == "ser" and predicate(following) == root:
                        forms = {"irei": "seria", "irás": "serias", "irá": "seria",
                                 "iremos": "seríamos", "ireis": "seríeis", "irão": "seriam"}
                        contracted = forms.get(target.lower_)
                        if contracted:
                            proposal, last = match_case(contracted, target.text), following
                reason = (f"‘{anchor.text}’ estabelece uma hipótese ou projeção no futuro do pretérito; "
                          f"‘{target.text}’, em oração dependente, está no futuro do presente. "
                          "Se as duas ações compartilham a mesma projeção temporal, confira a uniformidade. "
                          "Uma referência futura própria pode justificar a alternância.")
                out.append(temporal_alert(block, offset, anchor, target, "conditional_future", reason,
                                          "probable_error", .82, proposal, last))
                continue
            markers = {child.lower_ for child in root.children if child.dep_ in {"mark", "advmod"}}
            simultaneous = "advcl" in path and "enquanto" in markers
            if (anchor_form == "past" and simultaneous
                    and anchor.lemma_.casefold() not in STATIVE and target.lemma_.casefold() not in STATIVE):
                if target_form == "present":
                    reason = (f"‘{anchor.text}’ situa a ação no passado, enquanto ‘{target.text}’ está no presente. "
                              "O conectivo ‘enquanto’ pode ligar ações simultâneas: se esse for o sentido, "
                              "confira o tempo da oração subordinada. Uso contrastivo e mudança deliberada de perspectiva são possíveis.")
                    out.append(temporal_alert(block, offset, anchor, target, "simultaneous_present", reason,
                                              "probable_error", .8, imperfect_suggestion(target)))
                elif target_form == "ambiguous_past_present" and not bounded_interval(root):
                    reason = (f"‘{target.text}’ admite tanto presente quanto pretérito perfeito; a grafia não decide. "
                              f"‘{anchor.text}’ está no passado e ‘enquanto’ pode indicar simultaneidade. "
                              "Confira se a segunda ação descreve um processo em curso, que pode pedir o imperfeito, "
                              "ou um intervalo concluído, em que o perfeito pode ser legítimo. Não há erro confirmado.")
                    out.append(temporal_alert(block, offset, anchor, target, "ambiguous_simultaneity", reason,
                                              "editorial_attention", .5))
            elif anchor_form == "past" and target_form == "present" and "conj" in path:
                # Preserva presentes resultativos e declarações gerais frequentes.
                if target.lemma_.casefold() in STATIVE:
                    continue
                reason = (f"A análise liga ‘{target.text}’ (presente) a uma oração coordenada sob ‘{anchor.text}’ (passado). "
                          "Confira se a descrição continua no mesmo momento ou se passa ao presente do narrador. "
                          "Consequências que continuam válidas e mudanças intencionais podem justificar a alternância.")
                out.append(temporal_alert(block, offset, anchor, target, "coordinated_past_present", reason,
                                          "editorial_attention", .65, imperfect_suggestion(target)))
    return out


# Propriedade, posse, aparência e existência: no presente, descrevem mais do que narram.
# ‘estar’ fica de fora: estado passageiro (“está ali”) e progressivo (“está voando”) narram.
STATE = STATIVE | {"ser", "ter", "haver", "parecer", "viver", "morar", "custar", "medir", "pesar"}
# Modais com infinitivo (“posso garantir”, “deve haver”): atitude ou possibilidade, não evento.
MODAL = {"poder", "dever", "precisar", "querer"}
# Verbos que introduzem conteúdo relatado ou sabido: “explicou que a Terra gira”.
REPORTING = {"dizer", "explicar", "contar", "afirmar", "saber", "aprender", "ensinar", "descobrir", "lembrar",
             "perceber", "entender", "ler", "ouvir", "achar", "pensar", "acreditar", "notar", "garantir"}
HABITUAL_MARKS = {"quando", "se", "sempre", "sempre que", "toda vez que"}
MAIN_LINE = {"ROOT", "conj", "parataxis"}
EVENT_RELATIONS = {"past_present_past", "coordinated_tense_mismatch", "same_subject_narrative_shift"}


def event_tense(token):
    """Passado ou presente de um predicado finito, combinando modelo, léxico e sintaxe.

    O modelo às vezes etiqueta o verbo como adjetivo (“Ela segura a mochila”) ou como
    verbo sem morfologia (“e solta o peixe”). Com o léxico admitindo a forma finita, o
    modelo sem leitura não finita e um objeto ligado (particípio sem auxiliar não toma
    objeto), a leitura verbal é aceita. Formas ambíguas não decidem.
    """
    value = form(token)
    if value in {"past", "present"}:
        return value
    lex = flags(token.text)
    verb_form = token.morph.get("VerbForm")
    if value is not None or not lex & FINITE or (verb_form and "Fin" not in verb_form):
        return None
    # Forma só verbal e finita no léxico (“Abri”, “Procuro”): basta, mesmo etiquetada como nome.
    exclusive = not lex & (NONVERB | NONFINITE) and finite(token)
    if not exclusive:
        if not any(c.dep_ in {"obj", "iobj"} for c in token.children):
            return None
        if not (finite(token) or token.pos_ == "VERB"):
            return None
    if lex & PRESENT and not lex & (PAST | FUTURE):
        return "present"
    if lex & PAST and not lex & (PRESENT | FUTURE):
        return "past"
    return None


def present_function(token):
    """Função provável de um verbo no presente na narração, por sinais transparentes.

    `narrative_event` só quando nenhum sinal de pensamento, fala relatada, verdade geral,
    hábito, estado ou comentário aparece. Na dúvida, não é evento.
    """
    sentence = token.sent
    root = predicate(token)
    if sentence.text.rstrip().endswith(("?", "!")):
        return "thought"
    if explicit_shift(root):
        return "narrator_comment"
    walk = root
    while walk.head != walk:
        if walk.dep_ in {"ccomp", "csubj", "acl:relcl", "acl", "advcl", "xcomp"} and walk.head.lemma_.casefold() in REPORTING:
            return "general_truth"
        walk = walk.head
    # Hábito ou condição geral: “derrete quando a temperatura aumenta”. O modelo liga
    # ‘quando’ como mark ou advmod; a oração principal não pode estar no passado.
    def habitual(clause):
        return bool({m.lower_ for m in clause.children if m.dep_ in {"mark", "advmod"}} & HABITUAL_MARKS)
    if root.dep_ in {"advcl", "ccomp"} and habitual(root) and event_tense(root.head) != "past":
        return "general_truth"
    if any(c.dep_ in {"advcl", "ccomp"} and habitual(c) and event_tense(c) == "present" for c in root.children):
        return "general_truth"
    lemma = token.lemma_.casefold()
    copula = token if token.dep_ == "cop" else next((c for c in root.children if c.dep_ == "cop"), None)
    if copula is not None:
        lemma = copula.lemma_.casefold()
    # “Parece envolver”: aparência de um acontecimento, não propriedade.
    if lemma in STATE and not (lemma == "parecer" and any(c.dep_ == "xcomp" and c.pos_ in {"VERB", "AUX"}
                                                        for c in token.children)):
        return "state"
    if lemma in MODAL and any(c.dep_ == "xcomp" for c in token.children):
        return "state"
    # As mesmas exceções da regra de tempo verbal (marca explícita, ‘há muito tempo’, locuções).
    if legitimate_present(token):
        return "narrator_comment"
    # A pessoa não decide: narradores em 1ª pessoa também quebram a sequência (“Abri… Olho…”).
    return "narrative_event"


def subject_key(token):
    """Sujeito explícito (lema) ou elíptico; o coordenado sem sujeito herda o do núcleo."""
    root = predicate(token)
    current = root
    while True:
        subject = next((c for c in current.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
        if subject is not None:
            return subject.lemma_.casefold()
        if current.dep_ != "conj" or current.head == current:
            return None
        current = current.head


def compatible(a, b):
    """Mesmo sujeito explícito, ou um deles elíptico com pessoa e número iguais."""
    if a["subject"] and b["subject"]:
        return a["subject"] == b["subject"]
    return a["person"] == b["person"] or not a["person"] or not b["person"]


def events(block, offset, doc, nlp, sentence_base):
    """Predicados finitos da linha principal, com tempo, função, sujeito e posição."""
    out = []
    for index, sentence in enumerate(doc.sents):
        tokens, base = sentence, offset
        first = next((t for t in sentence if t.is_alpha), None)
        # Segunda leitura com inicial minúscula: “Procura durante…” lido como substantivo.
        if (first is not None and first.text[:1].isupper() and flags(first.text) & FINITE
                and not any(event_tense(t) for t in sentence)):
            start = first.idx - sentence.start_char
            text = sentence.text
            tokens = nlp(text[:start] + text[start].lower() + text[start + 1:])
            base = offset + sentence.start_char
        for token in tokens:
            tense = event_tense(token)
            if tense is None or token.dep_ in {"aux", "aux:pass"} or predicate(token).dep_ not in MAIN_LINE:
                continue
            idx = base + token.idx
            out.append({"block": block, "start": idx, "end": idx + len(token.text), "token": token, "tense": tense,
                        "function": present_function(token) if tense == "present" else "narrative_event",
                        "subject": subject_key(token), "person": "".join(token.morph.get("Person")) +
                        "".join(token.morph.get("Number")), "sentence": sentence_base + index})
    return out


def sequence_alert(event, anchors, subtype, reason, confidence, severity="probable_error"):
    block, target = event["block"], event["token"]
    result = asdict(finding(block, "Coerência temporal entre orações", "Verificar", event["start"], event["end"],
                            reason, "FONTE Morfossintático · " + subtype))
    result.update(rule="coerencia_temporal", category_code="temporal_consistency", relation=subtype,
                  severity=severity, confidence="alta" if confidence >= .85 else "média" if confidence >= .6 else "baixa",
                  confidence_score=confidence, suggestion=imperfect_suggestion(target) if target.morph.get("Person") else None,
                  suggestion_kind="possible",
                  related=[evidence(a["block"], a["start"], a["end"]) for a in anchors if a["block"] is block] or
                          [evidence(anchors[0]["block"], anchors[0]["start"], anchors[0]["end"])],
                  temporal_evidence={"anchor": anchors[0]["token"].text, "anchor_form": "past",
                                     "target": target.text, "target_form": "present",
                                     "function": event["function"]})
    return result


def sequence(evts):
    """Estado narrativo local: presente que é evento entre ações no passado do mesmo plano.

    Janela de até 4 frases antes e 2 depois. Exige função `narrative_event`; o sujeito
    precisa ser o mesmo, ou elíptico compatível, para a confiança alta.
    """
    out = []
    for i, event in enumerate(evts):
        if event["tense"] != "present" or event["function"] != "narrative_event":
            continue
        before = [e for e in evts[:i] if event["sentence"] - e["sentence"] <= 4]
        after = [e for e in evts[i + 1:] if e["sentence"] - event["sentence"] <= 2]
        token = event["token"]
        # Coordenação na mesma oração: “pega … e abriu”, “puxou … e solta”.
        linked = [e for e in before + after if e["sentence"] == event["sentence"] and e["tense"] == "past"
                  and ((token.dep_ == "conj" and e["token"] == token.head)
                       or (e["token"].dep_ == "conj" and e["token"].head == token))
                  # O coordenado sem sujeito próprio herda o do núcleo: compara o sujeito herdado,
                  # não a pessoa da morfologia do modelo (que erra na 1ª pessoa sem sujeito).
                  and e["subject"] == event["subject"]]
        if linked:
            reason = (f"‘{token.text}’ (presente) e ‘{linked[0]['token'].text}’ (passado) são ações coordenadas do mesmo "
                      "sujeito, na mesma sequência. Provável inconsistência de tempo verbal: confira se as duas "
                      "ações deveriam estar no mesmo tempo.")
            out.append(sequence_alert(event, linked, "coordinated_tense_mismatch", reason, .88))
            continue
        previous = before[-1] if before else None
        following = after[0] if after else None
        if (previous and following and previous["tense"] == "past" and following["tense"] == "past"
                and previous["sentence"] < event["sentence"] < following["sentence"]
                and (compatible(previous, event) or compatible(following, event))):
            reason = (f"Provável inconsistência de tempo verbal: ‘{token.text}’, uma ação no presente, aparece entre "
                      f"‘{previous['token'].text}’ e ‘{following['token'].text}’, narradas no passado, no mesmo plano "
                      "narrativo e sem marca de fala, pensamento ou mudança deliberada de tempo.")
            out.append(sequence_alert(event, [previous, following], "past_present_past", reason, .9))
            continue
        chain = [e for e in before if e["sentence"] < event["sentence"]][-3:]
        if (len(chain) >= 2 and all(e["tense"] == "past" and compatible(e, event) for e in chain)
                and not (following and following["tense"] == "present")):
            reason = (f"As ações anteriores do mesmo sujeito estão no passado ({', '.join(e['token'].text for e in chain)}); "
                      f"‘{token.text}’ passa ao presente sem marca de mudança de plano. Provável inconsistência de "
                      "tempo verbal; confira se a mudança é intencional.")
            out.append(sequence_alert(event, chain, "same_subject_narrative_shift", reason, .85))
    return out


def accent_candidates(word):
    """Recupera hiatos em formas do imperfeito confirmadas pelo léxico.

    A família não depende de um verbo específico: caía, saía, construía,
    distribuíam, atraíamos etc. Acentos são propostos, nunca aplicados.
    """
    normalized = unicodedata.normalize("NFC", word.casefold())
    if not re.search(r"i(?:a|as|am|amos|eis)$", normalized):
        return []
    candidates = []
    for i, char in enumerate(normalized):
        if char == "i":
            proposal = normalized[:i] + "í" + normalized[i+1:]
            value = flags(proposal)
            if value & PAST and not value & (PRESENT | FUTURE):
                candidates.append(match_case(proposal, word))
    return candidates


def accents(block, offset, doc, expected_tense):
    # Sem eixo passado explícito/inferido, não decide uma grafia ambígua.
    if expected_tense != "passado":
        return []
    out = []
    for sentence in doc.sents:
        if any(t.lower_ in SUBJUNCTIVE_CUES for t in sentence) or any(t.text in {"!", "?"} for t in sentence):
            continue
        for token in sentence:
            if token.pos_ != "VERB" or token.dep_ != "ROOT":
                continue
            subjects = [c for c in token.children if c.dep_ == "nsubj"]
            if not subjects or any(t.lower_ in {"tu", "vós", "você", "vocês"} for t in subjects):
                continue
            proposals = accent_candidates(token.text)
            if len(proposals) != 1:
                continue
            reason = (f"No eixo passado configurado/inferido, ‘{proposals[0]}’ é uma leitura possível deste predicado. "
                      f"O léxico confirma essa forma acentuada; ‘{token.text}’ pode ter outro uso ou uma análise incerta. "
                      "Confira o modo verbal e a intenção antes de alterar a acentuação.")
            result = asdict(finding(block, "Acentuação verbal no contexto", "Verificar", offset + token.idx,
                                    offset + token.idx + len(token.text), reason,
                                    "FONTE Morfossintático · acentuacao_contextual"))
            result.update(rule="acentuacao_contextual", category_code="contextual_accentuation",
                          severity="probable_error", confidence="média", confidence_score=.8,
                          suggestion=proposals[0], related=[evidence(block, offset + s.idx,
                              offset + s.idx + len(s.text)) for s in subjects])
            out.append(result)
    return out


def analyze(blocks, nlp, settings, expected_tense="auto"):
    roles = classify(blocks, settings)
    jobs = []
    allowed = set(settings["tense_scopes"] if settings["rules"]["coerencia_temporal"] else [])
    if settings["rules"]["acentuacao_contextual"]:
        allowed.add("narracao")
    for block, labels in zip(blocks, roles):
        for start, end, role in spans(labels, allowed):
            if block.text[start:end].strip():
                jobs.append((block, start, end, role))
    out, evts, sentences, last_block = [], [], 0, None
    headings = [b.number for b in blocks if b.heading]
    for (block, start, end, role), doc in zip(jobs, nlp.pipe((b.text[s:e] for b, s, e, _ in jobs), batch_size=32)):
        if settings["rules"]["coerencia_temporal"] and role in settings["tense_scopes"]:
            out.extend(relations(block, start, doc))
            # A sequência só considera a narração; um título (capítulo) recomeça a cena.
            if role == "narracao" and expected_tense == "passado":
                if last_block is not None and any(last_block.number < h < block.number for h in headings):
                    out.extend(sequence(evts)); evts = []
                if last_block is not None and last_block is not block:
                    sentences += 2  # Mudança de parágrafo pesa como distância.
                evts.extend(events(block, start, doc, nlp, sentences))
                sentences += len(list(doc.sents)); last_block = block
        if settings["rules"]["acentuacao_contextual"] and role == "narracao":
            out.extend(accents(block, start, doc, expected_tense))
    out.extend(sequence(evts))
    # O alerta de sequência substitui a relação genérica no mesmo verbo.
    strong = {(f["paragraph"], f["start"], f["end"]) for f in out if f.get("relation") in EVENT_RELATIONS}
    return [f for f in out if f.get("relation") in EVENT_RELATIONS or (f["paragraph"], f["start"], f["end"]) not in strong]
