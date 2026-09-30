"""Leitura do corpo de um documento do Pages (.pages), sem abrir o Pages.

O arquivo é um ZIP com `Index/*.iwa`: blocos Snappy contendo mensagens protobuf.
O formato não é documentado pela Apple; só são lidos os campos necessários para o
texto do corpo, o nome do estilo de cada parágrafo e o itálico. Nada é gravado.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
import io
from pathlib import Path
import zipfile

ROOT, DOCUMENT, STORAGE = 1, 10000, 2001
# Quebras de seção, página, coluna e parágrafo encerram um parágrafo.
BREAKS = '\n\r\x04\x05\x0c '
ERROR = ("Não foi possível ler este documento do Pages. Abra-o no Pages e salve novamente, "
         "ou use Arquivo → Exportar Para → Word.")


class _Malformed(Exception):
    """Estrutura fora do esperado; vira a mensagem de ERROR para o usuário."""


@dataclass
class PagesParagraph:
    text: str
    style: str = ''
    italic: list[tuple[int, int]] = field(default_factory=list)


def _varint(data, pos):
    result = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _snappy(data):
    _, pos = _varint(data, 0)
    out = bytearray()
    end = len(data)
    while pos < end:
        tag = data[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:
            size = tag >> 2
            if size >= 60:
                extra = size - 59
                size = int.from_bytes(data[pos:pos + extra], 'little')
                pos += extra
            size += 1
            if pos + size > end:
                raise _Malformed('literal truncado')
            out += data[pos:pos + size]
            pos += size
            continue
        if kind == 1:
            size = ((tag >> 2) & 7) + 4
            offset = ((tag >> 5) << 8) | data[pos]
            pos += 1
        else:
            width = 2 if kind == 2 else 4
            size = (tag >> 2) + 1
            offset = int.from_bytes(data[pos:pos + width], 'little')
            pos += width
        start = len(out) - offset
        if offset == 0 or start < 0:
            raise _Malformed('cópia inválida')
        if offset >= size:
            out += out[start:start + size]
        else:
            # Cópia sobreposta: repete o trecho final.
            for index in range(size):
                out.append(out[start + index])
    return bytes(out)


def _iwa(data):
    out = bytearray()
    pos = 0
    while pos < len(data):
        if data[pos] != 0:
            raise _Malformed('bloco desconhecido')
        size = int.from_bytes(data[pos + 1:pos + 4], 'little')
        pos += 4
        out += _snappy(data[pos:pos + size])
        pos += size
    return bytes(out)


def _fields(data):
    pos = 0
    end = len(data)
    while pos < end:
        key, pos = _varint(data, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire == 2:
            size, pos = _varint(data, pos)
            value = data[pos:pos + size]
            pos += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[pos:pos + size]
            pos += size
        else:
            raise _Malformed('campo desconhecido')
        if pos > end:
            raise _Malformed('campo truncado')
        yield number, wire, value


def _first(data, number, wire):
    return next((v for n, w, v in _fields(data) if n == number and w == wire), None)


def _reference(data):
    """Identificador apontado por uma mensagem de referência, ou None."""
    return None if data is None else _first(data, 1, 0)


def _objects(data, found):
    pos = 0
    while pos < len(data):
        size, pos = _varint(data, pos)
        info = data[pos:pos + size]
        pos += size
        identifier = _first(info, 1, 0)
        for number, wire, value in _fields(info):
            if number != 2 or wire != 2:
                continue
            kind, length = _first(value, 1, 0), _first(value, 3, 0) or 0
            found.setdefault(identifier, (kind, data[pos:pos + length]))
            pos += length


def _archives(path):
    """Conteúdo de cada Index/*.iwa, no ZIP ou no Index.zip interno de versões anteriores."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if any(n.endswith('.iwpv2') for n in names):
            raise ValueError("Este documento do Pages tem senha. Remova a senha de uma cópia "
                             "(Arquivo → Alterar Senha) antes de analisar.")
        if 'Index.zip' in names:
            if archive.getinfo('Index.zip').file_size > 100_000_000:
                raise ValueError("Documento do Pages muito grande: limite de 100 MB de texto e estilos.")
            with zipfile.ZipFile(io.BytesIO(archive.read('Index.zip'))) as inner:
                return _members(inner)
        return _members(archive)


def _members(archive):
    items = [i for i in archive.infolist() if i.filename.startswith('Index/') and i.filename.endswith('.iwa')]
    if not items:
        raise ValueError("Este arquivo é de uma versão antiga do Pages. Abra-o no Pages atual e "
                         "salve novamente, ou use Arquivo → Exportar Para → Word.")
    if sum(i.file_size for i in items) > 100_000_000:
        raise ValueError("Documento do Pages muito grande: limite de 100 MB de texto e estilos.")
    return [archive.read(i) for i in items]


def _table(storage, number):
    """Tabela de atributos: posições UTF-16 crescentes e o objeto válido a partir de cada uma."""
    table = _first(storage, number, 2)
    entries = []
    for n, wire, value in _fields(table or b''):
        if n == 1 and wire == 2:
            entries.append((_first(value, 1, 0) or 0, _reference(_first(value, 2, 2))))
    entries.sort(key=lambda entry: entry[0])
    return [e[0] for e in entries], [e[1] for e in entries]


def _at(table, position):
    index = bisect_right(table[0], position) - 1
    return table[1][index] if index >= 0 else None


class _Styles:
    def __init__(self, objects):
        self.objects = objects
        self.cache = {}
        self.italics = {}

    def _parts(self, identifier):
        if identifier not in self.cache:
            body = self.objects.get(identifier, (None, b''))[1]
            base = _first(body, 1, 2) or b''
            name = _first(base, 1, 2)
            properties = _first(body, 11, 2)
            italic = _first(properties, 2, 0) if properties else None
            self.cache[identifier] = ((name or b'').decode('utf-8', 'replace'),
                                      _reference(_first(base, 3, 2)), italic)
        return self.cache[identifier]

    def name(self, identifier):
        """Nome do estilo; variações sem nome (ajustes locais) usam o do estilo de origem."""
        seen = set()
        while identifier is not None and identifier not in seen:
            seen.add(identifier)
            name, identifier, _ = self._parts(identifier)
            if name:
                return name
        return ''

    def italic(self, identifier):
        """True/False quando o estilo ou um ancestral define itálico; None quando não define."""
        if identifier not in self.italics:
            seen, current, result = set(), identifier, None
            while current is not None and current not in seen:
                seen.add(current)
                _, current, italic = self._parts(current)
                if italic is not None:
                    result = bool(italic)
                    break
            self.italics[identifier] = result
        return self.italics[identifier]


def _body(objects):
    root = objects.get(ROOT)
    if root and root[0] == DOCUMENT:
        target = _reference(_first(root[1], 4, 2))
        if target in objects and objects[target][0] == STORAGE:
            return objects[target][1]
    # Sem a raiz esperada, só aceita um corpo inequívoco (tipo de armazenamento 0).
    bodies = [body for kind, body in objects.values() if kind == STORAGE and not _first(body, 1, 0)]
    if len(bodies) != 1:
        raise ValueError(ERROR)
    return bodies[0]


def read_pages_paragraphs(path: Path):
    """Parágrafos do corpo, inclusive os vazios, e se há alterações controladas."""
    try:
        objects = {}
        for data in _archives(path):
            _objects(_iwa(data), objects)
        storage = _body(objects)
        text = ''.join(v.decode('utf-8') for n, w, v in _fields(storage) if n == 3 and w == 2)
        paragraph_styles, character_styles = _table(storage, 5), _table(storage, 8)
        tracked = any(_first(storage, number, 2) for number in (19, 20))
    except ValueError:
        raise
    except Exception as exc:  # ZIP, Snappy ou protobuf fora do esperado
        raise ValueError(ERROR) from exc
    styles = _Styles(objects)
    paragraphs = []
    current = None
    position = 0  # unidades UTF-16, como nas tabelas do Pages
    for char in text:
        if current is None:
            style = _at(paragraph_styles, position)
            current = (style, [], [])
            base_italic = styles.italic(style)
        style, chars, italic = current
        width = 2 if ord(char) > 0xFFFF else 1
        if char in BREAKS:
            paragraphs.append(PagesParagraph(''.join(chars), styles.name(style), italic))
            current = None
        elif char == ' ':
            chars.append('\n')
        elif char == '\t' or (char >= ' ' and char != '￼'):
            # Marcas de objetos ancorados e de notas não fazem parte do texto.
            own = styles.italic(_at(character_styles, position))
            if base_italic if own is None else own:
                offset = len(chars)
                if italic and italic[-1][1] == offset:
                    italic[-1] = (italic[-1][0], offset + 1)
                else:
                    italic.append((offset, offset + 1))
            chars.append(char)
        position += width
    if current is not None:
        paragraphs.append(PagesParagraph(''.join(current[1]), styles.name(current[0]), current[2]))
    return paragraphs, tracked
