import copy
from dataclasses import replace
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.bundle import Bundle, sha256
from a7c_installer.configuration import FtpSettings, InstallerError
from a7c_installer.ftp_check import test_ftp
from a7c_installer.operations import (Installer, LOADER, ENABLE, DISPLAY_ENABLE, PRELOAD, META,
                                     PENDING, CONFIG, PASSWORD, without_loader)


SETTINGS = FtpSettings("192.168.1.20", 21, "camera-upload", "/Camera", "secret-$-中文")
DEFAULT_SETTINGS = replace(SETTINGS, pause_photos_for_native_ftp=True)


class MemoryCamera:
    model = "ILCE-7C"
    def __init__(self, bundle):
        self.files = {"/version.txt": bundle.firmware["version_txt"].encode(),
                      "/mnt/sd/DCIM/photo.JPG": b"KEEP", "/mnt/sd/receipt": b"KEEP"}
        self.dependencies = bundle.firmware["dependencies"].copy()
        self.events = []
        self.fail_path = None
        self.stopped = False

    def exists(self, path):
        return path in self.files

    def read(self, path):
        return self.files[path]

    def atomic(self, path, value, mode=0o600):
        self.events.append(("write", path, mode))
        if path == self.fail_path:
            self.fail_path = None
            raise InstallerError("simulated USB disconnect")
        self.files[path] = value

    def remove(self, path):
        self.events.append(("remove", path))
        self.files.pop(path, None)

    def hashes(self, paths):
        return {p: self.dependencies[p] for p in paths}

    def monitor_fields(self):
        return (0x20098000, 0x7c000)

    def directories(self, paths):
        self.events.append(("mkdir", tuple(paths)))

    def sync(self):
        self.events.append(("sync",))

    def quiesce(self, retire_display=True):
        self.stopped = True
        self.events.append(("quiesce", retire_display))

    def cleanup_staging(self, paths):
        self.events.append(('cleanup-staging', tuple(paths)))
        for path in paths:
            self.files.pop(path + '.installer-next', None)

    def start_service(self):
        assert ENABLE in self.files and PENDING not in self.files
        self.events.append(('start-service',))
        if getattr(self, 'start_failure', False):
            raise InstallerError('测试：服务启动未确认')
        self.stopped = False
        return {'supervisor_pid': 42, 'worker_pid': 43, 'health':self.service_health()}

    def service_health(self, process_state=None):
        return {'state':'stopped' if self.stopped else 'ready','detail':'测试服务状态'}


class ConfigurationTests(unittest.TestCase):
    def test_photo_setting_is_explicit_and_does_not_change_existing_video_config(self):
        from dataclasses import replace
        enabled = replace(SETTINGS, photos=True)
        self.assertEqual(enabled.camera_files()['config'].splitlines(),
                         [b'a7c-plainftp-v2', b'192.168.1.20', b'21', b'camera-upload', b'/Camera', b'1'])
        self.assertTrue(enabled.public()['photos'])
        self.assertFalse(SETTINGS.public()['photos'])
        with self.assertRaises(InstallerError):
            replace(SETTINGS, photos='yes').validate()
    def test_contract(self):
        files = SETTINGS.camera_files()
        self.assertEqual(files["config"].splitlines(), [b"a7c-plainftp-v1", b"192.168.1.20", b"21", b"camera-upload", b"/Camera"])
        self.assertEqual(files["password"], SETTINGS.password.encode() + b"\n")
        self.assertNotIn(SETTINGS.password, repr(SETTINGS))
        self.assertNotIn("password", SETTINGS.public())

    def test_reject_unsafe_input(self):
        import dataclasses
        for field, value in (("host", "nas.local"), ("port", 0), ("username", "u\nx"),
                             ("directory", "/../other"), ("directory", "/A//B"),
                             ("password", "x\ny"), ("password", "")):
            with self.subTest(field=field, value=value), self.assertRaises(InstallerError):
                dataclasses.replace(SETTINGS, **{field: value}).validate()


