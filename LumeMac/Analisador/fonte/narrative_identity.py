"""Identidade de itens por introdução, dono e descrição; estado nunca decide identidade."""
import re

COLORS = {'vermelho', 'vermelha', 'azul', 'dourado', 'dourada', 'preto', 'preta', 'branco', 'branca'}
ORDINALS = {'primeiro': 0, 'primeira': 0, 'segundo': 1, 'segunda': 1, 'terceiro': 2, 'terceira': 2}


class ObjectRegistry:
    def __init__(self, key):
        self.key = key
        self.entities = []
        self.location = None
        self.scene = None

    def observe(self, scene, text):
        if scene != self.scene:
            self.location = None
            self.scene = scene
        arrival = re.search(r'\b(?:chegou|cheguei|entrou|entrei)\s+(?:em|na|no|à|ao)\s+(?:sua?\s+)?(casa|escola|hospital|quarto|sala|escritório|apartamento)\b', text, re.I)
        if arrival:
            self.location = arrival[1].casefold()

    def mention(self, token, proof, scene_id, base, actor=None, recipient=None):
        children = list(token.children)
        color = next((c.lower_ for c in children if c.lower_ in COLORS), None)
        owner_token = next((c for c in children if c.dep_ == 'nmod' and c.pos_ == 'PROPN'
                            and any(a.dep_ == 'case' and a.lower_ in {'de','do','da'} for a in c.children)), None)
        owner_name = None
        if owner_token is not None:
            names = sorted([owner_token] + [c for c in owner_token.children if c.dep_ == 'flat:name' and c.pos_ == 'PROPN'], key=lambda t: t.i)
            owner_name = ' '.join(c.text for c in names)
        qualifier = next((c.lower_ for c in children if c.lower_ in {'pessoal', 'profissional', 'reserva', 'trabalho'}), None)
        site = next((c for c in children if c.dep_ == 'nmod' and c.pos_ == 'NOUN'
                     and c.lower_ not in {'trabalho'}), None)
        if base in {'porta', 'janela', 'relógio'} and site is not None:
            qualifier = ' '.join(t.lower_ for t in site.subtree if t.i >= site.i)
        owner = self.key('char', owner_name) if owner_name else None
        personal = base in {'celular', 'bolsa', 'mochila'}
        # Pista de manuseio separa candidatos; não afirma propriedade jurídica.
        handler = actor if personal and token.head.lemma_.casefold() in {'pegar', 'abaixar', 'guardar', 'colocar', 'erguer'} else None
        place = (qualifier or self.location or scene_id) if base in {'porta', 'janela', 'relógio'} else None
        context = self.location or scene_id
        ordinal = next((ORDINALS[c.lower_] for c in children if c.lower_ in ORDINALS), None)
        new = any(c.lower_ in {'um', 'uma', 'outro', 'outra'} for c in children)
        plural = 'Plur' in token.morph.get('Number') or any(c.pos_ == 'NUM' and c.text not in {'1', 'um', 'uma'} for c in children)
        label = base + (' ' + qualifier if qualifier else '') + (' ' + color if color else '') + (' de ' + owner_name if owner_name else '')
        candidates = [e for e in self.entities if e['base'] == base
                      and (e['scene'] == scene_id or owner or qualifier or color
                           or any(c.lower_ in {'mesmo','mesma'} for c in children)
                           or actor and e.get('handler') == actor)
                      and (not qualifier or e.get('qualifier') == qualifier) and (not color or e['color'] == color) and (not owner or e['owner'] == owner)
                      and (not place or e.get('place') == place)
                      and (not handler or not e.get('handler') or e['handler'] == handler)
                      and (not personal or owner or (handler and e.get('handler') == handler) or e.get('context') == context)]
        if ordinal is not None:
            candidates = [e for e in candidates if e['scene'] == scene_id]
            candidates = candidates[ordinal:ordinal+1]
        selected = candidates[0] if not new and not plural and len(candidates) == 1 else None
        ambiguous = plural or (not new and len(candidates) > 1) or (ordinal is not None and not candidates)
        if selected is None and not ambiguous:
            ident = self.key('obj', label)
            if any(e['id'] == ident for e in self.entities):
                ident = self.key('obj', f"{label}@{proof['range']['start']}")
            selected = dict(id=ident, base=base, owner=owner, color=color, qualifier=qualifier, scene=scene_id, place=place, handler=handler, context=context)
            self.entities.append(selected)
        if selected and personal:
            if recipient:
                selected['handler'] = recipient
            elif handler:
                selected['handler'] = handler
            selected['context'] = context
        return dict(id=selected['id'] if selected else self.key('obj_unresolved', str(proof['range']['start'])),
                    name=label, base=base, owner=owner, color=color, qualifier=qualifier,
                    location_context=place, handler_hint=handler,
                    identity_status='resolved' if selected else 'unresolved',
                    identity_confidence=.9 if selected else .0,
                    identity_candidates=[e['id'] for e in candidates])
