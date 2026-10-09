"""Regras explicáveis. Os resultados são candidatos, nunca vereditos."""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import re

from .reader import Block
from .lexicon import FINITE, FUTURE, NONFINITE, NONVERB, PAST, PRESENT, flags
from .verbo import RELATIVOS, certamente_verbo, model_finite, pode_ser_verbo
from .tempo import DEPOIS_DE_PARAR, passado_so_no_lexico, tempo_narrativo
from .segments import FECHA_ASPAS, marcar_travessoes, percorrer_aspas
from .elocucao import verbo_de_fala

# Depois destas palavras “para” não pode ser preposição: é o verbo parar (“o braço para no ar”).


def para_verbal(sent):
    return any(t.lower_ == "para" and t.i + 1 < len(t.doc) and t.nbor().lower_ in DEPOIS_DE_PARAR
               and t.i > sent.start for t in sent)


# Preposição de base de cada forma (simples ou contraída), para comparar complementos.
_DEMONSTRATIVOS = "o a os as um uma uns umas aquele aquela aqueles aquelas aquilo este esta estes estas isto esse essa esses essas isso ele ela eles elas".split()
PREPOSICOES = {**{"n" + d: "em" for d in _DEMONSTRATIVOS}, **{"d" + d: "de" for d in _DEMONSTRATIVOS},
               **{"à" + d[1:]: "a" for d in _DEMONSTRATIVOS if d.startswith("a") and len(d) > 2},
               "ao": "a", "aos": "a", "à": "a", "às": "a", "pelo": "por", "pela": "por", "pelos": "por",
               "pelas": "por", **{p: p for p in "em de por com para sem sobre contra entre até desde".split()}}


def elipse_de_complemento(sent, previous):
    """Fragmento que é só um complemento preposicionado retomando o verbo da frase anterior.

    “Pensei na sala. Naquela pessoa…” → “[pensei] naquela pessoa”. Exige a mesma
    preposição depois de um verbo finito na frase anterior e nenhuma vírgula no
    fragmento (adjunto anteposto + núcleo nominal não é retomada).
    """
    words = [t for t in sent if not t.is_space and not t.is_punct]
    if previous is None or not words or any(t.text == "," for t in sent):
        return False
    base = PREPOSICOES.get(words[0].lower_)
    if base is None:
        return False
    verb = next((t for t in previous if certamente_verbo(t)), None)
    return verb is not None and any(PREPOSICOES.get(t.lower_) == base and t.i > verb.i for t in previous)


RETICENCIAS = re.compile(r"…|\.\.\.")


def fragmento_suspenso(sent, limite=5):
    """Pensamento suspenso por reticências internas e concluído por expressão nominal curta.

    “Depois do exame… nenhuma resposta.” A frase toda já não tem verbo finito; o
    que vem depois das últimas reticências tem até `limite` palavras.
    """
    text = sent.text.rstrip().rstrip(".!?…")
    marks = list(RETICENCIAS.finditer(text))
    if not marks:
        return False
    words = re.findall(r"[^\W\d_]+", text[marks[-1].end():])
    return 0 < len(words) <= limite


# Abertura que contrapõe ou retoma o que veio antes (“Por outro lado, uma saída lenta.”): frase
# nominal deliberada, como as de uma enumeração (“Pedras soltas, galhos secos, lama.”).
OPOSICAO = re.compile(r"(?:(?:por|de)\s+(?:um|outro)\s+lado|em\s+compensação|ao\s+contrário|em\s+contrapartida)\b", re.I)


