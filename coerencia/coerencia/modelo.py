"""Clientes de modelo com a mesma interface: API do Claude (padrão), Google Gemini e Ollama local.

Ambos pedem respostas em JSON com esquema (saída estruturada) e registram tempo
e tokens de cada chamada em `chamadas`. Com a API do Claude, o texto das cenas
enviadas vai aos servidores da Anthropic (ou do Google, com `gemini-*`); com o Ollama, nada sai do computador.
"""
import json
import os
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

LOCAIS = {"127.0.0.1", "localhost", "::1"}


class ErroModelo(Exception):
    pass


class Recusa(ErroModelo):
    """O modelo recusou o pedido (classificadores de segurança)."""


class RespostaCortada(ErroModelo):
    """A resposta atingiu `max_tokens` antes de terminar."""


class TetoAtingido(ErroModelo):
    """O teto de gasto da execução foi atingido antes da próxima chamada.
    `minimo`: teto mínimo estimado para que a chamada barrada fosse enviada."""

    def __init__(self, mensagem, minimo=None):
        super().__init__(mensagem)
        self.minimo = minimo


class Ollama:
    def __init__(self, modelo, endereco="http://127.0.0.1:11434", pensar=False, contexto=16384, tempo_limite=900):
        if urlparse(endereco).hostname not in LOCAIS:
            raise ValueError("O Coerencia só conversa com um modelo nesta máquina (127.0.0.1).")
        self.modelo, self.endereco, self.pensar = modelo, endereco.rstrip("/"), pensar
        self.contexto, self.tempo_limite = contexto, tempo_limite
        self.abrir = build_opener(ProxyHandler({})).open
        self.chamadas = []
        self.envia_pensar = True  # Alguns modelos não aceitam o campo ‘think’.

    def _post(self, caminho, corpo):
        pedido = Request(self.endereco + caminho, data=json.dumps(corpo).encode("utf-8"),
                         headers={"Content-Type": "application/json"})
        try:
            with self.abrir(pedido, timeout=self.tempo_limite) as resposta:
                return json.load(resposta)
        except HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")
            raise ErroModelo(f"O modelo recusou o pedido ({erro.code}): {detalhe[:300]}") from erro
        except (URLError, TimeoutError, OSError) as erro:
            raise ErroModelo("Não foi possível falar com o Ollama em " + self.endereco +
                             ". Confirme que ele está ativo (ollama serve).") from erro

    def verificar(self):
        modelos = {m["name"] for m in self._post_get("/api/tags").get("models", [])}
        if self.modelo not in modelos and self.modelo + ":latest" not in modelos:
            raise ErroModelo(f"Modelo {self.modelo} não instalado. Use: ollama pull {self.modelo}")

    def _post_get(self, caminho):
        try:
            with self.abrir(self.endereco + caminho, timeout=30) as resposta:
                return json.load(resposta)
        except (URLError, OSError) as erro:
            raise ErroModelo("Não foi possível falar com o Ollama em " + self.endereco +
                             ". Confirme que ele está ativo (ollama serve).") from erro

    def json(self, sistema, usuario, esquema, etapa):
        corpo = {"model": self.modelo, "stream": False, "format": esquema,
                 "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                 "options": {"temperature": 0, "seed": 7, "num_ctx": self.contexto}}
        ultimo = None
        for tentativa in range(3):
            if self.envia_pensar:
                corpo["think"] = self.pensar
            inicio = time.monotonic()
            try:
                resposta = self._post("/api/chat", corpo)
            except ErroModelo as erro:
                if self.envia_pensar and "think" in str(erro).lower():
                    self.envia_pensar = False
                    corpo.pop("think", None)
                    continue
                raise
            duracao = time.monotonic() - inicio
            texto = resposta.get("message", {}).get("content", "")
            self.chamadas.append({"etapa": etapa, "segundos": round(duracao, 1),
                                  "tokens_entrada": resposta.get("prompt_eval_count"),
                                  "tokens_saida": resposta.get("eval_count"), "tentativa": tentativa + 1})
            try:
                return json.loads(texto)
            except json.JSONDecodeError as erro:
                ultimo = erro
        raise ErroModelo(f"O modelo não devolveu JSON válido na etapa {etapa}: {ultimo}")


# Preços por milhão de tokens (entrada, saída, leitura de cache), em dólares.
# Fonte: platform.claude.com/docs/en/about-claude/pricing, conferida em 10/10/2026.
PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
    # Haiku 5.5: tarifa da faixa acima de 100 mil tokens (a de até 100 mil é US$ 0,10/0,50/0,01);
    # fica na mais cara porque a faixa não é medida aqui.
    "claude-haiku-5-5": (0.50, 2.50, 0.05),
    # Destinos da retomada automática (cobrados pela tarifa de quem executou) e modelos de topo.
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
}
ESCRITA_CACHE = 1.25  # escrita de cache de 5 min: 1,25 × a entrada (tabela da Anthropic)
# Pior caso de uma chamada: o pedido pode ser respondido por qualquer destes (retomada automática).
DESTINOS_RETOMADA = ("claude-opus-5", "claude-opus-4-8")
CARACTERES_POR_TOKEN = 2.5  # conservador: o tokenizador novo gera ~30% mais tokens
MAX_TOKENS = 16000
TENTATIVAS = 3  # 1 envio + 2 repetições, só para falhas que a API não cobra (429, 5xx, rede)


