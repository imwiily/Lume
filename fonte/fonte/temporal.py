"""Relações temporais locais por dependências, morfologia e confirmação lexical.

Não infere a intenção narrativa nem impõe concordância temporal absoluta.
As regras não contêm nomes próprios, frases de manuscritos ou fatos de obras.
"""
from dataclasses import asdict
import re
import unicodedata

from .analysis import TERMINACOES, explicar, finding, lista_ou_rotulo
from .editorial.common import evidence
from .lexicon import FINITE, PAST, PRESENT, FUTURE, NONFINITE, flags
from .verbo import certamente_verbo, model_finite, so_verbo_no_lexico
from .tempo import (IMPERFECT_ENDING, IRREGULAR_IMPERFECT, TERMINACAO_CONDICIONAL, TERMINACAO_IMPERFEITO_SUBJUNTIVO, imperfeito,
                    mais_que_perfeito_composto, para_como_verbo, tempo_estrito, tempo_recuperado,
                    verbo_unico_da_frase)
from .segments import classify, spans

TIME_SHIFTS = {"hoje", "agora", "atualmente", "amanhã", "ontem", "outrora", "antigamente",
               "sempre", "geralmente", "habitualmente", "ainda", "desde", "depois", "atual"}
STATIVE = {"saber", "conhecer", "existir", "possuir", "pertencer", "entender", "compreender",
           "gostar", "preferir", "continuar", "permanecer", "valer", "significar"}
SUBJUNCTIVE_CUES = {"talvez", "quiçá", "oxalá", "tomara", "embora", "caso", "se", "que"}



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


def own_clause(root):
    """Tokens da oração de `root`, sem as orações coordenadas ou subordinadas a ela (“…, mas ele
    ainda…”, “desde que acordei”) e sem adjuntos de nome (“a reunião de hoje”)."""
    skip = set()
    for child in root.children:
        if child.dep_ in {"conj", "parataxis", "advcl", "ccomp", "acl", "acl:relcl"}:
            skip.update(t.i for t in child.subtree)
    return [t for t in root.subtree if t.i not in skip and not (t.dep_ == "nmod" and t.head.pos_ in {"NOUN", "PROPN"})]


def governs(root, token):
    """O verbo mais próximo acima de `token` na árvore é `root`: a marca pertence a esta oração,
    não a uma subordinada (“desde que saímos”) nem a um verbo dependente (“lembrar da prova de hoje”)."""
    if token.dep_ == "mark":
        return False  # Subordinante: abre outra oração.
    walk = token.head
    while walk != root and walk.head != walk and walk.pos_ not in {"VERB", "AUX"} and not certamente_verbo(walk):
        walk = walk.head
    return walk == root


def explicit_shift(root):
    tokens = [t for t in own_clause(root) if t.lower_ not in TIME_SHIFTS or governs(root, t)]
    markers = {t.lower_ for t in tokens} & TIME_SHIFTS
    # ‘Ainda’ mantém no presente um estado que continua (“está quebrado ainda”), não uma ação
    # da cena (“ainda caem pelo chão”).
    # ‘Ficar’ muda de estado: “fica mais forte ainda” é intensidade, não continuidade.
    # ‘Estar’ sem predicativo (“ainda está no quintal”) é posição na cena; “está quebrado ainda” conta pela cópula.
    if markers == {"ainda"} and not (root.lemma_.casefold() in STATIVE | {"ser", "permanecer", "ter", "haver"}
                                     or root.pos_ in {"ADJ", "NOUN"} or any(c.dep_ == "cop" for c in root.children)):
        markers = set()
    if markers:
        return True
    text = " ".join(t.text for t in tokens)
    return bool(re.search(r"\b(?:[12]\d{3}|pr[oó]xim[oa]|atualmente|neste (?:momento|instante)|no momento)\b", text, re.I))


# O narrador em primeira pessoa fala de si no presente, fora da cena: “me chamo”, “sou” + nome ou
# adjetivo, “acho que”, “confesso que”, “vou contar”. Ações da cena (“Sinto o frio”, “Vou até a
# porta”, “Sou atingido”) continuam comparadas com a narração.
NARRATOR_THAT = {"acho", "sinto", "sei", "creio", "acredito", "confesso", "admito", "imagino", "espero",
                 "lembro", "garanto", "juro", "suponho", "quero", "penso", "reconheço"}
NARRATOR_TELLS = re.compile(r"vou\s+(?:\w+\s+)?(?:contar|narrar|relatar|explicar|falar|dizer|começar|descrever|"
                            r"mostrar|resumir|apresentar)\b", re.I)


def narrator_frame(token):
    """Verbo na primeira pessoa do singular que é comentário do narrador sobre si, não evento da cena.

    Um passado antes dele na mesma frase (“desde que acordei, sinto que…”) o prende à cena, exceto
    na identidade do narrador sem predicado depois (“mudou quem eu sou”)."""
    word = token.lower_
    tail = token.doc.text[token.idx:token.sent.end_char]
    prefix = token.doc.text[token.sent.start_char:token.idx]
    if word == "sou" and re.search(r"\b(?:quem|que)\s+(?:eu\s+)?$", prefix, re.I) and re.fullmatch(r"sou\W*", tail):
        return True
    if any(tempo_estrito(t) in {"past", "ambiguous_past_present"} for t in token.sent if t.i < token.i):
        return False
    if word == "chamo" and re.search(r"\bme\s*$", prefix, re.I):
        return True
    if word == "sou":
        head = token.head if token.dep_ == "cop" else None
        following = next((t for t in token.doc[token.i + 1:token.sent.end] if not t.is_space), None)
        participle = following is not None and "Part" in following.morph.get("VerbForm")
        return head is not None and head.pos_ in {"NOUN", "ADJ", "PROPN", "PRON", "NUM"} and not participle
    if word in NARRATOR_THAT and re.match(r"\w+\s+que\b", tail, re.I):
        return True
    return word == "vou" and bool(NARRATOR_TELLS.match(tail))


def legitimate_present(token):
    """Evidências locais compartilhadas pelas duas verificações temporais.

    Abstém-se diante de estados atuais plausíveis; não prova causalidade.
    Não libera ações no presente só porque aparecem depois de um passado.
    """
    if tempo_estrito(token) != "present":
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
            and not any(tempo_estrito(t) in {"past", "ambiguous_past_present"} for t in token.sent if t.i < token.i)):
        return True
    if token.lemma_.casefold() in STATIVE:
        return True
    # Comentário do narrador e o que ele afirma nele (“sinto que devo…”).
    if narrator_frame(token) or any(narrator_frame(a) for a in token.ancestors if tempo_estrito(a) == "present"):
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
            if tempo_estrito(candidate):
                groups.setdefault(predicate(candidate).i, []).append(candidate)
        anchor, path = nearest_anchor(root, groups, token.sent)
        if anchor is not None and tempo_estrito(anchor) == "past" and "conj" in path:
            return predicate(anchor).lemma_.casefold() in {
                "sofrer", "quebrar", "ferir", "machucar", "adoecer", "cair", "morrer",
                "nascer", "chegar", "perder", "ganhar", "terminar", "concluir", "aposentar"}
    return False


