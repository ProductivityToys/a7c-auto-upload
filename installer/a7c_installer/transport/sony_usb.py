"""Pinned PMCA service transport; no firmware updater or raw-storage writes."""
import os
from pathlib import Path, PurePosixPath
import plistlib
import hashlib
import re
import secrets
import shlex
import subprocess
import sys
import time
import traceback
from ..configuration import InstallerError

VENDOR = Path(__file__).resolve().parents[2] / "vendor"
if not VENDOR.exists():
    VENDOR = Path(getattr(sys, "_MEIPASS", ".")) / "vendor"
sys.path.insert(0, str(VENDOR))
NORMAL = (0x0d28, 0x0d29)
SERVICE = 0x0336


def usb_modules(legacy=False):
    try:
        import usb.core
        import usb.backend.libusb1
        import libusb_package
        if legacy:
            # The installed libusb-win32 package supplies this DLL. libusb-1.0
            # would additionally need libusbK.dll to use the same kernel driver.
            import usb.backend.libusb0
            library = Path(os.environ['SystemRoot']) / 'System32' / 'libusb0.dll'
            if not library.is_file():
                raise InstallerError('libusb-win32 访问库缺失，请恢复 Windows 驱动后重新准备。')
            backend = usb.backend.libusb0.get_backend(find_library=lambda _: str(library))
        else:
            backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        if backend is None:
            raise ImportError()
        return usb, backend
    except (ImportError, OSError):
        raise InstallerError("USB 运行库缺失；请使用完整安装包，或安装 requirements.txt。") from None


def enumerate_devices(legacy=False):
    usb, backend = usb_modules(legacy)
    try:
        devices = list(usb.core.find(find_all=True, idVendor=0x054c, backend=backend))
        return usb, backend, devices
    except usb.core.USBError:
        raise InstallerError("无法枚举 USB；请检查相机连接及 USB 访问权限。") from None


def detect():
    """Enumeration only: no service-mode transition, claim or disk unmount."""
    _, _, devices = enumerate_devices()
    return [{"vid": "054c", "pid": f"{d.idProduct:04x}",
             "mode": "normal" if d.idProduct in NORMAL else
                     "service" if d.idProduct == SERVICE else
                     "charger" if d.idProduct == 0x0994 else
                     "firmware-updater" if d.idProduct == 0x03e2 else "other"}
            for d in devices]


def nodes(value, predicate):
    if isinstance(value, dict):
        if predicate(value):
            yield value
            return
        for child in value.values():
            yield from nodes(child, predicate)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child, predicate)


def unmount_macos_disks(product):
    tree = plistlib.loads(subprocess.check_output(["ioreg", "-p", "IOService", "-a", "-l"]))
    camera = list(nodes(tree, lambda n: n.get("idVendor") == 0x054c and n.get("idProduct") == product))
    if len(camera) != 1:
        raise InstallerError("无法唯一对应相机的磁盘；未卸载任何磁盘。")
    for disk in nodes(camera[0], lambda n: n.get("Whole") and "BSD Name" in n):
        name = disk["BSD Name"]
        if not re.fullmatch(r"disk\d+", name):
            raise InstallerError("相机磁盘名称异常。")
        result = subprocess.run(["diskutil", "unmountDisk", "/dev/" + name], capture_output=True)
        if result.returncode:
            raise InstallerError("相机卷正被其他程序使用；请关闭照片导入、Finder 预览后重试。")


def claimed_macos_driver(device):
    """Claim before StartSenser; upstream device constructors also call reset()."""
    import usb.util
    from pmca.usb.driver.generic import GenericUsbDriver
    from pmca.usb.driver.generic.libusb import UsbBackend

    class ClaimedBackend(UsbBackend):
        ready = False

        def reset(self):
            if not self.ready:
                super().reset()
                usb.util.claim_interface(self.dev, 0)
                self.ready = True

    backend = ClaimedBackend(device)
    driver = GenericUsbDriver(backend)
    backend.reset()
    return driver


