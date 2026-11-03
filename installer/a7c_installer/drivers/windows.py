"""Device-scoped libusb binding with a durable pre-change journal.

Only our generated OEM packages are removed. Existing libusb bindings are
borrowed, never claimed as ours. No camera protocol commands are sent here.
"""
import json
import os
from pathlib import Path
import re
import time
import uuid
from ..configuration import InstallerError

NORMAL = (0x0d28, 0x0d29)
SERVICE = 0x0336
COMPATIBLE = ('libusb0', 'libusbk', 'winusb')


def target(device):
    match = re.fullmatch(r'USB\\VID_054C&PID_(0D28|0D29|0336)(?:&REV_[0-9A-F]{4})?\\[^\\]+', device['id'].upper())
    if not match:
        raise InstallerError('USB 设备不在 A7C 驱动范围内；未修改驱动。')
    return int(match[1], 16)


class DriverManager:
    def __init__(self, backend=None, log=lambda _: None):
        if backend is None:
            from .windows_native import WindowsBackend
            backend = WindowsBackend()
        self.backend = backend
        self.log = log

    def ensure(self, service=False):
        changed = False
        for _ in range(3):
            result = self._ensure_once(service)
            changed = changed or result['changed']
            if result.get('normal_mode_changed'):
                self.log('同一台 A7C 已切换普通 USB 接口，继续准备当前接口')
                continue
            result['changed'] = changed
            return result
        raise InstallerError('相机 USB 接口持续切换；驱动恢复记录已保留，请保持海量存储器模式后重试。')

    def _ensure_once(self, service):
        with self.backend.lock():
            state = self.backend.load()
            devices = self.backend.inventory(present=True)
            if any('VID_054C&PID_03E2' in d['id'].upper() for d in devices):
                raise InstallerError('相机处于固件更新模式，未安装驱动。')
            candidates = [d for d in devices if re.match(r'USB\\VID_054C&PID_(0D28|0D29|0336)\\', d['id'], re.I)]
            if len(candidates) != 1:
                raise InstallerError('请只连接一台 A7C，开机并选择海量存储器；未找到唯一的相机接口。')
            device = candidates[0]
            pid = target(device)
            if pid in NORMAL:
                if device['bus_name'].strip() != 'ILCE-7C':
                    raise InstallerError('USB 设备报告的型号不是 ILCE-7C，未更换驱动。')
            elif not service:
                # Do not install a shared Sony service PID based only on VID/PID.
                raise InstallerError('当前是服务模式；请先退出服务模式或重新连接普通模式，再准备驱动。')
            if device['driver'].lower() in COMPATIBLE:
                self.log('USB 驱动已可用：' + device['driver'])
                return {'driver_ready': True, 'changed': False, 'driver': device['driver'].lower()}
            self.backend.check_admin()
            prior = state['devices'].get(device['id'])
            if prior and prior['status'] != 'restored':
                raise InstallerError('这台设备有未完成的驱动变更；请先恢复 Windows USB 驱动。')
            token = uuid.uuid4().hex
            # System-provided INF stays in Windows INF; third-party original
            # packages are exported before any changes, so future recovery is local.
            backup = self.backend.backup_original(device, token)
            row = {'id': device['id'], 'hardware_id': device['hardware_id'],
                   'before_inf': device['inf'], 'before_driver': device['driver'],
                   'backup': backup, 'inf_name': 'a7c_' + token + '.inf',
                   'token': token, 'published_inf': None, 'status': 'preparing'}
            state['devices'][device['id']] = row
            self.backend.save(state)
            self.log('已记录原驱动；准备 A7C 专用 libusb-win32 驱动包')
            # prepare may add a per-package trust certificate. Journal already
            # exists; generated files stay available if power/process is lost.
            self.backend.prepare(device, row)
            row['published_inf'] = self.backend.stage(row)
            row['status'] = 'staged'
            self.backend.save(state)
            self.backend.install(device, row)
            row['status'] = 'installed'
            self.backend.save(state)
            if self.backend.wait_bound(device['id'], 'libusb0') == 'normal_mode_changed':
                return {'normal_mode_changed': True, 'changed': True}
            self.log('A7C USB 驱动已准备好；恢复记录已保存在此电脑')
            return {'driver_ready': True, 'changed': True, 'driver': 'libusb0'}

    def restore(self):
        with self.backend.lock():
            self.backend.check_admin()
            state = self.backend.load()
            rows = [r for r in state['devices'].values() if r['status'] != 'restored']
            if not rows:
                return {'drivers_restored': True, 'message': '没有本安装器修改的 Windows 驱动记录；已有手工驱动未改动。'}
            # Service package first; normal USB import last.
            rows.sort(key=lambda r: target(r) in NORMAL)
            for row in rows:
                self.backend.validate_original(row)
            for row in rows:
                target(row)
                package = row.get('published_inf') or self.backend.find_staged(row)
                current = {d['id'].upper(): d for d in self.backend.inventory(present=False)}
                device = current.get(row['id'].upper())
                if device and device['inf'].lower() not in ('', (package or '').lower(), row['before_inf'].lower()) and device['driver'].lower() != row['before_driver'].lower():
                    raise InstallerError('驱动已被其他工具更换，保留当前状态与恢复记录，未强行覆盖。')
                if package:
                    if not re.fullmatch(r'oem[0-9]+\.inf', package, re.I):
                        raise InstallerError('恢复记录的驱动包名异常，未删除。')
                    if self.backend.verify_owned(package, row):
                        self.backend.remove_package(package, row)
                if row['before_inf']:
                    self.backend.restore_original(row)
                row['status'] = 'restored'
                self.backend.save(state)
            self.backend.rescan()
            return {'drivers_restored': True, 'message': '本安装器的 USB 驱动已撤销，原驱动已恢复。请重新插拔相机，检查普通 USB 导入。相机内服务是否保留取决于是否执行过“卸载相机服务”。'}


def wait_service(log=lambda _: None, timeout=25):
    manager = DriverManager(log=log)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        devices = manager.backend.inventory(present=True)
        if any(re.match(r'USB\\VID_054C&PID_0336\\', d['id'], re.I) for d in devices):
            return manager.ensure(service=True)
        time.sleep(.5)
    raise InstallerError('等待 Sony 服务接口超时；恢复记录已保留，可重试或恢复 Windows 驱动。')
