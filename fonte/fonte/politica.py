"""Política de destino editorial: o que interrompe o editor e o que impede o encerramento.

A severidade diz que tipo de problema é; o destino diz o que o editor faz com ele:

- `diagnostico`: fora da mesa; serve só para medir e melhorar o motor;
- `informacao`: observação recolhida, que não conta nem pede decisão;
- `pendencia`: entra na fila e pede decisão. Pendência não afirma que a regra é confiável:
  só que a classe ainda merece atenção editorial segundo a política atual.

`confidence` é evidência auxiliar. O destino vem da política versionada em
`data/politica.json`, calibrada com as decisões reais (`scripts/medir_precisao.py`): com 20
decisões ou mais, os dados prevalecem sobre o rótulo de confiança. O limiar de observação é um
critério de não-interrupção, não de qualidade da regra.

Plano: `.agent/plans/encerramento-editorial.md`.
"""
from functools import lru_cache
import json
from pathlib import Path

DESTINOS = ("diagnostico", "informacao", "pendencia")
SEVERIDADES_DE_ERRO = {"confirmed_error", "probable_error"}


@lru_cache(maxsize=1)
def politica():
    return json.loads((Path(__file__).with_name("data") / "politica.json").read_text(encoding="utf-8"))


def classe(ocorrencia):
    """Regra do alerta; o LanguageTool separa ortografia de gramática, que se comportam diferente.
    Mesma chave usada por `scripts/medir_precisao.py`."""
    fonte = ocorrencia.get("source") or ""
    if fonte.startswith("LanguageTool"):
        return "languagetool:ortografia" if "MORFOLOGIK" in fonte or "SPELLING" in fonte else "languagetool:gramatica"
    # A Auditoria mede-se por categoria (audit_crase, audit_referencia…), não pela regra comum.
    if ocorrencia.get("rule") == "auditoria_ia" and ocorrencia.get("category_code"):
        return ocorrencia["category_code"]
    return ocorrencia.get("rule") or ocorrencia.get("category_code") or ocorrencia.get("category") or "desconhecida"


def medicao(ocorrencia):
    """(decisões, precisão) medidos para a classe e a confiança, ou None."""
    dado = politica()["medicoes"].get(f"{classe(ocorrencia)}|{ocorrencia.get('confidence')}")
    return (dado["decisoes"], dado["precisao"]) if dado else None


def destino(ocorrencia):
    regras = politica()["limiares"]
    auditoria = ocorrencia.get("rule") == "auditoria_ia"
    # Auditoria = controle de qualidade: confiança baixa nunca chega à mesa.
    if auditoria and ocorrencia.get("confidence") == "baixa":
        return "diagnostico"
    medido = medicao(ocorrencia)
    if medido and medido[0] >= regras["minimo_decisoes"]:
        return "informacao" if medido[1] < regras["observacao_precisao"] else "pendencia"
    if auditoria:
        inicial = politica().get("auditoria", {})
        return inicial.get("destino_inicial", {}).get(classe(ocorrencia), inicial.get("padrao", "diagnostico"))
    # Sem amostra suficiente, o rótulo é a única evidência: confiança baixa não interrompe.
    return "informacao" if ocorrencia.get("confidence") == "baixa" else "pendencia"


def impeditivo(ocorrencia, destino_atual):
    """As três condições juntas; precisão alta sozinha nunca basta."""
    regras = politica()["limiares"]
    medido = medicao(ocorrencia)
    if ocorrencia.get("rule") == "auditoria_ia" and classe(ocorrencia) not in politica()["natureza_objetiva"]:
        return False  # a Auditoria não torna nada impeditivo por conta própria
    return bool(destino_atual == "pendencia" and medido
                and medido[0] >= regras["minimo_decisoes"] and medido[1] >= regras["impeditivo_precisao"]
                and classe(ocorrencia) in politica()["natureza_objetiva"]
                and ocorrencia.get("severity") in SEVERIDADES_DE_ERRO)


def aplicar(ocorrencias):
    """Marca destino e impedimento. Devolve (mesa, diagnóstico): o diagnóstico não vai para a mesa.
    IDs, trechos e severidades não mudam, então as decisões antigas continuam valendo."""
    mesa, diagnostico = [], []
    for item in ocorrencias:
        alvo = destino(item)
        item.update(destino=alvo, impeditivo=impeditivo(item, alvo))
        (diagnostico if alvo == "diagnostico" else mesa).append(item)
    return mesa, diagnostico
