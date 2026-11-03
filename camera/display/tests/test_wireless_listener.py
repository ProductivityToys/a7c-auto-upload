"""Check real listener authentication and observer-only command boundaries."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[2] / "debugger/tests/test_listener.py"
spec = importlib.util.spec_from_file_location("shared_listener_tests", source)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


class ObserverListenerTests(unittest.TestCase):
    additional_flags = ["-DDISPLAY_OBSERVER_ONLY"]
    setUp = shared.ListenerTests.setUp
    tearDown = shared.ListenerTests.tearDown
    call = shared.ListenerTests.call
    test_auth_session_replay_and_unknown_action = shared.ListenerTests.test_auth_session_replay_and_unknown_action
    test_idle_blocks_without_periodic_timer_and_term_exits = shared.ListenerTests.test_idle_blocks_without_periodic_timer_and_term_exits

    def test_only_status_and_probe_accepted(self):
        for action in ("TRACE", "START", "PAUSE", "HOLD", "RELEASE", "EXIT"):
            self.assertEqual(self.call(action), "REJECTED\n")
        self.assertEqual(self.call("UPDATE", extra=" " + "c" * 64), "REJECTED\n")
        self.assertFalse((self.p / "calls").exists())
        self.assertIn("STATUS 0", self.call("STATUS"))
        self.assertIn("PROBE 0", self.call("PROBE"))
        self.assertEqual((self.p / "calls").read_text().splitlines(),
                         ["STATUS", "PROBE", "STATUS"])
        self.assertFalse((self.r / "lease.ready").exists())


class BlinkListenerTests(ObserverListenerTests):
    additional_flags = ["-DDISPLAY_OBSERVER_ONLY", "-DDISPLAY_BLINK_CONTROL"]

    def test_only_status_and_probe_accepted(self):
        for action in ("TRACE", "START", "HOLD", "RELEASE", "EXIT", "RUN", "SHELL"):
            self.assertEqual(self.call(action), "REJECTED\n")
        self.assertIn("PAUSE 0", self.call("PAUSE"))
        self.assertEqual((self.p / "calls").read_text().splitlines(), ["PAUSE", "STATUS"])
        self.assertFalse((self.r / "lease.ready").exists())
