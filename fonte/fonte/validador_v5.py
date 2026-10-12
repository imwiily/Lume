"""Validador de decisões V5 (experimental): o contrato da V4.1 avaliado por GPT-6.1 Sol (API da OpenAI).

Módulo isolado. Não altera nem lê V2, V3, V4 ou V4.1 (nem seus estados persistidos); só reutiliza, sem
mudar, o contrato editorial da V4.1: prompt de sistema, esquema, montagem dos pedidos (mesmo texto), recuperação
de antecedentes por relevância, derivação do resultado e verificação determinística das evidências. Estado e
trava próprios (`validacoes-v5.json`).

O que é inevitavelmente diferente do contrato da Anthropic (ver `DIFERENCAS_DE_CONTRATO`):
API Responses com `text.format` JSON Schema estrito; esforço de raciocínio em `reasoning.effort`; os tokens de
raciocínio contam no `max_output_tokens` e são cobrados como saída; cache automático (a escrita é cobrada à
parte); `store=false` para não reter a resposta; ids de pedido e de modelo vêm do próprio objeto de resposta.

A chave da API vem de `OPENAI_API_KEY` ou das Chaves do macOS (serviço `lume-openai`) e nunca é gravada,
registrada nem passada em argumento.
"""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import validador_decisoes as vd
from . import validador_v3 as v3
from . import validador_v4 as v4
from . import validador_v4_1 as v41
from .validador_v4 import ValidacaoEmAndamento

VERSAO = "5"
MODELO = "gpt-6.1-sol"
ESFORCO = "medium"              # padrão do modelo; a mesma intenção do esforço médio usado com o Sonnet
ARQUIVO = "validacoes-v5.json"
TRAVA = "validacoes-v5.lock"
SERVICO_KEYCHAIN = "lume-openai"
ENDERECO = "https://api.openai.com"

# Preços por milhão de tokens (entrada, escrita de cache, leitura de cache, saída), contexto curto (até 272 mil
# tokens de entrada). Fonte: developers.openai.com/api/docs/pricing e /models/gpt-6.1-sol, consultadas em
# 11/10/2026. Acima de 272 mil tokens o preço sobe; este experimento nunca chega perto.
PRECOS = {"gpt-6.1-sol": {"entrada": 2.00, "escrita_cache": 2.50, "cache": 0.10, "saida": 10.00}}
CONTEXTO_CURTO_MAX = 272_000
CARACTERES_POR_TOKEN = vd.CARACTERES_POR_TOKEN   # estimativa conservadora; o tokenizador da OpenAI difere

# O raciocínio consome o mesmo limite da saída visível. A documentação recomenda reservar bastante folga; o
# limite abaixo é por pedido (fixo + por item) e é o que o orçamento reserva no pior caso.
SAIDA_FIXA, SAIDA_POR_ITEM = 10_000, 4_000
SAIDA_VISIVEL_ESPERADA = v41.SAIDA_ESPERADA          # (400, 560): mesma saída visível da V4.1
RACIOCINIO_CENARIOS = (0, 1_500, 4_000, 8_000)       # tokens de raciocínio por item: não medidos

DIFERENCAS_DE_CONTRATO = (
    "Endpoint /v1/responses com text.format json_schema estrito (todas as propriedades obrigatórias e "
    "additionalProperties=false), em vez de output_config da Anthropic.",
    "Raciocínio: reasoning.effort (medium) em vez de output_config.effort; tokens de raciocínio contam no "
    "max_output_tokens e são cobrados como saída; podem esgotar o limite antes de qualquer texto visível.",
    "Cache de prompt automático (>= 1.024 tokens), sem marcação cache_control; escrita cobrada a 1,25x e leitura "
    "a 0,05x do preço de entrada; reportados em usage.input_tokens_details.",
    "Sem retomada automática para outro modelo (a Anthropic tem); o modelo servido vem em response.model.",
    "Tokenizador diferente: a estimativa de entrada por caracteres não equivale à contagem real.",
    "store=false: a resposta não é retida para consulta posterior; não há recuperação por id depois da falha.",
    "Recusas aparecem como item `refusal` na saída; truncamento como status incomplete / max_output_tokens.",
)

