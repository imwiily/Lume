"""Apresentação local dos resultados do Validador de decisões (registros V4.1/V5).

Só formata o que o registro persistido já contém: não chama modelo, não lê manuscrito, não altera registro,
classificação, prioridade, diagnóstico nem decisão humana. Quando um dado não existe no registro, a saída diz
"informação insuficiente" em vez de preencher. Mantém separados o *fenômeno observado* (algo que merece olhar)
e o *problema técnico identificado* (desvio com fundamento suficiente, segundo o modelo; não é a decisão humana "Erro confirmado").
"""
from copy import deepcopy

INSUFICIENTE = "informação insuficiente no registro"

RESULTADO = {
    "mantida": "Decisão mantida",
    "contestada": "Decisão contestada pelo modelo (a decisão humana não foi alterada)",
    "revisao_recomendada": "Revisão recomendada (o modelo reconhece o desvio, sem contestar a decisão)",
    "apontamento_inadequado": "O apontamento do detector não se sustenta",
    "inconclusiva": "Inconclusiva: a validação não chegou a uma conclusão segura",
}
EXISTE = {"sim": "o modelo considerou que há desvio", "nao": "o modelo não encontrou desvio",
          "incerto": "o modelo não conseguiu dizer se há desvio"}
NATUREZA = {"objetivo": "de natureza objetiva (resposta única na norma)",
            "interpretativo": "de natureza interpretativa (depende de leitura)", "nenhuma": None}
CERTEZA = {"clara": "inequívoco no texto enviado", "discutivel": "admite outra leitura razoável", "nao_se_aplica": None}
GRAVIDADE = {"alta": "gravidade alta", "media": "gravidade média", "baixa": "gravidade baixa", "nenhuma": None}
MOTIVO = {
    "resposta_contraditoria": "a resposta do modelo era internamente contraditória e foi rebaixada",
    "conflito_entre_itens": "outro julgamento sobre o mesmo trecho conflitava com este",
    "ocorrencia_divergente": "o modelo se referiu a outra ocorrência do mesmo texto",
    "evidencia_ausente": "o modelo não apresentou a evidência exigida",
    "evidencia_inexistente": "a evidência citada pelo modelo não existe no texto enviado",
    "evidencia_de_outra_ocorrencia": "a evidência citada não cobre este trecho",
    "intencao_indeterminada": "não há como saber, pelo texto enviado, se o desvio foi intencional",
    "intencao_nao_determinada": "não há como saber, pelo texto enviado, se o desvio foi intencional",
}


def _trecho(alerta):
    if not alerta:
        return None
    t = alerta.get("text") or ""
    i, f = alerta.get("start"), alerta.get("end")
    return t[i:f] if isinstance(i, int) and isinstance(f, int) else None


def problema_tecnico(registro):
    """('identificado'|'discutivel'|'nao_estabelecido'|'nao_identificado', rótulo). Sempre diagnóstico do modelo
    (existe e certeza); nunca confirmação humana, que é a decisão "Erro confirmado" do revisor."""
    t = registro.get("problema_tecnico") or {}
    existe, certeza = t.get("existe"), t.get("certeza")
    if existe == "sim" and certeza == "clara":
        return "identificado", "Problema técnico identificado pelo modelo, com certeza clara (diagnóstico da IA; não é confirmação humana)"
    if existe == "sim":
        return "discutivel", "Desvio reconhecido pelo modelo, mas discutível (diagnóstico da IA; não é erro confirmado)"
    if existe == "nao":
        return "nao_identificado", "Problema técnico não identificado pelo modelo"
    if existe == "incerto":
        return "nao_estabelecido", "Problema técnico não estabelecido pelo modelo (resultado incerto)"
    return "nao_estabelecido", f"Problema técnico: {INSUFICIENTE}"


def _identificado(registro):
    t = registro.get("problema_tecnico") or {}
    partes = [EXISTE.get(t.get("existe"))]
    for campo, tabela in (("natureza", NATUREZA), ("certeza", CERTEZA), ("gravidade", GRAVIDADE)):
        partes.append(tabela.get(t.get(campo)))
    partes = [p for p in partes if p]
    return partes[0].capitalize() + (": " + "; ".join(partes[1:]) if len(partes) > 1 else "") if partes else None


def _por_que_nao_concluiu(registro):
    """Razões estruturadas registradas; nunca inferidas do texto da explicação."""
    razoes = []
    t = registro.get("problema_tecnico") or {}
    av = registro.get("avaliacao") or {}
    if t.get("existe") == "incerto":
        razoes.append("o modelo registrou dúvida sobre a existência do desvio (existe = incerto)")
    if av.get("evidencia_suficiente") is False:
        razoes.append("o modelo declarou que o texto enviado não bastava para concluir (evidencia_suficiente = falso)")
    if registro.get("motivo") in MOTIVO:
        razoes.append(MOTIVO[registro["motivo"]])
    if registro.get("motivo_inconclusivo") in MOTIVO:
        razoes.append(MOTIVO[registro["motivo_inconclusivo"]])
    return razoes


