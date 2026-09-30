"""Deriva um índice compacto dos arquivos públicos do PortiLexicon-UD.

Uso: python tools/build_lexicon.py PASTA_DOS_TSV
Não recebe nem incorpora manuscritos ou decisões de revisores.
"""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

FINITE, PAST, PRESENT, FUTURE, NONFINITE, NONVERB = 1, 2, 4, 8, 16, 32


def build(source, destination):
    words = defaultdict(int)
    skipped = []
    for number, line in enumerate((source / 'WORDmaster.txt').read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        if ',' not in line:
            skipped.append({'file':'WORDmaster.txt','line':number,'text':line})
            continue
        word, tags = line.rsplit(',', 1)
        word = unicodedata.normalize('NFC', word.casefold())
        words[word] |= NONVERB if set(tags.split()) - {'VERB', 'AUX'} else 0
    for filename in ['VERB.tsv', 'AUX.tsv']:
        with (source / filename).open(encoding='utf-8') as handle:
            for line in handle:
                if not line.strip():
                    continue
                word, lemma, features = line.rstrip('\n').split('\t')
                word = unicodedata.normalize('NFC', word.casefold())
                attrs = dict(pair.split('=', 1) for pair in features.split('|'))
                if attrs.get('VerbForm') != 'Fin':
                    words[word] |= NONFINITE
                    continue
                words[word] |= FINITE
                if attrs.get('Mood') == 'Ind':
                    tense = attrs.get('Tense')
                    words[word] |= {'Past': PAST, 'Imp': PAST, 'Pqp': PAST,
                                    'Pres': PRESENT, 'Fut': FUTURE}.get(tense, 0)
    destination.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(sorted(words.items())), ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    (destination / 'portilexicon.json.gz').write_bytes(gzip.compress(payload, mtime=0))
    meta = {'name': 'PortiLexicon-UD', 'commit': (source / 'commit.txt').read_text().strip(),
            'source': 'https://github.com/LuceleneL/PortiLexicon-UD',
            'entries': len(words), 'derived_sha256': hashlib.sha256(payload).hexdigest(),
            'malformed_source_rows_skipped': skipped,
            'inputs': {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                       for name in ['WORDmaster.txt', 'VERB.tsv', 'AUX.tsv']}}
    (destination / 'portilexicon-meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    build(Path(sys.argv[1]), Path(__file__).resolve().parents[1] / 'fonte' / 'data')
