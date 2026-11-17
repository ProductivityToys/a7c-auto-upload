"""One shared install engine for CLI and Qt; explicit files, one rollback slot."""
import json
from dataclasses import replace
from .bundle import Bundle, sha256
from .configuration import FtpSettings, InstallerError
from .ftp_check import test_ftp

P = "/setting/a7c-uploader"
S = "/setting/a7c-display"
STATE = "/setting/a7c-installer"
META = P + "/installed.json"
CONFIG = P + "/plainftp/config"
PASSWORD = P + "/plainftp/password"
PRELOAD = "/etc/ld.so.preload"
LOADER = P + "/launcher.so"
ENABLE = P + "/enabled"
DISPLAY_ENABLE = S + "/enabled"
DIAG = "/setting/a7c-diag"
DIAG_ENABLE = DIAG + "/enabled"
DIAG_TOKEN = DIAG + "/token"
# Maintainer debug add-on (not in release payloads). Tolerated in an installed
# manifest so a debug-equipped camera is not rejected as unknown; uninstall
# removes it together with the pairing.
DIAG_FILES = {DIAG + "/listener", DIAG + "/listener.sha256", DIAG + "/diag.sh", DIAG + "/start.sh"}
PENDING = STATE + "/pending.json"
BACKUP = STATE + "/backup"
STARTED_MESSAGE = "上传服务已启动。请拔掉 USB 并回到拍摄画面，连接 Wi-Fi 后自动上传，无需关机或取电池。"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def optional(camera, path):
    return camera.read(path) if camera.exists(path) else None


def parse_settings(camera):
    data = optional(camera, CONFIG)
    secret = optional(camera, PASSWORD)
    if data is None or secret is None:
        raise InstallerError("未发现本上传器的现有 FTP 配置，请填写新配置。")
    try:
        lines = data.decode("ascii").splitlines()
        v1 = len(lines) == 5 and lines[0] == "a7c-plainftp-v1"
        v2 = len(lines) == 6 and lines[0] == "a7c-plainftp-v2" and lines[5] in ("0", "1")
        v3 = (len(lines) == 7 and lines[0] == "a7c-plainftp-v3"
              and all(line in ("0", "1") for line in lines[5:]))
        if not (v1 or v2 or v3) or not secret.endswith(b"\n"):
            raise ValueError()
        return FtpSettings(lines[1], int(lines[2]), lines[3], lines[4], secret[:-1].decode("utf-8"),
                           photos=(v2 or v3) and lines[5] == "1",
                           pause_photos_for_native_ftp=(lines[6] == "1") if v3 else None).validate()
    except (ValueError, UnicodeError):
        raise InstallerError("现有 FTP 配置格式异常；请填写新配置。") from None


def without_loader(data):
    """Preserve every foreign token/comment; only remove this uploader's token."""
    if data is None:
        return b""
    if len(data) > 8192 or b"\x00" in data:
        raise InstallerError("ld.so.preload 格式异常，未修改。")
    text = data.decode("ascii")
    result = []
    for line in text.splitlines(keepends=True):
        code, separator, comment = line.partition("#")
        # Standard ld.so.preload separators include ':' as well as whitespace.
        import re
        tokens = re.split(r"([\s:]+)", code)
        if LOADER not in tokens:
            result.append(line)
            continue
        remaining = [t for t in tokens if t != LOADER]
        remaining_code = "".join(remaining).strip(" \t\r\n:")
        if remaining_code or separator:
            result.append(remaining_code + ((" #" + comment.rstrip("\r\n")) if separator else "") + "\n")
    return "".join(result).encode("ascii")


