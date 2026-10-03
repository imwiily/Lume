"""Corretor gramatical LanguageTool, sempre local (127.0.0.1), sem redirects.

O motor pode iniciar um LanguageTool embutido (pasta com o servidor e Java) ou
usar um servidor já ativo. O texto das falas é enviado, porque grafia e
concordância também valem ali; regras de estilo e registro ficam de fora para
não formalizar a voz. Itálicos marcados como pensamento não recebem alertas de
grafia (estrangeirismos). Nada é enviado para fora do computador.
"""
from contextlib import contextmanager
from dataclasses import asdict
from collections import Counter
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

from .analysis import finding, forma_de_fala
from .lexicon import flags
from .settings import validate

SERVER_JAR = "languagetool-server.jar"
IGNORED_ISSUES = {"style", "register", "locale-violation"}
IGNORED_CATEGORIES = {"STYLE", "REDUNDANCY", "COLLOQUIALISMS", "REGIONALISMS", "FORMAL"}
SENTENCE_END = set(".!?…\"“”«»—–")
# Sugestões de estilo sobre a pontuação de falas (“Olá.” → “Olá!”, vírgula de despedida).
IGNORED_RULES = {"INTERJECTIONS_PUNTUATION", "REGARDS_COMMA"}
# Locuções de uso consagrado sem vírgulas internas (“Agora sim, …”).
LOCUCOES_SEM_VIRGULA = {"agora sim"}
# “Além de” + complemento (“além disso”, “além dele”, “além daquilo”, “além desse”…).
ALEM_DE = re.compile(r"\balém\s+d[^\W\d_]*", re.I)
# Pronomes e quantificadores que “além de” completa: “nada além disso” = “nada mais do que isso”.
# Os pospostos (“coisa alguma”, “livro algum”) também entram.
COMPLETADOS_POR_ALEM = {"nada", "ninguém", "algo", "alguém", "tudo", "mais", "nenhum", "nenhuma", "nenhuns",
                        "nenhumas", "algum", "alguma", "alguns", "algumas"}
NEGATIVOS = {"nenhum", "nenhuma", "nenhuns", "nenhumas"}
FIM_DE_ORACAO = re.compile(r"[,.;:!?…—–()\[\]\"“”«»]")
# Afirmação falsa das mensagens de VERB_COMMA_CONJUNCTION: o conector pode vir no meio da frase.
SO_NO_INICIO = re.compile(r",?\s*e só deve ser utilizada no início duma frase para efeitos de estilo")
PARTICIPIO = re.compile(r"\w+(?:ad|id)[oa]s", re.I)
# Onomatopeias e interjeições expressivas: letras repetidas, caixa-alta ou formas como “Humm”, “Hm”.
EXPRESSIVA = re.compile(r"(\w)\1\1|^(?:h+u*m+|h+a+m+|a+h+[mn]*|a+h+a+|h+[mn]+|hã+|u+é|u+h+|o+h+|a+i+)$", re.I)


def expressiva(palavra):
    """Letras repetidas (“Haaaa”), interjeição (“Humm”, “Hm”) ou onomatopeia em caixa-alta (“SHING”)."""
    return bool(EXPRESSIVA.search(palavra)) or (len(palavra) >= 3 and palavra.isalpha() and palavra.isupper())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def alem_integrado(text, start, end):
    """‘Além de’ como complemento dentro da oração, e não o conector ‘além disso’ (= ademais).

    “Não havia nada além disso”, “ninguém além dele”, “coisa alguma além daquilo”,
    “nenhum caderno além desse”: a palavra anterior, na mesma oração, é pronome ou
    quantificador que ‘além de’ completa, ou há ‘nenhum’ nas três palavras anteriores.
    Depois de conjunção, adjetivo, verbo ou pontuação, é o conector.
    """
    alem = ALEM_DE.search(text, start, end)
    if alem is None:
        return False
    oracao = FIM_DE_ORACAO.split(text[:alem.start()])[-1]
    palavras = [p.casefold() for p in re.findall(r"[^\W\d_]+", oracao)]
    return bool(palavras) and (palavras[-1] in COMPLETADOS_POR_ALEM or bool(NEGATIVOS & set(palavras[-3:])))


def utf16_index(text, units):
    """A API Java usa unidades UTF-16; Python usa pontos de código."""
    return len(text.encode("utf-16-le")[:2*units].decode("utf-16-le", errors="ignore"))


