import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
import engine_packages as packages


class EnginePackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lume motor d'água ")
        self.root = Path(self.temporary.name)
        self.support = self.root / 'dados'
        self.base = self.make_package('base', '0.2.1')

    def tearDown(self):
        self.temporary.cleanup()

    def make_package(self, name, version, fail=False):
        root = self.root / (name + '.lumemotor')
        (root / 'runtime').mkdir(parents=True)
        script = root / packages.EXECUTABLE
        data = {'healthy': True, 'api_version': 1, 'engine_version': version, 'report_schema': 1, 'decision_schema': 1}
        script.write_text('#!' + sys.executable + '\nimport sys\n' + ('sys.exit(9)\n' if fail else 'print(' + repr(json.dumps(data)) + ')\n'))
        script.chmod(0o755)
        manifest = dict(package_schema=1, api_version=1, report_schema=1, decision_schema=1,
                        platform=sys.platform, architecture=platform.machine(), engine_version=version,
                        executable=packages.EXECUTABLE, minimum_os=platform.mac_ver()[0] or '0', files=packages.inventory(root))
        (root / 'manifest.json').write_text(json.dumps(manifest))
        return root

    def edit_manifest(self, root, **changes):
        path = root / 'manifest.json'
        data = json.loads(path.read_text()); data.update(changes); path.write_text(json.dumps(data))

    def test_install_and_relocate_uses_copy(self):
        source = self.make_package('new', '0.3.0')
        packages.install(source, self.support)
        state = packages.read_state(self.support)
        installed = self.support / 'Engines' / state['active']
        self.assertEqual(packages.validate(installed)['engine_version'], '0.3.0')
        self.assertNotEqual(source, installed)
        self.assertIsNone(state['previous'])
        self.assertFalse((self.base / 'engine-state.json').exists())

    def test_rollback_and_reset_preserve_versions(self):
        packages.install(self.make_package('v1', '0.3.0'), self.support)
        first = packages.read_state(self.support)['active']
        packages.install(self.make_package('v2', '0.4.0'), self.support)
        second = packages.read_state(self.support)['active']
        packages.switch(self.support, self.base)
        self.assertEqual(packages.read_state(self.support)['active'], first)
        packages.switch(self.support, self.base, reset=True)
        self.assertIsNone(packages.read_state(self.support)['active'])
        self.assertTrue((self.support / 'Engines' / second).is_dir())

    def test_failed_probe_preserves_active(self):
        packages.install(self.base, self.support)
        before = (self.support / 'engine-state.json').read_bytes()
        with self.assertRaises(subprocess.CalledProcessError):
            packages.install(self.make_package('broken', '0.3.0', fail=True), self.support)
        self.assertEqual((self.support / 'engine-state.json').read_bytes(), before)
        self.assertEqual(len(list((self.support / 'Engines').iterdir())), 1)

    def test_failed_atomic_save_preserves_active(self):
        packages.install(self.base, self.support)
        before = (self.support / 'engine-state.json').read_bytes()
        with patch.object(packages, 'write_state', side_effect=OSError('disco cheio')):
            with self.assertRaises(OSError):
                packages.install(self.make_package('new', '0.3.0'), self.support)
        self.assertEqual((self.support / 'engine-state.json').read_bytes(), before)
        self.assertEqual(len(list((self.support / 'Engines').iterdir())), 1)

    def test_interrupt_after_commit_keeps_active_engine(self):
        original_write = packages.write_state
        def commit_then_interrupt(support, state):
            original_write(support, state)
            raise KeyboardInterrupt()
        with patch.object(packages, 'write_state', side_effect=commit_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                packages.install(self.base, self.support)
        active = self.support / 'Engines' / packages.read_state(self.support)['active']
        self.assertEqual(packages.validate(active)['engine_version'], '0.2.1')

    def test_tampered_file_rejected_before_activation(self):
        (self.base / packages.EXECUTABLE).write_text('alterado')
        with self.assertRaises(ValueError): packages.install(self.base, self.support)
        self.assertFalse((self.support / 'engine-state.json').exists())

    def test_wrong_architecture_and_protocol(self):
        for field, value in [('architecture', 'wrong'), ('api_version', 2), ('report_schema', 2)]:
            source = self.make_package(field, '0.3.0')
            self.edit_manifest(source, **{field: value})
            with self.assertRaises(ValueError): packages.validate(source)

    def test_outside_link_rejected(self):
        (self.base / 'runtime/escape').symlink_to(self.root)
        with self.assertRaises(ValueError): packages.validate(self.base)

    def test_internal_link_preserved(self):
        (self.base / 'runtime/link').symlink_to('lume-engine')
        self.edit_manifest(self.base, files=packages.inventory(self.base))
        packages.install(self.base, self.support)
        root = self.support / 'Engines' / packages.read_state(self.support)['active']
        self.assertTrue((root / 'runtime/link').is_symlink())

    def test_traversal_manifest_rejected(self):
        self.edit_manifest(self.base, files={'../outside': {'sha256': 'a' * 64}})
        with self.assertRaises(ValueError): packages.validate(self.base)

    def test_corrupt_pointer_can_restore_base(self):
        self.support.mkdir(); (self.support / 'engine-state.json').write_text('invalid')
        packages.switch(self.support, self.base, reset=True)
        self.assertIsNone(packages.read_state(self.support)['active'])
        self.assertEqual(len(list(self.support.glob('engine-state-recovery-*'))), 1)

    def test_incomplete_json_pointer_can_restore_base(self):
        self.support.mkdir()
        (self.support / 'engine-state.json').write_text('{"schema_version": 1}')
        packages.switch(self.support, self.base, reset=True)
        self.assertIsNone(packages.read_state(self.support)['active'])

    def test_lock_blocks_second_update(self):
        with packages.locked(self.support):
            with self.assertRaises(ValueError): packages.install(self.base, self.support)

    def test_real_controller_install_arguments(self):
        controller = Path(__file__).resolve().parents[1] / 'packaging/lume_engine.py'
        completed = subprocess.run([sys.executable, str(controller), '--lume-install', '--support', str(self.support), '--package', str(self.base)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