# Orações dependentes: relativa, completiva, adverbial, subjetiva.
DEPENDENT = {"acl:relcl", "acl", "ccomp", "advcl", "csubj"}
# Modais que, no imperfeito com infinitivo, podem expressar expectativa ou possibilidade, não
# uma ação passada da cena. ‘Devia’ é quase sempre ‘deveria’ (“deviam atrapalhar”); ‘podia’ divide-se
# entre ‘poderia’ e a capacidade no passado, por isso só perde confiança. ‘Parecia estar’, ‘queria
# sair’, ‘precisava ir’ e ‘tinha que’ descrevem aparência, desejo ou necessidade no passado e
# continuam comparados com a narração.
MODAL_IMPERFECT = {"dever", "poder"}
# Introdutores de oração dependente ligados ao verbo dela.
INTRODUCERS = {"que", "onde", "cujo", "cuja", "cujos", "cujas", "quem", "qual", "quais", "quando", "enquanto",
               "porque", "embora", "se", "como", "conforme", "caso", "porquanto", "conquanto"}


def modal_imperfect(token):
    """Lema do modal (‘dever’ ou ‘poder’) no imperfeito seguido de infinitivo; senão None."""
    lemma = lemma_of(token, MODAL_IMPERFECT)
    if lemma is None or not IMPERFECT_ENDING.search(token.lower_):
        return None
    following = [t for t in token.doc[token.i + 1:token.i + 4] if not t.is_punct]
    if following and following[0].lower_ in {"não", "nunca", "mesmo", "até", "também", "bem"}:
        following = following[1:]
    return lemma if following and "Inf" in following[0].morph.get("VerbForm") else None


def introduced(clause):
    """A oração tem introdutor próprio: subordinante (mark) ou relativo ligado ao verbo dela."""
    return any(c.dep_ == "mark" or "Rel" in c.morph.get("PronType") or c.lower_ in INTRODUCERS
               for c in clause.children if c.i < clause.i)


def misattached(conjunct):
    """Verbo finito coordenado pela análise a um infinitivo, gerúndio ou subjuntivo: o modelo o
    pendurou na oração errada (“abaixa para pegar a moeda, mas não encontrou nada”); a coordenação
    verdadeira é com a linha principal."""
    head = conjunct.head
    finite_conjunct = certamente_verbo(conjunct) and "Sub" not in conjunct.morph.get("Mood")
    return finite_conjunct and (bool(set(head.morph.get("VerbForm")) & {"Inf", "Ger"}) or "Sub" in head.morph.get("Mood"))


def dependent_clause(token):
    """O predicado de `token` está numa oração dependente (relativa, completiva ou adverbial) com
    introdutor próprio. O rótulo da árvore sozinho não basta: o modelo pendura verbos principais em
    adjetivos, particípios e infinitivos. ‘Enquanto’ fica de fora: liga ações simultâneas, e o
    passado ali continua comparável com a oração principal."""
    walk = predicate(token)
    while walk.head != walk:
        markers = {c.lower_ for c in walk.children if c.dep_ in {"mark", "advmod"}}
        if "enquanto" in markers:
            return False
        if walk.dep_ == "conj" and misattached(walk):
            return False
        if walk.dep_ in DEPENDENT and introduced(walk):
            return True
        walk = walk.head
    return False


def past_plane(token):
    """Plano de um passado numa narração no presente.

    “anterior”: fato anterior ao momento narrado ou expectativa, legítimo — mais-que-perfeito
    composto, perfeito em oração dependente (“o rapaz que encontrou na festa”, “descobre que foi
    ali que…”) e ‘devia’ + infinitivo. “incerto”: imperfeito em oração dependente (estado anterior
    ou ação simultânea à cena, que pediria o presente: “por onde passava”) e ‘podia’ + infinitivo.
    None: passado da linha principal (“abre a porta e caminhou”), comparado com a narração.
    """
    if mais_que_perfeito_composto(token):
        return "anterior"
    modal = modal_imperfect(token)
    if modal:
        return "anterior" if modal == "dever" else "incerto"
    if dependent_clause(token):
        return "incerto" if imperfeito(token) else "anterior"
    return None


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
                  temporal_evidence={"anchor": anchor.text, "anchor_form": tempo_estrito(anchor),
                                     "target": target.text, "target_form": tempo_estrito(target)})
    return result


# Precedência entre alertas do mesmo verbo: o mais específico prevalece.
PRECEDENCE = ("conditional_tense_mismatch", "modal_mood_mismatch", "coordinated_tense_mismatch", "past_present_past",
              "same_subject_narrative_shift", "local_narrative_tense_shift")


def clause_tense(token):
    """Tempo da principal de uma condicional: futuro do pretérito pela terminação confirmada no
    léxico (o modelo lê “morreria” como adjetivo), senão futuro ou presente do indicativo."""
    word, value = token.text.casefold(), flags(token.text)
    if TERMINACAO_CONDICIONAL.search(word) and value & FINITE and not value & (PAST | PRESENT | FUTURE):
        return "conditional"
    tense = tempo_estrito(token)
    if tense in {"future", "present"}:
        return tense
    return tempo_recuperado(token) if tempo_recuperado(token) == "present" else None


def conditionals(block, offset, doc):
    """Par condição-consequência: “se” + imperfeito do subjuntivo pede futuro do pretérito
    (“se chegasse, conseguiria”); “se” + presente ou futuro do subjuntivo pede presente ou
    futuro (“se chover, ficaremos”). Discurso indireto fica de fora."""
    out = []
    for sub in doc:
        if sub.dep_ != "advcl" or not any(c.dep_ == "mark" and c.lower_ == "se" for c in sub.children):
            continue
        main = sub.head
        walk = main
        reported = False
        while walk.head != walk:
            if walk.dep_ in {"ccomp", "xcomp"} and walk.head.lemma_.casefold() in REPORTING:
                reported = True
            walk = walk.head
        if reported:
            continue
        word = sub.text.casefold()
        if TERMINACAO_IMPERFEITO_SUBJUNTIVO.search(word) and flags(word) & FINITE:
            condition, expected = "imperfeito do subjuntivo", "conditional"
        # Depois de ‘se’, a forma igual ao infinitivo (“se isso acertar”) é o futuro do subjuntivo.
        elif (("Sub" in sub.morph.get("Mood") and "Fut" in sub.morph.get("Tense")) or tempo_estrito(sub) == "present"
              or ("Inf" in sub.morph.get("VerbForm") and not sub.morph.get("Mood"))):
            condition, expected = "presente ou futuro do subjuntivo", "present_future"
        else:
            continue
        found = clause_tense(main)
        if found is None:
            continue
        if expected == "conditional" and found in {"future", "present"}:
            simple = (f"A condição ‘se … {sub.text}’ é uma hipótese, que costuma vir com verbos como ‘seria’ ou "
                      f"‘conseguiria’. ‘{main.text}’ não está nessa forma.")
        elif expected == "present_future" and found == "conditional":
            simple = (f"A condição ‘se … {sub.text}’ fala de algo possível, que costuma vir com verbos como ‘é’ ou "
                      f"‘vai ser’. ‘{main.text}’ está na forma de hipótese (‘…ria’).")
        else:
            continue
        reason = explicar(simple + " Confira se a condição e o resultado combinam. Em falas relatadas ou por estilo, "
                          "a mistura pode ser intencional.",
                          f"correlação de tempos na condicional (condição no {condition})")
        out.append(temporal_alert(block, offset, sub, main, "conditional_tense_mismatch", reason, "probable_error", .86))
    return out