class BundleTests(unittest.TestCase):
    def test_frozen_package(self):
        bundle = Bundle()
        self.assertEqual(len(bundle.files), 22)
        # The Wi-Fi diagnostics are a maintainer debug add-on, never shipped.
        self.assertFalse(any(p.startswith('/setting/a7c-diag/') for p in bundle.files))
        self.assertNotIn('wifi-diag', bundle.manifest['features'])
        self.assertEqual(len(bundle.firmware["dependencies"]), 9)
        self.assertFalse(any("debug/" in p or "password" in p for p in bundle.files))

    def altered(self, transform):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.zip"
            with zipfile.ZipFile(Bundle().path) as original:
                files = {n: original.read(n) for n in original.namelist()}
            transform(files)
            with zipfile.ZipFile(path, "w") as archive:
                for name, value in files.items():
                    archive.writestr(name, value)
            with self.assertRaises(InstallerError):
                Bundle(path)

    def test_tamper(self):
        self.altered(lambda files: files.__setitem__("a7c-uploader/launcher.so", b"tampered"))

    def test_extra_file(self):
        self.altered(lambda files: files.__setitem__("password", b"unexpected"))

    def test_escape(self):
        def alter(files):
            manifest = json.loads(files["manifest.json"])
            first = next(iter(manifest["files"].values()))
            first["target"] = "/setting/a7c-display/../../etc/passwd"
            files["manifest.json"] = json.dumps(manifest).encode()
        self.altered(alter)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.bundle = Bundle()
        self.camera = MemoryCamera(self.bundle)
        self.logs = []
        self.tested = []
        self.installer = Installer(self.camera, self.bundle, self.logs.append, self.tested.append)

    def test_first_install_publish_last_and_no_media_access(self):
        result = self.installer.install(SETTINGS)
        self.assertFalse(result["requires_power_cycle"])
        self.assertTrue(result['service_started'])
        self.assertEqual(self.camera.events[-1], ('start-service',))
        self.assertEqual(self.camera.files[ENABLE], b"a7c-resident-v1\n")
        self.assertEqual(self.camera.files[PRELOAD], LOADER.encode() + b"\n")
        index = max(i for i, e in enumerate(self.camera.events) if e[:2] == ("write", PRELOAD))
        for path in self.bundle.files:
            self.assertLess(next(i for i, e in enumerate(self.camera.events) if e[:2] == ("write", path)), index)
        self.assertEqual(self.camera.files["/mnt/sd/DCIM/photo.JPG"], b"KEEP")
        self.assertNotIn(SETTINGS.password, "\n".join(self.logs) + json.dumps(result))
        self.assertFalse(self.camera.exists(PENDING))
        self.assertEqual(self.tested, [DEFAULT_SETTINGS])

    def test_activation_failure_keeps_committed_install_and_backup(self):
        self.camera.start_failure = True
        result = self.installer.install(SETTINGS)
        self.assertFalse(result['service_started'])
        self.assertTrue(self.camera.exists(META))
        self.assertTrue(self.camera.exists(ENABLE))
        self.assertFalse(self.camera.exists(PENDING))
        self.assertTrue(self.camera.exists('/setting/a7c-installer/backup/manifest.json'))
        self.assertIn('服务未就绪', result['message'])

    def test_start_installed_service_does_not_reinstall_or_test_ftp(self):
        self.installer.install(SETTINGS)
        self.camera.events.clear()
        self.tested.clear()
        result = self.installer.start()
        self.assertTrue(result['started'])
        self.assertEqual(self.camera.events, [('start-service',)])
        self.assertEqual(self.tested, [])

    def test_pending_install_cannot_start(self):
        self.installer.install(SETTINGS)
        self.camera.files[PENDING] = b'pending'
        self.camera.events.clear()
        with self.assertRaisesRegex(InstallerError, '未完成'):
            self.installer.start()
        self.assertEqual(self.camera.events, [])

    def test_changed_native_module_requires_cold_load_but_starts_upload(self):
        self.camera.files['/tmp_bt/a7X.so'] = b'previous native module'
        result = self.installer.install(SETTINGS)
        self.assertTrue(result['service_started'])
        self.assertTrue(result['requires_power_cycle'])

    def test_changed_staged_scripts_require_restart_even_with_same_native_binary(self):
        self.camera.files['/tmp_bt/a7X.so'] = self.bundle.files['/setting/a7c-display/native-module.so']
        self.camera.files['/setting/a7c-debug/ram/dds-once/bundle.digest'] = b'old display bundle\n'
        self.camera.start_failure = True
        result = self.installer.install(SETTINGS)
        self.assertTrue(result['requires_power_cycle'])
        self.assertFalse(result['service_started'])
        self.assertIn('不用再次安装', result['message'])
        self.assertNotIn('选择「启动上传服务」', result['message'])

    def test_wrong_firmware_no_writes(self):
        self.camera.files["/version.txt"] = b"2.03"
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertEqual(self.camera.events, [])

    def test_dependency_mismatch_no_writes(self):
        self.camera.dependencies[next(iter(self.camera.dependencies))] = "0" * 64
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertEqual(self.camera.events, [])

    def test_unknown_loader_no_writes(self):
        self.camera.files[LOADER] = b"OTHER"
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertEqual(self.camera.events, [])

    def test_failed_install_restores_exact_old_files(self):
        self.camera.files[PRELOAD] = b"/foreign.so\n"
        self.camera.fail_path = CONFIG
        before = copy.deepcopy(self.camera.files)
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertTrue(self.camera.exists(PENDING))
        self.installer.restore()
        actual = {p: v for p, v in self.camera.files.items() if not p.startswith("/setting/a7c-installer/")}
        self.assertEqual(actual, before)

    def test_restore_does_not_overwrite_new_foreign_preload(self):
        self.installer.install(SETTINGS)
        self.camera.files[PRELOAD] += b"/new-foreign.so\n"
        self.installer.restore()
        self.assertEqual(self.camera.files[PRELOAD], b"/new-foreign.so\n")

    def test_reuse_credentials(self):
        self.installer.install(SETTINGS)
        self.installer.install(reuse=True, display=False)
        self.assertEqual(self.camera.files[PASSWORD], SETTINGS.password.encode() + b"\n")
        self.assertFalse(self.camera.exists(DISPLAY_ENABLE))
        self.assertEqual(self.tested, [DEFAULT_SETTINGS, DEFAULT_SETTINGS])
    def test_enable_photos_with_saved_secret_and_readback_then_disable(self):
        self.bundle.manifest['features'] = ['photos-jpeg-arw']
        self.installer.install(SETTINGS)
        result = self.installer.install(reuse=True, photos=True)
        self.assertTrue(result['ftp']['photos'])
        self.assertTrue(self.installer.inspect()['ftp']['photos'])
        self.assertEqual(self.camera.files[PASSWORD], SETTINGS.password.encode() + b'\n')
        self.assertEqual(self.camera.files[CONFIG].splitlines()[-1], b'1')
        self.installer.install(reuse=True, photos=False)
        self.assertFalse(self.installer.inspect()['ftp']['photos'])
        self.assertEqual(self.camera.files[CONFIG], SETTINGS.camera_files()['config'])
    def test_video_only_payload_refuses_photo_configuration_before_writing(self):
        self.bundle.manifest.pop('features', None)
        self.camera.events.clear()
        with self.assertRaisesRegex(InstallerError, '不含图片上传'):
            self.installer.install(SETTINGS, photos=True)
        self.assertEqual(self.camera.events, [])

    def test_native_ftp_photo_pause_round_trips_with_saved_configuration(self):
        legacy = replace(SETTINGS, photos=True)
        self.installer.install(legacy)
        self.assertEqual(self.camera.files[CONFIG], replace(DEFAULT_SETTINGS, photos=True).camera_files()['config'])
        self.camera.files[CONFIG] = legacy.camera_files()['config']
        self.assertIsNone(self.installer.inspect()['ftp']['pause_photos_for_native_ftp'])
        self.assertTrue(self.installer.install(reuse=True)['ftp']['pause_photos_for_native_ftp'])
        self.installer.install(reuse=True, pause_photos_for_native_ftp=False)
        self.assertFalse(self.installer.inspect()['ftp']['pause_photos_for_native_ftp'])
        self.assertEqual(self.camera.files[CONFIG].splitlines()[-2:], [b'1', b'0'])
        self.assertFalse(self.installer.install(reuse=True)['ftp']['pause_photos_for_native_ftp'])

    def test_empty_password_update_preserves_saved_secret(self):
        from dataclasses import replace
        saved = self.installer.install(SETTINGS)['ftp']
        changed = replace(SETTINGS, directory='/Other', password='')
        result = self.installer.install(changed, preserve_password=True, expected_config=saved)
        self.assertEqual(self.camera.files[PASSWORD], SETTINGS.password.encode() + b'\n')
        self.assertEqual(result['ftp']['directory'], '/Other')
        self.assertNotIn(SETTINGS.password, json.dumps(result))

    def test_new_password_replaces_existing_secret(self):
        from dataclasses import replace
        self.installer.install(SETTINGS)
        self.installer.install(replace(SETTINGS, password='replacement'))
        self.assertEqual(self.camera.files[PASSWORD], b'replacement\n')

    def test_changed_camera_config_rejects_implicit_password_reuse(self):
        from dataclasses import replace
        original = self.installer.install(SETTINGS)['ftp']
        self.installer.install(replace(SETTINGS, username='another-account'))
        self.camera.events.clear()
        with self.assertRaisesRegex(InstallerError, '配置已变化'):
            self.installer.install(replace(SETTINGS, password=''), preserve_password=True, expected_config=original)
        self.assertEqual(self.camera.events, [])

    def test_unchanged_loaded_display_is_paused_and_rebound(self):
        self.installer.install(SETTINGS)
        self.camera.files['/tmp_bt/a7X.so'] = self.bundle.files['/setting/a7c-display/native-module.so']
        self.camera.events.clear()
        self.installer.install(reuse=True)
        self.assertIn(('quiesce',False),self.camera.events)
        self.camera.events.clear()
        self.installer.uninstall()
        self.assertIn(('quiesce',True),self.camera.events)

    def test_previous_preview_manifest_can_be_upgraded(self):
        self.installer.install(SETTINGS)
        metadata=json.loads(self.camera.files[META])
        metadata['files'].pop('/setting/a7c-display/redraw')
        self.camera.files[META]=json.dumps(metadata).encode()
        self.installer.install(reuse=True)
        self.assertEqual(set(json.loads(self.camera.files[META])['files']),set(self.bundle.files))

    def test_uninstall_previous_preview_keeps_unmanaged_file(self):
        self.installer.install(SETTINGS)
        metadata=json.loads(self.camera.files[META])
        path='/setting/a7c-display/redraw'
        metadata['files'].pop(path)
        self.camera.files[META]=json.dumps(metadata).encode()
        self.installer.uninstall()
        self.assertEqual(self.camera.files[path],self.bundle.files[path])

    def test_uninstall_preserves_foreign_preload_and_media(self):
        self.camera.files[PRELOAD] = b"/foreign.so # other app\n"
        self.installer.install(SETTINGS)
        self.installer.uninstall()
        self.assertEqual(self.camera.files[PRELOAD], b"/foreign.so # other app\n")
        for path in self.bundle.files:
            self.assertNotIn(path, self.camera.files)
        self.assertNotIn(PASSWORD, self.camera.files)
        self.assertNotIn(META, self.camera.files)
        self.assertEqual(self.camera.files["/mnt/sd/receipt"], b"KEEP")

    def test_pending_blocks_new_install(self):
        self.camera.files[PENDING] = b"{}"
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertEqual(self.camera.events, [])

    def test_uninstall_quiesce_failure_keeps_programs_and_recovery(self):
        from unittest.mock import patch
        self.installer.install(SETTINGS)
        with patch.object(self.camera, "quiesce", side_effect=InstallerError("busy")):
            with self.assertRaises(InstallerError):
                self.installer.uninstall()
        self.assertFalse(self.camera.exists(ENABLE))
        self.assertNotIn(LOADER.encode(), self.camera.files.get(PRELOAD, b""))
        for path, value in self.bundle.files.items():
            self.assertEqual(self.camera.files[path], value)
        self.assertTrue(self.camera.exists(PENDING))
        self.installer.restore()
        self.assertTrue(self.camera.exists(ENABLE))

    def test_uninstall_removes_service_and_restore_recovers_configuration(self):
        self.installer.install(SETTINGS)
        result = self.installer.uninstall()
        self.assertTrue(result["uninstalled"])
        self.assertTrue(result["requires_power_cycle"])
        for path in (ENABLE, DISPLAY_ENABLE, CONFIG, PASSWORD, META, PENDING):
            self.assertFalse(self.camera.exists(path), path)
        self.assertEqual(self.camera.files["/mnt/sd/DCIM/photo.JPG"], b"KEEP")
        self.installer.restore()
        self.assertTrue(self.camera.exists(ENABLE))
        self.assertTrue(self.camera.exists(DISPLAY_ENABLE))
        self.assertEqual(self.camera.files[PASSWORD], SETTINGS.password.encode() + b"\n")

    def test_restore_interruption_remains_recoverable(self):
        self.installer.install(SETTINGS)
        self.installer.install(reuse=True)
        self.camera.fail_path = CONFIG
        with self.assertRaises(InstallerError):
            self.installer.restore()
        self.assertTrue(self.camera.exists(PENDING))
        self.installer.restore()
        self.assertFalse(self.camera.exists(PENDING))

    def test_ftp_failure_does_not_touch_camera(self):
        def failed(_):
            raise InstallerError("FTP unavailable")
        self.installer.ftp_test = failed
        with self.assertRaises(InstallerError):
            self.installer.install(SETTINGS)
        self.assertEqual(self.camera.events, [])

    def test_corrupt_backup_no_recovery_writes(self):
        self.installer.install(SETTINGS)
        self.camera.files["/setting/a7c-installer/backup/manifest.json"] = b"{}"
        self.camera.events.clear()
        with self.assertRaises(InstallerError):
            self.installer.restore()
        self.assertEqual(self.camera.events, [])


