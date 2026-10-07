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

from .analysis import explicar, finding, forma_de_fala
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


# Mensagens do LanguageTool em linguagem do dia a dia (explicacoes-simples): regra → (texto, termo).
# ‘{w}’ é o trecho marcado; ‘{s}’, a primeira sugestão, e [[…]] some quando não há sugestão. Famílias de
# regras casam pelo prefixo.
CRASE = ("[[O corretor espera ‘{s}’ aqui. ]]O acento grave (à) aparece quando se juntam o ‘a’ que a palavra "
         "anterior pede (ir a, chegar a) e o ‘a’ antes de palavra feminina.", "crase")
PALAVRAS_PARECIDAS = ("Pode haver troca de palavras parecidas[[: talvez aqui seja ‘{s}’, e não ‘{w}’]]. Confira "
                      "pelo sentido.", "palavras parecidas (parônimos)")
ESPACO = ("Parece faltar ou sobrar um espaço junto da pontuação.", "espaço e pontuação")
SIMPLES = {
    "MORFOLOGIK_RULE_PT_BR": ("O corretor não conhece a palavra ‘{w}’ escrita assim[[; talvez seja ‘{s}’]]. Se for nome, termo "
                              "da obra ou palavra estrangeira, está certo.", "ortografia"),
    "PT_MULTITOKEN_SPELLING": ("O corretor não conhece ‘{w}’ escrito assim[[; talvez seja ‘{s}’]].", "ortografia"),
    "VERB_COMMA_CONJUNCTION": ("Expressões que ligam ideias (como ‘além disso’, ‘no entanto’, ‘por isso’) costumam "
                               "ficar entre vírgulas.", "vírgula com conectores"),
    "ALTERNATIVE_CONJUNCTIONS_COMMA": ("Em pares como ‘ora… ora’, ‘quer… quer’ e ‘seja… seja’, as partes costumam "
                                       "ser separadas por vírgula.", "vírgula com conjunções alternativas"),
    "DASH_ENUMERATION_SPACE_RULE": ("Depois do travessão que abre uma fala costuma vir um espaço (— Vamos.).",
                                    "travessão de diálogo"),
    "GENERAL_NUMBER_AGREEMENT_ERRORS": ("Uma palavra parece estar no singular e outra no plural, quando deveriam "
                                        "combinar (como em ‘as casa’).", "concordância de número"),
    "GENERAL_GENDER_AGREEMENT_ERRORS": ("Uma palavra parece estar no masculino e outra no feminino, quando deveriam "
                                        "combinar (como em ‘a casa bonito’).", "concordância de gênero"),
    "GENERAL_GENDER_NUMBER_AGREEMENT_ERRORS": ("As palavras deste trecho parecem não combinar em masculino/feminino "
                                               "ou singular/plural.", "concordância nominal"),
    "ERRO_DE_CONCORDNCIA_DO_GÉNERO": ("As palavras deste trecho parecem não combinar em masculino e feminino.",
                                      "concordância de gênero"),
    "GENERAL_VERB_AGREEMENT_ERRORS": ("O verbo parece não combinar com quem faz a ação (como em ‘eles foi’).",
                                      "concordância verbal"),
    "NON_IMPERSONAL_VERBS": ("Verbos como ‘faltar’ e ‘sobrar’ combinam com o que falta ou sobra (‘faltam dois "
                             "dias’).", "concordância verbal"),
    "LINKING_VERB_PREDICATE_AGREEMENT": ("Em frases como ‘eles estão cansados’, a palavra que descreve acompanha o "
                                         "singular ou o plural do verbo; aqui parece não acompanhar.",
                                         "concordância do predicativo"),
    "UPPERCASE_SENTENCE_START": ("A frase parece começar com letra minúscula.", "maiúscula no início da frase"),
    "UPPERCASE_AFTER_COMMA": ("Depois de vírgula ou ponto e vírgula a frase continua; a palavra seguinte vai com "
                              "letra minúscula, a não ser que seja um nome.", "minúscula depois de vírgula"),
    "ACENTUAÇÃO_VOGAL_ÊNCLISE": ("Quando o pronome vem depois do verbo com hífen (‘vendê-lo’, ‘pô-la’), o verbo "
                                 "pode precisar de acento. Confira o acento de ‘{w}’.",
                                 "acentuação com pronome depois do verbo (ênclise)"),
    "FRAGMENT_TWO_ARTICLES": ("Aparecem duas palavras como ‘o’, ‘a’ ou ‘um’ em sequência; pode ter sobrado ou "
                              "faltado uma palavra.", "possível palavra faltando ou sobrando"),
    "SPACE_AFTER_PUNCTUATION": ("Falta um espaço depois da pontuação.", "espaço e pontuação"),
    "SENTENCE_WHITESPACE": ("Falta um espaço entre o fim de uma frase e o começo da outra.", "espaço e pontuação"),
    "COMMA_PARENTHESIS_WHITESPACE": ESPACO,
    "PARENTESESE_AND_QUOTES_SPACING": ESPACO,
    "DOUBLE_PUNCTUATION": ("Há dois sinais de pontuação seguidos, como ‘,,’ ou ‘.,’.", "pontuação duplicada"),
    "UNPAIRED_BRACKETS": ("Uma aspa ou um parêntese abre e não fecha, ou fecha sem ter aberto.", "sinal sem par"),
    "CRASE_CONFUSION": CRASE,
    "IR_CONTRACTION_NOUN": ("Depois de verbos como ‘ir’ e ‘chegar’, o ‘a’ costuma se juntar ao artigo: ‘ao’ (ir ao "
                            "mercado) ou ‘à’ (ir à praia).", "contração com preposição"),
    "CONTRACOES_OBRIGATORIAS": ("Talvez aqui as palavras devam se juntar[[: ‘{s}’]].", "contração"),
    "AS_VEZES": ("‘Às vezes’, no sentido de ‘de vez em quando’, leva acento grave.", "crase em locução"),
    "ATOA": ("‘À toa’ (sem motivo, sem rumo) se escreve separado e com acento grave.", "locução ‘à toa’"),
    "CONFUSÃO_À_HÁ": ("‘Há’, com h, indica tempo que já passou (‘há dois dias’); ‘a’ e ‘à’ indicam lugar, direção "
                      "ou tempo que ainda vem (‘daqui a dois dias’).", "há / a / à"),
    "AUXILIARY_VERB_INFINITIVE": ("Depois de verbos como ‘poder’, ‘dever’ e ‘querer’, o verbo seguinte costuma "
                                  "terminar em -r (‘pode sair’). Se não for o caso, talvez falte uma vírgula.",
                                  "verbo auxiliar + infinitivo"),
    "CP_AI_AÍ": ("‘Aí’ (lugar ou ‘então’) leva acento; ‘ai’, sem acento, é o gemido de dor.", "aí / ai"),
    "AO90_CARDINAL_POINTS_CASING": ("Norte, sul, leste e oeste vão com letra minúscula, a não ser quando dão nome a "
                                    "uma região (o Nordeste).", "pontos cardeais (Acordo Ortográfico)"),
    "AO90_WEEKDAYS_CASING": ("Dias da semana e meses vão com letra minúscula.", "Acordo Ortográfico"),
    "PT_COMPOUNDS_POST_REFORM": ("Esta palavra composta se escreve com hífen[[: ‘{s}’]].", "hífen em palavra composta"),
    "PT_COLOUR_HYPHENATION": ("Cores compostas, como ‘azul-escuro’, se escrevem com hífen.", "hífen em cores"),
    "COLOCACAO_PRONOMINAL_COM_ATRATOR": ("Quando antes do verbo vem uma palavra como ‘não’, ‘nunca’, ‘que’ ou ‘já’, "
                                         "o pronome costuma ir antes do verbo (‘não me disse’).",
                                         "colocação pronominal (próclise)"),
    "CONFUSÃO_AONDE_ONDE": ("‘Aonde’ é para movimento (aonde você vai?); ‘onde’, para lugar parado (onde você "
                            "está?).", "onde / aonde"),
    "NADA_HAVER": ("A expressão é ‘nada a ver’ (sem relação), sem o verbo haver.", "a ver / haver"),
    "MAU_MAL_CONFUSION": ("‘Mal’ é o contrário de ‘bem’; ‘mau’ é o contrário de ‘bom’.", "mal / mau"),
    "TRAZ_TRÁS": ("‘Traz’ é do verbo trazer (ela traz); ‘trás’ é posição (para trás).", "traz / trás"),
    "ASSISTIR_VER": ("No sentido de ver (um filme, uma luta), ‘assistir’ pede ‘a’: assistir ao filme.",
                     "regência de ‘assistir’"),
    "PHRASAL_VERB_COM": ("Este verbo normalmente não vem acompanhado de ‘com’.", "regência"),
    "CONFUSÃO": PALAVRAS_PARECIDAS,
    "CONFUSION": PALAVRAS_PARECIDAS,
    "CONFUSAO": PALAVRAS_PARECIDAS,
    "HOMONYM": PALAVRAS_PARECIDAS,
}
# Mensagens próprias do corretor que acrescentam o sentido de cada forma.
GENERICAS = {"Possível confusão de termos.", "Possível erro.", "Confira."}


