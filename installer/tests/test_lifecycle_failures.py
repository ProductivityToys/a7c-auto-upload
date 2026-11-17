"""Exercise reconnect/recovery at every persistent mutation, without USB.

The camera boundary models a disconnected command before or after its effect;
it does not emulate NAND power-loss durability or native display unloading.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.bundle import Bundle, sha256
from a7c_installer.configuration import InstallerError
from a7c_installer.operations import (
    BACKUP, CONFIG, DIAG_ENABLE, DIAG_FILES, DIAG_TOKEN, ENABLE, Installer,
    LOADER, META, PASSWORD, PENDING, PRELOAD, STATE,
)
from test_installer import MemoryCamera, SETTINGS


class DisconnectCamera(MemoryCamera):
    def __init__(self, bundle):
        super().__init__(bundle)
        self.checkpoints = []
        self.fail_at = None

    def mutation(self, name, operation, *args, **kwargs):
        for phase in ('before', 'after'):
            self.checkpoints.append((name, phase, args[0] if args else None))
            if len(self.checkpoints) == self.fail_at:
                self.fail_at = None
                raise InstallerError('simulated lost USB response')
            if phase == 'before':
                result = operation(*args, **kwargs)
        return result

    def atomic(self, *args, **kwargs):
        return self.mutation('atomic', super().atomic, *args, **kwargs)

    def remove(self, *args, **kwargs):
        return self.mutation('remove', super().remove, *args, **kwargs)

    def sync(self):
        return self.mutation('sync', super().sync)

    def directories(self, paths):
        return self.mutation('directories', super().directories, paths)

    def quiesce(self, retire_display=True):
        return self.mutation('quiesce', super().quiesce, retire_display)

    def cleanup_staging(self, paths):
        return self.mutation('cleanup-staging', super().cleanup_staging, paths)


def application_files(camera):
    return {p: sha256(v) for p, v in camera.files.items() if not p.startswith(STATE + '/')}


class LifecycleFailureTests(unittest.TestCase):
    def setUp(self):
        self.bundle = Bundle()
        self.scenarios = 0

    def engine(self, camera):
        return Installer(camera, self.bundle, ftp_test=lambda _: None)

    def prepare(self, installed=False, diagnostics=False):
        camera = DisconnectCamera(self.bundle)
        camera.files[PRELOAD] = b'/another-app.so # keep\n'
        camera.files['/setting/a7c-uploader/user-note.txt'] = b'not owned'
        if installed:
            self.engine(camera).install(SETTINGS)
        if diagnostics:
            for path in DIAG_FILES | {DIAG_ENABLE, DIAG_TOKEN}:
                camera.files[path] = ('private ' + path).encode()
            metadata = json.loads(camera.files[META])
            metadata['files'].update({p: sha256(camera.files[p]) for p in DIAG_FILES})
            camera.files[META] = json.dumps(metadata).encode()
        camera.checkpoints.clear()
        return camera

    def exercise_disconnects(self, prepare, operation):
        baseline = prepare()
        before = application_files(baseline)
        operation(self.engine(baseline))
        committed = application_files(baseline)
        checkpoints = baseline.checkpoints
        for index, checkpoint in enumerate(checkpoints, 1):
            with self.subTest(boundary=index, command=checkpoint):
                camera = prepare()
                camera.fail_at = index
                try:
                    operation(self.engine(camera))
                except InstallerError:
                    pass
                self.assertIsNone(camera.fail_at, 'boundary was not reached')
                if PENDING in camera.files:
                    self.engine(camera).restore()
                    self.assertEqual(application_files(camera), before)
                else:
                    self.assertIn(application_files(camera), (before, committed))
                self.assertNotIn(PENDING, tuple(camera.files))
                self.assertEqual(camera.files['/mnt/sd/DCIM/photo.JPG'], b'KEEP')
                self.assertEqual(camera.files['/mnt/sd/receipt'], b'KEEP')
                self.assertEqual(camera.files['/setting/a7c-uploader/user-note.txt'], b'not owned')
                self.assertLessEqual(camera.files.get(PRELOAD, b'').split().count(LOADER.encode()), 1)
                self.scenarios += 1
        # Keep the sweep non-vacuous if future refactoring removes a stage.
        self.assertGreater(len(checkpoints), 40)

    def test_fresh_install_disconnect_at_each_mutation(self):
        self.exercise_disconnects(self.prepare, lambda engine: engine.install(SETTINGS))

    def test_configuration_update_disconnect_at_each_mutation(self):
        updated = replace(SETTINGS, host='192.168.1.21', password='new-test-secret', photos=True)
        self.exercise_disconnects(lambda: self.prepare(installed=True),
                                 lambda engine: engine.install(updated, display=False))

    def test_uninstall_disconnect_at_each_mutation_including_diagnostics(self):
        self.exercise_disconnects(lambda: self.prepare(installed=True, diagnostics=True),
                                 lambda engine: engine.uninstall())

    def test_recovery_can_be_retried_at_every_mutation(self):
        def prepare_restore():
            camera = self.prepare(installed=True)
            self.engine(camera).install(replace(SETTINGS, password='replacement', photos=True))
            camera.checkpoints.clear()
            return camera

        baseline = prepare_restore()
        self.engine(baseline).restore()
        expected = application_files(baseline)
        for index, checkpoint in enumerate(baseline.checkpoints, 1):
            with self.subTest(boundary=index, command=checkpoint):
                camera = prepare_restore()
                backup = {p: sha256(v) for p, v in camera.files.items() if p.startswith(BACKUP + '/')}
                camera.fail_at = index
                try:
                    self.engine(camera).restore()
                except InstallerError:
                    pass
                self.assertIsNone(camera.fail_at)
                self.engine(camera).restore()
                self.assertEqual(application_files(camera), expected)
                self.assertEqual({p: sha256(v) for p, v in camera.files.items() if p.startswith(BACKUP + '/')}, backup)
                self.assertNotIn(PENDING, tuple(camera.files))

    def test_repeated_updates_and_uninstall_leave_no_owned_preload_or_active_secret(self):
        camera = self.prepare()
        engine = self.engine(camera)
        for index in range(5):
            engine.install(replace(SETTINGS, photos=bool(index % 2)), display=bool(index % 2))
            self.assertEqual(camera.files[PRELOAD].split().count(LOADER.encode()), 1)
            self.assertFalse(engine.inspect()['pending_recovery'])
        engine.uninstall()
        expected = {p: sha256(v) for p, v in camera.files.items()}
        with self.assertRaisesRegex(InstallerError, '没有发现'):
            engine.uninstall()
        self.assertEqual({p: sha256(v) for p, v in camera.files.items()}, expected)
        for path in set(self.bundle.files) | {CONFIG, PASSWORD, META, ENABLE}:
            self.assertNotIn(path, tuple(camera.files))
        self.assertEqual(camera.files[PRELOAD], b'/another-app.so # keep\n')

    def test_uninstall_removes_staging_files_left_by_interrupted_transfer(self):
        camera = self.prepare(installed=True)
        for path in set(self.bundle.files) | {CONFIG, PASSWORD, META, ENABLE, PRELOAD}:
            camera.files[path + '.installer-next'] = b'incomplete transfer'
        camera.files['/setting/a7c-uploader/user-note.txt.installer-next'] = b'not ours'
        self.engine(camera).uninstall()
        self.assertFalse(any(p + '.installer-next' in camera.files
                             for p in set(self.bundle.files) | {CONFIG, PASSWORD, META, ENABLE, PRELOAD}))
        self.assertEqual(camera.files['/setting/a7c-uploader/user-note.txt.installer-next'], b'not ours')

    def test_restore_removes_staging_secret_left_by_interrupted_transfer(self):
        camera = self.prepare(installed=True)
        self.engine(camera).install(replace(SETTINGS, password='replacement'))
        camera.files[PASSWORD + '.installer-next'] = b'partial new password'
        self.engine(camera).restore()
        self.assertEqual(camera.files[PASSWORD], SETTINGS.password.encode() + b'\n')
        self.assertNotIn(PASSWORD + '.installer-next', tuple(camera.files))


if __name__ == '__main__':
    unittest.main()