SISTEMA = v41.SISTEMA        # critérios e significados editoriais da V4.1, sem alteração
ESQUEMA_V41 = v41.ESQUEMA


def esquema_estrito(esquema=None):
    """Esquema da V4.1 no formato que o modo estrito da OpenAI exige: objetos fechados e todas as propriedades
    obrigatórias. O conteúdo editorial do contrato é o mesmo."""
    def fechar(no):
        if isinstance(no, dict):
            novo = {k: fechar(v) for k, v in no.items()}
            if novo.get("type") == "object":
                novo["additionalProperties"] = False
                novo["required"] = list(novo.get("properties", {}))
            return novo
        if isinstance(no, list):
            return [fechar(v) for v in no]
        return no
    return fechar(json.loads(json.dumps(esquema or ESQUEMA_V41)))


ESQUEMA = esquema_estrito()


# --- chave e transporte ---------------------------------------------------------------------------

def chave_da_api():
    """OPENAI_API_KEY ou as Chaves do macOS (serviço lume-openai). Devolve None se não houver."""
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    try:
        saida = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", SERVICO_KEYCHAIN, "-w"],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (saida.stdout.strip() or None) if saida.returncode == 0 else None


def transporte_http(chave, tempo_limite=600):
    """Transporte real (urllib). `chave` só entra no cabeçalho Authorization; erros nunca a carregam."""
    def enviar(metodo, caminho, corpo=None):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        pedido = Request(ENDERECO + caminho, data=dados, method=metodo,
                         headers={"Authorization": "Bearer " + chave, "Content-Type": "application/json"})
        try:
            with urlopen(pedido, timeout=tempo_limite) as resposta:
                return resposta.status, json.load(resposta), dict(resposta.headers)
        except HTTPError as erro:
            try:
                corpo_erro = json.loads(erro.read().decode("utf-8", "replace"))
            except ValueError:
                corpo_erro = {}
            return erro.code, corpo_erro, dict(erro.headers)
        except TimeoutError as erro:
            raise TimeoutError("tempo esgotado") from None
        except (URLError, OSError) as erro:
            raise ConnectionError("sem conexão") from None
    return enviar


# --- cliente ---------------------------------------------------------------------------------------

def _erros():
    from coerencia.modelo import ErroModelo, Recusa, RespostaCortada, TetoAtingido
    return ErroModelo, Recusa, RespostaCortada, TetoAtingido


