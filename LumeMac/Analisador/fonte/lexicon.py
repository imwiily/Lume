"""Confirmação lexical local; não substitui a leitura do contexto."""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re
import unicodedata

FINITE, PAST, PRESENT, FUTURE, NONFINITE, NONVERB = 1, 2, 4, 8, 16, 32
CLITIC = re.compile(r'-(?:me|te|se|nos|vos|lhe|lhes|o|a|os|as|lo|la|los|las)$', re.I)


@lru_cache(maxsize=1)
def data():
    path = Path(__file__).with_name('data') / 'portilexicon.json.gz'
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            return json.load(handle)
    except OSError as exc:
        raise ValueError('Léxico de confirmação ausente. Reinstale a versão 0.2 completa.') from exc


def flags(word):
    key = unicodedata.normalize('NFC', word.casefold())
    key = CLITIC.sub('', key)
    return data().get(key, 0)


def model_finite(token):
    return (token.pos_ in {'VERB', 'AUX'}
            and ('Fin' in token.morph.get('VerbForm') or bool(token.morph.get('Mood'))))


def nominal_context(token, value):
    """Em homógrafos, exige apoio sintático para sustentar a leitura verbal."""
    has_subject = any(c.dep_.startswith(('nsubj', 'csubj')) for c in token.children)
    exclusive_finite = bool(value & FINITE and not value & (NONVERB | NONFINITE))
    def possible_clitic(child):
        return (child.text.casefold() in {'o', 'a', 'os', 'as'}
                and child.i == token.i - 1
                and (exclusive_finite or has_subject))
    if any(c.dep_ in {'case', 'cop'}
           or (c.dep_ == 'det' and not possible_clitic(c)) for c in token.children):
        return True
    if value & NONVERB and token.dep_ != 'ROOT':
        if not has_subject:
            return True
    return False


def finite(token):
    value = flags(token.text)
    if value and not value & FINITE:
        return False
    if value & FINITE:
        if model_finite(token):
            # Cópulas/auxiliares herdam o sujeito do predicado; não são adjetivos.
            return token.pos_ == 'AUX' or not nominal_context(token, value)
        # Só recupera sem o modelo se não houver leitura nominal ou não finita.
        if value & NONVERB and not value & NONFINITE and token.i > 0:
            previous = token.doc[token.i-1]
            if previous.text.casefold() in {'eu','tu','ele','ela','nós','vós','eles','elas','você','vocês'}:
                return True
        return not value & (NONVERB | NONFINITE)
    # Fora do léxico, aceita o modelo para evitar alertas de estrutura excessivos.
    return model_finite(token)


def indicative_tense(token):
    value = flags(token.text)
    if not finite(token):
        return None
    # Uma forma como "passamos" admite ambos. Não escolhe o tempo pela grafia.
    if value & PAST and value & PRESENT:
        return None
    if value & PAST and not value & (PRESENT | FUTURE):
        return 'passado'
    if value & PRESENT and not value & (PAST | FUTURE):
        # Exige que o modelo também indique o indicativo para separar imperativo.
        if 'Ind' in token.morph.get('Mood') and model_finite(token):
            return 'presente'
    # Sem confirmação lexical não cria alerta temporal, mesmo que o modelo sugira.
    return None
