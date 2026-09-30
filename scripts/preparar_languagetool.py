"""Prepara o corretor gramatical local embutido: LanguageTool (só português) e Java mínimo.

Baixa uma versão fixa conferida por SHA-256 (ou usa um ZIP local), mantém apenas
o módulo de português, gera um runtime Java com jlink e testa o servidor. O
resultado é uma pasta nova, usada pelo motor em desenvolvimento
(`fonte/.languagetool`) e copiada para o pacote `.lumemotor`.

Requer um JDK 17 ou posterior (jlink) no Mac arm64. Licenças: LanguageTool é
LGPL 2.1 (COPYING.txt e third-party-licenses são preservados); o runtime Java
leva a pasta legal/ do OpenJDK.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '6.6'
URL = f'https://languagetool.org/download/LanguageTool-{VERSION}.zip'
SHA256 = '53600506b399bb5ffe1e4c8dec794fd378212f14aaf38ccef9b6f89314d11631'
# As regras de português consultam o dicionário de inglês (IsEnglishWordFilter).
KEEP_LANGUAGES = {'pt', 'en'}
# Módulos informados por jdeps para o servidor, mais registro, XML, rede,
# criptografia e dados de localidade usados em tempo de execução.
MODULES = ['java.base', 'java.compiler', 'java.desktop', 'java.instrument', 'java.logging', 'java.management',
           'java.naming', 'java.net.http', 'java.scripting', 'java.sql', 'java.xml', 'jdk.crypto.ec',
           'jdk.httpserver', 'jdk.localedata', 'jdk.management', 'jdk.unsupported', 'jdk.zipfs']
# Bibliotecas exclusivas de outros idiomas (dicionários e modelos).
FOREIGN_LIBS = ('lucene-gosen-ipadic', 'hanlp', 'morfologik-ukrainian-lt', 'morfologik-crh-lt', 'languagetool-ga-dicts',
                'jwordsplitter')


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def fetch(target):
    print(f'Baixando LanguageTool {VERSION}…', flush=True)
    with urllib.request.urlopen(URL, timeout=120) as response, open(target, 'wb') as stream:
        shutil.copyfileobj(response, stream)


def language_codes(root):
    resource = root / 'org/languagetool/resource'
    return {p.name for p in resource.iterdir() if p.is_dir()} | {p.name for p in (root / 'org/languagetool/rules').iterdir() if p.is_dir()}


def prune(root):
    """Remove dicionários e regras grandes de outros idiomas.

    O registro de idiomas continua completo: o detector de idioma do servidor
    exige todos na inicialização. Regras e dicionários de cada idioma só são
    lidos quando esse idioma é verificado, e o motor sempre pede pt-BR. Arquivos
    pequenos (palavras comuns etc.) ficam para a detecção inicial.
    """
    removed = 0
    for code in language_codes(root) - KEEP_LANGUAGES:
        if len(code) > 3:
            continue
        for base in ('org/languagetool/rules', 'org/languagetool/resource'):
            folder = root / base / code
            for path in folder.rglob('*') if folder.is_dir() else ():
                # Classes Java são carregadas na inicialização; só dados grandes saem.
                if (path.is_file() and path.suffix != '.class' and path.stat().st_size > 256_000
                        and 'common' not in path.name):
                    removed += path.stat().st_size
                    path.unlink()
    for jar in (root / 'libs').glob('*.jar'):
        name = jar.stem
        foreign_dict = name.endswith('-pos-dict') and not name.startswith(('portuguese', 'english'))
        if foreign_dict or name in FOREIGN_LIBS:
            removed += jar.stat().st_size
            jar.unlink()
    return removed


def jdk_home(explicit):
    if explicit:
        return Path(explicit)
    if os.environ.get('JAVA_HOME'):
        return Path(os.environ['JAVA_HOME'])
    found = subprocess.run(['/usr/libexec/java_home'], capture_output=True, text=True)
    if found.returncode:
        raise SystemExit('JDK não encontrado. Instale um JDK 17+ (por exemplo, brew install openjdk) ou use --jdk.')
    return Path(found.stdout.strip())


def smoke(root):
    """Inicia o servidor preparado e confere uma correção conhecida em português."""
    sys.path.insert(0, str(ROOT / 'fonte'))
    os.environ['FONTE_LANGUAGETOOL'] = str(root)
    from fonte import languagetool
    from fonte.reader import Block
    assert languagetool.home() == root, 'Pasta preparada não reconhecida pelo motor'
    with languagetool.embedded() as port:
        results, _ = languagetool.check([Block(1, '— Voce chegou cedo — disse ela.')], port)
    assert any(r['suggestion'] == 'Você' for r in results), 'Correção de teste ausente: ' + repr(results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--saida', type=Path, default=ROOT / 'fonte/.languagetool',
                        help='Pasta nova (padrão: fonte/.languagetool)')
    parser.add_argument('--zip', type=Path, help='ZIP do LanguageTool já baixado (conferido pelo SHA-256)')
    parser.add_argument('--jdk', help='JDK com jlink (padrão: JAVA_HOME ou /usr/libexec/java_home)')
    args = parser.parse_args(argv)
    output = args.saida.expanduser().resolve()
    if output.exists():
        raise SystemExit(f'A pasta {output} já existe. Remova-a ou escolha outra saída.')
    jdk = jdk_home(args.jdk)
    jlink = jdk / 'bin/jlink'
    if not jlink.is_file():
        raise SystemExit(f'jlink ausente em {jdk}.')
    with tempfile.TemporaryDirectory(prefix='languagetool-') as temporary:
        work = Path(temporary)
        archive = args.zip.expanduser().resolve() if args.zip else work / 'languagetool.zip'
        if not args.zip:
            fetch(archive)
        if digest(archive) != SHA256:
            raise SystemExit('SHA-256 do LanguageTool diferente do esperado; o arquivo não será usado.')
        with zipfile.ZipFile(archive) as source:
            source.extractall(work / 'zip')
        extracted = work / 'zip' / f'LanguageTool-{VERSION}'
        removed = prune(extracted)
        staging = work / 'saida'
        shutil.copytree(extracted, staging, symlinks=True)
        print('Gerando runtime Java mínimo…', flush=True)
        subprocess.run([str(jlink), '--add-modules', ','.join(MODULES), '--include-locales=pt,en',
                        '--strip-debug', '--no-man-pages', '--no-header-files',
                        '--output', str(staging / 'jre')], check=True)
        release = (staging / 'jre/release').read_text(encoding='utf-8')
        java_version = next((line.split('=', 1)[1].strip('"') for line in release.splitlines()
                             if line.startswith('JAVA_VERSION=')), 'desconhecida')
        (staging / 'lume-languagetool.json').write_text(json.dumps({
            'languagetool_version': VERSION, 'languagetool_sha256': SHA256, 'languages': sorted(KEEP_LANGUAGES),
            'java_version': java_version, 'java_modules': MODULES, 'bytes_removed': removed}, indent=2) + '\n')
        smoke(staging)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), output)
    size = sum(f.stat().st_size for f in output.rglob('*') if f.is_file())
    print(f'Corretor gramatical preparado em {output} ({size / 1e6:.0f} MB).')


if __name__ == '__main__':
    main()
