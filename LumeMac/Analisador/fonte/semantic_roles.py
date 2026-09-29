"""Papéis locais por predicado. Identidade não implica participação na ação."""
import re
from .narrative_context import first_person

UNCERTAIN = re.compile(r'\b(?:talvez|caso|sonhou|sonhava|imaginou|imaginava|fingiu|fingia|poderia|teria|queria|tentou|planejava)\b|\bse\s+\w+\s+(?:tivesse|fosse)|\?', re.I)

REPORTING = {'dizer', 'contar', 'revelar', 'afirmar', 'negar', 'imaginar', 'sonhar'}


def passive_agents(token):
    return [c for c in token.subtree if c.pos_ in {'PROPN', 'PRON'}
            and any(x.dep_ == 'case' and x.lower_ in {'por', 'pelo', 'pela'} for x in c.children)
            and next((a for a in c.ancestors if a.pos_ == 'VERB'), None) == token]


def clauses(doc):
    """Separa coordenações, preservando os índices do documento original."""
    for sent in doc.sents:
        if UNCERTAIN.search(sent.text) or any(t.lower_ == 'se' and t.pos_ == 'SCONJ' for t in sent) or re.search(r'\b(?:em sonho|num sonho|no sonho|em um sonho|flashback)\b', sent.text, re.I) or any(t.lemma_ in REPORTING for t in sent) or re.search(r'saíram às.+chegaram às', sent.text, re.I):
            yield sent
            continue
        cuts = []
        for token in sent:
            if token.dep_ == 'conj' and (token.pos_ == 'VERB' or any(c.dep_ == 'cop' for c in token.children)):
                cc = next((c for c in token.children if c.dep_ == 'cc' and c.lower_ in {'e', 'mas'}), None)
                if cc is not None and cc.i > sent.start:
                    cuts.append(cc.i)
        points = [sent.start, *sorted(set(cuts)), sent.end]
        for start, end in zip(points, points[1:]):
            yield doc[start:end]


class Roles:
    def __init__(self, scene, span, offset):
        self.scene, self.span, self.offset = scene, span, offset

    def entity(self, token, kind=None):
        if token is None:
            return None
        if token.lower_ in {'eu', 'me', 'mim'} and kind != 'object' and self.scene.narrator != 'unknown':
            return self.scene.narrator
        absolute = self.offset + token.idx
        collections = self.scene.participants if kind == 'person' else self.scene.objects if kind == 'object' else [*self.scene.participants, *self.scene.objects, *self.scene.location]
        matches = {e['id'] for e in collections if e['evidence']['range']['start'] == absolute and e.get('identity_status') != 'unresolved'}
        if len(matches) == 1:
            return next(iter(matches))
        refs = {r['reference'] for r in self.scene.references if r['evidence']['range']['start'] == absolute and r['reference']}
        if kind == 'person':
            refs = {x for x in refs if x.startswith('char_')}
        elif kind == 'object':
            refs = {x for x in refs if x.startswith('obj_')}
        if len(refs) == 1:
            return next(iter(refs))
        if token.lower_ == 'que' and token.dep_ == 'nsubj':
            # Relativa adjacente: "João, que tinha...". Não usa o sujeito da oração matriz.
            left = [t for t in token.doc[max(0, token.i-3):token.i] if not t.is_punct]
            if left and left[-1].pos_ == 'PROPN':
                return self.entity(left[-1], kind)
        return None

    def predicate(self, char=None):
        if char is None:
            return self.span.root
        token = next((t for t in self.span if t.idx <= char < t.idx + len(t)), None)
        if token is None:
            return self.span.root
        return token.head if token.dep_ in {'cop', 'aux', 'aux:pass'} else token

    def subjects(self, token):
        return [c for c in token.children if c.dep_ in {'nsubj', 'nsubj:pass'}
                and not (token.lemma_ in {'contar', 'dizer', 'revelar', 'entregar'} and c.i > token.i
                         and c.i and token.doc[c.i-1].lower_ in {'a', 'para'})]

    def subject(self, predicate=None, patient=False):
        token = predicate if predicate is not None else self.span.root
        if first_person(token) and self.scene.narrator != 'unknown':
            return self.scene.narrator
        seen = set()
        while token.i not in seen:
            seen.add(token.i)
            subjects = self.subjects(token)
            passive = any(c.dep_ == 'nsubj:pass' for c in subjects)
            if passive and not patient:
                agents = passive_agents(token)
                return self.entity(agents[0], 'person') if len(agents) == 1 else None
            if subjects:
                if len(subjects) != 1 or any(c.dep_ == 'conj' for c in subjects[0].children):
                    return None
                return self.entity(subjects[0], 'person')
            if token.dep_ == 'conj' and token.head.i < token.i:
                token = token.head
            else:
                return None
        return None

    def object(self):
        root = self.span.root
        candidates = [self.entity(t, 'object') for t in root.children if t.dep_ in {'obj', 'nsubj:pass', 'nsubj'}]
        found = {x for x in candidates if x}
        return next(iter(found)) if len(found) == 1 else None

    def has_subject(self):
        return bool(self.subjects(self.span.root))

    def factual_attribute(self, predicate):
        return not any(t.lemma_ in REPORTING for t in predicate.ancestors)
