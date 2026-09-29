"""Leitura do DOCX em parágrafos numerados, capítulos e cenas.

A numeração segue a do FONTE: parágrafos não vazios, a partir de 1, incluindo
títulos. Assim os relatórios dos dois motores apontam o mesmo parágrafo.
"""
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re

TITULO = re.compile(r"^\s*(cap[ií]tulo|parte|pr[oó]logo|ep[ií]logo|interl[uú]dio)\b", re.I)
QUEBRA = re.compile(r"^\s*([*#~]\s*){1,5}$")


@dataclass
class Paragrafo:
    numero: int
    texto: str
    capitulo: str
    titulo: bool = False


@dataclass
class Cena:
    numero: int
    capitulo: str
    paragrafos: list = field(default_factory=list)

    @property
    def inicio(self):
        return self.paragrafos[0].numero

    @property
    def fim(self):
        return self.paragrafos[-1].numero

    def texto_numerado(self):
        return "\n".join(f"[§{p.numero}] {p.texto}" for p in self.paragrafos)

    def assinatura(self):
        return hashlib.sha256(self.texto_numerado().encode("utf-8")).hexdigest()


def ler_docx(caminho):
    from docx import Document
    documento = Document(str(caminho))
    paragrafos, capitulo = [], "Sem capítulo"
    for bruto in documento.paragraphs:
        texto = bruto.text.strip()
        if not texto:
            continue
        titulo = len(texto) <= 80 and bool(TITULO.match(texto) or (bruto.style is not None and
                                                                   bruto.style.name.lower().startswith(("heading", "título"))))
        if titulo:
            capitulo = texto
        paragrafos.append(Paragrafo(len(paragrafos) + 1, texto, capitulo, titulo))
    return paragrafos


def ler_paragrafos(textos):
    """Mesma numeração a partir de uma lista de strings (testes e corpus JSON)."""
    paragrafos, capitulo = [], "Sem capítulo"
    for texto in textos:
        texto = texto.strip()
        if not texto:
            continue
        titulo = len(texto) <= 80 and bool(TITULO.match(texto))
        if titulo:
            capitulo = texto
        paragrafos.append(Paragrafo(len(paragrafos) + 1, texto, capitulo, titulo))
    return paragrafos


def cenas(paragrafos, maximo=3500):
    """Nova cena em cada capítulo, em quebras explícitas (***) ou ao passar de `maximo` caracteres."""
    resultado, atual, tamanho = [], None, 0
    for p in paragrafos:
        if p.titulo or QUEBRA.match(p.texto):
            atual = None
            continue
        if atual is None or atual.capitulo != p.capitulo or (tamanho + len(p.texto) > maximo and atual.paragrafos):
            atual = Cena(len(resultado) + 1, p.capitulo)
            resultado.append(atual)
            tamanho = 0
        atual.paragrafos.append(p)
        tamanho += len(p.texto)
    return resultado


def sha256(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()