def modality(block, offset, doc):
    """‘Talvez’ antes do verbo, na mesma oração, com o verbo no futuro do pretérito (“Talvez essa
    decisão ajudaria”): a dúvida costuma pedir o subjuntivo (“ajudasse”). Fica de fora ‘talvez’
    seguido de vírgula (inciso) e o verbo de uma condicional, que tem regra própria."""
    out = []
    for adverb in doc:
        if adverb.lower_ != "talvez":
            continue
        # Até a pontuação, sem depender da árvore (o modelo lê “ajudaria” como adjetivo de “decisão”).
        clause = []
        for t in doc[adverb.i + 1:]:
            if t.is_punct:
                break
            clause.append(t)
        verb = next((t for t in clause if clause_tense(t) is not None), None)
        if (not clause or clause[0].is_punct or verb is None or clause_tense(verb) != "conditional"
                # “se” (condicional) ou “que” (comparativa, subordinada) antes do verbo: outra oração.
                or any(t.lower_ in {"se", "que"} for t in clause[:clause.index(verb)])
                or any(c.dep_ == "advcl" and any(m.lower_ == "se" for m in c.children) for c in verb.children)):
            continue
        reason = explicar(f"Com ‘talvez’ antes do verbo, a dúvida costuma usar a forma terminada em ‘…sse’ (‘talvez "
                          f"ajudasse’). ‘{verb.text}’ está na forma ‘…ria’. Confira qual você quis dizer.",
                          "modo verbal com ‘talvez’ (subjuntivo × futuro do pretérito)")
        out.append(temporal_alert(block, offset, adverb, verb, "modal_mood_mismatch", reason, "editorial_attention", .7))
    return out


def relations(block, offset, doc):
    out = []
    for sentence in doc.sents:
        groups = {}
        for token in sentence:
            if tempo_estrito(token):
                groups.setdefault(predicate(token).i, []).append(token)
        for target in sentence:
            target_form = tempo_estrito(target)
            if target_form not in {"future", "present", "ambiguous_past_present"}:
                continue
            root = predicate(target)
            anchor, path = nearest_anchor(root, groups, sentence)
            if anchor is None or explicit_shift(root) or legitimate_present(target):
                continue
            anchor_form = tempo_estrito(anchor)
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
                reason = explicar(f"‘{anchor.text}’ fala de uma hipótese (forma ‘…ria’), mas ‘{target.text}’, ligado a "
                                  "ele, está no futuro comum (‘…rá’). Quando as duas coisas fazem parte da mesma hipótese, "
                                  "costumam usar a mesma forma. Se a segunda for um futuro de verdade, está certo.",
                                  "futuro do pretérito × futuro do presente")
                out.append(temporal_alert(block, offset, anchor, target, "conditional_future", reason,
                                          "probable_error", .82, proposal, last))
                continue
            markers = {child.lower_ for child in root.children if child.dep_ in {"mark", "advmod"}}
            simultaneous = "advcl" in path and "enquanto" in markers
            if (anchor_form == "past" and simultaneous
                    and anchor.lemma_.casefold() not in STATIVE and target.lemma_.casefold() not in STATIVE):
                if target_form == "present":
                    reason = explicar(f"‘{anchor.text}’ está no passado e ‘{target.text}’ está no presente. Se o ‘enquanto’ "
                                      "indica que as duas coisas aconteceram ao mesmo tempo, costumam ficar no mesmo tempo. "
                                      "Se for um contraste ou mudança proposital, está certo.",
                                      "tempo verbal em orações simultâneas")
                    out.append(temporal_alert(block, offset, anchor, target, "simultaneous_present", reason,
                                              "probable_error", .8, imperfect_suggestion(target)))
                elif target_form == "ambiguous_past_present" and not bounded_interval(root):
                    reason = explicar(f"‘{target.text}’ pode ser presente ou passado; a palavra é igual nos dois. "
                                      f"‘{anchor.text}’ está no passado, e o ‘enquanto’ indica coisas ao mesmo tempo. Se "
                                      "a ação ainda estava acontecendo, costuma-se usar a forma ‘…ava’/‘…ia’; se já tinha "
                                      "terminado, a forma atual pode estar certa. Não há erro confirmado.",
                                      "pretérito perfeito × imperfeito em orações simultâneas")
                    out.append(temporal_alert(block, offset, anchor, target, "ambiguous_simultaneity", reason,
                                              "editorial_attention", .5))
            elif anchor_form == "past" and target_form == "present" and "conj" in path:
                # Preserva presentes resultativos e declarações gerais frequentes.
                if target.lemma_.casefold() in STATIVE:
                    continue
                # A âncora precisa estar no mesmo nível da coordenação: um passado dentro de relativa ou
                # subordinada (“a briga que havia tido e percebe…”) e o imperfeito modal (“deviam
                # atrapalhar, mas é…”) não são o predicado coordenado.
                if dependent_clause(anchor) or modal_imperfect(anchor):
                    continue
                reason = explicar(f"‘{target.text}’ está no presente e vem ligado a ‘{anchor.text}’, que está no passado. "
                                  "Confira se as duas falam do mesmo momento. Se a segunda for algo que continua valendo "
                                  "hoje, ou uma mudança proposital, está certo.", "tempo verbal em orações coordenadas")
                out.append(temporal_alert(block, offset, anchor, target, "coordinated_past_present", reason,
                                          "editorial_attention", .65, imperfect_suggestion(target)))
    return out


# Propriedade, posse, aparência e existência: no presente, descrevem mais do que narram.
# ‘estar’ fica de fora: estado passageiro (“está ali”) e progressivo (“está voando”) narram.
STATE = STATIVE | {"ser", "ter", "haver", "parecer", "viver", "morar", "custar", "medir", "pesar",
                   # Memória e crença do narrador (“quase não lembro o rosto dela”): estado mental.
                   "lembrar", "recordar", "esquecer", "acreditar", "achar", "imaginar", "duvidar"}
