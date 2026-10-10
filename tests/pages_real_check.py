"""Conferência com o Pages REAL, só em documentos sintéticos criados numa pasta temporária.

Não faz parte da descoberta automática (`test_*.py`): exige o Pages instalado e a permissão de
Automação do macOS, e abre janelas do Pages. Roda a partir da raiz Git:

    fonte/.venv/bin/python tests/pages_real_check.py

Cobre: Unicode (emoji, acento combinado, fora do plano básico, travessões, início/meio/fim,
inserção), formatação dos trechos não alterados, recusa de documento já aberto, descarte sem salvar
numa falha no meio da troca e recusa de resultado divergente antes de salvar.
"""
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'fonte'))
from fonte.pages import read_pages_paragraphs  # noqa: E402

SWIFT = (ROOT / 'app/Lume/ManuscriptEditor.swift').read_text(encoding='utf-8')
SCRIPT = re.search(r'static let script = """\n(.*?)\n    """', SWIFT, re.S).group(1)
FAILS, OK = [], []


def check(name, condition, detail=''):
    (OK if condition else FAILS).append(name)
    print(('OK     ' if condition else 'FALHOU ') + name + ('' if condition else '  ' + str(detail)))


def osa(source, *args):
    done = subprocess.run(['osascript', '-e', source, *map(str, args)], capture_output=True, text=True, timeout=180)
    return done.returncode, (done.stdout + done.stderr).strip()


def codes(text):
    return ','.join(str(ord(c)) for c in text)


def make(path, paragraphs, bold=()):
    """Cria um .pages sintético; `bold` = [(parágrafo, de, até)] com posições 1-based inclusivas."""
    sets = '\n'.join(f'set p{i} to character id {{{codes(t)}}}' for i, t in enumerate(paragraphs))
    body = ' & return & '.join(f'p{i}' for i in range(len(paragraphs)))
    fmt = '\n'.join(f'set font of (characters {a} thru {b} of paragraph {n} of body text of d) to "Helvetica-Bold"'
                    for n, a, b in bold)
    code, out = osa(f'''{sets}
set alvo to POSIX file "{path}"
tell application id "com.apple.Pages"
  set d to make new document
  set body text of d to {body}
  {fmt}
  save d in alvo
  close d saving no
end tell''')
    assert code == 0, out


def fonts(path):
    code, out = osa(f'''set alvo to POSIX file "{path}" as alias
set saida to ""
tell application id "com.apple.Pages"
  set d to open alvo
  repeat with n from 1 to (count of paragraphs of body text of d)
    repeat with c in (every character of paragraph n of body text of d)
      set saida to saida & (font of c) & "|"
    end repeat
    set saida to saida & "#"
  end repeat
  close d saving no
end tell
return saida''')
    assert code == 0, out
    return [x.split('|')[:-1] for x in out.split('#')[:-1]]


def state(path):
    return osa(f'''tell application id "com.apple.Pages"
  set r to "FECHADO"
  repeat with x in documents
    try
      if (POSIX path of ((file of x) as alias)) is "{path}" then set r to "ABERTO modified=" & (modified of x) & " par2=[" & ((paragraph 2 of body text of x) as text) & "]"
    end try
  end repeat
  return r
end tell''')[1]


def close_all(path):
    osa(f'''tell application id "com.apple.Pages"
  repeat with x in documents
    try
      if (POSIX path of ((file of x) as alias)) is "{path}" then close x saving no
    end try
  end repeat
end tell''')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def texts(path):
    return [p.text for p in read_pages_paragraphs(Path(path))[0]]