def tarifa(modelo):
    """(entrada, escrita de cache, leitura de cache, saída) por milhão de tokens. Modelo desconhecido
    paga, em cada coluna, o maior preço conhecido: nunca zero, para o teto não deixar de valer.
    Gemini tem tabela própria: sem escrita de cache cobrada (usamos o preço de entrada)."""
    if str(modelo).startswith("gemini-"):
        entrada, saida, leitura = precos_gemini(modelo)
        return entrada, entrada, leitura, saida
    conhecido = PRECOS.get(modelo) or PRECOS.get(next(
        (m for m in sorted(PRECOS, key=len, reverse=True) if str(modelo).startswith(m)), None))
    entrada, saida, leitura = conhecido or tuple(max(coluna) for coluna in zip(*PRECOS.values()))
    return entrada, entrada * ESCRITA_CACHE, leitura, saida
# Modelos que aceitam esforço e retomada automática em outro modelo quando o
# pedido é recusado pelos classificadores de segurança.
ATUAIS = {"claude-opus-5-5", "claude-sonnet-5-5"}


SERVICO_KEYCHAIN = "coerencia-anthropic"


def chave_do_keychain():
    """Chave guardada nas Chaves do macOS (serviço coerencia-anthropic), se houver.
    Evita deixar a chave em texto em arquivos de configuração."""
    try:
        saida = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", SERVICO_KEYCHAIN, "-w"],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if saida.returncode != 0:
        return None
    return saida.stdout.strip() or None


def estrito(esquema):
    """A saída estruturada da API exige objetos fechados (additionalProperties=false)."""
    if isinstance(esquema, dict):
        novo = {k: estrito(v) for k, v in esquema.items()}
        if novo.get("type") == "object":
            novo["additionalProperties"] = False
        return novo
    if isinstance(esquema, list):
        return [estrito(v) for v in esquema]
    return esquema