class Installer:
    def __init__(self, camera, bundle=None, log=lambda _: None, ftp_test=test_ftp):
        self.camera = camera
        self.bundle = bundle or Bundle()
        self.log = log
        self.ftp_test = ftp_test

    def inspect(self, full=False):
        version = self.camera.read("/version.txt").decode("ascii", errors="replace").strip()
        installed = optional(self.camera, META)
        metadata = self.metadata(installed) if installed is not None else None
        public = None
        if self.camera.exists(CONFIG) and self.camera.exists(PASSWORD):
            public = parse_settings(self.camera).public()
        report = {"model": self.camera.model, "firmware_build": version,
                  "supported": version == self.bundle.firmware["version_txt"],
                  "installed_version": metadata.get("version") if metadata else None,
                  "enabled": self.camera.exists(ENABLE),
                  "pending_recovery": self.camera.exists(PENDING), "ftp": public,
                  "wifi_diag": self.camera.exists(DIAG_ENABLE) and self.camera.exists(DIAG_TOKEN)}
        report['health'] = (self.camera.service_health() if metadata and report['enabled'] and not report['pending_recovery']
                            else {'state':'stopped','detail':'上传服务未运行'})
        if full:
            self.verify_firmware()
            report["verified_dependencies"] = len(self.bundle.firmware["dependencies"])
        return report

    def resolve_settings(self, settings, preserve_password=False, expected_config=None):
        """Read a saved secret only inside the camera operation, never into Qt."""
        if preserve_password:
            if settings is None or settings.password:
                raise InstallerError('保留密码请求与输入不一致，请重新读取配置。')
            previous = parse_settings(self.camera)
            if expected_config is None or previous.public() != expected_config:
                raise InstallerError('相机里的 FTP 配置已变化，请重新连接并读取配置后重试。')
            settings = replace(settings, password=previous.password)
        if settings is None:
            raise InstallerError('请填写 FTP 配置。')
        return settings.validate()

    def metadata(self, data):
        try:
            value = json.loads(data)
            if value["owner"] != "a7c-usb-installer" or value["format"] != 1:
                raise ValueError()
            managed = value["files"]
            required = {LOADER, P + "/worker.sh", P + "/supervisor.sh"}
            if not isinstance(managed, dict) or not required <= set(managed) <= set(self.bundle.files) | DIAG_FILES:
                raise ValueError()
            if any(not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in managed.values()):
                raise ValueError()
            return value
        except (ValueError, KeyError, TypeError):
            raise InstallerError("已安装清单无法识别，请保留现场，不覆盖未知版本。") from None

    def verify_firmware(self):
        if self.camera.model != self.bundle.firmware["model"]:
            raise InstallerError("仅支持第一代 ILCE-7C。")
        if self.camera.read("/version.txt").decode("ascii", errors="replace").strip() != self.bundle.firmware["version_txt"]:
            raise InstallerError("仅支持已验证的 2.00；本安装器不升级或降级相机固件。")
        if self.camera.monitor_fields() != (0x20098000, 0x7c000):
            raise InstallerError("机身内部接口布局不同，未写入安装文件。")
        dependencies = self.bundle.firmware["dependencies"]
        if self.camera.hashes(list(dependencies)) != dependencies:
            raise InstallerError("固件程序与 2.00 适配清单不符，未写入安装文件。")
        self.log("ILCE-7C 2.00 与 9 项原厂接口依赖核对通过")

    def ownership(self):
        meta = optional(self.camera, META)
        if meta is not None:
            self.metadata(meta)
        else:
            # Known inactive home baseline can be adopted, never an unknown loader.
            loader = optional(self.camera, LOADER)
            if loader is not None and loader != self.bundle.files[LOADER]:
                raise InstallerError("已有未知启动模块，请先用原安装工具卸载。")
            worker = optional(self.camera, P + "/worker.sh")
            if worker is not None and worker != self.bundle.files[P + "/worker.sh"]:
                raise InstallerError("已有未知上传器，请先导出其配置并用原工具卸载。")
        preload = optional(self.camera, PRELOAD)
        if preload and b"/setting/a7c-debug/launcher.so" in preload:
            raise InstallerError("研究版无线调试自启仍开启；请先通过原维护工具停用，再安装发布版。")

    def paths(self):
        return sorted(set(self.bundle.files) | {CONFIG, PASSWORD, META, ENABLE, DISPLAY_ENABLE, PRELOAD, DIAG_ENABLE, DIAG_TOKEN} | DIAG_FILES)

    def prepare_directories(self):
        self.camera.directories([STATE, BACKUP, P, P + "/plainftp", P + "/ram", S,
                                 "/setting/a7c-debug", "/setting/a7c-debug/ram", DIAG])

    def snapshot(self, operation="install"):
        rows = []
        for number, path in enumerate(self.paths()):
            value = optional(self.camera, path)
            row = {"path": path, "saved": str(number) if value is not None else None}
            if value is not None:
                row["sha256"] = sha256(value)
                self.camera.atomic(BACKUP + "/" + row["saved"], value)
            rows.append(row)
        manifest = {"format": 1, "files": rows}
        self.camera.atomic(BACKUP + "/manifest.json", encoded(manifest))
        self.camera.atomic(PENDING, encoded({"format": 1, "operation": operation}))
        self.camera.sync()

    def publish_preload(self, data):
        if data:
            self.camera.atomic(PRELOAD, data, 0o644)
        else:
            self.camera.remove(PRELOAD)

    def stop(self, retire_display=True):
        self.camera.remove(ENABLE)
        self.publish_preload(without_loader(optional(self.camera, PRELOAD)))
        self.camera.sync()
        self.log("已暂停自启，等待现有上传与显示合作退出")
        self.camera.quiesce(retire_display=retire_display)

    def cleanup_staging(self):
        # A lost USB response can leave an incomplete atomic-write temporary.
        # Only explicit installer destinations are eligible; never recurse into
        # application directories, RAM mounts, media, or the rollback contents.
        paths = self.paths()
        self.camera.cleanup_staging(paths + [PENDING, BACKUP + "/manifest.json"] +
                                    [BACKUP + "/" + str(i) for i in range(len(paths))])

    def install(self, settings=None, reuse=False, display=True, preserve_password=False, expected_config=None,
                photos=None, pause_photos_for_native_ftp=None):
        self.verify_firmware()
        self.ownership()
        if self.camera.exists(PENDING):
            raise InstallerError("上次操作尚未完成；请先执行「恢复上次安装」。")
        settings = parse_settings(self.camera) if reuse else settings
        if settings is None:
            raise InstallerError("请填写 FTP 配置，或选择沿用本上传器已有配置。")
        settings = self.resolve_settings(settings, preserve_password, expected_config)
        if photos is not None:
            settings = replace(settings, photos=photos).validate()
        if pause_photos_for_native_ftp is not None:
            settings = replace(settings, pause_photos_for_native_ftp=pause_photos_for_native_ftp).validate()
        features = self.bundle.manifest.get('features', [])
        if settings.photos and 'photos-jpeg-arw' not in features:
            raise InstallerError('当前相机载荷不含图片上传，请使用图片支持版本的完整安装包。')
        supports_pause = 'photo-native-ftp-pause' in features
        if settings.pause_photos_for_native_ftp and not supports_pause:
            raise InstallerError('当前安装包不支持根据原厂 FTP 开关暂停照片上传。')
        pause = settings.pause_photos_for_native_ftp is not False if supports_pause else None
        settings = replace(settings, pause_photos_for_native_ftp=pause)
        self.log("测试 FTP 目标目录：创建、长度确认并删除小测试文件")
        self.ftp_test(settings)
        self.prepare_directories()
        self.snapshot()
        try:
            previous_module = optional(self.camera, "/tmp_bt/a7X.so") if display else None
            same_module = display and previous_module == self.bundle.files[S + "/native-module.so"]
            previous_stage = optional(self.camera, "/setting/a7c-debug/ram/dds-once/bundle.digest") if display else None
            changed_stage = previous_stage is not None and previous_stage.strip() != sha256(self.bundle.files[S + "/manifest"]).encode()
            display_restart = display and ((previous_module is not None and not same_module) or changed_stage)
            self.stop(retire_display=not same_module)
            self.cleanup_staging()
            for path, value in self.bundle.files.items():
                self.camera.atomic(path, value)
            for name, value in settings.camera_files().items():
                self.camera.atomic(P + "/plainftp/" + name, value)
            self.camera.atomic(META, encoded({"owner": "a7c-usb-installer", "format": 1,
                                             "version": self.bundle.version,
                                             "files": {p: sha256(v) for p, v in self.bundle.files.items()}}))
            if display:
                self.camera.atomic(DISPLAY_ENABLE, b"a7c-upload-display-v1\n")
            else:
                self.camera.remove(DISPLAY_ENABLE)
            self.camera.atomic(ENABLE, b"a7c-resident-v1\n")
            # Enable last. A power loss before this leaves the uploader disabled.
            other = without_loader(optional(self.camera, PRELOAD))
            self.publish_preload(other.rstrip(b"\n") + (b"\n" if other.strip() else b"") + LOADER.encode() + b"\n")
            self.camera.sync()
            self.camera.remove(PENDING)
            self.camera.sync()
        except Exception:
            # Do not blindly write more over a disconnected/unknown USB session.
            self.log("操作中止；已保留机内私有备份。重新连接后选择「恢复上次安装」。")
            raise
        self.log("安装完成；备份留在机内私有目录，可显式恢复")
        result = {"version": self.bundle.version, "ftp": settings.public(), "display": display,
                  "requires_power_cycle": bool(display_restart)}
        try:
            result['processes'] = self.camera.start_service()
            result['health'] = result['processes']['health']
            result['service_started'] = True
            result['message'] = ("上传服务已启动；显示模块版本有变化，需完全断电一次才能使用新版显示。"
                                 if display_restart else STARTED_MESSAGE)
        except InstallerError as ex:
            # Activation follows the committed file transaction. A runtime
            # failure must not misreport installation as rolled back/pending.
            result['service_started'] = False
            next_step = (' 显示组件已更新，请按恢复说明完整重启相机后使用，不用再次安装。'
                         if display_restart else ' 可从「更多」选择「启动上传服务」。')
            result['message'] = '安装文件已完成，但服务未就绪：' + str(ex) + next_step
            self.log(result['message'])
        return result

    def start(self):
        self.verify_firmware()
        report = self.inspect()
        if report['pending_recovery']:
            raise InstallerError('上次操作未完成，请先恢复，不启动服务。')
        if report['installed_version'] != self.bundle.version or not report['enabled']:
            raise InstallerError('未发现已启用的当前版本，请先安装或更新。')
        processes = self.camera.start_service()
        return {'started': True, 'version': self.bundle.version, 'service_started': True,
                'processes': processes, 'health':processes['health'], 'requires_power_cycle': False, 'message': STARTED_MESSAGE}

    def diag_enable(self, token):
        """Pair the read-only Wi-Fi diagnostics with a host-generated key."""
        if not isinstance(token, str) or len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            raise InstallerError("诊断配对密钥格式不正确。")
        if 'wifi-diag' not in self.bundle.manifest.get('features', []):
            raise InstallerError("当前相机载荷不含无线诊断。")
        report = self.inspect()
        if report['pending_recovery']:
            raise InstallerError('上次操作未完成，请先恢复。')
        meta = self.metadata(self.camera.read(META)) if self.camera.exists(META) else None
        if not meta or meta['version'] != self.bundle.version or DIAG + "/listener" not in meta['files']:
            raise InstallerError('请先安装或更新到含无线诊断的当前版本。')
        self.camera.diag_stop()
        self.camera.atomic(DIAG_TOKEN, (token + "\n").encode())
        self.camera.atomic(DIAG_ENABLE, b"a7c-diag-v1\n")
        self.camera.sync()
        pid = self.camera.diag_start() if report['enabled'] else None
        self.log("无线诊断已配对" + ("，监听已启动" if pid else "；将随上传服务下次启动"))
        return {"wifi_diag": True, "listener_pid": pid}

    def diag_disable(self):
        self.camera.remove(DIAG_ENABLE)
        self.camera.remove(DIAG_TOKEN)
        self.camera.sync()
        self.camera.diag_stop()
        self.log("无线诊断已关闭，配对密钥已从相机删除")
        return {"wifi_diag": False}

    def restore(self):
        self.verify_firmware()
        raw = optional(self.camera, BACKUP + "/manifest.json")
        if raw is None:
            raise InstallerError("没有可恢复的安装备份。")
        try:
            manifest = json.loads(raw)
            rows = manifest["files"]
            names = {r["path"] for r in rows}
            required = {PRELOAD, ENABLE, META, CONFIG, PASSWORD, LOADER}
            if manifest["format"] != 1 or len(rows) != len(names) or not required <= names <= set(self.paths()):
                raise ValueError()
            values = {}
            for row in rows:
                name = row["saved"]
                if name is None:
                    values[row["path"]] = None
                else:
                    if not isinstance(name, str) or not name.isdecimal() or len(name) > 3:
                        raise ValueError()
                    data = self.camera.read(BACKUP + "/" + name)
                    if sha256(data) != row["sha256"]:
                        raise ValueError()
                    values[row["path"]] = data
        except (ValueError, KeyError, TypeError):
            raise InstallerError("安装备份不完整或校验失败；保留现场，未开始恢复。") from None
        self.camera.atomic(PENDING, encoded({"format": 1, "operation": "restore"}))
        self.camera.sync()
        self.stop()
        self.cleanup_staging()
        # Restore previous loader last; keep changes by other installers intact.
        old_preload = values.pop(PRELOAD)
        for path, value in values.items():
            if value is None:
                self.camera.remove(path)
            else:
                self.camera.atomic(path, value)
        foreign = without_loader(optional(self.camera, PRELOAD))
        old_owned = old_preload is not None and without_loader(old_preload) != old_preload
        self.publish_preload(foreign.rstrip(b"\n") + (b"\n" if foreign.strip() else b"") + (LOADER.encode() + b"\n" if old_owned else b""))
        self.camera.sync()
        self.camera.remove(PENDING)
        self.log("上次应用文件与启用状态已恢复；照片、视频和 SD 回执未改动")
        return {"restored": True, "requires_power_cycle": True}

    def uninstall(self):
        self.verify_firmware()
        raw = optional(self.camera, META)
        if raw is None:
            raise InstallerError("没有发现本安装器管理的版本；未删除未知程序。")
        installed = self.metadata(raw)
        if self.camera.exists(PENDING):
            raise InstallerError("请先恢复上次未完成的操作。")
        self.prepare_directories()
        self.snapshot("uninstall")
        self.stop()
        self.cleanup_staging()
        for path in set(installed['files']) | {CONFIG, PASSWORD, META, ENABLE, DISPLAY_ENABLE, DIAG_ENABLE, DIAG_TOKEN} | DIAG_FILES:
            self.camera.remove(path)
        self.camera.sync()
        self.camera.remove(PENDING)
        self.log("上传自启和本安装器的程序、FTP 配置已移除；机内回退备份仍保留")
        return {"uninstalled": True, "requires_power_cycle": True,
                "message": "相机上传与显示服务、自启和当前 FTP 配置已移除。请断开 USB 及外接电源，正常关机、等卡灯熄灭，取电池约 30 秒再装回，以释放旧 RAM 程序。照片、视频与 SD 回执保留。私有回退备份仍可能含 FTP 密码，恢复备份会重新启用原服务及其配置。Windows 驱动恢复结果由桌面工具或脚本另行报告。"}
