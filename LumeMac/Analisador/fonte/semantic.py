"""Memória narrativa: cenas, identidades e fatos com evidência e confiança.

Referências resolvidas alimentam eventos; falas e hipóteses não atestam ações.
"""
from dataclasses import dataclass, field, asdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import re
import unicodedata
from .analysis import SPEECH
from .narrative import enrich
from .narrative_identity import ObjectRegistry
from .narrative_dialogue import dialogue_roles, extract_turns
from .segments import classify
from .editorial.context import CUT
from .editorial.common import alert, evidence

RULES = ('memoria_narrativa', 'conflito_habilidade', 'conflito_objeto', 'conflito_cronologia', 'coerencia_generica')
NAME = r'[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç\u0300-\u036f]+(?: [A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç\u0300-\u036f]+)*'
ELEMENT = r'(?:fogo|gelo|água|terra|ar|eletricidade)'
DATE = r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
ABILITY = re.compile(rf'(?P<name>{NAME}) (?P<limit>só |apenas |nunca )?(?P<verb>usa|usava|domina|dominava|pode usar|podia usar|conseguiu usar|criou|produziu|invocou)(?: (?P<after>apenas|só))? (?:magia de )?(?P<value>{ELEMENT})[.!]?')
LEARN = re.compile(rf'(?P<name>{NAME}) (?:aprendeu a usar|passou a dominar) (?:magia de )?(?P<value>{ELEMENT})[.!]?')
OBJECT = re.compile(r'[Oo] (?P<name>pingente|dispositivo|espada|anel|amuleto)(?P<qualifier> (?:vermelho|azul|dourado|de [A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç\u0300-\u036f]+))? (?:(?:foi|estava|está|ficou) )?(?P<state>destruíd[oa]|intact[oa]|restaurad[oa]|reparad[oa]|reconstruíd[oa])(?: (?:estava|está) (?:no|na) [\w ]+)?[.!]?')
DEATH = re.compile(rf'(?P<name>{NAME}) morreu (?:em|no dia) (?P<date>{DATE})[.!]?')
NOW = re.compile(rf'(?:[Dd]ata atual(?: da cena)?\s*:\s*|[Hh]oje (?:é|era) (?:dia )?)(?P<date>{DATE})[.!]?')
CLAIM = re.compile(rf'[Oo]ntem (?:fez|completou) (?:exatamente )?(?P<years>\d+|um|dois|três|quatro|cinco|seis|sete|oito|nove|dez) anos?(?: (?:que|desde que) (?P<name>{NAME}) morreu)?[.!]?')


def key(kind, name):
    normalized = unicodedata.normalize('NFC', name).casefold()
    return kind + '_' + hashlib.sha256(normalized.encode()).hexdigest()[:12]


def text_evidence(offset, block, start=0, end=None):
    end = len(block.text) if end is None else end
    return {**evidence(block, start, end), 'type': 'text_evidence',
            'range': {'start': offset + start, 'end': offset + end}, 'excerpt': block.text[start:end]}


@dataclass
class Scene:
    id: str
    chapter: str
    start_paragraph: int
    end_paragraph: int
    entity_candidates: list = field(default_factory=list)
    participants: list = field(default_factory=list)
    speakers: list = field(default_factory=list)
    narrator: str = 'unknown'
    location: list = field(default_factory=list)
    time_reference: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    events: list = field(default_factory=list)
    dialogue_turns: list = field(default_factory=list)
    references: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    facts: list = field(default_factory=list)
    fact_candidates: list = field(default_factory=list)
    present_entities: list = field(default_factory=list)
    mentioned_entities: list = field(default_factory=list)
    entered_entities: list = field(default_factory=list)
    left_entities: list = field(default_factory=list)


