"""Avaliação cega da detecção em textos sintéticos anotados.

Gera um DOCX por texto do corpus, executa o motor (fontes ou executável) e
compara as ocorrências com o gabarito. Uma ocorrência acerta um erro quando está
no mesmo parágrafo e seu intervalo, ou o de uma evidência relacionada, se
sobrepõe ao trecho anotado. Ocorrências sobre trechos marcados como aceitáveis
não contam como acerto nem como alarme falso; as demais são alarmes falsos.

O corpus é escrito junto com o motor e não substitui uma avaliação independente.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'Analisador/tests/corpus/deteccao'
LAYERS = ('linguistica', 'narrativa')


def load(sets):
    texts = []
    for name in sets:
        data = json.loads((CORPUS / f'{name}.json').read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or data.get('conjunto') != name:
            raise ValueError(f'Corpus {name} inválido.')
        texts.extend(dict(item, conjunto=name) for item in data['textos'])
    return texts


def occurrences(paragraph, excerpt):
    """Ocorrências com limite de palavra: “a a” não casa dentro de “tinha acontecido”."""
    pattern = (r'(?<!\w)' if excerpt[0].isalnum() else '') + re.escape(excerpt) + (r'(?!\w)' if excerpt[-1].isalnum() else '')
    return [m.start() for m in re.finditer(pattern, paragraph)]


def locate(text, annotation):
    """Intervalo do trecho anotado no parágrafo; `n` escolhe a ocorrência."""
    paragraph = text['paragrafos'][annotation['p'] - 1]
    found = occurrences(paragraph, annotation['trecho'])
    n = annotation.get('n', 1)
    if len(found) < n:
        raise ValueError(f"{text['id']}: trecho ausente no parágrafo {annotation['p']}: {annotation['trecho']!r}")
    return annotation['p'], found[n - 1], found[n - 1] + len(annotation['trecho'])


def spans(finding):
    """Intervalo principal e evidências relacionadas no texto atual."""
    yield finding['paragraph'], finding['start'], finding['end']
    for proof in finding.get('related') or []:
        if proof.get('document', 'atual') == 'atual' and 'paragraph' in proof:
            yield proof['paragraph'], proof['start'], proof['end']


def overlaps(finding, target):
    paragraph, start, end = target
    return any(p == paragraph and s < end and e > start for p, s, e in spans(finding))


def score(text, findings):
    errors = [(annotation, locate(text, annotation)) for annotation in text['erros']]
    tolerated = [locate(text, annotation) for annotation in text.get('aceitaveis', [])]
    hits = [any(overlaps(f, target) for f in findings) for _, target in errors]
    true, neutral, false = [], [], []
    for finding in findings:
        if any(overlaps(finding, target) for _, target in errors):
            true.append(finding)
        elif any(overlaps(finding, target) for target in tolerated):
            neutral.append(finding)
        else:
            false.append(finding)
    return {
        'id': text['id'], 'conjunto': text['conjunto'], 'controle': bool(text.get('controle')),
        'erros': [dict(annotation, encontrado=hit) for (annotation, _), hit in zip(errors, hits)],
        'ocorrencias': len(findings), 'verdadeiras': len(true), 'neutras': len(neutral),
        'alarmes_falsos': [brief(f) for f in false],
    }


def brief(finding):
    return {'paragrafo': finding['paragraph'], 'trecho': finding.get('excerpt', finding['text'][finding['start']:finding['end']]),
            'regra': finding.get('rule') or finding.get('category_code') or finding['category'],
            'mensagem': finding.get('message', finding.get('reason', ''))[:160]}


def summarize(results):
    by_category = defaultdict(Counter)
    by_layer = defaultdict(Counter)
    for result in results:
        for error in result['erros']:
            for bucket in (by_category[error['categoria']], by_layer[error['camada']]):
                bucket['esperados'] += 1
                bucket['encontrados'] += error['encontrado']
    true = sum(r['verdadeiras'] for r in results)
    false = sum(len(r['alarmes_falsos']) for r in results)
    return {
        'textos': len(results),
        'por_camada': {k: dict(v) for k, v in sorted(by_layer.items())},
        'por_categoria': {k: dict(v) for k, v in sorted(by_category.items())},
        'ocorrencias': sum(r['ocorrencias'] for r in results),
        'ocorrencias_verdadeiras': true,
        'ocorrencias_neutras': sum(r['neutras'] for r in results),
        'alarmes_falsos': false,
        'alarmes_falsos_em_controles': sum(len(r['alarmes_falsos']) for r in results if r['controle']),
    }


def table(summary):
    lines = ['| Categoria | Encontrados / esperados |', '| --- | ---: |']
    for name, count in summary['por_categoria'].items():
        lines.append(f"| {name} | {count['encontrados']} / {count['esperados']} |")
    for name, count in summary['por_camada'].items():
        lines.append(f"| **Total {name}** | **{count['encontrados']} / {count['esperados']}** |")
    judged = summary['ocorrencias_verdadeiras'] + summary['alarmes_falsos']
    lines += ['', f"Ocorrências: {summary['ocorrencias']} ({summary['ocorrencias_verdadeiras']} sobre erros anotados, "
              f"{summary['ocorrencias_neutras']} sobre trechos aceitáveis, {summary['alarmes_falsos']} alarmes falsos; "
              f"{summary['alarmes_falsos_em_controles']} nos textos de controle).",
              f"Proporção de ocorrências sobre erros anotados: {summary['ocorrencias_verdadeiras']}/{judged}."
              if judged else 'Nenhuma ocorrência julgada.']
    return '\n'.join(lines)


def write_docx(text, path):
    from docx import Document
    document = Document()
    for paragraph in text['paragrafos']:
        document.add_paragraph(paragraph)
    document.save(path)


def analyze(text, work, engine, extra):
    docx = work / f"{text['id']}.docx"
    output = work / f"{text['id']}-relatorio"
    write_docx(text, docx)
    arguments = ['revisar', str(docx), '--modo', 'ambas', '--tempo', text.get('tempo', 'auto'), '--saida', str(output), *extra]
    if engine:
        command, cwd, env = [str(Path(engine).expanduser().resolve()), *arguments], work, dict(os.environ)
    else:
        command, cwd = [sys.executable, '-m', 'fonte', *arguments], ROOT / 'Analisador'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'Analisador'))
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise SystemExit(f"Falha ao analisar {text['id']}:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return json.loads((output / 'relatorio.json').read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--conjunto', choices=['desenvolvimento', 'validacao', 'todos'], default='desenvolvimento')
    parser.add_argument('--saida', type=Path, required=True, help='Pasta nova para resultados')
    parser.add_argument('--engine', type=Path, help='Executável do motor; sem ele, usa os fontes de Analisador/')
    parser.add_argument('--languagetool', action='store_true', help='Repassa --languagetool ao motor')
    parser.add_argument('--porta-lt', type=int, help='Repassa --porta-lt ao motor')
    args = parser.parse_args(argv)
    output = args.saida.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    sets = ['desenvolvimento', 'validacao'] if args.conjunto == 'todos' else [args.conjunto]
    extra = (['--languagetool'] if args.languagetool else []) + (['--porta-lt', str(args.porta_lt)] if args.porta_lt else [])
    results, engine_version, languagetool = [], None, None
    with tempfile.TemporaryDirectory() as temporary:
        for text in load(sets):
            report = analyze(text, Path(temporary), args.engine, extra)
            engine_version = report['metadata'].get('versao_fonte')
            languagetool = report['metadata'].get('languagetool_origem') or report['metadata'].get('languagetool')
            results.append(score(text, report['findings']))
            print(f"{text['id']}: {sum(e['encontrado'] for e in results[-1]['erros'])}/{len(text['erros'])} erros, "
                  f"{len(results[-1]['alarmes_falsos'])} alarmes falsos", flush=True)
    summary = summarize(results)
    payload = {'conjuntos': sets, 'motor': str(args.engine) if args.engine else 'fontes', 'versao_fonte': engine_version,
               'languagetool': languagetool, 'argumentos': extra, 'resumo': summary, 'textos': results}
    (output / 'resultado.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'resumo.md').write_text(table(summary) + '\n', encoding='utf-8')
    print('\n' + table(summary))
    print(f'\nDetalhes: {output / "resultado.json"}')


if __name__ == '__main__':
    main()
