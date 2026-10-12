"""Validador de decisões V5.1 (experimental): consistência contextual entre apontamentos relacionados.

Módulo isolado. Não altera V2, V3, V4, V4.1 nem V5 e não lê nem converte os estados persistidos deles; reutiliza,
sem mudar, o cliente da OpenAI, o orçamento, o contrato editorial da V4.1 (derivação do resultado e verificação das
evidências), a recuperação de antecedentes e as chaves de reaproveitamento. Estado e trava próprios
(`validacoes-v5-1.json`).

O que a V5.1 acrescenta, sem nova chamada obrigatória:
  1. relações CONTEXTUAIS entre apontamentos, calculadas em Python a partir de posições e de dados
     estruturados (`mesma_frase`, `mesmo_paragrafo`, `mesma_construcao`). São proximidade, não prova de relação
     semântica nem de dependência;
  2. agrupamento: alertas do mesmo parágrafo ou da mesma frase preferem o mesmo pedido, com limites de itens,
     contexto, saída e orçamento; o que não cabe é dividido de forma documentada, e as referências entre
     ocorrências são preservadas mesmo entre pedidos;
  3. o pedido informa, para cada item, os apontamentos relacionados (só posição; nunca decisão, veredito nem
     hipótese do detector deles) e o contrato ganha `relacoes`, em que o modelo declara dependência ou diferença
     e diz que propriedade a sustenta;
  4. uma camada local que COMPARA resultados já gravados. Ela é derivada na leitura, nunca altera `estado`,
     decisão humana, diagnóstico técnico nem prioridade, e não decide gramática: só afirma o que está em campos
     estruturados, posições e declarações verificáveis.
Reavaliação conjunta de um grupo é operação opcional e futura; não existe aqui.
"""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re

from . import validador_decisoes as vd
from . import validador_v4 as v4
from . import validador_v4_1 as v41
from . import validador_v5 as v5
from .validador_v4 import ValidacaoEmAndamento

VERSAO = "5.1"
VERSAO_RELACOES = 1
MODELO = v5.MODELO
ESFORCO = v5.ESFORCO
ARQUIVO = "validacoes-v5-1.json"
TRAVA = "validacoes-v5-1.lock"
MARCA = "v5_1"
PRECOS = v5.PRECOS
CARACTERES_POR_TOKEN = v5.CARACTERES_POR_TOKEN

# Limites efetivos do agrupamento (por pedido).
LOTE_MAX_ITENS = 6
LOTE_MAX_CARACTERES = v4.LOTE[1]          # contexto único, sem repetir parágrafos
RELACIONADOS_MAX = 8                      # relacionados informados por item; o excedente é omitido e contado
TRECHO_RELACIONADO = 60
CARACTERES_POR_ITEM = 700                 # estimativa do cabeçalho de cada item (hipótese, decisão, alvo)
CARACTERES_POR_RELACIONADO = 130
RELACAO_TOKENS = 70                       # saída visível esperada por relacionado declarado

TIPOS_CONTEXTUAIS = ("mesma_frase", "mesmo_paragrafo", "mesma_construcao")
NO_PEDIDO = ("mesma_frase", "mesmo_paragrafo")   # mesma_construcao entre parágrafos fica só na camada local
TIPOS_DECLARADOS = ("independente", "depende_de", "mesma_questao", "diferenca", "incerta")
EXIGEM_MOTIVO = ("depende_de", "mesma_questao", "diferenca")
EXIGEM_PROPRIEDADE = ("mesma_questao", "diferenca")
ESTADOS_CONSISTENCIA = ("classificacoes_alinhadas", "diferenca_nao_articulada", "diferenca_declarada",
                        "contradicao_declarada", "comparacao_indisponivel")
ESTADOS_DEPENDENCIA = ("dependencia_declarada", "dependencia_condicional", "dependencia_nao_analisada",
                       "dependencia_circular")
CAMPOS_COMPARADOS = ("existe", "natureza", "certeza")

# Uma palavra à esquerda do alvo que não serve de gatilho de construção (artigos e pronomes pessoais).
_NAO_GATILHO = frozenset("""o a os as um uma uns umas ele ela eles elas eu tu nós vós você vocês me te se lhe lhes
seu sua seus suas meu minha meus minhas nosso nossa""".split())
_FIM_DE_FRASE = re.compile(r'[.!?…]+["”»)\]]*\s+|\n')

# --- contrato: prompt e esquema ------------------------------------------------------------------------

_LINHA_ANTIGA = "Cada item é independente."
_BLOCO_RELACOES = """Relações entre apontamentos: alguns itens trazem, ao final do pedido, outros apontamentos \
do mesmo parágrafo ou da mesma frase. O Lume informa só a posição deles; não informa a decisão do revisor, o \
veredito nem a hipótese do detector. A relação é de proximidade no texto, não de significado. Julgue cada item por si, \
com o contexto enviado: semelhança entre itens NÃO obriga o mesmo resultado, e você não deve harmonizar \
resultados por conveniência. No campo `relacoes`, responda uma entrada para cada apontamento relacionado do \
item, com o id dado em `com`:
- "independente": seu julgamento não depende dele.
- "depende_de": sua conclusão pressupõe como aquele outro apontamento é lido; diga em `motivo` a que da \
leitura dele a sua se liga.
- "mesma_questao": os dois tratam do mesmo fenômeno e o mesmo critério vale para ambos; diga em `propriedade` qual.
- "diferenca": são casos distintos e merecem tratamento diferente; diga em `propriedade` a característica \
linguística ou contextual concreta que os distingue (por exemplo, a função da forma, o tipo de discurso ou o \
momento da cena) e em `motivo` por que ela importa aqui.
- "incerta": o contexto enviado não permite dizer.
Use `trecho` (cópia exata e curta do texto enviado) quando uma citação sustentar a relação; senão, "". \
`propriedade` e `motivo` podem ficar vazios só em "independente" e "incerta". Item sem relacionados: \
`relacoes` = [].

"""
_ANCORA = "Significado das decisões:\n"
assert v41.SISTEMA.count(_LINHA_ANTIGA) == 1 and v41.SISTEMA.count(_ANCORA) == 1
SISTEMA = v41.SISTEMA.replace(_LINHA_ANTIGA, "Cada item é julgado por si.").replace(_ANCORA, _BLOCO_RELACOES + _ANCORA)


