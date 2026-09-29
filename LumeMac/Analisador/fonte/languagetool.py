"""Corretor gramatical LanguageTool, sempre local (127.0.0.1), sem redirects.

O motor pode iniciar um LanguageTool embutido (pasta com o servidor e Java) ou
usar um servidor já ativo. O texto das falas é enviado, porque grafia e
concordância também valem ali; regras de estilo e registro ficam de fora para
não formalizar a voz. Itálicos marcados como pensamento não recebem alertas de
grafia (estrangeirismos). Nada é enviado para fora do computador.
"""
from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from urllib.error import URLError

from .analysis import finding
from .settings import validate

SERVER_JAR = "languagetool-server.jar"
IGNORED_ISSUES = {"style", "register", "locale-violation"}
IGNORED_CATEGORIES = {"STYLE", "REDUNDANCY", "COLLOQUIALISMS", "REGIONALISMS", "FORMAL"}
SENTENCE_END = set(".!?…\"“”«»—–")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def utf16_index(text, units):
    """A API Java usa unidades UTF-16; Python usa pontos de código."""
    return len(text.encode("utf-16-le")[:2*units].decode("utf-16-le", errors="ignore"))


def proper_names(blocks, settings):
    """Palavras com inicial maiúscula fora do início de frase em algum ponto do
    texto são tratadas como nomes; o corretor não aponta sua grafia."""
    names = {word.casefold() for entry in settings["ignored_names"] for word in entry.split()}
    for block in blocks:
        if block.heading:
            continue
        for match in re.finditer(r"[A-ZÀ-ÖØ-Þ][^\W\d_]+", block.text):
            before = block.text[:match.start()].rstrip()
            if before and before[-1] not in SENTENCE_END and before[-1] != ":":
                names.add(match[0].casefold())
    return names


def check(blocks, port=8081, protect_italics=True, settings=None):
    if not 1 <= port <= 65535:
        raise ValueError("A porta do LanguageTool precisa estar entre 1 e 65535.")
    settings = validate(settings or {})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    names = proper_names(blocks, settings)
    results, warnings = [], []
    for block in blocks:
        text = block.text
        if block.heading or not text.strip():
            continue
        if len(text) > 18000:
            warnings.append(f"LanguageTool: parágrafo {block.number} excede 18 mil caracteres e não foi enviado ao servidor local.")
            continue
        data = urlencode({"text": text, "language": "pt-BR",
                          "disabledCategories": ",".join(sorted(IGNORED_CATEGORIES))}).encode()
        request = Request(f"http://127.0.0.1:{port}/v2/check", data=data,
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(request, timeout=60) as response:
                payload = json.load(response)
            matches = payload["matches"]
        except (URLError, TimeoutError, ValueError, KeyError) as exc:
            raise ValueError(f"Não foi possível concluir a análise pelo LanguageTool local na porta {port}. Confirme que o servidor está ativo. Nenhum relatório completo foi gerado.") from exc
        italics = block.italic if protect_italics else ()
        for match in matches:
            rule = match.get("rule", {})
            if rule.get("issueType") in IGNORED_ISSUES or rule.get("category", {}).get("id") in IGNORED_CATEGORIES:
                continue
            start = utf16_index(text, match["offset"])
            end = utf16_index(text, match["offset"] + match["length"])
            excerpt = text[start:end]
            if not excerpt.strip():
                continue
            spelling = rule.get("issueType") == "misspelling" or rule.get("category", {}).get("id") == "TYPOS"
            # Inciso após travessão (“— Vamos? — perguntou ela.”) não é início de frase.
            if rule.get("id") == "UPPERCASE_SENTENCE_START" and text[:start].rstrip().endswith(("—", "–")):
                continue
            if spelling and (excerpt.strip().casefold() in names
                             or any(s < end and start < e for s, e in italics)):
                continue
            replacements = [r.get("value") for r in match.get("replacements", []) if r.get("value")]
            item = asdict(finding(block, "Ortografia e gramática", "Verificar", start, end,
                                  match.get("message", "Verifique este trecho."),
                                  "LanguageTool local · " + rule.get("id", "regra")))
            item.update(suggestion=replacements[0] if replacements else None, suggestion_kind="possible",
                        confidence="alta" if spelling else "média",
                        confidence_score=.9 if spelling else .75)
            results.append(item)
    return results, warnings


def home():
    """Pasta do LanguageTool embutido, se houver: variável de ambiente, pacote
    do motor (ao lado de runtime/) ou preparação local de desenvolvimento."""
    candidates = []
    if os.environ.get("FONTE_LANGUAGETOOL"):
        candidates.append(Path(os.environ["FONTE_LANGUAGETOOL"]))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent.parent / "languagetool")
    candidates.append(Path(__file__).resolve().parents[1] / ".languagetool")
    return next((c for c in candidates if (c / SERVER_JAR).is_file()), None)


def java(root):
    bundled = root / "jre/bin/java"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return bundled
    if getattr(sys, "frozen", False):
        return None  # O pacote do motor não depende de Java instalado no sistema.
    if os.environ.get("JAVA_HOME") and (Path(os.environ["JAVA_HOME"]) / "bin/java").is_file():
        return Path(os.environ["JAVA_HOME"]) / "bin/java"
    found = shutil.which("java")
    return Path(found) if found else None


def available():
    root = home()
    return root is not None and java(root) is not None


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def ready(port):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(f"http://127.0.0.1:{port}/v2/languages", timeout=2) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


@contextmanager
def embedded(timeout=120):
    """Inicia o servidor embutido numa porta livre de 127.0.0.1 e o encerra ao sair."""
    root = home()
    executable = java(root) if root else None
    if executable is None:
        raise ValueError("O corretor gramatical embutido não foi encontrado neste motor.")
    port = free_port()
    command = [str(executable), "-Xms128m", "-Xmx1536m", "-Djava.awt.headless=true",
               "-cp", str(root / SERVER_JAR), "org.languagetool.server.HTTPServer", "--port", str(port)]
    # Sem --public, o LanguageTool aceita somente conexões locais. O registro vai
    # para um arquivo temporário: um pipe cheio poderia travar o servidor.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + timeout
            while not ready(port):
                if process.poll() is not None:
                    log.seek(0)
                    detail = log.read().decode("utf-8", "replace")[-600:]
                    raise ValueError("O corretor gramatical embutido não iniciou. " + detail.strip())
                if time.monotonic() > deadline:
                    raise ValueError("O corretor gramatical embutido não respondeu a tempo.")
                time.sleep(.25)
            yield port
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
