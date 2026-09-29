"""Proteções da entrega contra motor antigo e sobrescrita de artefatos."""
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts'))
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


if __name__ == '__main__':
    unittest.main()