def _esquema_com_relacoes():
    esquema = json.loads(json.dumps(v41.ESQUEMA))
    item = esquema["properties"]["avaliacoes"]["items"]
    item["properties"]["relacoes"] = {"type": "array", "items": {
        "type": "object", "properties": {
            "com": {"type": "string"}, "tipo": {"type": "string", "enum": list(TIPOS_DECLARADOS)},
            "propriedade": {"type": "string"}, "motivo": {"type": "string"}, "trecho": {"type": "string"}},
        "required": ["com", "tipo", "propriedade", "motivo", "trecho"]}}
    item["required"] = [*item["required"], "relacoes"]
    return esquema


ESQUEMA = v5.esquema_estrito(_esquema_com_relacoes())


def configuracao(modelo=MODELO, esforco=ESFORCO):
    """Parte da chave de reaproveitamento. O tamanho do lote não entra: não muda o contexto de nenhum item."""
    base = v5.configuracao(modelo, esforco)
    return {**base, "versao": VERSAO, "relacoes": VERSAO_RELACOES,
            "contrato_editorial": base["contrato_editorial"] + "+relacoes",
            "prompt_sha256": v4._hash_texto(SISTEMA)[:16],
            "esquema_sha256": v4._hash_texto(json.dumps(ESQUEMA, sort_keys=True))[:16],
            "relacionados_max": RELACIONADOS_MAX}


# --- relações contextuais (determinísticas) -------------------------------------------------------------

def _ordem(item):
    return (item["_bloco"].number, item["start"], item["id"])


def _frase(item):
    texto = item["_bloco"].text
    return sum(1 for m in _FIM_DE_FRASE.finditer(texto) if m.end() <= item["start"])


def _gatilho(item):
    """Duas palavras que precedem o alvo, se a última não for artigo ou pronome pessoal; senão ()."""
    palavras = re.findall(r"\w+", item["_bloco"].text[:item["start"]].lower())[-2:]
    return tuple(palavras) if len(palavras) == 2 and palavras[-1] not in _NAO_GATILHO else ()


def relacoes_contextuais(itens):
    """Arestas entre apontamentos (cada um com `a`, `b`, `tipo`, `criterio`, `heuristica`), em ordem
    determinística. Proximidade e forma, nunca prova de relação semântica:
      mesma_frase     — mesmo parágrafo, sem pontuação final entre os alvos (heurística de segmentação);
      mesmo_paragrafo — mesmo parágrafo;
      mesma_construcao — parágrafos diferentes do mesmo capítulo, mesma categoria e regra, e as mesmas duas
                         palavras à esquerda do alvo (conservadora: tem recall baixo de propósito)."""
    ordenados = sorted(itens, key=_ordem)
    arestas = []
    for k, a in enumerate(ordenados):
        for b in ordenados[k + 1:]:
            na, nb = a["_bloco"].number, b["_bloco"].number
            if na == nb:
                if _frase(a) == _frase(b):
                    arestas.append({"a": a["id"], "b": b["id"], "tipo": "mesma_frase", "heuristica": True,
                                    "criterio": "mesmo parágrafo sem pontuação final entre os alvos"})
                else:
                    arestas.append({"a": a["id"], "b": b["id"], "tipo": "mesmo_paragrafo", "heuristica": False,
                                    "criterio": "mesmo parágrafo"})
            elif a["_bloco"].chapter == b["_bloco"].chapter and a.get("category") == b.get("category") \
                    and a.get("rule") == b.get("rule") and _gatilho(a) and _gatilho(a) == _gatilho(b):
                arestas.append({"a": a["id"], "b": b["id"], "tipo": "mesma_construcao", "heuristica": True,
                                "criterio": "mesma categoria e regra, mesmas duas palavras à esquerda do alvo"})
    return arestas


def _relacionados(item, por_id, arestas):
    """Relacionados que o pedido informa para `item`: mesma frase antes de mesmo parágrafo, os mais próximos
    primeiro, até RELACIONADOS_MAX. Devolve (lista, omitidos)."""
    candidatos = []
    for e in arestas:
        if e["tipo"] not in NO_PEDIDO or item["id"] not in (e["a"], e["b"]):
            continue
        outro = por_id[e["b"] if e["a"] == item["id"] else e["a"]]
        candidatos.append((e["tipo"] != "mesma_frase", abs(outro["start"] - item["start"]), _ordem(outro), e["tipo"], outro))
    candidatos.sort(key=lambda c: c[:3])
    lista = []
    for _, _, _, tipo, outro in candidatos[:RELACIONADOS_MAX]:
        ordem, total = vd.ocorrencia(outro["_bloco"].text, outro["start"], outro["end"])
        lista.append({"id": outro["id"], "tipo": tipo, "paragrafo": outro["_bloco"].number,
                      "inicio": outro["start"], "fim": outro["end"], "ocorrencia": ordem, "total": total,
                      "alvo": v4._sem_sinais(outro["_bloco"].text[outro["start"]:outro["end"]])[:TRECHO_RELACIONADO]
                      .replace("\n", " ")})
    return lista, max(0, len(candidatos) - RELACIONADOS_MAX)


def _chave_relacoes(lista):
    return vd._hash("relacoes", VERSAO_RELACOES,
                    [(r["id"], r["tipo"], r["paragrafo"], r["inicio"], r["fim"]) for r in lista])


# --- agrupamento seguro ---------------------------------------------------------------------------------

def _contexto_caracteres(lote, blocos):
    vistos = {}
    for i in lote:
        for b in [*v4._janela_item(blocos, i), i["_bloco"]]:
            vistos[b.number] = len(b.text)
    return sum(vistos.values())


def _pior_pedido(lote, blocos, preco=None):
    """Pior caso (US$) de um pedido, pelas mesmas premissas da estimativa: entrada à escrita de cache e o
    limite de saída inteiro à tarifa de saída. É conferência de planejamento; o cliente confere de novo."""
    preco = preco or PRECOS[MODELO]
    relacionados = sum(len(i.get("relacionados") or ()) for i in lote)
    corpo = (_contexto_caracteres(lote, blocos) + CARACTERES_POR_ITEM * len(lote)
             + CARACTERES_POR_RELACIONADO * relacionados) / CARACTERES_POR_TOKEN
    fixo = (len(SISTEMA) + len(json.dumps(ESQUEMA))) / CARACTERES_POR_TOKEN
    return ((fixo + corpo) * preco["escrita_cache"] + v5.limite_de_saida(len(lote)) * preco["saida"]) / 1e6


