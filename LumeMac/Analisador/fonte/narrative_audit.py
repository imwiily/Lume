"""Papéis, proveniência e presença compartilhados por todos os extratores."""

def event_roles(event):
    """Papéis resolvidos durante extração; leitores legados usam os campos planos."""
    return {
        'AGENT': event.get('subject'), 'PATIENT': event.get('patient'),
        'OBJECT': event.get('object'), 'RECIPIENT': event.get('to_entity'),
        'LOCATION': event.get('location'), 'SOURCE': event.get('source') or event.get('from_entity'),
        'DESTINATION': event.get('destination'), 'INSTRUMENT': event.get('instrument'),
        'HOLDER': event.get('holder'),
    }


def finalize(scenes):
    for scene in scenes:
        events = {e['id']:e for e in scene.events}
        for event in scene.events:
            event.setdefault('semantic_roles', event_roles(event))
        for fact in scene.facts:
            source = events.get(fact.get('event_id'))
            if source and fact['id'].startswith('fact_semantic_'):
                confidence = min(fact['fact_confidence'], source.get('event_confidence', 0))
                fact['confidence'] = fact['fact_confidence'] = confidence
            fact['source_event_ids'] = [fact['event_id']] if fact.get('event_id') else []
            actions = {'object_location': {'pegar','colocar','guardar','deixar','tirar'},
                       'object_use': {'pegar','abrir','ler','reler','usar','tirar'},
                       'holder': {'pegar','receber','entregar','devolver'},
                       'knows': {'saber','descobrir','aprender'}, 'tells': {'dizer','contar','revelar'}}.get(fact['relation'], set())
            if fact.get('generic') and actions:
                for event in scene.events:
                    proof = event['evidence']
                    if (not event['id'].startswith('generic_') and event['action'] in actions
                        and proof['paragraph'] == fact['evidence']['paragraph']
                        and max(proof['range']['start'], fact['evidence']['range']['start']) < min(proof['range']['end'], fact['evidence']['range']['end'])
                        and fact['subject'] in {event.get('subject'), event.get('object')}):
                        fact['source_event_ids'].append(event['id'])
        # Presença comprovada por ação ou fala; olhar/lembrar um local não prova estar nele.
        present = set(scene.present_entities)
        entered, left = set(scene.entered_entities), set(scene.left_entities)
        for e in sorted(scene.events, key=lambda e:e['evidence']['range']['start']):
            subject = e.get('subject')
            if not subject or not subject.startswith('char_') or not e.get('asserted'):
                continue
            if e['type'] == 'LEAVE_LOCATION':
                left.add(subject); present.discard(subject)
            elif e['type'] in {'ENTER_LOCATION', 'MOVE', 'ACQUIRE_OBJECT', 'INJURE', 'HEAL'}:
                present.add(subject)
                if e['type'] == 'ENTER_LOCATION':
                    entered.add(subject)
        present.update(t['speaker'] for t in scene.dialogue_turns if t['speaker'] and t.get('turn_kind') != 'thought')
        scene.present_entities = sorted(present)
        scene.entered_entities, scene.left_entities = sorted(entered), sorted(left)
        scene.mentioned_entities = sorted({p['id'] for p in scene.participants} - present)