class OpenAI:
    """Cliente mínimo da API Responses com a mesma interface do `Claude` do Coerencia usada pelo Validador:
    `json`, `verificar`, `modelo` e `chamadas`, mais orçamento preventivo obrigatório."""
    TENTATIVAS = 3

    def __init__(self, modelo=MODELO, esforco=ESFORCO, orcamento=None, transporte=None, tempo_limite=600):
        if modelo not in PRECOS:
            raise ValueError(f"Modelo sem preço conhecido: {modelo}.")
        self.modelo, self.esforco, self.orcamento = modelo, esforco, orcamento
        self.preco = PRECOS[modelo]
        self.chamadas = []
        self.espera = time.sleep
        self.caracteres_por_token = CARACTERES_POR_TOKEN
        if transporte is None:
            chave = chave_da_api()
            if not chave:
                ErroModelo = _erros()[0]
                raise ErroModelo("Chave da API da OpenAI ausente. Guarde-a nas Chaves do macOS (serviço "
                                 f"{SERVICO_KEYCHAIN}) ou defina OPENAI_API_KEY.")
            transporte = transporte_http(chave, tempo_limite)
        self.transporte = transporte

    def verificar(self):
        """Confere credencial e modelo sem gastar tokens (consulta de metadados do modelo)."""
        ErroModelo = _erros()[0]
        try:
            status, dados, _ = self.transporte("GET", f"/v1/models/{self.modelo}", None)
        except (ConnectionError, TimeoutError) as erro:
            raise ErroModelo("Sem conexão com a API da OpenAI.") from None
        if status in (401, 403):
            raise ErroModelo("Chave da API da OpenAI ausente ou inválida.")
        if status == 404:
            raise ErroModelo(f"Modelo {self.modelo} não encontrado na API.")
        if status >= 400:
            raise ErroModelo(f"A API recusou a consulta do modelo ({status}).")
        return dados.get("id") == self.modelo

    def custo(self, uso):
        """Custo real de um uso (dict `usage` da resposta). Cada token de entrada é cobrado a uma só taxa:
        não armazenado, escrito no cache ou lido do cache. Raciocínio já está dentro de output_tokens."""
        p = self.preco
        detalhe = uso.get("input_tokens_details") or {}
        entrada, cache, escrita = uso.get("input_tokens", 0), detalhe.get("cached_tokens", 0), detalhe.get("cache_write_tokens", 0)
        normal = max(entrada - cache - escrita, 0)
        return (normal * p["entrada"] + escrita * p["escrita_cache"] + cache * p["cache"]
                + uso.get("output_tokens", 0) * p["saida"]) / 1e6

    def custo_maximo(self, sistema, usuario, esquema, max_saida):
        """Pior caso de uma chamada: toda a entrada como escrita de cache e o limite de saída inteiro."""
        p = self.preco
        caracteres = len(sistema) + len(usuario) + len(json.dumps(esquema, ensure_ascii=False))
        entrada = int(caracteres / self.caracteres_por_token) + 1
        return (entrada * p["escrita_cache"] + max_saida * p["saida"]) / 1e6

    def json(self, sistema, usuario, esquema, etapa, max_saida=None):
        ErroModelo, Recusa, RespostaCortada, TetoAtingido = _erros()
        max_saida = max_saida or (SAIDA_FIXA + SAIDA_POR_ITEM)
        corpo = {"model": self.modelo, "instructions": sistema, "input": usuario,
                 "text": {"format": {"type": "json_schema", "name": "validacao_de_decisoes", "strict": True,
                                     "schema": esquema}},
                 "reasoning": {"effort": self.esforco}, "max_output_tokens": max_saida, "store": False}
        extra = self.custo_maximo(sistema, usuario, esquema, max_saida)
        if (len(sistema) + len(usuario)) / self.caracteres_por_token > CONTEXTO_CURTO_MAX:
            raise ErroModelo("Pedido acima do contexto curto: preço diferente e fora do orçamento do experimento.")
        inicio = time.monotonic()
        ultimo = None
        for tentativa in range(self.TENTATIVAS):
            if self.orcamento:
                self.orcamento.conferir(extra)
            try:
                status, dados, cabecalhos = self.transporte("POST", "/v1/responses", corpo)
            except TimeoutError:
                # Pode ter sido cobrado: conta o pior caso no teto, como o cliente da Anthropic.
                self.chamadas.append({"etapa": etapa, "segundos": 0, "tokens_entrada": 0, "tokens_cache": 0,
                                      "tokens_cache_escrita": 0, "tokens_saida": 0, "tokens_raciocinio": 0,
                                      "modelo_usado": None, "pedido": None, "presumido": True,
                                      "custo_usd": round(extra, 6)})
                if self.orcamento:
                    self.orcamento.gasto += extra
                raise ErroModelo("A API não respondeu a tempo; o pior caso do pedido foi contado no teto.") from None
            except ConnectionError:
                status, dados, cabecalhos = 0, {}, {}
            if status in (0, 429) or status >= 500:
                ultimo = status
                if tentativa < self.TENTATIVAS - 1:
                    self.espera(2 ** tentativa)
                    continue
                if status == 429:
                    raise ErroModelo("Limite de uso da API da OpenAI atingido. Tente mais tarde.")
                raise ErroModelo("Sem conexão com a API da OpenAI." if status == 0
                                 else f"A API da OpenAI falhou ({status}).")
            if status in (401, 403):
                raise ErroModelo("Chave da API da OpenAI ausente ou inválida.")
            if status >= 400:
                erro = (dados.get("error") or {}) if isinstance(dados, dict) else {}
                raise ErroModelo(f"A API da OpenAI recusou o pedido ({status}: {erro.get('code') or erro.get('type') or 'erro'}).")
            break
        uso = dados.get("usage") or {}
        detalhe_in, detalhe_out = uso.get("input_tokens_details") or {}, uso.get("output_tokens_details") or {}
        chamada = {"etapa": etapa, "segundos": round(time.monotonic() - inicio, 1),
                   "tokens_entrada": uso.get("input_tokens", 0), "tokens_cache": detalhe_in.get("cached_tokens", 0),
                   "tokens_cache_escrita": detalhe_in.get("cache_write_tokens", 0),
                   "tokens_saida": uso.get("output_tokens", 0), "tokens_raciocinio": detalhe_out.get("reasoning_tokens", 0),
                   "modelo_usado": dados.get("model"), "pedido": dados.get("id") or (cabecalhos or {}).get("x-request-id")}
        chamada["custo_usd"] = round(self.custo(uso), 6)
        self.chamadas.append(chamada)
        if self.orcamento:
            self.orcamento.gasto += chamada["custo_usd"]
        if dados.get("status") == "incomplete":
            razao = (dados.get("incomplete_details") or {}).get("reason")
            if razao == "max_output_tokens":
                raise RespostaCortada(f"Resposta cortada pelo limite de saída na etapa {etapa}.")
            raise ErroModelo(f"Resposta incompleta na etapa {etapa} ({razao or 'motivo desconhecido'}).")
        if dados.get("status") not in (None, "completed"):
            codigo = ((dados.get("error") or {}).get("code")) or dados.get("status")
            raise ErroModelo(f"A API da OpenAI não concluiu a etapa {etapa} ({codigo}).")
        texto = None
        for item in dados.get("output", []) or []:
            if item.get("type") != "message":
                continue
            for parte in item.get("content", []) or []:
                if parte.get("type") == "refusal":
                    raise Recusa(f"O modelo recusou a etapa {etapa}.")
                if parte.get("type") == "output_text" and texto is None:
                    texto = parte.get("text")
        try:
            return json.loads(texto or "")
        except ValueError:
            raise ErroModelo(f"A API não devolveu JSON válido na etapa {etapa}.") from None


