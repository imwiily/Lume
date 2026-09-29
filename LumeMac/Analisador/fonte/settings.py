"""Configuração explícita de busca por manuscrito, sem perfis de estilo."""
from copy import deepcopy
import json
from pathlib import Path

RULES = ['tempo_verbal', 'estrutura', 'pontuacao_dialogo', 'palavra_consecutiva',
         'palavra_proxima', 'frase_duplicada', 'variacao_nome', 'duracao_suspensao',
         'adiamento_amanha', 'referente_proximidade', 'pronome_apos_corte']
LEGACY_RULES = RULES[:]
NEW_RULES = ['construcao_invalida', 'pontuacao_duplicada', 'espacamento', 'virgula_que_nao',
             'que_tonico_interrogativo', 'coerencia_temporal', 'acentuacao_contextual',
             'vocativo', 'capitalizacao_contextual', 'dialogo_contextual',
             'referente_contextual', 'gerundismo', 'memoria_narrativa',
             'conflito_habilidade', 'conflito_objeto', 'conflito_cronologia', 'coerencia_generica']
RULES += NEW_RULES
# Classes gramaticais com apoio sintático (fonte/grammar.py). Ligadas por padrão,
# como as anteriores; ‘desativar todas’ de configurações antigas continua valendo.
GRAMMAR_RULES = ['crase', 'homofonos', 'concordancia', 'regencia', 'virgula_sujeito_verbo']
RULES += GRAMMAR_RULES
SCOPES = ['narracao', 'dialogo', 'pensamento']
DEFAULT = {
    'schema_version': 1,
    'rules': {r: True for r in RULES},
    'tense_scopes': ['narracao'],
    'repetition_scopes': SCOPES[:],
    'word_distance': 8,
    'repetition_boundary': 'trecho',
    'duplicate_across_paragraphs': True,
    'duplicate_similarity': 1.0,
    'dialogue_dashes': True,
    'quotes_role': 'dialogo',
    'italic_thoughts': True,
    'ignored_names': [],
    'chapter_titles': [],
    'chapter_styles': [],
    'chapter_auto': True,
}

def validate(value):
    if not isinstance(value, dict) or value.get('schema_version', 1) != 1:
        raise ValueError('Configuração de busca inválida ou versão não suportada.')
    if set(value) - set(DEFAULT):
        raise ValueError('Configuração contém opções desconhecidas: ' + ', '.join(sorted(set(value)-set(DEFAULT))))
    result = deepcopy(DEFAULT)
    result.update(value)
    rules = value.get('rules', {})
    if not isinstance(rules, dict) or set(rules)-set(RULES) or any(type(v) is not bool for v in rules.values()):
        raise ValueError('Lista de verificações inválida.')
    result['rules'] = {**DEFAULT['rules'], **rules}
    # Preserva ‘desativar todas’ em configurações da versão anterior.
    if set(LEGACY_RULES).issubset(rules) and not any(rules.values()):
        result['rules'] = {r: False for r in RULES}
    for key in ['tense_scopes','repetition_scopes']:
        if not isinstance(result[key], list) or any(x not in SCOPES for x in result[key]):
            raise ValueError('Áreas de busca inválidas: ' + key)
    for key in ['dialogue_dashes','italic_thoughts','duplicate_across_paragraphs','chapter_auto']:
        if type(result[key]) is not bool:
            raise ValueError('Opção booleana inválida: ' + key)
    if type(result['word_distance']) is not int or not 2 <= result['word_distance'] <= 40:
        raise ValueError('A distância deve estar entre 2 e 40 palavras.')
    if result['repetition_boundary'] not in ['trecho','frase']:
        raise ValueError('Limite de repetição inválido.')
    if type(result['duplicate_similarity']) not in [int,float] or not .8 <= result['duplicate_similarity'] <= 1:
        raise ValueError('A semelhança de frases deve estar entre 0,80 e 1,00.')
    if result['quotes_role'] not in SCOPES:
        raise ValueError('Marcação por aspas inválida.')
    for key in ['ignored_names','chapter_titles','chapter_styles']:
        if (not isinstance(result[key], list) or len(result[key]) > 500
                or any(not isinstance(x,str) or not x.strip() or len(x)>200 for x in result[key])):
            raise ValueError('Lista inválida: ' + key)
    return result

def load(path):
    path=Path(path)
    if path.stat().st_size > 200_000:
        raise ValueError('Configuração maior que 200 KB.')
    return validate(json.loads(path.read_text(encoding='utf-8')))
