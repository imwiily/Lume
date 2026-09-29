"""Compara uma análise atual com um relatório anterior do mesmo DOCX, preservando o arquivo.

Usar com o Python do analisador. --engine também verifica paridade do executável.
Os manuscritos permanecem externos ao repositório.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docx', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', type=Path)
    args = parser.parse_args()
    docx = args.docx.resolve()
    digest = hashlib.sha256(docx.read_bytes()).hexdigest()
    old = json.loads(args.baseline.read_text())
    assert digest == old['sha256'], 'O relatório anterior não corresponde ao DOCX'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = output/'config.json'
    config.write_text(json.dumps(old['metadata'].get('search_settings') or {}, ensure_ascii=False, indent=2))
    results = {}
    commands = {'fontes': [sys.executable, '-m', 'fonte']}
    if args.engine:
        commands['motor'] = [str(args.engine.resolve())]
    for name, command in commands.items():
        with (output/(name+'.log')).open('w') as log:
            subprocess.run([*command, 'revisar', str(docx), '--saida', str(output/name),
                            '--config', str(config), '--modo', 'ambas', '--tempo', 'passado'],
                           cwd=ROOT/'Analisador', stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=120)
        report = json.loads((output/name/'relatorio.json').read_text())
        meta = report['metadata']
        assert report['sha256'] == digest == hashlib.sha256(docx.read_bytes()).hexdigest()
        assert meta['text_index'] == old['metadata']['text_index']
        for finding in report['findings']:
            assert finding['text'][finding['start']:finding['end']] == finding['excerpt']
        results[name] = report
    if 'motor' in results:
        assert results['fontes']['findings'] == results['motor']['findings']
        for field in ['text_index']:
            assert results['fontes']['metadata'][field] == results['motor']['metadata'][field], field
    antes = {f['id'] for f in old['findings']}
    depois = {f['id'] for f in results['fontes']['findings']}
    summary = dict(preserved=True, sha256=digest, same_text_index=True, engine_parity=True if args.engine else None,
                   findings_before=len(antes), findings_after=len(depois),
                   kept=len(antes & depois), removed=len(antes - depois), added=len(depois - antes))
    (output/'validacao.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({k: summary[k] for k in ('findings_before', 'findings_after', 'kept', 'removed', 'added')}))


if __name__ == '__main__':
    main()
