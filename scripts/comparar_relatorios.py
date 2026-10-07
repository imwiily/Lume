"""Compara relatórios do FONTE alerta a alerta: identidade, destino e classe.

Uso: comparar_relatorios.py ANTES DEPOIS [--exigir-identico] [--saida PASTA]

ANTES e DEPOIS são arquivos relatorio.json ou pastas; nas pastas, os relatórios são pareados
pelo caminho relativo. Para cada par:

- identidade: IDs que saíram e que entraram;
- editorial: mudanças de destino, impedimento, classe estatística, severidade e confiança nos IDs
  que continuam;
- descritivo: mudanças de `rule`, categoria, mensagem e sugestão (informativas).

Com --exigir-identico, sai com código 1 se houver qualquer diferença de identidade ou editorial.
A saída não contém trechos do manuscrito, só IDs, classes e contagens.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fonte'))
from fonte.politica import classe  # noqa: E402 — a mesma chave estatística da política

EDITORIAIS = ('destino', 'impeditivo', 'classe', 'severity', 'confidence')
DESCRITIVOS = ('rule', 'category', 'category_code', 'reason', 'suggestion')


def pares(antes, depois):
    if antes.is_file():
        return [('.', antes, depois)]
    a = {p.relative_to(antes).parent: p for p in antes.rglob('relatorio.json')}
    b = {p.relative_to(depois).parent: p for p in depois.rglob('relatorio.json')}
    nomes = sorted(set(a) | set(b), key=str)
    return [(str(n), a.get(n), b.get(n)) for n in nomes]


def comparar(antes, depois):
    if antes is None or depois is None:
        return {'faltando': 'antes' if antes is None else 'depois'}
    A = {f['id']: dict(f, classe=classe(f)) for f in json.loads(antes.read_text(encoding='utf-8'))['findings']}
    B = {f['id']: dict(f, classe=classe(f)) for f in json.loads(depois.read_text(encoding='utf-8'))['findings']}
    comuns = A.keys() & B.keys()
    editoriais = Counter(); descritivos = Counter()
    for i in comuns:
        for campo in EDITORIAIS:
            if A[i].get(campo) != B[i].get(campo):
                editoriais[campo] += 1
        for campo in DESCRITIVOS:
            if A[i].get(campo) != B[i].get(campo):
                descritivos[campo] += 1
    return {
        'antes': len(A), 'depois': len(B),
        'saíram': sorted(A.keys() - B.keys()), 'entraram': sorted(B.keys() - A.keys()),
        'mudancas_editoriais': dict(editoriais), 'mudancas_descritivas': dict(descritivos),
        'classes_antes': dict(Counter(f['classe'] for f in A.values())),
        'classes_depois': dict(Counter(f['classe'] for f in B.values())),
        'destinos_antes': dict(Counter(f.get('destino') for f in A.values())),
        'destinos_depois': dict(Counter(f.get('destino') for f in B.values())),
    }


def identico(r):
    return 'faltando' not in r and not r['saíram'] and not r['entraram'] and not r['mudancas_editoriais']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('antes', type=Path)
    parser.add_argument('depois', type=Path)
    parser.add_argument('--exigir-identico', action='store_true')
    parser.add_argument('--saida', type=Path, help='Pasta nova para o resultado em JSON')
    args = parser.parse_args(argv)
    resultado = {nome: comparar(a, b) for nome, a, b in pares(args.antes, args.depois)}
    for nome, r in resultado.items():
        if 'faltando' in r:
            print(f'{nome}: relatório ausente em {r["faltando"]}')
            continue
        estado = 'idêntico' if identico(r) else 'DIFERENTE'
        print(f'{nome}: {estado} · {r["antes"]} → {r["depois"]} alertas · saíram {len(r["saíram"])}, '
              f'entraram {len(r["entraram"])} · editoriais {r["mudancas_editoriais"] or "—"} · '
              f'descritivas {r["mudancas_descritivas"] or "—"}')
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=False)
        (args.saida / 'comparacao.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.exigir_identico and not all(identico(r) for r in resultado.values()):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
