"""Executar com o Python de Analisador/.venv; gera um motor portátil no Mac nativo."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Engine'))
from engine_packages import inventory, validate, probe


def freeze_command(work):
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--noupx',
               '--name', 'lume-engine',
               '--distpath', str(work / 'dist'), '--workpath', str(work / 'work'), '--specpath', str(work),
               '--paths', str(ROOT / 'Analisador'), '--paths', str(ROOT / 'Engine'),
               # Coerência com IA: fonte única em LumeCoerencia/, embutida no motor.
               '--paths', str(ROOT.parent / 'LumeCoerencia')]
    for module in ('fonte', 'spacy', 'thinc', 'pt_core_news_sm', 'srsly', 'cymem', 'preshed', 'murmurhash', 'blis',
                   'coerencia', 'anthropic'):
        command += ['--collect-all', module]
    command += ['--collect-data', 'docx', '--recursive-copy-metadata', 'spacy',
                '--copy-metadata', 'pt-core-news-sm', '--copy-metadata', 'fonte-revisor', '--copy-metadata', 'anthropic']
    for module in ('torch', 'tensorflow', 'cupy', 'jax', 'matplotlib', 'pytest'):
        command += ['--exclude-module', module]
    command.append(str(ROOT / 'Engine/lume_engine.py'))
    if sys.platform == 'darwin':
        command += ['--target-architecture', 'arm64']
    return command


def languagetool_source(explicit):
    """Corretor gramatical preparado por Scripts/preparar_languagetool.py."""
    source = (explicit or ROOT / 'Analisador/.languagetool').resolve()
    if not (source / 'languagetool-server.jar').is_file() or not (source / 'jre/bin/java').is_file():
        raise SystemExit('Corretor gramatical embutido ausente em ' + str(source) +
                         '. Execute Scripts/preparar_languagetool.py ou use --sem-languagetool.')
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languagetool', type=Path, help='Pasta preparada do corretor (padrão: Analisador/.languagetool)')
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
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit('PyInstaller falhou. Consulte ' + str(log))
    runtime = work / 'dist/lume-engine'
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
    # Inclui inventário de dependências e respectivas licenças coletadas pelo PyInstaller.
    freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (package / 'dependencias.txt').write_text(freeze)
    manifest = {'package_schema': 1, 'api_version': 1, 'report_schema': 1, 'decision_schema': 1,
                'engine_version': health['engine_version'], 'platform': 'darwin', 'architecture': 'arm64',
                'minimum_os': platform.mac_ver()[0], 'executable': 'runtime/lume-engine', 'files': inventory(package)}
    (package / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
    validate(package); probe(package, manifest)
    # Contrato real da CLI após congelamento e relocação; não usa Python externo.
    report = work / 'relatorio-teste'
    subprocess.run([str(package / 'runtime/lume-engine'), 'revisar', str(ROOT / 'Exemplo/Manuscrito-exemplo.docx'),
                    '--saida', str(report), '--tempo', 'passado'], cwd=work, env=environment, check=True, timeout=120)
    payload = json.loads((report / 'relatorio.json').read_text())
    assert payload['schema_version'] == 1 and payload['metadata']['versao_fonte'] == health['engine_version']
    assert len(payload['findings']) > 0
    if grammar:
        # O executável relocado inicia o corretor embutido com o Java do pacote.
        checked = work / 'relatorio-corretor'
        subprocess.run([str(package / 'runtime/lume-engine'), 'revisar', str(ROOT / 'Exemplo/Manuscrito-exemplo.docx'),
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
