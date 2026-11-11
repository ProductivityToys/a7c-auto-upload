"""Numbered terminal entry for the script bundle; shares the install engine."""
import getpass
import json
import sys
from . import __version__
from .bundle import Bundle
from .configuration import FtpSettings, InstallerError
from .documentation import read_guide
from .ftp_check import test_ftp
from .operations import Installer

MENU = '''
1  连接相机并读取配置
2  安装 / 更新 FTP 配置
3  测试 FTP 目标目录
4  读取运行日志
5  卸载相机服务
6  恢复上次安装
7  准备 Windows 驱动
8  恢复 Windows 普通 USB 导入
9  使用说明与恢复步骤
0  退出
'''


def prompt_settings(saved, ask=input, secret=getpass.getpass):
    saved = saved or {}
    def field(label, name, default=''):
        value = str(saved.get(name, default))
        answer = ask(label + (f' [{value}]' if value else '') + '：').strip()
        return answer or value
    host = field('NAS IPv4', 'host')
    try:
        port = int(field('端口', 'port', '21'))
    except ValueError:
        raise InstallerError('端口须为数字。') from None
    username = field('用户名', 'username')
    directory = field('FTP 目录', 'directory', '/')
    def switch(label, current):
        answer = ask(label + (' [Y/n]：' if current else ' [y/N]：')).strip().lower()
        if answer in ('y', 'yes', '1', '是'):
            return True
        if answer in ('n', 'no', '0', '否'):
            return False
        if answer:
            raise InstallerError('图片上传选项请输入 y 或 n，留空沿用。')
        return current

    photos = switch('同时上传图片（JPEG 和 RAW）', bool(saved.get('photos', False)))
    pause_photos = saved.get('pause_photos_for_native_ftp')
    if photos:
        pause_photos = switch('原厂 FTP 开启时，暂停本服务的照片上传', pause_photos is not False)
    password = secret('FTP 密码（留空沿用相机已保存密码）：' if saved else 'FTP 密码：')
    settings = FtpSettings(host, port, username, directory, password, photos=photos,
                           pause_photos_for_native_ftp=pause_photos)
    preserve = bool(saved) and not password
    (settings.validate_target() if preserve else settings.validate())
    return settings, preserve


def main(ask=input, secret=getpass.getpass):
    saved = None
    print(f'A7C 自动上传 · 脚本版 {__version__}')
    print('先连接相机（开机、海量存储器），选择 1；再填写配置并选择 2。')
    while True:
        print(MENU)
        try:
            choice = ask('请输入数字：').strip()
            if choice == '0':
                return 0
            if choice == '9':
                print(read_guide('START_HERE.md'))
                print(read_guide('RECOVERY.md'))
                continue
            if choice not in tuple(str(n) for n in range(1, 9)):
                print('请选择 0–9。')
                continue
            if choice in ('7', '8'):
                from .drivers.windows import DriverManager
                manager = DriverManager(log=print)
                result = manager.ensure() if choice == '7' else manager.restore()
            else:
                settings = None
                preserve = False
                if choice in ('2', '3'):
                    settings, preserve = prompt_settings(saved, ask, secret)
                if choice == '3' and not preserve:
                    result = test_ftp(settings)
                else:
                    from .transport.sony_usb import SonyUsb
                    with SonyUsb(print) as camera:
                        engine = Installer(camera, Bundle(), print)
                        if choice == '1':
                            result = engine.inspect()
                            saved = result['ftp']
                            print('已读取配置；密码已保存，留空沿用。' if saved else '首次安装，请在选项 2 中填写 FTP 配置。')
                        elif choice == '2':
                            result = engine.install(settings, preserve_password=preserve, expected_config=saved)
                            saved = result['ftp']
                        elif choice == '3':
                            engine.verify_firmware()
                            settings = engine.resolve_settings(settings, preserve, saved)
                        elif choice == '4':
                            result = {'inspection': engine.inspect(), 'runtime': camera.runtime_report()}
                        elif choice == '5':
                            result = engine.uninstall()
                            saved = None
                        else:
                            result = engine.restore()
                            saved = None
                    if choice == '3':
                        result = test_ftp(settings)
                    if choice == '5' and sys.platform == 'win32':
                        from .drivers.windows import DriverManager
                        try:
                            result['driver_restore'] = DriverManager(log=print).restore()
                        except InstallerError as ex:
                            print('相机服务已卸载，驱动恢复未完成：' + str(ex) + '；可选 8 单独重试。')
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except InstallerError as ex:
            print('未完成：' + str(ex))
        except (EOFError, KeyboardInterrupt):
            print('\n已退出。')
            return 0
        except Exception:
            print('操作未完成，请保留相机状态。若安装已经开始，请选择 6 恢复；未输出可能含凭据的原始响应。')


if __name__ == '__main__':
    sys.exit(main())
