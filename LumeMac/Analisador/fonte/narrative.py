"""Classificação e referências locais conservadoras da memória v2.

Confianças são forças heurísticas, não probabilidades calibradas.
"""
import re
import hashlib
import json
from .semantic_roles import passive_agents, Roles
from .lexicon import flags, NONVERB
from .narrative_context import HUMAN, FIRST, valid_name, person_name, lemma as event_lemma, first_person, narrator, reference_candidates

ITEMS = set('pingente espada dispositivo carta arma chave livro artefato anel amuleto celular envelope bolsa porta janela pacote documento bilhete mochila caneta relógio papel folha lista equipamento caixa garrafa copo mesa cadeira bola corda borracha'.split())
PLACES = set('cidade torre sala portão telhado rua casa castelo floresta quarto vila reino hospital escritório escola colégio apartamento elevador cozinha restaurante estação parque biblioteca'.split())
ABSTRACT = set('direção suspiro medo coragem magia'.split())
TIME = set('ano semana dia mês hora minuto'.split())
BODY = set('mão braço rosto olho cabeça perna'.split())
NATURE = set('chuva neve vento gelo fogo'.split())
PRONOUNS = {'ele': ('Masc', 'Sing'), 'ela': ('Fem', 'Sing'), 'eles': ('Masc', 'Plur'),
            'elas': ('Fem', 'Plur'), 'dele': ('Masc', 'Sing'), 'dela': ('Fem', 'Sing'),
            'seu': ('', ''), 'sua': ('', ''), 'lo': ('Masc', 'Sing'), 'la': ('Fem', 'Sing'),
            'los': ('Masc', 'Plur'), 'las': ('Fem', 'Plur'), 'lhe': ('', 'Sing'), 'lhes': ('', 'Plur')}
OBJECT_PRONOUNS = {'o':('Masc','Sing'), 'a':('Fem','Sing'), 'os':('Masc','Plur'), 'as':('Fem','Plur')}
EVENTS = {'entrar': 'ENTER_LOCATION', 'sair': 'LEAVE_LOCATION', 'atravessar': 'MOVE',
          'caminhar': 'MOVE', 'ir': 'MOVE', 'chegar': 'MOVE', 'olhar': 'SEE', 'ver': 'SEE', 'saber': 'KNOW',
          'aprender': 'LEARN', 'pegar': 'ACQUIRE_OBJECT', 'receber': 'ACQUIRE_OBJECT',
          'quebrar': 'DESTROY_OBJECT', 'queimar': 'DESTROY_OBJECT', 'rasgar': 'DESTROY_OBJECT', 'reparar': 'STATE_CHANGE', 'restaurar': 'STATE_CHANGE', 'perder': 'LOSE_OBJECT', 'destruir': 'DESTROY_OBJECT', 'partir': 'DESTROY_OBJECT',
          'morrer': 'DIE', 'ferir': 'INJURE', 'machucar': 'INJURE', 'curar': 'HEAL', 'descobrir': 'DISCOVER',
          'entregar': 'TRANSFER_OBJECT', 'devolver': 'TRANSFER_OBJECT',
          'encontrar': 'FIND', 'conhecer': 'MEET', 'ler': 'USE_OBJECT', 'reler': 'USE_OBJECT',
          'abrir': 'STATE_CHANGE', 'fechar': 'STATE_CHANGE', 'trancar': 'STATE_CHANGE',
          'destrancar': 'STATE_CHANGE', 'ligar': 'STATE_CHANGE', 'desligar': 'STATE_CHANGE',
          'ativar': 'STATE_CHANGE', 'desativar': 'STATE_CHANGE',
          'guardar': 'STORE_OBJECT', 'segurar': 'HOLD_OBJECT',
          'retirar': 'ACQUIRE_OBJECT', 'tirar': 'ACQUIRE_OBJECT',
          'ouvir': 'HEAR', 'perceber': 'REALIZE',
          'criar': 'CREATE', 'formar': 'CREATE'}