@dataclass
class FactBank:
    characters: dict = field(default_factory=dict)
    local_participants: dict = field(default_factory=dict)
    objects: dict = field(default_factory=dict)
    locations: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)
    events: list = field(default_factory=list)
    fact_candidates: list = field(default_factory=list)
    incoming_fact_ids: dict = field(default_factory=dict)
    comparison_metrics: dict = field(default_factory=dict)

    @classmethod
    def consolidate(cls, scenes):
        bank = cls()
        for scene in scenes:
            bank.events.extend(scene.events)
            bank.facts.extend(deepcopy(scene.facts))
            bank.fact_candidates.extend(deepcopy(scene.fact_candidates))
            for person in scene.participants:
                collection = bank.local_participants if person.get('identity_tier') == 'local_participant' else bank.characters
                entity = collection.setdefault(person['id'], dict(id=person['id'], name=person['name'], aliases=[], mentions=[], facts=[], identity_tier=person.get('identity_tier'), promotion_basis=person.get('promotion_basis')))
                entity['mentions'].append(person)
                if person['name'] not in entity['aliases']:
                    entity['aliases'].append(person['name'])
            for obj in scene.objects:
                if obj.get('identity_status') == 'unresolved':
                    continue
                entity = bank.objects.setdefault(obj['id'], dict(id=obj['id'], name=obj['name'], owner=obj.get('owner'), identity_tier=obj.get('identity_tier'), promotion_basis=obj.get('promotion_basis'), aliases=[], mentions=[], facts=[]))
                entity['mentions'].append(obj)
                if obj['name'] not in entity['aliases']:
                    entity['aliases'].append(obj['name'])
            for place in scene.location:
                entity = bank.locations.setdefault(place['id'], dict(id=place['id'], name=place['name'], mentions=[]))
                entity['mentions'].append(place)
        for fact in bank.facts:
            collection = bank.objects if fact['subject'] in bank.objects else bank.locations if fact['subject'] in bank.locations else bank.local_participants if fact['subject'] in bank.local_participants else bank.characters
            if fact['subject'] in collection:
                collection[fact['subject']].setdefault('facts', []).append(fact['id'])
            if fact['relation'] == 'knows' and fact['polarity'] == 'positive' and fact['subject'] in bank.characters:
                bank.characters[fact['subject']].setdefault('known_facts', []).append(fact['id'])
        from .fact_candidates import derive_history
        active, bank.incoming_fact_ids = derive_history(scenes, bank.facts)
        # Histórico e estado reconhecido apontam para fatos, preservando a evidência.
        by_subject = {}
        for fact in bank.facts:
            by_subject.setdefault(fact['subject'], []).append(fact)
        for entity in [*bank.objects.values(), *bank.characters.values()]:
            relevant = by_subject.get(entity['id'], [])
            states = [f for f in relevant if f['relation'] in {'object_state', 'door_state', 'object_location', 'holder', 'life_state', 'mobility', 'physical_state', 'location', 'age', 'profession', 'physical_attribute', 'availability_state'} and f['polarity'] == 'positive' and f.get('scope') != 'reported' and f.get('fact_confidence', 0) >= .65]
            entity['state_history'] = [f['id'] for f in states]
            entity['current_state'] = {f['relation']: f['id'] for f in states if f['valid_until_position'] is None and not f.get('leave') and f.get('persistence') == 'persistent'}
            if entity['id'] in bank.characters:
                entity['knowledge_history'] = [dict(fact_id=f['id'], topic=f['value'], valid_from=f.get('valid_from'), polarity=f['polarity']) for f in relevant if f['relation'] == 'knows']
                entity['knowledge_state'] = {f['value']: dict(fact_id=f['id'], polarity=f['polarity']) for f in relevant if f['relation'] == 'knows' and f.get('persistence') == 'persistent' and not f.get('superseded_by')}
                possession = {}
                for f in relevant:
                    if f['relation'] == 'possesses' and f.get('persistence') == 'persistent':
                        if f['polarity'] == 'positive': possession[f['value']] = f['id']
                        else: possession.pop(f['value'], None)
                entity['possessions'] = possession
                entity['current_state']['possesses'] = dict(possession)
                entity['current_state']['knows'] = deepcopy(entity['knowledge_state'])
        return bank

    def to_dict(self):
        return {'schema_version': 2, **asdict(self)}


