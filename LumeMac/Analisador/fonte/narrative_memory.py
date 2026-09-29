"""Promoção seletiva e memória persistente, independente de nomes de obras.

Uma identidade local pode sustentar um evento sem virar personagem canônico.
Ausência de evidência nunca estabelece desconhecimento ou uma contradição certa.
"""
import re
from collections import defaultdict

PERSISTENT = {'age', 'profession', 'physical_attribute', 'physical_state', 'mobility',
              'life_state', 'possesses', 'holder', 'object_state', 'door_state',
              'object_location', 'location', 'left_location', 'knows', 'sibling',
              'siblings', 'parent', 'friend', 'spouse', 'teacher', 'boss', 'nationality',
              'position', 'availability_state', 'met', 'created', 'found', 'ability', 'demonstrated_ability'}


def enrich_event(scene, event, token, frame, roles):
    """Complementos pertencem ao predicado; objeto físico nunca substitui agente."""
    from .narrative import governing_verb
    if event['type'] == 'TRANSFER_OBJECT':
        recipients = [frame.entity(t, 'person') for t in token.subtree
                      if governing_verb(t) == token and t != token
                      and any(c.dep_ == 'case' and c.lower_ in {'a', 'para'} for c in t.children)]
        recipients = {x for x in recipients if x}
        event['to_entity'] = next(iter(recipients)) if len(recipients) == 1 else None
        event['from_entity'] = event['subject']
    event['source'] = event.get('location') if event['type'] == 'LEAVE_LOCATION' else None
    body = next((t for t in token.children if t.dep_ == 'obj' and t.lower_ in {'perna','pé','braço','mão'}), None)
    if body is not None and event['action'] == 'quebrar':
        event['type'] = 'INJURE'
    if event['type'] == 'INJURE' and body is not None:
        owners = {frame.entity(t, 'person') for t in body.children if t.dep_ == 'nmod'} - {None}
        event['patient'] = next(iter(owners)) if len(owners) == 1 else event['subject'] if not owners else None
        event['body_part'] = body.lower_
    if event['type'] == 'HEAL' and not event.get('patient') and any(t.lower_ == 'se' for t in token.children):
        event['patient'] = event['subject']
    # Falha funcional do membro: a tentativa não prova lesão; a oração adversativa
    # descreve separadamente a limitação. Exige possessivo resolvido, sem concorrentes.
    limb = next((t for t in token.children if t.dep_ == 'nsubj' and t.lower_ in {'perna', 'pé', 'braço', 'mão'}), None)
    if event['action'] == 'responder' and limb is not None and any(t.lower_ == 'não' for t in token.children):
        possessives = [t for t in limb.children if t.lower_ in {'sua', 'seu'}]
        owners = {frame.entity(t, 'person') for t in possessives} - {None}
        people = {p['id'] for p in scene.participants if p['evidence']['range']['end'] <= event['evidence']['range']['end']}
        low = token.sent.text.casefold()
        if len(owners) == 1 and len(people) == 1 and 'mas' in low and not re.search(r'\b(?:talvez|sonho|sonhou|imaginou|poderia|teria|disse|contou)\b', low) and all(r == 'narracao' for r in roles[token.sent.start_char:token.sent.end_char]):
            event.update(type='PHYSICAL_LIMITATION', patient=next(iter(owners)),
                         body_part=limb.lower_, asserted=True, inference_level='strong_inference',
                         event_confidence=.8, reference_confidence=.8)
    instruments = {frame.entity(t, 'object') for t in token.children
                   if t.dep_ == 'obl' and any(c.lower_ == 'com' and c.dep_ == 'case' for c in t.children)} - {None}
    event['instrument'] = next(iter(instruments)) if len(instruments) == 1 else None
    # "Descobriu a verdade" e "sabia do acidente" compartilham a mesma proposição.
    if event['type'] in {'KNOW', 'LEARN', 'DISCOVER', 'HEAR', 'SEE', 'REALIZE'}:
        complements = [t for t in token.children if t.dep_ in {'obj', 'ccomp'}]
        if event['type'] in {'HEAR', 'SEE', 'REALIZE'}:
            complements = [t for t in complements if t.dep_ == 'ccomp' and event['action'] != 'olhar'
                           and any(c.dep_ == 'mark' and c.lower_ == 'que' for c in t.children)]
        if len(complements) == 1:
            terms = [t for t in complements[0].subtree if not t.is_punct
                     and t.dep_ not in {'case', 'det'} and t.lemma_ not in {'ontem','hoje','amanhã'}]
            # Adjuntos temporais não fazem parte da identidade do conhecimento.
            text = ' '.join(t.text for t in sorted(terms, key=lambda t:t.i))
            text = re.split(r'\s+(?:na |no )?(?:segunda-feira|terça-feira|quarta-feira|quinta-feira|sexta-feira|sábado|domingo)|\s+às\s+', text)[0]
            if text.strip():
                event['proposition'] = text.casefold().strip()
        negatives = [t for t in token.subtree if t.lower_ in {'não','nunca','jamais','ninguém','nenhum','sem'} and (t.head == token or t.dep_ in {'mark','det'})]
        if negatives and event['type'] in {'KNOW', 'LEARN', 'DISCOVER'}:
            # Verifica modalidade usando o mesmo predicado, retirando apenas negação.
            from .semantic_roles import UNCERTAIN, REPORTING
            governing = [token, *token.ancestors, *[t for t in token.children if t.dep_ in {'aux','aux:pass'}]]
            modal = UNCERTAIN.search(token.sent.text) or any(t.lemma_ in REPORTING | {'poder','dever','querer','tentar','planejar'} for t in governing)
            narrative = all(r == 'narracao' for r in roles[token.sent.start_char:token.sent.end_char])
            event['asserted'] = bool(narrative and not modal and not re.search(r'\b(?:sonho|flashback)\b', token.sent.text, re.I))
            event['polarity'] = 'negative'
    # Confiança acompanha todos os papéis usados, inclusive paciente e destinatário.
    used = {event.get(k) for k in ('subject','object','patient','to_entity','instrument')} - {None}
    limits = [event['event_confidence']]
    for collection in (scene.participants, scene.objects):
        latest = {}
        for entity in collection:
            if entity['id'] in used and entity['evidence']['range']['start'] < event['evidence']['range']['end']:
                latest[entity['id']] = entity
        limits.extend(min(e.get('entity_confidence', .8), e.get('identity_confidence', 1)) for e in latest.values())
    limits.extend(r['reference_confidence'] for r in scene.references
                  if r['reference'] in used and event['evidence']['range']['start'] <= r['evidence']['range']['start'] < event['evidence']['range']['end'])
    event['confidence'] = event['event_confidence'] = min(limits)
    from .narrative_audit import event_roles
    event['semantic_roles'] = event_roles(event)
    event['semantic_role_confidence'] = event['event_confidence']


