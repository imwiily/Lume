"""Análise editorial local, independente de modelos generativos e de spaCy."""
from . import chronology, repetition, entities, references
from .common import evidence, WORDS


def analyze(blocks, original=None, settings=None):
    from ..settings import validate
    options=validate(settings or {})
    active=options['rules']
    findings=[]
    if active['duracao_suspensao'] or active['adiamento_amanha']:
        findings.extend(f for f in chronology.analyze(blocks) if active[f['rule']])
    if any(active[r] for r in ['palavra_proxima','frase_duplicada']):
        # Consecutivas são executadas junto à camada linguística na CLI configurada.
        from copy import deepcopy
        repetition_options=deepcopy(options)
        repetition_options['rules']['palavra_consecutiva']=False
        findings.extend(repetition.analyze(blocks,repetition_options))
    if active['variacao_nome']:
        findings.extend(entities.analyze(blocks, options['ignored_names']))
    if active['referente_proximidade'] or (active['pronome_apos_corte'] and original):
        findings.extend(f for f in references.analyze(blocks,original if active['pronome_apos_corte'] else None) if active[f['rule']])
    positions = {b.number: i for i, b in enumerate(blocks)}
    for item in findings:
        i = positions[item["paragraph"]]
        item["context"] = [evidence(b) for b in blocks[max(0, i-2):i+3]
                           if b.chapter == blocks[i].chapter]
    warnings = [
        "Análise editorial experimental: regras locais de duração/adiamento, repetições, grafias próximas de nomes e referências em construções específicas. Não detecta todas as inconsistências nem interpreta o cânone, o registro de personagem ou a causalidade do enredo.",
        "Confiança baixa/média/alta descreve a força do indício da regra, não a probabilidade de existir um erro. Mesmo alertas de confiança alta exigem leitura humana.",
        "As regras de continuidade e referências examinam também falas e itálicos. Repetições seguem as áreas de busca configuradas.",
    ]
    if original:
        warnings.append("Comparação com original: procura pronomes próximos de cortes extensos por alinhamento de palavras; não resolve o referente. Edições, cenas movidas e repetições podem produzir falsos positivos ou omissões.")
        if sum(len(WORDS.findall(b.text)) for b in blocks + original) > 120_000:
            warnings.append("A comparação de cortes pode ter sido omitida pelo limite de 120 mil tokens combinados. Divida os documentos em partes correspondentes.")
    return findings, warnings
