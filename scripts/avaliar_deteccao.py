"""Avaliação cega da detecção em textos sintéticos anotados.

Gera um DOCX por texto do corpus, executa o motor (fontes ou executável) e
compara as ocorrências com o gabarito. Uma ocorrência acerta um erro quando está
no mesmo parágrafo e seu intervalo, ou o de uma evidência relacionada, se
sobrepõe ao trecho anotado. Ocorrências sobre trechos marcados como aceitáveis
não contam como acerto nem como alarme falso; as demais são alarmes falsos.

Com --auditoria, a Auditoria final com IA roda em cada texto (chama a API da
Anthropic e custa dinheiro) e é medida à parte: erros que só ela encontrou, achados
sobre erros que as regras já apontavam, sobre trechos aceitáveis e alarmes falsos.

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
CORPUS = ROOT / 'fonte/tests/corpus/deteccao'
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


def score(text, findings, diagnostico=()):
    """`diagnostico`: achados fora da mesa (metadata.diagnostico); entram só na medição da Auditoria."""
    errors = [(annotation, locate(text, annotation)) for annotation in text['erros']]
    tolerated = [locate(text, annotation) for annotation in text.get('aceitaveis', [])]
    hits = [any(overlaps(f, target) for f in findings) for _, target in errors]
    rules = [f for f in findings if f.get('module') != 'audit']
    rule_hits = [any(overlaps(f, target) for f in rules) for _, target in errors]
    audit = {'achados': 0, 'sobre_erros_perdidos': 0, 'sobre_erros_ja_apontados': 0, 'neutros': 0, 'alarmes_falsos': []}
    for finding in [*findings, *diagnostico]:
        if finding.get('module') != 'audit':
            continue
        audit['achados'] += 1
        if finding.get('destino') == 'diagnostico':
            audit['diagnostico'] = audit.get('diagnostico', 0) + 1
        matched = [rule_hit for (_, target), rule_hit in zip(errors, rule_hits) if overlaps(finding, target)]
        if matched:
            audit['sobre_erros_ja_apontados' if all(matched) else 'sobre_erros_perdidos'] += 1
        elif any(overlaps(finding, target) for target in tolerated):
            audit['neutros'] += 1
        else:
            audit['alarmes_falsos'].append(brief(finding))
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
        'erros': [dict(annotation, encontrado=hit, encontrado_regras=rule_hit)
                  for (annotation, _), hit, rule_hit in zip(errors, hits, rule_hits)],
        'ocorrencias': len(findings), 'verdadeiras': len(true), 'neutras': len(neutral),
        'palavras': sum(len(re.findall(r'[^\W\d_]+', p)) for p in text['paragrafos']),
        # Só o que entra na fila (relatórios sem destino contam tudo como pendência).
        'pendencias_verdadeiras': sum(f.get('destino', 'pendencia') == 'pendencia' for f in true),
        'pendencias_alarmes_falsos': sum(f.get('destino', 'pendencia') == 'pendencia' for f in false),
        'alarmes_falsos': [brief(f) for f in false],
        'auditoria': audit,
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
    summary = {
        'textos': len(results),
        'por_camada': {k: dict(v) for k, v in sorted(by_layer.items())},
        'por_categoria': {k: dict(v) for k, v in sorted(by_category.items())},
        'ocorrencias': sum(r['ocorrencias'] for r in results),
        'ocorrencias_verdadeiras': true,
        'ocorrencias_neutras': sum(r['neutras'] for r in results),
        'alarmes_falsos': false,
        'alarmes_falsos_em_controles': sum(len(r['alarmes_falsos']) for r in results if r['controle']),
        'palavras': sum(r.get('palavras', 0) for r in results),
    }
    judged = true + false
    # Métrica principal (protocolo de 07/10/2026): quantas ocorrências julgadas estavam sobre erros.
    summary['precisao'] = round(true / judged, 3) if judged else None
    summary['alarmes_falsos_por_10k_palavras'] = (round(false * 10000 / summary['palavras'], 1)
                                                  if summary['palavras'] else None)
    queue_true = sum(r.get('pendencias_verdadeiras', r['verdadeiras']) for r in results)
    queue_false = sum(r.get('pendencias_alarmes_falsos', len(r['alarmes_falsos'])) for r in results)
    summary['precisao_pendencias'] = round(queue_true / (queue_true + queue_false), 3) if queue_true + queue_false else None
    summary['pendencias_alarmes_falsos_por_10k_palavras'] = (round(queue_false * 10000 / summary['palavras'], 1)
                                                             if summary['palavras'] else None)
    if any('custo_auditoria' in r or r.get('auditoria', {}).get('achados') for r in results):
        audits = [r.get('auditoria', {}) for r in results]
        errors = [e for r in results for e in r['erros']]
        summary['auditoria'] = {
            'achados': sum(a.get('achados', 0) for a in audits),
            'erros_so_auditoria': sum(e['encontrado'] and not e['encontrado_regras'] for e in errors),
            'erros_perdidos_pelas_regras': sum(not e['encontrado_regras'] for e in errors),
            'sobre_erros_ja_apontados': sum(a.get('sobre_erros_ja_apontados', 0) for a in audits),
            'neutros': sum(a.get('neutros', 0) for a in audits),
            'alarmes_falsos': sum(len(a.get('alarmes_falsos', [])) for a in audits),
            'diagnostico': sum(a.get('diagnostico', 0) for a in audits),
            'custo_usd': round(sum(r.get('custo_auditoria', 0) for r in results), 6),
        }
    return summary


def within_budget(spent, per_text, total):
    """Só começa outro texto se o teto por texto ainda couber no teto total da rodada."""
    return spent + per_text <= total + 1e-9


def table(summary):
    lines = []
    if summary.get('precisao') is not None:
        if summary.get('precisao_pendencias') is not None:
            lines.append(f"Precisão das pendências (o que interrompe o editor): {summary['precisao_pendencias']:.0%}. "
                         f"Alarmes falsos na fila por 10 mil palavras: {summary['pendencias_alarmes_falsos_por_10k_palavras']}.")
        lines += [f"Precisão de todas as ocorrências (sobre erros anotados ÷ julgadas): {summary['precisao']:.0%}. "
                  f"Alarmes falsos por 10 mil palavras: {summary['alarmes_falsos_por_10k_palavras']}.",
                  'A cobertura abaixo é guarda contra regressão, não meta.', '']
    lines += ['| Categoria | Encontrados / esperados |', '| --- | ---: |']
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
    if 'auditoria' in summary:
        a = summary['auditoria']
        lines += ['', f"Auditoria final: {a['achados']} achados; {a['erros_so_auditoria']} erros encontrados só por ela "
                      f"(de {a['erros_perdidos_pelas_regras']} que as regras perderam); {a['sobre_erros_ja_apontados']} sobre "
                      f"erros já apontados; {a['neutros']} sobre trechos aceitáveis; {a['alarmes_falsos']} alarmes falsos; "
                      f"{a.get('diagnostico', 0)} ficaram só no diagnóstico. "
                      f"Custo: US$ {a['custo_usd']:.4f}."]
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
    extra = [a.replace('{projeto}', str(work / f"{text['id']}-auditoria")) for a in extra]
    arguments = ['revisar', str(docx), '--modo', 'ambas', '--tempo', text.get('tempo', 'auto'), '--saida', str(output), *extra]
    if engine:
        command, cwd, env = [str(Path(engine).expanduser().resolve()), *arguments], work, dict(os.environ)
    else:
        command, cwd = [sys.executable, '-m', 'fonte', *arguments], ROOT / 'fonte'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'fonte'))
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise SystemExit(f"Falha ao analisar {text['id']}:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return json.loads((output / 'relatorio.json').read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--conjunto', choices=['desenvolvimento', 'validacao', 'todos'], default='desenvolvimento')
    parser.add_argument('--saida', type=Path, required=True, help='Pasta nova para resultados')
    parser.add_argument('--engine', type=Path, help='Executável do motor; sem ele, usa os fontes de fonte/')
    parser.add_argument('--languagetool', action='store_true', help='Repassa --languagetool ao motor')
    parser.add_argument('--porta-lt', type=int, help='Repassa --porta-lt ao motor')
    parser.add_argument('--auditoria', action='store_true',
                        help='Roda a Auditoria final com IA em cada texto (chama a API da Anthropic e custa dinheiro)')
    parser.add_argument('--auditoria-modelo', default='claude-opus-5-5')
    parser.add_argument('--auditoria-teto-texto', type=float, default=0.2, help='Teto em US$ por texto')
    parser.add_argument('--auditoria-teto-total', type=float, default=1.0,
                        help='Teto em US$ da rodada: para antes de um texto que poderia ultrapassá-lo')
    args = parser.parse_args(argv)
    output = args.saida.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    sets = ['desenvolvimento', 'validacao'] if args.conjunto == 'todos' else [args.conjunto]
    extra = (['--languagetool'] if args.languagetool else []) + (['--porta-lt', str(args.porta_lt)] if args.porta_lt else [])
    if args.auditoria:
        # Pasta de projeto nova por texto: nada é reaproveitado de rodadas anteriores.
        extra += ['--auditoria-ia', '--auditoria-projeto', '{projeto}', '--auditoria-modelo', args.auditoria_modelo,
                  '--auditoria-teto', f'{args.auditoria_teto_texto:.2f}']
    results, engine_version, languagetool, spent = [], None, None, 0.0
    with tempfile.TemporaryDirectory() as temporary:
        for text in load(sets):
            if args.auditoria and not within_budget(spent, args.auditoria_teto_texto, args.auditoria_teto_total):
                print(f"Teto total da auditoria (US$ {args.auditoria_teto_total:.2f}) alcançado com US$ {spent:.4f}; "
                      f"textos restantes não foram avaliados.", flush=True)
                break
            report = analyze(text, Path(temporary), args.engine, extra)
            engine_version = report['metadata'].get('versao_fonte')
            languagetool = report['metadata'].get('languagetool_origem') or report['metadata'].get('languagetool')
            results.append(score(text, report['findings'], report.get('metadata', {}).get('diagnostico', [])))
            if args.auditoria:
                rodada = report['metadata'].get('auditoria_ia') or {}
                results[-1]['custo_auditoria'] = rodada.get('custo_usd', 0)
                results[-1]['auditoria_ia'] = rodada
                spent += results[-1]['custo_auditoria']
            print(f"{text['id']}: {sum(e['encontrado'] for e in results[-1]['erros'])}/{len(text['erros'])} erros, "
                  f"{len(results[-1]['alarmes_falsos'])} alarmes falsos", flush=True)
    summary = summarize(results)
    payload = {'conjuntos': sets, 'motor': str(args.engine) if args.engine else 'fontes', 'versao_fonte': engine_version,
               'languagetool': languagetool, 'argumentos': extra, 'resumo': summary, 'textos': results,
               'textos_avaliados': len(results)}
    (output / 'resultado.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'resumo.md').write_text(table(summary) + '\n', encoding='utf-8')
    print('\n' + table(summary))
    print(f'\nDetalhes: {output / "resultado.json"}')


if __name__ == '__main__':
    main()