def promote_event(scene, event, people, items):
    from .narrative import add_fact
    roles = event['semantic_roles']
    subject, obj, kind = roles['AGENT'], roles['OBJECT'], event['type']
    def fact(s, relation, value, **extra):
        if s is None or value is None:
            return
        f = add_fact(scene, event, s, relation, value, polarity=event.get('polarity', 'positive'))
        f.update(extra)
    if kind in {'KNOW','LEARN','DISCOVER', 'HEAR', 'SEE', 'REALIZE'} and subject in people:
        fact(subject, 'knows', event.get('proposition'), transition=kind != 'KNOW')
    elif kind == 'HOLD_OBJECT' and subject in people and obj in items:
        fact(subject, 'holds', obj)
    elif kind == 'STORE_OBJECT' and subject in people and obj in items:
        fact(subject, 'possesses', obj, transition=True)
    elif kind == 'LOSE_OBJECT' and subject in people and obj in items:
        add_fact(scene, event, obj, 'holder', subject, polarity='negative')['transition'] = True
        add_fact(scene, event, obj, 'object_location', 'carried', polarity='negative')['transition'] = True
    elif kind == 'TRANSFER_OBJECT' and subject in people and obj in items and roles['RECIPIENT'] in people:
        fact(obj, 'holder', roles['RECIPIENT'], transition=True)
        add_fact(scene, event, subject, 'possesses', obj, polarity='negative')
        fact(roles['RECIPIENT'], 'possesses', obj, transition=True)
    elif kind == 'MEET' and subject in people and event.get('patient') in people and subject != event['patient']:
        fact(subject, 'met', event['patient'])
    elif kind == 'FIND' and subject in people and obj in items:
        # Encontrar não prova aquisição/posse.
        fact(subject, 'found', obj)
    elif kind == 'CREATE' and subject in people and obj in items:
        fact(subject, 'created', obj)
        fact(obj, 'object_state', 'intact', transition=True)
    elif kind in {'INJURE','HEAL'} and roles['PATIENT'] in people:
        fact(roles['PATIENT'], 'mobility', 'injured' if kind == 'INJURE' else 'healthy', transition=True)
        state = 'leg_injured' if event.get('body_part') in {'perna','pé'} else 'arm_injured' if event.get('body_part') in {'braço','mão'} else 'injured'
        fact(roles['PATIENT'], 'physical_state', state if kind == 'INJURE' else 'healthy', transition=True)
    elif kind == 'PHYSICAL_LIMITATION' and roles['PATIENT'] in people:
        f = add_fact(scene, event, roles['PATIENT'], 'physical_state',
                     'leg_impaired' if event['body_part'] in {'perna', 'pé'} else 'arm_impaired',
                     inference='strong_inference')
        f['transition'] = True
    elif kind == 'USE_OBJECT' and subject in people and obj in items:
        fact(obj, 'object_use', subject)


