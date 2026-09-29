"""Inclui um motor validado no app Release e gera uma entrega autocontida."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Engine'))
from engine_packages import probe, validate


def source_version():
    tree = ast.parse((ROOT / 'Analisador/fonte/__init__.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError('Versão do FONTE ausente nos fontes.')


def package(app, engine, output):
    app, engine, output = (Path(path).resolve() for path in (app, engine, output))
    if output.exists():
        raise FileExistsError('Escolha uma pasta de saída nova: ' + str(output))
    manifest = validate(engine)
    if manifest['engine_version'] != source_version():
        raise ValueError('O motor selecionado diverge da versão FONTE deste projeto.')
    probe(engine, manifest)
    with (app / 'Contents/Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    if info.get('CFBundleIdentifier') != 'br.fonte.editorial':
        raise ValueError('Selecione o aplicativo Lume compilado.')
    # Uma saída nova impede mistura de versões e sobrescrita de entregas anteriores.
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'Lume.app'
    subprocess.run(['/usr/bin/ditto', str(app), str(target)], check=True)
    embedded = target / 'Contents/Resources/Engine.lumemotor'
    if embedded.is_symlink():
        embedded.unlink()
    elif embedded.exists():
        shutil.rmtree(embedded)
    subprocess.run(['/usr/bin/ditto', str(engine), str(embedded)], check=True)
    # PyInstaller já assinou os Mach-O internos; assina somente o bundle externo.
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(target)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(target)], check=True)
    embedded_manifest = validate(embedded)
    health = probe(embedded, embedded_manifest)
    archive = output / 'Lume.app.zip'
    subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                    str(target), str(archive)], check=True)
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    checksum = digest.hexdigest()
    release = {
        'app_version': info['CFBundleShortVersionString'],
        'app_build': info['CFBundleVersion'],
        'engine_version': embedded_manifest['engine_version'],
        'architecture': embedded_manifest['architecture'],
        'minimum_os': embedded_manifest['minimum_os'],
        'signature': 'ad-hoc',
        'probe': health,
        'archive': archive.name,
        'sha256': checksum,
    }
    (output / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
    print(json.dumps(release, indent=2))
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    package(args.app, args.engine, args.output)
