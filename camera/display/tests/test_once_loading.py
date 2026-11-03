"""Real host files, processes and entry constructor; no Sony code or USB access."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class OneShotLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.root = cls.base / "once"
        cls.preload = cls.base / "ld.so.preload"
        cls.src = Path(__file__).resolve().parents[1] / "once"
        cls.fixture = Path(__file__).resolve().parent
        cls.define = "-DONCE_ROOT=" + json.dumps(str(cls.root))
        cls.flags = ["cc", "-std=c11", "-D_DARWIN_C_SOURCE", "-D_GNU_SOURCE",
                     "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                     "-fno-omit-frame-pointer", cls.define]
        # Compile shim alone with redirected syscall/execve/fsync names.
        cls.compile(["-Dexecve=once_execve", "-DONCE_TEST_SYSCALL",
                     "-Dreadlink=once_readlink", "-Dfsync=once_fsync",
                     "-c", str(cls.src / "shim.c"), "-o", str(cls.base / "shim.o")])
        cls.runner = cls.base / "runner"
        cls.compile([str(cls.base / "shim.o"), str(cls.src / "environment.c"),
                     str(cls.fixture / "once_exec_fixture.c"), "-o", str(cls.runner)])
        cls.entry = cls.base / "entry-test"
        cls.compile([str(cls.src / "entry.c"), str(cls.src / "environment.c"),
                     str(cls.fixture / "once_entry_fixture.c"), "-o", str(cls.entry)])
        cls.revoke = cls.base / "revoke"
        cls.compile(["-DPRELOAD_PATH=" + json.dumps(str(cls.preload)),
                     "-DPRELOAD_PARENT=" + json.dumps(str(cls.base)),
                     str(cls.src / "revoke.c"), str(cls.src / "environment.c"),
                     "-o", str(cls.revoke)])
        cls.enable = cls.base / "enable"
        cls.compile(["-DPRELOAD_PATH=" + json.dumps(str(cls.preload)),
                     "-DPRELOAD_PARENT=" + json.dumps(str(cls.base)),
                     "-DSETTING_PARENT=" + json.dumps(str(cls.base)),
                     "-Dfsync=once_enable_fsync", "-c", str(cls.src / "enable.c"),
                     "-o", str(cls.base / "enable.o")])
        cls.compile([str(cls.base / "enable.o"), str(cls.src / "environment.c"),
                     str(cls.fixture / "once_barrier_fixture.c"),
                     "-o", str(cls.enable)])

    @classmethod
    def compile(cls, args):
        result = subprocess.run(cls.flags + args, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.preload.write_bytes(b"/existing/debug.so\n/existing/upload.so\n")
        (self.root / "preload.before").write_bytes(self.preload.read_bytes())
        Path(str(self.preload) + ".a7c-ui-new").unlink(missing_ok=True)
        self.load = f"{self.root}/entry.so:{self.root}/observer.so"
        self.line = (str(self.root) + "/exec-shim.so\n").encode()
        self.env = {"PATH": "/usr/bin:/bin", "KEEP": "unchanged"}

    def arm(self):
        (self.root / "armed").write_bytes(b"a7c-ui-once-v1\n")

    def run_exec(self, caller="/usr/bin/bootin.elf", target="/usr/bin/im.elf",
                 fail=0, env=None):
        result = subprocess.run([str(self.runner), caller, target, str(fail)],
                                env=self.env if env is None else env,
                                check=True, capture_output=True, text=True)
        fields = dict(item.split("=") for item in result.stdout.strip().split())
        self.assertEqual(fields["restored"], "1")
        self.assertEqual(fields["argv"], "1")
        self.assertEqual(fields["errno"], "13")
        return fields

    def test_default_and_caller_target_scope(self):
        self.assertEqual(self.run_exec()["injected"], "0")
        self.arm()
        for caller, target in [("/bin/ash", "/usr/bin/im.elf"),
                               ("/usr/bin/bootin.elf", "/bin/ash"),
                               ("/usr/bin/bootin.elf", "/usr/bin/im.elf.extra")]:
            self.assertEqual(self.run_exec(caller, target)["injected"], "0")
        self.assertFalse((self.root / "spent").exists())

    def test_once_including_exec_failure_and_process_restart(self):
        self.arm()
        self.assertEqual(self.run_exec()["injected"], "1")
        self.assertEqual((self.root / "spent").read_bytes(), b"a7c-ui-once-v1\n")
        self.assertEqual(self.run_exec()["injected"], "0")

    def test_empty_existing_and_unset_preload_preserved(self):
        for value in (None, "", "/old/a.so:/old/b.so", " /old/a.so\t/old/b.so "):
            self.arm()
            (self.root / "spent").unlink(missing_ok=True)
            env = dict(self.env)
            if value is not None:
                env["LD_PRELOAD"] = value
            self.assertEqual(self.run_exec(env=env)["injected"], "1")

    def test_reject_internal_marker_and_oversized_environment(self):
        self.arm()
        for extra in ({"A7C_UI_ONCE": "v1"}, {"A7C_UI_SAVED_LD_PRELOAD": ""},
                      {"LD_PRELOAD": "x" * 2048},
                      {"LD_PRELOAD": self.load},
                      {f"X{i}": "v" for i in range(128)}):
            self.assertEqual(self.run_exec(env={**self.env, **extra})["injected"], "0")
            self.assertFalse((self.root / "spent").exists())

    def test_bad_overlong_and_symlink_tickets(self):
        for content in (b"", b"a7c-ui-once-v1\nextra", b"wrong\n"):
            (self.root / "armed").write_bytes(content)
            self.assertEqual(self.run_exec()["injected"], "0")
        (self.root / "armed").unlink()
        (self.root / "data").write_bytes(b"a7c-ui-once-v1\n")
        (self.root / "armed").symlink_to(self.root / "data")
        self.assertEqual(self.run_exec()["injected"], "0")
        self.assertFalse((self.root / "spent").exists())

    def test_each_durability_failure_consumes_without_injecting(self):
        for fail in (1, 2):
            self.arm()
            (self.root / "spent").unlink(missing_ok=True)
            self.assertEqual(self.run_exec(fail=fail)["injected"], "0")
            self.assertTrue((self.root / "spent").exists())
            self.assertEqual(self.run_exec()["injected"], "0")

    def test_concurrent_claim_has_single_winner(self):
        self.arm()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.run_exec()["injected"], range(6)))
        self.assertEqual(results.count("1"), 1)

    def test_real_entry_constructor_scrubs_before_child_exec(self):
        for old in (None, "", "/old/a.so:/old/b.so"):
            env = dict(self.env, LD_PRELOAD=self.load, A7C_UI_ONCE="v1")
            if old is not None:
                env["LD_PRELOAD"] += ":" + old
                env["A7C_UI_SAVED_LD_PRELOAD"] = old
            result = subprocess.run([str(self.entry)], env=env, capture_output=True,
                                    check=True, text=True)
            lines = result.stdout.splitlines()
            self.assertEqual(lines[0], "entry_constructor_ok")
            child = dict(line.split("=", 1) for line in lines[1:])
            expected = dict(self.env)
            if old is not None:
                expected["LD_PRELOAD"] = old
            self.assertEqual(child, expected)

    def disable(self, expected=0):
        result = subprocess.run([str(self.revoke), "--disable"], capture_output=True)
        self.assertEqual(result.returncode, expected, result.stderr)

    def test_revoke_restores_exact_original_including_no_newline(self):
        for before in (b"", b"/original.so", b"/original.so\n"):
            self.arm()
            (self.root / "preload.before").write_bytes(before)
            self.preload.write_bytes(before + (b"\n" if before and not before.endswith(b"\n") else b"")
                                     + self.line)
            self.disable()
            self.assertFalse((self.root / "armed").exists())
            self.assertEqual(self.preload.read_bytes(), before)
            self.disable()

    def test_revoke_preserves_other_later_entries_and_mapped_files(self):
        self.arm()
        old = self.preload.read_bytes()
        self.preload.write_bytes(old + self.line + b"/later.so\n")
        (self.root / "observer.so").write_bytes(b"mapped binary stand-in")
        self.disable()
        self.assertEqual(self.preload.read_bytes(), old + b"/later.so\n")
        self.assertTrue((self.root / "observer.so").exists())

    def test_revoke_ambiguous_line_disables_ticket_and_preserves_config(self):
        for tail in (self.line + self.line, b" " + self.line, b"/other.so " + self.line):
            self.arm()
            current = b"/existing.so\n" + tail
            self.preload.write_bytes(current)
            self.disable(3)
            self.assertFalse((self.root / "armed").exists())
            self.assertEqual(self.preload.read_bytes(), current)

    def test_revoke_refuses_stale_temp_without_overwrite(self):
        self.arm()
        current = self.preload.read_bytes() + self.line
        self.preload.write_bytes(current)
        temp = Path(str(self.preload) + ".a7c-ui-new")
        temp.write_bytes(b"preserve")
        self.disable(4)
        self.assertEqual(temp.read_bytes(), b"preserve")
        self.assertEqual(self.preload.read_bytes(), current)
        self.assertFalse((self.root / "armed").exists())

    def stage(self):
        for name in ("exec-shim.so", "entry.so", "observer.so", "enable", "revoke"):
            (self.root / name).write_bytes(b"hash-verified stand-in")

    def activate(self, arg="--enable", expected=0, fail=0):
        result = subprocess.run([str(self.enable), arg], capture_output=True,
                                env={**os.environ, "ONCE_FAIL_FSYNC": str(fail)})
        self.assertEqual(result.returncode, expected, result.stderr)

    def test_enable_storage_check_then_roundtrip_and_single_claim(self):
        self.stage()
        original = self.preload.read_bytes()
        self.activate("--check-storage")
        self.assertEqual(self.preload.read_bytes(), original)
        self.assertFalse((self.root / "armed").exists())
        self.activate()
        self.assertEqual(self.preload.read_bytes(), original + self.line)
        self.assertEqual(self.run_exec()["injected"], "1")
        self.disable()
        self.assertEqual(self.preload.read_bytes(), original)
        self.activate(expected=3)  # No rearming a consumed experiment.

    def test_enable_refuses_missing_payload_changed_baseline_and_owned_path(self):
        self.activate(expected=2)
        self.stage()
        self.preload.write_bytes(b"/changed.so\n")
        self.activate(expected=3)
        self.assertFalse((self.root / "armed").exists())
        self.preload.write_bytes(self.line)
        (self.root / "preload.before").write_bytes(self.line)
        self.activate(expected=3)

    def test_enable_refuses_stale_ticket_temp_and_embedded_nul(self):
        self.stage()
        self.arm()
        self.activate(expected=3)
        (self.root / "armed").unlink()
        temp = Path(str(self.preload) + ".a7c-ui-new")
        temp.write_bytes(b"preserve")
        self.activate(expected=3)
        self.assertEqual(temp.read_bytes(), b"preserve")
        temp.unlink()
        self.preload.write_bytes(b"/old.so\x00\n")
        (self.root / "preload.before").write_bytes(self.preload.read_bytes())
        self.activate(expected=3)

    def test_enable_each_sync_failure_leaves_no_ticket_and_is_revocable(self):
        for fail in range(1, 14):
            with self.subTest(fsync_call=fail):
                self.setUp()
                self.stage()
                original = self.preload.read_bytes()
                self.activate(expected=2 if fail <= 9 else 4 if fail <= 11 else 5,
                              fail=fail)
                self.assertFalse((self.root / "armed").exists())
                # Before rename, the temp is retained and current is unchanged.
                # After rename, revoke must undo the committed owned line.
                self.disable()
                self.assertEqual(self.preload.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