def classify_entity(token):
    word = token.lower_ if token.lower_ in ITEMS else token.lemma_.casefold()
    if '-' in token.text or token.lower_ in PRONOUNS:
        return 'REJECT', None, .0
    if word in TIME: return 'TIME', 'TEMPORAL_UNIT', .9
    if word in ABSTRACT: return 'ABSTRACT_CONCEPT', 'ABSTRACT_CONCEPT', .9
    if word in BODY: return 'OBJECT', 'BODY_PART', .85
    if word in NATURE: return 'OBJECT', 'NATURAL_PHENOMENON', .85
    if word in PLACES: return 'LOCATION', None, .9
    # Geografia explícita, inclusive quando o parser erra o sujeito/copulativo.
    if token.pos_ == 'PROPN':
        if token.lower_ in HUMAN:
            return 'UNKNOWN', None, .3
        from .narrative_context import NO_NAMES
        nominal_name = (token.dep_ == 'nmod' and token.head.lemma_.casefold() in HUMAN
                        and any(c.dep_ == 'case' and c.lower_ == 'de' for c in token.children)
                        and token.text[:1].isupper() and token.text.isalpha() and token.lower_ not in NO_NAMES)
        if not (valid_name(token.text) or nominal_name) or token.is_stop:
            return 'REJECT', None, .0
        if flags(token.text) & NONVERB and ('Plur' in token.morph.get('Number') or token.dep_ == 'vocative'):
            return 'UNKNOWN', None, .3
        sent = token.sent.text
        prefix = token.doc.text[max(token.sent.start_char, token.idx-35):token.idx]
        if re.search(r'\b(?:' + '|'.join(PLACES) + r')\s+$', prefix, re.I):
            return 'LOCATION', None, .9
        if re.search(rf'\b{re.escape(token.text)}\s+(?:é|era)\s+(?:uma?\s+)?(?:cidade|vila|reino)\b', sent) or (token.head.lemma_.casefold() in PLACES and token.dep_ in {'nmod', 'appos', 'obl'}):
            return 'LOCATION', None, .9
        if any(t.dep_ == 'aux:pass' for a in token.ancestors for t in a.children) and any(c.lower_ in {'por', 'pelo', 'pela'} for c in token.children):
            return 'PERSON', None, .8
        if token.text[:1].isupper() and token.text.isalpha():
            owner = token.dep_ == 'nmod' and token.head.lemma_.casefold() in ITEMS | BODY and any(c.dep_ == 'case' and c.lower_ in {'de','do','da'} for c in token.children)
            recipient = any(c.dep_ == 'case' and c.lower_ in {'a','para'} for c in token.children) and any(a.lemma_ in {'entregar','devolver','dar','contar','dizer','revelar'} for a in token.ancestors)
            if token.dep_ in {'nsubj', 'nsubj:pass', 'obj', 'iobj', 'vocative'} or token.head.pos_ == 'VERB' or token.head.lemma_.casefold() in HUMAN or owner or recipient:
                return 'PERSON', None, .8
            return 'UNKNOWN', None, .3
    if word == 'objeto': return 'OBJECT', 'PHYSICAL_OBJECT', .7
    if word in ITEMS: return 'OBJECT', 'NARRATIVE_ITEM', .9
    if token.pos_ == 'NOUN': return 'OBJECT', 'UNKNOWN', .4
    return 'UNKNOWN', None, .2


