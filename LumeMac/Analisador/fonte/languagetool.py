"""Integração opcional exclusivamente com um servidor local, sem redirects."""
import json
from dataclasses import asdict
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from urllib.error import URLError

from .analysis import finding, narrative_masks


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def utf16_index(text, units):
    """A API Java usa unidades UTF-16; Python usa pontos de código."""
    return len(text.encode("utf-16-le")[:2*units].decode("utf-16-le", errors="ignore"))


def check(blocks, port=8081, protect_italics=True):
    if not 1 <= port <= 65535:
        raise ValueError("A porta do LanguageTool precisa estar entre 1 e 65535.")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    masks, _, _ = narrative_masks(blocks, protect_italics)
    results, warnings = [], []
    for block, text in zip(blocks, masks):
        if not text.strip():
            continue
        if len(text) > 18000:
            warnings.append(f"LanguageTool: parágrafo {block.number} excede 18 mil caracteres e não foi enviado ao servidor local.")
            continue
        data = urlencode({"text": text, "language": "pt-BR",
                          "disabledCategories": "STYLE,REDUNDANCY"}).encode()
        request = Request(f"http://127.0.0.1:{port}/v2/check", data=data,
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(request, timeout=30) as response:
                payload = json.load(response)
            matches = payload["matches"]
        except (URLError, TimeoutError, ValueError, KeyError) as exc:
            raise ValueError(f"Não foi possível concluir a análise pelo LanguageTool local na porta {port}. Confirme que o servidor está ativo. Nenhum relatório completo foi gerado.") from exc
        for match in matches:
            rule = match.get("rule", {})
            if rule.get("issueType") in {"style", "register", "locale-violation"}:
                continue
            if rule.get("category", {}).get("id") in {"STYLE", "REDUNDANCY"}:
                continue
            start = utf16_index(text, match["offset"])
            end = utf16_index(text, match["offset"] + match["length"])
            if not text[start:end].strip():
                continue
            results.append(asdict(finding(block, "Ortografia e gramática", "Verificar",
                start, end, match.get("message", "Verifique este trecho."),
                "LanguageTool local · " + rule.get("id", "regra"))))
    return results, warnings
