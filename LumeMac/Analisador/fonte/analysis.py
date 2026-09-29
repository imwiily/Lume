"""Regras explicáveis. Os resultados são candidatos, nunca vereditos."""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import re

from .reader import Block
from .lexicon import finite, indicative_tense

SPEECH = set("dizer perguntar responder murmurar gritar sussurrar comentar retrucar afirmar falar exclamar replicar declarar indagar confessar explicar acrescentar argumentar insistir ordenar pedir protestar avisar pensar refletir ponderar admitir lembrar concluir continuar completar interromper balbuciar resmungar cochichar implorar vociferar anunciar observar sugerir repetir garantir negar confirmar questionar reclamar ironizar brincar saudar chamar".split())


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
    for block, doc, closed, mask in zip(blocks, docs, closings, masks):
        if block.heading:
            continue
        for token in doc:
            observed = indicative_tense(token)
            if "tempo_verbal" in active and expected and observed and observed != expected:
                results.append(finding(block, "Tempo verbal", "Verificar", token.idx,
                    token.idx+len(token.text),
                    f"O modelo e o léxico sustentam uma leitura no {observed}, em texto configurado/inferido como {expected}. Isso não confirma erro: pensamento, comentário do narrador, presente geral e mudanças deliberadas de plano temporal precisam ser avaliados no contexto."))
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if "estrutura" in active and len(words) >= min_words and not any(finite(t) for t in sent):
                # Segunda leitura só dos candidatos, sem espaços da máscara e
                # com inicial minúscula. Não modifica o texto nem seus offsets.
                clean = sent.text.strip()
                if clean:
                    second = nlp(clean[0].lower() + clean[1:])
                    if any(finite(t) for t in second):
                        continue
                start, end = words[0].idx, words[-1].idx + len(words[-1].text)
                results.append(finding(block, "Estrutura da frase", "Explorar", start, end,
                    "Após consulta ao léxico e uma segunda leitura do segmento, não foi identificado verbo finito com segurança. Uma frase nominal ou um fragmento intencional pode ser válido; confira o contexto. O analisador ainda pode falhar."))
        for position in (closed if "pontuacao_dialogo" in active else []):
            tail = block.text[position+1:]
            match = re.match(r"\s*,\s*", tail)
            if not match:
                continue
            start = position+1+match.end()
            remaining = [t for t in doc if t.idx >= start and not t.is_space]
            first_verb = next((t for t in remaining[:18] if finite(t)), None)
            if first_verb is not None and first_verb.lemma_.lower() not in SPEECH:
                results.append(finding(block, "Pontuação de diálogo", "Verificar",
                    position, first_verb.idx+len(first_verb.text),
                    "Após as aspas há uma vírgula, mas o primeiro verbo finito identificado não está na lista de elocução/pensamento. Confira se o trecho é uma ação independente ou uma construção válida no contexto."))
        for match in re.finditer(r"\b([^\W\d_]+)(\s+)\1\b", mask if "palavra_consecutiva" in active else "", re.I):
            results.append(finding(block, "Palavra repetida", "Verificar", match.start(), match.end(),
                "Palavra repetida consecutivamente na narração. Confira se é repetição expressiva ou digitação.", "Regras FONTE"))
    results.sort(key=lambda f: (f.paragraph, f.start, f.category))
    metadata = {"tempo": expected or "inconclusivo", "contagem_verbos": dict(counts),
                "modelo": nlp.meta.get("name"), "versao_modelo": nlp.meta.get("version"),
                "paragrafos": len(blocks), "excluir_italico": protect_italics,
                "confirmacao_lexical": "PortiLexicon-UD", "segunda_leitura_estrutura": True}
    return [asdict(f) for f in results], warnings, metadata
