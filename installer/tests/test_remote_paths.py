"""Camera paths must stay POSIX even when the installer runs on Windows."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class RemotePathTests(unittest.TestCase):
    def test_directory_preparation_terminates_and_keeps_linux_ancestors(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            "import sys,json;sys.path.insert(0," + repr(str(root)) + ");"
            "from a7c_installer.transport.sony_usb import SonyUsb;"
            "camera=SonyUsb();commands=[];camera.command=commands.append;"
            "camera.directories(['/setting/a7c-installer/backup',"
            "'/setting/a7c-uploader/plainftp']);print(json.dumps(commands))"
        )
        result = subprocess.run([sys.executable, '-c', source], capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = json.loads(result.stdout)
        self.assertEqual(len(commands), 1)
        command = commands[0]
        self.assertNotIn('\\', command)
        for path in ('/setting/a7c-installer', '/setting/a7c-installer/backup',
                     '/setting/a7c-uploader', '/setting/a7c-uploader/plainftp'):
            self.assertIn('[ ! -L ' + path + ' ]', command)
        self.assertNotIn('[ ! -L / ]', command)
        self.assertIn('/bin/busybox mkdir -p', command)
