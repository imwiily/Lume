"""Compara uma análise atual com um relatório anterior, preservando o DOCX.

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
        events = {e['id']:e for e in meta['fact_bank']['events']}
        for fact in meta['fact_bank']['facts']:
            assert fact['event_id'] in events
            proof = fact['evidence']
            assert proof['text'][proof['start']:proof['end']] == proof['excerpt']
            assert not (fact['relation']=='object_use' and fact['subject']==fact['value'])
        results[name] = report
    if 'motor' in results:
        assert results['fontes']['findings'] == results['motor']['findings']
        for field in ['scenes','fact_bank','narrative_diagnostics','text_index']:
            assert results['fontes']['metadata'][field] == results['motor']['metadata'][field], field
    current = results['fontes']['metadata']
    summary = dict(preserved=True, sha256=digest, same_text_index=True, engine_parity=True if args.engine else None,
                   before=old['metadata']['narrative_summary'], after=current['narrative_summary'],
                   before_diagnostics=old['metadata']['narrative_diagnostics'], after_diagnostics=current['narrative_diagnostics'])
    (output/'validacao.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary['after'], ensure_ascii=False))


if __name__ == '__main__':
    main()
