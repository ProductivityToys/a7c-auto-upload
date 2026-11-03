"""Run the actual observer C code with native ABI/platform stand-ins, offline."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class PassiveObserverTests(unittest.TestCase):
    def test_callback_boundaries_under_sanitizers(self):
        source = Path(__file__).resolve().parents[1] / "observer"
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "test-observer"
            subprocess.run([
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-Dreadlink=fake_readlink",
                "-Dgetpid=fake_getpid", "-Dsyscall=fake_syscall",
                str(source / "passive.c"), str(source / "test_passive.c"),
                "-o", str(binary),
            ], check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn("16 boundary groups passed", result.stdout)
            print(result.stdout, end="")


if __name__ == "__main__":
    unittest.main()
