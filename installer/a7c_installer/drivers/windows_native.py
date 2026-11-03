"""Windows-only libwdi / SetupAPI adapter. Loading it does not alter drivers."""
import base64
from contextlib import contextmanager
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from ..configuration import InstallerError


class Device(C.Structure):
    pass


Device._fields_ = [('next', C.POINTER(Device)), ('vid', C.c_uint16), ('pid', C.c_uint16),
    ('is_composite', C.c_int32), ('mi', C.c_ubyte), ('desc', C.c_char_p),
    ('driver', C.c_char_p), ('device_id', C.c_char_p), ('hardware_id', C.c_char_p),
    ('compatible_id', C.c_char_p), ('upper_filter', C.c_char_p), ('driver_version', C.c_uint64)]


class ListOptions(C.Structure):
    _fields_ = [('all', C.c_int32), ('hubs', C.c_int32), ('trim', C.c_int32)]


class PrepareOptions(C.Structure):
    _fields_ = [('type', C.c_int), ('vendor', C.c_char_p), ('guid', C.c_char_p),
        ('disable_cat', C.c_int32), ('disable_signing', C.c_int32), ('subject', C.c_char_p),
        ('wcid', C.c_int32), ('external', C.c_int32)]


class InstallOptions(C.Structure):
    _fields_ = [('window', C.c_void_p), ('filter', C.c_int32), ('timeout', C.c_uint32)]