def fragmento_deliberado(sent, previous=None):
    """Oposição, enumeração ou paralelismo com a frase anterior: sinais de fragmento de estilo."""
    text = sent.text.strip()
    if OPOSICAO.match(text):
        return True
    # Enumeração: três itens nominais ou mais, separados por vírgula ou pelo ‘e’ final. Advérbio ou
    # conectivo isolado entre vírgulas (“Hoje, porém, …”) não é item.
    itens, atual = [], []
    for t in sent:
        if t.text == "," or t.lower_ == "e":
            itens.append(atual); atual = []
        elif not t.is_punct:
            atual.append(t)
    itens.append(atual)
    if sum(1 for item in itens if any(t.pos_ in {"NOUN", "PROPN", "ADJ"} for t in item)) >= 3:
        return True
    # Paralelismo: abre com as mesmas duas palavras da frase anterior (“Um corredor… Um silêncio…”
    # não basta; “Por um lado… Por um momento…” sim).
    if previous is not None:
        mine = [t.lower_ for t in sent if t.is_alpha][:2]
        theirs = [t.lower_ for t in previous if t.is_alpha][:2]
        if len(mine) == 2 and mine == theirs:
            return True
    return False


# Conjunções que abrem oração subordinada: sem verbo finito, falta a oração.
SUBORDINANTES = {"quando", "enquanto", "porque", "embora", "conquanto", "caso", "porquanto"}
# “Enquanto isso, …”, “quando muito”: locuções adverbiais, não subordinação.
LOCUCAO_ADVERBIAL = {"isso", "isto", "aquilo", "assim", "muito", "pouco", "possível", "necessário"}
ARTIGOS = {"o", "a", "os", "as", "um", "uma", "uns", "umas"}
# Palavras que pedem continuação: fragmento terminado nelas foi cortado.
PEDEM_CONTINUACAO = set(PREPOSICOES) | ARTIGOS | {"e", "ou", "mas", "que", "se", "nem"}
# Aberturas de oração subordinada adverbial, das mais longas às mais curtas.
ABERTURAS_SUBORDINADAS = ("apesar de que", "assim que", "antes que", "depois que", "desde que", "logo que",
                          "sempre que", "a menos que", "quando", "enquanto", "embora", "porque", "conquanto",
                          "porquanto", "caso", "conforme", "se")
# Palavras que abrem orações dependentes: relativos e subordinantes.
ABREM_ORACAO = RELATIVOS | SUBORDINANTES | {"quem", "qual", "quais", "se", "como", "conforme"}


def abertura_subordinada(sent):
    """Subordinante que abre a frase (“Quando”, “Assim que”), com a grafia do texto; senão None."""
    words = [t for t in sent if t.is_alpha]
    lowered = [t.lower_ for t in words]
    for phrase in ABERTURAS_SUBORDINADAS:
        parts = phrase.split()
        if lowered[:len(parts)] == parts and len(words) > len(parts):
            first, last = words[0], words[len(parts) - 1]
            if len(parts) == 1 and lowered[1] in LOCUCAO_ADVERBIAL:
                return None
            return sent.doc.text[first.idx:last.idx + len(last.text)]
    return None


def fecha_oracao_dependente(verb):
    """O verbo é o primeiro da oração aberta por um relativo ou subordinante anterior (“o porão em
    que dormem”, “a casa onde moram”): pertence a essa oração, não ao predicado que vem depois."""
    for token in reversed(list(verb.sent[:verb.i - verb.sent.start])):
        if pode_ser_verbo(token):
            return False
        if token.lower_ in ABREM_ORACAO or "Rel" in token.morph.get("PronType") or token.dep_ == "mark":
            return True
    return False




def aspas_de_destaque(text, closing, nlp):
    """Aspas de destaque, ironia ou termo especial, não fala: até três palavras sem verbo finito nem
    pontuação interna, abertas no meio da oração (depois de uma palavra, não de pontuação final,
    dois-pontos ou travessão). Aspas que vêm de outro parágrafo continuam tratadas como fala."""
    opening = text.rfind(FECHA_ASPAS.get(text[closing], ""), 0, closing)
    if opening < 0:
        return False
    content = text[opening + 1:closing].strip()
    before = text[:opening].rstrip()
    words = re.findall(r"[^\W\d_]+", content)
    if (not before or before[-1] in ".!?…:—–\"“”«»" or not 0 < len(words) <= 3
            or re.search(r"[,.;:!?…]", content)):
        return False
    return not any(pode_ser_verbo(t) for t in nlp(content))