def enrich(scene, block, doc, roles, ev, key, speech, registry):
    """Resolve menções antes dos eventos, sem usar antecedentes futuros."""
    token_entities, refs, objects = {}, {}, {}
    registry.observe(scene.id, ''.join(c if r == 'narracao' else ' ' for c,r in zip(block.text, roles)))
    for token in doc:
        if token.pos_ in {'PROPN', 'NOUN'}:
            kind, category, confidence = classify_entity(token)
            if token.pos_ == 'PROPN' and any(p['name'] == token.text for p in scene.location):
                kind, category, confidence = 'LOCATION', None, .9
            if kind == 'PERSON' and roles[token.idx] != 'narracao':
                known = any(p['name'] == token.text for p in scene.participants)
                introduction = token.head.lemma_.casefold() in HUMAN
                vocative = token.dep_ == 'vocative' and not token.is_stop
                if not (known or introduction or vocative):
                    kind, category, confidence = 'UNKNOWN', None, .3
            # Comparação não introduz item físico persistente.
            if category == 'NARRATIVE_ITEM' and re.search(r'\bcomo se fosse\b', token.sent.text[:token.idx-token.sent.start_char], re.I):
                kind, category, confidence = 'UNKNOWN', None, .2
            if token.dep_ == 'flat:name' and token.i - 1 in token_entities:
                continue
            name = token.lemma_.casefold() if kind != 'PERSON' and token.pos_ != 'PROPN' else token.text
            end = token.idx + len(token)
            if kind == 'PERSON':
                children = [c for c in token.children if c.dep_ == 'flat:name' and c.pos_ == 'PROPN' and valid_name(c.text)]
                if children:
                    end = max(end, max(c.idx + len(c) for c in children))
                    name = block.text[token.idx:end]
                name = person_name(name)
            ident = key({'PERSON': 'char', 'LOCATION': 'loc'}.get(kind, 'obj'), name)
            entry = dict(id=ident, name=name, type=kind, category=category, entity_confidence=confidence,
                         gender=(next((c.morph.get('Gender')[0] for c in token.children if c.dep_ == 'det' and c.morph.get('Gender')), '') if kind == 'PERSON' else next(iter(token.morph.get('Gender')), '')),
                         number=next(iter(token.morph.get('Number')), 'Sing'), evidence=ev(token.idx, end))
            if category == 'NARRATIVE_ITEM':
                agent = next((c for c in token.head.children if c.dep_ == 'nsubj'), None)
                if agent is None and token.head.dep_ in {'advcl','conj','xcomp'}:
                    agent = next((c for c in token.head.head.children if c.dep_ == 'nsubj'), None)
                actor_hint = token_entities.get(agent.i) if agent is not None else None
                if agent is not None and agent.i in refs:
                    actor_hint = refs[agent.i]['reference']
                recipient = None
                if token.head.lemma_ in {'entregar','devolver'}:
                    recipient = next((key('char', t.text) for t in token.head.subtree if t.pos_ == 'PROPN' and valid_name(t.text)
                                      and governing_verb(t) == token.head
                                      and any(c.dep_ in {'case','det'} and c.lower_ in {'a','para'} for c in t.children)), None)
                entry.update(registry.mention(token, entry['evidence'], scene.id, token.lower_ if token.lower_ in ITEMS else token.lemma_.casefold(), actor_hint, recipient))
            if kind == 'PERSON':
                entry['gender'] = entry['gender'] or next((p['gender'] for p in reversed(scene.participants) if p['id'] == ident and p['gender']), '')
            scene.entity_candidates.append(entry)
            if kind == 'PERSON':
                role = 'mentioned'
                if roles[token.idx] == 'narracao' and token.dep_ in {'nsubj', 'nsubj:pass'}:
                    role = 'patient' if token.dep_ == 'nsubj:pass' else 'speaker' if token.head.lemma_.casefold() in speech else 'actor'
                entry.update(role=role, presence='explicit_action' if role in {'actor', 'patient'} else 'unresolved')
                scene.participants.append(entry)
                token_entities[token.i] = entry['id']
            elif kind == 'LOCATION':
                scene.location.append(entry)
                token_entities[token.i] = entry['id']
            elif category in {'NARRATIVE_ITEM', 'PHYSICAL_OBJECT'}:
                scene.objects.append(entry)
                objects[token.i] = entry
                if entry.get('identity_status') != 'unresolved':
                    token_entities[token.i] = entry['id']
        # Descrições humanas ligam-se a nome explícito ou a uma identidade local.
        if token.lemma_.casefold() in HUMAN and roles[token.idx] == 'narracao':
            named = next((c for c in token.children if c.pos_ == 'PROPN' and valid_name(c.text)), None)
            if named is not None:
                ident, label = key('char', named.text), named.text
            else:
                previous = {p['id']: p for p in scene.participants if p.get('description') == token.lemma_.casefold()}
                if len(previous) > 1:
                    continue
                new = any(c.lower_ in {'um','uma','outro','outra'} for c in token.children)
                # Uma descrição definida pode retomar a única pessoa compatível.
                # Profissões e relações familiares não são inferidas apenas do gênero.
                if not previous and not new and token.lemma_.casefold() in {'rapaz','moça','homem','mulher','garoto','garota'}:
                    compatible = reference_candidates(scene, ev(token.idx, token.idx), next(iter(token.morph.get('Gender')), ''), next(iter(token.morph.get('Number')), 'Sing'))
                    if len(compatible) == 1:
                        previous = compatible
                old = next(iter(previous.values()), None) if not new else None
                ident = old['id'] if old else key('char', token.lemma_ + '@' + scene.id + (str(ev(token.idx,token.idx)['range']['start']) if new else ''))
                label = old['name'] if old else token.text.casefold()
            entry = dict(id=ident, name=label, type='PERSON', category=None, entity_confidence=.8,
                         gender=next(iter(token.morph.get('Gender')), ''), number=next(iter(token.morph.get('Number')), 'Sing'),
                         description=token.lemma_.casefold(), named=True if named is not None else bool(old and old.get('named', not old.get('description'))),
                         role='actor' if token.dep_ == 'nsubj' else 'mentioned',
                         presence='explicit_action' if token.dep_ == 'nsubj' else 'unresolved', evidence=ev(token.idx, token.idx+len(token)))
            scene.participants.append(entry)
            token_entities[token.i] = ident
        if roles[token.idx] == 'narracao' and (first_person(token) or token.lower_ in {'eu', 'me', 'mim'}):
            ident = narrator(scene, token, ev, key)
            if token.lower_ in {'eu', 'me', 'mim'}:
                token_entities[token.i] = ident
        pronoun = token.lower_
        clitic = re.search(r'-(lo|la|los|las|lhe|lhes)$', pronoun)
        if clitic:
            pronoun = clitic[1]
        if pronoun in PRONOUNS or (pronoun in OBJECT_PRONOUNS and token.pos_ == 'PRON'):
            gender, number = (PRONOUNS | OBJECT_PRONOUNS)[pronoun]
            candidates = reference_candidates(scene, ev(token.idx, token.idx), gender, number)
            # Retomada local de objeto: não force um pronome para uma pessoa distante.
            prior_objects = [o for o in scene.objects if o['evidence']['paragraph'] == block.number
                             and o['evidence']['end'] <= token.idx and o.get('identity_status') == 'resolved'
                             and (not gender or o.get('gender') == gender)]
            if pronoun in {'ele','ela'} and prior_objects and token.head.lemma_ in {'permitir','funcionar','quebrar','acender','apagar'}:
                nearest = prior_objects[-1]
                intervening = [p for p in candidates.values() if p['evidence']['range']['start'] > nearest['evidence']['range']['end']]
                candidates = {} if intervening else {nearest['id']:nearest}
            if pronoun in OBJECT_PRONOUNS:
                if event_lemma(token.head) in {'abrir','fechar','ligar','desligar','ativar','desativar','trancar','destrancar','reler','ler'}:
                    candidates = {}
                candidates.update({o['id']:o for o in scene.objects if o['evidence']['range']['end'] <= ev(token.idx,token.idx)['range']['start']
                                   and block.number - o['evidence']['paragraph'] <= 2 and o.get('identity_status') == 'resolved'
                                   and o.get('gender') == gender and o.get('number') == number})
            ids = list(candidates)
            resolved = ids[0] if len(ids) == 1 and roles[token.idx] == 'narracao' else None
            ref = dict(text=token.text, candidates=ids, reference=resolved,
                       status='resolved' if resolved else 'unresolved', reference_confidence=min(.85, candidates[resolved].get('entity_confidence', .8)) if resolved else .0,
                       evidence=ev(token.idx, token.idx + len(token)))
            scene.references.append(ref)
            refs[token.i] = ref
            # Aprender gênero apenas da referência já inequívoca, para usos posteriores.
            if resolved and gender:
                for person in scene.participants:
                    if person['id'] == resolved:
                        person['gender'] = gender
            if resolved and resolved.startswith('char_'):
                person = candidates[resolved]
                scene.participants.append({**person, 'evidence': ref['evidence'],
                                           'role': 'actor' if token.dep_ == 'nsubj' else 'mentioned',
                                           'entity_confidence': min(person.get('entity_confidence', .8), ref['reference_confidence'])})

    cache = {}

    def subject_of(token, visited=()):
        if token.i in cache:
            return cache[token.i]
        if token.i in visited:
            return None, 'unresolved', .0
        subject_token = next((c for c in token.children if c.dep_ in {'nsubj', 'nsubj:pass'}), None)
        if first_person(token) and (subject_token is None or subject_token.pos_ != 'PROPN'):
            result = (narrator(scene, token, ev, key), 'first_person', .85)
        elif subject_token is not None:
            if subject_token.dep_ == 'nsubj:pass':
                agents = passive_agents(token)
                result = (token_entities.get(agents[0].i), 'passive_agent', .9) if len(agents) == 1 else (None, 'unresolved_passive_agent', .0)
            elif any(c.dep_ == 'conj' for c in subject_token.children):
                result = (None, 'coordinated_subject', .0)
            elif subject_token.i in refs:
                ref = refs[subject_token.i]
                result = (ref['reference'], 'coreference', ref['reference_confidence'])
            else:
                result = (token_entities.get(subject_token.i), 'explicit', .9)
        elif token.dep_ in {'conj', 'xcomp', 'advcl'} and token.head.pos_ == 'VERB':
            # Controle de objeto (mandou Tomás criar...) não herda o sujeito.
            if any(c.dep_ in {'obj', 'iobj'} and (c.pos_ == 'PROPN' or c.pos_ == 'PRON') for c in token.head.children):
                result = (None, 'ambiguous_control', .0)
            else:
                ident, _, confidence = subject_of(token.head, (*visited, token.i))
                result = (ident, 'shared_subject', min(confidence, .8))
        else:
            # Sujeito oculto: somente continuidade narrativa imediata e unívoca.
            previous = [e for e in scene.events if e.get('predicate_evidence', e['evidence'])['range']['end'] <= ev(token.idx, token.idx)['range']['start']]
            last = previous[-1] if previous else None
            active = set(reference_candidates(scene, ev(token.idx, token.idx), number='Sing'))
            allowed = ('3' in token.morph.get('Person') and 'Sing' in token.morph.get('Number')
                       and token.dep_ == 'ROOT' and token.lemma_ not in {'haver', 'chover', 'parecer'}
                       and last and last.get('asserted') and last['subject'] in active and len(active) == 1)
            result = (last['subject'], 'subject_continuity', .7) if allowed else (None, 'unresolved', .0)
        if result[0] and result[0].startswith('loc_'):
            result = (None, 'non_person_subject', .0)
        cache[token.i] = result
        return result

    for token in doc:
        if (token.pos_ != 'VERB' and not first_person(token)) or roles[token.idx] != 'narracao':
            continue
        subject, basis, confidence = subject_of(token)
        obj = next((c for c in token.children if c.dep_ == 'obj'), None)
        if obj is None and first_person(token):
            # Recuperação limitada quando a forma finita foi etiquetada como nome.
            following = [t for t in token.sent if t.i > token.i and t.i in objects
                         and not any(first_person(v) or v.pos_ == 'VERB' for v in doc[token.i+1:t.i])]
            obj = following[0] if len(following) == 1 else None
        subject_token = next((c for c in token.children if c.dep_ in {'nsubj', 'nsubj:pass'}), None)
        object_entry = objects.get(obj.i) if obj is not None else None
        if object_entry is None and obj is not None and obj.i in refs:
            ident = refs[obj.i]['reference']
            object_entry = next((o for o in reversed(scene.objects) if o['id'] == ident), None)
        if subject_token is not None and subject_token.i in objects and not first_person(token):
            object_entry = objects[subject_token.i]
            if subject_token.dep_ != 'nsubj:pass':
                subject = None
        location = next((token_entities[t.i] for t in token.subtree if t.i in token_entities and token_entities[t.i].startswith('loc_')
                         and governing_verb(t) == token and (t.head == token or t.head.lemma_ == 'direção')), None)
        lemma = {'produziur': 'produzir'}.get(event_lemma(token), event_lemma(token))
        kind = 'SPEAK' if lemma in speech else EVENTS.get(lemma, 'SYNTACTIC_EVENT')
        frame = Roles(scene, token.sent, ev(0, 0)['range']['start'])
        patient = frame.entity(subject_token, 'person') if subject_token is not None and subject_token.dep_ == 'nsubj:pass' else frame.entity(obj, 'person')
        if kind == 'FIND' and patient:
            kind = 'MEET'
        if patient:
            object_entry = None
        confidence = confidence if subject else 0.0
        event_confidence = min(confidence, .9) if subject else .9 if object_entry and object_entry.get('identity_status') == 'resolved' else .0
        event = dict(id=f'event_{block.number}_{token.idx}', token_index=token.i, subject=subject,
                     predicate_evidence=ev(token.idx, token.idx + len(token)),
                     subject_basis=basis, reference_confidence=confidence, action=lemma,
                     object=(object_entry['id'] if object_entry and object_entry.get('identity_status') != 'unresolved' else None),
                     object_text=obj.text if obj is not None else None,
                     patient=patient,
                     location=location, destination=location if kind in {'MOVE', 'ENTER_LOCATION'} else None,
                     type=kind, evidence=ev(token.sent.start_char, token.sent.end_char),
                     asserted=is_asserted(token, roles), inference_level='explicit',
                     confidence=event_confidence, event_confidence=event_confidence)
        from .narrative_memory import enrich_event
        enrich_event(scene, event, token, frame, roles)
        # Elemento restrito ao complemento deste verbo, não a qualquer trecho da frase.
        elements = [t.lower_ for t in token.subtree if t.lower_ in ELEMENTS and governing_verb(t) == token]
        if elements and len(set(elements)) == 1 and subject and subject.startswith('char_'):
            if lemma in {'criar', 'produzir', 'invocar', 'lançar', 'usar', 'manipular'}:
                event.update(type='USE_ABILITY', ability=elements[0])
            elif lemma in {'dominar', 'conseguir'}:
                event.update(type='ABILITY_STATE', ability=elements[0])
        if event['type'] in {'USE_ABILITY', 'ABILITY_STATE'}:
            event['exclusive'] = any(t.lower_ in {'só', 'apenas', 'somente'} and governing_verb(t) == token for t in token.subtree)
        scene.events.append(event)
        scene.actions.append(event['id'])
    for token in doc:
        states = {'intacto': 'intact', 'intacta': 'intact', 'destruído': 'destroyed', 'destruída': 'destroyed', 'restaurado': 'repaired', 'restaurada': 'repaired', 'reparado': 'repaired', 'reparada': 'repaired'}
        if token.pos_ not in {'ADJ', 'NOUN'} or token.lower_ not in states or token.dep_ != 'ROOT' or not is_asserted(token, roles):
            continue
        noun = next((c for c in token.children if c.dep_ == 'nsubj'), None)
        obj = objects.get(noun.i) if noun is not None else None
        if obj and obj.get('identity_status') == 'resolved':
            event = dict(id=f'event_{block.number}_{token.idx}', token_index=token.i, subject=None, object=obj['id'],
                         action='state', type='STATE_CHANGE', state_after=states[token.lower_],
                         asserted=True, evidence=ev(token.sent.start_char, token.sent.end_char), confidence=.9, event_confidence=.9)
            scene.events.append(event)
            scene.actions.append(event['id'])
    infer_ability(scene, block, doc, roles, ev)


