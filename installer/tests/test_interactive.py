"""Numbered entry never acts until chosen, keeps passwords out of output."""
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer import interactive
from a7c_installer.bundle import Bundle
from a7c_installer.operations import Installer
from test_installer import MemoryCamera, SETTINGS


class InteractiveTests(unittest.TestCase):
    def test_exit_does_not_connect_camera(self):
        with patch('a7c_installer.transport.sony_usb.SonyUsb') as usb, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(interactive.main(ask=lambda _: '0'), 0)
            usb.assert_not_called()

    def test_help_does_not_connect_camera(self):
        answers = iter(['9','0']); output=io.StringIO()
        with patch('a7c_installer.transport.sony_usb.SonyUsb') as usb, contextlib.redirect_stdout(output):
            interactive.main(ask=lambda _: next(answers))
            usb.assert_not_called()
        self.assertIn('Windows驱动恢复', output.getvalue())

    def test_blank_fields_and_password_keep_saved_values(self):
        settings, preserve = interactive.prompt_settings(SETTINGS.public(), ask=lambda _: '', secret=lambda _: '')
        self.assertTrue(preserve)
        self.assertEqual(settings.public(), SETTINGS.public())
        self.assertEqual(settings.password, '')

    def test_new_password_stays_out_of_repr(self):
        settings, preserve = interactive.prompt_settings(SETTINGS.public(), ask=lambda _: '', secret=lambda _: 'replacement-secret')
        self.assertFalse(preserve)
        self.assertNotIn('replacement-secret', repr(settings))

    def test_connect_then_update_reuses_secret_without_echo(self):
        camera=MemoryCamera(Bundle())
        Installer(camera, ftp_test=lambda _: None).install(SETTINGS)
        session=MagicMock(); session.__enter__.return_value=camera
        answers=iter(['1','2','','','','','0'])
        output=io.StringIO()
        def engine(cam,bundle,log):
            return Installer(cam,bundle,log,ftp_test=lambda _: None)
        with patch('a7c_installer.transport.sony_usb.SonyUsb',return_value=session), patch.object(interactive,'Installer',side_effect=engine), contextlib.redirect_stdout(output):
            interactive.main(ask=lambda _: next(answers),secret=lambda _: '')
        self.assertNotIn(SETTINGS.password,output.getvalue())
        self.assertEqual(camera.files['/setting/a7c-uploader/plainftp/password'],SETTINGS.password.encode()+b'\n')
        self.assertEqual(session.__enter__.call_count,2)

    @unittest.skipIf(sys.platform=='win32','POSIX entry is verified on macOS')
    def test_shell_entry_passes_arguments_through_directory_with_spaces(self):
        source=Path(__file__).resolve().parents[1]/'packaging/launchers/start.sh'
        with tempfile.TemporaryDirectory(prefix='A7C entry ') as directory:
            root=Path(directory);(root/'app').mkdir()
            shutil.copyfile(source,root/'start.sh')
            (root/'app/install.sh').write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            result=subprocess.run(['sh',str(root/'start.sh'),'--help','directory with spaces'],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout,'--help\ndirectory with spaces\n')
