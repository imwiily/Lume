"""Etapas sequenciais sobre uma captura imutável; sem correção automática."""
from copy import deepcopy
from dataclasses import asdict
from time import perf_counter
from .contracts import Manuscript, standardize
from .settings import GRAMMAR_RULES, validate

STAGES = (
    ("linguistic", "Revisão linguística"),
    ("morphosyntactic", "Análise morfossintática"),
    ("editorial", "Contexto curto"),
    ("global_coherence", "Coerência global"),
    ("audit", "Auditoria final"),
)


def run(blocks, model_loader, *, settings=None, tense="auto", mode="ambas",
        original=None, languagetool=False, port=8081, progress=None):
    if mode not in ("linguistica", "editorial", "ambas"):
        raise ValueError("Modo de análise inválido.")
    options = validate(settings or {})
    manuscript = Manuscript.capture(blocks)
    blocks = manuscript.blocks
    previous = Manuscript.capture(original).blocks if original else None
    rules = options["rules"]
    linguistic_mode = mode in ("linguistica", "ambas")
    editorial_mode = mode in ("editorial", "ambas")
    findings, warnings, stages = [], [], []
    meta = {"tempo": "não analisado", "paragrafos": len(blocks), "modelo": "não utilizado",
            "versao_modelo": "", "modo": mode}
    nlp = None
    scenes = []
    from .semantic import RULES as SEMANTIC_RULES, extract, FactBank, compare
    semantic_enabled = editorial_mode and any(rules[r] for r in SEMANTIC_RULES)

    def model():
        nonlocal nlp
        if nlp is None:
            nlp = model_loader()
            meta.update(modelo=nlp.meta.get("name"), versao_modelo=nlp.meta.get("version"))
        return nlp

    def selected(names):
        value = deepcopy(options)
        value["rules"] = {name: rules[name] and name in names for name in rules}
        return value

    def linguistic():
        from .linguistic import analyze
        from .editorial.repetition import analyze as repetition
        out = analyze(blocks, options)
        if rules["palavra_consecutiva"]:
            repeated = repetition(blocks, selected(["palavra_consecutiva"]))
            # A camada legada permanece linguística para relatórios anteriores.
            for item in repeated:
                item["layer"] = "linguistica"
            out.extend(repeated)
        if languagetool:
            from .languagetool import check
            extra, extra_warnings = check(blocks, port, options["italic_thoughts"], settings=options)
            # A regra específica do FONTE explica melhor o mesmo trecho.
            covered = [(f["paragraph"], f["start"], f["end"]) for f in out]
            out.extend(f for f in extra if not any(
                p == f["paragraph"] and s < f["end"] and f["start"] < e for p, s, e in covered))
            warnings.extend(extra_warnings)
        else:
            warnings.append("Revisão linguística sem o corretor gramatical local (LanguageTool): ortografia geral e boa parte da concordância não foram verificadas. As regras do FONTE cobrem apenas classes específicas.")
        return out

    def morphosyntactic():
        from .search import linguistic as legacy
        from .temporal import analyze as temporal
        language_model = model()
        out, extra_warnings, data = legacy(blocks, language_model, tense, selected(["tempo_verbal", "estrutura"]))
        warnings.extend(extra_warnings); meta.update(data)
        meta.update(modelo=language_model.meta.get("name"), versao_modelo=language_model.meta.get("version"))
        if rules["coerencia_temporal"] or rules["acentuacao_contextual"]:
            reference = tense if tense != "auto" else data.get("tempo", "inconclusivo")
            if reference in {"passado", "presente"}:
                # A referência também vale para as regras contextuais quando a
                # verificação antiga de tempo predominante está desligada.
                meta["tempo"] = reference
            more = temporal(blocks, language_model, options, reference)
            covered = [(f["paragraph"], f["start"], f["end"]) for f in more]
            # A explicação específica substitui o alerta genérico sobre o mesmo verbo.
            out = [f for f in out if not (f["category"] == "Tempo verbal" and
                   any(p == f["paragraph"] and s <= f["start"] and f["end"] <= e
                       for p, s, e in covered))]
            out.extend(more)
            meta["temporal_relations"] = ["conditional_future", "simultaneous_present",
                                          "ambiguous_simultaneity", "coordinated_past_present"]
        if any(rules[r] for r in GRAMMAR_RULES):
            from .grammar import analyze as grammar
            # O mesmo trecho não recebe um segundo alerta do corretor geral.
            reported = [(f["paragraph"], f["start"], f["end"]) for f in findings
                        if f["source"].startswith("LanguageTool")]
            out.extend(grammar(blocks, language_model, options, skip=reported))
        return out

    def editorial():
        nonlocal scenes
        from .editorial import analyze as legacy
        out = []
        if linguistic_mode and rules["pontuacao_dialogo"]:
            from .search import linguistic as grammar
            extra, extra_warnings, data = grammar(blocks, model(), tense, selected(["pontuacao_dialogo"]))
            meta.update({key: value for key, value in data.items() if key not in ("tempo", "contagem_verbos")})
            for item in extra:
                item["layer"] = "linguistica"  # Compatibilidade com os filtros v0.6.
            out.extend(extra); warnings.extend(extra_warnings)
        if editorial_mode:
            extra, extra_warnings = legacy(blocks, previous, selected(
                ["palavra_proxima", "frase_duplicada", "referente_proximidade", "pronome_apos_corte"]))
            out.extend(extra); warnings.extend(extra_warnings)
            from .editorial.context import analyze as contextual, RULES as CONTEXT_RULES
            if semantic_enabled or any(rules[r] for r in CONTEXT_RULES):
                docs = list(model().pipe((b.text for b in blocks), batch_size=32))
                if semantic_enabled:
                    scenes = extract(manuscript, docs, options)
                    meta["scenes"] = [asdict(scene) for scene in scenes]
                if any(rules[r] for r in CONTEXT_RULES):
                    out.extend(contextual(blocks, model(), options, docs=docs))
        return out

    def global_coherence():
        from .editorial import analyze as legacy
        out, extra_warnings = legacy(blocks, settings=selected(
            ["variacao_nome", "duracao_suspensao", "adiamento_amanha"]))
        warnings.extend(extra_warnings)
        if semantic_enabled:
            bank = FactBank.consolidate(scenes)
            out.extend(compare(bank, manuscript, options))
            meta["fact_bank"] = bank.to_dict()
            for scene in meta.get("scenes", []):
                scene["incoming_fact_ids"] = bank.incoming_fact_ids.get(scene["id"], [])
                # Projeção final consistente nos dois caminhos JSON; objetos Scene
                # da etapa Editorial permanecem intactos.
                scene["facts"] = [deepcopy(f) for f in bank.facts if f["scene"] == scene["id"]]
            from .narrative import diagnostics
            meta["narrative_diagnostics"] = diagnostics(scenes, bank)
            meta["narrative_summary"] = dict(scenes=len(scenes), facts=len(bank.facts),
                                              characters=len(bank.characters), objects=len(bank.objects), events=len(bank.events))
        return out

    from .linguistic import RULES
    jobs = [
        (linguistic_mode and (languagetool or any(rules[r] for r in (*RULES, "palavra_consecutiva"))), linguistic,
         "Padrões determinísticos; pontuação e interrogação também em falas/pensamentos. LanguageTool opcional."),
        (linguistic_mode and (rules["estrutura"] or rules["acentuacao_contextual"] or
            any(rules[r] for r in GRAMMAR_RULES) or
            ((rules["tempo_verbal"] or rules["coerencia_temporal"]) and options["tense_scopes"])), morphosyntactic,
         "Tempo predominante, estrutura, quatro relações temporais locais, acentuação verbal contextual, crase, homófonos, concordância, regência e vírgula entre sujeito e verbo. Cobertura parcial; homógrafos permanecem dúvidas."),
        (semantic_enabled or (linguistic_mode and rules["pontuacao_dialogo"]) or (editorial_mode and (
            any(rules[r] for r in ("palavra_proxima", "frase_duplicada", "referente_proximidade",
                                  "dialogo_contextual", "referente_contextual", "gerundismo")) or
            (rules["pronome_apos_corte"] and previous))), editorial,
         "Diálogo, repetições, gerundismo e referências em janelas curtas. Cenas, participantes, falantes, objetos, eventos e candidatos a referentes; extração parcial de fatos narrativos explícitos."),
        (semantic_enabled or (editorial_mode and any(rules[r] for r in ("variacao_nome", "duracao_suspensao", "adiamento_amanha"))), global_coherence,
         "Banco de fatos produzido pelas cenas; comparação de atributos, relações, posse, conhecimento, presença, estados e cronologia; regras anteriores preservadas. Cobertura parcial."),
        (False, None, "Auditor editorial independente ainda não implementado; nenhuma busca adicional foi realizada."),
    ]

    for (module, title), (enabled, action, detail) in zip(STAGES, jobs):
        stage = dict(module=module, title=title, state="pending", finding_count=0,
                     coverage="partial" if module != "audit" else "not_implemented", detail=detail)
        stages.append(stage)

        def emit(state):
            stage["state"] = state
            if progress:
                progress(dict(stage))

        if not enabled:
            emit("not_implemented" if module == "audit" else "skipped")
            continue
        emit("running")
        started = perf_counter()
        try:
            batch = standardize(action(), module, manuscript)
            seen = {f["id"]: f for f in findings}
            for item in batch:
                if item["id"] in seen:
                    if item != seen[item["id"]]:
                        raise ValueError("Identificador de ocorrência associado a resultados diferentes.")
                    continue
                findings.append(item); seen[item["id"]] = item
                stage["finding_count"] += 1
            stage["duration_ms"] = round((perf_counter() - started) * 1000)
            emit("completed")
        except BaseException:
            emit("failed")
            raise

    from .editorial.common import evidence
    positions = {b.number: i for i, b in enumerate(blocks)}
    for item in findings:
        if "context" not in item:
            i = positions[item["paragraph"]]
            item["context"] = [evidence(b) for b in blocks[max(0, i-2):i+3] if b.chapter == blocks[i].chapter]
    findings.sort(key=lambda f: (f["paragraph"], f["start"], f["category"]))
    meta.update(stages=stages, pipeline_version=2, occurrence_schema_version=1,
                text_index=manuscript.index(), confidence_semantics="rule_strength_not_calibrated_probability")
    warnings.append("Memória narrativa com cobertura restrita a fatos explícitos; identidade de objetos e referências permanecem hipóteses. Auditoria editorial independente ainda não implementada. Etapa concluída significa apenas que as regras disponíveis terminaram.")
    return findings, list(dict.fromkeys(warnings)), meta
