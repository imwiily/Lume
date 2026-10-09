"""Executar com o Python de fonte/.venv; gera um motor portátil no Mac nativo."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
from engine_packages import inventory, validate, probe

MACH_O = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'}


def minimum_os(root):
    """Maior macOS mínimo (minos) gravado nos binários do pacote. O sistema da montagem não conta:
    um binário com minos maior que o macOS do usuário não carrega."""
    versions = []
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            head = stream.read(8)
        # 0xcafebabe também abre classes Java; no binário universal, segue o número de arquiteturas.
        if head[:4] not in MACH_O or (head[:4] == b'\xca\xfe\xba\xbe' and int.from_bytes(head[4:], 'big') > 30):
            continue
        shown = subprocess.run(['/usr/bin/vtool', '-show-build', str(path)],
                               capture_output=True, text=True, check=True).stdout
        # Por comando de carga: minos em LC_BUILD_VERSION; version em LC_VERSION_MIN_MACOSX (antigo).
        found = re.findall(r'cmd LC_BUILD_VERSION\n.*?^\s*minos (\d+(?:\.\d+)*)$', shown, re.M | re.S)
        found += re.findall(r'cmd LC_VERSION_MIN_MACOSX\n.*?^\s*version (\d+(?:\.\d+)*)$', shown, re.M | re.S)
        if not found:
            raise SystemExit('Binário sem macOS mínimo declarado: ' + str(path))
        versions += [tuple(map(int, v.split('.'))) for v in found]
    if not versions:
        raise SystemExit('Nenhum binário no motor: ' + str(root))
    return '.'.join(map(str, max(versions)))


def own_packages_only(runtime):
    """O motor leva só os módulos de fonte/fonte e coerencia/coerencia. A pasta do projeto tem
    dados locais (Coerencia/Projetos guarda trechos de manuscritos), .venv e testes."""
    for name in ('fonte', 'coerencia'):
        source, frozen = ROOT / name / name, Path(runtime) / '_internal' / name
        files = lambda base: {p.relative_to(base) for p in base.rglob('*')
                              if p.is_file() and '__pycache__' not in p.parts}
        extra = sorted(str(p) for p in files(frozen) - files(source))
        if extra:
            raise SystemExit('O motor congelado leva arquivos fora do pacote ' + name + ': '
                             + ', '.join(extra[:5]) + '. Instale o pacote em modo editável compat.')


def freeze_command(work):
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--noupx',
               '--name', 'lume-engine',
               '--distpath', str(work / 'dist'), '--workpath', str(work / 'work'), '--specpath', str(work),
               '--paths', str(ROOT / 'fonte'), '--paths', str(ROOT / 'packaging'),
               # Coerência com IA: fonte única em coerencia/, embutida no motor.
               '--paths', str(ROOT / 'coerencia')]
    for module in ('fonte', 'spacy', 'thinc', 'pt_core_news_sm', 'srsly', 'cymem', 'preshed', 'murmurhash', 'blis',
                   'coerencia', 'anthropic'):
        command += ['--collect-all', module]
    command += ['--collect-data', 'docx', '--recursive-copy-metadata', 'spacy',
                '--copy-metadata', 'pt-core-news-sm', '--copy-metadata', 'fonte-revisor', '--copy-metadata', 'anthropic']
    for module in ('torch', 'tensorflow', 'cupy', 'jax', 'matplotlib', 'pytest'):
        command += ['--exclude-module', module]
    command.append(str(ROOT / 'packaging/lume_engine.py'))
    if sys.platform == 'darwin':
        command += ['--target-architecture', 'arm64']
    return command


# Só usados para montar o motor; não seguem dentro dele.
SO_MONTAGEM = {'pip', 'setuptools', 'wheel', 'altgraph', 'macholib', 'pyinstaller-hooks-contrib'}
# Código do próprio Lume; licenças de terceiros que ele contém entram à parte.
PROPRIOS = {'fonte-revisor', 'coerencia'}
USOS = {'spacy': 'Análise sintática', 'pt-core-news-sm': 'Modelo de português', 'anthropic': 'Coerência com IA',
        'python-docx': 'Leitura do DOCX', 'pyinstaller': 'Carregador do motor empacotado', 'numpy': 'Cálculo numérico',
        'thinc': 'Modelos do spaCy', 'lxml': 'Leitura do DOCX', 'httpx': 'Conexão com a API'}
# Rótulos curtos quando o metadado traz o texto inteiro ou um nome genérico.
LICENCAS = {'pyinstaller': 'GPL-2.0-or-later com exceção para o carregador'}


def licencas(package, grammar):
    """Grava licencas/indice.json e copia os textos de licença de tudo que segue no motor."""
    import importlib.metadata as metadata
    pasta = package / 'licencas'
    pasta.mkdir()
    itens, vistos = [], set()

    def copiar(nome, origem, destino):
        alvo = pasta / nome / destino
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, alvo)
        return str(alvo.relative_to(package))

    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].casefold()):
        nome = dist.metadata['Name']
        chave = nome.casefold().replace('_', '-')
        if chave in vistos or chave in SO_MONTAGEM or chave in PROPRIOS:
            continue
        vistos.add(chave)
        md = dist.metadata
        classificadores = [c.split(' :: ')[-1] for c in md.get_all('Classifier') or [] if c.startswith('License ::')]
        texto = md.get('License-Expression') or (md.get('License') or '').strip()
        licenca = LICENCAS.get(chave) or (texto if texto and len(texto) <= 80 and '\n' not in texto
                                          else (classificadores[0] if classificadores else 'Ver texto'))
        arquivos = [copiar(nome, dist.locate_file(f), f.name if i == 0 else f'{i}-{f.name}')
                    for i, f in enumerate(f for f in dist.files or []
                                          if any(k in f.name.upper() for k in ('LICEN', 'COPYING', 'NOTICE')))
                    if Path(dist.locate_file(f)).is_file()]
        itens.append({'nome': nome, 'versao': dist.version, 'licenca': licenca,
                      'uso': USOS.get(chave, 'Dependência do motor'), 'arquivos': arquivos})
    python = Path(sys.base_prefix) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'LICENSE.txt'
    if python.is_file():
        itens.append({'nome': 'Python', 'versao': platform.python_version(), 'licenca': 'PSF-2.0',
                      'uso': 'Linguagem do motor', 'arquivos': [copiar('Python', python, 'LICENSE.txt')]})
    lexico = ROOT / 'fonte/fonte/data/PORTILEXICON-LICENSE.txt'
    itens.append({'nome': 'PortiLexicon-UD', 'versao': '', 'licenca': 'MIT', 'uso': 'Léxico do português',
                  'arquivos': [copiar('PortiLexicon-UD', lexico, 'LICENSE.txt')]})
    if grammar:
        info = json.loads((grammar / 'lume-languagetool.json').read_text())
        terceiros = sorted(p for p in (grammar / 'third-party-licenses').iterdir() if p.is_file())
        itens.append({'nome': 'LanguageTool', 'versao': info['languagetool_version'], 'licenca': 'LGPL-2.1-or-later',
                      'uso': 'Corretor gramatical local',
                      'arquivos': ['languagetool/COPYING.txt'] + [f'languagetool/third-party-licenses/{p.name}' for p in terceiros]})
        legal = grammar / 'jre/legal/java.base'
        itens.append({'nome': 'OpenJDK', 'versao': info['java_version'], 'licenca': 'GPL-2.0 com Classpath Exception',
                      'uso': 'Java mínimo do corretor',
                      'arquivos': [f'languagetool/jre/legal/java.base/{n}' for n in ('LICENSE', 'ASSEMBLY_EXCEPTION', 'ADDITIONAL_LICENSE_INFO')
                                   if (legal / n).is_file()]})
    itens.sort(key=lambda item: item['nome'].casefold())
    (pasta / 'indice.json').write_text(json.dumps({'schema': 1, 'componentes': itens}, ensure_ascii=False, indent=2))
    return itens


def languagetool_source(explicit):
    """Corretor gramatical preparado por scripts/preparar_languagetool.py."""
    source = (explicit or ROOT / 'fonte/.languagetool').resolve()
    if not (source / 'languagetool-server.jar').is_file() or not (source / 'jre/bin/java').is_file():
        raise SystemExit('Corretor gramatical embutido ausente em ' + str(source) +
                         '. Execute scripts/preparar_languagetool.py ou use --sem-languagetool.')
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languagetool', type=Path, help='Pasta preparada do corretor (padrão: fonte/.languagetool)')
    parser.add_argument('--sem-languagetool', action='store_true', help='Monta o motor sem o corretor gramatical embutido')
    args = parser.parse_args()
    grammar = None if args.sem_languagetool else languagetool_source(args.languagetool)
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise SystemExit('Monte com Python nativo arm64 no Mac Apple Silicon. Não use um ambiente Intel/Rosetta.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / ('build-engine-' + uuid.uuid4().hex)
    work.mkdir()
    log = work / 'pyinstaller.log'
    command = freeze_command(work)
    print('Empacotando Python, modelo e analisador. Registro: ' + str(log), flush=True)
    with log.open('w') as stream:
        # Fora da raiz: nela, coerencia/ (pasta do projeto) vira pacote de namespace, e --collect-all
        # levaria a pasta inteira (Projetos com trechos de manuscritos, .venv, testes).
        result = subprocess.run(command, cwd=work, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit('PyInstaller falhou. Consulte ' + str(log))
    runtime = work / 'dist/lume-engine'
    own_packages_only(runtime)
    environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(runtime / 'lume-engine'), '--lume-probe'], cwd=work,
                            env=environment, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise SystemExit('O motor empacotado falhou no teste:\n' + result.stdout + result.stderr)
    health = json.loads(result.stdout.strip().splitlines()[-1])
    package = output / ('fonte-' + health['engine_version'] + '-' + uuid.uuid4().hex[:8] + '.lumemotor')
    package.mkdir()
    shutil.copytree(runtime, package / 'runtime', symlinks=True)
    if grammar:
        # Fica ao lado de runtime/: o motor congelado o procura em ../languagetool.
        shutil.copytree(grammar, package / 'languagetool', symlinks=True)
    # Inventário de dependências e textos de licença, exibidos em “Sobre o Lume”.
    freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (package / 'dependencias.txt').write_text(freeze)
    licencas(package, grammar)
    manifest = {'package_schema': 1, 'api_version': 1, 'report_schema': 1, 'decision_schema': 1,
                'engine_version': health['engine_version'], 'platform': 'darwin', 'architecture': 'arm64',
                'minimum_os': minimum_os(package), 'executable': 'runtime/lume-engine', 'files': inventory(package)}
    (package / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
    validate(package); probe(package, manifest)
    # Contrato real da CLI após congelamento e relocação; não usa Python externo.
    report = work / 'relatorio-teste'
    subprocess.run([str(package / 'runtime/lume-engine'), 'revisar', str(ROOT / 'examples/Manuscrito-exemplo.docx'),
                    '--saida', str(report), '--tempo', 'passado'], cwd=work, env=environment, check=True, timeout=120)
    payload = json.loads((report / 'relatorio.json').read_text())
    assert payload['schema_version'] == 1 and payload['metadata']['versao_fonte'] == health['engine_version']
    assert len(payload['findings']) > 0
    if grammar:
        # O executável relocado inicia o corretor embutido com o Java do pacote.
        checked = work / 'relatorio-corretor'
        subprocess.run([str(package / 'runtime/lume-engine'), 'revisar', str(ROOT / 'examples/Manuscrito-exemplo.docx'),
                        '--saida', str(checked), '--tempo', 'passado', '--languagetool'],
                       cwd=work, env=environment, check=True, timeout=300)
        payload = json.loads((checked / 'relatorio.json').read_text())
        assert payload['metadata']['languagetool_origem'] == 'embutido', 'Corretor embutido não foi usado'
        assert any(f['source'].startswith('LanguageTool') for f in payload['findings']), 'Corretor embutido sem resultados'
    subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(package), str(package) + '.zip'], check=True)
    (output / 'engine-path.txt').write_text(str(package))
    print('Motor portátil validado: ' + str(package), flush=True)


if __name__ == '__main__':
    main()
