"""Pairing/unpairing of the opt-in read-only Wi-Fi diagnostics."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from a7c_installer.bundle import Bundle
from a7c_installer.configuration import InstallerError
from a7c_installer.operations import Installer, DIAG_ENABLE, DIAG_TOKEN, META, ENABLE, CONFIG, PASSWORD
from test_installer import MemoryCamera, SETTINGS

TOKEN = '0123456789abcdef' * 4


def diag_bundle(directory):
    """The shipped bundle plus the three diagnostic files and feature flag."""
    path = Path(directory) / 'camera.zip'
    with zipfile.ZipFile(Bundle().path) as original:
        files = {n: original.read(n) for n in original.namelist()}
    manifest = json.loads(files.pop('manifest.json'))
    extra = {'a7c-diag/listener': b'\x7fELF test listener', 'a7c-diag/diag.sh': b'#!/bin/ash\n',
             'a7c-diag/start.sh': b'#!/bin/ash\n'}
    extra['a7c-diag/listener.sha256'] = (hashlib.sha256(extra['a7c-diag/listener']).hexdigest() + '\n').encode()
    for name, value in extra.items():
        files[name] = value
        manifest['files'][name] = {'target': '/setting/' + name, 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
    manifest['payload_version'] += '-diag-test'
    manifest['features'] = manifest.get('features', []) + ['wifi-diag']
    with zipfile.ZipFile(path, 'w') as archive:
        for name, value in files.items():
            archive.writestr(name, value)
        archive.writestr('manifest.json', json.dumps(manifest))
    return Bundle(path)


class DiagCamera(MemoryCamera):
    def __init__(self, bundle):
        super().__init__(bundle)
        self.diag_running = False

    def diag_stop(self, wait=30):
        self.events.append(('diag-stop',))
        self.diag_running = False

    def diag_start(self):
        self.events.append(('diag-start',))
        self.diag_running = DIAG_ENABLE in self.files and DIAG_TOKEN in self.files
        return 77 if self.diag_running else None


class DiagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundle = diag_bundle(self.tmp.name)
        self.camera = DiagCamera(self.bundle)
        self.engine = Installer(self.camera, self.bundle, ftp_test=lambda s: None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pairing_requires_current_install_then_writes_key_and_starts(self):
        with self.assertRaises(InstallerError):
            self.engine.diag_enable(TOKEN)
        self.assertNotIn(DIAG_TOKEN, self.camera.files)
        self.engine.install(SETTINGS)
        self.assertFalse(self.engine.inspect()['wifi_diag'])
        result = self.engine.diag_enable(TOKEN)
        self.assertEqual(result, {'wifi_diag': True, 'listener_pid': 77})
        self.assertEqual(self.camera.files[DIAG_TOKEN], (TOKEN + '\n').encode())
        self.assertEqual([e for e in self.camera.events if e[0] == 'write' and e[1] == DIAG_TOKEN][0][2], 0o600)
        self.assertTrue(self.engine.inspect()['wifi_diag'])
        events = [e[0] if e[0] != 'write' else e[1] for e in self.camera.events[-6:]]
        self.assertLess(events.index('diag-stop'), events.index(DIAG_TOKEN))

    def test_bad_keys_and_payload_without_feature_are_rejected(self):
        self.engine.install(SETTINGS)
        for bad in ('', 'x' * 64, TOKEN.upper(), TOKEN[:-1], TOKEN + '0'):
            with self.subTest(bad=bad), self.assertRaises(InstallerError):
                self.engine.diag_enable(bad)
        plain = Installer(self.camera, Bundle(), ftp_test=lambda s: None)
        with self.assertRaises(InstallerError):
            plain.diag_enable(TOKEN)

    def test_reinstall_keeps_pairing_and_uninstall_removes_it(self):
        self.engine.install(SETTINGS)
        self.engine.diag_enable(TOKEN)
        self.engine.install(None, reuse=True)
        self.assertEqual(self.camera.files[DIAG_TOKEN], (TOKEN + '\n').encode())
        self.assertIn('/setting/a7c-diag/listener', json.loads(self.camera.files[META])['files'])
        self.engine.uninstall()
        for path in (DIAG_TOKEN, DIAG_ENABLE, '/setting/a7c-diag/listener', '/setting/a7c-diag/start.sh', ENABLE, CONFIG, PASSWORD):
            self.assertNotIn(path, self.camera.files)

    def test_release_installer_accepts_and_updates_a_debug_equipped_camera(self):
        self.engine.install(SETTINGS)
        self.engine.diag_enable(TOKEN)
        release = Installer(self.camera, Bundle(), ftp_test=lambda s: None)
        self.assertEqual(release.inspect()['installed_version'], self.bundle.version)
        release.install(None, reuse=True)
        # Release files replace the managed set; the debug add-on and pairing stay.
        self.assertNotIn('/setting/a7c-diag/listener', json.loads(self.camera.files[META])['files'])
        self.assertIn('/setting/a7c-diag/listener', self.camera.files)
        release.uninstall()
        for path in ('/setting/a7c-diag/listener', '/setting/a7c-diag/start.sh', DIAG_TOKEN, DIAG_ENABLE):
            self.assertNotIn(path, self.camera.files)

    def test_disable_removes_key_and_stops_listener(self):
        self.engine.install(SETTINGS)
        self.engine.diag_enable(TOKEN)
        self.assertEqual(self.engine.diag_disable(), {'wifi_diag': False})
        self.assertNotIn(DIAG_TOKEN, self.camera.files)
        self.assertNotIn(DIAG_ENABLE, self.camera.files)
        self.assertFalse(self.camera.diag_running)
        self.assertIn(ENABLE, self.camera.files)


if __name__ == '__main__':
    unittest.main()
