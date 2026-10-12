"""Cliente Claude que envia no máximo UMA requisição ao provedor (execuções pagas autorizadas uma a uma).

Em relação a `coerencia.modelo.Claude` (que não é alterado): sem repetição por 429/5xx/rede, sem a verificação
prévia do modelo (`verificar` seria outra requisição), sem retomada automática no servidor (`fallbacks`) e com
`max_tokens` configurável por execução. O teto de gasto e o registro de custo e tokens são os do cliente original.

`max_tokens` limita a saída inteira, raciocínio incluído: com esforço alto, o raciocínio pode consumi-lo antes de o
JSON terminar (`stop_reason=max_tokens`, sem resposta aproveitável).
"""
import json

import coerencia.modelo as modelo_compartilhado
from coerencia.modelo import MAX_TOKENS, Claude, ErroModelo, tarifa
from coerencia2.auditoria import CARACTERES_POR_TOKEN


class UmaRequisicao(Claude):
    requisicoes = 0
    erro_original = None

    def __init__(self, *args, max_tokens=MAX_TOKENS, **kwargs):
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1000 <= max_tokens <= 64000:
            raise ValueError("max_tokens precisa ser um inteiro entre 1000 e 64000.")
        super().__init__(*args, **kwargs)
        self.max_tokens = max_tokens
        self.caracteres_por_token = min(self.caracteres_por_token, CARACTERES_POR_TOKEN)

    def verificar(self):
        """Não faz nada: a credencial é conferida pela própria requisição."""

    def custo_maximo(self, sistema, usuario, esquema, max_tokens):
        """Pior caso desta classe: um único envio, sem fallback nem repetição. Entrada à tarifa de escrita de cache
        (a mais cara) mais a saída inteira até `max_tokens`."""
        caracteres = len(sistema) + len(usuario) + len(json.dumps(esquema, ensure_ascii=False))
        tokens = int(caracteres / self.caracteres_por_token) + 1
        _, escrita, _, saida = tarifa(self.modelo)
        return (tokens * escrita + max_tokens * saida) / 1e6

    def json(self, sistema, usuario, esquema, etapa):
        # `Claude.json` lê `MAX_TOKENS` do módulo compartilhado; troca-se só durante esta chamada e restaura-se sempre.
        anterior = modelo_compartilhado.MAX_TOKENS
        modelo_compartilhado.MAX_TOKENS = self.max_tokens
        try:
            return super().json(sistema, usuario, esquema, etapa)
        finally:
            modelo_compartilhado.MAX_TOKENS = anterior

    def _enviar(self, criar, pedido, extra, etapa):
        pedido = {k: v for k, v in pedido.items() if k not in ("fallbacks", "betas")}
        self.espera = lambda segundos: None

        def uma(**parametros):
            if self.requisicoes:
                raise ErroModelo("Uma única requisição foi autorizada: nova tentativa bloqueada"
                                 + (f" (falha original: {self.erro_original})." if self.erro_original else "."))
            self.requisicoes += 1
            try:
                return criar(**parametros)
            except self.anthropic.APIError as erro:
                self.erro_original = f"{type(erro).__name__}"
                raise
        return super()._enviar(uma, pedido, extra, etapa)
