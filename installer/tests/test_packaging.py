"""Reject release builds which omit this project's license."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_packaging', HERE / 'packaging/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'Installer.app'
        self.resources = self.app / 'Contents/Resources/a7c_installer/resources'
        help_dir = self.resources / 'help'
        help_dir.mkdir(parents=True)
        for name in (*release.GUIDES, 'THIRD_PARTY.md', 'validation.json'):
            (help_dir / name).write_bytes((HERE / name).read_bytes())
        (help_dir / 'LICENSE').write_bytes(release.LICENSE.read_bytes())
        (self.resources / 'camera.zip').write_bytes((HERE / 'a7c_installer/resources/camera.zip').read_bytes())
        self.windows = self.root / 'windows.zip'

    def windows_archive(self, include_license=True):
        with zipfile.ZipFile(self.windows, 'w') as archive:
            for path in self.resources.rglob('*'):
                if path.is_file() and (include_license or path.name != 'LICENSE'):
                    archive.write(path, 'Installer/_internal/a7c_installer/resources/' + path.relative_to(self.resources).as_posix())

    def test_matching_payload_guides_and_project_license_pass(self):
        self.windows_archive()
        release.verify_payloads(self.app, self.windows)

    def test_missing_macos_project_license_stops_packaging(self):
        self.windows_archive()
        (self.resources / 'help/LICENSE').unlink()
        with self.assertRaisesRegex(ValueError, 'macOS App project license'):
            release.verify_payloads(self.app, self.windows)

    def test_missing_windows_project_license_stops_packaging(self):
        self.windows_archive(include_license=False)
        with self.assertRaisesRegex(ValueError, 'Windows App project license'):
            release.verify_payloads(self.app, self.windows)


if __name__ == '__main__':
    unittest.main()
