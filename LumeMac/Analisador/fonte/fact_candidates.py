"""Propostas dos extratores → candidatos → filtros → fatos publicados.

Cada efeito tem seu próprio candidato. Eventos sem efeito reconhecido recebem um
candidato descartado; sua ausência de promoção nunca é escondida nas métricas.
Não reinterpreta texto nem resolve identidades: consome eventos/papéis/evidências.
"""
from collections import Counter
from copy import deepcopy
from .narrative_memory import PERSISTENT


def classify_objects(scenes):
    relevant = set()
    for scene in scenes:
        for f in scene.facts:
            if f.get('persistence') == 'persistent' and f['fact_confidence'] >= .65 and f['scope'] != 'reported':
                relevant.add(f['subject'])
                if isinstance(f['value'], str):
                    relevant.add(f['value'])
    for scene in scenes:
        for obj in scene.objects:
            obj['identity_tier'] = ('unresolved_object' if obj.get('identity_status') != 'resolved'
                                    else 'persistent_object' if obj['id'] in relevant else 'local_object')
            obj['promotion_basis'] = ('relevant_resolved_effect' if obj['identity_tier'] == 'persistent_object'
                                      else 'unresolved_identity' if obj['identity_tier'] == 'unresolved_object'
                                      else 'no_persistent_consequence')


def filter_candidates(scenes):
    """Materializa somente após avaliar relevância, identidade e persistência."""
    classify_objects(scenes)
    from .generic_facts import TYPES
    for scene in scenes:
        entities = {e['id']: e for e in [*scene.participants, *scene.objects, *scene.location]}
        events = {e['id']: e for e in scene.events}
        proposals = scene.facts
        scene.facts = []
        scene.fact_candidates = []
        linked = set()
        for proposal in proposals:
            f = deepcopy(proposal)
            f.setdefault('fact_type', TYPES.get(f['relation'], 'STATE') + '_FACT')
            event = events.get(f.get('event_id'), {})
            dependencies = {f['subject']}
            if isinstance(f['value'], str) and f['value'] in entities:
                dependencies.add(f['value'])
            dependencies.update(v for v in event.get('semantic_roles', {}).values() if v in entities)
            chain = dict(f['confidence_chain'])
            chain['semantic_role'] = event.get('semantic_role_confidence', event.get('event_confidence', 0))
            chain['inference'] = {'explicit': 1., 'strong_inference': .8, 'weak_inference': .45}.get(f['inference_level'], 0.)
            confidence = min(f['fact_confidence'], chain['semantic_role'], chain['inference'])
            chain['fact'] = confidence
            unresolved = any(entities.get(i, {}).get('identity_tier') in {'unresolved_object', 'unresolved_participant'} for i in dependencies)
            local_identity = any(entities.get(i, {}).get('identity_tier') in {'local_participant', 'local_object'} for i in dependencies)
            missing_identity = any(isinstance(i, str) and i.startswith(('char_', 'obj_')) and i not in entities for i in dependencies)
            relevant = f['relation'] in PERSISTENT
            persistent = relevant and not unresolved and not local_identity and not missing_identity and confidence >= .65 and f['scope'] != 'reported'
            reason = ('unresolved_identity' if unresolved else 'reported_scope' if f['scope'] == 'reported'
                      else 'low_confidence' if confidence < .65 else 'local_identity' if local_identity or missing_identity
                      else 'persistent_consequence' if persistent else 'scene_observation')
            # Uma observação de cena permanece útil localmente; não é ruído global.
            accepted = bool(event) and not unresolved
            candidate = dict(id='candidate_' + f['id'], event_id=f.get('event_id'),
                             source_event_ids=list(f.get('source_event_ids', [])), subject=f['subject'],
                             relation=f['relation'], value=f['value'], fact_type=f['fact_type'],
                             confidence=confidence, confidence_chain=chain, relevance=.9 if relevant else .4,
                             persistence='persistent' if persistent else 'local',
                             inference_level=f['inference_level'], evidence=deepcopy(f['evidence']),
                             reason=reason if event else 'missing_source_event',
                             status='promoted' if accepted else 'discarded', fact_id=f['id'] if accepted else None,
                             scene=scene.id, chapter=scene.chapter, polarity=f['polarity'], scope=f['scope'],
                             valid_from=deepcopy(f.get('valid_from')), valid_until=None)
            scene.fact_candidates.append(candidate)
            linked.update(candidate['source_event_ids'])
            if accepted:
                f.update(candidate_id=candidate['id'], persistence=candidate['persistence'],
                         fact_level='PERSISTENT_FACT' if persistent else 'LOCAL_FACT',
                         confidence=confidence, fact_confidence=confidence, confidence_chain=chain,
                         relevance=candidate['relevance'], persistence_reason=reason)
                if f['fact_type'] == 'STATE_FACT':
                    f['state_subtype'] = ('open_closed_state' if f['value'] in {'open', 'closed'} else
                                          'locked_state' if f['value'] in {'locked', 'unlocked'} else
                                          'active_inactive_state' if f['value'] in {'on', 'off'} else
                                          'damaged_state' if f['relation'] == 'object_state' and f['value'] == 'destroyed' else
                                          'alive_state' if f['relation'] == 'life_state' else f['relation'])
                scene.facts.append(f)
        for event in scene.events:
            if event['id'] in linked:
                continue
            roles = event['semantic_roles']
            reason = ('non_asserted_event' if not event.get('asserted') else
                      'unresolved_roles' if not roles['AGENT'] and not roles['OBJECT'] else
                      'no_supported_consequence')
            scene.fact_candidates.append(dict(
                id='candidate_' + event['id'], event_id=event['id'], source_event_ids=[event['id']],
                subject=roles['PATIENT'] or roles['OBJECT'] or roles['AGENT'], relation=None, value=None,
                fact_type=None, confidence=event.get('event_confidence', 0), relevance=0.,
                persistence='local', inference_level=event.get('inference_level', 'explicit'),
                evidence=deepcopy(event['evidence']), reason=reason, status='discarded', fact_id=None,
                scene=scene.id, chapter=scene.chapter, polarity=event.get('polarity', 'positive'),
                scope='asserted' if event.get('asserted') else 'unasserted', valid_from=None, valid_until=None))


