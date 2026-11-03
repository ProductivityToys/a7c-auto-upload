"""Select the user API matching the already installed Windows kernel driver."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.transport.sony_usb import usb_modules
from a7c_installer.configuration import InstallerError


class BackendTests(unittest.TestCase):
    def test_libusb_win32_uses_its_installed_dll_without_the_libusbK_bridge(self):
        backend = object()
        with patch.dict('os.environ', {'SystemRoot': '/windows'}), \
                patch('pathlib.Path.is_file', return_value=True), \
                patch('usb.backend.libusb0.get_backend', return_value=backend) as legacy, \
                patch('usb.backend.libusb1.get_backend') as modern:
            _, result = usb_modules(legacy=True)
            self.assertIs(result, backend)
            library = legacy.call_args.kwargs['find_library']('usb')
            self.assertEqual(Path(library), Path('/windows/System32/libusb0.dll'))
            modern.assert_not_called()

    def test_other_drivers_keep_the_libusb1_backend(self):
        backend = object()
        with patch('usb.backend.libusb1.get_backend', return_value=backend), \
                patch('usb.backend.libusb0.get_backend') as legacy:
            _, result = usb_modules()
            self.assertIs(result, backend)
            legacy.assert_not_called()

    def test_missing_legacy_runtime_does_not_silently_choose_the_wrong_backend(self):
        with patch.dict('os.environ', {'SystemRoot': '/windows'}), \
                patch('pathlib.Path.is_file', return_value=False), \
                patch('usb.backend.libusb1.get_backend') as modern:
            with self.assertRaises(InstallerError):
                usb_modules(legacy=True)
            modern.assert_not_called()
