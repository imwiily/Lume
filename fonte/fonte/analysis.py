"""Regras explicáveis. Os resultados são candidatos, nunca vereditos."""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import re

from .reader import Block
from .lexicon import finite, flags, indicative_tense

SPEECH = set("dizer informar perguntar responder murmurar gritar sussurrar comentar retrucar afirmar falar exclamar replicar declarar indagar confessar explicar acrescentar argumentar insistir ordenar pedir protestar avisar pensar refletir ponderar admitir lembrar concluir continuar completar interromper balbuciar resmungar cochichar implorar vociferar anunciar observar sugerir repetir garantir negar confirmar questionar reclamar ironizar brincar saudar chamar ler recitar citar ditar cantar declamar terminar".split())

# Terminações verbais comuns; com o radical de um verbo de elocução, reconhecem a forma
# mesmo quando o modelo pequeno erra o lema (“perguntei” → “perguntei”, “respondemos” → “respond”).
TERMINACOES = re.compile(r"(?:o|a|as|amos|ais|am|ei|aste|ou|astes|aram|ava|avas|ávamos|avam|e|es|emos|em|i|este|eu|"
                         r"estes|eram|ia|ias|íamos|iam|iu|imos|iram|ará|arão|erá|erão|irá|irão|ando|endo|indo)(?:-\w+)?")