# Modais com infinitivo (“posso garantir”, “deve haver”): atitude ou possibilidade, não evento.
MODAL = {"poder", "dever", "precisar", "querer"}
# Verbos que introduzem conteúdo relatado ou sabido: “explicou que a Terra gira”.
REPORTING = {"dizer", "explicar", "contar", "afirmar", "saber", "aprender", "ensinar", "descobrir", "lembrar",
             "perceber", "entender", "ler", "ouvir", "achar", "pensar", "acreditar", "notar", "garantir"}
HABITUAL_MARKS = {"quando", "se", "sempre", "sempre que", "toda vez que"}
# Hábito sem conjunção: “durante todo o ano”, “todos os dias”, “normalmente”, “costuma”.
HABITUAL_WORDS = {"normalmente", "geralmente", "habitualmente", "frequentemente", "costumar"}
HABITUAL_TIME = re.compile(r"\b(?:tod[oa]s?\s+(?:o|a|os|as)\s+(?:anos?|dias?|semanas?|meses|noites?|manhãs?|tardes?|vezes|inverno|verão)"
                           r"|o\s+ano\s+(?:todo|inteiro)|a\s+vida\s+toda)\b", re.I)
PROXIMAL = {"este", "esta", "estes", "estas", "esse", "essa", "esses", "essas"}
MAIN_LINE = {"ROOT", "conj", "parataxis"}
EVENT_RELATIONS = {"past_present_past", "coordinated_tense_mismatch", "same_subject_narrative_shift",
                   "local_narrative_tense_shift"}
# Linha separadora de cena (“* * *”, “---”, “#”): interrompe o estado local.
SCENE_BREAK = re.compile(r"^\W+$")
# Âncoras na cena: entidade nova (indefinido), retomada (pronome, possessivo, demonstrativo).
INDEFINITE = {"um", "uma", "uns", "umas", "alguns", "algumas", "vários", "várias", "outro", "outra", "outros", "outras"}
ANAPHORIC = {"ele", "ela", "eles", "elas", "seu", "sua", "seus", "suas", "dele", "dela", "deles", "delas",
             "me", "te", "lhe", "lhes", "meu", "minha", "meus", "minhas", "esse", "essa", "este", "esta",
             "aquele", "aquela", "isso", "aquilo", "nosso", "nossa"}
ASPECTUAL = {"começar", "voltar", "continuar", "passar", "acabar", "tornar", "pôr", "ficar"}


def lemma_of(token, verbs):
    """Lema do verbo no grupo `verbs`; com o lema errado do modelo (“lembro”), pelo radical
    mais uma terminação verbal, o mesmo critério dos verbos de fala."""
    lemma = token.lemma_.casefold()
    if lemma in verbs:
        return lemma
    word = token.text.casefold()
    for verb in verbs:
        stem = verb[:-2]
        if len(stem) >= 3 and word.startswith(stem) and TERMINACOES.fullmatch(word[len(stem):]):
            return verb
    return None


def asks(sentence):
    """Pergunta ou exclamação; o modelo às vezes separa o “?” numa frase própria."""
    following = sentence.doc.text[sentence.end_char:].lstrip()[:1]
    return sentence.text.rstrip().endswith(("?", "!")) or following in {"?", "!"}


def discourse_marker(token):
    """Forma verbal sem predicação (“Tá.”, “Tá, então vamos.”): resposta curta ou marcador
    discursivo, não ação. Sem sujeito, complemento nem adjunto, e só ela na frase ou na abertura."""
    # Cópula de um predicativo curto (“Tá bom.”): a unidade é o predicativo.
    if token.dep_ == "cop" and token.head.pos_ in {"ADJ", "ADV"} and token.head.i == token.i + 1:
        head = token.head
        if any(not c.is_punct and c != token for c in head.children):
            return False
        after = token.doc.text[head.idx + len(head.text):].lstrip()[:1]
        before = token.doc.text[:token.idx].rstrip()[-1:]
        return after in {",", ".", "!", "…", ";"} and (not before or before in ".!?…:—–\n\"“")
    # Negação colada antes (“Não importa.”, “Não sei.”) faz parte da expressão.
    negation = next((c for c in token.children if c.lower_ == "não" and c.i == token.i - 1), None)
    args = [c for c in token.children if not c.is_punct and (negation is None or c.i != negation.i)]
    # “Tá bom.”, “Tá certo.”: no máximo um adjetivo ou advérbio sem dependentes, colado ao verbo.
    if len(args) > 1 or (args and (args[0].pos_ not in {"ADJ", "ADV"} or list(args[0].children)
                                   or args[0].i != token.i + 1)):
        return False
    last = args[0] if args else token
    first = negation if negation is not None else token
    # Pelo texto, não pela divisão de frases do modelo: a forma vem logo antes de pontuação e abre a frase.
    after = token.doc.text[last.idx + len(last.text):].lstrip()[:1]
    before = token.doc.text[:first.idx].rstrip()[-1:]
    return after in {",", ".", "!", "…", ";"} and (not before or before in ".!?…:—–\n\"“")