def extract(manuscript, docs, settings):
    """Usa os mesmos documentos sintáticos do Editorial; não reanalisa na comparação."""
    scenes = []
    registry = ObjectRegistry(key)
    labels = classify(manuscript.blocks, settings)
    scene = None
    for block, offset, doc, roles in zip(manuscript.blocks, manuscript.offsets, docs, labels):
        if block.heading:
            scene = None
            continue
        if scene is None or scene.chapter != block.chapter or CUT.match(block.text):
            scene = Scene(f'scene_{len(scenes)+1:04}', block.chapter, block.number, block.number)
            scenes.append(scene)
        scene.end_paragraph = block.number
        ev = lambda start=0, end=None: text_evidence(offset, block, start, end)
        roles = dialogue_roles(block.text, roles, NAME)
        enrich(scene, block, doc, roles, ev, key, SPEECH, registry)
        extract_turns(scene, block, roles, ev, key, NAME)
        # Fatos são extraídos somente de frases inteiramente narrativas.
        for sent in doc.sents:
            start, end = sent.start_char, sent.end_char
            if any(r != 'narracao' for r in roles[start:end]):
                continue
            fragment = sent.text.strip()
            proof = ev(start, end)
            def fact(subject, relation, value, polarity='positive', scope='asserted'):
                item = dict(id=f'fact_{block.number}_{start}_{len(scene.facts)}', scene=scene.id,
                            subject=subject, relation=relation, value=value, polarity=polarity,
                            scope=scope, confidence=.85, fact_confidence=.85, inference_level='explicit', evidence=proof)
                source = next((e for e in scene.events if e['evidence']['range'] == proof['range']), None)
                if relation in {'scene_date', 'anniversary_yesterday'}:
                    source = dict(id=f'event_time_{block.number}_{start}', subject=subject, object=None,
                                  action=relation, type='TIME_OBSERVATION', asserted=True,
                                  event_confidence=.85, confidence=.85, evidence=proof)
                    scene.events.append(source)
                item['event_id'] = source['id'] if source else None
                scene.facts.append(item)
                return item
            def actor(name):
                if name.casefold() in {'ele', 'ela', 'eles', 'elas'}:
                    return next((e['subject'] for e in scene.events if e['evidence']['range'] == proof['range'] and e['subject'] and e['subject'].startswith('char_')), None)
                ident = key('char', name)
                return ident if any(p['id'] == ident and proof['range']['start'] <= p['evidence']['range']['start'] < proof['range']['end'] for p in scene.participants) else None

            match = ABILITY.fullmatch(fragment)
            if match and actor(match['name']):
                name, value = match['name'], match['value']
                limit = (match['limit'] or match['after'] or '').strip()
                negative = limit == 'nunca'
                relation = 'demonstrated_ability' if match['verb'] in {'criou', 'produziu', 'invocou'} else 'ability'
                fact(actor(name), relation, value, 'negative' if negative else 'positive',
                     'historical' if negative else 'exclusive' if limit else 'asserted')
            match = LEARN.fullmatch(fragment)
            if match and actor(match['name']):
                fact(actor(match['name']), 'ability_change', match['value'])
            match = OBJECT.fullmatch(fragment)
            if match:
                mentions = [o for o in scene.objects if o.get('base') == match['name']
                            and proof['range']['start'] <= o['evidence']['range']['start'] < proof['range']['end']]
                if len(mentions) == 1 and mentions[0].get('identity_status') == 'resolved':
                    ident = mentions[0]['id']
                    state = match['state']
                    item = fact(ident, 'object_state', 'destroyed' if state.startswith('destru') else 'intact' if state.startswith('intact') else 'repaired')
                    if item['event_id'] is None:
                        event = dict(id=f'event_state_{block.number}_{start}', subject=None, object=ident,
                                     action='state', type='STATE_CHANGE', state_after=item['value'],
                                     evidence=proof, asserted=True, event_confidence=.9, confidence=.9)
                        scene.events.append(event)
                        scene.actions.append(event['id'])
                        item['event_id'] = event['id']
            match = DEATH.fullmatch(fragment)
            if match:
                parsed = parse_date(match['date'])
                if parsed and actor(match['name']):
                    fact(actor(match['name']), 'death_date', parsed.isoformat())
            match = NOW.fullmatch(fragment)
            if match:
                parsed = parse_date(match['date'])
                if parsed:
                    scene.time_reference.append(fact(scene.id, 'scene_date', parsed.isoformat()))
            match = CLAIM.fullmatch(fragment)
            if match:
                words = ['zero','um','dois','três','quatro','cinco','seis','sete','oito','nove','dez']
                years = int(match['years']) if match['years'].isdigit() else words.index(match['years'])
                fact(key('char', match['name']) if match['name'] else None, 'anniversary_yesterday', years)
    from .narrative import promote
    promote(scenes, key)
    from .generic_facts import extract_generic
    extract_generic(scenes, manuscript, docs, labels, key, text_evidence)
    from .narrative_audit import finalize
    finalize(scenes)
    from .narrative_memory import finalize_memory
    finalize_memory(scenes)
    from .fact_candidates import filter_candidates
    filter_candidates(scenes)
    return scenes


