"""Script interface. Password input is hidden; never accepted on the command line."""
import argparse
import getpass
import json
import sys
from .bundle import Bundle
from .configuration import FtpSettings, InstallerError
from .ftp_check import test_ftp
from .operations import Installer


def main(argv=None):
    parser = argparse.ArgumentParser(description="A7C USB Installer — ILCE-7C 2.00")
    parser.add_argument("action", choices=("detect", "inspect", "diagnose", "install", "configure", "uninstall", "restore", "start", "test-ftp", "driver-install", "driver-restore"))
    parser.add_argument("--host", help="NAS IPv4")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--username")
    parser.add_argument("--directory", default="/")
    parser.add_argument("--reuse", action="store_true", help="沿用本上传器已有的 FTP 配置")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--yes", action="store_true", help="执行安装/配置/卸载/恢复")
    parser.add_argument("--full", action="store_true", help="inspect 时验证原厂文件依赖")
    parser.add_argument('--keep-driver', action='store_true', help='Windows 卸载相机服务后保留电脑驱动')
    args = parser.parse_args(argv)

    def log(message):
        print(message, file=sys.stderr, flush=True)

    try:
        if args.action in ("install", "configure", "uninstall", "restore", "driver-install", "driver-restore") and not args.yes:
            raise InstallerError("此命令会修改相机应用或 Windows USB 驱动；检查参数后添加 --yes 执行。")
        settings = None
        if args.action in ("install", "configure", "test-ftp") and not args.reuse:
            if not args.host or not args.username:
                raise InstallerError("请填写 --host 与 --username；密码通过隐藏输入读取。")
            settings = FtpSettings(args.host, args.port, args.username, args.directory,
                                   getpass.getpass("FTP 密码：")).validate()
        if args.action in ('driver-install', 'driver-restore'):
            from .drivers.windows import DriverManager
            manager = DriverManager(log=log)
            result = manager.ensure() if args.action == 'driver-install' else manager.restore()
        elif args.action == "test-ftp":
            if settings is None:
                raise InstallerError("test-ftp 请填写连接参数。")
            result = test_ftp(settings)
        else:
            from .transport.sony_usb import SonyUsb, detect
            if args.action == "detect":
                result = {"usb": detect()}
            else:
                with SonyUsb(log) as camera:
                    engine = Installer(camera, Bundle(), log)
                    if args.action == "inspect":
                        result = engine.inspect(args.full)
                    elif args.action == "diagnose":
                        result = {"inspection": engine.inspect(), "runtime": camera.runtime_report()}
                    elif args.action in ("install", "configure"):
                        result = engine.install(settings, args.reuse, not args.no_display)
                    elif args.action == "uninstall":
                        result = engine.uninstall()
                    elif args.action == "start":
                        result = engine.start()
                    else:
                        result = engine.restore()
                if args.action == 'uninstall' and sys.platform == 'win32' and not args.keep_driver:
                    from .drivers.windows import DriverManager
                    try:
                        result['driver_restore'] = DriverManager(log=log).restore()
                    except InstallerError as ex:
                        log('相机服务已卸载，Windows 驱动恢复未完成：' + str(ex))
                        log('可使用 driver-restore --yes 单独重试。')
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                        return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except InstallerError as ex:
        log(str(ex))
        return 1
    except KeyboardInterrupt:
        log("操作已中断；若已开始写入，请重新连接后检查或恢复。")
        return 130
    except Exception:
        log("操作未完成；未输出原始设备响应以避免泄漏凭据。请重新连接后检测，必要时恢复上次安装。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