# --- preparação, estado e trava ---------------------------------------------------------------------

def configuracao(modelo=MODELO, esforco=ESFORCO):
    return {"provedor": "openai", "modelo": modelo, "esforco": esforco, "versao": VERSAO, "api": "responses",
            "contrato_editorial": f"v4.1:{v41.VERSAO_PROMPT}.{v41.VERSAO_CONTRATO}",
            "janela": vd.JANELA["juiz"], "prompt_sha256": v4._hash_texto(SISTEMA)[:16],
            "saida": [SAIDA_FIXA, SAIDA_POR_ITEM]}


def preparar(blocks, findings, decisoes, guardados=None, modelo=MODELO, esforco=ESFORCO, config=None):
    avaliar, perdidos, fora = vd.preparar(blocks, findings, decisoes, f"v5-{modelo}", (modelo,), config)
    cfg_hash = vd._hash(configuracao(modelo, esforco))
    for item in avaliar:
        item["antecedentes"] = v41._antecedentes_do_item(item, blocks, (guardados or {}).get(item["id"]))
        # a chave de conteúdo é a da V4.1: mesmo alerta, decisão e contexto
        item["chave_conteudo"] = v41.chave_conteudo(item, blocks, item["antecedentes"])
        item["chave_configuracao"] = cfg_hash
    return avaliar, perdidos, fora


def ler(pasta):
    caminho = Path(pasta) / ARQUIVO
    if not caminho.exists():
        return {}, None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if dados.get("v5") != 1:
            raise ValueError
        return dict(dados["itens"]), None
    except (OSError, ValueError, KeyError, TypeError):
        return {}, f"Validador V5: {ARQUIVO} não pôde ser lido; tudo foi tratado como não analisado."