def _componentes(itens, arestas, tipos):
    """Componentes conexos (listas ordenadas) pelas arestas dos `tipos`, só entre os itens dados."""
    pai = {i["id"]: i["id"] for i in itens}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x
    for e in arestas:
        if e["tipo"] in tipos and e["a"] in pai and e["b"] in pai:
            pai[raiz(e["a"])] = raiz(e["b"])
    grupos = {}
    for i in sorted(itens, key=_ordem):
        grupos.setdefault(raiz(i["id"]), []).append(i)
    return sorted(grupos.values(), key=lambda g: _ordem(g[0]))


def agrupar(itens, blocos, arestas, *, maximo_itens=LOTE_MAX_ITENS, maximo_caracteres=LOTE_MAX_CARACTERES,
            limite_pedido_usd=None):
    """(lotes, divisoes). Alertas do mesmo parágrafo ou da mesma frase formam uma unidade que prefere um único
    pedido; unidades com a mesma construção ficam adjacentes quando cabem. Uma unidade que não cabe nos limites
    (itens, contexto, pior caso financeiro) é dividida, preferindo fronteiras de frase, e a divisão é registrada.
    Nenhum limite é relaxado para manter uma unidade inteira."""
    def cabe(lote):
        return (len(lote) <= maximo_itens and _contexto_caracteres(lote, blocos) <= maximo_caracteres
                and (limite_pedido_usd is None or _pior_pedido(lote, blocos) <= limite_pedido_usd))
    divisoes = []

    def quebrar(unidade):
        if cabe(unidade):
            return [unidade]
        pedacos = _componentes(unidade, arestas, ("mesma_frase",))
        if len(pedacos) == 1:
            pedacos = [[i] for i in unidade]
        partes, atual = [], []
        for p in pedacos:
            if atual and not cabe(atual + p):
                partes.append(atual)
                atual = []
            atual = atual + p
            while len(atual) > 1 and not cabe(atual):             # um pedaço sozinho já não cabe: parte-se por item
                partes.append(atual[:1])
                atual = atual[1:]
        partes.append(atual)
        motivo = ("excede_itens" if len(unidade) > maximo_itens
                  else "excede_contexto" if _contexto_caracteres(unidade, blocos) > maximo_caracteres
                  else "excede_orcamento")
        divisoes.append({"motivo": motivo, "itens": [i["id"] for i in unidade], "partes": [[i["id"] for i in p] for p in partes],
                         "referencias_preservadas": True})
        return partes

    por_id = {i["id"]: i for i in itens}
    unidades = _componentes(itens, arestas, NO_PEDIDO)
    onde = {i["id"]: k for k, u in enumerate(unidades) for i in u}
    afins = {}
    for e in arestas:
        if e["tipo"] == "mesma_construcao" and e["a"] in onde and e["b"] in onde and onde[e["a"]] != onde[e["b"]]:
            afins.setdefault(onde[e["a"]], set()).add(onde[e["b"]])
            afins.setdefault(onde[e["b"]], set()).add(onde[e["a"]])
    fila, colocadas = [], set()
    for k in range(len(unidades)):
        for j in [k, *sorted(afins.get(k, ()))]:
            if j not in colocadas and (j == k or por_id[unidades[j][0]["id"]]["_bloco"].chapter
                                       == unidades[k][0]["_bloco"].chapter):
                colocadas.add(j)
                fila.append(unidades[j])
    lotes, atual = [], []
    for unidade in fila:
        for parte in quebrar(unidade):
            muda = atual and atual[0]["_bloco"].chapter != parte[0]["_bloco"].chapter
            if atual and (muda or not cabe(atual + parte)):
                lotes.append(atual)
                atual = []
            atual = atual + parte
    return lotes + ([atual] if atual else []), divisoes