ELEMENTS = {'fogo', 'gelo', 'água', 'terra', 'ar', 'eletricidade'}


def governing_verb(token):
    return next((t for t in token.ancestors if t.pos_ == 'VERB'), None)


def is_asserted(token, roles):
    sent = token.sent
    # Uma ação narrativa adjunta ao marcador de fala tem sua própria modalidade.
    # "disse, pegando a carta" afirma pegar; "disse que pegou" apenas relata.
    branch = next((a for a in [token, *token.ancestors] if a.dep_ == 'advcl' and a.head.lemma_ in {'dizer','responder','perguntar','afirmar','pensar'}), None)
    if branch is not None:
        indices = [t.i for t in branch.subtree]
        sent = token.doc[min(indices):max(indices)+1]
    if re.search(r'\b(?:em sonho|num sonho|no sonho|em um sonho|flashback)\b', sent.text, re.I):
        return False
    if any(r != 'narracao' for r in roles[sent.start_char:sent.end_char]):
        return False
    if re.search(r'[—“”"?]|\b(?:se|caso|talvez|não|nunca|jamais|ninguém|nenhum)\b', sent.text, re.I):
        # Reflexivo se não é condicional.
        words = [t for t in sent if t.lower_ == 'se']
        if not words or any(t.pos_ == 'SCONJ' or t.dep_ == 'mark' for t in words) or re.search(r'[—“”"?]|\b(?:caso|talvez|não|nunca|jamais|ninguém|nenhum)\b', sent.text, re.I):
            return False
    if any(t.pos_ == 'AUX' and t.lemma_ == 'ir' for t in sent):
        return False
    if any(t.lemma_ in {'querer', 'poder', 'dever', 'tentar', 'imaginar', 'sonhar', 'planejar', 'esperar', 'fingir', 'dizer', 'contar', 'revelar', 'afirmar', 'negar'} or ('Sub' in t.morph.get('Mood') and t.lower_ not in FIRST) or 'Fut' in t.morph.get('Tense') or 'Cnd' in t.morph.get('Mood') for t in sent if t.pos_ in {'VERB', 'AUX'}):
        return False
    return True


