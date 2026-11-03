"""Exercise timed observation, cancellation and single-query failure handling."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "detached_layout.sh"


class CollectorTest(unittest.TestCase):
    def run_case(self, states, cancel=False, snapshot_fails=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ram = root / "ram"
            dest = ram / "ui-layout-once"
            dest.mkdir(parents=True)
            if cancel:
                (dest / "cancel").touch()
            (root / "mounts").write_text(f"a7c-debug-ram {ram} tmpfs rw 0 0\n")
            (root / "uptime").write_text("1000.00 1.00\n")
            (root / "states").write_text(json.dumps(states))
            busybox = root / "busybox"
            busybox.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys,subprocess\n"
                "from pathlib import Path\n"
                "r=Path(__file__).parent;a=sys.argv[1:]\n"
                "if a[0]=='sleep':sys.exit(0)\n"
                "if a[:2]==['cat',str(r/'udc')]:\n"
                " p=r/'index';i=int(p.read_text()) if p.exists() else 0\n"
                " s=json.loads((r/'states').read_text());v=s[min(i,len(s)-1)]\n"
                " p.write_text(str(i+1))\n"
                " if v is None:sys.exit(1)\n"
                " print(v);sys.exit(0)\n"
                "if a[0]=='timeout':a=a[5:]\n"
                "sys.exit(subprocess.call(a))\n"
            )
            logtool = root / "ulogio"
            logtool.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\nfrom pathlib import Path\n"
                "assert sys.argv[1:4]==['dk','0x034fd000','0x8000']\n"
                f"if {snapshot_fails!r}:sys.exit(7)\n"
                "Path(sys.argv[4]).write_bytes(b'x'*32768)\n"
            )
            probe = dest / "ui-layout"
            probe.write_text(
                "#!/bin/sh\n"
                f"echo query >> '{root}/queries'\n"
            )
            for p in (busybox, logtool, probe):
                p.chmod(0o700)
            script = SOURCE.read_text()
            for old, new in (
                ("B=/bin/busybox", f"B={busybox}"),
                ("R=/setting/a7c-debug/ram", f"R={ram}"),
                ("UDC=/sys/class/udc/dwc3.0/state", f"UDC={root}/udc"),
                ("/proc/mounts", str(root / "mounts")),
                ("/proc/uptime", str(root / "uptime")),
                ("/usr/bin/ulogio", str(logtool)),
            ):
                script = script.replace(old, new)
            result = subprocess.run(["/bin/sh"], input=script, text=True,
                                    capture_output=True, timeout=30)
            queries = (root / "queries").read_text().splitlines() if (root / "queries").exists() else []
            return result.returncode, queries, (dest / "done").read_text()

    def test_default_state_queries_once(self):
        rc, queries, done = self.run_case(["configured"] + ["default"] * 100)
        self.assertEqual((rc, len(queries), done), (0, 1, "exit=0\n"))

    def test_stable_disconnect_queries_once(self):
        rc, queries, done = self.run_case(["configured"] + ["not attached"] * 20)
        self.assertEqual((rc, len(queries), done), (0, 1, "exit=0\n"))

    def test_connected_still_allows_verified_readonly_query(self):
        rc, queries, _ = self.run_case(["configured"])
        self.assertEqual((rc, len(queries)), (0, 1))

    def test_missing_state_is_not_disconnect(self):
        rc, queries, _ = self.run_case(["configured", None])
        self.assertEqual((rc, queries), (97, []))

    def test_cancel_prevents_query(self):
        rc, queries, _ = self.run_case(["configured"], cancel=True)
        self.assertEqual((rc, queries), (94, []))

    def test_failed_baseline_prevents_query(self):
        rc, queries, _ = self.run_case(["configured"], snapshot_fails=True)
        self.assertEqual((rc, queries), (96, []))


if __name__ == "__main__":
    unittest.main()