class Claude:
    """API do Claude. Credencial: ANTHROPIC_API_KEY (ou perfil do `ant auth login`)."""

    def __init__(self, modelo="claude-sonnet-5-5", esforco="medium", cliente=None, tempo_limite=600, orcamento=None):
        import anthropic
        self.anthropic = anthropic
        self.modelo, self.esforco, self.orcamento = modelo, esforco, orcamento
        if cliente is None:
            # Variável de ambiente tem prioridade; senão, as Chaves do macOS.
            chave = None if os.environ.get("ANTHROPIC_API_KEY") else chave_do_keychain()
            # Repetições feitas aqui (ver `json`), onde cada uma passa de novo pela conferência do teto.
            opcoes = {"timeout": tempo_limite, "max_retries": 0}
            cliente = anthropic.Anthropic(api_key=chave, **opcoes) if chave else anthropic.Anthropic(**opcoes)
        self.cliente = cliente
        self.chamadas = []
        self.caracteres_por_token = CARACTERES_POR_TOKEN
        self.espera = time.sleep

    def verificar(self):
        """Confere credencial e modelo sem gastar tokens."""
        try:
            self.cliente.models.retrieve(self.modelo)
        except (self.anthropic.AuthenticationError, TypeError) as erro:  # TypeError: nenhuma credencial
            raise ErroModelo("Chave da API ausente ou inválida. Guarde-a nas Chaves do macOS (serviço coerencia-anthropic) ou defina ANTHROPIC_API_KEY "
                             "(crie a chave em console.anthropic.com).") from erro
        except self.anthropic.NotFoundError as erro:
            raise ErroModelo(f"Modelo {self.modelo} não encontrado na API.") from erro
        except self.anthropic.APIConnectionError as erro:
            raise ErroModelo("Sem conexão com a API da Anthropic.") from erro

    def custo(self, chamada, modelo=None):
        """Custo de uma chamada pela tarifa do modelo que respondeu: entrada normal, escrita de
        cache, leitura de cache e saída têm preços diferentes."""
        entrada, escrita, leitura, saida = tarifa(modelo or chamada.get("modelo_usado") or self.modelo)
        cache, criacao = chamada["tokens_cache"], chamada.get("tokens_cache_criacao", 0)
        normal = chamada["tokens_entrada"] - cache - criacao
        return (normal * entrada + criacao * escrita + cache * leitura + chamada["tokens_saida"] * saida) / 1e6

    def custo_maximo(self, sistema, usuario, esquema, max_tokens):
        """Pior caso de uma chamada, antes de enviá-la. Cada tentativa paga texto e esquema como
        escrita de cache (a entrada mais cara) e saída inteira até `max_tokens`. Com retomada
        automática, a recusa da primeira tentativa pode ser cobrada (no meio da saída, ou em categorias
        faturadas) *além* da tentativa no destino mais caro: as duas somam. A entrada é estimada por
        caracteres; a saída é limite rígido da API."""
        caracteres = len(sistema) + len(usuario) + len(json.dumps(esquema, ensure_ascii=False))
        tokens = int(caracteres / self.caracteres_por_token) + 1
        tentativa = lambda modelo: (tokens * tarifa(modelo)[1] + max_tokens * tarifa(modelo)[3]) / 1e6
        if self.modelo not in ATUAIS:
            return tentativa(self.modelo)
        return tentativa(self.modelo) + max(tentativa(destino) for destino in (self.modelo, *DESTINOS_RETOMADA))

    def _custo_da_resposta(self, resposta, chamada):
        """Se a resposta itemiza as tentativas (`usage.iterations`, p.ex. retomada em outro modelo),
        soma cada uma na tarifa do seu modelo; nunca fica abaixo do que o uso final já indica."""
        total = 0.0
        for item in getattr(resposta.usage, "iterations", None) or []:
            campo = lambda nome: getattr(item, nome, None) or 0
            cache, criacao = campo("cache_read_input_tokens"), campo("cache_creation_input_tokens")
            total += self.custo({"tokens_cache": cache, "tokens_cache_criacao": criacao, "tokens_saida": campo("output_tokens"),
                                 "tokens_entrada": campo("input_tokens") + cache + criacao},
                                getattr(item, "model", None) or resposta.model)
        return max(total, self.custo(chamada))

    def _enviar(self, criar, pedido, extra, etapa):
        """Envia com repetição só para falhas que a API não cobra (429, 5xx, rede), conferindo o
        teto de novo antes de cada tentativa. Tempo esgotado pode ter sido cobrado: conta o pior caso."""
        for tentativa in range(TENTATIVAS):
            if self.orcamento:
                self.orcamento.conferir(extra)
            try:
                return criar(**pedido)
            except self.anthropic.AuthenticationError as erro:
                raise ErroModelo("Chave da API ausente ou inválida.") from erro
            except self.anthropic.APITimeoutError as erro:
                self.chamadas.append({"etapa": etapa, "segundos": 0, "tokens_entrada": 0, "tokens_cache": 0,
                                      "tokens_cache_criacao": 0, "tokens_saida": 0, "modelo_usado": None,
                                      "pedido": None, "presumido": True, "custo_usd": round(extra, 6)})
                if self.orcamento:
                    self.orcamento.gasto += extra
                raise ErroModelo("A API não respondeu a tempo; o pior caso do pedido foi contado no teto.") from erro
            except (self.anthropic.RateLimitError, self.anthropic.APIConnectionError, self.anthropic.InternalServerError) as erro:
                if tentativa < TENTATIVAS - 1:
                    self.espera(2 ** tentativa)
                    continue
                if isinstance(erro, self.anthropic.RateLimitError):
                    raise ErroModelo("Limite de uso da API atingido. Tente mais tarde ou confira o limite de gasto no console.") from erro
                if isinstance(erro, self.anthropic.APIConnectionError):
                    raise ErroModelo("Sem conexão com a API da Anthropic.") from erro
                raise ErroModelo(f"A API recusou o pedido ({erro.status_code}): {erro.message}") from erro
            except self.anthropic.APIStatusError as erro:
                raise ErroModelo(f"A API recusou o pedido ({erro.status_code}): {erro.message}") from erro

    def json(self, sistema, usuario, esquema, etapa):
        pedido = {
            "model": self.modelo, "max_tokens": MAX_TOKENS,
            # Prompt de sistema fixo: fica em cache entre chamadas quando atinge o tamanho mínimo.
            "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": usuario}],
            "output_config": {"format": {"type": "json_schema", "schema": estrito(esquema)}},
        }
        if self.modelo in ATUAIS:
            pedido["output_config"]["effort"] = self.esforco
            pedido.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            criar = self.cliente.beta.messages.create
        else:
            criar = self.cliente.messages.create
        # Reserva o pior caso da própria chamada: ela só sai se couber no que resta do teto.
        extra = self.custo_maximo(sistema, usuario, esquema, pedido["max_tokens"])
        inicio = time.monotonic()
        resposta = self._enviar(criar, pedido, extra, etapa)
        uso = resposta.usage
        cache = (getattr(uso, "cache_read_input_tokens", 0) or 0)
        criacao = getattr(uso, "cache_creation_input_tokens", 0) or 0
        entrada = (uso.input_tokens or 0) + cache + criacao
        chamada = {"etapa": etapa, "segundos": round(time.monotonic() - inicio, 1), "tokens_entrada": entrada,
                   "tokens_cache": cache, "tokens_cache_criacao": criacao, "tokens_saida": uso.output_tokens or 0,
                   "modelo_usado": resposta.model, "pedido": getattr(resposta, "_request_id", None)}
        chamada["custo_usd"] = round(self._custo_da_resposta(resposta, chamada), 6)
        self.chamadas.append(chamada)
        if self.orcamento:
            self.orcamento.gasto += chamada["custo_usd"]
        # A estimativa de caracteres por token falhou: aprende com a medição para as próximas.
        medido = (len(sistema) + len(usuario) + len(json.dumps(esquema, ensure_ascii=False))) / max(entrada, 1)
        self.caracteres_por_token = min(self.caracteres_por_token, max(medido, 1.0))
        if resposta.stop_reason == "refusal":
            raise Recusa(f"O modelo recusou a etapa {etapa} (pedido {chamada['pedido']}).")
        if resposta.stop_reason == "max_tokens":
            raise RespostaCortada(f"Resposta cortada por tamanho na etapa {etapa}; diminua --cena.")
        texto = next((b.text for b in resposta.content if b.type == "text"), "")
        try:
            return json.loads(texto)
        except json.JSONDecodeError as erro:
            raise ErroModelo(f"A API não devolveu JSON válido na etapa {etapa}.") from erro