def _concorda(palavra, token):
    """Gênero e número da terminação de `palavra` compatíveis com o referente `token`."""
    word, number = palavra.casefold(), token.morph.get("Number")
    plural = word.endswith("s")
    if number and plural != ("Plur" in number):
        return False
    if not number and plural != token.lower_.endswith("s"):
        return False
    gender = token.morph.get("Gender")
    raiz = word[:-1] if plural else word
    if raiz.endswith("a"):
        return not gender or "Fem" in gender
    if raiz.endswith("o"):
        return not gender or "Masc" in gender
    return True


def _nucleo_nominal(words):
    """Artigo fora de sintagma preposicionado (“uma longa fila”, “o canto dos pássaros”).

    Determinantes antes do artigo não contam: “por toda a casa” continua preposicionado.
    """
    for i, w in enumerate(words):
        if w.lower_ not in ARTIGOS:
            continue
        j = i - 1
        while j >= 0 and words[j].pos_ == "DET" and words[j].lower_ not in ARTIGOS:
            j -= 1
        if j < 0 or words[j].lower_ not in PREPOSICOES:
            return True
    return False


def classificar_fragmento(sent, previous=None, following=None):
    """Classe de um segmento sem verbo finito, lido com a frase anterior e a seguinte.

    Só `likely_incomplete_clause` (subordinante ou relativo sem oração, ou corte em
    palavra que pede continuação) indica estrutura incompleta. Adjetivo que concorda
    com referente da frase anterior é predicação elíptica (“[as chaves eram]
    enferrujadas”); advérbio sem núcleo nominal continua a ação anterior (“primeiro
    devagar, depois mais depressa”); frase nominal com núcleo sem artigo ou vizinha de
    outro fragmento é descrição fragmentada. O resto fica `uncertain`.
    """
    if any(certamente_verbo(t) for t in sent):
        return "complete_clause"
    words = [t for t in sent if t.is_alpha]
    if not words:
        return "uncertain"
    first, second = words[0].lower_, words[1].lower_ if len(words) > 1 else ""
    ultima = sent.text.rstrip()
    if ((first in SUBORDINANTES and second not in LOCUCAO_ADVERBIAL)
            or any(w.lower_ in RELATIVOS and words[i - 1].pos_ in {"NOUN", "PROPN", "PRON"}
                   for i, w in enumerate(words) if i > 0)
            or (words[-1].lower_ in PEDEM_CONTINUACAO and not ultima.endswith(("…", "...")))):
        return "likely_incomplete_clause"
    if fragmento_deliberado(sent, previous):
        return "likely_literary_fragment"
    nucleo = _nucleo_nominal(words)
    abre_adverbio = (words[0].pos_ == "ADV" or first.endswith("mente")
                     or (first in PREPOSICOES and words[1:2] and words[1].pos_ in {"PRON", "ADV", "VERB"}))
    if abre_adverbio and not nucleo:
        return "likely_adverbial_fragment"
    referentes = [t for t in (previous or []) if t.pos_ in {"NOUN", "PRON"} and t.is_alpha]
    nua = first not in PREPOSICOES and first not in ARTIGOS and words[0].pos_ in {"ADJ", "NOUN", "PROPN", "VERB"}
    if nua and not nucleo and any(_concorda(words[0].text, r) for r in referentes):
        return "likely_elliptical_predication"
    # Frase nominal com núcleo no singular sem artigo (“Silêncio por toda a casa”): marca de
    # estilo. No plural (“Minúsculas diante do…”) depende de um referente que concorde.
    if nua and not nucleo and not first.endswith("s"):
        return "likely_literary_fragment"
    vizinhos = [s for s in (previous, following) if s is not None]
    if any(not any(certamente_verbo(t) for t in s) for s in vizinhos):
        return "likely_literary_fragment"
    return "uncertain"


@dataclass
class Finding:
    id: str
    category: str
    priority: str
    paragraph: int
    chapter: str
    text: str
    start: int
    end: int
    reason: str
    source: str = "Regras FONTE + spaCy + PortiLexicon-UD"