def proper_names(blocks, settings):
    """Palavras com inicial maiúscula fora do início de frase são tratadas como nomes;
    o corretor não aponta sua grafia. Também conta como nome a palavra que aparece mais
    de uma vez, sempre com inicial maiúscula (nome que só surge no início de frases ou
    falas). Devolve os nomes para a grafia e, mais exigente, para a maiúscula após vírgula."""
    names = {word.casefold() for entry in settings["ignored_names"] for word in entry.split()}
    capitalized, middle, lowercase = Counter(), Counter(), set()
    for block in blocks:
        if block.heading:
            continue
        for match in re.finditer(r"[^\W\d_]+", block.text):
            word = match[0]
            if not word[0].isupper():
                lowercase.add(word.casefold())
                continue
            if word.isupper() and len(word) > 1:
                continue
            capitalized[word.casefold()] += 1
            before = block.text[:match.start()].rstrip()
            if before and before[-1] not in SENTENCE_END and before[-1] != ":":
                middle[word.casefold()] += 1
    always = {w for w, n in capitalized.items() if n >= 2 and w not in lowercase}
    # Grafia: uma ocorrência no meio de frase basta. Maiúscula depois de vírgula: a
    # própria ocorrência apontada não prova que a palavra é um nome; exige outra.
    spelling = names | set(middle) | always
    after_comma = names | {w for w, n in middle.items() if n >= 2} | always
    return spelling, after_comma


def check(blocks, port=8081, protect_italics=True, settings=None, avancar=None):
    """`avancar(feitos, total)` é chamado ao longo da verificação, para o progresso na interface."""
    if not 1 <= port <= 65535:
        raise ValueError("A porta do LanguageTool precisa estar entre 1 e 65535.")
    settings = validate(settings or {})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    names, vocatives = proper_names(blocks, settings)
    results, warnings = [], []
    total = sum(1 for b in blocks if not b.heading and b.text.strip())
    passo, feitos = max(1, total // 200), 0
    for block in blocks:
        text = block.text
        if block.heading or not text.strip():
            continue
        feitos += 1
        if avancar and (feitos % passo == 0 or feitos == total):
            avancar(feitos, total)
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
            if rule.get("id") in IGNORED_RULES:
                continue
            antes, depois = text[:start].rstrip(), text[end:]
            palavra = excerpt.strip(" ,.;:!?…")
            # Espaço depois de reticências (“…Mais”) é escolha de estilo da fala.
            if rule.get("id") == "SENTENCE_WHITESPACE" and antes.endswith(("…", "...")):
                continue
            # Nome próprio depois de vírgula ou dois-pontos (vocativo, enumeração) mantém a maiúscula.
            if rule.get("id") == "UPPERCASE_AFTER_COMMA" and palavra.split()[-1].casefold() in vocatives:
                continue
            # Depois de dois-pontos a maiúscula é legítima para nomes, citações e falas.
            if rule.get("id") == "UPPERCASE_AFTER_COMMA" and excerpt.lstrip().startswith(":"):
                continue
            # “Quero todos alinhados”: particípio usado como adjetivo, não substantivo.
            if rule.get("id") == "TODOS_FOLLOWED_BY_NOUN_PLURAL" and PARTICIPIO.fullmatch(palavra.split()[-1]):
                continue
            # “A chuva continua caindo”: verbo seguido de gerúndio, não o adjetivo acentuado.
            if rule.get("id") == "LP_PARONYMS" and re.match(r"\s+[^\W\d_]+ndo\b", depois):
                continue
            if rule.get("id") == "VERB_COMMA_CONJUNCTION" and palavra.casefold() in LOCUCOES_SEM_VIRGULA:
                continue
            if rule.get("id") == "VERB_COMMA_CONJUNCTION" and alem_integrado(text, start, end):
                continue
            # Onomatopeia reduplicada (“Au au”): palavra repetida fora do léxico.
            if rule.get("id") == "PORTUGUESE_WORD_REPEAT_RULE" and palavra and not flags(palavra.split()[0]):
                continue
            # Onomatopeias, interjeições e palavras cortadas na fala (“proí…”) não são erros de grafia.
            sozinha = re.fullmatch(r"[—–\s]*\w+[!?]+[\s.…]*", text) is not None  # “Fwoosh!” num parágrafo
            if spelling and (expressiva(palavra) or sozinha or depois.startswith(("…", "...", "-", "—"))):
                continue
            # “— … — respondeu a doutora”: sujeito posposto ao verbo de fala, sem crase.
            if rule.get("id") == "CRASE_CONFUSION" and forma_de_fala(excerpt.split()[0]):
                continue
            # Inciso após travessão (“— Vamos? — perguntou ela.”) não é início de frase.
            if rule.get("id") == "UPPERCASE_SENTENCE_START" and text[:start].rstrip().endswith(("—", "–")):
                continue
            if spelling and (excerpt.strip().casefold() in names
                             or any(s < end and start < e for s, e in italics)):
                continue
            replacements = [r.get("value") for r in match.get("replacements", []) if r.get("value")]
            message = match.get("message", "Verifique este trecho.")
            if rule.get("id") == "VERB_COMMA_CONJUNCTION" and SO_NO_INICIO.search(message):
                message = ("Quando funciona como conector, a expressão costuma ficar entre vírgulas, inclusive no meio "
                           "da frase. Se ela integra a oração, sem valor de conector, a vírgula não se aplica.")
            item = asdict(finding(block, "Ortografia e gramática", "Verificar", start, end, message,
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
