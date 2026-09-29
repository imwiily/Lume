"""Atribuição local de falas: marcadores explícitos antes de alternância."""
import re
from .segments import spans
from .narrative_context import HUMAN, valid_name, person_name

SAY = r'(?:disse|respondeu|perguntou|gritou|sussurrou|informou|explicou|afirmou|comentou|acrescentou|avisou|ordenou|murmurou|retrucou|indagou|anunciou|falou|replicou)'


def dialogue_roles(text, roles, name):
    """Acrescenta apenas o caso nome/verbo + dois-pontos + travessão."""
    marker = re.match(rf'\s*(?:{name}|[Ee]l[ae])\s+{SAY}\s*:\s*[—–]', text)
    if marker:
        roles = list(roles)
        start = marker.end()
        end = next((i for i in range(start, len(text)) if text[i] in '—–'), len(text))
        roles[start:end] = ['dialogo'] * (end-start)
    return roles


def extract_turns(scene, block, roles, ev, key, name):
    segments = list(spans(roles, ['dialogo']))
    for index, (start, end, _) in enumerate(segments):
        next_start = segments[index+1][0] if index+1 < len(segments) else len(block.text)
        tail = block.text[end:next_start]
        description = r'(?:[OoAa]\s+)?(?:' + '|'.join(sorted(HUMAN, key=len, reverse=True)) + ')'
        actor = rf'(?P<actor>{description}(?:\s+{name})?|{name}|[Ee]l[ae])'
        separator = r'\s*[”»"’]?\s*[,—–]?\s*'
        after = re.match(rf'{separator}(?:{SAY}\s+{actor})\b', tail)
        if not after:
            after = re.match(rf'{separator}{actor}\s+{SAY}\b', tail)
        before = re.search(rf'{actor}\s+{SAY}\s*:\s*[—–“«"]?\s*$', block.text[:start]) if not after else None
        marker = after or before
        speaker, confidence, basis, attribution = None, .0, 'unresolved', None
        if marker:
            name_text = marker['actor']
            actor_start = (end if after else 0) + marker.start('actor')
            attribution = ev(actor_start, actor_start + len(name_text))
            if name_text.casefold() in {'ele', 'ela'}:
                ref = next((r for r in scene.references if r['evidence']['range'] == attribution['range']), None)
                if ref:
                    speaker, confidence = ref['reference'], ref['reference_confidence']
                    basis = 'coreference' if speaker else 'unresolved'
            else:
                descriptive = re.match(description + r'\b\s*', name_text)
                clean_name = name_text[descriptive.end():] if descriptive else name_text
                if descriptive:
                    matches = {p['id']:p for p in scene.participants if p['evidence']['range']['start'] == attribution['range']['start'] or
                               (p.get('description') and p['description'] in name_text.casefold().split() and p['evidence']['range']['start'] >= attribution['range']['start'] and p['evidence']['range']['end'] <= attribution['range']['end'])}
                    if len(matches) == 1:
                        person = next(iter(matches.values()))
                        speaker, confidence, basis = person['id'], .85, 'description'
                if not speaker and valid_name(clean_name):
                    name_text = person_name(clean_name)
                    speaker, confidence, basis = key('char', name_text), .95, 'explicit'
                if speaker and not any(p['id'] == speaker for p in scene.participants):
                    scene.participants.append(dict(id=speaker, name=name_text, type='PERSON', category=None,
                        entity_confidence=.95, gender='', number='Sing', role='speaker',
                        presence='explicit_speech', evidence=attribution))
            # SPEAK herda a mesma identidade usada pelo turno, inclusive se o parser errou.
            for event in scene.events:
                if event['type'] == 'SPEAK' and event['evidence']['paragraph'] == block.number:
                    lo, hi = event['evidence']['range']['start'], event['evidence']['range']['end']
                    if lo <= attribution['range']['start'] < hi:
                        event.update(subject=speaker, subject_basis=basis, reference_confidence=confidence,
                                     event_confidence=confidence, confidence=confidence)
        elif re.match(separator + r'(?:respondi|perguntei|afirmei|gritei|murmurei|sussurrei|pensei)\b', tail) and scene.narrator != 'unknown':
            speaker, confidence, basis = scene.narrator, .85, 'first_person'
        elif len(scene.dialogue_turns) >= 2:
            first, last = scene.dialogue_turns[-2:]
            participants = {p['id'] for p in scene.participants if p['evidence']['paragraph'] >= first['evidence']['paragraph']}
            pair = {first['speaker'], last['speaker']}
            adjacent = last['evidence']['paragraph'] == block.number - 1 and first['evidence']['paragraph'] == block.number - 2
            if adjacent and None not in pair and len(pair) == 2 and participants == pair and first['speaker_basis'] in {'explicit','coreference'} and last['speaker_basis'] in {'explicit','coreference'}:
                speaker, confidence, basis = first['speaker'], .6, 'alternation'
        thought = bool(re.match(separator + r'(?:(?:pensou|pensei|refletiu|refleti)\b|' + actor + r'\s+(?:pensou|refletiu)\b)', tail))
        scene.dialogue_turns.append(dict(speaker=speaker, speech=block.text[start:end].strip(), turn_kind='thought' if thought else 'speech',
            speech_act='question' if '?' in block.text[start:end] else 'statement', confidence=confidence,
            speaker_confidence=confidence, speaker_basis=basis, attribution_evidence=attribution, evidence=ev(start, end)))
        if speaker and speaker not in scene.speakers:
            scene.speakers.append(speaker)
        # Declarações permanecem atribuídas ao falante; não atestam o mundo narrado.
        if speaker and not thought:
            from .generic_facts import CARDINAL, number
            from .narrative import add_fact
            age = re.fullmatch(rf'\s*(?:Eu\s+)?tenho\s+({CARDINAL})\s+anos(?:[,!.].*)?\s*', block.text[start:end], re.I)
            if age:
                event = dict(id=f'reported_{block.number}_{start}', type='REPORTED_ATTRIBUTE', subject=speaker,
                             action='age', object=None, asserted=False, confidence=confidence, event_confidence=confidence, evidence=ev(start,end))
                scene.events.append(event)
                item = add_fact(scene, event, speaker, 'age', number(age[1]), scope='reported')
                item.update(fact_type='ATTRIBUTE_FACT', valid_from=None, valid_until=None)