class SonyUsb:
    """Context manager owns one service session and always requests normal exit."""
    def __init__(self, log=lambda _: None):
        self.log = log
        self.auth = self.cam = self.dev = None
        self.terminal = False
        self.model = "ILCE-7C"
        self.stage = '初始化 USB'
        self._usb_devices = []
        self._native_log = None

    def __enter__(self):
        try:
            self.connect()
            return self
        except BaseException as ex:
            if self._native_log is not None:
                for note in self._native_log.messages:
                    self.log('macOS USB：' + note)
            if not isinstance(ex, (InstallerError, KeyboardInterrupt, SystemExit)):
                # Keep the failing phase and nested libusb error codes, without
                # logging packet data, authentication challenges or credentials.
                details = []
                cause = ex
                seen = set()
                while cause is not None and id(cause) not in seen:
                    seen.add(id(cause))
                    codes = [f'{name}={getattr(cause, name)}'
                             for name in ('errno', 'backend_error_code')
                             if isinstance(getattr(cause, name, None), int)]
                    detail = type(cause).__name__ + (': ' + ', '.join(codes) if codes else '')
                    if re.fullmatch(r'(?:Invalid response:|Senser error) \d+', str(cause)):
                        detail += ': ' + str(cause)
                    details.append(detail)
                    cause = cause.__cause__ or cause.__context__
                frames = traceback.extract_tb(ex.__traceback__)
                origin = ' → '.join(f'{Path(f.filename).name}:{f.name}:{f.lineno}' for f in frames[-4:])
                self.log(f'USB 失败阶段：{self.stage}；' + ' ← '.join(details))
                self.log('USB 调用位置：' + origin)
            self.close()
            if isinstance(ex, (InstallerError, KeyboardInterrupt, SystemExit)):
                raise
            hint = ('请检查相机普通/服务模式 USB 驱动。' if sys.platform == 'win32'
                    else '请保持接线、唤醒相机后重新连接。')
            raise InstallerError(f'相机 USB 通信失败（{self.stage}）。{hint}具体原因已记录在运行日志中。') from None

    def prepare_windows_drivers(self):
        if sys.platform == 'win32':
            from ..drivers.windows import DriverManager
            # Driverless devices are not reliably visible to libusb. Inspect
            # Windows PnP first; this also rejects updater and non-A7C devices.
            manager = DriverManager(log=self.log)
            current = manager.backend.inventory()
            service_only = any('VID_054C&PID_0336' in d['id'].upper() for d in current)
            if service_only:
                # An already-bound service device may be re-opened. Installing
                # a driver for the shared service PID requires the verified
                # normal -> service transition below.
                candidates = [d for d in current if 'VID_054C&PID_0336' in d['id'].upper()]
                if len(candidates) != 1 or candidates[0]['driver'].lower() not in ('libusb0', 'libusbk', 'winusb'):
                    raise InstallerError('服务接口缺驱动；请重新连接相机普通模式，再运行安装器以自动准备驱动。')
                return candidates[0]['driver'].lower()
            else:
                return manager.ensure()['driver']

    def connect(self):
        self.stage = '加载 USB 组件'
        from pmca.usb.driver.generic import GenericUsbDriver
        from pmca.usb.driver.generic.libusb import UsbBackend
        from pmca.usb.sony import SonySenserAuthDevice, SonySenserDevice, SonySenserCamera
        windows_driver = self.prepare_windows_drivers()
        self.stage = '查找相机'
        usb, backend, all_devices = enumerate_devices(legacy=windows_driver == 'libusb0')
        if sys.platform == 'darwin' and backend is not None:
            from .native_log import NativeUsbLog
            self._native_log = NativeUsbLog(backend)
        # A previous service session can still be re-enumerating when the next
        # button is clicked. Wait for that transition, not for a manual replug.
        deadline = time.monotonic() + 8
        while not all_devices and time.monotonic() < deadline:
            time.sleep(.25)
            usb, backend, all_devices = enumerate_devices(legacy=windows_driver == 'libusb0')
        candidates = [d for d in all_devices if d.idProduct in (*NORMAL, SERVICE)]
        if any(d.idProduct == 0x03e2 for d in all_devices):
            raise InstallerError("相机处于固件更新模式 054c:03e2；请先完成官方恢复，安装器不会向该模式发送命令。")
        if len(candidates) != 1:
            if any(d.idProduct == 0x0994 for d in all_devices):
                raise InstallerError("当前是 Sony USB Charger（054c:0994），尚无相机数据接口。请保持接线、拨到 ON 并轻半按快门，确认出现 USB 连接界面后重试。")
            raise InstallerError("请只连接一台 A7C，开机并将 USB 连接设为「海量存储器」。当前没有唯一的普通/服务模式设备。")
        d = candidates[0]
        self._usb_devices.append(d)
        if d.idProduct in NORMAL:
            self.stage = '释放普通 USB 接口'
            if sys.platform == "darwin":
                if os.geteuid() != 0:
                    raise InstallerError("macOS 需要管理员权限释放相机 USB 接口；请用 sudo 运行脚本，或以管理员方式启动 App。")
                unmount_macos_disks(d.idProduct)
            config = d.get_active_configuration()
            if config[(0, 0)].bInterfaceClass != 8:
                raise InstallerError("请在相机菜单将 USB 连接改为「海量存储器」，然后重新连接。")
            if sys.platform != 'darwin':
                try:
                    if d.is_kernel_driver_active(0):
                        d.detach_kernel_driver(0)
                except NotImplementedError:
                    pass
            import usb.util
            product = usb.util.get_string(d, d.iProduct) or ""
            if product != "ILCE-7C":
                raise InstallerError("USB 型号不是第一代 ILCE-7C；未进入服务模式。")
            self.stage = '申请普通 USB 接口'
            driver = claimed_macos_driver(d) if sys.platform == 'darwin' else GenericUsbDriver(UsbBackend(d))
            temporary_auth = SonySenserAuthDevice(driver)
            self.log("进入 USB 服务模式（临时模式切换）")
            temporary_auth.start()
            self.auth = temporary_auth
            self.stage = '普通模式认证'
            temporary_auth.authenticate()
            # The handle is invalid after re-enumeration. Keep a strong driver
            # reference until transition completes; do not dispose the new handle.
            usb.util.dispose_resources(d)
            self.auth = None
            del temporary_auth, driver
            self.stage = '等待服务接口'
            if sys.platform == 'win32':
                from ..drivers.windows import wait_service
                service_driver = wait_service(self.log)['driver']
                # A previously installed service interface can use another
                # compatible driver than the normal camera interface.
                if service_driver != windows_driver:
                    usb, backend, _ = enumerate_devices(legacy=service_driver == 'libusb0')
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                service = list(usb.core.find(find_all=True, idVendor=0x054c, idProduct=SERVICE, backend=backend))
                if len(service) == 1:
                    d = service[0]
                    self._usb_devices.append(d)
                    break
                time.sleep(.25)
            else:
                raise InstallerError("未打开服务设备 054c:0336。Windows 首次使用需为该设备安装 libusb-win32 驱动，再重试；无需升级固件。")
        self.stage = '打开服务接口'
        driver = claimed_macos_driver(d) if sys.platform == 'darwin' else GenericUsbDriver(UsbBackend(d))
        self.auth = SonySenserAuthDevice(driver)
        self.auth.start()
        self.stage = '服务模式认证'
        self.auth.authenticate()
        self.dev = SonySenserDevice(driver)
        self.cam = SonySenserCamera(self.dev)
        self.stage = '已连接'
        if self._native_log is not None:
            self._native_log.close()
            self._native_log = None

    def close(self):
        if self.terminal and self.cam:
            try:
                self.cam.setTerminalEnable(False)
            except Exception:
                self.log("USB 终端关闭未收到确认；请重新连接后检测状态。")
        if self.auth:
            try:
                self.auth.stop()
                self.log("已请求退出服务模式，恢复普通 USB")
            except Exception:
                self.log("退出服务模式未收到确认；请重新连接 USB 后检测。")
        self.auth = self.cam = self.dev = None
        self.terminal = False
        if self._native_log is not None:
            self._native_log.close()
            self._native_log = None
        if self._usb_devices:
            import usb.util
            devices, self._usb_devices = self._usb_devices, []
            for device in devices:
                try:
                    usb.util.dispose_resources(device)
                except Exception:
                    self.log('USB 句柄释放未完成；请保留连接后重试。')

    def __exit__(self, *args):
        self.close()

    def read(self, path):
        try:
            return self.cam.readFile(path)
        except Exception:
            raise InstallerError("USB 文件读取失败；停止操作并保留现场。") from None

    def write(self, path, value):
        try:
            self.cam.writeFile(path, value)
        except Exception:
            raise InstallerError("USB 文件写入未确认；请保留连接并执行恢复。") from None

    def remove(self, path):
        if self.exists(path):
            self.command("/bin/busybox rm -f -- " + shlex.quote(path))

    def command(self, command, timeout=15):
        if not self.terminal:
            self.cam.setTerminalEnable(False)
            self.cam.setTerminalEnable(True)
            self.terminal = True
            self.dev.writeTerminal(b"\n")
            deadline = time.monotonic() + 10
            buffer = b""
            while time.monotonic() < deadline:
                buffer += self.dev.readTerminal()
                if b"# " in buffer:
                    break
            else:
                raise InstallerError("USB 终端尚未就绪。")
        nonce = secrets.token_hex(10)
        # Split marker in the echoed command so an echo cannot signal completion.
        marker = "__A7C_END_" + nonce
        begin = "__A7C_BEGIN_" + nonce
        wire = (f"printf '\\n%s%s\\n' '__A7C_BEGIN_' '{nonce}'; ({command}); "
                f"r=$?; printf '\\n%s%s:%s\\n' '__A7C_END_' '{nonce}' \"$r\"\n")
        buffer = b""
        if len(wire.encode()) > 800:
            # Stay below BusyBox's interactive input-line limits. Assemble in
            # a private shell variable using bounded quoted lines,
            # then evaluate once in the same subshell as the short-command path.
            # This needs no temporary file and never retries a mutation.
            variable = '_a7c_cmd_' + nonce
            lines = [variable + "=''\n"]
            for offset in range(0, len(command), 128):
                chunk = shlex.quote(command[offset:offset + 128])
                lines.append(f'{variable}="${variable}"{chunk}\n')
            lines.append(f"printf '\\n%s%s\\n' '__A7C_BEGIN_' '{nonce}'; "
                         f'(eval "${variable}"); r=$?; unset {variable}; '
                         f"printf '\\n%s%s:%s\\n' '__A7C_END_' '{nonce}' \"$r\"\n")
            for line in lines:
                self.dev.writeTerminal(line.encode())
                # Drain the echoed input between lines. Sending a whole script
                # without reading can overflow the camera's terminal queues,
                # dropping bytes even when every individual line is short.
                drain_deadline = time.monotonic() + 2
                while time.monotonic() < drain_deadline:
                    data = self.dev.readTerminal()
                    if not data:
                        break
                    buffer += data
                    if len(buffer) > 256 * 1024:
                        raise InstallerError("USB 命令输出超过预期；已停止。")
        else:
            self.dev.writeTerminal(wire.encode())
        # printk may put a fragment immediately before a marker. The random
        # nonce still identifies it uniquely; the echoed command only contains
        # its two separate quoted halves, never the complete marker.
        pattern = re.compile(marker.encode() + rb":(\d+)\r?\n")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(buffer) > 256 * 1024:
                raise InstallerError("USB 命令输出超过预期；已停止。")
            match = pattern.search(buffer)
            if match:
                started = re.search(begin.encode() + rb"\r?\n", buffer[:match.start()])
                if not started:
                    raise InstallerError("USB 命令没有有效的开始标记。")
                output = buffer[started.end():match.start()].decode(errors="replace").replace("\r", "")
                # Linux console messages may arrive asynchronously on this
                # shell, including an unfinished timestamp just before our
                # completion marker. It is not part of the command's output.
                output = "\n".join(line for line in output.splitlines()
                                   if not re.match(r"^\[\s*\d+(?:\.\d*)?(?:\]|$)", line)).strip()
                if int(match[1]) != 0:
                    raise InstallerError("机内文件/运行状态操作未完成；未继续下一阶段。")
                return output
            buffer += self.dev.readTerminal()
        # Name the timed-out step for diagnosis: a short fixed-length digest of
        # the command (never its text, which may carry paths or arguments).
        self.log("USB 命令超时：步骤 " + hashlib.sha256(command.encode()).hexdigest()[:8] + " · " + str(timeout) + " 秒")
        raise InstallerError("USB 命令超时，完成状态未知；请重新检测，不要直接重装。")

    def exists(self, path):
        out = self.command(f"if [ -e {shlex.quote(path)} ] || [ -L {shlex.quote(path)} ]; then echo EXISTS; else echo ABSENT; fi")
        # Keep the explicit answer even when asynchronous console fragments
        # remain between the command's nonce-delimited markers.
        answers = [line for line in out.splitlines() if line in ("EXISTS", "ABSENT")]
        if answers == ["EXISTS"]:
            return True
        if answers == ["ABSENT"]:
            return False
        raise InstallerError("文件存在性查询未返回明确结果。")

    def hashes(self, paths):
        out = self.command("/bin/busybox sha256sum " + " ".join(shlex.quote(p) for p in paths), timeout=60)
        result = {}
        for line in out.splitlines():
            match = re.fullmatch(r"([a-f0-9]{64})\s+(/\S+)", line)
            if match:
                result[match[2]] = match[1]
        if set(result) != set(paths):
            raise InstallerError("固件文件校验结果不完整。")
        return result

    def monitor_fields(self):
        return tuple(int.from_bytes(self.cam.readBackup(i), "little") for i in (0xfa0028, 0xfa005d))

    def runtime_report(self):
        # Fixed allowlist, no config/password/token, media, raw storage or env.
        paths = ["/proc/uptime", "/proc/sys/kernel/random/boot_id", "/proc/mounts",
                 "/tmp_network/a7c-uploader.claim", "/setting/a7c-uploader/ram/worker.stdout",
                 "/setting/a7c-uploader/ram/worker.exit", "/setting/a7c-uploader/ram/supervisor.pid",
                 "/setting/a7c-uploader/ram/display-bootstrap.log",
                 "/setting/a7c-uploader/ram/plain-boot-timings.log",
                 "/setting/a7c-uploader/ram/ftp-health",
                 "/setting/a7c-uploader/ram/ftp-health-check.log",
                 "/setting/a7c-uploader/ram/ftp-health-display.log",
                 "/setting/a7c-debug/ram/dds-once/native-start.log",
                 "/setting/a7c-debug/ram/dds-once/native-service/ready.log",
                 "/setting/a7c-debug/ram/dds-once/native-service/start.log"]
        report = {}
        for path in paths:
            if self.exists(path):
                report[path] = self.command("/bin/busybox tail -c 8192 " + shlex.quote(path))
        return report

    def directories(self, paths):
        # Reject symlinks in all existing ancestors before mkdir/chmod/write.
        ancestors = set()
        for path in paths:
            current = PurePosixPath(path)
            while str(current) not in ("/setting", "/", "."):
                ancestors.add(str(current))
                current = current.parent
        checks = " && ".join("[ ! -L " + shlex.quote(p) + " ]" for p in sorted(ancestors))
        args = " ".join(shlex.quote(p) for p in paths)
        self.command(checks + " && /bin/busybox mkdir -p " + args + " && /bin/busybox chmod 700 " + args)

    def resident_status(self):
        # Read only our tmpfs and exact supervisor/worker command paths. PID
        # files alone are not proof that a process still belongs to us.
        return self.command(
            'D=/setting/a7c-uploader/ram; B=/bin/busybox; '
            'if ! $B grep -q "^a7c-upload-ram $D tmpfs " /proc/mounts; then '
            'if $B grep -q " $D " /proc/mounts; then echo FOREIGN; else echo IDLE; fi; '
            'elif [ -d "$D/supervisor.lock" ]; then '
            's=$($B cat "$D/supervisor.pid" 2>/dev/null); w=$($B cat "$D/worker.pid" 2>/dev/null); '
            'case "$s:$w" in *[!0-9:]*|:*|*:) echo BUSY;; *) '
            'if kill -0 "$s" 2>/dev/null && kill -0 "$w" 2>/dev/null && '
            '$B grep -q /setting/a7c-uploader/supervisor.sh /proc/$s/cmdline && '
            '$B grep -q -E "/setting/a7c-uploader/(worker.sh|ram/plain-worker.sh)" /proc/$w/cmdline; '
            'then echo RUNNING:$s:$w; else echo BUSY; fi;; esac; '
            'elif [ -d "$D/lock" ] || [ -e "$D/source.fifo" ] || [ -e "$D/network.fifo" ]; '
            'then echo BUSY; else echo IDLE; fi')

    def start_service(self):
        state = self.resident_status()
        requested = False
        deadline = time.monotonic() + 60
        detail = '上传进程尚未就绪'
        while True:
            match = re.fullmatch(r'RUNNING:(\d+):(\d+)', state)
            if match:
                health = self.service_health(state)
                detail = health['detail']
                if health['state'] == 'ready':
                    self.log('服务健康检查通过：' + detail)
                    return {'supervisor_pid': int(match[1]), 'worker_pid': int(match[2]), 'health': health}
                if health['state'] in ('error', 'restart_required'):
                    raise InstallerError('服务健康检查未通过：' + detail)
            if state == 'FOREIGN':
                raise InstallerError('上传运行目录被其他挂载占用，未启动服务。')
            if state == 'IDLE' and not requested:
                # HUP is ignored before exec; no terminal descriptors or secret
                # arguments are retained. The installed supervisor owns mounting,
                # its exclusive lock and all worker startup/verification.
                self.command("trap '' HUP; /bin/ash /setting/a7c-uploader/supervisor.sh --start </dev/null >/dev/null 2>&1 &")
                requested = True
            elif state not in ('IDLE', 'BUSY') and not match:
                raise InstallerError('服务运行状态查询未返回明确结果，未重复启动。')
            if time.monotonic() >= deadline:
                raise InstallerError('服务启动未确认：' + detail + '。请查看运行日志，无需重新安装。')
            time.sleep(.5)
            state = self.resident_status()

    def service_health(self, process_state=None):
        state = process_state or self.resident_status()
        match = re.fullmatch(r'RUNNING:(\d+):(\d+)', state)
        if not match:
            return {'state':'stopped', 'detail':'上传服务未运行', 'process_state':state}
        worker = match[2]
        # Existing startup records plus a read-only check of the actual native
        # module; no media scan, credentials, network traffic or idle polling.
        out = self.command(
            'B=/bin/busybox; D=/setting/a7c-uploader/ram; '
            'N=/setting/a7c-debug/ram/dds-once/native-service; '
            f'if [ "$($B cat "$D/plain.worker.pid" 2>/dev/null)" = {worker} ] && '
            '$B grep -q "op=worker_exec " "$D/plain-boot-timings.log"; then echo UPLOAD=ready; else echo UPLOAD=starting; fi; '
            'if [ ! -f /setting/a7c-display/enabled ]; then echo DISPLAY=disabled; '
            'elif [ -d "$D/display-bootstrap.lock" ]; then echo DISPLAY=starting; '
            'elif $B grep -qx NATIVE_SERVICE_RETIRED "$N/../native-start.log"; then echo DISPLAY=restart; '
            # A display consumer that could not restore the indicator keeps the
            # maintenance lock; outside an active upload that is a display fault.
            'elif [ -d "$N/../maintenance" ] && [ ! -e "$D/display.active" ]; then echo DISPLAY=restart; '
            'else p=$($B cat "$N/im.pid" 2>/dev/null); '
            f'if [ "$($B cat "$N/owner" 2>/dev/null)" = {worker} ] && '
            '[ "$p" = "$($B pidof im.elf)" ] && [ -x "$N/probe" ] && '
            '$B grep -qx NATIVE_SERVICE_READY "$N/../native-start.log"; then '
            # Keep a slow, read-only probe from blocking the USB response. A
            # killed probe may still be pending in the kernel: retain its PID
            # and do not launch another one until that exact probe has exited.
            'f="$D/display-health.pid"; c=$($B cat "$f" 2>/dev/null); pending=0; '
            'case "$c" in ""|*[!0-9]*) ;; *) '
            'if kill -0 "$c" 2>/dev/null && $B grep -qF "$N/probe" "/proc/$c/cmdline" 2>/dev/null; then pending=1; fi;; esac; '
            'if [ "$pending" = 1 ]; then echo DISPLAY=starting; else '
            '"$N/probe" --inspect-service "$p" >/dev/null 2>&1 & c=$!; echo "$c" > "$f"; n=0; '
            'while kill -0 "$c" 2>/dev/null && [ "$n" -lt 8 ]; do $B sleep 1; n=$((n+1)); done; '
            'if kill -0 "$c" 2>/dev/null; then kill -KILL "$c" 2>/dev/null; echo DISPLAY=starting; '
            'else if wait "$c"; then echo DISPLAY=ready; else echo DISPLAY=error; fi; $B rm -f "$f"; fi; fi; '
            'else echo DISPLAY=error; fi; fi')
        fields = dict(line.split('=',1) for line in out.splitlines() if re.fullmatch(r'(UPLOAD|DISPLAY)=(ready|starting|disabled|error|restart)',line))
        if set(fields) != {'UPLOAD','DISPLAY'}:
            raise InstallerError('健康检查响应不完整，未标为服务正常。')
        if fields['UPLOAD'] != 'ready':
            status, detail = 'starting', '上传器初始化中'
        elif fields['DISPLAY'] == 'starting':
            status, detail = 'starting', '显示模块初始化中'
        elif fields['DISPLAY'] == 'error':
            status, detail = 'error', '上传器已就绪，显示模块初始化未通过'
        elif fields['DISPLAY'] == 'restart':
            status, detail = 'restart_required', '显示模块已在本次开机中退出，需完整重启相机后再启动服务'
        else:
            status = 'ready'
            detail = '上传器和显示模块已就绪' if fields['DISPLAY']=='ready' else '上传器已就绪，显示已关闭'
        return {'state':status, 'detail':detail, 'upload':fields['UPLOAD'], 'display':fields['DISPLAY']}

    def atomic(self, path, data, mode=0o600):
        temporary = path + ".installer-next"
        self.command("[ ! -L " + shlex.quote(path) + " ] && [ ! -L " + shlex.quote(temporary) + " ]")
        self.write(temporary, data)
        if self.read(temporary) != data:
            raise InstallerError("机内暂存文件读回不符，尚未发布。")
        self.command(f"/bin/busybox chmod {mode:o} {shlex.quote(temporary)} && /bin/busybox mv {shlex.quote(temporary)} {shlex.quote(path)}")

    def cleanup_staging(self, paths):
        # One bounded USB command; no globs or recursive deletion. Called only
        # after the worker/display have quiesced in an installer transaction.
        if paths:
            self.command("/bin/busybox rm -f -- " +
                         " ".join(shlex.quote(path + ".installer-next") for path in paths))

    def sync(self):
        self.command("/bin/busybox sync", timeout=30)

    DIAG_RAM = "/setting/a7c-uploader/ram/diag"

    def diag_stop(self, wait=30):
        """Cooperatively stop only our exact diagnostics listener."""
        d = self.DIAG_RAM
        self.command(
            f'D={d}; B=/bin/busybox; if [ -d "$D/lock" ]; then : > "$D/stop"; p=$($B cat "$D/listener.pid" 2>/dev/null); '
            'case "$p" in ""|*[!0-9]*) ;; *) if $B grep -q "$D/listener" "/proc/$p/cmdline" 2>/dev/null; then kill -TERM "$p"; fi;; esac; fi; true')
        deadline = time.monotonic() + wait
        while self.command(f'if [ -d {d}/lock ]; then echo RUNNING; else echo STOPPED; fi') != 'STOPPED':
            if time.monotonic() >= deadline:
                raise InstallerError("无线诊断入口尚未退出，未继续操作。")
            time.sleep(.5)

    def diag_start(self):
        """Start the paired listener now; returns its pid or None."""
        self.command("trap '' HUP; /bin/ash /setting/a7c-diag/start.sh </dev/null >/dev/null 2>&1 &")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            out = self.command(
                f'D={self.DIAG_RAM}; p=$(/bin/busybox cat "$D/listener.pid" 2>/dev/null); '
                'case "$p" in ""|*[!0-9]*) echo NONE;; *) if /bin/busybox grep -q "$D/listener" "/proc/$p/cmdline" 2>/dev/null; then echo PID:$p; else echo NONE; fi;; esac')
            if out.startswith('PID:'):
                return int(out[4:])
            time.sleep(.5)
        return None

    def quiesce(self, retire_display=True):
        ram = "/setting/a7c-uploader/ram"
        self.command(f"if /bin/busybox grep -q '^a7c-upload-ram {ram} tmpfs ' /proc/mounts; then : > {ram}/stop; fi")
        self.diag_stop()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            out = self.command(f"if [ ! -d {ram}/lock ] && [ ! -d {ram}/supervisor.lock ] && [ ! -e {ram}/source.fifo ] && [ ! -e {ram}/network.fifo ] && [ ! -d {ram}/display-bootstrap.lock ] && [ ! -d {ram}/plain.bootstrap.lock ]; then echo IDLE; else echo BUSY; fi")
            if out == "IDLE":
                break
            time.sleep(1)
        else:
            raise InstallerError("上传任务尚未安全退出；自启已暂停，未覆盖活动程序。请稍后重试或恢复备份。")
        native = "/setting/a7c-debug/ram/dds-once/native-service"
        out = self.command(f"if [ -f {native}/probe ] && [ -f {native}/im.pid ]; then echo NATIVE; else echo NONE; fi")
        if out == "NATIVE":
            # The controller's zero exit code includes marker/callback checks;
            # already-unloaded is also success and does not print EVENT_FINISH.
            finish = f' && {native}/probe --finish-event "$p"' if retire_display else ""
            self.command(f"p=$(/bin/busybox pidof im.elf); case \"$p\" in ''|*[!0-9]*) exit 1;; esac; {native}/probe --service-off \"$p\"" + finish, timeout=30)