def lista_ou_rotulo(texto):
    """Linha sem pontuação final só com palavras de inicial maiúscula e números (“Equipe 2 Ana Rui”,
    “Parte 3”): lista ou rótulo, não frase da narração."""
    partes = texto.split()
    return (len(partes) >= 2 and texto.rstrip()[-1:].isalnum()
            and all(p[0].isupper() or p[0].isdigit() for p in partes))


# Regra e código de categoria de cada alerta deste módulo. O código é o mesmo que a padronização
# deduzia antes de existir `rule` aqui; ele é também a classe estatística (política e medição).
REGRA_POR_CATEGORIA = {
    "Tempo verbal": {"rule": "tempo_verbal", "category_code": "narrative_tense"},
    "Estrutura da frase": {"rule": "estrutura", "category_code": "sentence_structure"},
    "Resíduo de edição": {"rule": "residuo_edicao", "category_code": "editorial_review"},
    "Pontuação de diálogo": {"rule": "pontuacao_dialogo", "category_code": "dialogue_punctuation"},
    "Palavra repetida": {"rule": "palavra_consecutiva", "category_code": "repetition"},
}


def explicar(texto, termo):
    """Explicação em linguagem do dia a dia e, numa linha final, o nome gramatical para quem quiser
    pesquisar. Termos técnicos ficam só nessa linha."""
    return f"{texto}\n\nNa gramática: {termo}."


def finding(block, category, priority, start, end, reason, source="Regras FONTE + spaCy + PortiLexicon-UD"):
    # Mantém a identidade dos alertas antigos que continuam no mesmo trecho.
    key_source = source.replace(" + PortiLexicon-UD", "")
    key = f"{block.number}:{category}:{key_source}:{start}:{end}:{block.text}"
    return Finding(hashlib.sha256(key.encode()).hexdigest()[:16], category,
                   priority, block.number, block.chapter, block.text,
                   start, end, reason, source)


def narrative_masks(blocks, protect_italics=True):
    """Leitura antiga da narração, com as peças de `segments`. Mantém comprimento/offsets.

    Diferente de `segments.classify`, de propósito (registrado no plano da estabilização): as aspas
    contam sempre como fala; a aspa que reabre a mesma fala no início de um parágrafo continua a
    fala; o travessão só abre fala no início do parágrafo, sem hífen de diálogo e sem leitura por
    linha. Devolve as máscaras (narração visível), as posições das aspas que fecham e os avisos."""
    aspas, warnings = percorrer_aspas(blocks, repete_abertura=True)
    masks, closing_positions = [], []
    for block, (marcas, fechamentos) in zip(blocks, aspas):
        text = block.text
        if block.heading:
            masks.append(" " * len(text))
            closing_positions.append([])
            continue
        roles = ['narracao' if marca is None else 'fala' for marca in marcas]
        marcar_travessoes(text, roles, por_linha=False, hifen=False)
        if protect_italics:
            for start, end in block.italic:
                roles[start:end] = ['italico'] * (end - start)
        masks.append("".join(c if role == 'narracao' else " " for c, role in zip(text, roles)))
        closing_positions.append(fechamentos)
    return masks, closing_positions, warnings


def tense_contradiction(counts, tense, minimum=20, share=.7):
    """Contagem de verbos da narração que contradiz o tempo escolhido pelo autor.

    Só indica: os alertas continuam medidos pelo tempo escolhido. Exige ao menos `minimum`
    verbos do outro tempo e `share` do total com tempo identificado (o mesmo critério do
    modo automático); narração mista ou curta não sustenta a conclusão."""
    if tense not in ("passado", "presente"):
        return None
    other = "presente" if tense == "passado" else "passado"
    past, present = counts.get("passado", 0), counts.get("presente", 0)
    found = counts.get(other, 0)
    if found < minimum or found / max(1, past + present) < share:
        return None
    return {"escolhido": tense, "predominante": other, "passado": past, "presente": present}


