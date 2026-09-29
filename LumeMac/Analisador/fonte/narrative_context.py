"""Evidências locais de identidade; não contém nomes de obras ou personagens."""
import re
from .lexicon import flags, FINITE, NONVERB, NONFINITE

HUMAN = set('homem mulher garota garoto rapaz moça professor professora médico médica doutor doutora aluno aluna irmão irmã pai mãe filho filha senhor senhora'.split())
NO_NAMES = set('oi olá hã hum hm humm hamm hahaha haaaa ops ufa ué ah oh ei ai au tá ok bom bem melhor pior merda desgraça idiotice nojento patético fraco inútil desgraçado calma verdade interessante impossível entendo obrigado obrigada ótimo beleza eu você ele ela nós eles elas seu sua meu minha quem qual quando onde aquilo aquela'.split())
FIRST = {
    'cheguei': 'chegar', 'entrei': 'entrar', 'saí': 'sair', 'peguei': 'pegar',
    'recebi': 'receber', 'perdi': 'perder', 'abri': 'abrir', 'fechei': 'fechar',
    'tranquei': 'trancar', 'destranquei': 'destrancar', 'liguei': 'ligar',
    'desliguei': 'desligar', 'coloquei': 'colocar', 'guardei': 'guardar',
    'joguei': 'jogar', 'ativei': 'ativar', 'olhei': 'olhar', 'vi': 'ver',
    'soube': 'saber', 'aprendi': 'aprender', 'descobri': 'descobrir',
    'respondi': 'responder', 'perguntei': 'perguntar', 'pensei': 'pensar',
    'tirei': 'tirar', 'deixei': 'deixar', 'entreguei': 'entregar', 'reli': 'reler',
}
# "soube" é ambíguo entre primeira e terceira pessoa; exige sujeito explícito.
FIRST.pop('soube')


def valid_name(text):
    return all(part[:1].isupper() and part.isalpha() and part.casefold() not in NO_NAMES
               and not (flags(part) & FINITE and not flags(part) & (NONVERB | NONFINITE))
               and not part.casefold().endswith('mente')
               for part in text.split()) and bool(text.strip())


def person_name(text):
    parts = text.split()
    if len(parts) > 1 and parts[0].casefold() in HUMAN:
        return ' '.join(parts[1:])
    return text


def lemma(token):
    return FIRST.get(token.lower_, token.lemma_.casefold())


def first_person(token):
    return token.lower_ in FIRST or (token.pos_ in {'VERB', 'AUX'} and '1' in token.morph.get('Person') and 'Sing' in token.morph.get('Number'))


def narrator(scene, token, ev, key):
    if scene.narrator == 'unknown':
        # Identidade provisória de escopo local: mudança de foco não funde narradores.
        scene.narrator = key('char', 'narrador@' + scene.id)
    proof = ev(token.idx, token.idx + len(token))
    if not any(p['id'] == scene.narrator for p in scene.participants):
        scene.participants.append(dict(id=scene.narrator, name='Narrador (eu)', type='PERSON',
            category=None, entity_confidence=.85, gender='', number='Sing',
            role='actor', presence='explicit_action', provisional=True, evidence=proof))
    return scene.narrator


def reference_candidates(scene, proof, gender='', number='Sing'):
    """Somente antecedentes; janela discursiva não cria novas cenas."""
    candidates = {}
    for p in scene.participants:
        e = p['evidence']
        if e['range']['end'] > proof['range']['start'] or p.get('provisional') and p['id'] == scene.narrator:
            continue
        if gender and p.get('gender') and gender != p['gender']:
            continue
        if number and number != p.get('number', 'Sing'):
            continue
        candidates[p['id']] = p
    recent = {i:p for i,p in candidates.items() if proof['paragraph'] - p['evidence']['paragraph'] <= 3}
    return recent or candidates