def physical_facts(frame, text, actor, fact):
    """Estados explícitos e inferência física limitada, sempre com portador resolvido."""
    from .semantic_roles import REPORTING
    if any(t.lemma_ in REPORTING for t in frame.span):
        return
    low = text.casefold()
    if re.search(r'\b(?:não|nunca|jamais|ninguém|nenhum|sem)\b', low):
        return
    target = frame.subject(patient=True)
    injury = re.search(r'\b(perna|pé|braço|mão)(?: direit[oa]| esquerd[oa])? (?:quebrad[oa]|ferid[oa]|machucad[oa]|engessad[oa])\b', low)
    if injury and target:
        state = 'leg_disabled' if injury[1] in {'perna','pé'} else 'arm_disabled'
        fact(target, 'physical_state', state, patient=target)
    hurt = re.search(r'\b(?:machucou|feriu) (?:a |o )(perna|pé|braço|mão)\b', low)
    if hurt and actor:
        fact(actor, 'physical_state', 'leg_injured' if hurt[1] in {'perna','pé'} else 'arm_injured', 'INJURE', patient=actor, transition=True)
    for pattern, value in [(r'\bestava inconsciente\b', 'unconscious'),
                           (r'\b(?:sangrava|estava sangrando)\b', 'bleeding'),
                           (r'\b(?:estava curad[oa]|recuperou-se)\b', 'healthy'),
                           (r'\bincapaz de correr\b', 'leg_disabled')]:
        if target and re.search(pattern, low):
            fact(target, 'physical_state', value, transition=value == 'healthy')
    if actor and re.search(r'\bmancava\b', low) and re.search(r'\bevitava apoiar (?:a |o )(?:perna|pé)\b', low):
        fact(actor, 'physical_state', 'leg_injured', inference='strong_inference')
    elif actor and re.search(r'\bmancava\b', low):
        whole = frame.span[0].sent
        avoidance = next((t for t in whole if t.lemma_ == 'evitar'), None)
        if avoidance is not None and frame.subject(avoidance) == actor and re.search(r'\bevitava apoiar (?:a |o )(?:perna|pé)\b', whole.text.casefold()):
            fact(actor, 'physical_state', 'leg_injured', inference='strong_inference')
    if actor and re.search(r'\bparecia sentir dor\b', low):
        fact(actor, 'physical_state', 'pain', inference='weak_inference')
    if actor and re.search(r'\b(?:correu|chutou|saltou)\b', low):
        fact(actor, 'physical_action', 'kick' if 'chutou' in low else 'run' if 'correu' in low else 'jump')


