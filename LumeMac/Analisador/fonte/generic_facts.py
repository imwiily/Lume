"""Fatos editoriais comuns, com evidência; comparação independente do texto.

Gramáticas locais deliberadamente conservadoras. Confiança é heurística.
Nenhum nome próprio ou manuscrito determina uma regra.
"""
import re
from collections import defaultdict
from .narrative import add_fact
from .semantic_roles import Roles, clauses, REPORTING, UNCERTAIN
from .editorial.common import alert

WEEKDAYS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
NUMBERS = dict(zip('zero um dois três quatro cinco seis sete oito nove dez onze doze'.split(), range(13)))
NUMBERS.update(uma=1, duas=2, vinte=20, trinta=30, quarenta=40, cinquenta=50)
NUMBERS.update(dict(zip('treze catorze quinze dezesseis dezessete dezoito dezenove'.split(), range(13,20))))
NUMBERS.update(quatorze=14, sessenta=60, setenta=70, oitenta=80, noventa=90, cem=100, cento=100,
               duzentos=200, trezentos=300, quatrocentos=400, quinhentos=500, seiscentos=600, setecentos=700, oitocentos=800, novecentos=900)
CARDINAL = r'(?:\d+|(?:' + '|'.join(sorted(NUMBERS, key=len, reverse=True)) + r')(?: e (?:' + '|'.join(sorted(NUMBERS, key=len, reverse=True)) + r')){0,2})'
NUMBER = CARDINAL
HOUR = r'(?:vinte e (?:um|uma|dois|duas|três)|\d+|zero|um|uma|dois|duas|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quatorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)'
NEGATION = r'\b(?:não|nunca|jamais|nenhum|ninguém|sem)\b'
TYPES = {'age': 'ATTRIBUTE', 'physical_attribute': 'ATTRIBUTE', 'profession': 'ATTRIBUTE',
         'siblings': 'RELATION', 'sibling': 'RELATION', 'parent': 'RELATION', 'friend': 'RELATION',
         'spouse': 'RELATION', 'teacher': 'RELATION', 'boss': 'RELATION', 'met': 'RELATION', 'arrival_after': 'TIME',
         'location': 'LOCATION', 'object_location': 'LOCATION', 'possesses': 'POSSESSION', 'holder': 'POSSESSION',
         'knows': 'KNOWLEDGE', 'tells': 'KNOWLEDGE', 'weekday': 'TIME', 'duration': 'TIME',
         'elapsed': 'TIME', 'identity_name': 'IDENTITY'}


def number(text):
    return int(text) if text.isdigit() else sum(NUMBERS[w] for w in text.casefold().split(' e '))


