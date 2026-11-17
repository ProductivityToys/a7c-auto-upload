"""Run production staging commands on real temporary files, never on USB."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.configuration import InstallerError
from a7c_installer.transport.sony_usb import SonyUsb


@unittest.skipIf(os.name == 'nt', 'POSIX command execution is covered on macOS')
class AtomicStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='A7C staging 中文 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'password'
        self.stage = self.root / 'password.installer-next'
        self.target.write_bytes(b'old complete configuration')
        self.camera = SonyUsb()
        self.camera.exists = lambda path: Path(path).exists()
        self.camera.read = lambda path: Path(path).read_bytes()
        self.camera.write = lambda path, data: Path(path).write_bytes(data)
        self.commands = []

        def command(text):
            self.commands.append(text)
            # Only replace the camera's BusyBox executable. The production
            # quoting, symlink checks, chmod, mv and rm arguments remain intact.
            result = subprocess.run(['sh', '-c', text.replace('/bin/busybox ', '')],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode:
                raise InstallerError('simulated camera shell error')
            return result.stdout

        self.camera.command = command

    def test_success_replaces_whole_file_and_removes_temporary(self):
        self.camera.atomic(str(self.target), b'new complete configuration')
        self.assertEqual(self.target.read_bytes(), b'new complete configuration')
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_short_transfer_does_not_replace_original_and_cleanup_removes_partial(self):
        self.camera.write = lambda path, data: Path(path).write_bytes(data[:7])
        with self.assertRaisesRegex(InstallerError, '读回不符'):
            self.camera.atomic(str(self.target), b'new complete configuration')
        self.assertEqual(self.target.read_bytes(), b'old complete configuration')
        self.assertEqual(self.stage.read_bytes(), b'new com')
        self.camera.cleanup_staging([str(self.target)])
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.target.read_bytes(), b'old complete configuration')

    def test_lost_publish_response_after_rename_is_safe_to_cleanup_and_retry(self):
        execute = self.camera.command

        def lose_response(text):
            result = execute(text)
            if '/bin/busybox mv ' in text:
                raise InstallerError('USB response lost after rename')
            return result

        self.camera.command = lose_response
        with self.assertRaisesRegex(InstallerError, 'response lost'):
            self.camera.atomic(str(self.target), b'complete new file')
        self.assertEqual(self.target.read_bytes(), b'complete new file')
        self.camera.command = execute
        self.camera.cleanup_staging([str(self.target)])
        self.camera.atomic(str(self.target), b'complete retry')
        self.assertEqual(self.target.read_bytes(), b'complete retry')
        self.assertFalse(self.stage.exists())

    def test_cleanup_is_explicit_single_command_and_keeps_unowned_files(self):
        self.stage.write_bytes(b'partial secret')
        unowned = self.root / 'unrelated.installer-next'
        unowned.write_bytes(b'keep')
        special = self.root / "user's $(touch SHOULD_NOT_EXIST);file"
        Path(str(special) + '.installer-next').write_bytes(b'partial')
        self.camera.cleanup_staging([str(self.target), str(special)])
        self.assertEqual(len(self.commands), 1)
        self.assertFalse(self.stage.exists())
        self.assertFalse(Path(str(special) + '.installer-next').exists())
        self.assertEqual(unowned.read_bytes(), b'keep')
        self.assertEqual(self.target.read_bytes(), b'old complete configuration')
        self.assertFalse(Path('SHOULD_NOT_EXIST').exists())
        self.assertNotIn('rm -r', self.commands[0])
        self.assertIn(shlex.quote(str(special) + '.installer-next'), self.commands[0])

    def test_staging_symlink_is_not_followed_and_cleanup_keeps_its_target(self):
        outside = self.root / 'unrelated-original'
        outside.write_bytes(b'keep')
        self.stage.symlink_to(outside)
        with self.assertRaises(InstallerError):
            self.camera.atomic(str(self.target), b'replacement')
        self.assertEqual(outside.read_bytes(), b'keep')
        self.camera.cleanup_staging([str(self.target)])
        self.assertFalse(self.stage.is_symlink())
        self.assertEqual(outside.read_bytes(), b'keep')

    def test_long_terminal_command_preserves_quotes_unicode_and_exit_status(self):
        expected = "a'中文 $literal `literal` \"quoted\"\n" * 90
        class Terminal:
            wire = b''
            parts = []
            def writeTerminal(inner, wire):
                inner.wire += wire
                self.assertTrue(all(len(line) <= 800 for line in wire.splitlines()))
                if b"'__A7C_BEGIN_'" not in wire:
                    return
                result = subprocess.run(['sh'], input=inner.wire, capture_output=True, timeout=3)
                inner.wire = b''
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, b'')
                inner.parts = [result.stdout[i:i + 17] for i in range(0, len(result.stdout), 17)]
            def readTerminal(inner):
                return inner.parts.pop(0) if inner.parts else b''
        camera = SonyUsb()
        camera.terminal = True
        camera.dev = Terminal()
        self.assertEqual(camera.command('printf %s ' + shlex.quote(expected)), expected.strip())
        with self.assertRaises(InstallerError):
            camera.command('false' + ' ' * 3500)


if __name__ == '__main__':
    unittest.main()