def parse_date(value):
    try:
        day, month, year = map(int, re.split(r'[/\-]', value))
        return date(year, month, day)
    except ValueError:
        return None


def compare(bank, manuscript, settings):
    """Apenas compara fatos, sem NLP ou releitura livre do manuscrito."""
    from .fact_comparisons import ComparisonLedger
    ledger = ComparisonLedger(bank.facts)
    out = []
    exclusive, destroyed, deaths, current_dates = [ledger.cache() for _ in range(4)]
    blocks = {b.number: b for b in manuscript.blocks}
    def emit(rule, category, code, previous, current, message, extra=()):
        proof = current['evidence']
        related = [previous['evidence'], *[f['evidence'] for f in extra], proof]
        item = alert(blocks[proof['paragraph']], rule, category, proof['start'], proof['end'], message, 'média', related)
        item.update(category_code=code, severity='possible_inconsistency', confidence_score=min(previous['fact_confidence'], current['fact_confidence']),
                    suggestion=None, evidence=related)
        out.append(item)
    for fact in bank.facts:
        ledger.current = fact
        if fact.get('scope') == 'reported' or fact.get('fact_confidence', fact['confidence']) < .65:
            continue
        relation, subject, value = fact['relation'], fact['subject'], fact['value']
        if relation == 'ability' and fact['scope'] == 'exclusive' and fact['polarity'] == 'positive':
            exclusive[subject] = fact
        elif relation == 'ability_change':
            exclusive.pop(subject, None)
        elif relation in {'ability_use', 'demonstrated_ability'} and fact['polarity'] == 'positive' and subject in exclusive and settings['rules']['conflito_habilidade']:
            old = exclusive[subject]
            if old['value'] != value:
                emit('conflito_habilidade', 'Habilidade possivelmente contraditória', 'ability_conflict', old, fact,
                     f'A personagem tinha habilidade exclusiva de {old["value"]}, mas agora usa {value}. Confira se houve uma evolução ou exceção explicada na obra.')
        elif relation == 'object_state':
            if value == 'destroyed':
                destroyed[subject] = fact
            elif value == 'repaired':
                destroyed.pop(subject, None)
            elif subject in destroyed and settings['rules']['conflito_objeto']:
                emit('conflito_objeto', 'Estado de objeto possivelmente incompatível', 'object_state_conflict', destroyed[subject], fact,
                     'Um objeto com a mesma designação foi destruído e aparece intacto. Nenhuma restauração explícita foi reconhecida; confirme a identidade e a continuidade do objeto.')
        elif relation == 'death_date':
            deaths.setdefault(subject, []).append(fact)
        elif relation == 'scene_date':
            current_dates[fact['scene']] = fact
        elif relation == 'anniversary_yesterday' and settings['rules']['conflito_cronologia']:
            candidates = deaths.get(subject, []) if subject else [f for values in deaths.values() for f in values]
            now = current_dates.get(fact['scene'])
            if len(candidates) != 1 or now is None:
                continue
            old = candidates[0]
            death = date.fromisoformat(old['value'])
            yesterday = date.fromisoformat(now['value']) - timedelta(days=1)
            try:
                anniversary = death.replace(year=death.year + value)
            except ValueError:
                continue  # Calendários e aniversários em 29/02 exigem decisão editorial.
            if anniversary != yesterday:
                emit('conflito_cronologia', 'Cronologia incompatível', 'chronology_conflict', old, fact,
                     f'A data da cena implica ontem em {yesterday:%d/%m/%Y}; o aniversário de {value} anos seria em {anniversary:%d/%m/%Y}.', (now,))
    from .generic_facts import compare_generic
    out.extend(compare_generic(bank, manuscript, settings, ledger))
    bank.comparison_metrics = ledger.metrics()
    return out