# --- Google Gemini -----------------------------------------------------------------------------------
# Preços por milhão de tokens (entrada, saída incl. raciocínio, cache). Fonte: ai.google.dev/gemini-api/docs/pricing,
# conferida em 12/10/2026. A tabela traz preço promocional até 31/12/2026 (0,75/3,75/0,075); aqui vale sempre o
# vigente a partir de 01/01/2027, para a estimativa não depender de promoção.
PRECOS_GEMINI = {"gemini-3.8-flash": (1.50, 7.50, 0.15)}
BUSCA_GEMINI_USD = 0.014   # por consulta executada (Gemini 3+); cobrada aqui mesmo dentro da cota gratuita mensal
BUSCAS_MAXIMAS = 5         # pior caso reservado no teto por pedido com pesquisa (a API não limita as consultas)
ENDERECO_GEMINI = "https://generativelanguage.googleapis.com"
SERVICO_KEYCHAIN_GEMINI = "lume-gemini"
MAX_TOKENS_GEMINI = 16000
NIVEIS_GEMINI = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def precos_gemini(modelo):
    """(entrada, saída, cache); modelo Gemini sem preço conhecido paga o maior conhecido, nunca zero."""
    return PRECOS_GEMINI.get(modelo) or tuple(max(coluna) for coluna in zip(*PRECOS_GEMINI.values()))