# Depois destas palavras “para” não pode ser preposição: é o verbo parar (“o braço para no ar”).
DEPOIS_DE_PARAR = {"de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "num", "numa"}


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
    verb = next((t for t in previous if finite(t)), None)
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


# Conjunções que abrem oração subordinada: sem verbo finito, falta a oração.
SUBORDINANTES = {"quando", "enquanto", "porque", "embora", "conquanto", "caso", "porquanto"}
# “Enquanto isso, …”, “quando muito”: locuções adverbiais, não subordinação.
LOCUCAO_ADVERBIAL = {"isso", "isto", "aquilo", "assim", "muito", "pouco", "possível", "necessário"}
RELATIVOS = {"que", "onde", "cujo", "cuja", "cujos", "cujas"}
ARTIGOS = {"o", "a", "os", "as", "um", "uma", "uns", "umas"}
# Palavras que pedem continuação: fragmento terminado nelas foi cortado.
PEDEM_CONTINUACAO = set(PREPOSICOES) | ARTIGOS | {"e", "ou", "mas", "que", "se", "nem"}


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
    if any(finite(t) for t in sent):
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
    if any(not any(finite(t) for t in s) for s in vizinhos):
        return "likely_literary_fragment"
    return "uncertain"


def verbo_de_fala(token):
    """Verbo de elocução ou pensamento, pelo lema ou pelo radical + terminação verbal."""
    return token.lemma_.casefold() in SPEECH or forma_de_fala(token.lower_)


IRREGULARES_DE_FALA = {"disse", "disseram", "diz", "dizem", "dizia", "diziam", "dirá", "pediu", "pediram", "pede", "pedia"}


def forma_de_fala(forma):
    """Mesmo critério, só pela forma escrita (sem análise sintática)."""
    forma = forma.casefold()
    if forma in IRREGULARES_DE_FALA:
        return True
    for verbo in SPEECH:
        radical = verbo[:-2]
        if len(radical) >= 3 and forma.startswith(radical) and TERMINACOES.fullmatch(forma[len(radical):]):
            return True
    return False


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


def finding(block, category, priority, start, end, reason, source="Regras FONTE + spaCy + PortiLexicon-UD"):
    # Mantém a identidade dos alertas antigos que continuam no mesmo trecho.
    key_source = source.replace(" + PortiLexicon-UD", "")
    key = f"{block.number}:{category}:{key_source}:{start}:{end}:{block.text}"
    return Finding(hashlib.sha256(key.encode()).hexdigest()[:16], category,
                   priority, block.number, block.chapter, block.text,
                   start, end, reason, source)


def narrative_masks(blocks, protect_italics=True):
    """Mantém comprimento/offsets. Aspas podem atravessar parágrafos."""
    masks, closing_positions, warnings = [], [], []
    closer = None
    for block in blocks:
        text = block.text
        if block.heading:
            if closer:
                warnings.append(f"Aspas possivelmente abertas antes do título no parágrafo {block.number}.")
            closer = None
            masks.append(" " * len(text))
            closing_positions.append([])
            continue
        # Recupera sincronização após aspas ausentes: um novo par completo
        # no início é tratado como nova fala, nunca invertido em narração.
        stripped = text.lstrip()
        opener = {'”': '“', '»': '«', '"': '"', '’': '‘'}.get(closer)
        if closer and opener and stripped.startswith(opener) and closer in stripped[1:]:
            warnings.append(f"Aspas anteriores possivelmente sem fechamento: a separação foi reiniciada no parágrafo {block.number}. Confira o trecho anterior.")
            closer = None
        visible = list(text)
        closed = []
        for i, char in enumerate(text):
            if closer and i == len(text)-len(stripped) and char == opener:
                # Abertura repetida no início de uma fala com vários parágrafos.
                visible[i] = " "
                continue
            if closer:
                visible[i] = " "
                if char == closer:
                    closer = None
                    closed.append(i)
            elif char in {'“', '«', '"', '‘'}:
                closer = {'“': '”', '«': '»', '"': '"', '‘': '’'}[char]
                visible[i] = " "
        # Travessão inicial: alterna fala / inciso narrativo / fala.
        if text.lstrip().startswith(("—", "–")):
            spoken = False
            for i, char in enumerate(text):
                if char in "—–":
                    spoken = not spoken
                    visible[i] = " "
                elif spoken:
                    visible[i] = " "
        if protect_italics:
            for start, end in block.italic:
                visible[start:end] = [" "] * (end-start)
        masks.append("".join(visible))
        closing_positions.append(closed)
    if closer:
        warnings.append("Há aspas sem fechamento até o fim do texto; isso pode ocultar trechos da análise narrativa.")
    return masks, closing_positions, warnings


def analyze(blocks: list[Block], nlp, tense="auto", protect_italics=True, min_words=5, masks_override=None, enabled_rules=None):
    masks, closings, warnings = narrative_masks(blocks, protect_italics)
    if masks_override is not None:
        masks = masks_override
    active = set(enabled_rules) if enabled_rules is not None else {'tempo_verbal','estrutura','pontuacao_dialogo','palavra_consecutiva'}
    docs = list(nlp.pipe(masks, batch_size=32))
    counts = Counter(indicative_tense(t) for d in docs for t in d)
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
    fragment_classes, low_confidence = Counter(), set()
    for block, doc, closed, mask in zip(blocks, docs, closings, masks):
        if block.heading:
            continue
        for token in doc:
            observed = indicative_tense(token)
            if "tempo_verbal" in active and expected and observed and observed != expected:
                from .temporal import legitimate_present, present_function
                if expected == "passado" and legitimate_present(token):
                    continue
                reason = (f"O modelo e o léxico sustentam uma leitura no {observed}, em texto configurado/inferido como {expected}. "
                          "Isso não confirma erro: pensamento, comentário do narrador, presente geral e mudanças deliberadas "
                          "de plano temporal precisam ser avaliados no contexto.")
                elapsed = re.match(r"há\s+(?:\d+|[^\W\d_]+)\s+(?:segundos?|minutos?|horas?|dias?|semanas?|meses|anos?)\b",
                                   block.text[token.idx:], re.I)
                if expected == "passado" and elapsed:
                    reason = (f"‘{elapsed[0]}’ mede o tempo a partir do presente. Numa narração no passado, ‘havia’ ou "
                              "uma referência como ‘… antes’ situa o intervalo no plano da história; a leitura atual "
                              "pode ser intencional (voz do narrador).")
                function = present_function(token) if expected == "passado" and observed == "presente" else None
                # Marcador discursivo (“Tá.”, “Tá bom.”): resposta curta, não verbo da narração.
                if function == "discourse_marker":
                    continue
                item = finding(block, "Tempo verbal", "Verificar", token.idx, token.idx+len(token.text), reason)
                # Presente que não é evento narrativo (estado, verdade geral, pensamento, comentário)
                # continua visível, com confiança baixa; a sequência temporal trata os eventos.
                if function is not None and function not in {"narrative_event", "transient_state"}:
                    low_confidence.add(item.id)
                results.append(item)
        previous = None
        sents = list(doc.sents)
        for index, sent in enumerate(sents):
            words = [t for t in sent if t.is_alpha]
            before, previous = previous, sent
            if ("estrutura" in active and len(words) >= min_words and not any(finite(t) for t in sent)
                    and not para_verbal(sent) and not elipse_de_complemento(sent, before)
                    and not fragmento_suspenso(sent)):
                # Segunda leitura só dos candidatos, sem espaços da máscara e
                # com inicial minúscula. Não modifica o texto nem seus offsets.
                clean = sent.text.strip()
                if clean:
                    second = nlp(clean[0].lower() + clean[1:])
                    if any(finite(t) for t in second):
                        continue
                following = sents[index + 1] if index + 1 < len(sents) else None
                classe = classificar_fragmento(sent, before, following)
                fragment_classes[classe] += 1
                if classe not in {"likely_incomplete_clause", "uncertain"}:
                    continue
                start, end = words[0].idx, words[-1].idx + len(words[-1].text)
                if classe == "likely_incomplete_clause":
                    reason = (f"O segmento ‘{block.text[start:end]}’ parece uma oração incompleta: não tem verbo finito e "
                              "começa com subordinante ou relativo, ou termina em palavra que pede continuação. "
                              "Confira se falta a oração principal ou parte do texto.")
                else:
                    reason = (f"O segmento ‘{block.text[start:end]}’ não tem verbo finito expresso. Frases nominais e fragmentos "
                              "são comuns em prosa literária e podem ser deliberados; revise apenas se uma oração completa era pretendida.")
                item = finding(block, "Estrutura da frase", "Explorar", start, end, reason)
                if classe == "uncertain":
                    low_confidence.add(item.id)
                results.append(item)
        for position in (closed if "pontuacao_dialogo" in active else []):
            tail = block.text[position+1:]
            match = re.match(r"\s*,\s*", tail)
            if not match:
                continue
            start = position+1+match.end()
            remaining = [t for t in doc if t.idx >= start and not t.is_space]
            first_verb = next((t for t in remaining[:18] if finite(t)), None)
            if first_verb is not None and not verbo_de_fala(first_verb):
                results.append(finding(block, "Pontuação de diálogo", "Verificar",
                    position, first_verb.idx+len(first_verb.text),
                    "Após as aspas há uma vírgula, mas o primeiro verbo finito identificado não está na lista de elocução/pensamento. Confira se o trecho é uma ação independente ou uma construção válida no contexto."))
        for match in re.finditer(r"\b([^\W\d_]+)(\s+)\1\b", mask if "palavra_consecutiva" in active else "", re.I):
            # Onomatopeia reduplicada (“au au”, “blá blá”): forma fora do léxico.
            if not flags(match[1]):
                continue
            results.append(finding(block, "Palavra repetida", "Verificar", match.start(), match.end(),
                "Palavra repetida consecutivamente na narração. Confira se é repetição expressiva ou digitação.", "Regras FONTE"))
        # Resíduo de edição: dois auxiliares conjugados seguidos no mesmo predicado (“tinha havia
        # percebido”). Na locução verbal só o primeiro é finito; os outros ficam no infinitivo,
        # gerúndio ou particípio (“tinha sido”, “vai ter”, “estava sendo”).
        for head in (doc if "estrutura" in active else []):
            auxiliaries = [c for c in head.children if c.dep_ in {"aux", "aux:pass", "cop"} and finite(c)]
            for first, second in zip(auxiliaries, auxiliaries[1:]):
                if second.i == first.i + 1 and first.lower_ != second.lower_:
                    excerpt = block.text[first.idx:second.idx + len(second.text)]
                    results.append(finding(block, "Resíduo de edição", "Verificar", first.idx, second.idx + len(second.text),
                        f"‘{excerpt}’: dois verbos auxiliares conjugados seguidos no mesmo predicado. Numa locução "
                        "verbal só um deles fica conjugado; pode ser resto de uma edição. Confira qual forma deve ficar.",
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
    return [asdict(f) | (low if f.id in low_confidence else {}) for f in results], warnings, metadata
