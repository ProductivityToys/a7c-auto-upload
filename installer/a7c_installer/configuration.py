"""FTP configuration contract matching the camera's ordinary FTP client."""
from dataclasses import dataclass, field
import ipaddress
import posixpath


class InstallerError(Exception):
    """A bounded, user-facing error; never contains credentials."""


@dataclass(frozen=True)
class FtpSettings:
    host: str
    port: int
    username: str
    directory: str
    password: str = field(repr=False, compare=False)
    photos: bool = False
    pause_photos_for_native_ftp: bool | None = None

    def validate_target(self):
        if (not isinstance(self.photos, bool) or
                (self.pause_photos_for_native_ftp is not None and not isinstance(self.pause_photos_for_native_ftp, bool))):
            raise InstallerError("图片上传开关须为布尔值。")
        try:
            address = ipaddress.IPv4Address(self.host)
            if address.is_unspecified or address.is_multicast or int(address) == 0xffffffff:
                raise ValueError()
        except (ValueError, ipaddress.AddressValueError):
            raise InstallerError("NAS 地址须填写 IPv4 地址，例如 192.168.1.20。") from None
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise InstallerError("FTP 端口须为 1–65535。")
        for name, value, limit in (("用户名", self.username, 128), ("目录", self.directory, 400)):
            if not value or len(value) > limit or any(not 32 <= ord(c) <= 126 for c in value):
                raise InstallerError(f"{name}须为可打印英文字符，最长 {limit} 个字符。")
        if (not self.directory.startswith("/") or posixpath.normpath(self.directory) != self.directory
                or "//" in self.directory or any(x in (".", "..") for x in self.directory.split("/"))):
            raise InstallerError("目录须为规范的绝对 FTP 路径，例如 / 或 /Camera。")
        return self

    def validate(self):
        self.validate_target()
        secret = self.password.encode("utf-8")
        if not secret or len(secret) > 255 or any(c < 32 or c == 127 for c in secret):
            raise InstallerError("FTP 密码须为 1–255 字节，不能包含换行或控制字符。")
        return self

    def camera_files(self):
        self.validate()
        target = f"{self.host}\n{self.port}\n{self.username}\n{self.directory}\n"
        if self.pause_photos_for_native_ftp is not None:
            text = f"a7c-plainftp-v3\n{target}{int(self.photos)}\n{int(self.pause_photos_for_native_ftp)}\n"
        elif self.photos:
            text = f"a7c-plainftp-v2\n{target}1\n"
        else:
            text = f"a7c-plainftp-v1\n{target}"
        return {"config": text.encode("ascii"), "password": self.password.encode("utf-8") + b"\n"}

    def public(self):
        return {"host": self.host, "port": self.port, "username": self.username, "directory": self.directory,
                "photos": self.photos, "pause_photos_for_native_ftp": self.pause_photos_for_native_ftp}