def extract_generic(scenes, manuscript, docs, labels, key, evidence):
    """Enriquece as mesmas cenas e identidades da extração sintática."""
    from .narrative_dialogue import dialogue_roles
    from .semantic import NAME
    records = {b.number: (b, o, d, r) for b, o, d, r in zip(manuscript.blocks, manuscript.offsets, docs, labels)}
    time = dict(day=0, year=0, week=0, weekday=None, minute=None)
    context = 0
    prior_chapter = None
    identity_claim = None
    scene_contexts = {}
    for scene in scenes:
        recent_actor = None
        first_block = records[scene.start_paragraph][0]
        if scene.chapter != prior_chapter or re.match(r'\s*(?:\*{3}|—{3})', first_block.text):
            context += 1
            time = dict(day=0, year=0, week=0, weekday=None, minute=None)
            identity_claim = None
        prior_chapter = scene.chapter
        scene_contexts[scene.id] = context
        deictic_day = time['day']
        original_facts = defaultdict(list)
        original_events = {e['id']:e for e in scene.events}
        for f in scene.facts:
            original_facts[f['evidence']['paragraph']].append(f)
        for block, offset, doc, roles in (records[n] for n in range(scene.start_paragraph, scene.end_paragraph + 1) if n in records):
            if not scene.start_paragraph <= block.number <= scene.end_paragraph or block.heading:
                continue
            roles = dialogue_roles(block.text, roles, NAME)
            for sent in clauses(doc):
                text = sent.text.strip()
                low = text.casefold()
                proof = evidence(offset, block, sent.start_char, sent.end_char)
                claim = re.search(r'(?:—\s*)?Meu nome é (' + NAME + r')\s*—\s*disse o mesmo (?:homem|médico|rapaz)\.', text)
                if claim and identity_claim:
                    old = identity_claim
                    event = dict(id=f'generic_identity_{block.number}_{sent.start_char}', type='TELL', subject=old['subject'], object=None, action='identity_claim', asserted=False, confidence=.8, event_confidence=.8, evidence=proof)
                    scene.events.append(event)
                    new = add_fact(scene, event, old['subject'], 'identity_name', claim[1], scope='reported')
                    new.update(generic=True, fact_type='IDENTITY_FACT', valid_from=dict(time), valid_until=None, context=context)
                if any(r != 'narracao' for r in roles[sent.start_char:sent.end_char]) or UNCERTAIN.search(text) or any(t.lower_ == 'se' and t.pos_ == 'SCONJ' for t in sent):
                    continue
                if re.search(r'\b(?:em sonho|num sonho|no sonho|em um sonho|flashback)\b', low):
                    continue
                if re.search(r'\b(?:no dia seguinte|na manhã seguinte)\b', low):
                    time['day'] += 1
                    time['minute'] = None
                    if time['weekday'] is not None:
                        time['weekday'] = (time['weekday'] + 1) % 7
                if 'semana seguinte' in low:
                    time['week'] += 1
                deictic = re.search(r'\b(hoje|ontem|amanhã)\b', low)
                if deictic:
                    time['day'] = deictic_day + {'hoje':0, 'ontem':-1, 'amanhã':1}[deictic[1]]
                    time['minute'] = None
                days = re.search(rf'\b({NUMBER}) dias? (depois|antes)\b', low)
                if days:
                    time['day'] += number(days[1]) * (1 if days[2] == 'depois' else -1)
                    time['minute'] = None
                years = re.search(rf'\b({NUMBER}) anos? (depois|antes)\b', low)
                if years:
                    time['year'] += number(years[1]) * (1 if years[2] == 'depois' else -1); time['minute'] = None
                weekday = next((i for i, day in enumerate(WEEKDAYS) if day in low), None)
                expected_day = time['weekday']
                if weekday is not None:
                    if re.search(r'\b(?:dias depois|semana seguinte)\b', low) and expected_day is not None and weekday < expected_day and 'semana seguinte' not in low:
                        time['week'] += 1
                    time['weekday'] = weekday
                clock = re.search(rf'\bàs ({HOUR})(?:(?: horas)? e ({NUMBER})|:(\d{{2}}))?(?: horas)?\b', low)
                hours = re.search(rf'\b({NUMBER}) horas? depois\b', low)
                if clock:
                    hour, minute = number(clock[1]), number(clock[2]) if clock[2] else int(clock[3] or 0)
                    time['minute'] = hour * 60 + minute if hour < 24 and minute < 60 else None
                elif hours and time['minute'] is not None:
                    day_delta, time['minute'] = divmod(time['minute'] + number(hours[1]) * 60, 24 * 60)
                    time['day'] += day_delta
                elif re.search(r'\b(?:depois|à noite|naquela noite|naquela tarde)\b', low):
                    time['minute'] = None

                for existing in original_facts[block.number]:
                    source = original_events.get(existing.get('event_id'), {})
                    token_index = source.get('token_index')
                    belongs = token_index in range(sent.start, sent.end) if token_index is not None else existing['evidence']['range'] == proof['range']
                    if belongs:
                        existing.update(valid_from=dict(time), context=context, explicit_clock=clock is not None and time['minute'] is not None)

                # Use apenas menções anteriores/atuais; nunca antecedentes futuros.
                local_people = [p for p in scene.participants if proof['range']['start'] <= p['evidence']['range']['start'] < proof['range']['end']]
                names = {p['name']: p['id'] for p in local_people}
                def resolve(name):
                    if name.casefold() in {'ele', 'ela', 'seu', 'sua'}:
                        refs = [r['reference'] for r in scene.references if r['reference'] and proof['range']['start'] <= r['evidence']['range']['start'] < proof['range']['end']]
                        return refs[0] if len(set(refs)) == 1 else recent_actor if not names and len({p['id'] for p in scene.participants if p['evidence']['range']['end'] <= proof['range']['start']}) == 1 else None
                    return names.get(name)
                frame = Roles(scene, sent, offset)
                actor = frame.subject()
                explicit_actor = actor is not None
                prior_people = {p['id'] for p in scene.participants if p['evidence']['range']['end'] <= proof['range']['start']}
                if not actor and not frame.has_subject() and len(prior_people) == 1:
                    actor = recent_actor
                if not actor and not names and len(prior_people) == 1 and re.match(r'(?:Poucas horas depois, )?seus?\b', text, re.I):
                    actor = recent_actor
                objects = {o['id']: o for o in scene.objects if o.get('identity_status') == 'resolved' and proof['range']['start'] <= o['evidence']['range']['start'] < proof['range']['end']}
                obj = frame.object()
                if obj is None and len(objects) == 1 and not frame.has_subject():
                    obj = next(iter(objects))
                from .narrative import governing_verb
                location_starts = {offset + t.idx for t in sent if t == sent.root or
                                   (governing_verb(t) == sent.root and (t.head == sent.root or t.head.lemma_ in {'reunião', 'direção'}))}
                places = [p['id'] for p in scene.location if proof['range']['start'] <= p['evidence']['range']['start'] < proof['range']['end']
                          and p['evidence']['range']['start'] in location_starts]
                location = places[-1] if places else None

                def fact(subject, relation, value, kind='OBSERVE', polarity='positive', inference='explicit', agent=None, **extra):
                    if subject is None or value is None:
                        return None
                    if inference == 'explicit' and not explicit_actor and subject == actor and actor is not None:
                        inference = 'strong_inference'
                    event = dict(id=f'generic_{block.number}_{sent.start_char}_{len(scene.events)}',
                                 type=kind, subject=agent if agent is not None else actor, object=obj, location=location, action=relation,
                                 asserted=True, polarity=polarity, confidence=.9 if inference == 'explicit' else .8, event_confidence=.9 if inference == 'explicit' else .8, evidence=proof,
                                 inference_level=inference, time=dict(time), **extra)
                    dependencies = [p.get('entity_confidence', .8) for p in scene.participants
                                    if p['id'] == event['subject'] and proof['range']['start'] <= p['evidence']['range']['start'] < proof['range']['end']]
                    dependencies += [r['reference_confidence'] for r in scene.references if r['reference'] == event['subject']
                                     and proof['range']['start'] <= r['evidence']['range']['start'] < proof['range']['end']]
                    if dependencies:
                        event['confidence'] = event['event_confidence'] = min(event['event_confidence'], *dependencies)
                    scene.events.append(event)
                    scene.actions.append(event['id'])
                    existing = next((f for f in scene.facts if f['evidence']['paragraph'] == block.number and f['subject'] == subject and f['relation'] == relation and f['value'] == value and f['polarity'] == polarity and any(e['id'] == f.get('event_id') and e.get('token_index') in range(sent.start, sent.end) for e in scene.events)), None)
                    item = existing or add_fact(scene, event, subject, relation, value, inference, polarity)
                    item['evidence'] = proof
                    if item['event_id'] != event['id']:
                        scene.events.pop()
                        scene.actions.pop()
                    item.update(fact_type=TYPES.get(relation, 'STATE') + '_FACT', valid_from=dict(time), valid_until=None, generic=True, context=context, **extra)
                    if inference == 'weak_inference':
                        item.update(confidence=.45, fact_confidence=.45)
                    return item

                identity = re.search(r'\bapresentou-se como (' + NAME + r')', text)
                if identity:
                    ident = key('char', identity[1])
                    identity_claim = fact(ident, 'identity_name', identity[1], 'TELL')
                    if not any(p['id'] == ident for p in scene.participants):
                        scene.participants.append(dict(id=ident, name=identity[1], aliases=[], role='actor', presence='explicit_action', gender='', number='Sing', evidence=proof))
                if weekday is not None:
                    fact(scene.id, 'weekday', weekday, expected_weekday=expected_day if 'dia seguinte' in low else None)
                age = re.search(rf'\b(?:tinha|tem|tenho|completei|completou|comemorou (?:seu |o )?aniversário de) ({CARDINAL}) anos\b', low)
                if age is None and any(f['relation'] == 'age' and f['subject'] == actor for f in scene.facts):
                    age = re.search(r'\bcompletou (\d+)(?=[.!]|$)', low)
                if age:
                    age_predicate = frame.predicate(sent.start_char + age.start())
                    age_actor = frame.subject(age_predicate) or (actor if not frame.has_subject() else None)
                if age and age_actor and frame.factual_attribute(age_predicate):
                    fact(age_actor, 'age', number(age[1]), agent=age_actor, polarity='negative' if re.search(NEGATION, low[:age.start()]) else 'positive')
                weak_age = re.search(r'parecia ter (?:pouco mais de )?(\d+)', low)
                if weak_age:
                    fact(actor, 'age', int(weak_age[1]), inference='weak_inference')
                if re.search(r'\b(?:era|é) filh[oa] únic[oa]\b', low) and not re.search(NEGATION, low):
                    fact(actor or next(iter(names.values()), None), 'siblings', 'none', quantifier='only')
                sibling = re.search(rf'\b[Ss](?:ua|eu) irm(?:ão|ã) (?:mais velh[oa],? )?({NAME})', text)
                if sibling and recent_actor and len(prior_people) == 1:
                    relative = key('char', sibling[1])
                    fact(recent_actor, 'sibling', relative, 'RELATION_CHANGE')
                    actor = relative
                    if not any(p['id'] == relative for p in local_people):
                        scene.participants.append(dict(id=relative, name=sibling[1], role='actor', presence='explicit_action', gender='', number='Sing', evidence=proof))

                # Conhecimento é um fato sobre a personagem, não uma verdade do narrador.
                knowledge = re.search(r'\b(soube|sabia|sabe|sei|descobri|descobriu|aprendi|aprendeu|recebeu a notícia|contou|disse|revelou)\b', low)
                if knowledge and actor:
                    knowledge_actor = frame.subject(frame.predicate(sent.start_char + knowledge.start())) or actor
                    tail = text[knowledge.end():]
                    topic = re.match(r'\s*(?:(?:a|para) ' + NAME + r'\s+)?\b(?:sobre (?:o |a )?|d[oa] |que )(.+?)(?=\s+(?:n[ao] (?:segunda|terça|quarta|quinta|sexta|sábado|domingo)|às )|[.!]|$)', tail)
                    if topic:
                        content = re.sub(r'^notícia d[ao] ', '', topic[1].casefold().strip())
                        death = re.match(r'(.+?) havia morrido', content)
                        if death: content = 'morte de ' + death[1]
                        negative = bool(re.search(NEGATION, low[:knowledge.start()]))
                        relation = 'tells' if knowledge[1] in {'contou', 'disse', 'revelou'} else 'knows'
                        fact(knowledge_actor, relation, content, 'TELL' if relation == 'tells' else 'LEARN', polarity='negative' if negative else 'positive', explicit_clock=clock is not None and time['minute'] is not None)
                    elif knowledge[1] in {'contou', 'disse', 'revelou'} and not re.search(NEGATION, low[:knowledge.start()]) and re.match(r'\s+(?:isso|aquilo|a ' + NAME + r'\s*[.!]?$)', tail):
                        topics = {f['value'] for f in scene.facts if f['subject'] == knowledge_actor and f['relation'] in {'knows', 'tells'} and f['polarity'] == 'positive'
                                  and f['evidence']['range']['end'] <= proof['range']['start']}
                        if len(topics) == 1:
                            fact(knowledge_actor, 'tells', next(iter(topics)), 'TELL', inference='strong_inference', explicit_clock=clock is not None and time['minute'] is not None)

                if any(t.lemma_ in REPORTING for t in sent):
                    continue
                negative_meet = re.search(rf'({NAME}) (?:nunca|jamais|não) (?:havia )?(?:conhecido|conheceu|encontrou) ({NAME})', text)
                if negative_meet:
                    fact(resolve(negative_meet[1]), 'met', key('char', negative_meet[2]), 'MEET', polarity='negative')
                past_meet = re.search(rf'\b(?:viagem que fizera com|viajou com|conheceu|encontrou) ({NAME})', text)
                if past_meet and not negative_meet:
                    fact(actor, 'met', key('char', past_meet[1]), 'MEET')

                negative = bool(re.search(r'\b(?:não|nunca|jamais|ninguém)\b', low))
                if not negative:
                    if obj:
                        if re.search(r'\b(?:destruíd[oa]|destruiu|queimou|rasgou)\b', low):
                            fact(obj, 'object_state', 'destroyed', 'DESTROY')
                        elif re.search(r'\b(?:reparou|restaurou|reconstruiu)\b', low):
                            fact(obj, 'object_state', 'repaired', 'REPAIR')
                        elif actor and re.search(r'\b(?:releu|leu|usou|abriu|tirou|pegou)\b', low):
                            fact(obj, 'object_use', actor, 'USE')
                        state = re.search(r'\b(?:estava|está|ficou) (abert[oa]|fechad[oa]|trancad[oa])\b', low)
                        transition = re.search(r'\b(abriu|fechou|trancou|destrancou)\b', low)
                        states = {'abriu': ('open', 'OPEN'), 'fechou': ('closed', 'CLOSE'), 'trancou': ('locked', 'LOCK'), 'destrancou': ('unlocked', 'UNLOCK')}
                        if transition:
                            value, kind = states[transition[1]]
                            fact(obj, 'door_state' if objects.get(obj, {}).get('base') in {'porta','janela'} else 'object_state', value, kind, transition=True)
                        elif state:
                            value = 'open' if state[1].startswith('abert') else 'closed' if state[1].startswith('fechad') else 'locked'
                            fact(obj, 'door_state' if objects.get(obj, {}).get('base') in {'porta','janela'} else 'object_state', value, transition=False)
                        availability = re.search(r'\b(?:estava|está|ficou) (indisponível|disponível)\b', low)
                        if availability:
                            fact(obj, 'availability_state', 'unavailable' if availability[1] == 'indisponível' else 'available')
                        stationary = re.search(r'\b(?:estava|está|ficou) (?:sobre a |sobre o |na |no )([\wá-ú]+)', low)
                        if stationary:
                            fact(obj, 'object_location', stationary[1], transition=False)
                        placed = re.search(r'\b(?:deixou|guardou|colocou)\b.*?\b(?:sobre a |sobre o |na |no )([\wá-ú]+)', low)
                        if placed:
                            fact(obj, 'object_location', placed[1], 'LOSE' if 'deixou' in low else 'MOVE', holder=actor, transition=True)
                        removed = re.search(r'\b(?:tirou|retirou)\b.*?\b(?:do|da) ([\wá-ú]+)', low)
                        if removed and actor:
                            # A origem é evidência da retirada, não o destino atual.
                            fact(obj, 'object_location', 'carried', 'ACQUIRE', holder=actor, source_location=removed[1], transition=True)
                        if re.search(r'\b(?:pegou|apanhou|recuperou)\b', low):
                            fact(obj, 'holder', actor, 'ACQUIRE')
                            fact(obj, 'object_location', 'carried', 'ACQUIRE', holder=actor, transition=True)
                        transfer = re.search(rf'\b(?:entregou|devolveu|deu|entregue|devolvido|devolvida)\b.*?\b(?:a|para) ({NAME})', text)
                        if transfer:
                            recipient = key('char', transfer[1])
                            fact(obj, 'holder', recipient, 'TRANSFER', from_entity=actor, to_entity=recipient)
                            fact(actor, 'possesses', obj, 'TRANSFER', polarity='negative')
                            fact(recipient, 'possesses', obj, 'TRANSFER')
                    if actor:
                        if re.search(r'\b(?:morreu|estava mort[oa])\b', low):
                            fact(actor, 'life_state', 'dead', 'DIE')
                        elif re.search(r'\b(?:ressuscitou|reviveu)\b', low):
                            fact(actor, 'life_state', 'alive', 'STATE_CHANGE')
                        elif re.search(r'\b(?:entrou|correu|caminhou|respondeu|abriu|chegou)\b', low):
                            fact(actor, 'activity', 'active', 'MOVE')
                        if re.search(r'\b(?:curou|recuperou-se|estava curad[oa])\b', low):
                            healed = frame.entity(next((t for t in sent.root.children if t.dep_ == 'obj'), None), 'person') if sent.root.lemma_ == 'curar' else actor
                            fact(healed, 'mobility', 'healthy', 'HEAL', patient=healed)
                        elif re.search(r'\bcorreu\b', low):
                            fact(actor, 'mobility_use', 'running', 'MOVE')
                        hair = re.search(r'\b(?:(curtos|longos) cabelos|cabelos (curtos|longos))\b', low)
                        if hair:
                            fact(actor, 'physical_attribute', 'hair:' + ('short' if (hair[1] or hair[2]) == 'curtos' else 'long'), transition=bool(re.search(r'\b(?:cortou|alongou|peruca)\b', low)))
                        located = re.search(r'\b(?:entrou|chegou|saiu|estava|está|abriu|respondeu|trabalhava)\b', low)
                        if location and located:
                            enter = bool(re.search(r'\b(?:entrou|chegou)\b', low))
                            leave = bool(re.search(r'\bsaiu\b', low))
                            fact(actor, 'location', location, 'LEAVE' if leave else 'ENTER' if enter else 'MOVE', entry=enter, leave=leave, explicit_clock=clock is not None and time['minute'] is not None, distance_km=(number(re.search(rf'({NUMBER}) quilômetros', low)[1]) if re.search(rf'({NUMBER}) quilômetros', low) else None))
                        if re.search(r'\bentrou\b', low):
                            fact(actor, 'access', location or scene.id, 'ENTER')
                        if re.search(r'\bentrou sozinh[oa]\b', low):
                            fact(actor, 'alone_entry', location or scene.id, 'ENTER')
                        elif re.search(r'\brespondeu\b.*\b(?:dentro|outro lado da mesa)\b', low):
                            fact(actor, 'scene_speech', location or scene.id, 'TELL')
                from .narrative_memory import physical_facts
                physical_facts(frame, text, actor, fact)
                injury = re.search(r'\b(?:perna|pé)\b.*\b(?:engessad[oa]|quebrad[oa])\b', low)
                if injury and not re.search(r'\b(?:não|nunca|jamais)\b', low[:injury.end()]):
                    target = None
                    if target is None:
                        named = re.search(r'\b(?:perna|pé)(?: direit[oa]| esquerd[oa])?(?: engessad[oa]| quebrad[oa])? de (' + NAME + r')', text)
                        if named:
                            target = key('char', named[1])
                            scene.participants.append(dict(id=target, name=named[1], role='mentioned', presence='unresolved', gender='', number='Sing', evidence=proof))
                    fact(target, 'mobility', 'injured', 'OBSERVE')
                profession = re.search(r'\b(?:trabalhava como|trabalha como|era|é) (professor[a]?|médic[oa]|enfermeir[oa]|advogad[oa]|engenheir[oa]|motorista|jornalista)\b', low)
                if profession and not negative:
                    predicate = frame.predicate(sent.start_char + profession.start())
                    owner = frame.subject(predicate)
                    if owner and frame.factual_attribute(predicate):
                        fact(owner, 'profession', profession[1], agent=owner)
                if re.search(r'\b(?:nunca|jamais) havia trabalhado com ensino\b', low):
                    fact(actor, 'profession', 'professor', polarity='negative')
                family = re.search(rf'({NAME}) (?:era|é) irm(?:ão|ã) de ({NAME})', text)
                if family and not negative:
                    fact(key('char', family[2]), 'sibling', key('char', family[1]), 'RELATION_CHANGE')
                    fact(key('char', family[1]), 'sibling', key('char', family[2]), 'RELATION_CHANGE')
                relation = re.search(rf'({NAME}) (?:era|é) (pai|mãe|amig[oa]|cônjuge|marido|esposa|professor[a]?|chefe) de ({NAME})', text)
                if relation and not negative:
                    left, right = resolve(relation[1]), resolve(relation[3])
                    link = {'pai': 'parent', 'mãe': 'parent', 'amigo': 'friend', 'amiga': 'friend',
                            'cônjuge': 'spouse', 'marido': 'spouse', 'esposa': 'spouse',
                            'professor': 'teacher', 'professora': 'teacher', 'chefe': 'boss'}[relation[2]]
                    fact(left, link, right, 'RELATION_CHANGE')
                    if link in {'friend', 'spouse'}:
                        fact(right, link, left, 'RELATION_CHANGE')
                wounded = re.search(r'\b(?:foi ferid[oa]|estava ferid[oa]|estava machucad[oa]|feriu)\b', low)
                if wounded and not negative:
                    patient = frame.subject(patient=True)
                    if wounded[0] == 'feriu':
                        patients = [frame.entity(t, 'person') for t in sent.root.children if t.dep_ == 'obj']
                        patient = patients[0] if len(patients) == 1 else None
                    kind = 'INJURE' if sent.root.pos_ == 'VERB' and sent.root.lemma_ == 'ferir' else 'OBSERVE'
                    fact(patient, 'mobility', 'injured', kind, patient=patient)
                after = re.search(rf'({NAME}) chegou depois de ({NAME})', text)
                if after:
                    fact(resolve(after[1]), 'arrival_after', key('char', after[2]), 'MOVE')
                waiting = re.search(rf'({NAME}) encontrou ({NAME}) esperando por (?:ela|ele) quando chegou', text)
                if waiting:
                    fact(resolve(waiting[1]), 'arrival_after', key('char', waiting[2]), 'MOVE')
                duration = re.search(rf'\b(?:viagem|trajeto) levaria ({NUMBER}) horas?', low)
                if duration:
                    fact(scene.id, 'duration', number(duration[1]) * 60)
                elapsed = re.search(rf'\bsaíram às ({NUMBER}) e chegaram às ({NUMBER})', low)
                if elapsed:
                    fact(scene.id, 'elapsed', (number(elapsed[2]) - number(elapsed[1])) % 24 * 60)
                if actor:
                    recent_actor = actor
        scene.facts.sort(key=lambda f: (f['evidence']['range']['start'], f['id']))
        scene.events.sort(key=lambda e: (e['evidence']['range']['start'], e['id']))
        scene.present_entities = sorted({f['subject'] for f in scene.facts if f.get('generic') and f['relation'] in {'location', 'activity', 'scene_speech'} and not f.get('leave')})
        scene.entered_entities = sorted({f['subject'] for f in scene.facts if f.get('entry')})
        scene.left_entities = sorted({f['subject'] for f in scene.facts if f.get('leave')})
        for person in list(scene.present_entities):
            latest_presence = next((f for f in reversed(scene.facts) if f['subject'] == person and f['relation'] in {'location', 'activity', 'scene_speech'}), {})
            if latest_presence.get('leave'):
                scene.present_entities.remove(person)
        scene.mentioned_entities = sorted({p['id'] for p in scene.participants} - set(scene.present_entities))
    latest = {}
    for scene in scenes:
        for item in scene.facts:
            item.setdefault('fact_type', TYPES.get(item['relation'], 'STATE') + '_FACT')
            item.setdefault('valid_from', None)
            item.setdefault('valid_until', None)
            if item['relation'] in {'object_state', 'life_state'} and item['polarity'] == 'positive':
                item.setdefault('generic', True)
                item.setdefault('context', scene_contexts[scene.id])
            if item.get('generic') and item['relation'] in {'door_state', 'object_state', 'holder', 'object_location', 'life_state', 'mobility'}:
                slot = item['subject'], item['relation'], item['context']
                old = latest.get(slot)
                if old and old['value'] != item['value']:
                    old['valid_until'] = item['valid_from']
                latest[slot] = item


