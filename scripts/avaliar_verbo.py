"""Mede as três operações do núcleo verbal (`fonte/fonte/verbo.py`) contra uma anotação humana.

Cada item anotado traz o parágrafo, a forma (com posição ou, nos itens construídos, a primeira
ocorrência da palavra) e a classe esperada: `finito`, `nao_finito` ou `nao_verbal`. O parágrafo é
analisado de novo, como no FONTE, e a forma é avaliada por:

- `certamente_verbo` (identificação positiva): **precisão** é a métrica principal, porque esta
  operação sustenta alertas sobre verbos; cobertura dos finitos é secundária;
- `pode_ser_verbo` (identificação conservadora): **cobertura dos finitos** é a principal, porque
  esta operação impede dizer “sem verbo” quando há verbo; a taxa sobre os não verbais é o custo;
- `ha_forma_verbal` (verificação de presença): cobertura dos finitos e taxa sobre os não verbais.

Para os finitos, separa três situações: confirmado (`certamente_verbo`), não confirmado (o sistema
admite a possibilidade, mas não confirma) e classificado incorretamente pelo modelo (etiqueta não
verbal). Itens marcados como ambíguos ficam fora das métricas e são listados à parte.

Protocolo: no conjunto de validação, só números agregados são mostrados; a lista de erros
individuais (--erros) é recusada, para que a validação não oriente ajustes.

Uso: avaliar_verbo.py ANOTACAO.json [mais.json …] [--erros] [--saida PASTA]
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fonte'))
from fonte.verbo import certamente_verbo, ha_forma_verbal, pode_ser_verbo  # noqa: E402

OPERACOES = {'certamente_verbo': certamente_verbo, 'pode_ser_verbo': pode_ser_verbo, 'ha_forma_verbal': ha_forma_verbal}
VERBAIS = {'VERB', 'AUX'}


def localizar(doc, item):
    if 'inicio' in item:
        return next((t for t in doc if t.idx == item['inicio']), None)
    achado = re.search(r'(?<!\w)' + re.escape(item['forma']) + r'(?!\w)', item['paragrafo'])
    return next((t for t in doc if achado and t.idx == achado.start()), None)


def avaliar(nlp, itens):
    resultados = []
    for item, doc in zip(itens, nlp.pipe([i['paragrafo'] for i in itens], batch_size=32)):
        token = localizar(doc, item)
        if token is None or token.text != item['forma']:
            raise ValueError(f"Forma não encontrada na posição anotada: {item.get('id', item['forma'])}")
        resultados.append(dict(item, ops={nome: bool(op(token)) for nome, op in OPERACOES.items()},
                               modelo={'pos': token.pos_, 'morph': str(token.morph)}))
    return resultados


def taxa(numerador, denominador):
    return {'n': denominador, 'valor': round(numerador / denominador, 3) if denominador else None}


def metricas(resultados):
    claros = [r for r in resultados if not r['ambiguo']]
    finitos = [r for r in claros if r['esperado'] == 'finito']
    nao_verbais = [r for r in claros if r['esperado'] == 'nao_verbal']
    marcados = [r for r in claros if r['ops']['certamente_verbo']]
    situacao = Counter()
    for r in finitos:
        if r['ops']['certamente_verbo']:
            situacao['confirmado'] += 1
        elif r['modelo']['pos'] not in VERBAIS:
            situacao['classificado_incorretamente_pelo_modelo'] += 1
        else:
            situacao['nao_confirmado'] += 1
    por_estrato = defaultdict(lambda: Counter())
    for r in claros:
        e = r.get('estrato', 'construido')
        por_estrato[e]['itens'] += 1
        por_estrato[e]['certamente_correto'] += r['ops']['certamente_verbo'] == (r['esperado'] == 'finito')
        por_estrato[e]['pode_ser_falha_em_finito'] += r['esperado'] == 'finito' and not r['ops']['pode_ser_verbo']
    return {
        'itens': len(resultados), 'ambiguos': len(resultados) - len(claros),
        'certamente_verbo': {
            'precisao': taxa(sum(r['esperado'] == 'finito' for r in marcados), len(marcados)),
            'cobertura_finitos': taxa(sum(r['ops']['certamente_verbo'] for r in finitos), len(finitos)),
            'falsos_positivos': sum(r['esperado'] != 'finito' for r in marcados),
        },
        'pode_ser_verbo': {
            'cobertura_finitos': taxa(sum(r['ops']['pode_ser_verbo'] for r in finitos), len(finitos)),
            'taxa_em_nao_verbais': taxa(sum(r['ops']['pode_ser_verbo'] for r in nao_verbais), len(nao_verbais)),
        },
        'ha_forma_verbal': {
            'cobertura_finitos': taxa(sum(r['ops']['ha_forma_verbal'] for r in finitos), len(finitos)),
            'taxa_em_nao_verbais': taxa(sum(r['ops']['ha_forma_verbal'] for r in nao_verbais), len(nao_verbais)),
        },
        'situacao_dos_finitos': dict(situacao),
        'invariante_certo_implica_possivel': all(not r['ops']['certamente_verbo'] or r['ops']['pode_ser_verbo']
                                                for r in resultados),
        'por_estrato': {k: dict(v) for k, v in sorted(por_estrato.items())},
    }


def erros(resultados):
    """Discordâncias com a anotação (só para desenvolvimento)."""
    out = []
    for r in resultados:
        problemas = []
        if r['ops']['certamente_verbo'] and r['esperado'] != 'finito':
            problemas.append('certamente_verbo afirma verbo')
        if r['esperado'] == 'finito' and not r['ops']['certamente_verbo']:
            problemas.append('certamente_verbo não confirma')
        if r['esperado'] == 'finito' and not r['ops']['pode_ser_verbo']:
            problemas.append('pode_ser_verbo descarta verbo')
        if r['esperado'] == 'nao_verbal' and r['ops']['ha_forma_verbal']:
            problemas.append('ha_forma_verbal vê verbo')
        if problemas:
            out.append({'forma': r['forma'], 'frase': r.get('frase', r['paragrafo']), 'esperado': r['esperado'],
                        'ambiguo': r['ambiguo'], 'modelo': r['modelo'], 'problemas': problemas,
                        'estrato': r.get('estrato', 'construido')})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('anotacoes', type=Path, nargs='+')
    parser.add_argument('--erros', action='store_true', help='Lista as discordâncias (só desenvolvimento)')
    parser.add_argument('--saida', type=Path)
    args = parser.parse_args(argv)
    itens, conjuntos = [], set()
    for caminho in args.anotacoes:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
        conjuntos.add(dados['conjunto'])
        itens.extend(dict(i, conjunto=dados['conjunto']) for i in dados['itens'])
    if args.erros and 'validacao' in conjuntos:
        raise SystemExit('Protocolo: a validação reservada só mostra números agregados.')
    import spacy
    nlp = spacy.load('pt_core_news_sm', disable=['ner'])
    resultados = avaliar(nlp, itens)
    resumo = {c: metricas([r for r in resultados if r['conjunto'] == c]) for c in sorted(conjuntos)}
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    if args.erros:
        for e in erros(resultados):
            print(f"- {e['forma']} ({e['esperado']}{', ambíguo' if e['ambiguo'] else ''}; modelo {e['modelo']['pos']}; "
                  f"{e['estrato']}): {'; '.join(e['problemas'])} — {e['frase'][:110]}")
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=False)
        (args.saida / 'metricas.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