class WindowsBackend:
    def __init__(self):
        if sys.platform != 'win32':
            raise InstallerError('Windows USB 驱动操作仅适用于 Windows。')
        self.root = Path(os.environ['ProgramData']) / 'A7CInstaller' / 'drivers'
        self.resources = Path(__file__).resolve().parents[1] / 'resources/windows-drivers'
        self._dll = None

    def check_admin(self):
        if not C.windll.shell32.IsUserAnAdmin():
            raise InstallerError('请以管理员权限打开安装器，再准备或恢复 Windows 驱动。')

    def run(self, args, **kwargs):
        p = subprocess.run(args, capture_output=True, creationflags=0x08000000, timeout=180, **kwargs)
        if p.returncode == 3010:
            raise InstallerError('Windows 要求重启电脑才能完成驱动变更；请重启后使用恢复入口重试，恢复记录已保留。')
        if p.returncode != 0:
            # Raw setup logs can be localized. Keep them locally, show an actionable
            # error without swallowing the original return code.
            if self.root.is_dir():
                (self.root / 'last-command.log').write_bytes(p.stdout + p.stderr)
            raise InstallerError(f'Windows 驱动命令未完成（{p.returncode}），请查看 {self.root / "last-command.log"}；恢复记录已保留。')
        return p.stdout

    def ps(self, script):
        prefix = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
        encoded = base64.b64encode((prefix + script).encode('utf-16le')).decode()
        return self.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded]).decode('utf-8-sig').strip()

    @contextmanager
    def lock(self):
        self.check_admin()
        # A machine-wide kernel mutex works across GUI/CLI and does not trust a
        # user-writable lock file in an elevated process.
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [C.c_void_p, C.c_int32, C.c_wchar_p]
        kernel.CreateMutexW.restype = C.c_void_p
        kernel.WaitForSingleObject.argtypes = [C.c_void_p, C.c_uint32]
        kernel.ReleaseMutex.argtypes = [C.c_void_p]
        kernel.CloseHandle.argtypes = [C.c_void_p]
        mutex = kernel.CreateMutexW(None, False, 'Global\\A7CInstallerDrivers')
        if not mutex:
            raise InstallerError('无法锁定 Windows 驱动操作。')
        try:
            if kernel.WaitForSingleObject(mutex, 0) not in (0, 0x80):
                raise InstallerError('另一个安装器正在处理驱动，请等待完成。')
            # Reject links before writing elevated state. Protect the entire tree,
            # including pre-existing children, from non-admin changes.
            for p in (self.root.parent, self.root):
                if p.exists() and p.lstat().st_file_attributes & 0x400:
                    raise InstallerError('驱动备份路径是重解析点，未写入。')
                p.mkdir(exist_ok=True)
                self.run(['icacls.exe', str(p), '/inheritance:r', '/grant:r',
                          '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'])
            yield
        finally:
            kernel.ReleaseMutex(mutex)
            kernel.CloseHandle(mutex)

    def load(self):
        p = self.root / 'state.json'
        if not p.exists():
            return {'format': 1, 'devices': {}}
        try:
            data = json.loads(p.read_text())
            assert data['format'] == 1 and isinstance(data['devices'], dict)
            for key, row in data['devices'].items():
                assert key == row['id']
                assert re.fullmatch('[a-f0-9]{32}', row['token'])
                assert row['inf_name'] == 'a7c_' + row['token'] + '.inf'
                assert not row['before_inf'] or re.fullmatch(r'[a-z0-9_.-]+\.inf', row['before_inf'], re.I)
            return data
        except (ValueError, KeyError, TypeError, AssertionError):
            raise InstallerError('Windows 驱动恢复记录损坏，未修改驱动。') from None

    def save(self, state):
        p = self.root / 'state.next'
        with p.open('w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        p.replace(self.root / 'state.json')

    def inventory(self, present=True):
        present_arg = '-PresentOnly' if present else ''
        script = r'''
function Prop($id,$key) {
 $v=Get-PnpDeviceProperty -InstanceId $id -KeyName $key -ErrorAction SilentlyContinue
 if($null -ne $v) { return $v.Data }; return ''
}
$rows=@(Get-PnpDevice PRESENT | Where-Object { $_.InstanceId -match '^USB\\VID_054C&PID_' } | ForEach-Object {
 $id=$_.InstanceId
 [PSCustomObject]@{id=$id;bus_name=(Prop $id 'DEVPKEY_Device_BusReportedDeviceDesc');
 driver=(Prop $id 'DEVPKEY_Device_Service');inf=(Prop $id 'DEVPKEY_Device_DriverInfPath');
 hardware_id=@(Prop $id 'DEVPKEY_Device_HardwareIds')[0]}
}); ConvertTo-Json -InputObject $rows -Compress
'''.replace('PRESENT', present_arg)
        rows = json.loads(self.ps(script) or '[]')
        for row in rows:
            for key in ('id', 'bus_name', 'driver', 'inf', 'hardware_id'):
                row[key] = row[key] or ''
        return rows

    def directory(self, row):
        return self.root / row['token']

    def backup_original(self, device, token):
        directory = self.root / token / 'original'
        directory.mkdir(parents=True)
        if re.fullmatch(r'oem\d+\.inf', device['inf'], re.I):
            self.run(['pnputil.exe', '/export-driver', device['inf'], str(directory)])
            found = list(directory.rglob('*.inf'))
            if len(found) != 1:
                raise InstallerError('原驱动备份不唯一，未更换驱动。')
            return {'path': str(found[0].relative_to(self.root)),
                    'sha256': hashlib.sha256(found[0].read_bytes()).hexdigest()}
        if device['inf']:
            original = Path(os.environ['SystemRoot']) / 'INF' / device['inf']
            if not original.is_file():
                raise InstallerError('没有找到原系统驱动，未更换驱动。')
        return None

    def dll(self):
        if self._dll is None:
            manifest = json.loads((self.resources / 'manifest.json').read_text())
            for name, digest in manifest['binaries'].items():
                if hashlib.sha256((self.resources / name).read_bytes()).hexdigest() != digest:
                    raise InstallerError('内置驱动组件校验失败，请重新下载完整包。')
            dll = C.CDLL(str(self.resources / 'libwdi.dll'))
            dll.wdi_create_list.argtypes = [C.POINTER(C.POINTER(Device)), C.POINTER(ListOptions)]
            dll.wdi_destroy_list.argtypes = [C.POINTER(Device)]
            dll.wdi_prepare_driver.argtypes = [C.POINTER(Device), C.c_char_p, C.c_char_p, C.POINTER(PrepareOptions)]
            dll.wdi_install_driver.argtypes = [C.POINTER(Device), C.c_char_p, C.c_char_p, C.POINTER(InstallOptions)]
            dll.wdi_strerror.argtypes = [C.c_int]
            dll.wdi_strerror.restype = C.c_char_p
            self._dll = dll
        return self._dll

    def wdi_check(self, result):
        if result:
            text = self.dll().wdi_strerror(result).decode('utf-8', errors='replace')
            raise InstallerError(f'USB 驱动操作失败：{text}（{result}）。系统签名或组织策略阻止时请保留日志，勿关闭系统保护。')

    @contextmanager
    def device(self, instance):
        head = C.POINTER(Device)()
        dll = self.dll()
        self.wdi_check(dll.wdi_create_list(C.byref(head), C.byref(ListOptions(1, 0, 1))))
        try:
            ptr = head
            while ptr:
                if ptr.contents.device_id and ptr.contents.device_id.decode().upper() == instance.upper():
                    yield ptr
                    return
                ptr = ptr.contents.next
            raise InstallerError('设备在驱动准备期间断开，恢复记录已保留。')
        finally:
            dll.wdi_destroy_list(head)

    def prepare(self, device, row):
        path = self.directory(row) / 'driver'
        with self.device(device['id']) as ptr:
            options = PrepareOptions(1, b'A7C Installer', None, 0, 0, None, 0, 0)
            self.wdi_check(self.dll().wdi_prepare_driver(ptr, str(path).encode(), row['inf_name'].encode(), C.byref(options)))

    def stage(self, row):
        api = C.WinDLL('setupapi', use_last_error=True)
        api.SetupCopyOEMInfW.argtypes = [C.c_wchar_p, C.c_wchar_p, C.c_uint32, C.c_uint32,
                                        C.c_wchar_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_void_p]
        dest = C.create_unicode_buffer(4096)
        src = self.directory(row) / 'driver' / row['inf_name']
        if not api.SetupCopyOEMInfW(str(src), None, 1, 0, dest, len(dest), None, None):
            raise InstallerError(f'驱动包暂存失败（{C.get_last_error()}），恢复记录已保留。')
        return Path(dest.value).name

    def install(self, device, row):
        with self.device(device['id']) as ptr:
            options = InstallOptions(None, 0, 120000)
            self.wdi_check(self.dll().wdi_install_driver(ptr, str(self.directory(row) / 'driver').encode(), row['inf_name'].encode(), C.byref(options)))

    def wait_bound(self, instance, driver):
        normal = re.fullmatch(r'USB\\VID_054C&PID_(0D28|0D29)\\([^\\]+)', instance, re.I)
        for _ in range(12):
            devices = self.inventory()
            if any(d['id'].upper() == instance.upper() and d['driver'].lower() == driver for d in devices):
                return True
            candidates = [d for d in devices if re.match(r'USB\\VID_054C&PID_(0D28|0D29|0336)\\', d['id'], re.I)]
            if normal and len(candidates) == 1:
                device = candidates[0]
                current = re.fullmatch(r'USB\\VID_054C&PID_(0D28|0D29)\\([^\\]+)', device['id'], re.I)
                if (current and current[1].upper() != normal[1].upper()
                        and current[2].upper() == normal[2].upper()
                        and device['bus_name'].strip() == 'ILCE-7C'):
                    return 'normal_mode_changed'
            time.sleep(.5)
        raise InstallerError('驱动已安装，但设备尚未就绪。请重新连接，或选择恢复 Windows 驱动。')

    def find_staged(self, row):
        name = row['inf_name']
        values = json.loads(self.ps("$r=@(Get-WindowsDriver -Online -All | Where-Object { [IO.Path]::GetFileName($_.OriginalFileName) -eq '" + name + "' } | Select-Object -ExpandProperty Driver); ConvertTo-Json -InputObject $r -Compress") or '[]')
        if len(values) > 1:
            raise InstallerError('驱动包记录不唯一，未删除。')
        return values[0] if values else None

    def verify_owned(self, package, row):
        inf = Path(os.environ['SystemRoot']) / 'INF' / package
        source = self.directory(row) / 'driver' / row['inf_name']
        if not inf.exists():
            return False  # Recovery can resume after package removal interrupted it.
        if not source.exists() or inf.read_bytes() != source.read_bytes():
            raise InstallerError('驱动包与本次生成的专用 INF 不一致，未删除。')
        others = [d for d in self.inventory(present=False)
                  if d['inf'].lower() == package.lower() and d['id'].upper() != row['id'].upper()]
        if others:
            present = {d['id'].upper() for d in self.inventory(present=True)}
            # Windows retains absent service-interface instances after changing
            # USB ports. Removing our verified package can retire those too;
            # an additional live device or different hardware must still block.
            if any(d['id'].upper() in present or
                   d['hardware_id'].upper() != row['hardware_id'].upper() for d in others):
                raise InstallerError('此驱动包还绑定了另一个在线设备或不同硬件，保留驱动；请先断开其他设备。')
        return True

    def remove_package(self, package, row):
        self.run(['pnputil.exe', '/delete-driver', package, '/uninstall'])

    def validate_original(self, row):
        if not row['before_inf']:
            return None
        backup = row['backup']
        if backup:
            src = (self.root / backup['path']).resolve()
            if not src.is_relative_to(self.directory(row).resolve()) or hashlib.sha256(src.read_bytes()).hexdigest() != backup['sha256']:
                raise InstallerError('原驱动备份校验失败，恢复记录保留。')
        else:
            src = Path(os.environ['SystemRoot']) / 'INF' / row['before_inf']
        if not src.is_file():
            raise InstallerError('没有找到原驱动备份，保留当前驱动。')
        return src

    def restore_original(self, row):
        src = self.validate_original(row)
        if row['backup']:
            # Inbox packages already live in the Windows driver store.
            self.run(['pnputil.exe', '/add-driver', str(src), '/install'])
        devices = self.inventory(present=True)
        if any(d['id'].upper() == row['id'].upper() for d in devices):
            if any(d['hardware_id'].upper() == row['hardware_id'].upper() and d['id'].upper() != row['id'].upper() for d in devices):
                raise InstallerError('还有另一台设备使用相同硬件ID，请只连接待恢复的相机。')
            api = C.WinDLL('newdev', use_last_error=True)
            api.UpdateDriverForPlugAndPlayDevicesW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_wchar_p, C.c_uint32, C.POINTER(C.c_int32)]
            reboot = C.c_int32()
            if not api.UpdateDriverForPlugAndPlayDevicesW(None, row['hardware_id'], str(src), 1, C.byref(reboot)):
                raise InstallerError(f'原驱动重新绑定失败（{C.get_last_error()}），恢复记录保留。')

    def rescan(self):
        self.run(['pnputil.exe', '/scan-devices'])
