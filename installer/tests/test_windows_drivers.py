"""Driver transaction regressions. Fake PnP boundary never touches host USB."""
from contextlib import nullcontext
import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.drivers.windows import DriverManager, target
from a7c_installer.configuration import InstallerError
from a7c_installer.drivers.windows_native import WindowsBackend

NORMAL = {'id': 'USB\\VID_054C&PID_0D28\\CAMERA', 'bus_name': 'ILCE-7C',
          'driver': 'USBSTOR', 'inf': 'usbstor.inf', 'hardware_id': 'USB\\VID_054C&PID_0D28'}
SERVICE = {'id': 'USB\\VID_054C&PID_0336\\SERVICE', 'bus_name': 'Sony',
           'driver': '', 'inf': '', 'hardware_id': 'USB\\VID_054C&PID_0336'}

class FakeWindows:
    def __init__(self, device=NORMAL):
        self.devices = [copy.deepcopy(device)]
        self.state = {'format': 1, 'devices': {}}
        self.events = []
        self.fail = None
    def lock(self): return nullcontext()
    def check_admin(self): pass
    def load(self): return copy.deepcopy(self.state)
    def save(self, s):
        self.state = copy.deepcopy(s)
        self.events.append('save')
    def inventory(self, present=True): return copy.deepcopy(self.devices)
    def backup_original(self, d, token):
        self.events.append('backup')
        return None
    def prepare(self, d, r):
        self.events.append('prepare')
        if self.fail == 'prepare': raise InstallerError('prepare failed')
    def stage(self, r): return 'oem123.inf'
    def install(self, d, r):
        self.events.append('install')
        if self.fail == 'install': raise InstallerError('install failed')
        self.devices[0].update(inf='oem123.inf', driver='libusb0')
    def wait_bound(self, *args): pass
    def validate_original(self, r):
        if self.fail == 'backup': raise InstallerError('backup corrupt')
    def verify_owned(self, *args): return True
    def remove_package(self, p, r): self.events.append('remove')
    def restore_original(self, r):
        self.events.append('restore')
        if self.fail == 'restore': raise InstallerError('restore failed')

        if self.devices:self.devices[0].update(inf=r['before_inf'], driver=r['before_driver'])
    def find_staged(self, r): return None
    def rescan(self): self.events.append('scan')

class DriverTests(unittest.TestCase):
    def test_backup_and_journal_precede_install(self):
        b=FakeWindows(); DriverManager(b).ensure()
        self.assertLess(b.events.index('backup'), b.events.index('prepare'))
        self.assertLess(b.events.index('save'), b.events.index('prepare'))
        self.assertEqual(next(iter(b.state['devices'].values()))['published_inf'], 'oem123.inf')
    def test_install_failure_is_recoverable(self):
        b=FakeWindows(); b.fail='install'; m=DriverManager(b)
        with self.assertRaises(InstallerError): m.ensure()
        self.assertEqual(next(iter(b.state['devices'].values()))['status'], 'staged')
        b.fail=None; m.restore()
        self.assertEqual(b.devices[0]['driver'], 'USBSTOR')
    def test_restore_can_retry_after_failure(self):
        b=FakeWindows(); m=DriverManager(b); m.ensure(); b.fail='restore'
        with self.assertRaises(InstallerError):m.restore()
        b.fail=None; m.restore()
        self.assertEqual(next(iter(b.state['devices'].values()))['status'], 'restored')
    def test_corrupt_original_backup_does_not_remove_driver(self):
        b=FakeWindows();m=DriverManager(b);m.ensure();b.fail='backup'
        with self.assertRaises(InstallerError):m.restore()
        self.assertNotIn('remove',b.events)
    def test_borrowed_driver_is_not_uninstalled(self):
        b=FakeWindows();b.devices[0]['driver']='libusb0';m=DriverManager(b)
        self.assertFalse(m.ensure()['changed']);m.restore()
        self.assertEqual(b.events,[])
    def test_no_camera_and_multiple_cameras_are_rejected(self):
        for rows in ([], [NORMAL,NORMAL]):
            b=FakeWindows();b.devices=rows
            with self.assertRaises(InstallerError):DriverManager(b).ensure()
            self.assertEqual(b.events,[])
    def test_model_mismatch_and_composite_interface_rejected(self):
        for key,value in [('bus_name','ILCE-7M3'),('id','USB\\VID_054C&PID_0D28&MI_00\\CAMERA')]:
            b=FakeWindows();b.devices[0][key]=value
            with self.assertRaises(InstallerError):DriverManager(b).ensure()
            self.assertEqual(b.events,[])
    def test_updater_prevents_driver_changes(self):
        b=FakeWindows();b.devices.append({'id':'USB\\VID_054C&PID_03E2\\UPDATE'})
        with self.assertRaises(InstallerError):DriverManager(b).ensure()
        self.assertEqual(b.events,[])
    def test_service_requires_verified_transition(self):
        b=FakeWindows(SERVICE)
        with self.assertRaises(InstallerError):DriverManager(b).ensure()
        DriverManager(b).ensure(service=True)
        self.assertIn('install',b.events)
    def test_foreign_driver_change_prevents_restore(self):
        b=FakeWindows();m=DriverManager(b);m.ensure();b.devices[0]['inf']='oem999.inf'
        with self.assertRaises(InstallerError):m.restore()
        self.assertNotIn('remove',b.events)
    def test_invalid_published_package_not_deleted(self):
        b=FakeWindows();m=DriverManager(b);m.ensure()
        next(iter(b.state['devices'].values()))['published_inf']='usbstor.inf'
        with self.assertRaises(InstallerError):m.restore()
        self.assertNotIn('remove',b.events)
    def test_service_and_normal_restore_in_order(self):
        b=FakeWindows();m=DriverManager(b);m.ensure();b.devices=[copy.deepcopy(SERVICE)];m.ensure(service=True)
        b.devices=[];m.restore()
        self.assertTrue(all(r['status']=='restored' for r in b.state['devices'].values()))

    def test_normal_pid_change_prepares_new_interface_and_retains_both_backups(self):
        class SwitchingWindows(FakeWindows):
            def install(self, device, row):
                super().install(device, row)
                if 'PID_0D28' in device['id']:
                    self.devices = [dict(NORMAL, id=NORMAL['id'].replace('0D28', '0D29'),
                                         hardware_id=NORMAL['hardware_id'].replace('0D28', '0D29'))]
            def wait_bound(self, instance, driver):
                return 'normal_mode_changed' if self.devices[0]['id'] != instance else True
        b = SwitchingWindows()
        result = DriverManager(b).ensure()
        self.assertEqual(result, {'driver_ready': True, 'changed': True, 'driver': 'libusb0'})
        self.assertEqual(b.events.count('install'), 2)
        self.assertEqual(len(b.state['devices']), 2)
        self.assertTrue(all(r['status'] == 'installed' and r['before_driver'] == 'USBSTOR'
                            for r in b.state['devices'].values()))