def apresentar(registro, alerta=None):
    """Dicionário de apresentação. `alerta` (opcional) é o finding do relatório: dá categoria, hipótese do
    detector e trecho. Não modifica `registro` nem `alerta`."""
    r = deepcopy(registro)
    estado = r.get("estado")
    nivel, rotulo = problema_tecnico(r)
    alvo = _trecho(alerta)
    explicacao = (r.get("explicacao") or "").strip()
    ativas = [e for e in r.get("evidencias_verificadas", []) if e.get("situacao") == "ativa"]
    descartadas = [e for e in r.get("evidencias_verificadas", []) if e.get("situacao") != "ativa"]
    razoes = _por_que_nao_concluiu(r) if estado in ("inconclusiva", "revisao_recomendada") or nivel == "nao_estabelecido" else []
    contexto = []
    if r.get("antecedentes"):
        contexto.append("antecedentes enviados: " + ", ".join(f"§{n}" for n in r["antecedentes"]))
    if r.get("pediu_mais_contexto"):
        contexto.append("o modelo pediu mais contexto"
                        + (" (atendido)" if r["pediu_mais_contexto"].get("atendido") else " (não atendido)"))
    humano = []
    if estado == "inconclusiva":
        humano.append("Decidir se o fenômeno observado é uma escolha do autor ou deve ser revisto: o modelo não "
                      "apresentou base suficiente para afirmar erro nem para afirmar adequação.")
    elif estado == "revisao_recomendada":
        humano.append("O modelo reconhece o desvio, mas não há como saber se foi intencional: a avaliação "
                      "editorial é humana.")
    elif nivel == "discutivel":
        humano.append("O modelo admite outra leitura razoável: a escolha entre as leituras é editorial.")
    humano.append(f"A decisão registrada ({r.get('decisao_humana') or r.get('decisao') or INSUFICIENTE}) "
                  "permanece como está; esta validação não a altera.")
    return {
        "resultado": RESULTADO.get(estado, f"Resultado: {INSUFICIENTE}"),
        "estado": estado,
        "decisao_humana": r.get("decisao_humana") or r.get("decisao"),
        "alvo": alvo,
        "fenomeno_investigado": {
            "categoria": (alerta or {}).get("category"),
            "hipotese_do_detector": (alerta or {}).get("reason"),
            "nota": "hipótese do detector, não um fato",
        } if alerta else INSUFICIENTE,
        "problema_tecnico": {"nivel": nivel, "rotulo": rotulo},
        "o_que_o_modelo_identificou": _identificado(r) or INSUFICIENTE,
        "explicacao_do_modelo": explicacao or INSUFICIENTE,
        "por_que_nao_concluiu": razoes or (INSUFICIENTE if estado == "inconclusiva" else None),
        "evidencias_verificadas": [{"papel": e.get("sustenta"), "paragrafo": e.get("paragrafo"), "trecho": e.get("trecho")}
                                   for e in ativas] or "nenhuma evidência verificada registrada para este resultado",
        "evidencias_descartadas": [{"papel": e.get("sustenta"), "motivo": e.get("motivo")} for e in descartadas],
        "contexto": contexto,
        "sugestao_do_modelo": (r.get("recomendacao") or "").strip() or None,
        "depende_de_avaliacao_humana": humano,
    }


def markdown(a):
    """Texto legível. Cada afirmação vem de `apresentar`; nada novo é acrescentado."""
    L = [f"**{a['resultado']}**", ""]
    if a["alvo"]:
        L.append(f"- Trecho apontado: «{a['alvo']}»")
    L.append(f"- Decisão do revisor: {a['decisao_humana'] or INSUFICIENTE}")
    f = a["fenomeno_investigado"]
    if isinstance(f, dict):
        L.append(f"- Fenômeno investigado: {f['categoria'] or INSUFICIENTE} — hipótese do detector (não confirmada): "
                 f"{f['hipotese_do_detector'] or INSUFICIENTE}")
    else:
        L.append(f"- Fenômeno investigado: {f}")
    L.append(f"- {a['problema_tecnico']['rotulo']}")
    L.append(f"- O que o modelo identificou: {a['o_que_o_modelo_identificou']}")
    L.append(f"- Explicação do modelo: {a['explicacao_do_modelo']}")
    p = a["por_que_nao_concluiu"]
    if p:
        L.append("- Por que não concluiu: " + (p if isinstance(p, str) else "; ".join(p)))
    ev = a["evidencias_verificadas"]
    L.append("- Evidências verificadas: " + (ev if isinstance(ev, str) else
                                            "; ".join(f"§{e['paragrafo']} «{e['trecho']}» ({e['papel']})" for e in ev)))
    for d in a["evidencias_descartadas"]:
        L.append(f"- Evidência descartada ({d['papel']}): {d['motivo'] or INSUFICIENTE}")
    for c in a["contexto"]:
        L.append(f"- Contexto: {c}")
    if a["sugestao_do_modelo"]:
        L.append(f"- Sugestão do modelo (nada é aplicado ao manuscrito): {a['sugestao_do_modelo']}")
    for h in a["depende_de_avaliacao_humana"]:
        L.append(f"- Depende da avaliação humana: {h}")
    return "\n".join(L)