def classify_participants(scenes):
    mentions, events, speeches = defaultdict(list), defaultdict(list), defaultdict(set)
    for scene in scenes:
        for p in scene.participants:
            mentions[p['id']].append((scene.id, p))
        for e in scene.events:
            if e.get('asserted') and e.get('event_confidence', 0) >= .65:
                events[e.get('subject')].append(e)
        for t in scene.dialogue_turns:
            if t.get('speaker') and t.get('turn_kind') != 'thought':
                speeches[t['speaker']].add(t['evidence']['paragraph'])
    for ident, entries in mentions.items():
        named = any(p.get('named', not p.get('description') and not p.get('provisional')) for _, p in entries)
        recurring = len({p['evidence']['paragraph'] for _, p in entries} | speeches[ident]) >= 2
        relevant = any(e['type'] in {'ACQUIRE_OBJECT','TRANSFER_OBJECT','INJURE','HEAL','DISCOVER','DIE'} for e in events[ident])
        singular = all(p.get('number', 'Sing') == 'Sing' for _, p in entries)
        canonical = named or any(p.get('provisional') for _, p in entries) or (singular and recurring and (bool(speeches[ident]) or relevant))
        reason = 'proper_name' if named else 'narrator' if any(p.get('provisional') for _,p in entries) else 'recurring_relevant_participant' if canonical else 'insufficient_persistent_evidence'
        for _, person in entries:
            person.update(identity_tier='canonical_character' if canonical else 'local_participant', promotion_basis=reason)


def finalize_memory(scenes):
    """Proveniência, dependências e tempo em todos os caminhos de extração."""
    classify_participants(scenes)
    entities = {}
    for scene in scenes:
        for p in [*scene.participants, *scene.objects, *scene.location]:
            entities[p['id']] = p
    for scene in scenes:
        events = {e['id']:e for e in scene.events}
        timed = sorted((f for f in scene.facts if f.get('valid_from')), key=lambda f:f['evidence']['range']['start'])
        cursor, clock = 0, None
        context = next((f.get('context') for f in scene.facts if f.get('context') is not None), scene.id)
        for f in sorted(scene.facts, key=lambda f:f['evidence']['range']['start']):
            while cursor < len(timed) and timed[cursor]['evidence']['range']['start'] <= f['evidence']['range']['start']:
                clock = timed[cursor]['valid_from']; cursor += 1
            source = events.get(f.get('event_id'))
            dependencies = {f['subject']}
            if isinstance(f['value'], str) and f['value'] in entities:
                dependencies.add(f['value'])
            if source:
                dependencies.update(source.get(k) for k in ('subject','object','patient','to_entity'))
            dependencies.discard(None)
            limits = [f['fact_confidence']]
            if source:
                limits.append(source.get('event_confidence', 0))
            limits.extend(min(entities[i].get('entity_confidence', .8), entities[i].get('identity_confidence', 1)) for i in dependencies if i in entities)
            limits.extend(r['reference_confidence'] for r in scene.references if r['reference'] in dependencies and f['evidence']['range']['start'] <= r['evidence']['range']['start'] < f['evidence']['range']['end'])
            f['confidence'] = f['fact_confidence'] = min(limits)
            local = any(entities[i].get('identity_tier') == 'local_participant' for i in dependencies if i in entities)
            f['persistence'] = 'persistent' if f['relation'] in PERSISTENT and f['scope'] != 'reported' and not local and f['fact_confidence'] >= .65 else 'local'
            f['canonical_entity'] = f['subject'] if f['subject'] in entities and not local else None
            f['chapter'] = scene.chapter
            if f.get('valid_from') is None:
                f['valid_from'] = dict(clock) if clock else None
            f.setdefault('valid_until', None)
            f['time'] = f['valid_from']
            if f['relation'] in {'physical_state', 'mobility', 'knows', 'object_use', 'location'}:
                f.setdefault('generic', True)
                f.setdefault('context', context)
            f['confidence_chain'] = {'entity': min((entities[i].get('entity_confidence', .8) for i in dependencies if i in entities), default=1),
                                     'reference': source.get('reference_confidence', source.get('event_confidence', 0)) if source else 0,
                                     'event': source.get('event_confidence', 0) if source else 0, 'fact': f['fact_confidence']}
