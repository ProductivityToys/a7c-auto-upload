"""Read the installer payload and its explicit file/firmware manifest."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import zipfile
from .configuration import InstallerError


RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
ROOTS = ("/setting/a7c-uploader/", "/setting/a7c-display/", "/setting/a7c-diag/")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Bundle:
    def __init__(self, path=None):
        self.path = Path(path) if path else RESOURCE_DIR / "camera.zip"
        self.files = {}
        try:
            with zipfile.ZipFile(self.path) as archive:
                names = archive.namelist()
                if len(names) > 64 or sum(i.file_size for i in archive.infolist()) > 4 * 1024 * 1024 or len(names) != len(set(names)):
                    raise ValueError("duplicate members")
                self.manifest = json.loads(archive.read("manifest.json"))
                if self.manifest["format"] != 1:
                    raise ValueError("format")
                expected = set(self.manifest["files"]) | {"manifest.json"}
                if set(names) != expected:
                    raise ValueError("unexpected members")
                for name, row in self.manifest["files"].items():
                    p = PurePosixPath(name)
                    target = row["target"]
                    if (p.is_absolute() or ".." in p.parts or "\\" in name
                            or not target.startswith(ROOTS) or ".." in PurePosixPath(target).parts
                            or "//" in target or "\\" in target or target in self.files):
                        raise ValueError("unsafe target")
                    value = archive.read(name)
                    if len(value) != row["bytes"] or sha256(value) != row["sha256"]:
                        raise ValueError("digest mismatch")
                    self.files[target] = value
        except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile):
            raise InstallerError("安装载荷缺失或校验失败，请重新解压完整安装包。") from None

    @property
    def version(self):
        return self.manifest["payload_version"]

    @property
    def firmware(self):
        return self.manifest["firmware"]
