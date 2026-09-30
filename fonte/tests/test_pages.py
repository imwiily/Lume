"""Leitura de documentos do Pages: arquivo real sintético e estruturas montadas no teste."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import spacy

from fonte.cli import main
from fonte.pages import _iwa, read_pages_paragraphs
from fonte.reader import read_docx, read_manuscript, read_pages, verify_edit

# Criado no Pages 15.3 com texto escrito para este teste. O nome da impressora gravado pelo Pages
# foi trocado por um genérico do mesmo tamanho; o restante é o arquivo original.
SAMPLE = Path(__file__).parent / 'corpus' / 'pages' / 'manuscrito-sintetico.pages'


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode('utf-8')
    return varint(number << 3 | 2) + varint(len(value)) + value


def reference(identifier):
    return field(1, identifier)


def table(entries):
    """Entradas (posição UTF-16, identificador ou None)."""
    return b''.join(field(1, field(1, position) + (field(2, reference(target)) if target else b''))
                    for position, target in entries)


def style(name='', parent=None, italic=None):
    base = (field(1, name) if name else b'') + (field(3, reference(parent)) if parent else b'')
    return field(1, base) + (field(11, field(2, int(italic))) if italic is not None else b'')


def iwa(objects):
    """Arquivo .iwa com Snappy só de literais; objects = [(identificador, tipo, corpo)]."""
    raw = b''.join(
        (lambda info: varint(len(info)) + info + body)(
            field(1, identifier) + field(2, field(1, kind) + field(3, len(body))))
        for identifier, kind, body in objects)
    out = b''
    for start in range(0, len(raw), 60):
        chunk = raw[start:start + 60]
        compressed = varint(len(chunk)) + bytes([(len(chunk) - 1) << 2]) + chunk
        out += b'\x00' + len(compressed).to_bytes(3, 'little') + compressed
    return out


def document(text, paragraph_styles=(), character_styles=(), styles=(), extra=b''):
    storage = (field(1, 0) + field(3, text) + field(5, table(paragraph_styles))
               + field(8, table(character_styles)) + extra)
    return iwa([(1, 10000, field(4, reference(50))), (50, 2001, storage),
                (60, 2001, field(1, 1) + field(3, 'Texto de cabeçalho.')),
                *((identifier, 2022 if kind == 'p' else 2021, body) for identifier, kind, body in styles)])


def write(folder, data, name='Teste.pages', member='Index/Document.iwa'):
    path = Path(folder) / name
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(member, data)
    return path


class PagesSampleTests(unittest.TestCase):
    def test_real_file_text_styles_italics_and_input_unchanged(self):
        digest = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
        blocks, warnings = read_pages(SAMPLE)
        self.assertEqual([b.number for b in blocks], [1, 2, 4, 5, 6, 7])
        self.assertEqual(blocks[1].text, 'A lanterna de Otávio piscou duas vezes — “café” 😀 e açúcar.')
        # O itálico vem depois de um emoji: as posições do Pages são UTF-16.
        self.assertEqual([blocks[2].text[a:b] for a, b in blocks[2].italic], ['inclinada'])
        self.assertIn('café decomposto', blocks[2].text)
        self.assertEqual(blocks[3].text, 'Primeira linha\nsegunda linha do mesmo parágrafo.')
        self.assertEqual([b.text for b in blocks if b.heading], ['Capítulo Um', 'Capítulo Dois'])
        self.assertEqual(blocks[-1].chapter, 'Capítulo Dois')
        self.assertTrue(any('Pages' in w and 'Tabelas' in w for w in warnings))
        self.assertFalse(any('alterações controladas' in w for w in warnings))
        self.assertEqual(hashlib.sha256(SAMPLE.read_bytes()).hexdigest(), digest)

    def test_paragraph_style_name_is_available_to_chapter_settings(self):
        options = {'chapter_auto': False, 'chapter_styles': ['Corpo']}
        self.assertTrue(read_pages(SAMPLE, options)[0][0].heading)
        self.assertFalse(read_pages(SAMPLE, {'chapter_auto': False})[0][0].heading)

    def test_dispatch_by_extension(self):
        self.assertEqual(read_manuscript(SAMPLE)[0][0].text, 'Capítulo Um')
        with self.assertRaisesRegex(ValueError, r'\.docx ou'):
            read_manuscript(Path('x.txt'))
        with self.assertRaisesRegex(ValueError, 'Pages'):
            read_docx(SAMPLE)

    def test_cli_report_preserves_pages_file(self):
        nlp = spacy.load("pt_core_news_sm", disable=["ner"])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'Manuscrito com espaços.pages'
            path.write_bytes(SAMPLE.read_bytes())
            out = Path(td) / 'resultado'
            with patch("fonte.cli.load_model", return_value=nlp), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["revisar", str(path), "--saida", str(out)]), 0)
            data = json.loads((out / "relatorio.json").read_text())
            self.assertEqual(data["document"], path.name)
            self.assertEqual(data["sha256"], hashlib.sha256(SAMPLE.read_bytes()).hexdigest())
            self.assertEqual(path.read_bytes(), SAMPLE.read_bytes())
            self.assertEqual([c["title"] for c in data["metadata"]["chapters"]], ['Capítulo Um', 'Capítulo Dois'])
            index = data["metadata"]["text_index"]
            self.assertEqual(index["length"], len('\n'.join(b.text for b in read_pages(path)[0])))

    def test_cli_explains_package_folder(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'Pacote.pages'
            folder.mkdir()
            errors = io.StringIO()
            with redirect_stderr(errors):
                self.assertEqual(main(["revisar", str(folder)]), 2)
            self.assertIn('Arquivo Único', errors.getvalue())


class PagesStructureTests(unittest.TestCase):
    def read(self, data, **kwargs):
        with tempfile.TemporaryDirectory() as td:
            return read_pages_paragraphs(write(td, data, **kwargs))

    def test_builder_roundtrip(self):
        self.assertIn('Texto de cabeçalho.'.encode(), _iwa(document('Corpo.')))

    def test_breaks_anchors_and_only_the_body_storage(self):
        paragraphs, tracked = self.read(document('Um.\x05Dois￼ aqui.\x04\nTrês\x0e.'))
        self.assertEqual([p.text for p in paragraphs], ['Um.', 'Dois aqui.', '', 'Três.'])
        self.assertFalse(tracked)

    def test_italic_from_character_style_parent_and_paragraph_style(self):
        # 72 é uma variação sem nome (ajuste local) do estilo Título.
        styles = [(70, 'p', style('Título')), (72, 'p', style(parent=70)), (71, 'p', style('Citação', italic=True)),
                  (80, 'c', style('Ênfase', italic=True)), (81, 'c', style(parent=80)),
                  (82, 'c', style(italic=False)), (83, 'c', style('Negrito'))]
        text = 'A Casa\nEla 😀 viu tudo.\nToda inclinada menos isto.'
        second = len('A Casa\n')
        third = second + len('Ela 😀 viu tudo.\n') + 1  # o emoji ocupa duas unidades UTF-16
        paragraphs, _ = self.read(document(
            text, [(0, 72), (second, None), (third, 71)],
            [(0, None), (second + 7, 81), (second + 10, 83), (third + 21, 82)], styles))
        self.assertEqual(paragraphs[0].style, 'Título')
        self.assertEqual([paragraphs[1].text[a:b] for a, b in paragraphs[1].italic], ['viu'])
        self.assertEqual([paragraphs[2].text[a:b] for a, b in paragraphs[2].italic], ['Toda inclinada menos '])
        with tempfile.TemporaryDirectory() as td:
            path = write(td, document(text, [(0, 72), (second, None)], styles=styles))
            blocks, _ = read_pages(path)
        self.assertTrue(blocks[0].heading)
        self.assertEqual(blocks[1].chapter, 'A Casa')

    def test_tracked_changes_are_warned(self):
        data = document('Texto.', extra=field(20, table([(0, 90)])))
        self.assertTrue(self.read(data)[1])
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(any('alterações controladas' in w for w in read_pages(write(td, data))[1]))

    def test_index_zip_of_earlier_versions(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, 'w') as archive:
            archive.writestr('Index/Document.iwa', document('Texto antigo.'))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'Antigo.pages'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Index.zip', inner.getvalue())
            self.assertEqual(read_pages(path)[0][0].text, 'Texto antigo.')

    def test_unreadable_files_give_guidance_not_tracebacks(self):
        with tempfile.TemporaryDirectory() as td:
            cases = [(write(td, b'\x00\x05\x00\x00\x09\xf0abc', 'Corrompido.pages'), 'Não foi possível ler'),
                     (write(td, b'<xml/>', 'Pages09.pages', 'index.xml'), 'versão antiga'),
                     (write(td, b'', 'Senha.pages', '.iwpv2'), 'senha'),
                     (write(td, iwa([(7, 2001, field(1, 1))]), 'SemCorpo.pages'), 'Não foi possível ler'),
                     (write(td, document('\n \n'), 'Vazio.pages'), 'Não foi encontrado texto')]
            plain = Path(td) / 'Texto.pages'
            plain.write_text('não é um zip')
            for path, message in cases + [(plain, 'Não foi possível ler')]:
                with self.subTest(path.name), self.assertRaisesRegex(ValueError, message):
                    read_pages(path)


class EditVerificationTests(unittest.TestCase):
    TEXT = 'Capítulo Um\nEla chegou a noite.\n\nO farol piscou.'

    def pair(self, td, after, **kwargs):
        return (write(td, document(self.TEXT), 'Antes.pages'), write(td, document(after, **kwargs), 'Depois.pages'))

    def test_accepts_only_the_expected_paragraph_change(self):
        with tempfile.TemporaryDirectory() as td:
            before, after = self.pair(td, self.TEXT.replace('a noite', 'à noite'))
            verify_edit(before, after, 2, 'Ela chegou à noite.')
            with self.assertRaisesRegex(ValueError, 'texto esperado'):
                verify_edit(before, after, 2, 'Ela chegou a noite.')
            with self.assertRaisesRegex(ValueError, 'não existe'):
                verify_edit(before, after, 3, '')

    def test_rejects_changes_elsewhere(self):
        with tempfile.TemporaryDirectory() as td:
            cases = {'outro texto': self.TEXT.replace('a noite', 'à noite').replace('piscou', 'apagou'),
                     'parágrafo novo': self.TEXT.replace('a noite.', 'à noite.\nNovo.'),
                     'parágrafo removido': 'Capítulo Um\nEla chegou à noite.'}
            for name, text in cases.items():
                with self.subTest(name):
                    before, after = self.pair(td, text)
                    with self.assertRaises(ValueError):
                        verify_edit(before, after, 2, 'Ela chegou à noite.')
            styles = [(80, 'c', style('Ênfase', italic=True))]
            before, after = self.pair(td, self.TEXT.replace('a noite', 'à noite'),
                                      character_styles=[(0, None), (len(self.TEXT) - 7, 80)], styles=styles)
            with self.assertRaisesRegex(ValueError, 'Outros parágrafos'):
                verify_edit(before, after, 2, 'Ela chegou à noite.')

    def test_cli_reports_hash_and_leaves_both_files_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            before, after = self.pair(td, self.TEXT.replace('a noite', 'à noite'))
            expected = Path(td) / 'esperado.txt'
            expected.write_text('Ela chegou à noite.', encoding='utf-8')
            bytes_before, bytes_after = before.read_bytes(), after.read_bytes()
            out, errors = io.StringIO(), io.StringIO()
            command = ["conferir-edicao", str(before), str(after), "--esperado", str(expected)]
            with redirect_stdout(out), redirect_stderr(errors):
                self.assertEqual(main(command + ["--paragrafo", "2"]), 0)
                self.assertEqual(main(command + ["--paragrafo", "4"]), 2)
            line = next(x for x in out.getvalue().splitlines() if x.startswith('LUME_EDICAO '))
            self.assertEqual(json.loads(line[12:])["sha256"], hashlib.sha256(bytes_after).hexdigest())
            self.assertEqual(out.getvalue().count('LUME_EDICAO'), 1)
            self.assertEqual((before.read_bytes(), after.read_bytes()), (bytes_before, bytes_after))


if __name__ == '__main__':
    unittest.main()