class ReadinessTests(unittest.TestCase):
    def wait(self, instance, devices):
        # Only the PnP observation boundary is replaced; no Windows API calls.
        backend = WindowsBackend.__new__(WindowsBackend)
        backend.inventory = lambda: copy.deepcopy(devices)
        with patch('a7c_installer.drivers.windows_native.time.sleep'):
            return backend.wait_bound(instance, 'libusb0')

    def test_expected_driver_is_ready(self):
        self.assertIs(self.wait(NORMAL['id'], [dict(NORMAL, driver='libusb0')]), True)

    def test_same_serial_normal_variant_is_followed(self):
        changed = dict(NORMAL, id=NORMAL['id'].replace('0D28', '0D29'))
        self.assertEqual(self.wait(NORMAL['id'], [changed]), 'normal_mode_changed')

    def test_other_camera_or_multiple_interfaces_do_not_retarget(self):
        changed = dict(NORMAL, id=NORMAL['id'].replace('0D28', '0D29'))
        for devices in ([dict(changed, id=changed['id'].replace('CAMERA', 'OTHER'))],
                        [dict(changed, bus_name='ILCE-7M3')], [changed, NORMAL]):
            with self.subTest(devices=devices), self.assertRaises(InstallerError):
                self.wait(NORMAL['id'], devices)

    def test_service_mode_is_not_followed_as_a_normal_mode_change(self):
        with self.assertRaises(InstallerError):
            self.wait(SERVICE['id'], [NORMAL])


class OwnedPackageTests(unittest.TestCase):
    def verify(self, other, present=(), modified=False):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {'SystemRoot': directory}):
            root = Path(directory)
            backend = WindowsBackend.__new__(WindowsBackend)
            backend.root = root / 'journal'
            row = dict(SERVICE, token='owned', inf_name='owned.inf')
            source = backend.directory(row) / 'driver' / row['inf_name']
            source.parent.mkdir(parents=True)
            source.write_bytes(b'our generated package')
            inf = root / 'INF' / 'oem123.inf'
            inf.parent.mkdir()
            inf.write_bytes(b'other package' if modified else source.read_bytes())
            backend.inventory = lambda present=True: list(present_devices if present else [other])
            present_devices = present
            return backend.verify_owned('oem123.inf', row)

    def test_absent_matching_port_instance_does_not_block_our_package_removal(self):
        ghost = dict(SERVICE, id=SERVICE['id'] + '-OLD-PORT', inf='oem123.inf')
        self.assertTrue(self.verify(ghost))

    def test_additional_live_device_still_blocks_package_removal(self):
        other = dict(SERVICE, id=SERVICE['id'] + '-OTHER', inf='oem123.inf')
        with self.assertRaises(InstallerError):
            self.verify(other, present=[other])

    def test_absent_different_hardware_still_blocks_package_removal(self):
        other = dict(NORMAL, inf='oem123.inf')
        with self.assertRaises(InstallerError):
            self.verify(other)

    def test_modified_inf_still_blocks_package_removal(self):
        ghost = dict(SERVICE, id=SERVICE['id'] + '-OLD-PORT', inf='oem123.inf')
        with self.assertRaises(InstallerError):
            self.verify(ghost, modified=True)

if __name__=='__main__':unittest.main()
