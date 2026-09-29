"""Contagem de pares elegíveis e efetivamente consultados pelos comparadores.

Elegibilidade inclui antecedentes compatíveis, não só o último da memória.
Uma consulta real ao histórico marca o par mesmo quando não resulta em alerta.
Pares são únicos por IDs: múltiplos comparadores não multiplicam o denominador.
"""
from collections import defaultdict

ROUTES = {
    'age': {'age'}, 'sibling': {'siblings'}, 'object_location': {'object_location'},
    'object_use': {'object_state', 'holder'}, 'door_state': {'door_state'},
    'activity': {'life_state', 'location', 'alone_entry'}, 'scene_speech': {'location', 'alone_entry'},
    'mobility_use': {'mobility'}, 'physical_action': {'physical_state'},
    'physical_attribute': {'physical_attribute'}, 'profession': {'profession'}, 'met': {'met'},
    'weekday': {'weekday'}, 'elapsed': {'duration'}, 'arrival_after': {'arrival_after'},
    'location': {'location'}, 'access': {'door_state'}, 'identity_name': {'identity_name'},
    'tells': {'knows'}, 'ability_use': {'ability'}, 'demonstrated_ability': {'ability'},
    'object_state': {'object_state'}, 'anniversary_yesterday': {'death_date', 'scene_date'},
}
GLOBAL_RELATIONS = {'weekday', 'access', 'anniversary_yesterday', 'arrival_after'}


def trusted(f):
    return (f.get('fact_confidence', 0) >= .65 and f.get('inference_level') != 'weak_inference'
            and (f.get('scope') != 'reported' or f['relation'] == 'identity_name'))


class ComparisonLedger:
    def __init__(self, facts):
        self.current = None
        self.eligible = set()
        self.compared = set()
        by_relation = defaultdict(list)
        for fact in facts:
            if trusted(fact):
                by_relation[fact['relation']].append(fact)
        for new in facts:
            if not trusted(new):
                continue
            for relation in ROUTES.get(new['relation'], ()):
                for old in by_relation[relation]:
                    if old['id'] == new['id']:
                        continue
                    if new['relation'] != 'tells' and old['evidence']['range']['start'] > new['evidence']['range']['start']:
                        continue
                    cross = old['scene'] != new['scene']
                    if cross and old.get('persistence') != 'persistent' and new['relation'] not in {'weekday', 'anniversary_yesterday'}:
                        continue
                    if new['relation'] not in GLOBAL_RELATIONS and relation != 'alone_entry' and old['subject'] != new['subject']:
                        continue
                    if relation == 'alone_entry' and (cross or old['subject'] == new['subject']):
                        continue
                    if new['relation'] in {'met', 'profession', 'tells'} and old['value'] != new['value']:
                        continue
                    if new['relation'] == 'arrival_after' and (cross or old['subject'] != new['value'] or old['value'] != new['subject']):
                        continue
                    if new['relation'] == 'access' and cross:
                        continue
                    if new['relation'] == 'anniversary_yesterday' and (relation == 'scene_date' and cross or relation == 'death_date' and new['subject'] and old['subject'] != new['subject']):
                        continue
                    self.eligible.add(self.pair(old, new))

    @staticmethod
    def pair(a, b):
        return tuple(sorted((a['id'], b['id'])))

    def record(self, old, new=None):
        new = new or self.current
        if isinstance(old, list):
            for item in old:
                self.record(item, new)
        elif old and new:
            pair = self.pair(old, new)
            if pair in self.eligible:
                self.compared.add(pair)
        return old

    def cache(self):
        return ObservedHistory(self)

    def metrics(self):
        return dict(global_eligible_fact_pairs=len(self.eligible), global_compared_fact_pairs=len(self.compared),
                    global_comparison_rate=len(self.compared) / len(self.eligible) if self.eligible else None)


class ObservedHistory(dict):
    def __init__(self, ledger):
        super().__init__()
        self.ledger = ledger

    def get(self, key, default=None):
        return self.ledger.record(super().get(key, default))

    def __getitem__(self, key):
        return self.ledger.record(super().__getitem__(key))