def _dividir(lote):
    """Duas partes de um lote: na fronteira de parágrafo mais próxima do meio; senão, na de frase; senão, no meio."""
    meio = len(lote) / 2
    for chave in (lambda a, b: a["_bloco"].number != b["_bloco"].number, lambda a, b: _frase(a) != _frase(b)):
        cortes = [k for k in range(1, len(lote)) if chave(lote[k - 1], lote[k])]
        if cortes:
            k = min(cortes, key=lambda c: abs(c - meio))
            return lote[:k], lote[k:]
    return lote[:len(lote) // 2], lote[len(lote) // 2:]


# --- pedido ----------------------------------------------------------------------------------------------

def pedido(lote, blocos, extras_por_id=None, segunda_rodada=False):
    """O pedido da V4 (mesmo contexto compartilhado e marcação do alvo) e, ao final, os relacionados de cada
    item. Devolve (texto, autorizado por item): `autorizado` é só o que o item recebeu; os parágrafos dos
    relacionados em outros pedidos não são evidência autorizada."""
    texto, autorizado = v4.pedido(lote, blocos, extras_por_id, segunda_rodada)
    partes = []
    for item in lote:
        relacionados = item.get("relacionados") or []
        if not relacionados:
            continue
        partes.append(f"[RELACOES ITEM {item['id']}]")
        for r in relacionados:
            tipo = "mesma frase" if r["tipo"] == "mesma_frase" else "mesmo parágrafo"
            partes.append(f"- com={r['id']} «{r['alvo']}» §{r['paragrafo']} posições {r['inicio']}–{r['fim']}, "
                          f"ocorrência {r['ocorrencia']} de {r['total']}, {tipo}")
        if item.get("relacionados_omitidos"):
            partes.append(f"({item['relacionados_omitidos']} relacionado(s) a mais não listado(s))")
    if partes:
        texto += ("\nApontamentos relacionados (informados pelo Lume; relação de posição, não de significado; sem "
                  "decisão, veredito nem hipótese do detector):\n" + "\n".join(partes))
    return texto, autorizado


# --- declarações do modelo: verificação determinística ---------------------------------------------------

def conferir_relacoes(item, bruto, autorizado, descartes):
    """(declaradas, nao_declaradas). Só o que se verifica por estrutura: o id precisa ser um relacionado
    fornecido àquele item, sem duplicata contraditória; `propriedade` e `motivo` são exigidos conforme o tipo; um
    `trecho` precisa existir no contexto autorizado do item. A verdade da explicação não é verificada aqui."""
    fornecidos = {r["id"] for r in item.get("relacionados") or []}
    if not isinstance(bruto, list):
        descartes["relacoes_invalidas"] += 1
        bruto = []
    vistas, contraditorias = {}, set()
    for e in bruto:
        if not isinstance(e, dict) or not all(isinstance(e.get(k), str) for k in ("com", "tipo", "propriedade",
                                                                                    "motivo", "trecho")):
            descartes["relacao_malformada"] += 1
            continue
        if e["com"] == item["id"]:
            descartes["relacao_consigo_mesmo"] += 1
        elif e["com"] not in fornecidos:
            descartes["relacao_desconhecida"] += 1
        elif e["tipo"] not in TIPOS_DECLARADOS:
            descartes["relacao_tipo_invalido"] += 1
        elif e["com"] in vistas and vistas[e["com"]]["tipo"] != e["tipo"]:
            contraditorias.add(e["com"])
            descartes["relacao_duplicada_contraditoria"] += 1
        elif e["com"] not in vistas:
            vistas[e["com"]] = e
    declaradas = []
    for ident, e in vistas.items():
        if ident in contraditorias:
            continue
        propriedade, motivo = e["propriedade"].strip(), e["motivo"].strip()
        problemas = []
        if e["tipo"] in EXIGEM_MOTIVO and not motivo:
            problemas.append("motivo_ausente")
        elif e["tipo"] in EXIGEM_MOTIVO and (len(motivo.split()) < 4 or motivo.lower() == propriedade.lower()):
            problemas.append("motivo_pouco_informativo")
        if e["tipo"] in EXIGEM_PROPRIEDADE and not propriedade:
            problemas.append("propriedade_ausente")
        trecho, autentico = v4._sem_sinais(e["trecho"]).strip(), None
        if trecho:
            autentico = bool(v4.localizar_evidencia(trecho, autorizado))
            if not autentico:
                descartes["relacao_trecho_inexistente"] += 1
                trecho = ""
        declaradas.append({"com": ident, "tipo": e["tipo"], "propriedade": propriedade, "motivo": motivo,
                           "trecho": trecho[:200], "trecho_autentico": autentico, "completa": not problemas,
                           "problemas": problemas})
    dados = {d["com"] for d in declaradas}
    return declaradas, sorted(fornecidos - dados)


# --- camada local de consistência (derivada, nunca persistida como fato) -----------------------------------

def _campos(registro):
    t = registro.get("problema_tecnico") or {}
    return tuple(t.get(k) for k in CAMPOS_COMPARADOS)


def _declaracao(registros, de, para):
    return next((d for d in (registros.get(de) or {}).get("relacoes", []) if d["com"] == para), None)


def validos(avaliar, registros, ativo=False):
    """Registros analisados cuja chave ainda vale para o item atual."""
    return {i["id"]: registros[i["id"]] for i in avaliar
            if registros.get(i["id"]) and registros[i["id"]].get("estado_validacao") == "analisada"
            and v4.situacao(registros[i["id"]], i, ativo) == "valida"}


def _ciclos(declaradas):
    """Conjunto de ids em ciclo do grafo `depende_de` (componentes fortemente conexos com mais de um nó)."""
    grafo = {}
    for de, para in declaradas:
        grafo.setdefault(de, set()).add(para)
        grafo.setdefault(para, set())
    indice, baixo, pilha, na_pilha, saida, n = {}, {}, [], set(), set(), [0]

    def visitar(v):
        indice[v] = baixo[v] = n[0]
        n[0] += 1
        pilha.append(v)
        na_pilha.add(v)
        for w in grafo[v]:
            if w not in indice:
                visitar(w)
                baixo[v] = min(baixo[v], baixo[w])
            elif w in na_pilha:
                baixo[v] = min(baixo[v], indice[w])
        if baixo[v] == indice[v]:
            comp = []
            while True:
                w = pilha.pop()
                na_pilha.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                saida.update(comp)
    for v in list(grafo):
        if v not in indice:
            visitar(v)
    return saida


def consistencia(avaliar, registros, arestas, ativo=False):
    """Relatório derivado dos vereditos válidos e das declarações. Nunca altera registro, `estado`, decisão
    humana, diagnóstico técnico nem prioridade; só descreve. `atencao` marca o que merece olhar humano; o resto é
    informação neutra e não deve virar aviso editorial."""
    por_id = {i["id"]: i for i in avaliar}
    ok = validos(avaliar, registros, ativo)
    pares = []
    for e in arestas:
        if e["a"] not in por_id or e["b"] not in por_id:
            continue
        a, b = e["a"], e["b"]
        linha = {"a": a, "b": b, "relacao": e["tipo"], "heuristica": e["heuristica"], "criterio": e["criterio"],
                 "campos_comparados": list(CAMPOS_COMPARADOS), "atencao": False}
        if a not in ok or b not in ok:
            linha.update(estado="comparacao_indisponivel", detalhe="um dos apontamentos não tem veredito válido")
            pares.append(linha)
            continue
        da, db = _declaracao(ok, a, b), _declaracao(ok, b, a)
        ca, cb = _campos(ok[a]), _campos(ok[b])
        tipos = {d["tipo"] for d in (da, db) if d}
        diferem = ca != cb
        if ("mesma_questao" in tipos and "diferenca" in tipos) or \
                ("mesma_questao" in tipos and {ca[0], cb[0]} == {"sim", "nao"}):
            linha.update(estado="contradicao_declarada", atencao=True,
                         detalhe="declarações explicitamente incompatíveis entre si ou com os campos estruturados")
        elif "diferenca" in tipos and any(d and d["tipo"] == "diferenca" and d["completa"] for d in (da, db)):
            completas = [d for d in (da, db) if d and d["tipo"] == "diferenca" and d["completa"]]
            linha.update(estado="diferenca_declarada",
                         verificacao="formal_com_trecho_autentico" if any(d["trecho_autentico"] for d in completas)
                         else "formal",
                         detalhe="o modelo declarou a diferença e a propriedade; a procedência da explicação "
                                 "não foi comprovada")
        elif not diferem:
            linha.update(estado="classificacoes_alinhadas",
                         detalhe="campos comparados equivalentes; não confirma correção linguística")
        else:
            grau = "existe" if ca[0] != cb[0] else "classificacao"
            linha.update(estado="diferenca_nao_articulada", grau=grau, atencao=grau == "existe",
                         detalhe="campos diferem sem diferença declarada e completa"
                                 + ("; declaração incompleta" if "diferenca" in tipos else ""))
        pares.append(linha)
    declaradas = {(i, d["com"]) for i, r in ok.items() for d in r.get("relacoes", []) if d["tipo"] == "depende_de"}
    ciclo = _ciclos(declaradas)
    dependencias = []
    for de, para in sorted(declaradas):
        if de in ciclo and para in ciclo:
            estado, detalhe = "dependencia_circular", "A depende de B e B, direta ou indiretamente, de A"
        elif para not in por_id:
            estado, detalhe = "dependencia_nao_analisada", "o apontamento do qual depende não está mais no relatório"
        elif para not in ok:
            estado, detalhe = "dependencia_nao_analisada", "o apontamento do qual depende não tem veredito válido"
        elif ok[para].get("estado") == "inconclusiva":
            estado, detalhe = "dependencia_condicional", "o veredito do qual depende é inconclusivo"
        else:
            estado, detalhe = "dependencia_declarada", "referência declarada e existente; conteúdo não verificado"
        dependencias.append({"de": de, "para": para, "estado": estado, "detalhe": detalhe,
                             "atencao": estado in ("dependencia_circular", "dependencia_nao_analisada")})
    resumo = Counter(p["estado"] for p in pares) + Counter(d["estado"] for d in dependencias)
    return {"pares": pares, "dependencias": dependencias, "resumo": dict(resumo),
            "atencao": [p for p in pares + dependencias if p["atencao"]]}


# --- persistência e trava (adaptadores mínimos; V5 intacto) -----------------------------------------------

def ler(pasta):
    caminho = Path(pasta) / ARQUIVO
    if not caminho.exists():
        return {}, None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if dados.get(MARCA) != 1:
            raise ValueError
        return dict(dados["itens"]), None
    except (OSError, ValueError, KeyError, TypeError):
        return {}, f"Validador V5.1: {ARQUIVO} não pôde ser lido; tudo foi tratado como não analisado."


def gravar(pasta, itens, meta=None):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = pasta / (ARQUIVO + ".tmp")
    temporario.write_text(json.dumps({"versao": 1, MARCA: 1, "meta": meta or {}, "itens": itens},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    temporario.replace(pasta / ARQUIVO)


@contextmanager
def trava(pasta):
    """Trava exclusiva por projeto (flock, não bloqueante). Outro processo na mesma pasta recebe
    ValidacaoEmAndamento; a trava cai com o processo, então uma execução morta nunca prende o projeto."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = open(pasta / TRAVA, "a+")
    try:
        try:
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as erro:
            raise ValidacaoEmAndamento("Já existe uma validação em andamento neste projeto.") from erro
        arquivo.seek(0)
        arquivo.truncate()
        arquivo.write(f"{os.getpid()}\n")
        arquivo.flush()
        yield
    finally:
        try:
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        finally:
            arquivo.close()


def ocupada(pasta):
    caminho = Path(pasta) / TRAVA
    if not caminho.exists():
        return False
    with open(caminho, "a+") as arquivo:
        try:
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        return False


# --- preparo, plano e estimativa ----------------------------------------------------------------------------

def preparar(blocks, findings, decisoes, guardados=None, modelo=MODELO, esforco=ESFORCO, config=None):
    """Itens da V5 (mesma localização, antecedentes e contexto) com os relacionados e as chaves da V5.1."""
    avaliar, perdidos, fora = v5.preparar(blocks, findings, decisoes, guardados, modelo, esforco, config)
    arestas = relacoes_contextuais(avaliar)
    por_id = {i["id"]: i for i in avaliar}
    cfg = vd._hash(configuracao(modelo, esforco))
    for item in avaliar:
        item["relacionados"], item["relacionados_omitidos"] = _relacionados(item, por_id, arestas)
        item["chave_relacoes"] = _chave_relacoes(item["relacionados"])
        item["chave_conteudo"] = vd._hash("v5.1", item["chave_conteudo"], item["chave_relacoes"])
        item["chave_configuracao"] = cfg
    return avaliar, perdidos, fora


def planejar(blocks, findings, decisoes, pasta=None, *, modelo=MODELO, esforco=ESFORCO, revalidar=(), config=None,
             ativo=None):
    guardados, aviso = ler(pasta) if pasta else ({}, None)
    avaliar, perdidos, fora = preparar(blocks, findings, decisoes, guardados, modelo, esforco, config)
    if ativo is None:
        ativo = ocupada(pasta) if pasta else False
    plano, contagem = {}, Counter()
    for item in avaliar:
        registro = guardados.get(item["id"])
        s = v4.situacao(registro, item, ativo)
        plano[item["id"]] = {"situacao": s, "estado_ui": v4.estado_ui(registro, item, ativo),
                             "analisar": s == "nova" or (s.startswith("desatualizada") and item["id"] in set(revalidar))}
        contagem[s] += 1
    return {"itens": plano, "a_analisar": [i for i in avaliar if plano[i["id"]]["analisar"]],
            "reutilizadas": contagem["valida"],
            "desatualizadas": sum(v for k, v in contagem.items() if k.startswith("desatualizada")),
            "em_processamento": contagem["em_processamento"], "nao_localizadas": len(perdidos), "fora": fora,
            "situacoes": dict(contagem), "elegiveis": len(avaliar) + len(perdidos), "aviso": aviso,
            "avaliar": avaliar, "arestas": relacoes_contextuais(avaliar)}


def _custos(lotes, blocos, texto_do_lote, sistema, esquema, com_relacoes, modelo=MODELO):
    """Tokens e custos estimados por componente (entrada, cache, saída visível, raciocínio por cenário) e o
    pior caso por pedido. Estimativa por caracteres: o tokenizador da OpenAI difere."""
    preco = PRECOS[modelo]
    fixo = (len(sistema) + len(json.dumps(esquema))) / CARACTERES_POR_TOKEN
    entrada_tokens = visivel = 0.0
    entrada_usd = cache_usd = 0.0
    piores = []
    for k, lote in enumerate(lotes):
        corpo = len(texto_do_lote(lote)) / CARACTERES_POR_TOKEN
        entrada_tokens += fixo + corpo
        entrada_usd += corpo * preco["entrada"] / 1e6
        cache_usd += fixo * (preco["escrita_cache"] if k == 0 else preco["cache"]) / 1e6
        extra = RELACAO_TOKENS * sum(len(i.get("relacionados") or ()) for i in lote) if com_relacoes else 0
        visivel += v5.SAIDA_VISIVEL_ESPERADA[0] + v5.SAIDA_VISIVEL_ESPERADA[1] * len(lote) + extra
        piores.append(((fixo + corpo) * preco["escrita_cache"] + v5.limite_de_saida(len(lote)) * preco["saida"]) / 1e6)
    n = sum(len(l) for l in lotes)
    limites = sum(v5.limite_de_saida(len(l)) for l in lotes)
    saida = lambda r: min(visivel + r * n, limites)          # o limite de saída trunca qualquer cenário acima dele
    base = entrada_usd + cache_usd
    return {"pedidos": len(lotes), "itens": n, "itens_por_pedido": [len(l) for l in lotes],
            "cenarios_limitados_pelo_limite_de_saida": [r for r in v5.RACIOCINIO_CENARIOS if visivel + r * n > limites],
            "tokens_entrada_estimados": int(entrada_tokens), "tokens_saida_visivel_esperados": int(visivel),
            "custo_por_componente_usd": {"entrada_nao_cacheada": round(entrada_usd, 5),
                                         "cache_prompt_fixo": round(cache_usd, 5),
                                         "saida_visivel": round(visivel * preco["saida"] / 1e6, 5)},
            "raciocinio_usd_por_cenario": {str(r): round((saida(r) - visivel) * preco["saida"] / 1e6, 5)
                                           for r in v5.RACIOCINIO_CENARIOS},
            "custo_total_usd_por_cenario": {str(r): round(base + saida(r) * preco["saida"] / 1e6, 4)
                                            for r in v5.RACIOCINIO_CENARIOS},
            "pior_caso_por_pedido_usd": [round(x, 4) for x in piores],
            "custo_maximo_primeira_rodada_usd": round(sum(piores), 4),
            "pior_pedido_usd": round(max(piores, default=0.0), 4)}


def estimar(blocks, findings, decisoes, pasta=None, *, modelo=MODELO, esforco=ESFORCO, revalidar=(), config=None,
            teto=None):
    """Sem rede. Custos por componente e cenários de raciocínio (nunca medido neste conjunto); o pior caso é o
    limite de saída inteiro. O que a V5.1 acrescenta à V5 é estimativa, não garantia."""
    p = planejar(blocks, findings, decisoes, pasta, modelo=modelo, esforco=esforco, revalidar=revalidar, config=config)
    lotes, divisoes = agrupar(p["a_analisar"], blocks, p["arestas"], limite_pedido_usd=teto)
    extras = lambda lote: {i["id"]: i["antecedentes"] for i in lote if i.get("antecedentes")}
    c = _custos(lotes, blocks, lambda l: pedido(l, blocks, extras(l))[0], SISTEMA, ESQUEMA, True, modelo)
    saida = {"versao": VERSAO, "provedor": "openai", "modelo": modelo, "esforco": esforco, "elegiveis": p["elegiveis"],
             "a_analisar": len(p["a_analisar"]), "reutilizadas_sem_custo": p["reutilizadas"],
             "nao_localizadas": p["nao_localizadas"], "chamadas_primeira_rodada": c["pedidos"],
             "chamadas_segunda_rodada_maximo": c["pedidos"], "divisoes": divisoes,
             "limite_de_saida_por_pedido": [v5.limite_de_saida(n) for n in c["itens_por_pedido"]],
             "teto_minimo_usd": round(c["pior_pedido_usd"] + 0.005, 2),
             "custo_maximo_com_segunda_rodada_usd": round(2 * c["custo_maximo_primeira_rodada_usd"], 4),
             "precos_usd_por_milhao": PRECOS[modelo], **c,
             "premissas": ["entrada estimada por caracteres (o tokenizador da OpenAI difere)",
                           "raciocínio por item não medido: ver cenários",
                           f"cada relacionado informado soma ~{RELACAO_TOKENS} tokens de saída visível esperados"]}
    if teto is not None:
        saida["teto_usd"] = teto
        saida["cabe_no_teto"] = saida["teto_minimo_usd"] <= teto
    return saida


def comparar_com_v5(blocks, findings, decisoes, *, modelo=MODELO):
    """Comparação local, sem rede e sem estado, entre o agrupamento da V5 (v4.lotes) e o da V5.1 sobre os mesmos
    itens elegíveis: composição dos pedidos por (parágrafo, início) e custos estimados por componente."""
    avaliar, _, _ = preparar(blocks, findings, decisoes, None, modelo)
    arestas = relacoes_contextuais(avaliar)
    extras = lambda lote: {i["id"]: i["antecedentes"] for i in lote if i.get("antecedentes")}
    v5_lotes = v4.lotes(avaliar, blocks)
    v51_lotes, divisoes = agrupar(avaliar, blocks, arestas)
    nome = lambda i: f"§{i['_bloco'].number}:{i['start']}"
    paragrafos = Counter(i["_bloco"].number for i in avaliar)
    multi = {n for n, c in paragrafos.items() if c > 1}
    partidos = lambda lotes: sorted(n for n in multi
                                    if len({k for k, l in enumerate(lotes) for i in l if i["_bloco"].number == n}) > 1)
    return {"itens": len(avaliar), "paragrafos_com_varios_alertas": len(multi),
            "arestas": dict(Counter(e["tipo"] for e in arestas)),
            "v5": {"composicao": [[nome(i) for i in l] for l in v5_lotes], "paragrafos_divididos": partidos(v5_lotes),
                   **_custos(v5_lotes, blocks, lambda l: v4.pedido(l, blocks, extras(l))[0], v5.SISTEMA, v5.ESQUEMA,
                             False, modelo)},
            "v5_1": {"composicao": [[nome(i) for i in l] for l in v51_lotes], "paragrafos_divididos": partidos(v51_lotes),
                     "divisoes": divisoes,
                     **_custos(v51_lotes, blocks, lambda l: pedido(l, blocks, extras(l))[0], SISTEMA, ESQUEMA, True,
                               modelo)}}


# --- execução --------------------------------------------------------------------------------------------

def avaliar(blocks, findings, decisoes, *, pasta, teto, modelo=MODELO, esforco=ESFORCO, revalidar=(), cliente=None,
            transporte=None, avancar=None, meta=None, config=None, rodada_extra=True, apenas=None):
    """Executa a V5.1. Só analisa o que é novo ou foi pedido para revalidar; o resto é reutilizado sem chamada.
    Nenhuma chamada é obrigatória além das da V5 (uma por pedido, e a segunda rodada de contexto só quando o
    modelo pede)."""
    ErroModelo, Recusa, RespostaCortada, TetoAtingido = v5._erros()
    from coerencia.modelo import Orcamento
    with trava(pasta):
        p = planejar(blocks, findings, decisoes, pasta, modelo=modelo, esforco=esforco, revalidar=revalidar,
                     config=config, ativo=False)
        guardados, aviso = ler(pasta)
        por_id = {i["id"]: i for i in p["avaliar"]}
        registros, avisos = dict(guardados), [aviso] if aviso else []
        descartes, falhas, log, divisoes_exec = Counter(), Counter(), [], []
        estado = {"interrompida": False, "motivo": "", "teto": False}
        meta = dict(meta or {}, configuracao=configuracao(modelo, esforco), pedidos=log, divisoes=divisoes_exec)
        a_analisar = p["a_analisar"]
        if apenas is not None:                       # recorte do experimento: os demais ficam só como relacionados
            a_analisar = [i for i in a_analisar if i["id"] in set(apenas)]
        antigo = {i["id"]: guardados[i["id"]] for i in a_analisar
                  if i["id"] in guardados and guardados[i["id"]].get("estado_validacao") != "em_processamento"}
        for i in a_analisar:
            if registros.get(i["id"], {}).get("estado_validacao") == "em_processamento":
                registros.pop(i["id"])
        agora = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

        def salvar():
            gravar(pasta, registros, meta)

        def conectar():
            if cliente is not None:
                return cliente
            novo = v5.OpenAI(modelo, esforco, orcamento=Orcamento(teto), transporte=transporte)
            novo.verificar()
            return novo
        c = conectar() if a_analisar else None

        def devolver(lote):
            for i in lote:
                if registros.get(i["id"], {}).get("estado_validacao") == "em_processamento":
                    if i["id"] in antigo:
                        registros[i["id"]] = antigo[i["id"]]
                    else:
                        registros.pop(i["id"], None)
            salvar()

        def custo_do_item(ident):
            return round(sum(x["custo_usd"] / max(len(x["itens"]), 1) for x in log if ident in x["itens"]), 6)

        def gasto():
            orc = getattr(c, "orcamento", None)
            return orc.gasto if orc is not None else sum(x.get("custo_usd", 0) for x in log)

        def pior_caso(texto, n):
            if hasattr(c, "custo_maximo"):
                return c.custo_maximo(SISTEMA, texto, ESQUEMA, v5.limite_de_saida(n))
            preco = PRECOS[modelo]
            return ((len(SISTEMA) + len(texto) + len(json.dumps(ESQUEMA))) / CARACTERES_POR_TOKEN
                    * preco["escrita_cache"] + v5.limite_de_saida(n) * preco["saida"]) / 1e6

        def chamar(lote, extras, segunda, texto, autorizado):
            antes = len(getattr(c, "chamadas", []))
            etapa = f"v5.1-r{2 if segunda else 1} §{lote[0]['_bloco'].number}"
            try:
                resposta = c.json(SISTEMA, texto, ESQUEMA, etapa, max_saida=v5.limite_de_saida(len(lote)))
            finally:
                for x in getattr(c, "chamadas", [])[antes:]:
                    log.append({"etapa": etapa, "itens": [i["id"] for i in lote], "pedido": x.get("pedido"),
                                "modelo": x.get("modelo_usado") or modelo, "tokens_entrada": x.get("tokens_entrada", 0),
                                "tokens_cache": x.get("tokens_cache", 0),
                                "tokens_cache_escrita": x.get("tokens_cache_escrita", 0),
                                "tokens_saida": x.get("tokens_saida", 0),
                                "tokens_raciocinio": x.get("tokens_raciocinio", 0),
                                "custo_usd": x.get("custo_usd", 0), "segundos": x.get("segundos"),
                                "limite_de_saida": v5.limite_de_saida(len(lote))})
            usado = next((x["modelo"] for x in reversed(log) if x["etapa"] == etapa), modelo)
            ids, vistos = {i["id"] for i in lote}, {}
            for e in resposta.get("avaliacoes", []) if isinstance(resposta, dict) else []:
                ident = e.get("id") if isinstance(e, dict) else None
                if ident not in ids:
                    descartes["id_desconhecido"] += 1
                elif ident in vistos and vistos[ident] != e:
                    vistos[ident] = None
                    descartes["resposta_contraditoria_duplicada"] += 1
                elif vistos.get(ident, 0) is not None:
                    vistos[ident] = e
            return {k: v for k, v in vistos.items() if v}, usado

        def processar(lote, extras, segunda):
            texto, autorizado = pedido(lote, blocks, extras, segunda)
            if len(lote) > 1 and pior_caso(texto, len(lote)) > teto - gasto():
                a, b = _dividir(lote)                      # o orçamento nunca é esticado para manter o grupo
                divisoes_exec.append({"motivo": "orcamento", "itens": [i["id"] for i in lote],
                                      "partes": [[i["id"] for i in a], [i["id"] for i in b]],
                                      "referencias_preservadas": True})
                return {**processar(a, extras, segunda), **processar(b, extras, segunda)}
            try:
                obtidas, usado = chamar(lote, extras, segunda, texto, autorizado)
            except RespostaCortada:
                if len(lote) > 1:
                    a, b = _dividir(lote)
                    divisoes_exec.append({"motivo": "resposta_cortada", "itens": [i["id"] for i in lote],
                                          "partes": [[i["id"] for i in a], [i["id"] for i in b]],
                                          "referencias_preservadas": True})
                    return {**processar(a, extras, segunda), **processar(b, extras, segunda)}
                falhas["cortada"] += 1
                return {}
            except Recusa:
                falhas["recusa"] += 1
                return {}
            saida = {}
            for item in lote:
                entrada = obtidas.get(item["id"])
                if entrada is None:
                    continue
                editorial = {k: v for k, v in entrada.items() if k != "relacoes"}
                registro, recusa = v41.julgar(item, editorial, autorizado[item["id"]], descartes, usado or modelo)
                if registro is None:
                    descartes["resposta_invalida_" + str(recusa)] += 1
                    continue
                declaradas, faltantes = conferir_relacoes(item, entrada.get("relacoes"), autorizado[item["id"]],
                                                          descartes)
                registro.update(relacoes=declaradas, relacoes_nao_declaradas=faltantes,
                                dependencias=[d["com"] for d in declaradas if d["tipo"] == "depende_de"])
                saida[item["id"]] = (registro, entrada)
            return saida

        pedidos_extra = {}
        try:
            feitos = 0
            lotes, divisoes_plano = agrupar(a_analisar, blocks, p["arestas"])
            divisoes_exec.extend(divisoes_plano)
            for lote in lotes:
                for i in lote:
                    registros[i["id"]] = {"id": i["id"], "decisao_humana": i["decisao"],
                                          "estado_validacao": "em_processamento",
                                          "chave_conteudo": i["chave_conteudo"],
                                          "chave_configuracao": i["chave_configuracao"], "iniciado_em": agora()}
                salvar()
                try:
                    saida = processar(lote, {i["id"]: i["antecedentes"] for i in lote if i.get("antecedentes")}, False)
                except BaseException:
                    devolver(lote)
                    raise
                for item in lote:
                    r = saida.get(item["id"])
                    if r is None:
                        devolver([item])
                        continue
                    registro, entrada = r
                    registro.update(estado_validacao="analisada", decisao_humana=item["decisao"],
                                    chave_conteudo=item["chave_conteudo"], chave_configuracao=item["chave_configuracao"],
                                    chave_relacoes=item["chave_relacoes"],
                                    configuracao=configuracao(modelo, esforco), rodadas=1, avaliado_em=agora(),
                                    antecedentes=[e.paragrafo for e in item["antecedentes"]],
                                    relacionados=[{k: r_[k] for k in ("id", "tipo", "paragrafo", "inicio", "fim")}
                                                  for r_ in item["relacionados"]],
                                    relacionados_omitidos=item["relacionados_omitidos"],
                                    consumo={"custo_usd": custo_do_item(item["id"]), "compartilhado_com": len(lote)},
                                    integridade={"paragrafo_sha256": v4._hash_texto(item["_bloco"].text),
                                                 "alvo_sha256": v4._hash_texto(
                                                     item["_bloco"].text[item["start"]:item["end"]])})
                    registros[item["id"]] = registro
                    if rodada_extra and entrada.get("precisa_mais_contexto") is True:
                        novas = v41.pedido_de_contexto(item, entrada, blocks, item["antecedentes"])
                        registro["pediu_mais_contexto"] = {"atendido": bool(novas),
                                                           "paragrafos": [e.paragrafo for e in novas]}
                        if novas:
                            pedidos_extra[item["id"]] = (item, item["antecedentes"] + novas)
                salvar()
                feitos += len(lote)
                if avancar:
                    avancar("avaliacao", feitos, len(a_analisar))
            if pedidos_extra:
                itens = [v[0] for v in pedidos_extra.values()]
                extras = {i: v[1] for i, v in pedidos_extra.items()}
                for lote in agrupar(itens, blocks, p["arestas"])[0]:
                    saida = processar(lote, extras, True)
                    for item in lote:
                        r = saida.get(item["id"])
                        if r is None:
                            registros[item["id"]]["pediu_mais_contexto"]["segunda_rodada"] = "sem_resposta"
                            continue
                        novo, _ = r
                        anterior = registros[item["id"]]
                        novo.update({k: anterior[k] for k in ("estado_validacao", "decisao_humana", "chave_conteudo",
                                                                "chave_configuracao", "chave_relacoes", "configuracao",
                                                                "avaliado_em", "integridade", "antecedentes",
                                                                "relacionados", "relacionados_omitidos")})
                        novo.update(rodadas=2, consumo={"custo_usd": custo_do_item(item["id"]),
                                                        "compartilhado_com": len(lote)},
                                    pediu_mais_contexto=dict(anterior["pediu_mais_contexto"],
                                                             estado_primeira_rodada=anterior["estado"]),
                                    contexto_alterou_conclusao=novo["estado"] != anterior["estado"])
                        registros[item["id"]] = novo
                    salvar()
        except TetoAtingido as erro:
            estado.update(interrompida=True, motivo=str(erro), teto=True)
        except ErroModelo as erro:
            estado.update(interrompida=True, motivo=str(erro))
        julgados = [por_id[i] for i, r in registros.items() if i in por_id and r.get("avaliacao")]
        conflitos = v41.reconciliar(julgados, registros, descartes)
        salvar()

    contagem = Counter(r.get("estado") for i, r in registros.items()
                       if i in por_id and r.get("estado_validacao") == "analisada")
    sem = [i["id"] for i in a_analisar if registros.get(i["id"], {}).get("estado_validacao") != "analisada"]
    soma = lambda k: sum(x.get(k, 0) for x in log)
    relatorio = consistencia(p["avaliar"], registros, p["arestas"])
    resumo = {"versao": VERSAO, "provedor": "openai", "modelo": modelo, "esforco": esforco, "elegiveis": p["elegiveis"],
              "analisadas_agora": len(a_analisar) - len(sem), "reutilizadas_sem_custo": p["reutilizadas"],
              "desatualizadas": p["desatualizadas"], "nao_localizadas": p["nao_localizadas"], "sem_resposta": len(sem),
              "interrompida": estado["interrompida"], "motivo_interrupcao": estado["motivo"],
              "resultados": {k: contagem[k] for k in v4.RESULTADOS},
              "pediram_mais_contexto": sum(bool(r.get("pediu_mais_contexto")) for r in registros.values()),
              "contexto_alterou_conclusao": sum(bool(r.get("contexto_alterou_conclusao")) for r in registros.values()),
              "conflitos": conflitos, "descartes": dict(descartes), "falhas": dict(falhas), "pedidos": len(log),
              "divisoes": divisoes_exec, "consistencia": relatorio["resumo"],
              "pontos_de_atencao": len(relatorio["atencao"]),
              "tokens_entrada": soma("tokens_entrada"), "tokens_cache": soma("tokens_cache"),
              "tokens_cache_escrita": soma("tokens_cache_escrita"), "tokens_saida": soma("tokens_saida"),
              "tokens_raciocinio": soma("tokens_raciocinio"), "custo_usd": round(soma("custo_usd"), 6),
              "modelos_servidos": sorted({x["modelo"] for x in log}), "teto_usd": teto}
    if estado["interrompida"]:
        avisos.append("Validador V5.1: execução parcial. " + estado["motivo"] +
                      f" {len(sem)} apontamento(s) ficaram sem análise e voltam a ser analisados na próxima execução.")
    avisos.append(f"Validador V5.1 ({modelo}): {resumo['analisadas_agora']} analisada(s), {p['reutilizadas']} "
                  f"reutilizada(s) sem custo; custo US$ {resumo['custo_usd']:.4f}. A consistência entre apontamentos "
                  "é informativa; resultado armazenado não é prova de correção; nenhuma decisão foi alterada.")
    return registros, avisos, resumo