def promotion_metrics(bank):
    candidates = bank.fact_candidates
    discarded = [c for c in candidates if c['status'] == 'discarded']
    return dict(fact_candidate_count=len(candidates), promoted_fact_count=len(bank.facts),
                discarded_fact_candidate_count=len(discarded),
                fact_candidate_discard_reasons=dict(Counter(c['reason'] for c in discarded)),
                local_fact_count=sum(f['persistence'] == 'local' for f in bank.facts))


MUTABLE = {'object_state', 'door_state', 'object_location', 'holder', 'life_state',
           'mobility', 'physical_state', 'location', 'left_location', 'possesses', 'knows',
           'age', 'profession', 'physical_attribute', 'availability_state'}


def state_slot(f):
    relation = 'location' if f['relation'] == 'left_location' else f['relation']
    discriminator = f['value'] if relation in {'possesses', 'knows'} else None
    return f['subject'], relation, discriminator


def derive_history(scenes, facts):
    """Fechamentos pertencem à projeção do banco, sem mutar fatos das cenas."""
    active = {}
    by_scene = {}
    for f in facts:
        # Toda validade é recalculada desta projeção; um rascunho de baixa
        # confiança não pode encerrar um estado forte antes dos filtros.
        f['valid_until'] = None
        by_scene.setdefault(f['scene'], []).append(f)
    incoming = {}
    for scene in scenes:
        incoming[scene.id] = [f['id'] for f in active.values() if f['persistence'] == 'persistent']
        for f in by_scene.get(scene.id, []):
            f.setdefault('valid_until_position', None)
            f.setdefault('superseded_by', None)
            f['valid_from_position'] = dict(scene=f['scene'], paragraph=f['evidence']['paragraph'],
                                             offset=f['evidence']['range']['start'], event_id=f['event_id'])
            if f['scope'] == 'reported' or f['fact_confidence'] < .65:
                continue
            if f['relation'] not in MUTABLE:
                if f['persistence'] == 'persistent':
                    active[f['subject'], f['relation'], str(f['value'])] = f
                continue
            slot = state_slot(f)
            old = active.get(slot)
            leaving = f['relation'] == 'left_location' or f.get('leave')
            if old and leaving and old['value'] != f['value']:
                continue
            if old and f['polarity'] == 'negative' and f['relation'] != 'knows' and old['value'] != f['value']:
                continue
            if old and old['id'] != f['id']:
                old['valid_until'] = deepcopy(f.get('valid_from')) or {'text_position': f['evidence']['range']['start']}
                old['valid_until_position'] = dict(f['valid_from_position'])
                old['superseded_by'] = f['id']
            if leaving or (f['polarity'] == 'negative' and f['relation'] != 'knows'):
                active.pop(slot, None)
            else:
                active[slot] = f
        # Separa fim de cena de tempo absoluto, que pode continuar desconhecido.
        for slot, f in list(active.items()):
            if f['persistence'] != 'persistent':
                f['valid_until'] = {'scene_end': scene.id}
                f['valid_until_position'] = {'scene': scene.id, 'paragraph': scene.end_paragraph, 'boundary': 'scene_end'}
                del active[slot]
        for f in by_scene.get(scene.id, []):
            if f['persistence'] == 'local' and not f['valid_until_position']:
                f['valid_until'] = {'scene_end': scene.id}
                f['valid_until_position'] = {'scene': scene.id, 'paragraph': scene.end_paragraph, 'boundary': 'scene_end'}
    return active, incoming
