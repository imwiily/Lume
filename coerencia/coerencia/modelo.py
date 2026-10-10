"""Clientes de modelo com a mesma interface: API do Claude (padrão) e Ollama local.

Ambos pedem respostas em JSON com esquema (saída estruturada) e registram tempo
e tokens de cada chamada em `chamadas`. Com a API do Claude, o texto das cenas
enviadas vai aos servidores da Anthropic; com o Ollama, nada sai do computador.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

LOCAIS = {"127.0.0.1", "localhost", "::1"}


class ErroModelo(Exception):
    pass


class Recusa(ErroModelo):
    """O modelo recusou o pedido (classificadores de segurança)."""


class RespostaCortada(ErroModelo):
    """A resposta atingiu `max_tokens` antes de terminar."""


class TetoAtingido(ErroModelo):
    """O teto de gasto da execução foi atingido antes da próxima chamada."""


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
# Referência: tabela da Anthropic em 25/09/2026; conferir antes de orçar.
PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
    # Faixa de prompts até 100 mil tokens; acima disso vale OFICIAL_LONGA.
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
# Contabilidade completa, por milhão: (entrada, escrita de cache 5 min, leitura de cache, saída).
# Haiku 5.5: a tarifa depende do tamanho do prompt (entrada + leituras e escritas de cache).
OFICIAL = {"claude-opus-5-5": (4.00, 5.00, 0.20, 20.00), "claude-sonnet-5-5": (2.00, 2.50, 0.10, 10.00),
           "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50)}
OFICIAL_LONGA = {"claude-haiku-5-5": (100_000, (0.50, 0.625, 0.05, 2.50))}
# Modelos que aceitam esforço e retomada automática em outro modelo quando o
# pedido é recusado pelos classificadores de segurança.
ATUAIS = {"claude-opus-5-5", "claude-sonnet-5-5"}
# Experimental: aceita esforço, mas não tem retomada automática (`fallbacks` seria recusado) e
# nunca pode ser respondido por outro modelo sem que isso apareça como erro.
EXPERIMENTAIS = {"claude-haiku-5-5"}


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
            opcoes = {"timeout": tempo_limite, "max_retries": 4}
            cliente = anthropic.Anthropic(api_key=chave, **opcoes) if chave else anthropic.Anthropic(**opcoes)
        self.cliente = cliente
        self.chamadas = []

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

    def completa(self):
        """Contabilidade completa (escrita de cache incluída): modelos experimentais e execuções
        com orçamento global. Fora disso o cálculo da versão estável fica como estava."""
        return self.modelo in EXPERIMENTAIS or isinstance(self.orcamento, OrcamentoGlobal)

    def tarifa(self, tokens_entrada):
        """(entrada, escrita de cache 5 min, leitura de cache, saída) por milhão, para um prompt desse
        tamanho. Tarifas da página de preços da Anthropic (conferida em 10/10/2026)."""
        limite, longa = OFICIAL_LONGA.get(self.modelo, (None, None))
        if limite and tokens_entrada > limite:
            return longa
        if self.modelo in OFICIAL:
            return OFICIAL[self.modelo]
        entrada, saida, cache = PRECOS.get(self.modelo, (0, 0, 0))
        return entrada, entrada * 1.25, cache, saida

    def custo(self, chamada):
        if self.completa() and (self.modelo in OFICIAL):
            entrada, escrita, leitura, saida = self.tarifa(chamada["tokens_entrada"])
            criacao = chamada.get("tokens_cache_criacao", 0)
            normal = chamada["tokens_entrada"] - chamada["tokens_cache"] - criacao
            return (normal * entrada + chamada["tokens_cache"] * leitura + criacao * escrita
                    + chamada["tokens_saida"] * saida) / 1e6
        entrada, saida, cache = PRECOS.get(self.modelo, (0, 0, 0))
        return ((chamada["tokens_entrada"] - chamada["tokens_cache"]) * entrada
                + chamada["tokens_cache"] * cache + chamada["tokens_saida"] * saida) / 1e6

    def custo_maximo(self, sistema, usuario, max_tokens):
        """Teto conservador de uma chamada, antes de enviá-la: 2,5 caracteres por token (o tokenizador
        novo gera ~30% mais), tudo cobrado como escrita de cache, e a saída inteira até `max_tokens`."""
        tokens = int((len(sistema) + len(usuario)) / 2.5) + 1
        _, escrita, _, saida = self.tarifa(tokens)
        return (tokens * escrita + max_tokens * saida) / 1e6

    def json(self, sistema, usuario, esquema, etapa):
        pedido = {
            "model": self.modelo, "max_tokens": 16000,
            # Prompt de sistema fixo: fica em cache entre chamadas quando atinge o tamanho mínimo.
            "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": usuario}],
            "output_config": {"format": {"type": "json_schema", "schema": estrito(esquema)}},
        }
        if self.modelo in ATUAIS:
            pedido["output_config"]["effort"] = self.esforco
            pedido.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            criar = self.cliente.beta.messages.create
        elif self.modelo in EXPERIMENTAIS:
            pedido["output_config"]["effort"] = self.esforco
            criar = self.cliente.messages.create
        else:
            criar = self.cliente.messages.create
        if self.orcamento:
            # Com contabilidade completa, confere também o pior caso da própria chamada.
            extra = self.custo_maximo(sistema, usuario, pedido["max_tokens"]) if self.completa() else 0
            self.orcamento.conferir(extra)
            if isinstance(self.orcamento, OrcamentoGlobal):
                self.orcamento.contexto = {"modelo_pedido": self.modelo, "esforco": self.esforco, "etapa": etapa,
                                           "custo_maximo_usd": round(extra, 6)}
        inicio = time.monotonic()
        try:
            resposta = criar(**pedido)
        except self.anthropic.AuthenticationError as erro:
            raise ErroModelo("Chave da API ausente ou inválida.") from erro
        except self.anthropic.RateLimitError as erro:
            raise ErroModelo("Limite de uso da API atingido. Tente mais tarde ou confira o limite de gasto no console.") from erro
        except self.anthropic.APIStatusError as erro:
            raise ErroModelo(f"A API recusou o pedido ({erro.status_code}): {erro.message}") from erro
        except self.anthropic.APIConnectionError as erro:
            raise ErroModelo("Sem conexão com a API da Anthropic.") from erro
        uso = resposta.usage
        cache = (getattr(uso, "cache_read_input_tokens", 0) or 0)
        entrada = (uso.input_tokens or 0) + cache + (getattr(uso, "cache_creation_input_tokens", 0) or 0)
        chamada = {"etapa": etapa, "segundos": round(time.monotonic() - inicio, 1), "tokens_entrada": entrada,
                   "tokens_cache": cache, "tokens_saida": uso.output_tokens or 0, "modelo_usado": resposta.model,
                   "pedido": getattr(resposta, "_request_id", None),
                   "tokens_cache_criacao": getattr(uso, "cache_creation_input_tokens", 0) or 0}
        chamada["custo_usd"] = round(self.custo(chamada), 6)
        self.chamadas.append(chamada)
        if self.orcamento:
            if isinstance(self.orcamento, OrcamentoGlobal):
                self.orcamento.contexto.update({k: chamada[k] for k in (
                    "modelo_usado", "pedido", "tokens_entrada", "tokens_cache", "tokens_cache_criacao",
                    "tokens_saida", "segundos")})
            self.orcamento.gasto += chamada["custo_usd"]
        if self.modelo in EXPERIMENTAIS and not str(resposta.model).startswith(self.modelo):
            raise ErroModelo(f"Pediu {self.modelo}, mas respondeu {resposta.model} (etapa {etapa}, pedido "
                             f"{chamada['pedido']}). Sem substituição silenciosa de modelo.")
        if resposta.stop_reason == "refusal":
            raise Recusa(f"O modelo recusou a etapa {etapa} (pedido {chamada['pedido']}).")
        if resposta.stop_reason == "max_tokens":
            raise RespostaCortada(f"Resposta cortada por tamanho na etapa {etapa}; diminua --cena.")
        texto = next((b.text for b in resposta.content if b.type == "text"), "")
        try:
            return json.loads(texto)
        except json.JSONDecodeError as erro:
            raise ErroModelo(f"A API não devolveu JSON válido na etapa {etapa}.") from erro


class Orcamento:
    """Teto de gasto em dólares para uma execução; interrompe antes da próxima chamada."""

    def __init__(self, teto):
        self.teto, self.gasto = teto, 0.0

    def conferir(self, proxima=0.0):
        """Para antes da chamada se o gasto já bateu o teto ou se o pior caso dela o ultrapassaria."""
        if self.gasto >= self.teto or self.gasto + proxima > self.teto:
            raise TetoAtingido(f"Teto de gasto atingido (US$ {self.gasto:.4f} de US$ {self.teto:.2f}). "
                             "O que já foi lido ficou salvo na pasta de saída.")


class OrcamentoGlobal(Orcamento):
    """Teto local da execução + limite acumulado entre execuções, guardado em arquivo (experimento).
    Cada chamada paga é registrada com o modelo que respondeu; antes de enviar, o pior caso da própria
    chamada precisa caber no que resta. Ativado só por LUME_ORCAMENTO_GLOBAL (arquivo) e _LIMITE."""

    def __init__(self, teto, arquivo, limite):
        super().__init__(teto if teto else float("inf"))
        self.arquivo, self.limite, self.contexto = Path(arquivo), float(limite), {}

    def _ler(self):
        try:
            return json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"limite_usd": self.limite, "gasto_usd": 0.0, "chamadas": []}

    def gasto_global(self):
        return self._ler()["gasto_usd"]

    @property
    def gasto(self):
        return self._gasto

    @gasto.setter
    def gasto(self, valor):
        delta = valor - getattr(self, "_gasto", 0.0)
        self._gasto = valor
        if delta > 0:
            dados = self._ler()
            dados["gasto_usd"] = round(dados["gasto_usd"] + delta, 6)
            dados["chamadas"].append({"custo_usd": round(delta, 6), **self.contexto})
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            self.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    def conferir(self, proxima=0.0):
        if self.gasto >= self.teto:
            raise TetoAtingido(f"Teto da execução atingido (US$ {self.gasto:.4f} de US$ {self.teto:.2f}).")
        restante = self.limite - self.gasto_global()
        if proxima > restante:
            raise TetoAtingido(f"Orçamento global do experimento: o pior caso desta chamada (US$ {proxima:.4f}) "
                               f"excede o que resta (US$ {restante:.4f} de US$ {self.limite:.2f}). Nada foi enviado.")


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
    """`claude-*` usa a API da Anthropic; qualquer outro nome, o Ollama local.
    Com `juiz`, a leitura usa `nome` e os julgamentos usam `juiz`."""
    orcamento = Orcamento(teto) if teto else None
    if os.environ.get("LUME_ORCAMENTO_GLOBAL"):
        orcamento = OrcamentoGlobal(teto, os.environ["LUME_ORCAMENTO_GLOBAL"],
                                    os.environ.get("LUME_ORCAMENTO_GLOBAL_LIMITE", "0.50"))

    def um(n):
        if n.startswith("claude-"):
            return Claude(n, esforco=esforco, orcamento=orcamento)
        return Ollama(n, pensar=pensar, contexto=contexto)
    if juiz and juiz != nome:
        return Dupla(um(nome), um(juiz))
    return um(nome)
