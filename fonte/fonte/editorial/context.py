"""Primeira leitura de contexto curto, sem resolução semântica de cenas.

Janelas não atravessam capítulos/cortes explícitos. Evidências anteriores
sustentam referências; parágrafos seguintes só ajudam a revisão humana.
"""
import re
from ..analysis import explicar
from ..elocucao import forma_de_fala, verbo_de_fala
from ..verbo import model_finite
from ..segments import TRAVESSOES, classify, spans
from .common import alert, evidence

RULES = {'dialogo_contextual', 'referente_contextual', 'gerundismo'}
CUT = re.compile(r'\s*(?:\*{3}|—{3}|no dia seguinte\b|dias depois\b|na manhã seguinte\b)', re.I)
GERUND = re.compile(r'\b(?:vou|vai|vamos|vão|vais|irei|irá|iremos|irão)\s+(?:poder\s+)?estar\s+[^\W\d_]+(?:ando|endo|indo)\b', re.I)


def window(blocks, index):
    current = blocks[index]
    previous, following = [], []
    if index and not CUT.match(current.text):
        old = blocks[index - 1]
        if not old.heading and old.chapter == current.chapter:
            previous = [old]
    for other in blocks[index + 1:index + 4]:
        if other.heading or other.chapter != current.chapter or CUT.match(other.text):
            break
        following.append(other)
    return previous + [current] + following


def action_reason(speech, action):
    """Diz o que falta antes do travessão, com exemplo montado do próprio texto."""
    words = action.split()[:4]
    head = ' '.join(words).rstrip('.,;:!?…')
    fixed = head[:1].upper() + head[1:]
    tail = speech.split()[-1] if speech.split() else ''
    if speech.endswith(('.', '!', '?', '…')):
        problem = 'A fala já termina com pontuação, então a ação começa com letra maiúscula.'
    else:
        tail = tail.rstrip(',;:') + '.' if tail else ''
        problem = ('Nesse caso, falta pontuação para encerrar a fala antes do travessão '
                   '(ponto, interrogação, exclamação ou reticências)'
                   + ('' if head[:1].isupper() else ', e a ação começa com letra maiúscula') + '.')
    example = f'…{tail} — {fixed}…' if tail else f'— {fixed}…'
    return explicar(f'Depois da fala, “{head}…” parece ser uma ação de quem narra, e não um “disse” ou “perguntou”. '
                    f'{problem} Ex.: “{example}”. Confira; a lista de verbos de fala do Lume é limitada.',
                    'pontuação de diálogo com travessão')