def infer_ability(scene, block, doc, roles, ev):
    # Ligação causal local explícita: um único agente concentra magia, gelo se forma.
    for sent in doc.sents:
        events = [e for e in scene.events if e['evidence']['range'] == ev(sent.start_char, sent.end_char)['range']]
        focus = [e for e in events if e['action'] == 'concentrar' and e['subject'] and e['subject'].startswith('char_') and e['asserted']]
        match = re.search(r'\b(gelo|fogo|água|terra|ar|eletricidade) (?:começou a se formar|se formou|surgiu)\b', sent.text)
        if not match or len(focus) != 1 or not re.search(r'concentrou\b.*\bmagia\b.*\be\b', sent.text) or re.search(r'\b(?:mas|enquanto|naturalmente)\b', sent.text):
            continue
        actors = {e['subject'] for e in events if e['subject'] and e['subject'].startswith('char_')}
        if len(actors) != 1:
            continue
        focus[0].update(type='USE_ABILITY', ability=match[1], inference_level='strong_inference', event_confidence=.8)


def diagnostics(scenes, bank):
    from .fact_candidates import promotion_metrics
    refs = [r for s in scenes for r in s.references]
    turns = [t for s in scenes for t in s.dialogue_turns if t.get('turn_kind') != 'thought']
    events = [e for e in bank.events if e['type'] != 'SYNTACTIC_EVENT']
    rate = lambda xs, pred: sum(bool(pred(x)) for x in xs) / len(xs) if xs else None
    original = [e for e in events if not e['id'].startswith('generic_')]
    eligible = [e for e in original if e.get('asserted') and e['type'] in
                {'ENTER_LOCATION','LEAVE_LOCATION','MOVE','ACQUIRE_OBJECT','LOSE_OBJECT','DESTROY_OBJECT','STATE_CHANGE','DIE','INJURE','HEAL','USE_ABILITY','ABILITY_STATE','KNOW','LEARN','DISCOVER','TRANSFER_OBJECT','CREATE','FIND','MEET','USE_OBJECT'}]
    linked = {i for f in bank.facts for i in f.get('source_event_ids', [f.get('event_id')])}
    direct = {f.get('event_id') for f in bank.facts}
    return dict(entity_precision=None, false_entity_count=None, semantic_event_precision=None,
                false_fact_count=None, evaluation_status='requires_annotated_corpus',
                reference_resolution_rate=rate(refs, lambda r: r['status'] == 'resolved'),
                resolved_subject_rate=rate(events, lambda e: e['subject']),
                speaker_resolution_rate=rate(turns, lambda t: t['speaker']), semantic_event_count=len(events),
                fact_count=len(bank.facts), fact_conversion_rate=rate(events, lambda e: e['id'] in direct),
                eligible_event_count=len(eligible), eligible_fact_conversion_rate=rate(eligible, lambda e:e['id'] in linked),
                original_semantic_event_count=len(original), generated_fact_event_count=len(events)-len(original),
                reference_count=len(refs), dialogue_turn_count=len(turns),
                **bank.comparison_metrics, **promotion_metrics(bank), false_fact_rate=None,
                canonical_character_precision=None, canonical_object_precision=None,
                persistent_fact_count=sum(f.get('persistence') == 'persistent' for f in bank.facts),
                local_participant_count=len(bank.local_participants),
                fact_persistence_rate=rate(bank.facts, lambda f:f.get('persistence') == 'persistent'),
                metric_definitions=dict(reference_resolution_rate='resolved references / reference candidates; correctness requires annotation',
                    resolved_subject_rate='semantic events with a subject / semantic events; correctness requires annotation',
                    speaker_resolution_rate='speech turns with a speaker / speech turns; explicit thoughts excluded',
                    fact_conversion_rate='legacy: linked semantic events / all semantic events, including generated fact events',
                    eligible_fact_conversion_rate='original asserted state-changing events linked to facts / original asserted state-changing events',
                    fact_persistence_rate='facts eligible for persistent memory / all extracted facts; does not measure correctness',
                    canonical_character_precision='requires annotated corpus', canonical_object_precision='requires annotated corpus',
                    fact_candidate_count='one candidate per proposed effect plus one discarded candidate per event without an effect',
                    promoted_fact_count='accepted effect candidates; one transfer can yield multiple facts',
                    discarded_fact_candidate_count='candidates with status discarded; reasons included',
                    global_comparison_rate='unique compared fact pairs / unique eligible fact pairs in existing comparator routes; null for zero eligible pairs', false_fact_rate='requires annotated corpus'))


