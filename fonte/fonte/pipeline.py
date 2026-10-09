"""Etapas sequenciais sobre uma captura imutável; sem correção automática."""
from copy import deepcopy
from time import perf_counter
from .contracts import Manuscript, check_destination, standardize
from . import deduplicacao
from .settings import GRAMMAR_RULES, validate

STAGES = (
    ("linguistic", "Revisão linguística"),
    ("morphosyntactic", "Análise morfossintática"),
    ("editorial", "Contexto curto"),
    ("global_coherence", "Coerência global"),
    ("audit", "Auditoria final"),
)


def run(blocks, model_loader, *, settings=None, tense="auto", mode="ambas",
        original=None, languagetool=False, port=8081, progress=None, coerencia=None, auditoria=None,
        languagetool_falha=None):
    """`languagetool_falha`: motivo, quando o corretor pedido não pôde iniciar; a análise segue sem
    ele, marcada como parcial (o mesmo vale se ele parar de responder). `coerencia`: opções da Coerência com IA (pasta, documento, modelo, teto, esforco), que
    verifica contradições narrativas na etapa Coerência global. `auditoria`: opções da
    Auditoria final com IA, que procura o que as etapas anteriores deixaram passar."""
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
    atual = {}

    def avancar(feitos, total, unidade):
        """Andamento dentro da etapa em curso (campos opcionais do evento de progresso)."""
        if progress and "stage" in atual:
            progress(dict(atual["stage"], done=feitos, total=total, unit=unidade))

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
            from .languagetool import LanguageToolIndisponivel, check
            try:
                if languagetool_falha:
                    raise LanguageToolIndisponivel(languagetool_falha)
                extra, extra_warnings = check(blocks, port, options["italic_thoughts"], settings=options,
                                              avancar=lambda f, t: avancar(f, t, "parágrafos"))
            except LanguageToolIndisponivel as falha:
                # Sem nenhum alerta do corretor (nem os de antes da falha): a ausência é da etapa toda.
                meta["languagetool_status"] = "indisponivel"
                meta.setdefault("analise_parcial", {"ausente": []})["ausente"].append(
                    {"etapa": "linguistic", "componente": "LanguageTool", "motivo": str(falha)})
                atual["stage"]["ausente"] = "LanguageTool"
                warnings.append(f"Análise parcial: o corretor gramatical local (LanguageTool) foi pedido, mas não "
                                f"executou. {falha} Ortografia geral e boa parte da gramática não foram verificadas; "
                                "as regras do FONTE rodaram normalmente. Analise de novo com o corretor disponível "
                                "para uma leitura completa.")
            else:
                out.extend(extra)
                warnings.extend(extra_warnings)
        else:
            warnings.append("Revisão linguística sem o corretor gramatical local (LanguageTool): ortografia geral e boa parte da concordância não foram verificadas. As regras do FONTE cobrem apenas classes específicas.")
        return out

    def morphosyntactic():
        from .search import linguistic as legacy
        from .temporal import analyze as temporal
        language_model = model()
        out, extra_warnings, data = legacy(blocks, language_model, tense, selected(["tempo_verbal", "estrutura", "residuo_edicao"]))
        warnings.extend(extra_warnings); meta.update(data)
        # Tempo escolhido contrariado pela narração: avisa, sem mudar os alertas. Falas no
        # escopo distorcem a contagem (o presente é comum nelas); nesse caso, nada se conclui.
        if rules["tempo_verbal"] and set(options["tense_scopes"]) == {"narracao"}:
            from .analysis import tense_contradiction
            contradiction = tense_contradiction(data.get("contagem_verbos", {}), tense)
            if contradiction:
                meta["tempo_contradito"] = contradiction
                chosen, other = contradiction["escolhido"], contradiction["predominante"]
                share = round(100 * contradiction[other] / (contradiction["passado"] + contradiction["presente"]))
                warnings.append(
                    f"Tempo escolhido: {chosen}. A narração tem {contradiction[other]} verbos no {other} e "
                    f"{contradiction[chosen]} no {chosen} ({share}% no {other}). Se o livro é narrado no {other}, "
                    f"analise de novo com {other.capitalize()}: os alertas de tempo verbal desta análise "
                    "tratam como desvio o tempo da própria narração.")
        meta.update(modelo=language_model.meta.get("name"), versao_modelo=language_model.meta.get("version"))
        if rules["coerencia_temporal"] or rules["acentuacao_contextual"]:
            reference = tense if tense != "auto" else data.get("tempo", "inconclusivo")
            if reference in {"passado", "presente"}:
                # A referência também vale para as regras contextuais quando a
                # verificação antiga de tempo predominante está desligada.
                meta["tempo"] = reference
            more = temporal(blocks, language_model, options, reference)
            narrative_form = {"presente": "present", "passado": "past"}.get(reference)
            more = deduplicacao.relacao_que_repete_tempo_verbal(more, out, narrative_form)
            out = deduplicacao.tempo_verbal_sob_relacao(out, more)
            out.extend(more)
            meta["temporal_relations"] = ["conditional_future", "simultaneous_present",
                                          "ambiguous_simultaneity", "coordinated_past_present",
                                          "conditional_tense_mismatch", "coordinated_tense_mismatch",
                                          "past_present_past", "same_subject_narrative_shift",
                                          "local_narrative_tense_shift"]
        if any(rules[r] for r in GRAMMAR_RULES):
            from .grammar import analyze as grammar
            out.extend(grammar(blocks, language_model, options))
        return out

    def editorial():
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
            if any(rules[r] for r in CONTEXT_RULES):
                out.extend(contextual(blocks, model(), options))
        return out

    def global_coherence():
        from .editorial import analyze as legacy
        out, extra_warnings = legacy(blocks, settings=selected(
            ["variacao_nome", "duracao_suspensao", "adiamento_amanha"]))
        warnings.extend(extra_warnings)
        if coerencia:
            from .coerencia_ia import analisar as coerencia_ia
            extra, extra_warnings, rodada = coerencia_ia(blocks, registrar=lambda *_: None,
                                                         avancar=lambda f, t: avancar(f, t, "cenas"), **coerencia)
            out.extend(extra); warnings.extend(extra_warnings)
            meta["coerencia_ia"] = rodada
        return out

    def audit():
        from .auditoria_ia import auditar
        # Cópia: o auditor lê os alertas anteriores, mas não os altera.
        reference = tense if tense != "auto" else meta.get("tempo", "inconclusivo")
        out, extra_warnings, rodada = auditar(blocks, deepcopy(findings),
                                              avancar=lambda f, t: avancar(f, t, "trechos"),
                                              tempo=reference, configuracao=options, **auditoria)
        warnings.extend(extra_warnings)
        meta["auditoria_ia"] = rodada
        return out

    from .linguistic import RULES
    jobs = [
        (linguistic_mode and (languagetool or any(rules[r] for r in (*RULES, "palavra_consecutiva"))), linguistic,
         "Padrões determinísticos; pontuação e interrogação também em falas/pensamentos. LanguageTool opcional."),
        (linguistic_mode and (rules["estrutura"] or rules["residuo_edicao"] or rules["acentuacao_contextual"] or
            any(rules[r] for r in GRAMMAR_RULES) or
            ((rules["tempo_verbal"] or rules["coerencia_temporal"]) and options["tense_scopes"])), morphosyntactic,
         "Tempo predominante, estrutura, quatro relações temporais locais, acentuação verbal contextual, crase, homófonos, concordância, regência, vírgula entre sujeito e verbo, correlação de tempos, frase cortada e locuções. Cobertura parcial; homógrafos permanecem dúvidas."),
        ((linguistic_mode and rules["pontuacao_dialogo"]) or (editorial_mode and (
            any(rules[r] for r in ("palavra_proxima", "frase_duplicada", "referente_proximidade",
                                  "dialogo_contextual", "referente_contextual", "gerundismo")) or
            (rules["pronome_apos_corte"] and previous))), editorial,
         "Diálogo, repetições, gerundismo e referências em janelas curtas."),
        (bool(coerencia) or (editorial_mode and any(rules[r] for r in ("variacao_nome", "duracao_suspensao", "adiamento_amanha"))), global_coherence,
         "Variações de nomes e prazos; contradições narrativas com a Coerência com IA, quando ligada. Cobertura parcial."),
        (bool(auditoria), audit,
         "Problemas que as etapas anteriores deixaram passar, com a API do Claude; só quando ligada e confirmada. Cobertura parcial."),
    ]

    for (module, title), (enabled, action, detail) in zip(STAGES, jobs):
        stage = dict(module=module, title=title, state="pending", finding_count=0,
                     coverage="partial", detail=detail)
        stages.append(stage)

        def emit(state):
            stage["state"] = state
            if progress:
                progress(dict(stage))

        if not enabled:
            emit("skipped")
            continue
        emit("running")
        atual["stage"] = stage
        started = perf_counter()
        before = len(findings)
        try:
            # Uma ocorrência com trecho fora do texto (defeito de uma regra) é descartada e
            # avisada; não derruba a etapa nem o que já foi analisado.
            rejected = []
            batch = standardize(action(), module, manuscript, rejected=rejected)
            if rejected:
                meta.setdefault("ocorrencias_descartadas", []).extend(rejected)
                rules_hit = ", ".join(sorted({str(r["rule"]) for r in rejected}))
                warnings.append(f"{title}: {len(rejected)} alerta(s) descartado(s) porque apontavam um trecho "
                                f"que não existe no manuscrito (regra {rules_hit}). É um defeito do Lume, não "
                                "do seu texto; o restante da análise foi mantido.")
            novas = deduplicacao.mesmo_id(batch, findings)
            findings.extend(novas)
            stage["finding_count"] += len(novas)
            stage["duration_ms"] = round((perf_counter() - started) * 1000)
            emit("completed")
        except Exception as error:
            emit("failed")
            if module != "audit":
                raise
            # Nenhuma etapa depende da auditoria: a falha (API, teto, recusa) fica só nela.
            del findings[before:]
            stage["finding_count"] = 0
            warnings.append(f"{error} A auditoria final foi interrompida; as demais etapas foram concluídas "
                            "e o relatório foi mantido.")
        except BaseException:
            emit("failed")
            raise

    # FONTE × LanguageTool: só o mesmo fenômeno, com a mesma correção, vira uma ocorrência.
    findings, absorvidas = deduplicacao.consolidar(findings)
    if absorvidas:
        for stage in stages:
            stage["finding_count"] -= absorvidas.get(stage["module"], 0)
        meta["deduplicacao"] = {"absorvidos": sum(absorvidas.values()),
                                "criterio": "mesma família, trecho em comum e mesma correção"}
    from .editorial.common import evidence
    positions = {b.number: i for i, b in enumerate(blocks)}
    for item in findings:
        if "context" not in item:
            i = positions[item["paragraph"]]
            item["context"] = [evidence(b) for b in blocks[max(0, i-2):i+3] if b.chapter == blocks[i].chapter]
    # Destino editorial (política versionada): o que entra na fila, o que fica como observação e o
    # que vai só para o diagnóstico do motor. Não muda IDs, trechos nem severidades.
    from .politica import aplicar, politica
    findings, diagnostico = aplicar(findings)
    for item in findings + diagnostico:
        check_destination(item)
    findings.sort(key=lambda f: (f["paragraph"], f["start"], f["category"]))
    meta.update(politica_versao=politica()["versao"], diagnostico=diagnostico,
                destinos={d: sum(f["destino"] == d for f in findings + diagnostico)
                          for d in ("pendencia", "informacao", "diagnostico")},
                impeditivos=sum(f["impeditivo"] for f in findings))
    meta.update(stages=stages, pipeline_version=2, occurrence_schema_version=1,
                text_index=manuscript.index(), confidence_semantics="rule_strength_not_calibrated_probability")
    warnings.append("Etapa concluída significa apenas que as regras disponíveis terminaram; a cobertura continua parcial.")
    return findings, list(dict.fromkeys(warnings)), meta
