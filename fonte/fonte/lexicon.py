"""Confirmação lexical local; não substitui a leitura do contexto."""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re
import unicodedata

FINITE, PAST, PRESENT, FUTURE, NONFINITE, NONVERB = 1, 2, 4, 8, 16, 32
# Relações em que o token é, pela própria análise, verbo de ligação ou auxiliar.
VERBAL_DEPS = {'cop', 'aux', 'aux:pass'}
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