def promote(scenes, key):
    """Eventos assertivos com papéis resolvidos produzem fatos rastreáveis."""
    for scene in scenes:
        people = {p['id'] for p in scene.participants}
        items = {o['id'] for o in scene.objects if o.get('identity_status') == 'resolved'}
        for event in scene.events:
            from .narrative_audit import event_roles
            roles = event.setdefault('semantic_roles', event_roles(event))
            subject, obj = roles['AGENT'], roles['OBJECT']
            if not event.get('asserted'):
                continue
            kind = event['type']
            if kind in {'USE_ABILITY', 'ABILITY_STATE'} and subject in people:
                relation = 'ability' if event.get('exclusive') or kind == 'ABILITY_STATE' else 'demonstrated_ability'
                # O padrão legado "usa fogo" já expressa habilidade; não duplicar.
                existing = next((f for f in scene.facts if f['subject'] == subject and f['value'] == event['ability'] and f['relation'] in {'ability', 'demonstrated_ability'} and f['evidence']['range'] == event['evidence']['range']), None)
                if existing:
                    existing['event_id'] = event['id']
                else:
                    add_fact(scene, event, subject, relation, event['ability'],
                             event.get('inference_level', 'explicit'), scope='exclusive' if event.get('exclusive') else 'asserted')
            elif kind in {'ENTER_LOCATION', 'LEAVE_LOCATION', 'MOVE'} and subject in people and event.get('location') and event['action'] in {'entrar','sair','chegar'}:
                add_fact(scene, event, subject, 'left_location' if kind == 'LEAVE_LOCATION' else 'location', event['location'])
            elif kind in {'ACQUIRE_OBJECT', 'LOSE_OBJECT'} and subject in people and obj in items:
                add_fact(scene, event, subject, 'possesses', obj, polarity='negative' if kind == 'LOSE_OBJECT' else 'positive')
            elif kind in {'DESTROY_OBJECT', 'STATE_CHANGE'} and obj in items and event['action'] not in {'abrir','fechar','trancar','destrancar','ligar','desligar','ativar','desativar'}:
                state = event.get('state_after') or ('destroyed' if kind == 'DESTROY_OBJECT' else 'repaired')
                item = add_fact(scene, event, obj, 'object_state', state)
                item.update(transition=True, state_detail={'rasgar': 'torn', 'queimar': 'burned', 'quebrar': 'broken'}.get(event['action'], state))
            elif kind == 'DIE' and subject in people:
                if not any(f['relation'] == 'death_date' and f['evidence']['range'] == event['evidence']['range'] for f in scene.facts):
                    add_fact(scene, event, subject, 'life_state', 'dead')
            elif obj in items and event['action'] in {'abrir', 'fechar', 'trancar', 'destrancar', 'ligar', 'desligar', 'ativar', 'desativar'}:
                states = {'abrir':'open', 'fechar':'closed', 'trancar':'locked', 'destrancar':'unlocked',
                          'ligar':'on', 'desligar':'off', 'ativar':'on', 'desativar':'off'}
                state = states[event['action']]
                base = next((o.get('base') for o in scene.objects if o['id'] == obj), None)
                item = add_fact(scene, event, obj, 'door_state' if base in {'porta','janela'} else 'object_state', state)
                item['transition'] = True
            from .narrative_memory import promote_event
            promote_event(scene, event, people, items)
        for event in scene.events:
            text = event['evidence']['excerpt'].strip()
            if event['subject'] in people and re.fullmatch(r'[\wÁ-ú]+ nunca (?:havia )?conseguido produzir nenhum outro elemento[.!]?', text):
                add_fact(scene, event, event['subject'], 'ability', 'other_elements', polarity='negative', scope='historical')
        scene.facts.sort(key=lambda f: (f['evidence']['range']['start'], f['id']))


def add_fact(scene, event, subject, relation, value, inference='explicit', polarity='positive', scope='asserted'):
    duplicate = next((f for f in scene.facts if (f['subject'], f['relation'], f['value'], f['polarity'], f['scope'], f['evidence']['range']) ==
                     (subject, relation, value, polarity, scope, event['evidence']['range'])), None)
    if duplicate:
        return duplicate
    confidence = min(.9, event.get('event_confidence', .85))
    identity = hashlib.sha256(json.dumps([subject, relation, value, polarity, scope], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    fact = dict(id=f"fact_semantic_{event['id']}_{relation}_{identity}", scene=scene.id, subject=subject,
                relation=relation, value=value, polarity=polarity, scope=scope,
                inference_level=inference, confidence=confidence, fact_confidence=confidence,
                event_id=event['id'], evidence=event['evidence'])
    scene.facts.append(fact)
    return fact