def analyze(blocks: list[Block], nlp, tense="auto", protect_italics=True, min_words=5, masks_override=None, enabled_rules=None):
    masks, closings, warnings = narrative_masks(blocks, protect_italics)
    if masks_override is not None:
        masks = masks_override
    active = set(enabled_rules) if enabled_rules is not None else {'tempo_verbal','estrutura','residuo_edicao','pontuacao_dialogo','palavra_consecutiva'}
    docs = list(nlp.pipe(masks, batch_size=32))
    counts = Counter(tempo_narrativo(t) for d in docs for t in d)
    counts.pop(None, None)
    if "tempo_verbal" not in active:
        expected = None
    elif tense == "auto":
        past, present = counts["passado"], counts["presente"]
        if max(past, present) >= 3 and max(past, present) / max(1, past+present) >= .7:
            expected = "passado" if past > present else "presente"
        else:
            expected = None
            warnings.append("Tempo predominante inconclusivo: a regra de tempo verbal não foi aplicada. Use --tempo passado ou --tempo presente se conhecer a escolha narrativa.")
    else:
        expected = tense
    results = []
    fragment_classes, low_confidence, extras = Counter(), set(), {}
    for block, doc, closed, mask in zip(blocks, docs, closings, masks):
        if block.heading or lista_ou_rotulo(block.text):
            continue
        for token in doc:
            observed = tempo_narrativo(token)
            if observed is None and expected == "presente" and passado_so_no_lexico(token):
                observed = "passado"
            if "tempo_verbal" in active and expected and observed and observed != expected:
                from .temporal import legitimate_present, past_plane, present_function
                if expected == "passado" and legitimate_present(token):
                    continue
                # Narração no presente: anterioridade (mais-que-perfeito, perfeito em oração dependente,
                # ‘devia’ + infinitivo) é outro plano temporal, não mudança da cena.
                plane = past_plane(token) if expected == "presente" else None
                if plane == "anterior":
                    continue
                reason = explicar(f"A história está sendo contada no {expected}, mas ‘{token.text}’ está no {observed}. "
                                  "Pode ser um erro ou uma mudança proposital: pensamento, fala, comentário do narrador ou "
                                  "algo que vale sempre (‘a água ferve a cem graus’) podem usar outro tempo. Confira.",
                                  "tempo verbal da narração")
                if plane == "incerto":
                    reason = explicar(f"‘{token.text}’ está no passado (forma ‘…ava’, ‘…ia’), numa história contada no "
                                      "presente. Pode ser algo que já era assim antes da cena, o que está certo, ou algo "
                                      "acontecendo agora, que pediria o presente. Confira.",
                                      "pretérito imperfeito em oração dependente ou com valor modal")
                elapsed = re.match(r"há\s+(?:\d+|[^\W\d_]+)\s+(?:segundos?|minutos?|horas?|dias?|semanas?|meses|anos?)\b",
                                   block.text[token.idx:], re.I)
                if expected == "passado" and elapsed:
                    reason = explicar(f"‘{elapsed[0]}’ conta o tempo a partir de hoje. Numa história contada no passado, "
                                      "costuma-se usar ‘havia’ (‘havia dois anos’) ou ‘… antes’. Pode ser intencional, como "
                                      "a voz de quem narra.", "há / havia em expressões de tempo")
                function = present_function(token) if expected == "passado" and observed == "presente" else None
                # Marcador discursivo (“Tá.”, “Tá bom.”): resposta curta, não verbo da narração.
                if function == "discourse_marker":
                    continue
                item = finding(block, "Tempo verbal", "Verificar", token.idx, token.idx+len(token.text), reason)
                # Presente que não é evento narrativo (estado, verdade geral, pensamento, comentário)
                # continua visível, com confiança baixa; a sequência temporal trata os eventos.
                if (function is not None and function not in {"narrative_event", "transient_state"}) or plane == "incerto":
                    low_confidence.add(item.id)
                results.append(item)
        previous = None
        sents = list(doc.sents)
        for index, sent in enumerate(sents):
            words = [t for t in sent if t.is_alpha]
            before, previous = previous, sent
            if ("estrutura" in active and len(words) >= min_words and not any(pode_ser_verbo(t) for t in sent)
                    and not para_verbal(sent) and not elipse_de_complemento(sent, before)
                    and not fragmento_suspenso(sent)):
                # Segunda leitura só dos candidatos, sem espaços da máscara e
                # com inicial minúscula. Não modifica o texto nem seus offsets.
                clean = sent.text.strip()
                if clean:
                    second = nlp(clean[0].lower() + clean[1:])
                    if any(pode_ser_verbo(t) for t in second):
                        continue
                following = sents[index + 1] if index + 1 < len(sents) else None
                classe = classificar_fragmento(sent, before, following)
                fragment_classes[classe] += 1
                if classe not in {"likely_incomplete_clause", "uncertain"}:
                    continue
                start, end = words[0].idx, words[-1].idx + len(words[-1].text)
                if classe == "likely_incomplete_clause":
                    reason = explicar(f"O trecho ‘{block.text[start:end]}’ parece incompleto: não tem verbo, e começa com "
                                      "uma palavra que pede continuação (como ‘quando’ ou ‘que’) ou termina em uma. Confira "
                                      "se faltou parte do texto.", "oração incompleta")
                else:
                    reason = explicar(f"O trecho ‘{block.text[start:end]}’ não tem verbo. Em literatura, frases assim podem "
                                      "ser de propósito. Verifique apenas se uma oração completa era pretendida.",
                                      "frase nominal (sem verbo conjugado)")
                item = finding(block, "Estrutura da frase", "Explorar", start, end, reason)
                if classe == "uncertain":
                    low_confidence.add(item.id)
                results.append(item)
            # Oração subordinada sem principal (“Quando chegou ao quarto depois de falar com todos.”,
            # “O homem que estava parado na porta enquanto todos conversavam.”): tem verbo finito,
            # mas todos estão em orações dependentes. Confiança baixa: o fragmento pode ser estilo.
            # Nome seguido só de relativa (“Uma ave que nunca tinha visto.”) fica de fora: é
            # fragmento nominal comum na prosa, e o modelo costuma engolir a principal na relativa.
            abertura = abertura_subordinada(sent)
            if ("estrutura" in active and len(words) >= (3 if abertura else 6)
                    and sent.text.rstrip().endswith(".")):
                root = sent.root
                opener = words[0].lower_
                verbs = [t for t in sent if certamente_verbo(t)]
                # O modelo erra a árvore nessas frases; a forma confirma. Abertura por subordinante:
                # sem vírgula e com um só verbo finito (“Quando o trem chegou, a menina…” tem a
                # principal depois da vírgula). O subordinante precisa estar ligado à raiz.
                marks = {c.lower_ for c in root.children if c.dep_ in {"mark", "advmod"}}
                subordinate_root = (abertura is not None and certamente_verbo(root) and len(verbs) == 1
                                    and "," not in sent.text
                                    and bool(set(abertura.casefold().split()) & marks))
                # O modelo às vezes pendura no verbo da subordinada o nome que a antecede (“O homem
                # que … enquanto todos conversavam”): dois sujeitos, o primeiro antes da conjunção.
                conj = next((c for c in root.children if c.dep_ in {"mark", "advmod"} and c.lower_ in SUBORDINANTES
                             and c.i < root.i), None) if certamente_verbo(root) else None
                hanging = conj is not None and len([c for c in root.children if c.dep_ == "nsubj"]) >= 2 and any(
                    c.dep_ == "nsubj" and c.pos_ in {"NOUN", "PROPN"} and c.i < conj.i for c in root.children)
                if verbs and (subordinate_root or hanging):
                    start, end = words[0].idx, words[-1].idx + len(words[-1].text)
                    if subordinate_root:
                        reason = explicar(f"O trecho iniciado por ‘{abertura}’ prepara outra parte da frase, que não aparece "
                                          "(como em ‘Quando as luzes se apagam, todos se calam’). Em literatura isso pode ser "
                                          "de propósito; confira se essa parte faltou.", "oração subordinada sem a principal")
                    else:
                        reason = explicar(f"O trecho ‘{block.text[start:end]}’ tem verbo, mas só nas partes que dependem de "
                                          "outra (‘que…’, ‘enquanto…’); falta a parte principal. Pode ser de propósito; confira "
                                          "se a frase foi cortada ou deveria se ligar à anterior.",
                                          "oração subordinada sem a principal")
                    item = finding(block, "Estrutura da frase", "Explorar", start, end, reason)
                    low_confidence.add(item.id)
                    extras[item.id] = {"category_code": "incomplete_subordinate_clause"}
                    fragment_classes["subordinate_without_main"] += 1
                    results.append(item)
        for position in (closed if "pontuacao_dialogo" in active else []):
            tail = block.text[position+1:]
            match = re.match(r"\s*,\s*", tail)
            if not match or aspas_de_destaque(block.text, position, nlp):
                continue
            start = position+1+match.end()
            remaining = [t for t in doc if t.idx >= start and not t.is_space]
            first_verb = next((t for t in remaining[:18] if certamente_verbo(t)), None)
            if first_verb is not None and not verbo_de_fala(first_verb):
                results.append(finding(block, "Pontuação de diálogo", "Verificar",
                    position, first_verb.idx+len(first_verb.text),
                    explicar("Depois das aspas e da vírgula, esperava-se um verbo de fala ou pensamento (‘disse’, "
                             "‘pensou’), mas vem outra ação. Se a fala terminou ali, a ação costuma começar uma frase "
                             "nova. Confira.", "pontuação de diálogo")))
        for match in re.finditer(r"\b([^\W\d_]+)(\s+)\1\b", mask if "palavra_consecutiva" in active else "", re.I):
            # Onomatopeia reduplicada (“au au”, “blá blá”): forma fora do léxico.
            if not flags(match[1]):
                continue
            results.append(finding(block, "Palavra repetida", "Verificar", match.start(), match.end(),
                explicar("A mesma palavra aparece duas vezes seguidas. Confira se é de propósito ou digitação.",
                         "palavra repetida"), "Regras FONTE"))
        # Resíduo de edição: dois auxiliares conjugados seguidos no mesmo predicado (“tinha havia
        # percebido”). Na locução verbal só o primeiro é finito; os outros ficam no infinitivo,
        # gerúndio ou particípio (“tinha sido”, “vai ter”, “estava sendo”).
        for head in (doc if "residuo_edicao" in active else []):
            auxiliaries = [c for c in head.children if c.dep_ in {"aux", "aux:pass", "cop"} and certamente_verbo(c)]
            for first, second in zip(auxiliaries, auxiliaries[1:]):
                # Verbos de orações diferentes (“o porão em que dormem é…”) não formam locução.
                if second.i == first.i + 1 and first.lower_ != second.lower_ and not fecha_oracao_dependente(first):
                    excerpt = block.text[first.idx:second.idx + len(second.text)]
                    results.append(finding(block, "Resíduo de edição", "Verificar", first.idx, second.idx + len(second.text),
                        explicar(f"‘{excerpt}’: dois verbos seguidos fazendo o mesmo papel. Normalmente só um fica "
                                 "(‘tinha percebido’ ou ‘havia percebido’). Pode ser sobra de uma edição; confira qual "
                                 "deve ficar.", "resíduo de edição (dois auxiliares conjugados)"),
                        "Regras FONTE"))
    results.sort(key=lambda f: (f.paragraph, f.start, f.category))
    metadata = {"tempo": expected or "inconclusivo", "contagem_verbos": dict(counts),
                "modelo": nlp.meta.get("name"), "versao_modelo": nlp.meta.get("version"),
                "paragrafos": len(blocks), "excluir_italico": protect_italics,
                "confirmacao_lexical": "PortiLexicon-UD", "segunda_leitura_estrutura": True}
    if "estrutura" in active:
        # Só a rodada da estrutura informa: as outras não apagam a contagem no relatório.
        metadata["fragmentos_sem_verbo"] = dict(fragment_classes)
    low = {"confidence": "baixa", "confidence_score": .4}
    return [asdict(f) | REGRA_POR_CATEGORIA[f.category] | (low if f.id in low_confidence else {}) | extras.get(f.id, {})
            for f in results], warnings, metadata
