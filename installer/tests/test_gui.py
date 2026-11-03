"""Regression for basic detection unexpectedly switching the camera's mode."""
import os
from pathlib import Path
import sys
import time
import tempfile
import json
import hashlib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication, QEvent
    from a7c_installer.gui import Window
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'Desktop dependencies are optional in the CLI bundle')
class DetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # GUI tests must never open a system authorization dialog or USB device.
        import subprocess
        original_run = subprocess.run
        def without_authorization(args, *a, **kw):
            if args[0] == 'osascript':
                raise AssertionError('Unexpected system authorization in GUI test')
            return original_run(args, *a, **kw)
        for guard in (
            patch.object(Window, 'needs_admin', return_value=False),
            patch('a7c_installer.gui.subprocess.run', side_effect=without_authorization),
            patch('a7c_installer.transport.sony_usb.SonyUsb', side_effect=AssertionError('Unexpected camera access in GUI test')),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def wait_task(self, window):
        deadline = time.monotonic() + 5
        while window.task is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertIsNone(window.task)

    def close_window(self, window):
        window.close()
        if window.task is not None:
            self.wait_task(window)
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_connection_loads_public_fields_without_retaining_secret(self):
        from test_installer import MemoryCamera, SETTINGS
        from a7c_installer.bundle import Bundle
        from a7c_installer.operations import Installer
        from unittest.mock import MagicMock
        camera = MemoryCamera(Bundle())
        Installer(camera, ftp_test=lambda _: None).install(SETTINGS)
        session = MagicMock()
        session.__enter__.return_value = camera
        window = Window()
        with patch('a7c_installer.transport.sony_usb.SonyUsb', return_value=session):
            window.run_camera('connect')
            self.wait_task(window)
        self.assertEqual(window.loaded_ftp, SETTINGS.public())
        self.assertEqual(window.host.text(), SETTINGS.host)
        self.assertEqual(window.password.text(), '')
        self.assertIn('已保存', window.password.placeholderText())
        self.assertTrue(window.host.isEnabled())
        self.assertIn('服务正常', window.status.text())
        self.assertEqual(window.installed_version, Bundle().version)
        self.assertEqual(window.install_button.text(), '更新配置')
        self.assertFalse(window.uninstall_button.isHidden())
        self.assertTrue(window.uninstall_button.isEnabled())
        self.assertNotIn(SETTINGS.password, window.output.toPlainText())
        self.assertNotIn(SETTINGS.password, repr(window.loaded_ftp))
        self.close_window(window)

    def test_first_install_requires_password(self):
        from a7c_installer.configuration import InstallerError
        window = Window(demo=True)
        window.apply_saved_config(None)
        with self.assertRaises(InstallerError):
            window.settings()
        window.apply_saved_config({'host':'192.168.1.20', 'port':21, 'username':'camera-upload', 'directory':'/Camera'})
        self.assertEqual(window.settings().password, '')
        window.password.setText('new-secret')
        self.assertEqual(window.settings().password, 'new-secret')
        self.close_window(window)

    def test_target_resolves_saved_password_in_worker_only(self):
        from test_installer import MemoryCamera, SETTINGS, FakeFtp
        from a7c_installer.bundle import Bundle
        from a7c_installer.operations import Installer
        from a7c_installer.ftp_check import test_ftp
        from unittest.mock import MagicMock
        camera = MemoryCamera(Bundle())
        Installer(camera, ftp_test=lambda _: None).install(SETTINGS)
        window = Window()
        window.apply_saved_config(SETTINGS.public())
        session = MagicMock()
        session.__enter__.return_value = camera
        captured = []
        def ftp(settings):
            captured.append(settings)
            return test_ftp(settings, lambda: FakeFtp())
        with patch('a7c_installer.transport.sony_usb.SonyUsb', return_value=session), patch('a7c_installer.gui.test_ftp', side_effect=ftp):
            window.test_target()
            self.wait_task(window)
        self.assertEqual(captured[0].password, SETTINGS.password)
        self.assertEqual(window.password.text(), '')
        self.assertNotIn(SETTINGS.password, window.output.toPlainText())
        self.close_window(window)

    def test_connect_ftp_test_and_install_share_one_usb_session(self):
        from test_installer import MemoryCamera, SETTINGS
        from a7c_installer.bundle import Bundle
        from a7c_installer.operations import Installer
        from unittest.mock import MagicMock
        camera = MemoryCamera(Bundle())
        Installer(camera, ftp_test=lambda _: None).install(SETTINGS)
        session = MagicMock()
        session.__enter__.return_value = camera
        window = Window()
        def engine(cam, bundle, log):
            return Installer(cam, bundle, log, ftp_test=lambda _: None)
        with patch('a7c_installer.transport.sony_usb.SonyUsb', return_value=session) as usb, patch('a7c_installer.gui.Installer', side_effect=engine), patch('a7c_installer.gui.test_ftp', return_value={'scope': 'computer-to-FTP'}):
            window.run_camera('connect')
            self.wait_task(window)
            self.assertTrue(window.usb_session.is_open)
            session.__exit__.assert_not_called()
            window.test_target()
            self.wait_task(window)
            self.assertTrue(window.usb_session.is_open)
            window.run_camera('install')
            self.wait_task(window)
            self.assertFalse(window.usb_session.is_open)
            self.assertIn('服务正常', window.status.text())
            self.assertEqual(window.installed_version, Bundle().version)
            self.assertFalse(window.uninstall_button.isHidden())
            self.assertFalse(window.uninstall_button.isEnabled())
            self.assertIn('连接相机', window.uninstall_button.toolTip())
            usb.assert_called_once()
            session.__enter__.assert_called_once()
            session.__exit__.assert_called_once()
        self.assertNotIn(SETTINGS.password, window.output.toPlainText())
        self.close_window(window)

    def test_help_navigates_bundled_recovery_without_usb(self):
        from a7c_installer.help_view import HelpDialog
        from PySide6.QtCore import QUrl
        from unittest.mock import patch
        with patch('a7c_installer.transport.sony_usb.SonyUsb') as usb:
            dialog = HelpDialog()
            dialog.open_link(QUrl('RECOVERY.md#windows驱动恢复'))
            self.assertEqual(dialog.topics.currentData(), 'RECOVERY.md')
            self.assertIn('Windows驱动恢复', dialog.browser.toPlainText())
            usb.assert_not_called()
            dialog.close()

    def test_help_does_not_open_local_file_links(self):
        from a7c_installer.help_view import HelpDialog
        from PySide6.QtCore import QUrl
        with patch('a7c_installer.help_view.QDesktopServices.openUrl') as opened:
            dialog = HelpDialog()
            dialog.open_link(QUrl('file:///etc/passwd'))
            opened.assert_not_called()
            dialog.close()

    def test_mac_admin_relaunch_preserves_unicode_app_path(self):
        window = Window(demo=True)
        window.password.setText('must-not-travel-in-launch-command')
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', '/Applications/A7C 自动上传.app/Contents/MacOS/A7C Installer'), patch('a7c_installer.gui.os.getuid', return_value=501, create=True), patch.object(window, 'start') as start, patch.object(window, '_elevated') as elevate:
            window.elevate()
            start.call_args.args[0](lambda _: None)
            script = elevate.call_args.args[0]
            self.assertIn('A7C 自动上传.app', script)
            self.assertNotIn('\\u81ea', script)
            self.assertIn('--camera-action connect', script)
            self.assertIn('/bin/launchctl asuser 501', script)
            self.assertNotIn('must-not-travel', script)
        self.close_window(window)

    def test_connect_requests_authorization_before_any_usb_operation(self):
        window = Window()
        with patch.object(window, 'needs_admin', return_value=True), patch.object(window, 'elevate') as elevate, patch('a7c_installer.transport.sony_usb.SonyUsb') as usb:
            window.run_camera('connect')
            elevate.assert_called_once_with('connect')
            usb.assert_not_called()
        self.close_window(window)

    def test_denied_authorization_keeps_connection_retryable(self):
        from types import SimpleNamespace
        window = Window()
        with patch.object(window, 'needs_admin', return_value=True), patch.object(sys, 'platform', 'darwin'), patch('a7c_installer.gui.os.getuid', return_value=501, create=True), patch('a7c_installer.gui.subprocess.run', return_value=SimpleNamespace(returncode=1)):
            window.run_camera('connect')
            self.wait_task(window)
        self.assertTrue(window.detect_button.isEnabled())
        self.assertTrue(window.setup_panel.isHidden())
        self.assertFalse(window.install_button.isEnabled())
        self.assertIn('授权', window.connection_note.text())
        self.close_window(window)

    def test_first_screen_does_not_offer_credentials_or_maintenance_buttons(self):
        from PySide6.QtWidgets import QPushButton
        window = Window()
        self.assertTrue(window.setup_panel.isHidden())
        self.assertTrue(window.output.isHidden())
        labels = [b.text() for b in window.findChildren(QPushButton) if not b.isHidden()]
        self.assertNotIn('以管理员权限重新打开', labels)
        self.assertNotIn('卸载相机服务', labels)
        self.assertFalse(window.password.isEnabled())
        self.close_window(window)

    def test_clean_camera_shows_install_instead_of_update_or_uninstall(self):
        from test_installer import MemoryCamera
        from a7c_installer.bundle import Bundle
        from unittest.mock import MagicMock
        session = MagicMock()
        session.__enter__.return_value = MemoryCamera(Bundle())
        window = Window()
        with patch('a7c_installer.transport.sony_usb.SonyUsb', return_value=session):
            window.run_camera('connect')
            self.wait_task(window)
        self.assertIn('未安装', window.status.text())
        self.assertEqual(window.install_button.text(), '安装到相机')
        self.assertTrue(window.uninstall_button.isHidden())
        self.close_window(window)

    def test_uninstall_completion_clears_detected_installed_state(self):
        window = Window(demo=True)
        self.assertFalse(window.uninstall_button.isHidden())
        window.completed({'uninstalled': True, 'message': '服务已移除'})
        self.assertIsNone(window.installed_version)
        self.assertIn('未安装', window.installation_status.text())
        self.assertTrue(window.uninstall_button.isHidden())
        self.assertEqual(window.install_button.text(), '安装到相机')
        self.close_window(window)

    def test_failed_reconnection_does_not_keep_previous_camera_installed_state(self):
        window = Window(demo=True)
        window.demo = False
        window.connecting = True
        window.failed('找不到相机')
        self.assertFalse(window.installation_checked)
        self.assertTrue(window.installation_status.isHidden())
        self.assertTrue(window.uninstall_button.isHidden())
        self.close_window(window)

    def test_demo_ftp_check_never_connects_to_server(self):
        window = Window(demo=True)
        with patch('a7c_installer.gui.test_ftp') as ftp:
            window.test_target()
            ftp.assert_not_called()
        self.close_window(window)

    def test_gui_can_start_installed_service_without_reinstall(self):
        from test_installer import MemoryCamera, SETTINGS
        from a7c_installer.bundle import Bundle
        from a7c_installer.operations import Installer
        from unittest.mock import MagicMock
        camera = MemoryCamera(Bundle())
        Installer(camera, ftp_test=lambda _: None).install(SETTINGS)
        camera.events.clear()
        window = Window()
        session = MagicMock()
        session.__enter__.return_value = camera
        with patch('a7c_installer.transport.sony_usb.SonyUsb', return_value=session), patch('a7c_installer.gui.test_ftp') as ftp:
            window.run_camera('start')
            self.wait_task(window)
        self.assertEqual(camera.events, [('start-service',)])
        ftp.assert_not_called()
        self.assertIn('健康检查通过', window.status.text())
        self.assertIn('无需关机或取电池', window.connection_note.text())
        self.assertFalse(window.usb_session.is_open)
        self.close_window(window)

    def test_activation_failure_does_not_show_service_as_started(self):
        window = Window(demo=True)
        window.completed({'version':'test-version', 'service_started':False, 'message':'安装完成但启动未确认'})
        self.assertIn('服务未就绪', window.status.text())
        self.assertEqual(window.installed_version, 'test-version')
        self.close_window(window)

    def test_display_upgrade_restart_is_visible_even_when_old_service_is_running(self):
        window = Window(demo=True)
        window.completed({'version':'test-version', 'service_started':True,
                          'requires_power_cycle':True, 'message':'显示组件更新后需重启'})
        self.assertEqual(window.status.text(), '安装完成，请重启相机')
        self.close_window(window)

    def test_unknown_action_never_opens_usb_or_falls_through_to_uninstall(self):
        window = Window()
        with patch('a7c_installer.transport.sony_usb.SonyUsb') as usb:
            window.run_camera('unknown')
        usb.assert_not_called()
        self.assertIn('未知相机操作', window.connection_note.text())
        self.close_window(window)

    def test_ftp_result_stays_next_to_button_without_replacing_camera_status(self):
        from test_installer import SETTINGS
        window = Window(demo=True)
        window.demo = False
        window.apply_saved_config(SETTINGS.public())
        window.password.setText(SETTINGS.password)
        status = window.status.text()
        note = window.connection_note.text()
        with patch.object(window, 'start'):
            window.test_target()
        self.assertIn('正在测试', window.test_result.text())
        window.completed({'scope': 'computer-to-FTP'})
        self.assertIn('测试通过', window.test_result.text())
        self.assertEqual(window.status.text(), status)
        self.assertEqual(window.connection_note.text(), note)
        for field, value in ((window.host, '192.168.1.21'), (window.port, 2121),
                             (window.username, 'other-user'), (window.password, 'other-secret'),
                             (window.directory, '/Other')):
            window.completed({'scope': 'computer-to-FTP'})
            field.setValue(value) if field is window.port else field.setText(value)
            self.assertEqual(window.test_result.text(), '')
        self.close_window(window)

    def test_ftp_failure_is_inline_and_keeps_camera_state(self):
        from test_installer import SETTINGS
        from a7c_installer.configuration import InstallerError
        window = Window(demo=True)
        window.demo = False
        window.apply_saved_config(SETTINGS.public())
        window.password.setText(SETTINGS.password)
        status = window.status.text()
        with patch('a7c_installer.gui.test_ftp', side_effect=InstallerError('FTP 连接失败')):
            window.test_target()
            self.wait_task(window)
        self.assertIn('测试失败', window.test_result.text())
        self.assertIn('FTP 连接失败', window.test_result.toolTip())
        self.assertEqual(window.status.text(), status)
        self.close_window(window)

    def test_authorized_relaunch_resumes_the_requested_action(self):
        from unittest.mock import MagicMock
        from a7c_installer.gui import main
        window = MagicMock()
        window.demo = False
        window.task = None
        app = MagicMock()
        app.exec.return_value = 0
        with patch.object(sys, 'argv', ['app', '--camera-action', 'connect']), patch('a7c_installer.gui.QApplication', return_value=app), patch('a7c_installer.gui.Window', return_value=window), patch('a7c_installer.gui.QTimer.singleShot', side_effect=lambda delay, callback: callback()):
            self.assertEqual(main(), 0)
        window.run_camera.assert_called_once_with('connect')

    def test_completion_instructions_are_visible_without_expanding_logs(self):
        window = Window(demo=True)
        message = '安装完成。请断开 USB，正常关机后完全断电一次。'
        window.completed({'message': message})
        self.assertTrue(window.output.isHidden())
        self.assertEqual(window.connection_note.text(), message)
        self.close_window(window)

    def test_offline_selfcheck_never_enumerates_usb(self):
        from a7c_installer.gui import main
        from a7c_installer.bundle import Bundle
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            with patch.object(sys, 'argv', ['app', '--self-check', str(report), '--offline']), patch('a7c_installer.transport.sony_usb.detect') as detect:
                self.assertEqual(main(), 0)
                detect.assert_not_called()
            result = json.loads(report.read_text())
            bundle = Bundle()
            self.assertEqual(result['payload_version'], bundle.version)
            self.assertEqual(result['payload_sha256'], hashlib.sha256(bundle.path.read_bytes()).hexdigest())
            self.assertEqual(result['usb'], 'skipped: offline self-check')


if __name__ == '__main__':
    unittest.main()
