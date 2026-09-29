"""Leitura do corpo do DOCX, incluindo tabelas, na ordem do documento."""
from dataclasses import dataclass, field
from pathlib import Path
import re
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


@dataclass
class Block:
    number: int
    text: str
    chapter: str = "Sem capítulo identificado"
    heading: bool = False
    italic: list[tuple[int, int]] = field(default_factory=list)
    narrative_role: str = 'body'


def _paragraphs(parent):
    for item in parent.iter_inner_content():
        if isinstance(item, Paragraph):
            yield item
        elif isinstance(item, Table):
            seen = set()
            for row in item.rows:
                for cell in row.cells:
                    if cell._tc in seen:
                        continue
                    seen.add(cell._tc)
                    yield from _paragraphs(cell)


# Extenso cobre cardinais até 99 e ordinais comuns; títulos próprios podem ser
# cadastrados exatamente, sem tentar adivinhar pela aparência do parágrafo.
NUMBER_WORDS = set("um uma dois duas três tres quatro cinco seis sete oito nove dez onze doze treze catorze quatorze quinze dezesseis dezasseis dezessete dezassete dezoito dezenove dezanove vinte trinta quarenta cinquenta sessenta setenta oitenta noventa cem primeiro primeira segundo segunda terceiro terceira quarto quarta quinto quinta sexto sexta sétimo sétima setimo setima oitavo oitava nono nona décimo décima decimo decima".split())

def chapter_label(text):
    text=text.strip()
    if len(text)>160:
        return False
    match=re.match(r"^cap[íi]tulo\s+([^\s:—–.\-]+)(.*)$", text, re.I)
    if not match:
        return False
    token,tail=match.groups()
    valid=token.casefold() in NUMBER_WORDS or bool(re.fullmatch(r"\d+[ºª]?|[ivxlcdm]+",token,re.I))
    if not valid:
        return False
    # Após o número, aceita fim, pontuação de título ou continuação de numeral.
    tail=tail.strip()
    return not tail or tail[0] in ':—–.-' or all(w.casefold() in NUMBER_WORDS|{'e'} for w in tail.split())


def read_docx(path: Path, settings=None):
    if path.suffix.lower() != ".docx":
        raise ValueError("Use um arquivo .docx. No Pages: Arquivo → Exportar Para → Word.")
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 100_000_000:
            raise ValueError("DOCX muito grande: limite de 100 MB descompactados.")
        xml = archive.read("word/document.xml")
        tracked = bool(re.search(rb"<w:(?:ins|del)(?:\s|>)", xml))
    from .settings import validate
    options=validate(settings or {})
    custom_titles={x.strip().casefold() for x in options['chapter_titles']}
    custom_styles={x.strip().casefold() for x in options['chapter_styles']}
    document = Document(path)
    blocks = []
    chapter = "Sem capítulo identificado"
    paragraphs = list(_paragraphs(document))
    # Front matter exige crédito editorial e um limite de capítulo reconhecido.
    # Nunca descarta arbitrariamente os primeiros N parágrafos de uma narrativa.
    first_chapter = next((i for i, p in enumerate(paragraphs) if chapter_label(p.text)), None)
    credit = re.compile(r'^\s*(?:autor(?:a)?\s*:|revisão(?: e correção)?\s*:?)\s*$', re.I)
    markers = [i for i,p in enumerate(paragraphs[:first_chapter]) if credit.match(p.text)] if first_chapter is not None else []
    # Não engloba um prólogo narrativo situado depois dos créditos.
    last_credit_value = next((i for i in range(markers[-1]+1, first_chapter) if paragraphs[i].text.strip()), markers[-1]) if markers else -1
    front_end = last_credit_value + 1
    for number, p in enumerate(paragraphs, 1):
        text = p.text
        if not text.strip():
            continue
        style = p.style.name.lower() if p.style else ""
        short_title = (len(text.split()) <= 10 and len(text) <= 100
                       and text.isupper() and not re.search(r'[.!?…,:;"“”]', text))
        # outlineLvl permite reconhecer títulos mesmo com nomes de estilo personalizados.
        outline = p._p.xpath('./w:pPr/w:outlineLvl')
        if not outline and p.style is not None:
            outline = p.style.element.xpath('./w:pPr/w:outlineLvl')
        outline_heading = any(int(item.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '9')) < 9 for item in outline)
        heading = (text.strip().casefold() in custom_titles or style in custom_styles
                   or (options['chapter_auto'] and
                       (style.startswith(("heading", "título", "title", "cabeçalho"))
                        or style in {'capítulo', 'capitulo', 'pré-capítulo', 'pre-capitulo', 'nome da obra'}
                        or outline_heading or chapter_label(text) or short_title)))
        narrative_role = 'front_matter' if number <= front_end else 'heading' if heading else 'body'
        if narrative_role == 'front_matter':
            heading = True
        if heading and narrative_role != 'front_matter':
            chapter = text.strip()
        italic = []
        offset = 0
        # iter_inner_content inclui texto de hyperlinks, preservando os offsets.
        for item in p.iter_inner_content():
            for run in getattr(item, "runs", [item]):
                if getattr(run, "italic", False):
                    italic.append((offset, offset + len(run.text)))
                offset += len(run.text)
        blocks.append(Block(number, text, chapter, heading, italic, narrative_role))
    warnings = ["Escopo: corpo do documento e tabelas. Cabeçalhos, rodapés, notas, comentários, caixas de texto e imagens não são analisados. A localização usa parágrafos, não páginas."]
    if not any(b.heading for b in blocks):
        warnings.append("Nenhum capítulo identificado. Cadastre os títulos ou estilos em Estrutura do manuscrito; aparência visual e quebra de página, isoladamente, não definem capítulos.")
    if tracked:
        warnings.append("Há alterações controladas no DOCX. O texto inserido/excluído pode não ter sido lido. Aceite ou rejeite as alterações em uma cópia antes da análise definitiva.")
    if not blocks:
        raise ValueError("Não foi encontrado texto no corpo do DOCX.")
    if any(len(b.text) > 100_000 for b in blocks):
        raise ValueError("Há um parágrafo com mais de 100 mil caracteres. Divida-o antes de analisar.")
    return blocks, warnings
