from .analysis import analyze, narrative_masks
from .segments import classify, masks
from .settings import validate


def linguistic(blocks, nlp, tense, settings):
    options=validate(settings)
    roles=classify(blocks,options)
    results=[];warnings=[];metadata={'tempo':'não analisado','paragrafos':len(blocks)}
    rules=options['rules']
    # As regras de estrutura e pontuação continuam restritas à narração.
    for allowed,active in [(options['tense_scopes'], ['tempo_verbal']),
                           (['narracao'], ['estrutura','pontuacao_dialogo'])]:
        enabled=[r for r in active if rules[r]]
        if not enabled or not allowed:
            continue
        findings,extra,meta=analyze(blocks,nlp,tense,True,masks_override=masks(blocks,roles,allowed),enabled_rules=enabled)
        results.extend(findings);warnings.extend(extra)
        if 'tempo_verbal' in enabled:
            metadata.update(meta)
        else:
            metadata.update({k:v for k,v in meta.items() if k not in ['tempo','contagem_verbos']})
    return results,list(dict.fromkeys(warnings)),metadata
