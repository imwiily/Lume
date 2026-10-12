"""Integração supervisionada da V5 ao Lume (Fase 1: backend).

Camada fina sobre `validador_v5`: não duplica nem altera a inferência, o prompt, o contrato nem a persistência
da V5; só decide O QUE é enviado (IDs explícitos, versão verificável), QUANDO (estimativa e teto antes), e COMO o
resultado é descrito (estruturas separadas e rótulos que não tratam toda contestação como "erro").

Garantias:
  - só entram decisões explicitamente selecionadas e elegíveis; nada é inferido ou ampliado;
  - o manuscrito precisa ser a versão do relatório (SHA-256) ou, só com autorização, ter o parágrafo e o contexto
    registrado no relatório presentes; o resto fica fora e é dito;
  - a segunda rodada de contexto da V5 fica DESLIGADA por padrão (`rodada_extra=False`, sem tocar na V5); o que o
    modelo pediu é registrado como pendência para uma autorização futura;
  - estado da V5 em `validacoes-v5.json` (trava própria); aqui só se acrescenta `validacoes-v5-integracao.json` e,
    quando o autor pede reanálise explícita, `validacoes-v5-historico.json` (nada é apagado sem cópia);
  - decisões humanas, relatório e manuscrito nunca são gravados.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from . import apresentacao_validacao as ap
from . import validador_decisoes as vd
from . import validador_v4 as v4
from . import validador_v5 as v5

VERSAO_INTEGRACAO = 1
ELEGIVEIS = ("Erro confirmado", "Estilo do autor", "Falso positivo", "Intencional", "Aceito editorialmente")
TETO_PADRAO, TETO_MAXIMO = 1.0, 5.0
ITENS_PADRAO, ITENS_MAXIMO = 40, 60
LATERAL = "validacoes-v5-integracao.json"
HISTORICO = "validacoes-v5-historico.json"
ROTULO = {
    "mantida": "A IA não encontrou motivo para reconsiderar a decisão",
    "contestada": "A IA discorda da decisão registrada",
    "revisao_recomendada": "A IA reconhece o desvio; a escolha editorial continua sendo sua",
    "apontamento_inadequado": "A IA considera que o apontamento do detector não se sustenta",
    "inconclusiva": "Sem conclusão segura da IA",
}
AVISO = "Diagnóstico da IA: não é confirmação humana nem altera a sua decisão."


class ErroIntegracao(ValueError):
    """Erro esperado, com código estável para o app."""
    def __init__(self, codigo, mensagem):
        super().__init__(mensagem)
        self.codigo = codigo


# --- seleção e verificação de versão -----------------------------------------------------------------

def selecionar(findings, decisoes, ids, maximo=ITENS_PADRAO):
    """(decisões dos IDs aceitos, excluídos). Só o que o autor listou; nunca completa a lista."""
    if not 1 <= maximo <= ITENS_MAXIMO:
        raise ErroIntegracao("limite_invalido", f"O limite de itens deve estar entre 1 e {ITENS_MAXIMO}.")
    ids = list(dict.fromkeys(str(i) for i in (ids or [])))
    if not ids:
        raise ErroIntegracao("selecao_vazia", "Nenhum apontamento foi selecionado.")
    if len(ids) > maximo:
        raise ErroIntegracao("itens_demais", f"{len(ids)} apontamentos selecionados; o limite desta execução é {maximo}.")
    no_relatorio = {f["id"] for f in findings}
    aceitas, excluidos = {}, []
    for i in ids:
        if i not in no_relatorio:
            excluidos.append({"id": i, "motivo": "id_fora_do_relatorio"})
        elif decisoes.get(i) not in ELEGIVEIS:
            excluidos.append({"id": i, "motivo": "decisao_nao_elegivel"})
        else:
            aceitas[i] = decisoes[i]
    return aceitas, excluidos


def verificar_versao(blocks, findings, aceitas, sha_arquivo, sha_relatorio, permitir_parcial=False):
    """(níveis por ID aceito, excluídos). Níveis: `versao_confere` (SHA do manuscrito = SHA do relatório) ou
    `contexto_parcial` (versão diferente, mas o parágrafo e os vizinhos que o relatório registrou estão presentes;
    exige autorização). Sem uma das duas coisas, o item não é enviado."""
    exata = bool(sha_relatorio) and sha_arquivo == sha_relatorio
    por_id = {f["id"]: f for f in findings}
    niveis, excluidos = {}, []
    for ident in aceitas:
        if exata:
            niveis[ident] = "versao_confere"
            continue
        if not permitir_parcial:
            excluidos.append({"id": ident, "motivo": "versao_do_manuscrito_diferente"})
            continue
        f = por_id[ident]
        posicoes = [k for k, b in enumerate(blocks) if b.text == f["text"]]
        vizinhos_esperados = [e["text"] for e in f.get("context", []) if e.get("paragraph") != f["paragraph"]]
        ok = len(posicoes) == 1 and bool(vizinhos_esperados) and all(
            any(b.text == t for b in blocks[max(0, posicoes[0] - 3):posicoes[0] + 4]) for t in vizinhos_esperados)
        if ok:
            niveis[ident] = "contexto_parcial"
        else:
            excluidos.append({"id": ident, "motivo": "contexto_nao_verificavel"})
    return niveis, excluidos


def preparar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, *, maximo=ITENS_PADRAO, permitir_parcial=False):
    aceitas, excluidos = selecionar(findings, decisoes, ids, maximo)
    niveis, fora_versao = verificar_versao(blocks, findings, aceitas, sha_arquivo, sha_relatorio, permitir_parcial)
    recusados = {e["id"] for e in fora_versao}
    return {"decisoes": {i: d for i, d in aceitas.items() if i not in recusados}, "niveis": niveis,
            "excluidos": excluidos + fora_versao,
            "versao_manuscrito": "confere" if sha_relatorio and sha_arquivo == sha_relatorio else "diferente"}


def _validar_teto(teto):
    if not (0 < teto <= TETO_MAXIMO):
        raise ErroIntegracao("teto_invalido", f"O teto desta execução deve estar entre US$ 0,01 e US$ {TETO_MAXIMO:.2f}.")


# --- estado complementar ------------------------------------------------------------------------------

def _ler_lateral(pasta):
    caminho = Path(pasta) / LATERAL
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
        return dict(d.get("itens", {})) if d.get("integracao") == VERSAO_INTEGRACAO else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _gravar_json(pasta, nome, dados):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    tmp = pasta / (nome + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pasta / nome)


class _Captura:
    """Proxy do cliente: repassa tudo e só registra o que o modelo pediu de contexto adicional."""
    def __init__(self, cliente):
        self._c = cliente
        self.pedidos_de_contexto = {}

    def __getattr__(self, nome):
        return getattr(self._c, nome)

    def json(self, *args, **kwargs):
        resposta = self._c.json(*args, **kwargs)
        for e in resposta.get("avaliacoes", []) if isinstance(resposta, dict) else []:
            if isinstance(e, dict) and e.get("precisa_mais_contexto") is True and isinstance(e.get("id"), str):
                self.pedidos_de_contexto[e["id"]] = {
                    "paragrafos": [n for n in (e.get("paragrafos_solicitados") or []) if isinstance(n, int)][:3],
                    "termos": [str(t)[:80] for t in (e.get("termos_solicitados") or [])][:3]}
        return resposta


# --- estimativa e execução -----------------------------------------------------------------------------

def estimar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, pasta, *, teto=TETO_PADRAO,
            maximo=ITENS_PADRAO, permitir_parcial=False, autorizar_contexto=False, config=None, revalidar=()):
    """Sem rede e sem gravar. Diz o que seria enviado, o custo esperado e o pior caso."""
    _validar_teto(teto)
    p = preparar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, maximo=maximo, permitir_parcial=permitir_parcial)
    por_id = {f["id"]: f for f in findings}
    rev = [i for i in dict.fromkeys(revalidar) if i in p["decisoes"]]       # só desatualizados: a V5 ignora o resto
    e = v5.estimar(blocks, findings, p["decisoes"], pasta, config=config, teto=teto, revalidar=rev) if p["decisoes"] else None
    a_enviar = []
    if e:
        plano = v5.planejar(blocks, findings, p["decisoes"], pasta, config=config, revalidar=rev)
        a_enviar = [i["id"] for i in plano["a_analisar"]]
    capitulos = sorted({por_id[i].get("chapter") or "—" for i in a_enviar})
    return {
        "integracao": VERSAO_INTEGRACAO, "provedor": "openai", "modelo": v5.MODELO, "esforco": v5.ESFORCO,
        "armazenamento_pelo_provedor": "store=false (a resposta não é retida para consulta)",
        "selecionadas": len(set(str(i) for i in ids)), "aceitas": len(p["decisoes"]), "excluidos": p["excluidos"],
        "versao_manuscrito": p["versao_manuscrito"], "verificacao": dict(Counter(p["niveis"].values())),
        "a_enviar": [{"id": i, "paragrafo": por_id[i]["paragraph"], "categoria": por_id[i]["category"]} for i in a_enviar],
        "capitulos_a_enviar": capitulos,
        "reutilizadas_sem_custo": e["reutilizadas_sem_custo"] if e else 0,
        "nao_localizadas": e["nao_localizadas"] if e else 0,
        "pedidos_primeira_rodada": e["chamadas_primeira_rodada"] if e else 0,
        "custo_esperado_usd": e["custo_por_cenario_de_raciocinio_usd"]["0"] if e and a_enviar else 0.0,
        "custo_maximo_usd": e["custo_maximo_primeira_rodada_usd"] if e and a_enviar else 0.0,
        "pior_pedido_usd": e["pior_chamada_usd"] if e and a_enviar else 0.0,
        "teto_minimo_usd": e["teto_minimo_usd"] if e and a_enviar else 0.0,
        "teto_usd": teto, "teto_padrao_usd": TETO_PADRAO, "teto_maximo_usd": TETO_MAXIMO,
        "cabe_no_teto": (e["teto_minimo_usd"] <= teto) if e and a_enviar else True,
        "segunda_rodada": {"autorizada": bool(autorizar_contexto),
                           "custo_maximo_adicional_usd": e["custo_maximo_primeira_rodada_usd"] if e and a_enviar else 0.0},
        "fonte_dos_precos": e["fonte_dos_precos"] if e else None,
        "aviso": "Estimativa por caracteres; o raciocínio do modelo não é previsível e o custo real pode diferir. "
                 "Nada é enviado antes da confirmação."}


def _reanalisar(pasta, ids, atuais):
    """Move para o histórico, com cópia integral, os registros dos IDs pedidos; só sob a trava da V5."""
    if not ids:
        return []
    movidos = []
    with v5.trava(pasta):
        itens, _ = v5.ler(pasta)
        historico = []
        try:
            historico = json.loads((Path(pasta) / HISTORICO).read_text(encoding="utf-8")).get("registros", [])
        except (OSError, ValueError, AttributeError):
            pass
        for i in ids:
            if i in itens and i in atuais:
                historico.append({"movido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "registro": itens.pop(i)})
                movidos.append(i)
        if movidos:
            _gravar_json(pasta, HISTORICO, {"integracao": VERSAO_INTEGRACAO, "registros": historico})
            v5.gravar(pasta, itens)
    return movidos


def executar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, pasta, *, teto=TETO_PADRAO,
             maximo=ITENS_PADRAO, permitir_parcial=False, autorizar_contexto=False, reanalisar=(), tentativas=None,
             cliente=None, transporte=None, avancar=None, meta=None, config=None, revalidar=()):
    """Executa a V5 só para os IDs aceitos. Devolve o resumo da integração (a V5 grava o próprio estado)."""
    _validar_teto(teto)
    p = preparar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, maximo=maximo, permitir_parcial=permitir_parcial)
    resumo = {"integracao": VERSAO_INTEGRACAO, "excluidos": p["excluidos"], "versao_manuscrito": p["versao_manuscrito"],
              "verificacao": dict(Counter(p["niveis"].values())), "decisoes_alteradas": False,
              "segunda_rodada_autorizada": bool(autorizar_contexto), "pendencias_de_contexto": 0, "reanalisados": []}
    if not p["decisoes"]:
        return {**resumo, "analisadas_agora": 0, "mensagem": "Nenhum apontamento verificável para enviar.", "v5": None}
    mover = [i for i in dict.fromkeys(reanalisar) if i in p["decisoes"]]
    rev = [i for i in dict.fromkeys(revalidar) if i in p["decisoes"]]
    plano = v5.planejar(blocks, findings, p["decisoes"], pasta, config=config, revalidar=rev)
    if plano["a_analisar"] or mover:
        # com reanálise, todos os selecionados contam como novos (pasta=None): pior caso conservador
        est = v5.estimar(blocks, findings, p["decisoes"], None if mover else pasta, config=config, teto=teto,
                         revalidar=rev)
        if est["teto_minimo_usd"] > teto:
            raise ErroIntegracao("teto_insuficiente",
                                 f"O teto de US$ {teto:.2f} não cobre o pior caso de um pedido (US$ {est['teto_minimo_usd']:.2f}). "
                                 "Nada foi enviado.")
    if cliente is None and transporte is None and not v5.chave_da_api():
        raise ErroIntegracao("chave_ausente", "Chave da API da OpenAI ausente. Nada foi enviado.")
    try:
        resumo["reanalisados"] = _reanalisar(pasta, mover, p["decisoes"])
        captura = None
        if cliente is None:
            from coerencia.modelo import Orcamento
            cliente = v5.OpenAI(v5.MODELO, v5.ESFORCO, orcamento=Orcamento(teto), transporte=transporte)
            if tentativas is not None:
                cliente.TENTATIVAS = max(1, min(3, int(tentativas)))
            cliente.verificar()
        captura = _Captura(cliente)
        registros, avisos, v5resumo = v5.avaliar(
            blocks, findings, p["decisoes"], pasta=pasta, teto=teto, cliente=captura, rodada_extra=bool(autorizar_contexto),
            avancar=avancar, meta=dict(meta or {}, integracao=VERSAO_INTEGRACAO), config=config, revalidar=rev)
    except v4.ValidacaoEmAndamento as erro:
        raise ErroIntegracao("em_andamento", str(erro)) from None
    lateral = _ler_lateral(pasta)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for i, nivel in p["niveis"].items():
        r = registros.get(i)
        if not r or r.get("estado_validacao") != "analisada":
            continue
        anterior = lateral.get(i, {}) if lateral.get(i, {}).get("chave_conteudo") == r.get("chave_conteudo") else {}
        pedido = None if autorizar_contexto else (captura.pedidos_de_contexto.get(i) or anterior.get("pendencia_contexto"))
        lateral[i] = {"verificacao": nivel, "chave_conteudo": r.get("chave_conteudo"), "registrado_em": agora,
                      "pendencia_contexto": pedido}
    _gravar_json(pasta, LATERAL, {"integracao": VERSAO_INTEGRACAO, "itens": lateral})
    resumo.update(pendencias_de_contexto=sum(1 for v in lateral.values() if v.get("pendencia_contexto")),
                  analisadas_agora=v5resumo["analisadas_agora"], avisos=avisos, v5=v5resumo,
                  arquivo=str(Path(pasta) / v5.ARQUIVO))
    return resumo


def previa(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, pasta, *, maximo=ITENS_PADRAO,
           permitir_parcial=False, config=None, revalidar=()):
    """O texto que o backend enviaria, tal como a V5 o monta (`v4.lotes` + `v4.pedido`), sem rede e sem gravar.
    A segunda rodada de contexto não existe aqui: nunca é enviada sem autorização."""
    p = preparar(blocks, findings, decisoes, ids, sha_arquivo, sha_relatorio, maximo=maximo, permitir_parcial=permitir_parcial)
    pedidos = []
    rev = [i for i in dict.fromkeys(revalidar) if i in p["decisoes"]]
    if p["decisoes"]:
        plano = v5.planejar(blocks, findings, p["decisoes"], pasta, config=config, revalidar=rev)
        for lote in v4.lotes(plano["a_analisar"], blocks):
            texto, _ = v4.pedido(lote, blocks, {i["id"]: i["antecedentes"] for i in lote if i.get("antecedentes")})
            pedidos.append({"itens": [i["id"] for i in lote], "caracteres": len(texto), "texto": texto})
    return {"integracao": VERSAO_INTEGRACAO, "modelo": v5.MODELO, "esforco": v5.ESFORCO, "pedidos": pedidos,
            "instrucoes_caracteres": len(v5.SISTEMA), "segunda_rodada_autorizada": False, "excluidos": p["excluidos"],
            "observacao": "Texto exato do pedido ao modelo, por requisição. As instruções fixas do Validador (sem o "
                          "manuscrito) acompanham cada pedido."}


def transporte_simulado(arquivo):
    """Transporte que responde a partir de um arquivo local (`{"avaliacoes": {id: entrada}}`); só para testes locais
    ponta a ponta, ativado por variável de ambiente que o aplicativo nunca define. Não toca a rede."""
    prontas = json.loads(Path(arquivo).read_text(encoding="utf-8"))["avaliacoes"]

    def enviar(metodo, caminho, corpo=None):
        if metodo == "GET":
            return 200, {"id": v5.MODELO}, {}
        ids = re.findall(r"\[ITEM (\w+)\]", corpo["input"])
        saida = {"avaliacoes": [prontas[i] for i in ids if i in prontas]}
        uso = {"input_tokens": 1200, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
               "output_tokens": 300, "output_tokens_details": {"reasoning_tokens": 50}}
        corpo_resposta = {"id": "resp_simulada", "model": v5.MODELO, "status": "completed", "usage": uso,
                          "output": [{"type": "reasoning", "id": "rs_1", "summary": []},
                                     {"type": "message", "content": [{"type": "output_text", "text": json.dumps(saida)}]}]}
        return 200, corpo_resposta, {"x-request-id": "req_simulado"}
    return enviar


# --- resultados apresentáveis (leitura; sem rede) ------------------------------------------------------

def significado(decisao, estado, existe, razao):
    """O que a discordância da IA quer dizer, em função da decisão humana. Não presume erro."""
    if estado != "contestada":
        return None
    if decisao in ("Erro confirmado", "Aceito editorialmente") and existe == "nao":
        return "A IA considera que o problema que você reconheceu não existe neste trecho."
    if decisao == "Falso positivo" and existe == "sim":
        return "A IA considera que existe um problema onde você marcou falso positivo."
    if decisao in ("Estilo do autor", "Intencional") and existe == "sim":
        return "A IA vê indício, no texto, de que o desvio não foi deliberado."
    return "A IA discorda da decisão registrada; veja o diagnóstico e as evidências."


def _limitacoes(r, verificacao, pendencia):
    t = r.get("problema_tecnico") or {}
    out = []
    if t.get("existe") == "incerto":
        out.append("O modelo não conseguiu estabelecer se há desvio (existe = incerto).")
    if (r.get("avaliacao") or {}).get("evidencia_suficiente") is False:
        out.append("O modelo declarou que o texto enviado não bastava para concluir.")
    if t.get("existe") == "sim" and t.get("certeza") == "discutivel":
        out.append("Certeza discutível: o modelo admite outra leitura razoável.")
    if not [e for e in r.get("evidencias_verificadas", []) if e.get("situacao") == "ativa"]:
        out.append("Nenhuma evidência verificada foi registrada para este resultado.")
    if verificacao == "contexto_parcial":
        out.append("Versão do manuscrito diferente da do relatório: só o contexto registrado no relatório foi verificado.")
    if pendencia:
        out.append("O modelo pediu mais contexto; a segunda rodada não foi autorizada (pendente).")
    return out


def resultados(blocks, findings, decisoes, pasta, *, ids=None, config=None):
    """Resultados já gravados, no estado atual do relatório e das decisões. Cada item traz, separados: decisão
    humana, existência segundo a IA, adequação da decisão, resultado, evidências e incertezas."""
    itens, aviso = v5.ler(pasta)
    lateral = _ler_lateral(pasta)
    por_id = {f["id"]: f for f in findings}
    alvo = [i for i, r in itens.items() if r.get("estado_validacao") == "analisada" and i in por_id
            and (ids is None or i in set(ids))]
    sub = {i: decisoes[i] for i in alvo if decisoes.get(i) in ELEGIVEIS}
    plano = v5.planejar(blocks, findings, sub, pasta, config=config, ativo=False) if sub else {"itens": {}}
    saida = []
    for i in sorted(alvo, key=lambda x: (por_id[x]["paragraph"], por_id[x]["start"])):
        r, f = itens[i], por_id[i]
        if i not in sub:
            situacao = "decisao_ausente_ou_nao_elegivel"
        else:
            situacao = plano["itens"].get(i, {}).get("situacao", "nao_localizada")
        valido = situacao == "valida"
        ap_ = ap.apresentar(r, f)
        lat = lateral.get(i, {}) if lateral.get(i, {}).get("chave_conteudo") == r.get("chave_conteudo") else {}
        pend = lat.get("pendencia_contexto")
        t = r.get("problema_tecnico") or {}
        saida.append({
            "id": i, "paragrafo": f["paragraph"], "categoria": f["category"], "trecho": ap_["alvo"],
            "situacao": situacao, "vale_para_o_texto_e_decisao_atuais": valido,
            "decisao_humana_anterior": r.get("decisao_humana"), "decisao_humana_atual": decisoes.get(i),
            "existencia_segundo_a_ia": {"existe": t.get("existe"), "natureza": t.get("natureza"), "certeza": t.get("certeza"),
                                        "gravidade": t.get("gravidade"), "rotulo": ap_["problema_tecnico"]["rotulo"]},
            "adequacao_da_decisao_segundo_a_ia": r.get("adequacao_decisao"),
            "resultado": r.get("estado"), "rotulo_do_resultado": ROTULO.get(r.get("estado"), ap_["resultado"]),
            "significado_da_discordancia": significado(r.get("decisao_humana"), r.get("estado"), t.get("existe"), r.get("razao_literaria")),
            "prioridade_da_revisao": r.get("prioridade_revisao"),
            "explicacao_da_ia": ap_["explicacao_do_modelo"],
            "evidencias_verificadas": ap_["evidencias_verificadas"] if isinstance(ap_["evidencias_verificadas"], list) else [],
            "evidencias_descartadas": ap_["evidencias_descartadas"],
            "incertezas_e_limitacoes": _limitacoes(r, lat.get("verificacao"), pend),
            "questao_independente": r.get("questao_independente"),
            "sugestao_da_ia": ap_["sugestao_do_modelo"], "sugestao_aplicada_ao_manuscrito": False,
            "verificacao_da_versao": lat.get("verificacao"), "pendencia_de_contexto": pend,
            "modelo": r.get("modelo_final"), "aviso": AVISO})
    return {"integracao": VERSAO_INTEGRACAO, "aviso_de_leitura": aviso, "itens": saida,
            "contagem": dict(Counter(x["resultado"] for x in saida if x["vale_para_o_texto_e_decisao_atuais"])),
            "desatualizadas": sum(1 for x in saida if not x["vale_para_o_texto_e_decisao_atuais"])}
