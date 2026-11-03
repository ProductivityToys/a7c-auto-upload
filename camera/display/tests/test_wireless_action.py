"""Use fake log I/O to check one-shot claiming across separate invocations."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "wireless_action.sh"


class WirelessActionTests(unittest.TestCase):
    def scenario(self, fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "ram/ui-layout-once"
            dest.mkdir(parents=True)
            (root / "mounts").write_text(f"a7c-debug-ram {root}/ram tmpfs rw\n")
            (root / "udc").write_text("default\n")
            (root / "uptime").write_text("1200.00 9.00\n")
            bb = root / "busybox"
            bb.write_text(
                "#!/usr/bin/env python3\nimport sys,subprocess\n"
                "a=sys.argv[1:]\n"
                "if a[0]=='sleep':sys.exit(0)\n"
                "if a[0]=='timeout':a=a[5:]\n"
                "sys.exit(subprocess.call(a))\n"
            )
            native = root / "ulogio"
            native.write_text(
                "#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n"
                f"if {fail!r}:sys.exit(7)\n"
                "text=b'== <Display LayoutList> ==\\ngroupID:123 layoutID:456\\n'\n"
                "Path(sys.argv[4]).write_bytes(text+b'\\n'*(32768-len(text)))\n"
            )
            probe = dest / "ui-layout"
            probe.write_text(f"#!/bin/sh\necho query >> '{root}/queries'\n")
            for p in (bb, native, probe):
                p.chmod(0o700)
            text = SOURCE.read_text()
            for a, b in [
                ("B=/bin/busybox", f"B={bb}"),
                ("/setting/a7c-debug/ram", str(root / "ram")),
                ("/proc/mounts", str(root / "mounts")),
                ("/proc/uptime", str(root / "uptime")),
                ("/sys/class/udc/dwc3.0/state", str(root / "udc")),
                ("/usr/bin/ulogio", str(native)),
            ]:
                text = text.replace(a, b)
            action = root / "action.sh"
            action.write_text(text)
            def run(verb):
                return subprocess.run(["sh", str(action), verb], capture_output=True,
                                      text=True, timeout=5)
            first, second, status = run("PROBE"), run("PROBE"), run("STATUS")
            count = len((root / "queries").read_text().splitlines()) if (root / "queries").exists() else 0
            return first.returncode, second.returncode, count, status.stdout

    def test_success_claim_blocks_duplicate(self):
        first, second, count, status = self.scenario()
        self.assertEqual((first, second, count), (0, 92, 1))
        self.assertIn("stage=captured", status)
        self.assertIn("groupID:123 layoutID:456", status)
        self.assertTrue(status.endswith("A7C_DEBUG_END\n"))

    def test_failed_baseline_claim_blocks_retry(self):
        first, second, count, status = self.scenario(fail=True)
        self.assertEqual((first, second, count), (96, 92, 0))
        self.assertIn("exit=96", status)