def simples(rule_id, palavra, sugestao, mensagem, categoria):
    """(texto, termo) da explicação: a regra mapeada (a mais longa que casar pelo prefixo) ou, sem
    mapa, a mensagem do próprio corretor com o nome da categoria."""
    if rule_id == "POR_QUE_PORQUE" and palavra.casefold() in {"porque", "por que"}:
        if palavra.casefold() == "porque":
            return ("‘Porque’, junto, explica um motivo (saí porque choveu). Se aqui for uma pergunta, "
                    "escreve-se separado: ‘por que’.", "por que / porque")
        return ("‘Por que’, separado, serve para perguntar. Se aqui for a explicação de um motivo, escreve-se "
                "junto: ‘porque’.", "por que / porque")
    chave = max((k for k in SIMPLES if rule_id == k or rule_id.startswith(k + "_")), key=len, default=None)
    if chave == "CRASE_CONFUSION" and "à" in palavra.casefold() and sugestao and "à" not in sugestao.casefold():
        return (f"O corretor espera ‘{sugestao}’ aqui, sem acento. Antes de verbo (‘a mexer’) ou de palavra "
                "masculina (‘a pé’), o ‘a’ não leva acento grave.", "crase")
    if chave is None:
        return mensagem, (categoria or "regra do corretor").lower().rstrip(".")
    texto, termo = SIMPLES[chave]
    texto = re.sub(r"\[\[(.*?)\]\]", r"\1" if sugestao else "", texto).format(w=palavra, s=sugestao)
    if chave == "HOMONYM" and mensagem not in GENERICAS:
        texto += " " + mensagem
    return texto, termo