def analyze(blocks, nlp, settings, *, docs=None):
    labels = classify(blocks, settings)
    if docs is None:
        docs = list(nlp.pipe((b.text for b in blocks), batch_size=32))
    by_number = {b.number: d for b, d in zip(blocks, docs)}
    out = []
    for index, (block, doc, roles) in enumerate(zip(blocks, docs, labels)):
        if block.heading:
            continue
        context = window(blocks, index)
        context_evidence = [evidence(b) for b in context]

        def emit(rule, category, start, end, reason, related=(), severity='editorial_attention'):
            item = alert(block, rule, category, start, end, reason, 'baixa', related)
            item.update(severity=severity, suggestion=None, suggestion_kind='possible',
                        context=context_evidence)
            # Extração verificável, ainda sem inferir identidade ou foco narrativo.
            item['scene_evidence'] = {
                'participants': [evidence(b, t.idx, t.idx + len(t.text))
                                 for b in context for t in by_number[b.number] if t.pos_ == 'PROPN'],
                'subjects': [evidence(b, t.idx, t.idx + len(t.text))
                             for b in context for t in by_number[b.number] if t.dep_ == 'nsubj'],
            }
            if category == 'Ação narrativa após fala':
                item['category_code'] = 'narrative_action_after_speech'
            elif rule == 'referente_contextual':
                item['category_code'] = 'ambiguous_reference'
            out.append(item)

        if settings['rules']['gerundismo']:
            for start, end, _ in spans(roles, ['narracao', 'dialogo', 'pensamento']):
                for match in GERUND.finditer(block.text[start:end]):
                    emit('gerundismo', 'Perífrase verbal possivelmente excessiva', start + match.start(), start + match.end(),
                         explicar('Vários verbos em sequência (como ‘vou estar fazendo’). Pode ser escolha de voz ou de '
                                  'ritmo; não é erro. O alerta só mostra onde a construção aparece.', 'gerundismo'))

        if settings['rules']['dialogo_contextual'] and settings['dialogue_dashes']:
            for start, end, role in spans(roles, ['narracao']):
                if start == 0 or block.text[start - 1] not in TRAVESSOES:
                    continue
                fragment = block.text[start:end]
                parsed = nlp(fragment)
                verb = next((t for t in parsed if model_finite(t)), None)
                # Verbos com clítico e nomes com acento decomposto não são
                # is_alpha no spaCy, mas continuam sendo tokens lexicais.
                first = next((t for t in parsed if any(c.isalpha() for c in t.text)), None)
                # O modelo pequeno às vezes não vê o verbo de fala logo após o
                # travessão (“— respondi, gaguejando…”); a forma escrita basta.
                if first is not None and forma_de_fala(first.text) and (verb is None or verb.i > first.i):
                    verb = first
                if verb is None or first is None:
                    continue
                if not verbo_de_fala(verb) and (first.text[0].islower() or
                        not block.text[:start-1].rstrip().endswith(('.', '!', '?', '…'))):
                    emit('dialogo_contextual', 'Ação narrativa após fala', start + first.idx,
                         start + verb.idx + len(verb.text),
                         action_reason(block.text[:start - 1].rstrip(), fragment.lstrip()))
                elif verbo_de_fala(verb) and end < len(block.text) and block.text[end] in TRAVESSOES:
                    continuation = block.text[end + 1:].lstrip()
                    if (continuation and continuation[0].isupper()
                            and not fragment.rstrip().endswith(('.', '!', '?', '…', ':'))):
                        first_spoken = next((t for t in nlp(continuation) if any(c.isalpha() for c in t.text)), None)
                        if first_spoken is not None and first_spoken.pos_ == 'PROPN':
                            continue
                        emit('dialogo_contextual', 'Retomada de fala após inciso', start + verb.idx, end,
                             explicar('Depois do “disse ele”, a fala volta com letra maiúscula, mas antes do travessão não '
                                      'há ponto. Ou falta um ponto ali, ou a fala continua a mesma frase e a letra seria '
                                      'minúscula. Nomes próprios ficam sempre com maiúscula.',
                                      'pontuação de diálogo com travessão'))

        if settings['rules']['referente_contextual']:
            for target in doc:
                if target.lower_ != 'objeto' or target.dep_ != 'obj' or target.i == 0 or doc[target.i - 1].lower_ != 'o':
                    continue
                # Só enumerações recentes, com pelo menos dois núcleos coordenados.
                candidates = []
                for prior in context[:context.index(block) + 1]:
                    for token in by_number[prior.number]:
                        if prior.number == block.number and token.idx >= target.idx:
                            continue
                        if token.pos_ == 'NOUN' and token.dep_ == 'conj' and token.head.pos_ == 'NOUN':
                            candidates.extend([evidence(prior, token.head.idx, token.head.idx + len(token.head.text)),
                                               evidence(prior, token.idx, token.idx + len(token.text))])
                unique = {(e['paragraph'], e['start']): e for e in candidates}
                if len(unique) >= 2:
                    emit('referente_contextual', 'Objeto com antecedente possivelmente ambíguo',
                         target.idx, target.idx + len(target.text),
                         explicar('Antes de “o objeto” foram citadas várias coisas. Qual delas é “o objeto”? Confira se a '
                                  'cena deixa isso claro.', 'referência ambígua'),
                         list(unique.values()), 'author_query')
    return out
