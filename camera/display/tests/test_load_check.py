"""Exercise direct child exit, signal, timeout and exec failure without a camera."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


class LoadCheckTests(unittest.TestCase):
    def test_bounded_child_and_fixed_modes(self):
        src = Path(__file__).resolve().parents[1] / "once"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, runner = root / "target", root / "check"
            subprocess.run([
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-DCHECK_SECONDS=1",
                "-DCHECK_TARGET=" + json.dumps(str(target)),
                str(src / "load_check.c"), str(src / "environment.c"),
                "-o", str(runner),
            ], check=True, capture_output=True)
            cases = [
                ("int main(void) { return 0; }", 0, "signal=0 exit=0"),
                ("int main(void) { return 7; }", 7, "signal=0 exit=7"),
                ("#include <signal.h>\nint main(void) { raise(SIGTERM); }", 143,
                 "signal=15 exit=0"),
                ("#include <unistd.h>\nint main(void) { for (;;) pause(); }", 124,
                 "signal=14 exit=0"),
            ]
            for source, code, output in cases:
                (root / "target.c").write_text(source)
                subprocess.run(["cc", str(root / "target.c"), "-o", str(target)],
                               check=True, capture_output=True)
                result = subprocess.run([str(runner), "baseline"], capture_output=True,
                                        text=True, timeout=4)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(output, result.stdout)
            target.unlink()
            result = subprocess.run([str(runner), "entry"], capture_output=True, timeout=4)
            self.assertEqual(result.returncode, 126)
            result = subprocess.run([str(runner), "/usr/bin/im.elf"], capture_output=True)
            self.assertEqual(result.returncode, 64)


if __name__ == "__main__":
    unittest.main()
