"""Amostra de formas para avaliar a identificação verbal do FONTE (estabilização, Fase 2b).

Lê textos de domínio público (arquivos .txt do Project Gutenberg), tira o cabeçalho e o rodapé,
analisa parágrafo por parágrafo e sorteia formas por estrato, de modo reprodutível (semente fixa).
Só entram frases em grafia contemporânea: toda palavra minúscula precisa existir no léxico do
FONTE. Assim, grafias históricas (“annos”, “ella”) nunca são tratadas como erro nem enviesam a
amostra. A saída registra, para cada forma, o contexto, a leitura do modelo e o resultado atual das
três operações do núcleo (`fonte/fonte/verbo.py`). A anotação esperada é feita à parte, por uma
pessoa, e o resultado é medido por `scripts/avaliar_verbo.py`.

Os textos e a amostra ficam fora do Git.

Uso: amostrar_verbos.py --fontes PASTA --divisao divisao.json --saida candidatos.json
divisao.json: {"desenvolvimento": ["pg55752.txt", …], "validacao": ["pg44540.txt", …]}
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fonte'))
from fonte.lexicon import FINITE, NONFINITE, NONVERB, flags  # noqa: E402
from fonte.verbo import certamente_verbo, ha_forma_verbal, pode_ser_verbo, so_verbo_no_lexico  # noqa: E402

ESTRATOS = ('homografo_nome_verbo', 'infinitivo_ou_futuro_subjuntivo', 'inicio_de_frase', 'discordancia',
            'controle_verbo', 'controle_nao_verbal')


def corpo(texto):
    """Texto sem o cabeçalho e o rodapé do Project Gutenberg."""
    inicio = re.search(r'\*\*\* ?START OF[^\n]*\n', texto)
    fim = re.search(r'\*\*\* ?END OF', texto)
    return texto[inicio.end() if inicio else 0:fim.start() if fim else len(texto)]


def paragrafos(texto):
    for bloco in re.split(r'\n\s*\n', corpo(texto)):
        linha = re.sub(r'\s+', ' ', bloco).strip()
        if len(re.findall(r'[^\W\d_]+', linha)) >= 6 and not linha.isupper():
            yield linha


def contemporanea(sentenca):
    """Toda palavra minúscula existe no léxico atual; nomes próprios e siglas passam."""
    return all(flags(t.text) or not t.text[:1].islower() for t in sentenca if t.is_alpha)


def estratos(token, ops):
    valor = flags(token.text)
    primeiro = next((t for t in token.sent if t.is_alpha), None)
    out = []
    if valor & FINITE and valor & NONVERB:
        out.append('homografo_nome_verbo')
    if valor & FINITE and valor & NONFINITE:
        out.append('infinitivo_ou_futuro_subjuntivo')
    if token == primeiro and valor & FINITE and token.text[:1].isupper():
        out.append('inicio_de_frase')
    if len(set(ops.values())) > 1:
        out.append('discordancia')
    if so_verbo_no_lexico(token) and token.pos_ in {'VERB', 'AUX'}:
        out.append('controle_verbo')
    if valor & NONVERB and not valor & FINITE and token.pos_ in {'NOUN', 'ADJ'}:
        out.append('controle_nao_verbal')
    return out


def candidatos(nlp, arquivo, conjunto, limite_paragrafos, semente):
    lista = list(paragrafos(arquivo.read_text(encoding='utf-8')))
    random.Random(f'{semente}:{arquivo.name}').shuffle(lista)
    for doc in nlp.pipe(lista[:limite_paragrafos], batch_size=32):
        for sentenca in doc.sents:
            if not contemporanea(sentenca):
                continue
            for token in sentenca:
                if not token.is_alpha:
                    continue
                ops = {'certamente_verbo': bool(certamente_verbo(token)), 'pode_ser_verbo': bool(pode_ser_verbo(token)),
                       'ha_forma_verbal': bool(ha_forma_verbal(token))}
                grupos = estratos(token, ops)
                if not grupos:
                    continue
                ident = hashlib.sha256(f'{arquivo.name}|{doc.text}|{token.idx}'.encode()).hexdigest()[:12]
                yield {'id': ident, 'conjunto': conjunto, 'fonte': arquivo.name, 'paragrafo': doc.text,
                       'inicio': token.idx, 'fim': token.idx + len(token.text), 'forma': token.text,
                       'frase': sentenca.text, 'estratos': grupos,
                       'modelo': {'pos': token.pos_, 'morph': str(token.morph), 'dep': token.dep_},
                       'lexico': {'finito': bool(flags(token.text) & FINITE), 'nao_finito': bool(flags(token.text) & NONFINITE),
                                  'nao_verbal': bool(flags(token.text) & NONVERB)},
                       'operacoes': ops}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--fontes', type=Path, required=True)
    parser.add_argument('--divisao', type=Path, required=True)
    parser.add_argument('--saida', type=Path, required=True)
    parser.add_argument('--por-estrato', type=int, default=25, help='Formas por estrato em cada conjunto')
    parser.add_argument('--paragrafos', type=int, default=500, help='Parágrafos sorteados por texto')
    parser.add_argument('--semente', default='fase2b')
    args = parser.parse_args(argv)
    if args.saida.exists():
        raise SystemExit(f'A saída já existe: {args.saida}')
    import spacy
    nlp = spacy.load('pt_core_news_sm', disable=['ner'])
    divisao = json.loads(args.divisao.read_text(encoding='utf-8'))
    amostra = []
    for conjunto, arquivos in divisao.items():
        todos = [c for nome in arquivos
                 for c in candidatos(nlp, args.fontes / nome, conjunto, args.paragrafos, args.semente)]
        sorteio = random.Random(f'{args.semente}:{conjunto}')
        usados = set()
        for estrato in ESTRATOS:
            grupo = [c for c in todos if estrato in c['estratos'] and c['id'] not in usados]
            # Uma mesma forma no máximo duas vezes por estrato, para não concentrar o sorteio.
            sorteio.shuffle(grupo)
            vistos = {}
            for c in grupo:
                chave = c['forma'].casefold()
                if vistos.get(chave, 0) >= 2:
                    continue
                vistos[chave] = vistos.get(chave, 0) + 1
                amostra.append(dict(c, estrato_sorteado=estrato))
                usados.add(c['id'])
                if sum(1 for a in amostra if a['conjunto'] == conjunto and a['estrato_sorteado'] == estrato) >= args.por_estrato:
                    break
    args.saida.write_text(json.dumps(amostra, ensure_ascii=False, indent=1), encoding='utf-8')
    for conjunto in divisao:
        print(conjunto, sum(1 for a in amostra if a['conjunto'] == conjunto), 'formas')


if __name__ == '__main__':
    main()