def present_function(token):
    """Função provável de um verbo no presente na narração, por sinais transparentes.

    `narrative_event` só quando nenhum sinal de pensamento, fala relatada, verdade geral,
    hábito, estado ou comentário aparece. Na dúvida, não é evento.
    """
    sentence = token.sent
    root = predicate(token)
    if discourse_marker(token):
        return "discourse_marker"
    if asks(sentence):
        return "thought"
    if explicit_shift(root):
        return "narrator_comment"
    walk = root
    while walk.head != walk:
        if walk.dep_ in {"ccomp", "csubj", "acl:relcl", "acl", "advcl", "xcomp"} and walk.head.lemma_.casefold() in REPORTING:
            return "general_truth"
        walk = walk.head
    # Consequência de uma condição (“Se eu parar, vou cair”): hipótese, não ação da cena.
    if any(c.dep_ == "advcl" and any(m.dep_ == "mark" and m.lower_ == "se" for m in c.children) for c in root.children):
        return "hypothetical"
    # Hábito ou condição geral: “derrete quando a temperatura aumenta”. O modelo liga
    # ‘quando’ como mark ou advmod; a oração principal não pode estar no passado.
    def habitual(clause):
        return bool({m.lower_ for m in clause.children if m.dep_ in {"mark", "advmod"}} & HABITUAL_MARKS)
    if root.dep_ in {"advcl", "ccomp"} and habitual(root) and tempo_recuperado(root.head) != "past":
        return "general_truth"
    if any(c.dep_ in {"advcl", "ccomp"} and habitual(c) and tempo_recuperado(c) == "present" for c in root.children):
        return "general_truth"
    clause_text = " ".join(t.text for t in own_clause(root))
    if (HABITUAL_TIME.search(clause_text) or {t.lower_ for t in own_clause(root)} & HABITUAL_WORDS
            or lemma_of(token, {"costumar"})):
        return "general_truth"
    # Propriedade genérica: sujeito com artigo definido e nada mais, objeto sem determinante
    # (“O ferro conduz eletricidade”): classe, não personagem da cena.
    subj = next((c for c in root.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
    obj = next((c for c in root.children if c.dep_ == "obj"), None)
    if (subj is not None and subj.pos_ == "NOUN" and [c.lower_ for c in subj.children] in (["o"], ["a"])
            and obj is not None and obj.pos_ == "NOUN" and not any(c.dep_ == "det" for c in obj.children)):
        return "general_truth"
    copula = token if token.dep_ == "cop" else next((c for c in root.children if c.dep_ == "cop"), None)
    lemma = lemma_of(copula if copula is not None else token, STATE) or token.lemma_.casefold()
    # ‘Estar’ + adjetivo ou particípio (“está quebrado”, “está acesa”): estado passageiro. Não é
    # ação da sequência, mas também não é propriedade; o alerta genérico mantém peso médio.
    if copula is not None and copula.lemma_.casefold() == "estar":
        return "transient_state"
    # Perífrase com gerúndio (“continua deslizando”, “está correndo”): ação em curso, não estado.
    if token.dep_ == "aux" and "Ger" in token.head.morph.get("VerbForm") or any(
            c.dep_ in {"xcomp", "aux"} and "Ger" in c.morph.get("VerbForm") for c in token.children):
        return "narrative_event"
    # “Ela parece assustada”: aparência passageira de uma pessoa da cena, como ‘estar’; “Aquele
    # lugar parece estranho” (coisa) continua avaliação.
    subject = next((c for c in root.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
    if (lemma == "parecer" and subject is not None and subject.pos_ in {"PRON", "PROPN"}
            and any(c.dep_ == "xcomp" and c.pos_ == "ADJ" for c in token.children)):
        return "transient_state"
    # “Parece envolver”: aparência de um acontecimento, não propriedade.
    if lemma in STATE and not (lemma == "parecer" and any(c.dep_ == "xcomp" and c.pos_ in {"VERB", "AUX"}
                                                        for c in token.children)):
        return "state"
    if lemma in MODAL and any(c.dep_ == "xcomp" for c in token.children):
        return "state"
    # Demonstrativo próximo no sujeito (“Esse diretor me causa arrepios”): aponta para o agora de
    # quem narra; na narração no passado a referência à história usa ‘aquele’.
    subject = next((c for c in root.children if c.dep_ in {"nsubj", "nsubj:pass"}), None)
    if subject is not None and any(c.lower_ in PROXIMAL for c in subject.children if c.dep_ == "det"):
        return "narrator_comment"
    # As mesmas exceções da regra de tempo verbal (marca explícita, ‘há muito tempo’, locuções).
    if legitimate_present(token):
        return "narrator_comment"
    # A pessoa não decide: narradores em 1ª pessoa também quebram a sequência (“Abri… Olho…”).
    return "narrative_event"


def subject_features(token):
    """Gênero e número do sujeito explícito (para o pronome retomar só um nome compatível)."""
    root = predicate(token)
    subject = next((c for c in root.children if c.dep_ in {"nsubj", "nsubj:pass"} and c.i < root.i), None)
    if subject is None:
        return ("", "")
    return ("".join(subject.morph.get("Gender")), "".join(subject.morph.get("Number")))


def subject_key(token):
    """Sujeito explícito (lema) ou elíptico; o coordenado sem sujeito herda o do núcleo."""
    root = predicate(token)
    current = root
    while True:
        subject = next((c for c in current.children if c.dep_ in {"nsubj", "nsubj:pass"} and c.i < current.i), None)
        if subject is not None:
            return subject.lemma_.casefold()
        if current.dep_ != "conj" or current.head == current:
            return None
        current = current.head


def compatible(a, b):
    """Mesmo sujeito explícito, ou um deles elíptico com pessoa e número iguais."""
    if a["subject"] and b["subject"]:
        # Pronome de 3ª pessoa retoma o sujeito anterior (“Helena… Ela… Helena”), se pessoa e número batem.
        if a["subject"] != b["subject"] and not ({a["subject"], b["subject"]} & PRONOUNS):
            return False
    # Pessoa e número só contam quando os dois estão definidos (o modelo nem sempre os dá).
    return all(x == y or not x or not y for x, y in zip(a["person"], b["person"]))


def anchored(token):
    """A oração pertence à cena: entidade nova (indefinido ou adjetivo anteposto ao sujeito),
    retomada (pronome, possessivo, demonstrativo), 1ª/2ª pessoa ou perífrase aspectual
    (“começa a sair”). Sem âncora, o presente pode ser comentário ou verdade geral."""
    root = predicate(token)
    # A frase inteira: o modelo às vezes pendura o verbo no sujeito (“Alguns livros ainda caem”).
    words = {t.lower_ for t in token.sent}
    subject = next((c for c in root.children if c.dep_ in {"nsubj", "nsubj:pass"}),
                   root.head if root.dep_ == "acl" else None)
    preposed = subject is not None and any(c.dep_ == "amod" and c.i < subject.i for c in subject.children)
    person = token.morph.get("Person")
    # Perífrase aspectual ou progressiva (“começa a sair”, “continua avançando”, “fico olhando”).
    aspectual = ((token.lemma_.casefold() in ASPECTUAL and any(c.dep_ == "xcomp" for c in token.children))
                 or (token.dep_ == "aux" and "Ger" in token.head.morph.get("VerbForm"))
                 or any(c.dep_ in {"xcomp", "aux"} and "Ger" in c.morph.get("VerbForm") for c in token.children))
    return bool(words & (INDEFINITE | ANAPHORIC)) or preposed or "1" in person or "2" in person or aspectual


# Parágrafo que abre com hífen ou travessão e espaço: fala, mesmo quando a marcação de
# diálogo configurada é outra. Fica fora da sequência narrativa.
SPEECH_OPENING = re.compile(r"^\s*[-–—]\s")


def events(block, offset, doc, nlp, sentence_base, trace=None):
    """Predicados finitos da linha principal, com tempo, função, sujeito e posição.

    `trace` (lista, só para depuração): recebe cada forma finita no presente descartada, com o motivo.
    """
    out = []
    if SPEECH_OPENING.match(block.text):
        if trace is not None:
            trace.append({"block": block.number, "token": block.text[:20], "discard_reason": "parágrafo de fala"})
        events.verbal = 0
        return out
    verbal = 0
    for sentence in doc.sents:
        # Só frases com verbo finito ocupam a janela; fragmentos (“Nada.”) não afastam a cena.
        index, before_count = verbal, len(out)
        tokens, base = sentence, offset
        first = next((t for t in sentence if t.is_alpha), None)
        # Segunda leitura com inicial minúscula: “Procura durante…” lido como substantivo.
        # Só quando a leitura original não reconhece a primeira palavra como evento: em minúscula
        # o modelo às vezes acerta (“procura”), às vezes piora (“Fico” vira advérbio).
        if (first is not None and first.text[:1].isupper() and flags(first.text) & FINITE
                and (tempo_recuperado(first) is None or predicate(first).dep_ not in MAIN_LINE)):
            start = first.idx - sentence.start_char
            text = sentence.text
            tokens = nlp(text[:start] + text[start].lower() + text[start + 1:])
            base = offset + sentence.start_char
        question = asks(sentence)
        opener = next((t for t in tokens if t.is_alpha), None)
        for token in tokens:
            tense = tempo_recuperado(token)
            head = predicate(token)
            # “Alguns livros ainda caem”: o modelo pendura o verbo no nome (acl) da raiz nominal.
            # Perífrase em que o modelo pôs o gerúndio ou infinitivo como raiz (“Fico olhando…”): a forma
            # finita que abre a frase é o auxiliar da linha principal.
            periphrasis = (token == opener and head.dep_ != "ROOT" and head.head.dep_ == "ROOT"
                           and set(head.head.morph.get("VerbForm")) & {"Ger", "Inf"})
            main = head.dep_ in MAIN_LINE or para_como_verbo(token) or periphrasis or verbo_unico_da_frase(token) or (head.dep_ == "acl" and head.head.dep_ == "ROOT"
                                              and head.head.pos_ in {"NOUN", "PROPN"}
                                              and not any(c.lower_ in {"que", "onde", "cujo", "cuja"} for c in head.children))
            # O auxiliar finito de uma locução (“estava observando”) dá o tempo ao predicado.
            progressive = token.dep_ == "aux" and set(token.head.morph.get("VerbForm")) & {"Ger", "Inf"}
            if tense is None or (token.dep_ in {"aux", "aux:pass"} and not progressive) or not main:
                if trace is not None and flags(token.text) & PRESENT and flags(token.text) & FINITE and token.is_alpha:
                    reason = ("sem tempo (modelo/léxico)" if tense is None else
                              "auxiliar" if token.dep_ in {"aux", "aux:pass"} else f"fora da linha principal ({head.dep_})")
                    trace.append({"block": block.number, "token": token.text, "pos": token.pos_, "dep": token.dep_,
                                  "lemma": token.lemma_, "tense": tense, "discard_reason": reason})
                continue
            idx = base + token.idx
            out.append({"block": block, "start": idx, "end": idx + len(token.text), "token": token, "tense": tense,
                        "text": block.text[idx:idx + len(token.text)],
                        "function": ("thought" if question else present_function(token)) if tense == "present"
                                    else "narrative_event", "pred": predicate(token),
                        "subject": subject_key(token), "subject_gn": subject_features(token), "anchored": anchored(token),
                        "person": ("".join(token.morph.get("Person")), "".join(token.morph.get("Number"))),
                        "sentence": sentence_base + index})
        if len(out) > before_count or any(certamente_verbo(t) for t in sentence):
            verbal += 1
    events.verbal = verbal
    return out


PRONOUNS = {"ele", "ela", "eles", "elas"}
# Marcadores de encadeamento: reforçam que dois eventos pertencem à mesma cadeia.
SEQUENCE_MARKERS = {"então", "depois", "logo", "imediatamente", "subitamente", "repente", "seguida"}
PERFECT = {"ar": ("ei", "aste", "ou", "amos", "astes", "aram"), "er": ("i", "este", "eu", "emos", "estes", "eram"),
           "ir": ("i", "iste", "iu", "imos", "istes", "iram")}


def perfect_suggestion(token):
    """Pretérito perfeito de um verbo regular, confirmado pelo léxico; senão, nenhum."""
    person, number = token.morph.get("Person"), token.morph.get("Number")
    lemma = token.lemma_.casefold()
    if len(person) != 1 or person[0] not in {"1", "2", "3"} or number not in (["Sing"], ["Plur"]) or lemma[-2:] not in PERFECT:
        return None
    proposal = lemma[:-2] + PERFECT[lemma[-2:]][int(person[0]) - 1 + (3 if number == ["Plur"] else 0)]
    value = flags(proposal)
    return match_case(proposal, token.text) if value & PAST and not value & (PRESENT | FUTURE) else None


def aspect_suggestion(target, anchors):
    """Sugestão no aspecto das âncoras: imperfeito com imperfeito (“observava”), perfeito com
    perfeito (“caiu e se quebrou”). Âncoras mistas ou forma incerta: nenhuma sugestão."""
    aspects = {"Imp" in a["token"].morph.get("Tense") for a in anchors}
    if len(aspects) != 1 or not target.morph.get("Person"):
        return None
    return imperfect_suggestion(target) if aspects.pop() else perfect_suggestion(target)


def surface_coordination(block, offset, doc):
    """Fallback quando a análise sintática se perde (“Mariana segura a bolsa e saiu”): forma que o
    léxico só admite no presente, colada ao sujeito e seguida de objeto, e depois ‘e’/‘mas’ + passado
    sem sujeito próprio, sem pontuação entre os dois. Evidência superficial: confiança média."""
    out = []
    for token in doc:
        lex = flags(token.text)
        if (not token.is_alpha or tempo_recuperado(token) is not None or not lex & FINITE or not lex & PRESENT
                or lex & (PAST | FUTURE) or token.i == 0 or token.i + 2 >= len(doc)):
            continue
        subject, nxt = doc[token.i - 1], doc[token.i + 1]
        # O “sujeito” não pode ser forma verbal (“Virei para…”); ‘para’ só pelo critério próprio.
        if (subject.pos_ not in {"NOUN", "PROPN", "PRON"} or nxt.pos_ != "DET" or flags(subject.text) & FINITE
                or (token.lower_ == "para" and not para_como_verbo(token))):
            continue
        for k in range(token.i + 2, min(len(doc) - 1, token.i + 9)):
            if doc[k].is_punct or doc[k].sent != token.sent:
                break
            if doc[k].lower_ in {"e", "mas"}:
                verb = doc[k + 1]
                if tempo_recuperado(verb) == "past" and not any(c.dep_.startswith("nsubj") and c.i < verb.i for c in verb.children):
                    def ev(t):
                        return {"block": block, "start": offset + t.idx, "end": offset + t.idx + len(t.text), "token": t,
                                "text": block.text[offset + t.idx:offset + t.idx + len(t.text)], "function": "narrative_event"}
                    reason = explicar(f"‘{ev(token)['text']}’ está no presente e ‘{ev(verb)['text']}’ está no passado, "
                                      "parecendo duas ações seguidas da mesma pessoa. A leitura desta frase é incerta; "
                                      "confira se as duas deveriam estar no mesmo tempo.",
                                      "tempo verbal em ações coordenadas")
                    state = {"state": "unknown", "score": {"past": 0.0, "present": 0.0, "other": 0.0}, "verbs": [], "following": [ev(verb)["text"]]}
                    alert = sequence_alert(ev(token), [ev(verb)], "coordinated_tense_mismatch", reason, .75, state, True)
                    alert["temporal_evidence"]["surface"] = True
                    out.append(alert)
                break
    return out


def sequence_alert(event, anchors, subtype, reason, confidence, state, same_subject, severity="probable_error"):
    block, target = event["block"], event["token"]
    result = asdict(finding(block, "Coerência temporal entre orações", "Verificar", event["start"], event["end"],
                            reason, "FONTE Morfossintático · " + subtype))
    result.update(rule="coerencia_temporal", category_code="temporal_consistency", relation=subtype,
                  severity=severity, confidence="alta" if confidence >= .85 else "média" if confidence >= .6 else "baixa",
                  confidence_score=confidence, suggestion=aspect_suggestion(target, anchors),
                  suggestion_kind="possible",
                  related=[evidence(a["block"], a["start"], a["end"]) for a in anchors if a["block"] is block] or
                          [evidence(anchors[0]["block"], anchors[0]["start"], anchors[0]["end"])],
                  temporal_evidence={"anchor": anchors[0]["text"], "anchor_form": "past",
                                     "target": event["text"], "target_form": "present",
                                     "function": event["function"], "local_state": state["state"],
                                     "local_tense_score": state["score"],
                                     "previous_narrative_verbs": state["verbs"],
                                     "following_narrative_verbs": state.get("following", []),
                                     "same_scene": True, "same_subject": same_subject})
    return result


def local_state(before):
    """Estado temporal local a partir dos últimos verbos da janela (até 8)."""
    recent = before[-8:]
    past = sum(e["tense"] == "past" for e in recent)
    present = sum(e["tense"] == "present" and e["function"] == "narrative_event" for e in recent)
    total = max(1, len(recent))
    score = {"past": round(past / total, 2), "present": round(present / total, 2),
             "other": round(1 - (past + present) / total, 2)}
    # Passado firme: dois ou mais passados (três quartos da janela) ou um só sem nenhum presente,
    # e o último verbo no passado.
    firm = recent[-1]["tense"] == "past" and ((past >= 2 and past / total >= .75) or (past == 1 and present == 0))
    return {"state": "past" if firm else "mixed", "score": score,
            "verbs": [e["text"] for e in recent if e["tense"] == "past"][-4:]}


def sequence(evts, trace=None):
    """Estado narrativo local: presente que é evento numa cena narrada no passado.

    Janela de até 4 frases antes (atravessa parágrafos; título, separador de cena e
    parágrafos só de diálogo interrompem) e 2 depois, que confirmam mas não são exigidas.
    Precedência, um alerta por verbo: coordenação > passado-presente-passado > mesmo
    sujeito > cena. Exige `narrative_event`; sem sujeito compatível, só com âncora na cena
    e confiança média.
    """
    out = []
    def note(event, reason, state=None):
        if trace is not None:
            trace.append({"block": event["block"].number, "token": event["text"], "lemma": event["token"].lemma_,
                          "tense": event["tense"], "function": event["function"], "subject": event["subject"],
                          "local_state": (state or {}).get("state"), "local_tense_score": (state or {}).get("score"),
                          "previous_verbs": (state or {}).get("verbs"), "discard_reason": reason})
    for i, event in enumerate(evts):
        if event["tense"] != "present":
            continue
        if event["function"] != "narrative_event":
            note(event, f"função {event['function']}")
            continue
        before = [e for e in evts[:i] if event["sentence"] - e["sentence"] <= 4]
        after = [e for e in evts[i + 1:] if e["sentence"] - event["sentence"] <= 2]
        earlier = [e for e in before if e["sentence"] < event["sentence"]]
        state = local_state(earlier) if earlier else {"state": "unknown", "score": {"past": 0.0, "present": 0.0, "other": 0.0}, "verbs": []}
        token = event["token"]
        # Coordenação na mesma oração: “pega … e abriu”, “puxou … e solta”.
        pred = event["pred"]
        # Coordenação entre predicados (“estava observando…, mas vira”): o tempo vem do verbo finito
        # da locução. Uma conjunção sozinha não basta; a relação conj precisa estar na análise.
        coordinated = [e for e in before + after if e["sentence"] == event["sentence"] and e["tense"] == "past"
                       and ((pred.dep_ == "conj" and e["pred"] == pred.head)
                            or (e["pred"].dep_ == "conj" and e["pred"].head == pred))]
        # O coordenado sem sujeito próprio herda o do núcleo: compara o sujeito herdado,
        # não a pessoa da morfologia do modelo (que erra na 1ª pessoa sem sujeito).
        linked = [e for e in coordinated if e["subject"] == event["subject"]]
        if linked:
            reason = explicar(f"‘{event['text']}’ está no presente e ‘{linked[0]['text']}’ está no passado, mas são duas "
                              "ações seguidas da mesma pessoa. Provavelmente deveriam estar no mesmo tempo.",
                              "tempo verbal em ações coordenadas")
            out.append(sequence_alert(event, linked, "coordinated_tense_mismatch", reason, .88, state, True))
            continue
        if coordinated:
            reason = explicar(f"‘{event['text']}’ está no presente e ‘{coordinated[0]['text']}’ está no passado, no mesmo "
                              "momento da história, com pessoas diferentes. Confira se deveriam estar no mesmo tempo.",
                              "tempo verbal em orações coordenadas")
            out.append(sequence_alert(event, coordinated, "coordinated_tense_mismatch", reason, .72, state, False))
            continue
        previous = before[-1] if before else None
        following = after[0] if after else None
        if (previous and following and previous["tense"] == "past" and following["tense"] == "past"
                and previous["sentence"] < event["sentence"] < following["sentence"]
                and (compatible(previous, event) or compatible(following, event))):
            reason = explicar(f"‘{event['text']}’ está no presente, mas fica entre ‘{previous['text']}’ e "
                              f"‘{following['text']}’, que estão no passado, na mesma cena e sem ser fala ou pensamento. "
                              "Provavelmente deveria estar no passado também.", "tempo verbal na sequência narrativa")
            out.append(sequence_alert(event, [previous, following], "past_present_past", reason, .9, state,
                                      compatible(previous, event)))
            continue
        if state["state"] != "past":
            # Presente → passado: a frase seguinte volta ao passado, com o mesmo sujeito (ou elíptico)
            # ou com marcador de sequência (“Então bateu”). Confiança média: só um lado confirma.
            nxt = following if following and following["sentence"] == event["sentence"] + 1 else None
            marker = nxt is not None and any(t.lower_ in SEQUENCE_MARKERS for t in nxt["token"].sent[:3])
            if nxt and nxt["tense"] == "past" and (compatible(nxt, event) or marker) and (event["anchored"] or event["subject"] is None or marker or compatible(nxt, event)):
                reason = explicar(f"‘{event['text']}’ está no presente, mas a ação seguinte, ‘{nxt['text']}’, está no "
                                  "passado. Confira se a sequência deveria estar toda no mesmo tempo.",
                                  "tempo verbal na sequência narrativa")
                # Evidência real: estado anterior (ou “unknown”) e o passado que confirma depois.
                out.append(sequence_alert(event, [nxt], "local_narrative_tense_shift", reason, .72,
                                          dict(state, following=[nxt["text"]]), compatible(nxt, event)))
            else:
                note(event, "estado local não é passado e não há passado logo depois", state)
            continue
        # Presente que continua em frases seguintes pode ser mudança deliberada de plano: reduz.
        continues = any(e["tense"] == "present" and e["sentence"] > event["sentence"] for e in after)
        # Cadeia do mesmo sujeito: os passados mais recentes com sujeito consistente (um só
        # sujeito explícito, ou elípticos de mesma pessoa), lidos de trás para frente.
        # Pronomes de 3ª pessoa retomam o sujeito e não contam como outro sujeito.
        chain, subjects = [], {event["subject"]} - {None} - PRONOUNS
        pronouns = [event] if event["subject"] in PRONOUNS else []
        for e in reversed(earlier):
            named = {e["subject"]} - {None} - PRONOUNS
            # O pronome só retoma um nome de gênero e número compatíveis (“ela” não retoma “o vento”).
            clash = named and any(x != y and x and y for p in pronouns for x, y in zip(p["subject_gn"], e["subject_gn"]))
            if e["tense"] != "past" or not compatible(e, event) or len(subjects | named) > 1 or clash:
                break
            subjects |= named
            if e["subject"] in PRONOUNS:
                pronouns.append(e)
            chain.insert(0, e)
            if len(chain) == 3:
                break
        adjacent = bool(chain) and chain[-1]["sentence"] >= event["sentence"] - 2
        # Um só passado basta quando o presente sem sujeito continua a ação imediatamente anterior.
        single = len(chain) == 1 and event["subject"] is None and adjacent
        if len(chain) >= 2 or single:
            explicit = event["subject"] is not None
            confidence = (.75 if single else .85 if explicit or adjacent else .75) - (.15 if continues else 0)
            reason = explicar(f"As ações anteriores da mesma pessoa estão no passado ({', '.join(e['text'] for e in chain)}), "
                              f"e ‘{event['text']}’ passa para o presente sem nada que indique a mudança. Confira se foi "
                              "intencional.", "tempo verbal na sequência narrativa")
            out.append(sequence_alert(event, chain, "same_subject_narrative_shift", reason, confidence, state, True))
            continue
        chain = earlier[-3:]
        # Outro sujeito na mesma cena: só com âncora na cena (entidade nova, retomada, 1ª pessoa,
        # perífrase aspectual). Sem âncora, pode ser comentário ou verdade geral sem marca.
        if not event["anchored"] or chain[-1]["sentence"] < event["sentence"] - 2:
            note(event, "outro sujeito sem âncora na cena" if not event["anchored"] else "último passado distante", state)
        if event["anchored"] and chain[-1]["sentence"] >= event["sentence"] - 2:
            reason = explicar(f"A cena vem sendo contada no passado ({', '.join(state['verbs'])}), e ‘{event['text']}’, "
                              "uma ação de outra pessoa na mesma cena, está no presente. Confira se foi intencional.",
                              "tempo verbal na sequência narrativa")
            out.append(sequence_alert(event, chain, "local_narrative_tense_shift", reason, .7 - (.1 if continues else 0),
                                      state, False))
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
            reason = explicar(f"Numa história contada no passado, aqui pode caber ‘{proposals[0]}’, com acento (como em "
                              f"‘caía’, ‘saía’). Sem acento, ‘{token.text}’ é outra forma do verbo. Confira qual você quis "
                              "dizer.", "acentuação de verbos no imperfeito")
            result = asdict(finding(block, "Acentuação verbal no contexto", "Verificar", offset + token.idx,
                                    offset + token.idx + len(token.text), reason,
                                    "FONTE Morfossintático · acentuacao_contextual"))
            result.update(rule="acentuacao_contextual", category_code="contextual_accentuation",
                          severity="probable_error", confidence="média", confidence_score=.8,
                          suggestion=proposals[0], related=[evidence(block, offset + s.idx,
                              offset + s.idx + len(s.text)) for s in subjects])
            out.append(result)
    return out


def analyze(blocks, nlp, settings, expected_tense="auto", trace=None):
    roles = classify(blocks, settings)
    jobs = []
    allowed = set(settings["tense_scopes"] if settings["rules"]["coerencia_temporal"] else [])
    if settings["rules"]["acentuacao_contextual"]:
        allowed.add("narracao")
    for block, labels in zip(blocks, roles):
        if lista_ou_rotulo(block.text):
            continue
        for start, end, role in spans(labels, allowed):
            if block.text[start:end].strip():
                jobs.append((block, start, end, role))
    out, evts, sentences, last_block = [], [], 0, None
    headings = [b.number for b in blocks if b.heading]
    breaks = [b.number for b in blocks if b.text.strip() and SCENE_BREAK.match(b.text.strip())]
    for (block, start, end, role), doc in zip(jobs, nlp.pipe((b.text[s:e] for b, s, e, _ in jobs), batch_size=32)):
        if settings["rules"]["coerencia_temporal"] and role in settings["tense_scopes"]:
            out.extend(relations(block, start, doc))
            out.extend(conditionals(block, start, doc))
            out.extend(modality(block, start, doc))
            # A sequência só considera a narração; um título (capítulo) recomeça a cena.
            if role == "narracao" and expected_tense == "passado":
                # O próprio separador (“* * *”) encerra a cena.
                if block.number in breaks:
                    out.extend(sequence(evts, trace)); evts, last_block = [], None
                    continue
                if last_block is not None and any(last_block.number < h < block.number for h in headings + breaks):
                    out.extend(sequence(evts, trace)); evts = []
                if last_block is not None and last_block is not block:
                    # Mudança de parágrafo pesa uma frase; fala intercalada (parágrafo sem narração)
                    # pesa uma frase por parágrafo: a cena continua numa troca curta, não numa longa.
                    sentences += 1 + max(0, block.number - last_block.number - 1)
                evts.extend(events(block, start, doc, nlp, sentences, trace))
                out.extend(surface_coordination(block, start, doc))
                sentences += events.verbal; last_block = block
        if settings["rules"]["acentuacao_contextual"] and role == "narracao":
            out.extend(accents(block, start, doc, expected_tense))
    out.extend(sequence(evts, trace))
    # Um alerta por verbo: o mais específico prevalece (PRECEDENCE); relações antigas só ficam
    # onde nenhum detector da lista apontou o mesmo trecho.
    rank = {name: i for i, name in enumerate(PRECEDENCE)}
    best = {}
    for f in out:
        key = (f["paragraph"], f["start"], f["end"])
        if key not in best or rank.get(f.get("relation"), len(rank)) < rank.get(best[key].get("relation"), len(rank)):
            best[key] = f
    return [f for f in out if best[(f["paragraph"], f["start"], f["end"])] is f]
