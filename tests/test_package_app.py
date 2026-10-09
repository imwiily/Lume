"""Proteções da entrega contra motor antigo e sobrescrita de artefatos."""
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_engine
import package_app


class AppPackagingTests(unittest.TestCase):
    def test_old_engine_is_rejected_before_execution_or_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'delivery'
            with patch.object(package_app, 'validate', return_value={'engine_version': '0.0.1'}), \
                 patch.object(package_app, 'probe') as probe:
                with self.assertRaisesRegex(ValueError, 'diverge'):
                    package_app.package('Lume.app', 'old.lumemotor', output)
                probe.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_delivery_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / 'Lume.app.zip'
            sentinel.write_bytes(b'existing delivery')
            with patch.object(package_app, 'validate') as validate:
                with self.assertRaises(FileExistsError):
                    package_app.package('Lume.app', 'engine.lumemotor', output)
                validate.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b'existing delivery')

    def test_unrelated_app_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'Other.app'
            (app / 'Contents').mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'other.app'}))
            with patch.object(package_app, 'validate', return_value={'engine_version': package_app.source_version()}), \
                 patch.object(package_app, 'probe'):
                with self.assertRaisesRegex(ValueError, 'Lume compilado'):
                    package_app.package(app, 'engine.lumemotor', root / 'delivery')
            self.assertFalse((root / 'delivery').exists())

    def test_app_cannot_announce_older_macos_than_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'Lume.app'
            (app / 'Contents').mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(
                {'CFBundleIdentifier': 'br.fonte.editorial', 'LSMinimumSystemVersion': '13.0'}))
            manifest = {'engine_version': package_app.source_version(), 'minimum_os': '27.0'}
            with patch.object(package_app, 'validate', return_value=manifest), patch.object(package_app, 'probe'):
                with self.assertRaisesRegex(ValueError, 'anuncia macOS 13.0, mas o motor exige macOS 27.0'):
                    package_app.package(app, 'engine.lumemotor', root / 'delivery')
            self.assertFalse((root / 'delivery').exists())


@unittest.skipUnless(shutil.which('clang') and Path('/usr/bin/vtool').exists(), 'requer clang e vtool (Xcode)')
class EngineMinimumOSTests(unittest.TestCase):
    """O manifesto declara o maior minos dos binários, não o macOS de quem montou."""

    def test_highest_binary_requirement_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'main.c').write_text('int main(void) { return 0; }\n')
            for name, version in (('old', '12.0'), ('lib/new', '14.2')):
                (root / name).parent.mkdir(exist_ok=True)
                subprocess.run(['clang', '-arch', 'arm64', '-mmacosx-version-min=' + version,
                                str(root / 'main.c'), '-o', str(root / name)], check=True)
            # Classe Java (mesmo início 0xcafebabe) e texto não são binários do macOS.
            (root / 'lib/A.class').write_bytes(b'\xca\xfe\xba\xbe\x00\x00\x00\x41' + b'\x00' * 16)
            (root / 'leia.txt').write_text('texto')
            self.assertEqual(build_engine.minimum_os(root), '14.2')

    def test_package_without_binaries_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'leia.txt').write_text('texto')
            with self.assertRaises(SystemExit):
                build_engine.minimum_os(directory)


class EngineContentsTests(unittest.TestCase):
    def test_project_folders_never_enter_the_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            for name in ('fonte/__init__.py', 'coerencia/analise.py'):
                (runtime / '_internal' / name).parent.mkdir(parents=True, exist_ok=True)
                (runtime / '_internal' / name).write_text('')
            build_engine.own_packages_only(runtime)
            leaked = runtime / '_internal/coerencia/Projetos/livro/cenas/c1.json'
            leaked.parent.mkdir(parents=True)
            leaked.write_text('{}')
            with self.assertRaisesRegex(SystemExit, 'Projetos'):
                build_engine.own_packages_only(runtime)


if __name__ == '__main__':
    unittest.main()