def compare_generic(bank, manuscript, settings, ledger=None):
    """Compara fatos, transições e tempo; jamais transforma suspeitas em erro certo."""
    if not settings['rules'].get('coerencia_generica', True):
        return []
    blocks = {b.number: b for b in manuscript.blocks}
    facts = [f for f in bank.facts if f.get('generic') and f['inference_level'] != 'weak_inference'
             and (f.get('scope') != 'reported' or f['relation'] == 'identity_name') and f.get('fact_confidence', f['confidence']) >= .65]
    from .fact_comparisons import ComparisonLedger
    ledger = ledger or ComparisonLedger(bank.facts)
    out = []
    previous, alone, arrivals, presence = [ledger.cache() for _ in range(4)]
    labels = dict(age_conflict='Idades incompatíveis', relationship_conflict='Relação familiar', object_continuity='Continuidade de objeto', object_state_conflict='Estado de objeto', possession_conflict='Posse do objeto', state_transition='Mudança de estado', life_state_conflict='Estado de vida', character_state_conflict='Estado físico', physical_attribute_conflict='Característica física', background_conflict='Histórico da personagem', negative_fact_conflict='Fatos opostos', chronology_conflict='Cronologia relativa', duration_conflict='Duração', event_order_conflict='Ordem dos eventos', scene_presence='Presença em cena', location_conflict='Localização', locked_access='Entrada e porta trancada', identity_conflict='Identidade', premature_knowledge='Conhecimento antecipado')
    seen = set()
    presence_key = lambda f: (f['scene'], f['subject'], f['evidence']['range']['start'], f['evidence']['range']['end'])
    entries = {presence_key(f) for f in facts if f.get('entry')}
    actions = {presence_key(f) for f in facts if f['relation'] in {'activity', 'scene_speech'}}
    knowledge = {}
    for fact in facts:
        if fact['relation'] == 'knows' and fact['polarity'] == 'positive':
            knowledge.setdefault((fact['subject'], fact['value'], fact.get('context')), []).append(fact)

    def emit(code, old, new, reason, severity='possible_inconsistency'):
        signature = code, old['id'], new['id']
        if signature in seen: return
        seen.add(signature)
        proof = new['evidence']; related = [old['evidence'], proof]
        item = alert(blocks[proof['paragraph']], 'coerencia_generica', labels[code],
                     proof['start'], proof['end'], reason, 'média', related)
        item.update(category_code=code, severity=severity, confidence_score=min(old['confidence'], new['confidence']), suggestion=None, evidence=related)
        out.append(item)

    for f in facts:
        ledger.current = f
        # Memória local não atravessa cenas; o histórico completo continua no banco.
        for slot, prior in list(previous.items()):
            if prior['scene'] != f['scene'] and prior.get('persistence') != 'persistent' and prior['relation'] != 'weekday':
                del previous[slot]
        s, r, v = f['subject'], f['relation'], f['value']
        k = (s, r, v) if r in {'met', 'profession'} else (s, r)
        old = previous.get(k)
        same_context = old is not None and old.get('context') == f.get('context')
        if r == 'age' and same_context and old['value'] != v:
            years = f['valid_from']['year'] - old['valid_from']['year']
            if old['polarity'] == f['polarity'] == 'positive' and (v < old['value'] or abs(v - old['value'] - years) > 1):
                emit('age_conflict', old, f, 'As idades não acompanham o intervalo temporal reconhecido. Confira a idade ou a passagem de tempo.')
        elif r == 'sibling':
            only = previous.get((s, 'siblings'))
            if only and only['value'] == 'none':
                emit('relationship_conflict', only, f, 'A personagem foi apresentada como filha única e agora tem um irmão ou irmã. Confira o vínculo familiar.')
        elif r == 'object_location' and same_context and (
                f.get('source_location') and old['value'] not in {f['source_location'], 'carried'}
                or not f.get('transition') and old['value'] not in {v, 'carried'}):
            emit('object_continuity', old, f, 'O objeto reaparece em outro local sem aquisição ou deslocamento reconhecido entre as evidências.')
        elif r == 'object_use':
            state = previous.get((s, 'object_state'))
            if state and state['value'] == 'destroyed':
                emit('object_state_conflict', state, f, 'O mesmo objeto é usado após ser destruído; confira restauração, cópia ou mudança de contexto.')
            holder = previous.get((s, 'holder'))
            if holder and v != s and holder['value'] != v and holder['scene'] == f['scene']:
                emit('possession_conflict', holder, f, 'O objeto estava com outra personagem e é usado sem devolução reconhecida.')
        elif r == 'door_state' and same_context and not f.get('transition') and old['value'] != v:
            emit('state_transition', old, f, 'O estado mudou sem uma transição explícita reconhecida.', 'editorial_attention')
        elif r == 'activity':
            state = previous.get((s, 'life_state'))
            if state and state['value'] == 'dead':
                emit('life_state_conflict', state, f, 'A personagem age após uma morte narrada. Confira sonho, retrospecto, engano ou retorno à vida.')
        elif r == 'mobility_use':
            state = previous.get((s, 'mobility'))
            if state and state['value'] == 'injured':
                emit('character_state_conflict', state, f, 'A ação pode ser incompatível com a lesão descrita. Confira recuperação ou explicação intermediária.')
        elif r == 'physical_action':
            state = previous.get((s, 'physical_state'))
            if state and state['polarity'] == 'positive' and state['value'] in {'leg_disabled','leg_injured','leg_impaired','unconscious'}:
                emit('character_state_conflict', state, f, 'A ação exige capacidade física afetada pelo estado anterior. Confira recuperação, passagem de tempo ou explicação intermediária.')
        elif r == 'physical_attribute' and same_context and old['value'] != v and not f.get('transition') and f['valid_from']['year'] == old['valid_from']['year']:
            emit('physical_attribute_conflict', old, f, 'A característica física mudou no mesmo contexto sem transformação reconhecida.')
        elif r in {'profession', 'met'} and old and old['value'] == v and old['polarity'] != f['polarity']:
            emit('background_conflict' if r == 'profession' else 'negative_fact_conflict', old, f, 'Uma afirmação e uma negação sobre o mesmo histórico parecem incompatíveis.')
        elif r == 'weekday' and f.get('expected_weekday') is not None and v != f['expected_weekday'] and previous.get(('timeline', 'weekday')):
            emit('chronology_conflict', previous['timeline', 'weekday'], f, 'O dia da semana não corresponde ao dia seguinte da referência anterior.')
        elif r == 'elapsed':
            expected = previous.get((s, 'duration'))
            if expected and expected['value'] != v:
                emit('duration_conflict', expected, f, 'A duração observada difere da duração prevista; confirme se houve mudança no trajeto.', 'editorial_attention')
        elif r == 'arrival_after':
            inverse = arrivals.get((v, s, f['scene']))
            if inverse: emit('event_order_conflict', inverse, f, 'As duas afirmações invertem a ordem de chegada das mesmas personagens.')
            arrivals[s, v, f['scene']] = f
        elif r == 'alone_entry':
            # Entrar sozinha não prova sala vazia. A ausência é somente uma pergunta.
            alone[f['scene']] = f
        elif r == 'location' and same_context and old['value'] != v and not old.get('leave'):
            a, b = old['valid_from'], f['valid_from']
            if a and b and all(a[x] == b[x] for x in ('day', 'year', 'week', 'weekday')) and old.get('explicit_clock') and f.get('explicit_clock') and a['minute'] is not None and b['minute'] is not None and 0 <= b['minute'] - a['minute'] <= 5 and (a['minute'] == b['minute'] or (f.get('distance_km') or 0) >= 20):
                emit('location_conflict', old, f, 'Os horários e locais indicam simultaneidade ou deslocamento muito rápido para a distância explícita. Confira transporte ou passagem de tempo.')
        elif r == 'access':
            locked = [x for slot, x in previous.items() if slot[1] == 'door_state' and x['value'] == 'locked' and x['scene'] == f['scene']]
            if len(locked) == 1:
                ledger.record(locked[0])
                emit('locked_access', locked[0], f, 'Houve uma entrada após trancar a porta, sem abertura reconhecida. Confirme por onde a personagem entrou.', 'author_query')
        elif r == 'identity_name' and old and old['value'] != v:
            emit('identity_conflict', old, f, 'A mesma pessoa apresentou nomes diferentes. Pode ser pseudônimo, mentira ou revelação; confirme a intenção.', 'author_query')
        if r in {'activity', 'scene_speech'}:
            prior = presence.get((f['scene'], s))
            entry = alone.get(f['scene'])
            introduced = presence_key(f) in entries
            missing = (prior and prior.get('leave')) or (entry and entry['subject'] != s and prior is None)
            if missing and not introduced:
                emit('scene_presence', prior or entry, f, 'A personagem age sem presença estabelecida, ou depois de sair. Confirme a entrada ou permanência no local.', 'author_query')
            presence[f['scene'], s] = f
        elif r == 'location':
            prior = presence.get((f['scene'], s))
            if not prior or f.get('entry') or f.get('leave') or prior['evidence']['range']['start'] != f['evidence']['range']['start']:
                # Uma fala localizada não pode apagar a saída antes da comparação da própria fala.
                if f.get('entry') or f.get('leave') or presence_key(f) not in actions:
                    presence[f['scene'], s] = f
        if r == 'weekday':
            previous['timeline', 'weekday'] = f
        previous[k] = f

    # A ordem do texto pode diferir da cronologia (conhecimento de terça narrado antes de segunda).
    for told in (f for f in facts if f['relation'] == 'tells' and f['polarity'] == 'positive'):
        candidates = knowledge.get((told['subject'], told['value'], told.get('context')), [])
        ledger.record(candidates, told)
        if not candidates: continue
        days = [f['valid_from']['week'] * 7 + f['valid_from']['weekday'] if f['valid_from']['weekday'] is not None else None for f in candidates]
        day = told['valid_from']['week'] * 7 + told['valid_from']['weekday'] if told['valid_from']['weekday'] is not None else None
        premature = day is not None and all(d is not None and day < d for d in days)
        if told.get('explicit_clock') and all(f.get('explicit_clock') for f in candidates) and (day is None and all(d is None for d in days) or day is not None and all(d == day for d in days)):
            t = told['valid_from']
            premature = all(t['year'] == f['valid_from']['year'] and t['day'] == f['valid_from']['day'] and t['minute'] < f['valid_from']['minute'] for f in candidates)
        if premature:
            emit('premature_knowledge', candidates[0], told, 'A personagem conta o fato antes da referência temporal em que teria tomado conhecimento dele. Confira a cronologia ou outra fonte da informação.')
    return out
