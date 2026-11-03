"""Qt presentation only; operations run off the UI thread through the shared engine."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QCoreApplication, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QFormLayout, QSpinBox,
    QGroupBox, QProgressBar, QToolButton, QMenu)
from .configuration import FtpSettings, InstallerError
from .bundle import Bundle
from .ftp_check import test_ftp
from .operations import Installer
from .transport.session import DesktopSession
from .log_view import RuntimeLog
from . import __version__


class Task(QThread):
    message = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.done.emit(self.function(self.message.emit))
        except InstallerError as ex:
            self.failed.emit(str(ex))
        except Exception:
            self.failed.emit("操作未完成。请保留相机状态，重新检测；若安装已开始，选择恢复上次安装。")


class Window(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.task = None
        self.usb_session = DesktopSession()
        self.closing = False
        self.loaded_ftp = None
        self.installed_version = None
        self.installation_checked = False
        self.camera_ready = demo
        self.connecting = False
        self.testing_ftp = False
        self.relaunching = False
        self.setWindowTitle("A7C 自动上传")
        self.resize(700, 300)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)
        title = QLabel("A7C 自动上传")
        title.setObjectName("title")
        header = QHBoxLayout()
        header.addWidget(title, 1)
        self.guide_button = QPushButton('使用帮助')
        self.guide_button.setObjectName('quiet')
        self.guide_button.clicked.connect(self.show_guide)
        header.addWidget(self.guide_button)
        self.more_button = QToolButton()
        self.more_button.setText('更多')
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        self.more_menu = QMenu(self.more_button)
        self.reread_action = self.more_menu.addAction('重新读取配置')
        self.reread_action.triggered.connect(lambda: self.run_camera('connect'))
        self.start_service_action = self.more_menu.addAction('启动上传服务')
        self.start_service_action.triggered.connect(lambda: self.run_camera('start'))
        self.start_service_action.setEnabled(False)
        self.diagnose_button = self.more_menu.addAction('读取运行日志')
        self.diagnose_button.triggered.connect(lambda: self.run_camera('diagnose'))
        self.restore_button = self.more_menu.addAction('恢复上次安装')
        self.restore_button.triggered.connect(lambda: self.run_camera('restore'))
        self.driver_prepare = self.more_menu.addAction('准备 Windows 驱动')
        self.driver_restore = self.more_menu.addAction('恢复普通 USB 导入')
        self.driver_prepare.triggered.connect(lambda: self.run_driver(False))
        self.driver_restore.triggered.connect(lambda: self.run_driver(True))
        self.restore_driver = self.more_menu.addAction('卸载服务时恢复 Windows USB 驱动')
        self.restore_driver.setCheckable(True)
        self.restore_driver.setChecked(True)
        for action in (self.driver_prepare, self.driver_restore, self.restore_driver):
            action.setVisible(sys.platform == 'win32')
        self.more_button.setMenu(self.more_menu)
        header.addWidget(self.more_button)
        layout.addLayout(header)
        subtitle = QLabel("将相机视频自动传到家中的 FTP 服务器")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        camera_card = QGroupBox('相机')
        camera_layout = QHBoxLayout(camera_card)
        camera_layout.setContentsMargins(18, 20, 18, 16)
        connection = QVBoxLayout()
        self.status = QLabel("尚未连接相机")
        self.status.setWordWrap(True)
        self.status.setObjectName("status")
        connection.addWidget(self.status)
        self.installation_status = QLabel()
        self.installation_status.setWordWrap(True)
        self.installation_status.hide()
        connection.addWidget(self.installation_status)
        self.connection_note = QLabel('用 USB 连接已开机的相机，选择「海量存储器」。')
        self.connection_note.setObjectName('muted')
        self.connection_note.setWordWrap(True)
        connection.addWidget(self.connection_note)
        camera_layout.addLayout(connection, 1)
        self.detect_button = QPushButton("连接相机")
        self.detect_button.setObjectName('primary')
        self.detect_button.setToolTip('读取本上传器已有配置；安装完成、断开连接或关闭窗口时退出 USB 服务模式。')
        self.detect_button.clicked.connect(self.connect_or_disconnect)
        camera_actions = QVBoxLayout()
        camera_actions.addWidget(self.detect_button)
        self.uninstall_button = QPushButton('卸载相机服务')
        self.uninstall_button.setObjectName('danger')
        self.uninstall_button.clicked.connect(lambda: self.run_camera('uninstall'))
        self.uninstall_button.hide()
        camera_actions.addWidget(self.uninstall_button)
        camera_layout.addLayout(camera_actions)
        layout.addWidget(camera_card)
        self.setup_panel = QWidget()
        setup = QVBoxLayout(self.setup_panel)
        setup.setContentsMargins(0, 0, 0, 0)
        setup.setSpacing(14)
        ftp = QGroupBox("上传到哪里")
        form = QFormLayout(ftp)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setContentsMargins(18, 22, 18, 18)
        form.setSpacing(10)
        self.saved_status = QLabel('连接相机后自动读取已有配置；首次安装请填写下方信息。')
        self.saved_status.setWordWrap(True)
        form.addRow(self.saved_status)
        self.host = QLineEdit()
        self.host.setPlaceholderText("例如 192.168.1.20")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(21)
        self.port.setFixedWidth(84)
        self.port.setToolTip('FTP 端口，通常为 21')
        self.port.setAccessibleName('FTP 端口')
        self.username = QLineEdit()
        self.username.setPlaceholderText("仅有目标目录权限的专用账号")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("密码只用于本次配置，不写入电脑日志")
        self.directory = QLineEdit("/")
        address = QHBoxLayout()
        address.addWidget(self.host, 1)
        port_label = QLabel('端口')
        port_label.setObjectName('muted')
        port_label.setBuddy(self.port)
        address.addWidget(port_label)
        address.addWidget(self.port)
        form.addRow('服务器', address)
        for label, widget in (("用户名", self.username),
                              ("密码", self.password), ("FTP 目录", self.directory)):
            form.addRow(label, widget)
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_target)
        note = QLabel("相机须已连上家中 Wi-Fi；FTP 目录须已创建。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        form.addRow(note)
        setup.addWidget(ftp)
        self.display = QCheckBox("在相机上显示上传状态和进度")
        self.display.setChecked(True)
        setup.addWidget(self.display)
        row = QHBoxLayout()
        row.addWidget(self.test_button)
        self.test_result = QLabel()
        self.test_result.setObjectName('ftpTestResult')
        self.test_result.setTextFormat(Qt.PlainText)
        self.test_result.setWordWrap(True)
        row.addWidget(self.test_result, 1)
        for field in (self.host, self.username, self.password, self.directory):
            field.textChanged.connect(self.clear_test_result)
        self.port.valueChanged.connect(self.clear_test_result)
        self.install_button = QPushButton("安装到相机")
        self.install_button.setObjectName("primary")
        self.install_button.clicked.connect(lambda: self.run_camera("install"))
        row.addWidget(self.install_button)
        self.uninstall_button.setToolTip("停止上传与显示，移除自启、程序和当前 FTP 配置；保留媒体与回退备份。Windows 可勾选卸载后恢复电脑驱动。")
        setup.addLayout(row)
        layout.addWidget(self.setup_panel)
        self.setup_panel.setVisible(demo)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.details_button = QToolButton()
        self.details_button.setText('运行日志')
        self.details_button.setCheckable(True)
        self.details_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_button.setArrowType(Qt.RightArrow)
        self.details_button.toggled.connect(self.toggle_details)
        log_header = QHBoxLayout()
        log_header.addWidget(self.details_button)
        log_header.addStretch()
        self.copy_log_button = QPushButton('复制日志')
        self.copy_log_button.setObjectName('quiet')
        self.copy_log_button.setToolTip('复制本次运行的日志，便于反馈问题。')
        self.copy_log_button.clicked.connect(lambda: QApplication.clipboard().setText(self.output.toPlainText()))
        self.copy_log_button.hide()
        log_header.addWidget(self.copy_log_button)
        layout.addLayout(log_header)
        self.output = RuntimeLog()
        self.output.append_entry('安装器已就绪。')
        self.output.hide()
        layout.addWidget(self.output, 1)
        footer = QLabel(f"ILCE-7C · 固件 2.00 · 安装器 {__version__}")
        footer.setObjectName("muted")
        layout.addWidget(footer)
        self.setStyleSheet("""
            QMainWindow { background: #f6f8fb; }
            QWidget { color: #18283b; font-size: 13px; }
            QLabel#title { font-size: 28px; font-weight: 650; }
            QLabel#muted { color: #637085; font-size: 12px; }
            QLabel#status { font-weight: 600; }
            QGroupBox { background: white; border: 1px solid #dce2ea; border-radius: 9px;
                        font-weight: 600; margin-top: 8px; padding-top: 9px; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
            QLineEdit, QSpinBox { background: white; border: 1px solid #cad3df; border-radius: 5px;
                                 padding: 7px; selection-background-color: #3375c5; }
            QPushButton { border: 1px solid #cbd5e0; background: white; border-radius: 6px; padding: 9px 14px; }
            QPushButton:hover { background: #eaf0f8; }
            QPushButton#primary { background: #245da7; color: white; border-color: #245da7; }
            QPushButton#danger { color: #a63737; border-color: #d8a8a8; }
            QPushButton#quiet { border: 0; background: transparent; color: #637085; padding: 6px; }
            QToolButton { border: 0; background: transparent; color: #637085; padding: 6px; }
            QToolButton::menu-indicator { image: none; }
            QMenu { background: white; border: 1px solid #dce2ea; padding: 4px; }
            QMenu::item { padding: 7px 16px; }
            QMenu::item:selected { background: #eaf0f8; }
            QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled {
                color: #8993a3; background: #edf0f4; border-color: #dce2ea; }
            QProgressBar { max-height: 5px; border: 0; background: #dce5f0; }
            QProgressBar::chunk { background: #245da7; }
        """)
        if demo:
            self.status.setText("A7C 已连接 · 演示")
            self.connection_note.setText('已读取上传配置；密码留空即可沿用。')
            self.detect_button.setText('断开连接')
            self.detect_button.setObjectName('secondary')
            self.apply_saved_config({'host': '192.168.1.20', 'port': 21,
                                     'username': 'camera-upload', 'directory': '/Camera'})
            self.set_installation(Bundle().version)
        self.set_fields_enabled(self.camera_ready)
        self.install_button.setEnabled(self.camera_ready)

    def set_installation(self, version, checked=True):
        self.installed_version = version
        self.installation_checked = checked
        self.refresh_installation()

    def refresh_installation(self):
        installed = self.installation_checked and bool(self.installed_version)
        self.installation_status.setVisible(self.installation_checked)
        self.installation_status.setText('已安装 · ' + self.installed_version if installed else '未安装上传服务')
        self.installation_status.setStyleSheet('color: #247044; font-weight: 600;' if installed else 'color: #637085;')
        self.installation_status.setToolTip('状态来自本次连接读取或刚完成的安装；重新连接时会刷新。')
        self.install_button.setText('更新配置' if installed else '安装到相机')
        self.uninstall_button.setVisible(installed)
        connected = self.usb_session.is_open or self.demo
        self.uninstall_button.setEnabled(installed and self.camera_ready and connected and self.task is None)
        self.start_service_action.setEnabled(installed and self.camera_ready and connected and self.task is None)
        self.uninstall_button.setToolTip('卸载上传与显示服务，保留照片、视频和 SD 回执。' if connected
                                        else '已安装；请先连接相机，再卸载服务。')

    def toggle_details(self, visible):
        self.output.setVisible(visible)
        self.copy_log_button.setVisible(visible)
        self.details_button.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
        self.resize(self.width(), self.sizeHint().height())

    def needs_admin(self):
        return not self.demo and sys.platform == 'darwin' and os.geteuid() != 0

    def connect_or_disconnect(self):
        if self.usb_session.is_open:
            self.start(self.disconnect_camera)
        else:
            self.run_camera('connect')

    def disconnect_camera(self, log):
        self.usb_session.close(log)
        return {'disconnected': True}

    def set_fields_enabled(self, enabled):
        for field in (self.host, self.port, self.username, self.password, self.directory, self.test_button, self.display):
            field.setEnabled(enabled)

    def clear_test_result(self):
        self.test_result.clear()
        self.test_result.setToolTip('')

    def set_test_result(self, text, color, detail=''):
        self.test_result.setText(text)
        self.test_result.setStyleSheet(f'color: {color};')
        self.test_result.setToolTip(detail)

    def apply_saved_config(self, config):
        self.clear_test_result()
        self.loaded_ftp = dict(config) if config else None
        if config:
            self.host.setText(config['host'])
            self.port.setValue(config['port'])
            self.username.setText(config['username'])
            self.directory.setText(config['directory'])
            self.password.clear()
            self.saved_status.setText('已读取相机配置 · 密码已保存，留空沿用；填写新密码可替换。')
            self.password.setPlaceholderText('已保存；留空沿用，输入新密码可替换')
        else:
            self.saved_status.setText('首次安装，请填写 FTP 服务器和账号。')
            self.password.setPlaceholderText('请输入 FTP 密码，不保存到电脑或日志')

    def show_guide(self):
        from .help_view import HelpDialog
        HelpDialog(self).exec()

    def settings(self):
        value = FtpSettings(self.host.text().strip(), self.port.value(), self.username.text(),
                            self.directory.text(), self.password.text())
        if self.loaded_ftp and not value.password:
            return value.validate_target()
        return value.validate()

    def start(self, function):
        if self.task is not None:
            return
        self.task = Task(function, self)
        self.task.message.connect(self.output.append_entry)
        self.task.done.connect(self.completed)
        self.task.failed.connect(self.failed)
        self.task.finished.connect(self.finished)
        for button in (self.detect_button, self.more_button, self.install_button, self.test_button, self.uninstall_button):
            button.setEnabled(False)
        self.driver_prepare.setEnabled(False)
        self.driver_restore.setEnabled(False)
        self.set_fields_enabled(False)
        self.progress.show()
        self.task.start()

    def run_camera(self, action):
        if action not in ('connect', 'diagnose', 'install', 'restore', 'uninstall', 'start'):
            self.failed('未知相机操作，未执行。')
            return
        if self.demo:
            self.output.append_entry("演示模式未连接或修改相机。")
            return
        if self.needs_admin():
            self.elevate(action)
            return
        try:
            settings = self.settings() if action == 'install' else None
            expected = dict(self.loaded_ftp) if self.loaded_ftp else None
            preserve_password = settings is not None and not settings.password and expected is not None
            display = self.display.isChecked()
            restore_driver = self.restore_driver.isChecked() and sys.platform == 'win32'
        except InstallerError as ex:
            self.failed(str(ex))
            return
        def work(log):
            with self.usb_session.use(log) as camera:
                engine = Installer(camera, Bundle(), log)
                if action == "connect":
                    return {"inspection": engine.inspect()}
                if action == "diagnose":
                    return {"inspection": engine.inspect(), "runtime": camera.runtime_report()}
                if action == "install":
                    result = engine.install(settings, display=display, preserve_password=preserve_password, expected_config=expected)
                elif action == "restore":
                    result = engine.restore()
                elif action == "start":
                    result = engine.start()
                else:
                    result = engine.uninstall()
            # End the USB session only once the whole operation is complete.
            self.usb_session.close(log)
            if restore_driver and action == 'uninstall':
                from .drivers.windows import DriverManager
                try:
                    result['driver_restore'] = DriverManager(log=log).restore()
                    result['message'] += '\n' + result['driver_restore']['message']
                except InstallerError as ex:
                    result['message'] += '\n相机服务已卸载，Windows 驱动恢复未完成：' + str(ex) + ' 可单独点击“恢复普通 USB 导入”重试。'
            return result
        if action == 'connect':
            self.connecting = True
            self.set_installation(None, checked=False)
            self.loaded_ftp = None
            self.saved_status.setText('正在连接并读取配置…')
            self.password.setPlaceholderText('待读取相机配置')
            self.status.setText('正在连接相机…')
        elif action == 'install':
            self.status.setText('正在安装并启动服务…')
            self.connection_note.setText('完成后会自动检查服务状态，请保持 USB 连接。')
        elif action == 'start':
            self.status.setText('正在启动并检查服务…')
            self.connection_note.setText('请保持 USB 连接，通过检查后即可拔线使用。')
        self.start(work)

    def run_driver(self, restore):
        if self.demo:
            self.output.append_entry('演示模式未修改 Windows 驱动。')
            return
        def work(log):
            from .drivers.windows import DriverManager
            self.usb_session.close(log)
            manager = DriverManager(log=log)
            return manager.restore() if restore else manager.ensure()
        self.start(work)

    def test_target(self):
        if self.task is not None:
            return
        if self.demo:
            self.output.append_entry('演示模式未连接 FTP 服务器。')
            return
        self.testing_ftp = True
        self.set_test_result('正在测试…', '#637085')
        try:
            settings = self.settings()
        except InstallerError as ex:
            self.failed(str(ex))
            return
        expected = dict(self.loaded_ftp) if self.loaded_ftp else None
        preserve = not settings.password and expected is not None
        if preserve and self.needs_admin():
            self.testing_ftp = False
            self.clear_test_result()
            self.elevate('connect')
            return
        def work(log):
            if not preserve:
                return test_ftp(settings)
            with self.usb_session.use(log) as camera:
                engine = Installer(camera, Bundle(), log)
                engine.verify_firmware()
                resolved = engine.resolve_settings(settings, True, expected)
            return test_ftp(resolved)
        self.start(work)

    def completed(self, result):
        if "inspection" in result:
            r = result["inspection"]
            self.camera_ready = r['supported'] and not r['pending_recovery']
            self.set_installation(r['installed_version'])
            self.setup_panel.setVisible(r['supported'])
            text = ('A7C 已连接 · 已安装' if r['installed_version'] else 'A7C 已连接 · 未安装') if r['supported'] else '此固件暂不支持安装'
            note = '已安装上传服务，可更新配置。' if r['installed_version'] else '填写下方 FTP 账号，即可安装上传服务。'
            if r['supported'] and r['installed_version']:
                health = r.get('health', {})
                text = 'A7C 已连接 · ' + ('服务正常' if health.get('state')=='ready' else '服务未就绪')
                note = health.get('detail', '服务状态未确认')
            if r["pending_recovery"]:
                text = '上次安装未完成'
                note = '请从「更多」选择「恢复上次安装」。'
            self.status.setText(text)
            self.connection_note.setText(note if r['supported'] else '此安装器仅支持第一代 ILCE-7C / 固件 2.00。')
            self.detect_button.setText('断开连接')
            self.detect_button.setObjectName('secondary')
            self.detect_button.style().unpolish(self.detect_button)
            self.detect_button.style().polish(self.detect_button)
            self.apply_saved_config(r['ftp'])
            self.output.append_entry('已自动读取本上传器的配置；密码未回填到界面。' if r['ftp'] else '相机没有本上传器的现有配置，请填写后安装。')
            for path, content in result.get("runtime", {}).items():
                self.output.append_entry(path + "\n" + content + "\n")
            if 'runtime' in result:
                self.details_button.setChecked(True)
            self.resize(self.width(), self.sizeHint().height())
        elif result.get("elevated"):
            self.relaunching = True
        elif result.get('disconnected'):
            self.camera_ready = False
            self.loaded_ftp = None
            self.password.clear()
            self.setup_panel.hide()
            self.status.setText('已断开相机')
            self.connection_note.setText('可以拔掉 USB。再次连接时请确认相机显示 USB 连接界面。')
        elif result.get('drivers_restored') or result.get('driver_ready'):
            self.status.setText('Windows 驱动操作完成')
            self.connection_note.setText(result.get('message', '现在可以连接相机。'))
            self.output.append_entry(result.get('message', '相机普通模式驱动已就绪；安装时会自动准备服务模式驱动。'))
        elif result.get("scope") == "computer-to-FTP":
            self.testing_ftp = False
            self.set_test_result('✓ 测试通过', '#247044',
                                 '电脑至 FTP：写入、长度确认和清理通过；相机须能访问同一 FTP 服务器。')
            self.output.append_entry("电脑至 FTP：写入、长度确认和清理通过；相机需连接同一可达网络。", 'OK')
        else:
            message = result.get("message", "应用备份已恢复。请断开 USB，正常关机后完全断电一次。")
            if result.get('uninstalled'):
                self.set_installation(None)
                self.status.setText('相机服务已卸载，需完全断电完成收尾')
            elif result.get('restored'):
                self.set_installation(None, checked=False)
                self.status.setText('已恢复上次安装，请重新连接确认状态')
            elif result.get('started'):
                self.set_installation(result['version'])
                self.status.setText('上传服务正常 · 健康检查通过')
            elif result.get('version'):
                self.set_installation(result['version'])
                self.status.setText('安装完成，请重启相机' if result.get('requires_power_cycle') else
                                    '安装完成，服务未就绪' if result.get('service_started') is False else
                                    '安装成功 · 服务正常' if result.get('service_started') else '安装成功 · 已安装')
            else:
                self.status.setText('操作完成')
            self.connection_note.setText(message)
            self.output.append_entry(message)
            self.password.clear()
            if 'ftp' in result:
                self.apply_saved_config(result['ftp'])
            elif result.get('uninstalled') or result.get('restored'):
                self.apply_saved_config(None)

    def failed(self, message):
        if self.testing_ftp:
            self.testing_ftp = False
            self.set_test_result('测试失败，查看日志', '#a63737', message)
            self.output.append_entry(message, 'ERROR')
            return
        if self.connecting:
            self.set_installation(None, checked=False)
            self.apply_saved_config(None)
            self.camera_ready = False
            self.setup_panel.hide()
            self.status.setText('未连接到相机')
            self.detect_button.setObjectName('primary')
            self.detect_button.style().unpolish(self.detect_button)
            self.detect_button.style().polish(self.detect_button)
        else:
            self.status.setText('操作未完成')
        if '当前没有唯一的普通/服务模式设备' in message:
            self.connection_note.setText('请确认相机开机、USB 设为「海量存储器」，再重新连接。')
        else:
            self.connection_note.setText(message)
        self.output.append_entry(message, 'ERROR')

    def finished(self):
        self.task.wait()
        self.task.deleteLater()
        self.task = None
        self.connecting = False
        self.testing_ftp = False
        self.progress.hide()
        for button in (self.detect_button, self.more_button):
            button.setEnabled(True)
        self.driver_prepare.setEnabled(True)
        self.driver_restore.setEnabled(True)
        self.set_fields_enabled(self.camera_ready)
        self.install_button.setEnabled(self.camera_ready)
        self.detect_button.setText('断开连接' if self.usb_session.is_open else '连接相机')
        if not self.usb_session.is_open and self.camera_ready:
            self.camera_ready = False
            self.set_fields_enabled(False)
            self.install_button.setEnabled(False)
        self.refresh_installation()
        if self.relaunching or self.closing:
            self.close()

    def elevate(self, action='connect'):
        if sys.platform != "darwin":
            return
        # The form is only offered after connecting. Authorize before the user
        # enters credentials, so the relaunch does not need a secret handoff.
        if action not in ('connect', 'diagnose', 'restore', 'uninstall', 'start'):
            action = 'connect'
        self.status.setText('请在系统窗口中允许 USB 访问…')
        self.connection_note.setText('授权用于释放相机 USB 接口，完成后会自动继续。')
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, str(Path(__file__).resolve().parents[1] / "app.py")]
        args += ['--camera-action', action]
        # AppleScript's privileged shell starts outside the user's audit
        # session. Root alone cannot prompt for removable-volume access.
        # Keep root credentials while adopting the caller's GUI/audit context.
        args = ['/bin/launchctl', 'asuser', str(os.getuid()), *args]
        command = shlex.join(args) + " >/dev/null 2>&1 &"
        # Administrator authentication is entirely handled by macOS; no password
        # is captured by this app or passed through argv/environment.
        script = 'do shell script ' + __import__("json").dumps(command, ensure_ascii=False) + ' with administrator privileges'
        self.start(lambda log: self._elevated(script))

    def _elevated(self, script):
        # Return immediately after launching the elevated GUI. AppleScript waits
        # only for the detached launch, not for the lifetime of the new app.
        result = subprocess.run(["osascript", "-e", script], capture_output=True)
        if result.returncode:
            raise InstallerError("未获得 USB 访问授权。请再次点击连接相机，在系统窗口中允许。")
        return {"elevated": True}

    def closeEvent(self, event):
        if self.task is not None and self.task.isRunning():
            event.ignore()
            self.status.setText("操作进行中，请等待 USB 会话安全退出后关闭。")
            return
        if self.usb_session.is_open:
            event.ignore()
            self.closing = True
            self.start(self.disconnect_camera)
            return
        super().closeEvent(event)


def main():
    if "--self-check" in sys.argv:
        import hashlib
        import json
        import platform
        from .transport.sony_usb import detect
        # Force the dynamically loaded USB/authentication dependencies to load.
        from pmca.usb.sony import SonySenserAuthDevice
        from pmca.usb.driver.generic.libusb import UsbBackend
        index = sys.argv.index("--self-check")
        bundle = Bundle()
        report = {"installer_version": __version__, "platform": platform.platform(),
                  "payload_version": bundle.version, "payload_files": len(bundle.files),
                  "payload_sha256": hashlib.sha256(bundle.path.read_bytes()).hexdigest(),
                  "firmware": bundle.firmware["version"],
                  "usb": "skipped: offline self-check" if "--offline" in sys.argv else detect()}
        from .documentation import GUIDES, read_guide
        for name in GUIDES.values():
            read_guide(name)
        report['bundled_help'] = {'guides': len(GUIDES), 'status': 'passed; readable inside App'}
        if sys.platform == 'win32':
            import ctypes
            from .drivers.windows_native import WindowsBackend, Device, PrepareOptions, InstallOptions
            dll = WindowsBackend().dll()
            dll.wdi_is_driver_supported.argtypes = [ctypes.c_int, ctypes.c_void_p]
            if not dll.wdi_is_driver_supported(1, None):
                raise InstallerError('内置驱动组件未包含 libusb-win32。')
            report['windows_driver'] = {'libwdi': '1.5.1', 'libusb_win32': '1.4.0.2',
                'component': 'loaded and hash verified; no device enumeration or driver changes',
                'abi_sizes': [ctypes.sizeof(t) for t in (Device, PrepareOptions, InstallOptions)]}
        Path(sys.argv[index + 1]).write_text(json.dumps(report, indent=2) + "\n")
        return 0
    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setFont(QFont("Microsoft YaHei UI", 10))
    elif sys.platform == "darwin":
        app.setFont(QFont("PingFang SC", 10))
    app.setApplicationName("A7C Installer")
    window = Window("--demo" in sys.argv)
    window.show()
    if '--camera-action' in sys.argv and not window.demo:
        index = sys.argv.index('--camera-action')
        if index + 1 < len(sys.argv):
            action = sys.argv[index + 1]
            if action in ('connect', 'diagnose', 'restore', 'uninstall', 'start'):
                QTimer.singleShot(0, lambda: window.run_camera(action))
    if "--screenshot" in sys.argv:
        index = sys.argv.index("--screenshot")
        target = sys.argv[index + 1]
        QTimer.singleShot(800, lambda: (window.grab().save(target), app.quit()))
    result = app.exec()
    if window.task is not None and window.task.isRunning():
        window.task.wait()
        app.processEvents()
    window.usb_session.close()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return result
