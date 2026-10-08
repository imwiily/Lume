"""Segmentação entre fala e narração (núcleo compartilhado; estabilização, Fase 4).

Só estrutura: onde começa e termina cada fala, pensamento ou narração, pelas marcações escolhidas
(travessão, hífen de diálogo, aspas, itálico). Não infere voz nem pensamento implícito e não
julga se a pontuação do diálogo está certa; as regras fazem isso com estas informações.

Representação: o papel de cada caractere do parágrafo (`narracao`, `dialogo`, `pensamento`,
`separador` para o próprio sinal, `titulo`), na posição original; `spans` agrupa os trechos.

Peças compartilhadas:
- `percorrer_aspas`: o estado das aspas ao longo dos parágrafos (abertura, dentro, fechamento,
  reinício depois de aspas sem fechamento, avisos);
- `marcar_travessoes`: falas e incisos por travessão ou hífen de diálogo;
- `abre_fala` e `termina_em_travessao`: verificações locais usadas por outras regras.

Duas leituras convivem e são preservadas de propósito (diferenças registradas no plano):
`classify`, a atual (fala por linha, hífen de diálogo, papel das aspas configurável), e
`narrative_masks` em `analysis.py`, a antiga (só travessão, só no início do parágrafo; aspas
sempre como fala; a aspa que reabre a mesma fala no início de um parágrafo continua a fala).
"""
import re

from .settings import validate

TRAVESSOES = "—–"
# Abertura → fechamento; e o inverso, fechamento → abertura.
ABRE_ASPAS = {'“': '”', '«': '»', '"': '"', '‘': '’'}
FECHA_ASPAS = {'”': '“', '»': '«', '"': '"', '’': '‘'}
# Parágrafo que abre com travessão ou hífen seguido de espaço (critério estrito, com espaço).
ABRE_FALA_COM_ESPACO = re.compile(r"^\s*[-–—]\s")


def abre_fala(texto, exige_espaco=False):
    """O texto (linha ou parágrafo) abre com travessão ou com hífen de diálogo (“- Vamos.”).
    Com `exige_espaco`, só conta o sinal seguido de espaço (“—Vamos” não conta)."""
    if exige_espaco:
        return bool(ABRE_FALA_COM_ESPACO.match(texto))
    return texto.lstrip().startswith(('—', '–', '- '))


def termina_em_travessao(prefixo):
    """O texto antes de um ponto termina em travessão: o que vem depois é inciso ou fala."""
    return prefixo.rstrip().endswith(("—", "–"))


def percorrer_aspas(blocks, repete_abertura):
    """Estado das aspas em cada parágrafo, atravessando parágrafos.

    Devolve, por parágrafo, `(marcas, fechamentos)`: `marcas[i]` é None, `abre`, `dentro`,
    `fecha` ou `repetida` (a aspa que reabre a mesma fala no início do parágrafo, só com
    `repete_abertura`); `fechamentos` são as posições das aspas que fecham. Também devolve os
    avisos. Um título encerra qualquer aspa aberta. Um parágrafo que começa com um par completo
    reinicia a leitura (aspas anteriores sem fechamento)."""
    closer, resultado, avisos = None, [], []
    for block in blocks:
        text = block.text
        marcas, fechamentos = [None] * len(text), []
        if block.heading:
            if closer:
                avisos.append(f"Aspas possivelmente abertas antes do título no parágrafo {block.number}.")
            closer = None
            resultado.append((marcas, fechamentos))
            continue
        stripped = text.lstrip()
        opener = FECHA_ASPAS.get(closer)
        if closer and opener and stripped.startswith(opener) and closer in stripped[1:]:
            avisos.append(f"Aspas anteriores possivelmente sem fechamento: a separação foi reiniciada no parágrafo "
                          f"{block.number}. Confira o trecho anterior.")
            closer = None
        for i, char in enumerate(text):
            if repete_abertura and closer and i == len(text) - len(stripped) and char == opener:
                marcas[i] = 'repetida'
                continue
            if closer:
                marcas[i] = 'dentro'
                if char == closer:
                    marcas[i] = 'fecha'
                    closer = None
                    fechamentos.append(i)
            elif char in ABRE_ASPAS:
                closer = ABRE_ASPAS[char]
                marcas[i] = 'abre'
        resultado.append((marcas, fechamentos))
    if closer:
        avisos.append("Há aspas sem fechamento até o fim do texto; isso pode ocultar trechos da análise narrativa.")
    return resultado, avisos


def marcar_travessoes(text, roles, por_linha=True, hifen=True):
    """Marca em `roles` as falas abertas por travessão (`dialogo`) e os sinais (`separador`).

    Cada sinal alterna fala e inciso narrativo. Com `hifen`, o hífen seguido de espaço também abre
    fala (“- Vamos.”) e, no meio da linha, só o hífen isolado por espaços separa, nunca o de palavra
    composta (“bem-vindo”). Com `por_linha`, cada linha (quebra de linha manual) vale como início
    possível de fala, e a fala que fica aberta continua na linha seguinte só se ela a fechar
    (“… — disse ela.”); sem `por_linha`, o parágrafo é uma linha só."""
    base, spoken, hyphen = 0, False, False

    def separator(line, j):
        return line[j] in TRAVESSOES or (hyphen and line[j] == '-' and (j == 0 or line[j-1].isspace())
                                         and (j + 1 == len(line) or line[j+1].isspace()))
    for line in text.split('\n') if por_linha else [text]:
        if line.strip():
            opens = line.lstrip().startswith(('—', '–')) or (hifen and line.lstrip().startswith('- '))
            if opens:
                spoken, hyphen = False, hifen and line.lstrip().startswith('- ')
            elif not any(separator(line, j) for j in range(len(line))):
                spoken = False
            for j in range(len(line)):
                if separator(line, j) and (spoken or opens):
                    spoken = not spoken
                    roles[base + j] = 'separador'
                elif spoken:
                    roles[base + j] = 'dialogo'
        base += len(line) + 1
    return roles


def classify(blocks, settings):
    settings = validate(settings)
    aspas = percorrer_aspas(blocks, repete_abertura=False)[0] if settings['quotes_role'] != 'narracao' else None
    result = []
    for k, block in enumerate(blocks):
        text = block.text
        if block.heading:
            result.append(['titulo'] * len(text))
            continue
        roles = ['narracao'] * len(text)
        if settings['dialogue_dashes']:
            marcar_travessoes(text, roles)
        if aspas is not None:
            for i, marca in enumerate(aspas[k][0]):
                if marca == 'dentro':
                    roles[i] = settings['quotes_role']
                elif marca in ('abre', 'fecha'):
                    roles[i] = 'separador'
        if settings['italic_thoughts']:
            for start, end in block.italic:
                roles[start:end] = ['pensamento'] * (end - start)
        result.append(roles)
    return result


def masks(blocks, roles, allowed):
    # Pontuação de encerramento nos limites impede unir frases de áreas separadas.
    return [''.join(c if role in allowed else ('\n' if c == '\n' else ' ')
                    for c, role in zip(block.text, labels))
            for block, labels in zip(blocks, roles)]


def spans(labels, allowed):
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            if labels[start] in allowed:
                yield start, i, labels[start]
            start = i