def gravar(pasta, itens, meta=None):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = pasta / (ARQUIVO + ".tmp")
    temporario.write_text(json.dumps({"versao": 1, "v5": 1, "meta": meta or {}, "itens": itens},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    temporario.replace(pasta / ARQUIVO)


@contextmanager
def trava(pasta):
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
            "reutilizadas": contagem["valida"], "desatualizadas": sum(v for k, v in contagem.items() if k.startswith("desatualizada")),
            "em_processamento": contagem["em_processamento"], "nao_localizadas": len(perdidos), "fora": fora,
            "situacoes": dict(contagem), "elegiveis": len(avaliar) + len(perdidos), "aviso": aviso, "avaliar": avaliar}


def limite_de_saida(n_itens):
    return SAIDA_FIXA + SAIDA_POR_ITEM * max(1, n_itens)


def estimar(blocks, findings, decisoes, pasta=None, *, modelo=MODELO, esforco=ESFORCO, revalidar=(), config=None,
            teto=None):
    """Chamadas, tokens e custo previstos, sem rede. O raciocínio do GPT nunca foi medido neste conjunto: o custo
    esperado é dado como cenários de tokens de raciocínio por item, e o pior caso é o limite de saída inteiro."""
    p = planejar(blocks, findings, decisoes, pasta, modelo=modelo, esforco=esforco, revalidar=revalidar, config=config)
    novos = p["a_analisar"]
    preco = PRECOS[modelo]
    grupos = v4.lotes(novos, blocks)
    fixo = (len(SISTEMA) + len(json.dumps(ESQUEMA))) / CARACTERES_POR_TOKEN
    entrada_tokens = visivel = 0.0
    entrada_usd = pior = limites = 0.0
    piores = []
    for k, lote in enumerate(grupos):
        texto, _ = v4.pedido(lote, blocks, {i["id"]: i["antecedentes"] for i in lote if i.get("antecedentes")})
        corpo = len(texto) / CARACTERES_POR_TOKEN
        entrada_tokens += fixo + corpo
        taxa_fixo = preco["escrita_cache"] if k == 0 else preco["cache"]
        entrada_usd += (fixo * taxa_fixo + corpo * preco["entrada"]) / 1e6
        visivel += SAIDA_VISIVEL_ESPERADA[0] + SAIDA_VISIVEL_ESPERADA[1] * len(lote)
        lim = limite_de_saida(len(lote))
        limites += lim
        piores.append(((fixo + corpo) * preco["escrita_cache"] + lim * preco["saida"]) / 1e6)
    n = len(novos)
    cenarios = {str(r): round(entrada_usd + (visivel + r * n) * preco["saida"] / 1e6, 4) for r in RACIOCINIO_CENARIOS}
    maximo = sum(piores)
    saida = {"versao": VERSAO, "provedor": "openai", "modelo": modelo, "esforco": esforco, "elegiveis": p["elegiveis"],
             "a_analisar": n, "reutilizadas_sem_custo": p["reutilizadas"], "nao_localizadas": p["nao_localizadas"],
             "chamadas_primeira_rodada": len(grupos), "chamadas_segunda_rodada_maximo": len(grupos),
             "tokens_entrada_estimados": int(entrada_tokens), "tokens_saida_visivel_esperados": int(visivel),
             "limite_de_saida_por_pedido": [limite_de_saida(len(g)) for g in grupos],
             "custo_por_cenario_de_raciocinio_usd": cenarios,
             "custo_maximo_primeira_rodada_usd": round(maximo, 4),
             "custo_maximo_com_segunda_rodada_usd": round(2 * maximo, 4),
             "pior_chamada_usd": round(max(piores, default=0.0), 4),
             "teto_minimo_usd": round(max(piores, default=0.0) + 0.005, 2),
             "precos_usd_por_milhao": preco, "fonte_dos_precos": "developers.openai.com (consulta de 11/10/2026)",
             "premissas": ["entrada estimada por caracteres (tokenizador da OpenAI difere)",
                           "raciocínio por item não medido: ver cenários",
                           "primeira chamada paga a escrita de cache; as demais leem o prompt de sistema do cache"]}
    if teto is not None:
        saida["teto_usd"] = teto
        saida["cabe_no_teto"] = saida["teto_minimo_usd"] <= teto
    return saida


# --- execução ------------------------------------------------------------------------------------------

def avaliar(blocks, findings, decisoes, *, pasta, teto, modelo=MODELO, esforco=ESFORCO, revalidar=(), cliente=None,
            transporte=None, avancar=None, meta=None, config=None, rodada_extra=True):
    """Executa a V5. Só analisa o que é novo ou foi pedido para revalidar; o resto é reutilizado sem chamada."""
    ErroModelo, Recusa, RespostaCortada, TetoAtingido = _erros()
    from coerencia.modelo import Orcamento
    with trava(pasta):
        p = planejar(blocks, findings, decisoes, pasta, modelo=modelo, esforco=esforco, revalidar=revalidar,
                     config=config, ativo=False)
        guardados, aviso = ler(pasta)
        por_id = {i["id"]: i for i in p["avaliar"]}
        registros, avisos = dict(guardados), [aviso] if aviso else []
        descartes, falhas, log = Counter(), Counter(), []
        estado = {"interrompida": False, "motivo": "", "teto": False}
        meta = dict(meta or {}, configuracao=configuracao(modelo, esforco), pedidos=log)
        a_analisar = p["a_analisar"]
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
            novo = OpenAI(modelo, esforco, orcamento=Orcamento(teto), transporte=transporte)
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

        def chamar(lote, extras, segunda):
            texto, autorizado = v4.pedido(lote, blocks, extras, segunda)
            antes = len(getattr(c, "chamadas", []))
            etapa = f"v5-r{2 if segunda else 1} §{lote[0]['_bloco'].number}"
            try:
                resposta = c.json(SISTEMA, texto, ESQUEMA, etapa, max_saida=limite_de_saida(len(lote)))
            finally:
                for x in getattr(c, "chamadas", [])[antes:]:
                    log.append({"etapa": etapa, "itens": [i["id"] for i in lote], "pedido": x.get("pedido"),
                                "modelo": x.get("modelo_usado") or modelo, "tokens_entrada": x.get("tokens_entrada", 0),
                                "tokens_cache": x.get("tokens_cache", 0), "tokens_cache_escrita": x.get("tokens_cache_escrita", 0),
                                "tokens_saida": x.get("tokens_saida", 0), "tokens_raciocinio": x.get("tokens_raciocinio", 0),
                                "custo_usd": x.get("custo_usd", 0), "segundos": x.get("segundos"),
                                "limite_de_saida": limite_de_saida(len(lote))})
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
            return {k: v for k, v in vistos.items() if v}, autorizado, usado

        def processar(lote, extras, segunda):
            try:
                obtidas, autorizado, usado = chamar(lote, extras, segunda)
            except RespostaCortada:
                if len(lote) > 1:
                    meio = len(lote) // 2
                    return {**processar(lote[:meio], extras, segunda), **processar(lote[meio:], extras, segunda)}
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
                registro, recusa = v41.julgar(item, entrada, autorizado[item["id"]], descartes, usado or modelo)
                if registro is None:
                    descartes["resposta_invalida_" + str(recusa)] += 1
                    continue
                saida[item["id"]] = (registro, entrada)
            return saida

        pedidos_extra = {}
        try:
            feitos = 0
            for lote in v4.lotes(a_analisar, blocks):
                for i in lote:
                    registros[i["id"]] = {"id": i["id"], "decisao_humana": i["decisao"], "estado_validacao": "em_processamento",
                                          "chave_conteudo": i["chave_conteudo"], "chave_configuracao": i["chave_configuracao"],
                                          "iniciado_em": agora()}
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
                                    configuracao=configuracao(modelo, esforco), rodadas=1, avaliado_em=agora(),
                                    antecedentes=[e.paragrafo for e in item["antecedentes"]],
                                    consumo={"custo_usd": custo_do_item(item["id"]), "compartilhado_com": len(lote)},
                                    integridade={"paragrafo_sha256": v4._hash_texto(item["_bloco"].text),
                                                 "alvo_sha256": v4._hash_texto(item["_bloco"].text[item["start"]:item["end"]])})
                    registros[item["id"]] = registro
                    if rodada_extra and entrada.get("precisa_mais_contexto") is True:
                        novas = v41.pedido_de_contexto(item, entrada, blocks, item["antecedentes"])
                        registro["pediu_mais_contexto"] = {"atendido": bool(novas), "paragrafos": [e.paragrafo for e in novas]}
                        if novas:
                            pedidos_extra[item["id"]] = (item, item["antecedentes"] + novas)
                salvar()
                feitos += len(lote)
                if avancar:
                    avancar("avaliacao", feitos, len(a_analisar))
            if pedidos_extra:
                itens = [v[0] for v in pedidos_extra.values()]
                extras = {i: v[1] for i, v in pedidos_extra.items()}
                for lote in v4.lotes(itens, blocks):
                    saida = processar(lote, extras, True)
                    for item in lote:
                        r = saida.get(item["id"])
                        if r is None:
                            registros[item["id"]]["pediu_mais_contexto"]["segunda_rodada"] = "sem_resposta"
                            continue
                        novo, _ = r
                        anterior = registros[item["id"]]
                        novo.update({k: anterior[k] for k in ("estado_validacao", "decisao_humana", "chave_conteudo",
                                                                "chave_configuracao", "configuracao", "avaliado_em",
                                                                "integridade", "antecedentes")})
                        novo.update(rodadas=2, consumo={"custo_usd": custo_do_item(item["id"]), "compartilhado_com": len(lote)},
                                    pediu_mais_contexto=dict(anterior["pediu_mais_contexto"], estado_primeira_rodada=anterior["estado"]),
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

    contagem = Counter(r.get("estado") for i, r in registros.items() if i in por_id and r.get("estado_validacao") == "analisada")
    sem = [i["id"] for i in a_analisar if registros.get(i["id"], {}).get("estado_validacao") != "analisada"]
    soma = lambda k: sum(x.get(k, 0) for x in log)
    resumo = {"versao": VERSAO, "provedor": "openai", "modelo": modelo, "esforco": esforco, "elegiveis": p["elegiveis"],
              "analisadas_agora": len(a_analisar) - len(sem), "reutilizadas_sem_custo": p["reutilizadas"],
              "desatualizadas": p["desatualizadas"], "nao_localizadas": p["nao_localizadas"], "sem_resposta": len(sem),
              "interrompida": estado["interrompida"], "motivo_interrupcao": estado["motivo"],
              "resultados": {k: contagem[k] for k in v4.RESULTADOS},
              "pediram_mais_contexto": sum(bool(r.get("pediu_mais_contexto")) for r in registros.values()),
              "contexto_alterou_conclusao": sum(bool(r.get("contexto_alterou_conclusao")) for r in registros.values()),
              "conflitos": conflitos, "descartes": dict(descartes), "falhas": dict(falhas), "pedidos": len(log),
              "tokens_entrada": soma("tokens_entrada"), "tokens_cache": soma("tokens_cache"),
              "tokens_cache_escrita": soma("tokens_cache_escrita"), "tokens_saida": soma("tokens_saida"),
              "tokens_raciocinio": soma("tokens_raciocinio"), "custo_usd": round(soma("custo_usd"), 6),
              "modelos_servidos": sorted({x["modelo"] for x in log}), "teto_usd": teto}
    if estado["interrompida"]:
        avisos.append("Validador V5: execução parcial. " + estado["motivo"] +
                      f" {len(sem)} apontamento(s) ficaram sem análise e voltam a ser analisados na próxima execução.")
    avisos.append(f"Validador V5 ({modelo}): {resumo['analisadas_agora']} analisada(s), {p['reutilizadas']} reutilizada(s) sem "
                  f"custo, {resumo['resultados']['contestada']} contestação(ões); custo US$ {resumo['custo_usd']:.4f}. "
                  "Resultado armazenado não é prova de correção; nenhuma decisão foi alterada.")
    return registros, avisos, resumo