def main():
    if subprocess.run(['osascript', '-e', 'id of application "Pages"'], capture_output=True).returncode != 0:
        print('Pages não encontrado: nada a conferir.'); return 0
    work = Path(tempfile.mkdtemp(prefix='lume-pages-real-')).resolve()  # o Pages informa o caminho real (/private/var)
    tool = work / 'edicao-swift'
    built = subprocess.run(['swiftc', str(ROOT / 'app/Lume/Models.swift'), str(ROOT / 'app/Lume/ManuscriptEditor.swift'),
                            str(ROOT / 'tests/EditCheck.swift'), '-o', str(tool)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr

    # 1. Unicode: o trecho do relatório (pontos de código) é o trecho trocado no Pages.
    cases = [
        ('emoji antes do trecho', 'Dia 🌿 e 😀 ela chegou a noite.', 'a noite', 'à noite', 0, False),
        ('acento combinado antes', 'Café fresco: ela chegou a noite.', 'a noite', 'à noite', 0, False),
        ('acento combinado no trecho', 'Ela bebeu café amargo.', 'café', 'café', 0, False),
        ('letra base de acento combinado', 'Ela bebeu café amargo.', 'e', 'E', 2, False),
        ('fora do plano básico', '𠮷 e 𝒜 e 😀 chegaram a noite.', 'a noite', 'à noite', 0, False),
        ('travessões', '— Vou — disse ela — a noite.', 'a noite', 'à noite', 0, False),
        ('travessão trocado', '— Vou — disse ela.', '—', '–', 1, False),
        ('início do parágrafo', 'ela chegou cedo.', 'ela', 'Ela', 0, False),
        ('fim do parágrafo', 'Ela chegou cedo.', 'cedo.', 'cedo!', 0, False),
        ('inserção no meio', 'Ela chegou a casa de 😀 Joana.', ' Joana', ',', 0, True),
        ('inserção no início', 'chegou cedo.', 'chegou', 'Ela ', 0, True),
        ('troca por emoji/astral', 'Ela chegou cedo.', 'cedo', '𠮷😀', 0, False),
        ('depois de astral e combinado', '😀 Café 𝒜 ela chegou cedo, e e ficou.', 'e e', 'e', 0, False),
    ]
    for i, (name, par, old, new, occurrence, insert) in enumerate(cases):
        f = work / f'u{i}.pages'
        make(f, ['Capítulo Um', par, 'Fim.'])
        idx = -1
        for _ in range(occurrence + 1):
            idx = par.index(old, idx + 1)
        start, end = idx, (idx if insert else idx + len(old))
        done = subprocess.run([str(tool), str(f), '2', str(start), str(end), new, par], capture_output=True, text=True, timeout=180)
        expected = par[:start] + new + par[end:]
        check('Unicode: ' + name, texts(f) == ['Capítulo Um', expected, 'Fim.'], (texts(f), done.stderr[-120:]))

    # 2. Formatação: fontes dos caracteres não trocados, e dos outros parágrafos, intactas.
    paragraphs = ['Capítulo Um', 'Ela chegou a noite com Joana.', 'Fim importante, sim.']
    bold = [(2, 1, 3), (2, 25, 29), (3, 5, 14)]
    for name, start, end, new in (('mesmo tamanho', 11, 12, 'à'), ('muda o tamanho', 11, 18, 'durante a noite'),
                                  ('troca dentro do negrito', 0, 3, 'Ela, a moça,')):
        f = work / f'f-{start}-{end}.pages'
        make(f, paragraphs, bold)
        before = fonts(f)
        subprocess.run([str(tool), str(f), '2', str(start), str(end), new, paragraphs[1]], capture_output=True, text=True, timeout=180)
        after = fonts(f)
        expected = list(before)
        target = before[1]
        expected[1] = target[:start] + [target[start]] * len(new) + target[end:]
        check('Formatação: ' + name, after == expected and texts(f)[1] == paragraphs[1][:start] + new + paragraphs[1][end:])

    # 3. Documento já aberto pelo autor: recusa, sem mexer em nada (nem na janela).
    f = work / 'aberto.pages'
    make(f, ['Capítulo Um', 'Ela chegou a noite.', 'Fim.'])
    before = sha(f)
    osa(f'tell application id "com.apple.Pages" to open (POSIX file "{f}")')
    done = subprocess.run([str(tool), str(f), '2', '12', '18', 'à noite', 'Ela chegou a noite.'], capture_output=True, text=True, timeout=180)
    estado = state(str(f))
    check('Documento aberto: correção recusada', done.returncode != 0 and 'aberto no Pages' in done.stderr + done.stdout,
          (done.returncode, done.stderr[-200:]))
    check('Documento aberto: janela e arquivo intactos', sha(f) == before and 'modified=false' in estado and 'a noite.]' in estado, estado)
    close_all(str(f))

    # 4. Falha no meio da troca (injetada): nada salvo; o documento aberto pelo script é fechado sem salvar.
    injected = SCRIPT.replace('                    set character a of paragraph n of body text to novo',
                              '                    error "FALHA_SIMULADA"\n                    set character a of paragraph n of body text to novo')
    assert injected != SCRIPT
    f = work / 'falha.pages'
    make(f, ['Capítulo Um', 'Ela chegou a noite.', 'Fim.'])
    before = sha(f)
    plan = ['Ela chegou à noite.']
    code, out = osa(injected, f, 2, 12, 18, codes('à noite'), codes('Ela chegou a noite.'), codes(plan[0]))
    check('Falha injetada: erro propagado, arquivo intacto e documento fechado',
          code != 0 and 'FALHA_SIMULADA' in out and sha(f) == before and state(str(f)) == 'FECHADO', (code, out[-80:], state(str(f))))

    # 5. Resultado divergente do esperado (índice errado): não salva.
    f = work / 'divergente.pages'
    make(f, ['Capítulo Um', 'Ela chegou a noite.', 'Fim.'])
    before = sha(f)
    code, out = osa(SCRIPT, f, 2, 12, 18, codes('à noite'), codes('Ela chegou a noite.'), codes('Ela chegou ao amanhecer.'))
    check('Resultado divergente: recusado antes de salvar', code != 0 and 'LUME_RESULTADO' in out and sha(f) == before
          and state(str(f)) == 'FECHADO', (code, out[-80:]))

    # 6. Caminho feliz com o script de produção.
    f = work / 'feliz.pages'
    make(f, ['Capítulo Um', 'Ela chegou a noite.', 'Fim.'])
    code, out = osa(SCRIPT, f, 2, 12, 18, codes('à noite'), codes('Ela chegou a noite.'), codes('Ela chegou à noite.'))
    check('Caminho feliz', code == 0 and texts(f) == ['Capítulo Um', 'Ela chegou à noite.', 'Fim.'] and state(str(f)) == 'FECHADO', (code, out))

    shutil.rmtree(work, ignore_errors=True)
    print(f'\n{len(OK)} conferências ok, {len(FAILS)} falhas.')
    return 1 if FAILS else 0


if __name__ == '__main__':
    raise SystemExit(main())