def expressiva(palavra):
    """Letras repetidas (“Haaaa”), interjeição (“Humm”, “Hm”) ou onomatopeia em caixa-alta (“SHING”)."""
    return bool(EXPRESSIVA.search(palavra)) or (len(palavra) >= 3 and palavra.isalpha() and palavra.isupper())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def alem_integrado(text, start, end):
    """‘Além de’ como complemento dentro da oração, e não o conector ‘além disso’ (= ademais).

    “Não sobrou nada além disso”, “ninguém além dele”, “coisa alguma além daquilo”,
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


def distance(a, b):
    """Edições entre duas grafias (troca de letras vizinhas conta uma), sem acentos, maiúsculas e espaços."""
    import unicodedata
    def plain(x):
        x = unicodedata.normalize("NFD", x.casefold().replace(" ", "").replace("-", ""))
        return "".join(c for c in x if not unicodedata.combining(c))
    a, b = plain(a), plain(b)
    previous, row = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            current[j] = min(row[j] + 1, current[j - 1] + 1, row[j - 1] + (a[i - 1] != b[j - 1]))
            if previous is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], previous[j - 2] + 1)
        previous, row = row, current
    return row[-1]


def utf16_index(text, units):
    """A API Java usa unidades UTF-16; Python usa pontos de código."""
    return len(text.encode("utf-16-le")[:2*units].decode("utf-16-le", errors="ignore"))


# Linha de créditos, assinatura ou rótulo: até quatro palavras, todas com inicial maiúscula
# (partículas de nome à parte), sem pontuação (“Ilustração”, “Talvren Mox”).
CREDITOS = re.compile(r"[^\W\d_]+(?:\s+(?:de|da|do|dos|das|e|[^\W\d_]+)){0,3}")
PARTICULAS = {"de", "da", "do", "dos", "das", "e"}


def credit_line(text):
    text = text.strip()
    if not CREDITOS.fullmatch(text):
        return False
    return all(w[0].isupper() for w in text.split() if w not in PARTICULAS)


def with_number_variants(names):
    """Um nome da obra também vale no plural ou no singular (“Kirvane” e “Kirvanes”)."""
    out = set(names)
    for name in names:
        out.update({name + "s", name + "es"})
        if name.endswith("es"):
            out.add(name[:-2])
        if name.endswith("s"):
            out.add(name[:-1])
    return out


def proper_names(blocks, settings):
    """Palavras com inicial maiúscula fora do início de frase são tratadas como nomes;
    o corretor não aponta sua grafia. Também conta como nome a palavra que aparece mais
    de uma vez, sempre com inicial maiúscula (nome que só surge no início de frases ou
    falas), a de uma linha de créditos e o plural ou singular de um nome já reconhecido.
    Devolve os nomes para a grafia e, mais exigente, para a maiúscula após vírgula."""
    names = {word.casefold() for entry in settings["ignored_names"] for word in entry.split()}
    capitalized, middle, lowercase, credits = Counter(), Counter(), set(), set()
    for block in blocks:
        if block.heading:
            continue
        if credit_line(block.text):
            credits.update(w.casefold() for w in block.text.split() if w not in PARTICULAS)
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
    spelling = with_number_variants(names | set(middle) | always | credits)
    after_comma = names | {w for w, n in middle.items() if n >= 2} | always
    return spelling, after_comma


def recurring_unknown(blocks):
    """Palavras fora do léxico que se repetem (três vezes ou mais) com a mesma grafia: podem ser
    termos da obra (espécies, lugares, poderes). Não deixam de ser conferidas; perdem confiança."""
    counts = Counter()
    for block in blocks:
        if not block.heading:
            counts.update(w.casefold() for w in re.findall(r"[^\W\d_]+", block.text) if not flags(w))
    return {w for w, n in counts.items() if n >= 3}


def check(blocks, port=8081, protect_italics=True, settings=None, avancar=None):
    """`avancar(feitos, total)` é chamado ao longo da verificação, para o progresso na interface."""
    if not 1 <= port <= 65535:
        raise ValueError("A porta do LanguageTool precisa estar entre 1 e 65535.")
    settings = validate(settings or {})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    names, vocatives = proper_names(blocks, settings)
    recurring = recurring_unknown(blocks)
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
            # “os passos do lobo correndo cessam”: o gerúndio descreve o nome; não é o auxiliar que pede infinitivo.
            if rule.get("id") == "AUXILIARY_VERB_INFINITIVE" and palavra.split()[0].casefold().endswith("ndo"):
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
            texto, termo = simples(rule.get("id", ""), palavra, replacements[0] if replacements else "", message,
                                   rule.get("category", {}).get("name"))
            if rule.get("id") == "VERB_COMMA_CONJUNCTION" and SO_NO_INICIO.search(message):
                texto = ("Quando a expressão funciona como conector (como ‘além disso’, ligando ideias), costuma "
                         "ficar entre vírgulas, mesmo no meio da frase. Se ela integra a oração, sem ligar ideias, "
                         "a vírgula não se aplica.")
            item = asdict(finding(block, "Ortografia e gramática", "Verificar", start, end, explicar(texto, termo),
                                  "LanguageTool local · " + rule.get("id", "regra")))
            item.update(suggestion=replacements[0] if replacements else None, suggestion_kind="possible",
                        confidence="alta" if spelling else "média",
                        confidence_score=.9 if spelling else .75)
            # Termo desconhecido e recorrente: pode ser vocabulário da obra; a sugestão do corretor
            # (uma palavra comum parecida) não é aceita como certa.
            # Sugestão a duas letras ou mais da palavra (“taser” → “fazer”): erro de digitação costuma ficar a
            # uma letra; palavra estrangeira ou termo da obra, não. Continua visível, com confiança baixa.
            if (spelling and replacements and palavra.casefold() not in recurring
                    and min(distance(palavra, r) for r in replacements[:3]) >= 2):
                item.update(confidence="baixa", confidence_score=.4,
                            reason=explicar(texto + "\n\nA sugestão do corretor é bem diferente da palavra; pode ser "
                                            "palavra estrangeira ou termo da obra. Palavras estrangeiras costumam ir em "
                                            "itálico, e o Lume não aponta a grafia de itálicos.", termo))
            if spelling and palavra.casefold() in recurring:
                item.update(confidence="baixa", confidence_score=.4,
                            reason=explicar(texto + "\n\nA palavra aparece várias vezes escrita do mesmo jeito e pode "
                                            "ser um termo da obra; se for, inclua-a em Nomes aceitos nos ajustes da "
                                            "leitura.", termo))
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
