"""Pacotes locais de motor: validar, testar, ativar atomicamente e reverter."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

API = 1
EXECUTABLE = 'runtime/lume-engine'
MAX_BYTES = 3_000_000_000
MAX_FILES = 40_000


def read_json(path):
    if path.stat().st_size > 12_000_000:
        raise ValueError('Manifesto ou estado excede o limite.')
    return json.loads(path.read_text(encoding='utf-8'))


def inside(path, root):
    return path.resolve(strict=True).is_relative_to(root.resolve(strict=True))


def inventory(root):
    root = Path(root).resolve(strict=True)
    result, total = {}, 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs[:] + files:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if relative == 'manifest.json':
                continue
            if path.is_symlink():
                if not inside(path, root):
                    raise ValueError('Link fora do pacote: ' + relative)
                result[relative] = {'link': os.readlink(path)}
                if name in dirs:
                    dirs.remove(name)
            elif path.is_file():
                total += path.stat().st_size
                if total > MAX_BYTES:
                    raise ValueError('O motor excede 3 GB.')
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                result[relative] = {'sha256': digest.hexdigest()}
            elif not path.is_dir():
                raise ValueError('Tipo de arquivo não permitido: ' + relative)
            if len(result) > MAX_FILES:
                raise ValueError('Pacote com arquivos demais.')
    return result


def validate(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Escolha uma pasta .lumemotor válida.')
    if (root / 'manifest.json').is_symlink():
        raise ValueError('Manifesto não pode ser um link.')
    manifest = read_json(root / 'manifest.json')
    if not isinstance(manifest, dict):
        raise ValueError('Manifesto inválido.')
    if any(manifest.get(k) != API for k in ('package_schema', 'api_version', 'report_schema', 'decision_schema')):
        raise ValueError('Este motor exige outra versão da interface Lume.')
    if manifest.get('platform') != sys.platform or manifest.get('architecture') != platform.machine():
        raise ValueError('O motor não é compatível com este sistema ou processador.')
    if sys.platform == 'darwin':
        minimum = tuple(map(int, manifest['minimum_os'].split('.')))
        current = tuple(map(int, platform.mac_ver()[0].split('.')))
        if current < minimum:
            raise ValueError('Este motor requer macOS ' + manifest['minimum_os'] + ' ou posterior.')
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}', manifest.get('engine_version', '')):
        raise ValueError('Versão de motor inválida.')
    if manifest.get('executable') != EXECUTABLE:
        raise ValueError('Executável inesperado.')
    files = manifest.get('files')
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise ValueError('Inventário inválido.')
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name or '\\' in name:
            raise ValueError('Caminho inválido no pacote.')
    if inventory(root) != files:
        raise ValueError('O conteúdo do motor não corresponde ao manifesto. Baixe ou gere o pacote novamente.')
    executable = root / EXECUTABLE
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError('Executável ausente ou sem permissão de execução.')
    return manifest


def probe(root, manifest):
    environment = dict(os.environ)
    # O filho é outro programa PyInstaller, não um processo auxiliar do congelado atual.
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    for key in ('PYTHONHOME', 'PYTHONPATH'):
        environment.pop(key, None)
    with tempfile.TemporaryFile() as log:
        subprocess.run([str((Path(root) / EXECUTABLE).resolve()), '--lume-probe'],
                       cwd=str(root), env=environment, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=120)
        log.seek(0)
        output = log.read(1_000_000).decode('utf-8', errors='replace')
    # A última linha é o contrato; avisos de dependências podem precedê-la.
    data = json.loads(output.strip().splitlines()[-1])
    if any(data.get(k) != API for k in ('api_version', 'report_schema', 'decision_schema')) or data.get('engine_version') != manifest['engine_version'] or not data.get('healthy'):
        raise ValueError('O motor não passou no teste de funcionamento.')
    return data


def package_id(value):
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value)):
        raise ValueError('Referência de motor inválida.')
    return value


def read_state(support):
    path = Path(support) / 'engine-state.json'
    if not path.exists():
        return {'schema_version': 1, 'active': None, 'previous': None}
    state = read_json(path)
    if not isinstance(state, dict) or state.get('schema_version') != 1 or not {'active', 'previous'} <= state.keys():
        raise ValueError('Estado dos motores incompatível.')
    package_id(state.get('active')); package_id(state.get('previous'))
    return state


def write_state(support, state):
    support = Path(support)
    fd, temporary = tempfile.mkstemp(prefix='.engine-state-', dir=support)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, support / 'engine-state.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(support):
    support = Path(support)
    support.mkdir(parents=True, exist_ok=True)
    with (support / '.engine-update.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Outra atualização está em andamento.') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def install(source, support):
    """Nunca altera o app nem o motor ativo; a troca ocorre após validação e probe."""
    source, support = Path(source), Path(support)
    with locked(support):
        state = read_state(support)
        validate(source)
        engines = support / 'Engines'; engines.mkdir(exist_ok=True)
        identifier = uuid.uuid4().hex
        stage, destination = engines / ('.staging-' + identifier), engines / identifier
        try:
            shutil.copytree(source, stage, symlinks=True)
            validate(stage)
            os.replace(stage, destination)
            manifest = validate(destination)
            probe(destination, manifest)  # testa no caminho definitivo, incluindo os links internos
            write_state(support, {'schema_version': 1, 'active': identifier, 'previous': state['active']})
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            # Uma interrupção após a troca atômica não pode apagar o novo motor ativo.
            try:
                active = read_state(support)['active']
            except (ValueError, OSError):
                active = identifier  # preserva a cópia se não puder conferir o ponteiro
            if active != identifier:
                shutil.rmtree(destination, ignore_errors=True)
            raise
        return manifest


def switch(support, bundled, reset=False):
    support, bundled = Path(support), Path(bundled)
    with locked(support):
        try:
            state = read_state(support)
        except (ValueError, OSError):
            if not reset:
                raise
            # Restauração explícita recupera até um ponteiro corrompido, preservando uma cópia.
            old = support / 'engine-state.json'
            if old.exists():
                shutil.copy2(old, support / ('engine-state-recovery-' + uuid.uuid4().hex + '.json'))
            state = {'schema_version': 1, 'active': None, 'previous': None}
        target = None if reset else state['previous']
        root = support / 'Engines' / target if target else bundled
        manifest = validate(root)
        probe(root, manifest)
        write_state(support, {'schema_version': 1, 'active': target, 'previous': state['active']})
        return manifest