def chave_gemini():
    """GEMINI_API_KEY ou as Chaves do macOS (serviço lume-gemini); nunca reaproveita a da Anthropic."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        saida = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", SERVICO_KEYCHAIN_GEMINI, "-w"],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (saida.stdout.strip() or None) if saida.returncode == 0 else None


def transporte_gemini(chave, tempo_limite=600):
    """Transporte real (urllib). A chave só vai no cabeçalho; nenhuma mensagem de erro a carrega."""
    def enviar(metodo, caminho, corpo=None):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        pedido = Request(ENDERECO_GEMINI + caminho, data=dados, method=metodo,
                         headers={"x-goog-api-key": chave, "Content-Type": "application/json"})
        try:
            with urlopen(pedido, timeout=tempo_limite) as resposta:
                return resposta.status, json.load(resposta)
        except HTTPError as erro:
            try:
                return erro.code, json.loads(erro.read().decode("utf-8", "replace"))
            except ValueError:
                return erro.code, {}
        except TimeoutError:
            raise TimeoutError("tempo esgotado") from None
        except (URLError, OSError):
            raise ConnectionError("sem conexão") from None
    return enviar


class Gemini:
    """API do Google (Interactions, /v1beta/interactions). Credencial: GEMINI_API_KEY ou serviço lume-gemini.
    Mesma interface do `Claude`: `json`, `verificar`, `modelo`, `esforco`, `chamadas`, `orcamento`.
    Sem repetição automática de chamada que possa ter sido cobrada; `pesquisa` fica desligada, salvo em `pesquisar`."""

    def __init__(self, modelo="gemini-3.8-flash", esforco="medium", orcamento=None, transporte=None, tempo_limite=600):
        self.modelo, self.esforco, self.orcamento = modelo, esforco, orcamento
        self.chamadas = []
        self.caracteres_por_token = CARACTERES_POR_TOKEN
        self.espera = time.sleep
        self.max_tokens, self.tentativas = MAX_TOKENS_GEMINI, TENTATIVAS
        if transporte is None:
            chave = chave_gemini()
            if not chave:
                raise ErroModelo("Chave da API do Google ausente. Guarde-a nas Chaves do macOS (serviço "
                                 f"{SERVICO_KEYCHAIN_GEMINI}) ou defina GEMINI_API_KEY (aistudio.google.com/apikey).")
            transporte = transporte_gemini(chave, tempo_limite)
        self.transporte = transporte

    def verificar(self):
        """Confere credencial e modelo consultando só os metadados do modelo (não gasta tokens)."""
        try:
            status, _ = self.transporte("GET", f"/v1beta/models/{self.modelo}", None)
        except (ConnectionError, TimeoutError):
            raise ErroModelo("Sem conexão com a API do Google.") from None
        if status in (400, 401, 403):
            raise ErroModelo("Chave da API do Google ausente ou inválida.")
        if status == 404:
            raise ErroModelo(f"Modelo {self.modelo} não encontrado na API.")
        if status >= 400:
            raise ErroModelo(f"A API do Google recusou a consulta do modelo ({status}).")

    def custo(self, chamada):
        """Custo do uso retornado: entrada normal e em cache, saída e raciocínio a tarifa de saída, mais as
        consultas de pesquisa executadas. `total_output_tokens` pode já incluir o raciocínio; somar os dois pode
        superestimar, nunca subestimar."""
        entrada, saida, cache = precos_gemini(self.modelo)
        cacheados = min(chamada["tokens_cache"], chamada["tokens_entrada"])
        return ((chamada["tokens_entrada"] - cacheados) * entrada + cacheados * cache
                + (chamada["tokens_saida"] + chamada["tokens_raciocinio"]) * saida) / 1e6 \
            + chamada.get("buscas", 0) * BUSCA_GEMINI_USD

    def custo_maximo(self, sistema, usuario, esquema, max_tokens, buscas=0):
        """Pior caso antes de enviar: toda a entrada ao preço cheio, saída até `max_tokens` (o raciocínio conta
        nesse limite) e, com pesquisa, `BUSCAS_MAXIMAS` consultas."""
        caracteres = len(sistema) + len(usuario) + len(json.dumps(esquema or {}, ensure_ascii=False))
        entrada, saida, _ = precos_gemini(self.modelo)
        return (int(caracteres / self.caracteres_por_token + 1) * entrada + max_tokens * saida) / 1e6 \
            + buscas * BUSCA_GEMINI_USD

    def _enviar(self, corpo, extra, etapa):
        """Uma tentativa, nunca repetida se pode ter sido cobrada: tempo esgotado conta o pior caso no teto.
        Só 429 e queda de rede antes de qualquer resposta (nada cobrado) repetem, conferindo o teto de novo."""
        for tentativa in range(self.tentativas):
            if self.orcamento:
                self.orcamento.conferir(extra)
            try:
                status, dados = self.transporte("POST", "/v1beta/interactions", corpo)
            except TimeoutError:
                self.chamadas.append({"etapa": etapa, "segundos": 0, "tokens_entrada": 0, "tokens_cache": 0,
                                      "tokens_cache_criacao": 0, "tokens_saida": 0, "tokens_raciocinio": 0, "buscas": 0, "modelo_usado": None,
                                      "pedido": None, "presumido": True, "custo_usd": round(extra, 6)})
                if self.orcamento:
                    self.orcamento.gasto += extra
                raise ErroModelo("A API do Google não respondeu a tempo; o pior caso do pedido foi contado no teto.") from None
            except ConnectionError:
                status, dados = 0, {}
            if status in (0, 429) and tentativa < self.tentativas - 1:
                self.espera(2 ** tentativa)
                continue
            if status == 0:
                raise ErroModelo("Sem conexão com a API do Google.")
            if status == 429:
                raise ErroModelo("Limite de uso da API do Google atingido. Tente mais tarde ou confira a cota no AI Studio.")
            if status in (401, 403):
                raise ErroModelo("Chave da API do Google ausente ou inválida.")
            if status >= 500:
                raise ErroModelo(f"A API do Google está indisponível ({status}). Nada foi repetido automaticamente.")
            if status >= 400:
                erro = (dados.get("error") or {}) if isinstance(dados, dict) else {}
                raise ErroModelo(f"A API do Google recusou o pedido ({status}: {erro.get('status') or 'erro'}).")
            return dados

    def _pedir(self, sistema, usuario, etapa, max_tokens, formato=None, pesquisa=False, esquema=None):
        corpo = {"model": self.modelo, "system_instruction": sistema, "input": usuario, "store": False,
                 "generation_config": {"max_output_tokens": max_tokens,
                                       "thinking_level": NIVEIS_GEMINI.get(self.esforco, "medium")}}
        if formato:
            corpo["response_format"] = formato
        if pesquisa:
            corpo["tools"] = [{"type": "google_search"}]
        extra = self.custo_maximo(sistema, usuario, esquema, max_tokens, BUSCAS_MAXIMAS if pesquisa else 0)
        inicio = time.monotonic()
        dados = self._enviar(corpo, extra, etapa)
        uso = dados.get("usage") or {}
        buscas = sum(g.get("count", 0) for g in uso.get("grounding_tool_count") or [] if g.get("type") == "google_search")
        chamada = {"etapa": etapa, "segundos": round(time.monotonic() - inicio, 1),
                   "tokens_entrada": uso.get("total_input_tokens", 0) or 0,
                   "tokens_cache": uso.get("total_cached_tokens", 0) or 0, "tokens_cache_criacao": 0,
                   "tokens_saida": uso.get("total_output_tokens", 0) or 0,
                   "tokens_raciocinio": uso.get("total_thought_tokens", 0) or 0, "buscas": buscas,
                   "modelo_usado": dados.get("model") or self.modelo, "pedido": dados.get("id")}
        # Pesquisa pedida mas uso não informado: o custo das consultas é desconhecido, não zero.
        if pesquisa and "grounding_tool_count" not in uso:
            chamada["buscas"] = BUSCAS_MAXIMAS
            chamada["buscas_presumidas"] = True
        chamada["custo_usd"] = round(self.custo(chamada), 6)
        self.chamadas.append(chamada)
        if self.orcamento:
            self.orcamento.gasto += chamada["custo_usd"]
        medido = (len(sistema) + len(usuario) + len(json.dumps(esquema or {}, ensure_ascii=False))) / max(chamada["tokens_entrada"], 1)
        self.caracteres_por_token = min(self.caracteres_por_token, max(medido, 1.0))
        status = dados.get("status")
        if status == "incomplete":
            raise RespostaCortada(f"Resposta cortada por tamanho na etapa {etapa}; diminua --cena.")
        if status not in (None, "completed"):
            raise ErroModelo(f"A API do Google não concluiu a etapa {etapa} ({status}).")
        return dados, chamada

    @staticmethod
    def _texto(dados):
        blocos = [b for passo in dados.get("steps") or [] if passo.get("type") == "model_output"
                  for b in passo.get("content") or [] if b.get("type") == "text"]
        return blocos

    def json(self, sistema, usuario, esquema, etapa):
        dados, chamada = self._pedir(sistema, usuario, etapa, self.max_tokens, esquema=esquema,
                                     formato={"type": "text", "mime_type": "application/json", "schema": estrito(esquema)})
        blocos = self._texto(dados)
        if not blocos:
            raise Recusa(f"O modelo não devolveu resposta na etapa {etapa} (pedido {chamada['pedido']}).")
        try:
            return json.loads(blocos[0].get("text", ""))
        except ValueError:
            raise ErroModelo(f"A API do Google não devolveu JSON válido na etapa {etapa}.") from None

    def pesquisar(self, sistema, pergunta, etapa, max_tokens=4000):
        """Uma pergunta com a ferramenta oficial `google_search` e texto livre (pesquisa e esquema não são
        combinados aqui: o recurso é prévia). Devolve resposta, consultas executadas e fontes realmente citadas."""
        dados, chamada = self._pedir(sistema, pergunta, etapa, max_tokens, pesquisa=True)
        blocos = self._texto(dados)
        consultas = [q for passo in dados.get("steps") or [] if passo.get("type") == "google_search_call"
                     for q in (passo.get("arguments") or {}).get("queries") or []]
        fontes = {}
        for b in blocos:
            for nota in b.get("annotations") or []:
                if nota.get("type") == "url_citation" and nota.get("url"):
                    fontes.setdefault(nota["url"], {"titulo": nota.get("title") or nota["url"], "url": nota["url"]})
        return {"resposta": "\n".join(b.get("text", "") for b in blocos).strip(), "consultas": consultas,
                "fontes": list(fontes.values()), "buscas": chamada["buscas"], "custo_usd": chamada["custo_usd"]}


class Orcamento:
    """Teto de gasto em dólares para uma execução; interrompe antes da próxima chamada."""

    def __init__(self, teto):
        self.teto, self.gasto = teto, 0.0

    def conferir(self, proxima=0.0):
        """Para antes da chamada se o gasto já bateu o teto ou se o pior caso dela o ultrapassaria."""
        if self.gasto >= self.teto or self.gasto + proxima > self.teto:
            minimo = self.gasto + proxima
            raise TetoAtingido(
                f"Teto de gasto atingido: gasto de US$ {self.gasto:.4f} em US$ {self.teto:.2f}. A chamada seguinte "
                f"NÃO foi enviada: o pior caso dela é US$ {proxima:.4f}. Para enviá-la, o teto precisa ser de pelo "
                f"menos US$ {minimo:.2f} (reserva conservadora; o custo real costuma ser bem menor). "
                "O que já foi lido ficou salvo na pasta de saída.", minimo=minimo)


class Dupla:
    """Um modelo lê as cenas e outro julga os pares, com chamadas e teto em comum."""

    def __init__(self, leitor, juiz):
        self.leitor, self.juiz = leitor, juiz
        self.modelo = f"{leitor.modelo}+{juiz.modelo}"
        self.chamadas = []
        leitor.chamadas = juiz.chamadas = self.chamadas

    def verificar(self):
        self.leitor.verificar()
        self.juiz.verificar()

    def json(self, sistema, usuario, esquema, etapa):
        return (self.juiz if etapa.startswith("juiz") else self.leitor).json(sistema, usuario, esquema, etapa)


def criar_modelo(nome, pensar=False, contexto=16384, esforco="medium", juiz=None, teto=None):
    """`claude-*` usa a API da Anthropic; `gemini-*`, a do Google; qualquer outro nome, o Ollama local.
    Com `juiz`, a leitura usa `nome` e os julgamentos usam `juiz`."""
    if teto is not None and not 0 <= teto < float("inf"):
        raise ValueError("O teto de gasto precisa ser um número maior ou igual a zero.")
    orcamento = Orcamento(teto) if teto is not None else None  # teto 0 não envia nada

    def um(n):
        if n.startswith("claude-"):
            return Claude(n, esforco=esforco, orcamento=orcamento)
        if n.startswith("gemini-"):
            return Gemini(n, esforco=esforco, orcamento=orcamento)
        return Ollama(n, pensar=pensar, contexto=contexto)
    if juiz and juiz != nome:
        return Dupla(um(nome), um(juiz))
    return um(nome)