class PreloadTests(unittest.TestCase):
    def test_comments_colons_foreign_entries(self):
        data = ("# owned text " + LOADER + "\n/foreign.so:" + LOADER + " # keep\n").encode()
        self.assertEqual(without_loader(data), ("# owned text " + LOADER + "\n/foreign.so # keep\n").encode())


class FakeFtp:
    def __init__(self, failure=None):
        self.files = {}
        self.failure = failure
        self.closed = False
    def connect(self, *args, **kw): pass
    def login(self, *args):
        if self.failure == "login":
            raise Exception(SETTINGS.password)
    def cwd(self, *args): pass
    def voidcmd(self, *args): pass
    def storbinary(self, command, stream): self.files[command[5:]] = stream.read()
    def size(self, name): return len(self.files[name]) + (1 if self.failure == "size" else 0)
    def rename(self, old, new): self.files[new] = self.files.pop(old)
    def delete(self, name): self.files.pop(name, None)
    def close(self): self.closed = True


class FtpTests(unittest.TestCase):
    def test_upload_length_rename_delete(self):
        ftp = FakeFtp()
        self.assertTrue(test_ftp(SETTINGS, lambda: ftp)["ok"])
        self.assertEqual(ftp.files, {})
        self.assertTrue(ftp.closed)

    def test_failure_cleanup_and_secret_redaction(self):
        for failure in ("size", "login"):
            ftp = FakeFtp(failure)
            with self.assertRaises(InstallerError) as error:
                test_ftp(SETTINGS, lambda: ftp)
            self.assertNotIn(SETTINGS.password, str(error.exception))
            self.assertEqual(ftp.files, {})
            self.assertTrue(ftp.closed)


