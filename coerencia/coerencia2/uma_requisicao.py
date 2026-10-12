"""Cliente Claude que envia no máximo UMA requisição ao provedor (execuções pagas autorizadas uma a uma).

Em relação a `coerencia.modelo.Claude` (que não é alterado): sem repetição por 429/5xx/rede, sem a verificação
prévia do modelo (`verificar` seria outra requisição) e sem retomada automática no servidor (`fallbacks`).
O teto de gasto e o registro de custo e tokens continuam os do cliente original.
"""
from coerencia.modelo import Claude, ErroModelo


class UmaRequisicao(Claude):
    requisicoes = 0
    erro_original = None

    def verificar(self):
        """Não faz nada: a credencial é conferida pela própria requisição."""

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
