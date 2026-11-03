"""Test the selected ordinary FTP directory without reading existing media."""
import ftplib
import io
import secrets
from .configuration import InstallerError


def test_ftp(settings, factory=ftplib.FTP):
    settings.validate()
    name = ".a7c-installer-" + secrets.token_hex(12)
    data = b"A7C installer directory test\n"
    ftp = factory()
    created = False
    try:
        ftp.connect(settings.host, settings.port, timeout=10)
        ftp.login(settings.username, settings.password)
        ftp.cwd(settings.directory)
        ftp.voidcmd("TYPE I")
        # ftplib's passive mode uses the control peer address by default.
        created = True
        ftp.storbinary("STOR " + name, io.BytesIO(data))
        if ftp.size(name) != len(data):
            raise InstallerError("FTP 测试文件长度不符。")
        ftp.rename(name, name + "-renamed")
        name += "-renamed"
        ftp.delete(name)
        created = False
        return {"ok": True, "bytes": len(data), "scope": "computer-to-FTP"}
    except InstallerError:
        raise
    except Exception:
        raise InstallerError("FTP 测试失败：请检查地址、账号、目录、被动端口及写入/删除权限。") from None
    finally:
        if created:
            try:
                ftp.delete(name)
            except Exception:
                pass
        try:
            ftp.close()
        except Exception:
            pass