class TerminalTests(unittest.TestCase):
    def test_start_service_reuses_verified_live_processes(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        camera = SonyUsb()
        with patch.object(camera, 'command', return_value='RUNNING:41:42') as command, patch.object(camera, 'service_health', return_value={'state':'ready','detail':'ready'}):
            result = camera.start_service()
        self.assertEqual(result['worker_pid'],42)
        self.assertEqual(result['health']['state'],'ready')
        self.assertEqual(command.call_count, 1)

    def test_start_service_detaches_once_and_waits_for_live_processes(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        camera = SonyUsb()
        with patch.object(camera, 'command', side_effect=['IDLE', '', 'RUNNING:41:42']) as command, patch.object(camera, 'service_health', return_value={'state':'ready','detail':'ready'}), patch('a7c_installer.transport.sony_usb.time.sleep'):
            result = camera.start_service()
        self.assertEqual(result['worker_pid'], 42)
        launch = command.call_args_list[1].args[0]
        self.assertIn("trap '' HUP", launch)
        self.assertIn('supervisor.sh --start </dev/null >/dev/null 2>&1 &', launch)

    def test_start_service_refuses_foreign_mount_or_unowned_busy_state(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        for state in ('FOREIGN','BUSY'):
            with self.subTest(state=state):
                camera = SonyUsb()
                with patch.object(camera, 'resident_status', return_value=state), patch.object(camera, 'command') as command, patch('a7c_installer.transport.sony_usb.time.monotonic', side_effect=[0,61]):
                    with self.assertRaises(InstallerError):
                        camera.start_service()
                command.assert_not_called()

    def test_health_requires_worker_initialization_and_live_display_probe(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        camera = SonyUsb()
        for output, state in [('UPLOAD=starting\nDISPLAY=starting','starting'),
                              ('UPLOAD=ready\nDISPLAY=error','error'),
                              ('UPLOAD=ready\nDISPLAY=restart','restart_required'),
                              ('UPLOAD=ready\nDISPLAY=ready','ready'),
                              ('UPLOAD=ready\nDISPLAY=disabled','ready')]:
            with patch.object(camera,'command',return_value=output) as command:
                self.assertEqual(camera.service_health('RUNNING:41:42')['state'],state)
                self.assertIn('--inspect-service', command.call_args.args[0])

    def test_running_pid_with_failed_display_is_not_healthy(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        camera=SonyUsb()
        with patch.object(camera,'resident_status',return_value='RUNNING:41:42'), patch.object(camera,'service_health',return_value={'state':'error','detail':'显示未就绪'}):
            with self.assertRaisesRegex(InstallerError,'健康检查未通过'):
                camera.start_service()

    def test_native_usb_log_keeps_ownership_errors_without_bulk_debug_and_unregisters(self):
        from unittest.mock import MagicMock
        from a7c_installer.transport.native_log import NativeUsbLog
        backend = MagicMock()
        trace = NativeUsbLog(backend)
        trace.receive(None, 1, b'error [darwin_claim_interface] could not set configuration')
        trace.receive(None, 4, b'debug bulk transfer private-data')
        self.assertEqual(list(trace.messages), ['error [darwin_claim_interface] could not set configuration'])
        trace.close()
        trace.close()
        self.assertEqual(backend.lib.libusb_set_log_cb.call_count, 2)
        self.assertIsNone(backend.lib.libusb_set_log_cb.call_args.args[1])

    def test_macos_claim_precedes_senser_start_and_constructor_resets_are_idempotent(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from a7c_installer.transport.sony_usb import claimed_macos_driver
        from pmca.usb.sony import SonySenserAuthDevice, SonySenserDevice
        events = []
        device = MagicMock()
        device.is_kernel_driver_active.return_value = True
        device.detach_kernel_driver.side_effect = lambda _: events.append('detach')
        device.get_active_configuration.return_value.__getitem__.return_value = [
            SimpleNamespace(bmAttributes=2, bEndpointAddress=0x81),
            SimpleNamespace(bmAttributes=2, bEndpointAddress=0x02)]
        with patch('usb.util.claim_interface', side_effect=lambda d, i: events.append('claim')), patch('usb.util.dispose_resources'):
            driver = claimed_macos_driver(device)
            SonySenserAuthDevice(driver)
            SonySenserDevice(driver)
            self.assertEqual(events, ['detach', 'claim'])

    def test_macos_claim_failure_does_not_send_start_senser(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from a7c_installer.transport.sony_usb import SonyUsb
        device = MagicMock()
        device.idProduct = 0x0d28
        device.is_kernel_driver_active.return_value = False
        device.get_active_configuration.return_value.__getitem__.return_value = [
            SimpleNamespace(bmAttributes=2, bEndpointAddress=0x81),
            SimpleNamespace(bmAttributes=2, bEndpointAddress=0x02)]
        # The ordinary-mode descriptor check uses the same interface slot.
        interface = device.get_active_configuration.return_value.__getitem__.return_value
        class Interface(list):
            bInterfaceClass = 8
        device.get_active_configuration.return_value.__getitem__.return_value = Interface(interface)
        with patch('a7c_installer.transport.sony_usb.sys.platform', 'darwin'), patch('os.geteuid', return_value=0, create=True), patch.object(SonyUsb, 'prepare_windows_drivers'), patch('a7c_installer.transport.sony_usb.unmount_macos_disks'), patch('a7c_installer.transport.sony_usb.enumerate_devices', return_value=(None, None, [device])), patch('usb.util.get_string', return_value='ILCE-7C'), patch('usb.util.claim_interface', side_effect=OSError('claim failed')), patch('usb.util.dispose_resources') as dispose, patch('pmca.usb.sony.SonySenserAuthDevice') as auth:
            with self.assertRaisesRegex(InstallerError, '申请普通 USB 接口'):
                with SonyUsb():
                    self.fail('Must not connect')
            auth.assert_not_called()
            dispose.assert_called()

    def test_close_releases_all_usb_handles_immediately_and_is_idempotent(self):
        from unittest.mock import MagicMock, patch, call
        from a7c_installer.transport.sony_usb import SonyUsb
        transport = SonyUsb()
        normal, service = object(), object()
        transport._usb_devices = [normal, service]
        transport.auth = auth = MagicMock()
        with patch('usb.util.dispose_resources') as dispose:
            transport.close()
            transport.close()
            self.assertEqual(dispose.call_args_list, [call(normal), call(service)])
            auth.stop.assert_called_once()

    def test_connection_error_records_phase_and_usb_code_without_packet_data(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        logs = []
        transport = SonyUsb(logs.append)
        def fail():
            transport.stage = '普通模式认证'
            try:
                ex = OSError(60, 'private-packet-data')
                ex.backend_error_code = -7
                raise ex
            except OSError:
                raise RuntimeError('private-authentication-challenge')
        with patch.object(transport, 'connect', side_effect=fail), patch.object(transport, 'close') as close:
            with self.assertRaisesRegex(InstallerError, '普通模式认证') as result:
                with transport:
                    self.fail('Connection should fail')
            close.assert_called_once()
        combined = '\n'.join(logs) + str(result.exception)
        self.assertIn('backend_error_code=-7', combined)
        self.assertNotIn('private-', combined)

    def test_charger_and_firmware_updater_are_actionable_no_session(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        for product, message in ((0x0994, "USB Charger"), (0x03e2, "固件更新模式")):
            with patch.object(SonyUsb, 'prepare_windows_drivers'), patch("a7c_installer.transport.sony_usb.enumerate_devices",
                       return_value=(None, None, [SimpleNamespace(idProduct=product)])):
                with self.assertRaisesRegex(InstallerError, message):
                    with SonyUsb():
                        self.fail("Must not open a session")

    def test_echo_cannot_signal_completion(self):
        from a7c_installer.transport.sony_usb import SonyUsb
        class Terminal:
            def writeTerminal(self, wire):
                nonce = re.search(rb"'__A7C_BEGIN_' '([0-9a-f]+)'", wire)[1]
                self.parts = [b"[ 1.23] boot noise\r\n" + wire.replace(b";", b";\r\n"),
                              b"\r\n__A7C_BEGIN_" + nonce + b"\r\nACTUAL\r\n[ 23.45] async kernel noise\r\n",
                              b"\r\n__A7C_END_" + nonce + b":0\r\n# "]
            def readTerminal(self): return self.parts.pop(0)
        transport = SonyUsb()
        transport.terminal = True
        transport.dev = Terminal()
        self.assertEqual(transport.command("echo ACTUAL"), "ACTUAL")

    def test_partial_kernel_timestamp_does_not_break_file_existence_reply(self):
        from a7c_installer.transport.sony_usb import SonyUsb
        class Terminal:
            def writeTerminal(self, wire):
                nonce = re.search(rb"'__A7C_BEGIN_' '([0-9a-f]+)'", wire)[1]
                self.parts = [b'\n__A7C_BEGIN_' + nonce + b'\r\nEXISTS\r\n'
                              b'[ 629.966942] Register interface\n'
                              b'[ 629.966958] \n[ 629\r\n'
                              b'__A7C_END_' + nonce + b':0\r\n# ']
            def readTerminal(self):
                return self.parts.pop(0)
        transport = SonyUsb()
        transport.terminal = True
        transport.dev = Terminal()
        self.assertTrue(transport.exists('/setting/a7c-uploader/plainftp/config'))

    def test_console_fragment_before_completion_marker_does_not_cause_timeout(self):
        from a7c_installer.transport.sony_usb import SonyUsb
        class Terminal:
            def writeTerminal(self, wire):
                nonce = re.search(rb"'__A7C_BEGIN_' '([0-9a-f]+)'", wire)[1]
                self.parts = [wire + b'\n__A7C_BEGIN_' + nonce + b'\r\nEXISTS\r\n'
                              b'[ 779.885150] Regi\r\ns__A7C_END_' + nonce + b':0\r\n'
                              b'ter interface\r\n# ']
            def readTerminal(self):
                return self.parts.pop(0)
        transport = SonyUsb()
        transport.terminal = True
        transport.dev = Terminal()
        self.assertTrue(transport.exists('/setting/a7c-uploader/plainftp/config'))

    def test_conflicting_existence_results_are_never_accepted(self):
        from unittest.mock import patch
        from a7c_installer.transport.sony_usb import SonyUsb
        transport = SonyUsb()
        for value in ('kernel noise only', 'EXISTS\nABSENT', 'EXISTS\nEXISTS'):
            with self.subTest(value=value), patch.object(transport, 'command', return_value=value):
                with self.assertRaises(InstallerError):
                    transport.exists('/setting/a7c-uploader/installed.json')

    def test_long_command_never_overflows_the_interactive_shell_line(self):
        from a7c_installer.transport.sony_usb import SonyUsb
        case = self
        class Terminal:
            needs_drain = False
            def writeTerminal(self, wire):
                case.assertFalse(self.needs_drain, 'input must be drained between short lines')
                self.needs_drain = True
                case.assertTrue(all(len(line) <= 800 for line in wire.splitlines()))
                match = re.search(rb"'__A7C_BEGIN_' '([0-9a-f]+)'", wire)
                self.parts = ([b'\n__A7C_BEGIN_' + match[1] + b'\nACTUAL\n'
                               b'__A7C_END_' + match[1] + b':0\n'] if match else [])
            def readTerminal(self):
                self.needs_drain = False
                return self.parts.pop(0) if self.parts else b''
        transport = SonyUsb()
        transport.terminal = True
        transport.dev = Terminal()
        self.assertEqual(transport.command('echo ACTUAL' + ' ' * 3500), 'ACTUAL')


if __name__ == "__main__":
    unittest.main()
