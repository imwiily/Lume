"""Precisão real de cada classe de alerta, a partir das decisões dos editores.

Lê os relatórios e as decisões guardados pelo app (por padrão em
~/Library/Application Support/FONTE) e conta, por classe (regra × confiança), quantas
decisões foram erro real (“Erro confirmado” ou “Corrigido”), falso positivo, estilo do autor,
intencional e aceito editorialmente. Pendentes não entram.

Um alerta que reaparece em versões diferentes do mesmo livro conta uma vez: a chave é o
documento, a classe, o parágrafo e o trecho, e vale a decisão do relatório mais recente.

A saída tem só números, nunca trechos ou nomes de livros (os livros aparecem pelo início do
SHA-256). Ela serve para propor a política de destino; não muda nada sozinha.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

PADRAO = Path.home() / 'Library/Application Support/FONTE'
DESFECHOS = {'Erro confirmado': 'erro', 'Corrigido': 'erro', 'Falso positivo': 'falso_positivo',
             'Estilo do autor': 'estilo', 'Intencional': 'intencional',
             'Aceito editorialmente': 'aceito'}
MINIMO = 20
LIMIAR = .9


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fonte'))
from fonte.politica import classe  # noqa: E402 — a mesma chave estatística da política


def carregar(dados):
    """[(data, relatório, decisões)] dos relatórios que têm decisões guardadas."""
    pares = []
    for caminho in sorted((dados / 'Relatorios').glob('*/relatorio.json')):
        try:
            relatorio = json.loads(caminho.read_text(encoding='utf-8'))
            arquivo = dados / 'Decisoes' / f"{relatorio['sha256']}.json"
            if not arquivo.exists():
                continue
            bruto = json.loads(arquivo.read_text(encoding='utf-8'))
        except (OSError, ValueError, KeyError):
            continue
        decisoes = bruto.get('decisions', bruto) if isinstance(bruto, dict) else {}
        pares.append((caminho.stat().st_mtime, relatorio, decisoes))
    pares.sort(key=lambda par: par[0])
    return pares


def medir(dados, minimo=MINIMO, limiar=LIMIAR):
    unicas = {}
    livros = defaultdict(lambda: {'relatorios': 0, 'decididas': 0})
    for _, relatorio, decisoes in carregar(dados):
        livro = hashlib.sha256(str(relatorio.get('document', '')).encode()).hexdigest()[:10]
        livros[livro]['relatorios'] += 1
        for f in relatorio.get('findings', []):
            valor = decisoes.get(f.get('id'))
            if valor not in DESFECHOS:
                continue
            trecho = f['text'][f['start']:f['end']]
            chave = hashlib.sha256(json.dumps([livro, classe(f), f['text'], trecho, f['start']],
                                              ensure_ascii=False).encode()).hexdigest()
            # O relatório mais recente vem depois e prevalece.
            unicas[chave] = (livro, classe(f), f.get('confidence') or 'sem', f.get('severity') or 'sem', valor)
    por_classe = defaultdict(Counter)
    for livro, nome, confianca, severidade, valor in unicas.values():
        livros[livro]['decididas'] += 1
        conta = por_classe[(nome, confianca)]
        conta[DESFECHOS[valor]] += 1
        conta['severidade:' + severidade] += 1
    classes = []
    for (nome, confianca), conta in sorted(por_classe.items(), key=lambda kv: -sum(
            v for k, v in kv[1].items() if not k.startswith('severidade:'))):
        n = sum(v for k, v in conta.items() if not k.startswith('severidade:'))
        precisao = conta['erro'] / n
        classes.append({
            'classe': nome, 'confianca': confianca, 'decisoes': n,
            'precisao': round(precisao, 3),
            **{k: conta[k] for k in ('erro', 'falso_positivo', 'estilo', 'intencional', 'aceito')},
            'severidades': {k.split(':', 1)[1]: v for k, v in conta.items() if k.startswith('severidade:')},
            'medida': n >= minimo,
            # Só a parte numérica da regra de impeditivo; natureza e severidade ficam na política.
            'atinge_limiar': n >= minimo and precisao >= limiar,
        })
    total = Counter()
    for c in classes:
        for k in ('decisoes', 'erro', 'falso_positivo', 'estilo', 'intencional', 'aceito'):
            total[k] += c[k]
    return {'dados': 'local', 'minimo_decisoes': minimo, 'limiar_precisao': limiar,
            'decisoes_unicas': len(unicas), 'livros': dict(livros), 'total': dict(total),
            'precisao_total': round(total['erro'] / total['decisoes'], 3) if total['decisoes'] else None,
            'classes': classes}


def medir_languagetool(dados):
    """Decisões dos alertas do LanguageTool por regra e pela categoria original (campo `languagetool`,
    gravado desde a Fase 6b; nos relatórios anteriores, “não registrada”). Só mede: não muda classes,
    severidades, destinos nem a política. Mesma deduplicação de `medir`."""
    unicas = {}
    for _, relatorio, decisoes in carregar(dados):
        livro = hashlib.sha256(str(relatorio.get('document', '')).encode()).hexdigest()[:10]
        for f in relatorio.get('findings', []):
            valor = decisoes.get(f.get('id'))
            if valor not in DESFECHOS or not str(f.get('source', '')).startswith('LanguageTool'):
                continue
            trecho = f['text'][f['start']:f['end']]
            chave = hashlib.sha256(json.dumps([livro, classe(f), f['text'], trecho, f['start']],
                                              ensure_ascii=False).encode()).hexdigest()
            original = f.get('languagetool') or {}
            unicas[chave] = (f['source'].rsplit(' · ', 1)[-1], original.get('categoria') or 'não registrada',
                             original.get('tipo') or 'não registrado', classe(f), DESFECHOS[valor])
    grupos = defaultdict(Counter)
    for regra, categoria, tipo, nome, valor in unicas.values():
        grupos[(regra, categoria, tipo, nome)][valor] += 1
    linhas = []
    for (regra, categoria, tipo, nome), conta in sorted(grupos.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(conta.values())
        linhas.append({'regra': regra, 'categoria': categoria, 'tipo': tipo, 'classe': nome, 'decisoes': n,
                       'precisao': round(conta['erro'] / n, 3),
                       **{k: conta[k] for k in ('erro', 'falso_positivo', 'estilo', 'intencional', 'aceito')}})
    return linhas


def tabela(resultado):
    linhas = [f"Decisões únicas: {resultado['decisoes_unicas']} em {len(resultado['livros'])} livros. "
              f"Precisão total (erro real ÷ decididas): "
              + (f"{resultado['precisao_total']:.0%}." if resultado['precisao_total'] is not None else "sem dados."),
              '', '| Classe | Confiança | Decisões | Erro real | Falso positivo | Estilo | Intencional | Aceito | ≥ limiar |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for c in resultado['classes']:
        marca = 'sim' if c['atinge_limiar'] else ('—' if c['medida'] else f"n < {resultado['minimo_decisoes']}")
        linhas.append(f"| {c['classe']} | {c['confianca']} | {c['decisoes']} | {c['precisao']:.0%} | {c['falso_positivo']} | "
                      f"{c['estilo']} | {c['intencional']} | {c['aceito']} | {marca} |")
    linhas += ['', '“≥ limiar” é só a condição numérica. Uma classe só é impeditiva se também for de natureza '
               'objetiva e de severidade de erro (política de destino).']
    return '\n'.join(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--dados', type=Path, default=PADRAO, help='Pasta de dados do Lume (FONTE)')
    parser.add_argument('--saida', type=Path, required=True, help='Pasta nova para resultados')
    parser.add_argument('--minimo', type=int, default=MINIMO)
    parser.add_argument('--languagetool', action='store_true',
                        help='Também grava as decisões do LanguageTool por regra e categoria original')
    args = parser.parse_args(argv)
    if args.saida.exists():
        raise SystemExit(f'A pasta de saída já existe: {args.saida}')
    resultado = medir(args.dados, args.minimo)
    args.saida.mkdir(parents=True)
    (args.saida / 'precisao.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.saida / 'resumo.md').write_text(tabela(resultado) + '\n', encoding='utf-8')
    print(tabela(resultado))
    if args.languagetool:
        linhas = medir_languagetool(args.dados)
        (args.saida / 'languagetool.json').write_text(json.dumps(linhas, ensure_ascii=False, indent=2) + '\n',
                                                       encoding='utf-8')
        print('\n| Regra do LanguageTool | Categoria | Tipo | Classe | Decisões | Erro real |\n| --- | --- | --- | --- | ---: | ---: |')
        for l in linhas:
            print(f"| {l['regra']} | {l['categoria']} | {l['tipo']} | {l['classe']} | {l['decisoes']} | {l['precisao']:.0%} |")


if __name__ == '__main__':
    main()
