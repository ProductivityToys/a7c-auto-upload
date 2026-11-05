"""Host tests for the read-only Wi-Fi diagnostic listener."""
from pathlib import Path
import hashlib, hmac, os, signal, socket, subprocess, tempfile, time, unittest

SRC = Path(__file__).resolve().parents[1]
TOKEN = 'ab' * 32


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class ListenerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.root, self.ram = d / 'root', d / 'ram'
        self.root.mkdir(); self.ram.mkdir()
        (self.root / 'token').write_text(TOKEN + '\n')
        (self.root / 'enabled').write_text('a7c-diag-v1\n')
        (self.root / 'diag.sh').write_text('echo "ran $1"; echo "$1" >> "' + str(d / 'calls') + '"; [ "$1" != PROBE ] || exit 3\n')
        self.port = free_port()
        exe = d / 'listener'
        subprocess.run(['cc', '-O1', f'-DROOT="{self.root}"', f'-DRAM="{self.ram}"', '-DSHELL="/bin/sh"',
                        f'-DPORT={self.port}', '-DACTION_TIMEOUT_MS=3000', str(SRC / 'listener.c'), '-o', str(exe)],
                       check=True)
        self.proc = subprocess.Popen([str(exe)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', self.port), timeout=.2).close()
                break
            except OSError:
                time.sleep(.05)
        self.calls = d / 'calls'

    def tearDown(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        self.proc.stdout.close()
        self.tmp.cleanup()

    def request(self, verb, seq=None, key=TOKEN, mac=None, line=None):
        with socket.create_connection(('127.0.0.1', self.port), timeout=5) as s:
            f = s.makefile('rb')
            greeting = f.readline().decode().split()
            self.assertEqual(greeting[0], 'A7CDIAG1')
            nonce, current = greeting[1], int(greeting[2])
            seq = current + 1 if seq is None else seq
            if line is None:
                msg = f'A7CDIAG1 {nonce} {seq} {verb}'.encode()
                mac = mac or hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()
                line = f'{verb} {seq} {mac}\n'
            s.sendall(line.encode())
            return f.read().decode()

    def test_authenticated_verbs_run_fixed_script(self):
        for verb in ('STATUS', 'TRACE'):
            reply = self.request(verb)
            self.assertTrue(reply.startswith('RESULT '), reply)
            self.assertIn(f' {verb} 0\nran {verb}\n', reply)
        self.assertIn(' PROBE 3\n', self.request('PROBE'))
        self.assertEqual(self.calls.read_text().split(), ['STATUS', 'TRACE', 'PROBE'])

    def test_wrong_key_replay_unknown_verb_and_garbage_are_rejected(self):
        self.assertEqual(self.request('STATUS', key='cd' * 32), 'REJECTED\n')
        self.assertTrue(self.request('STATUS').startswith('RESULT 1 '))
        self.assertEqual(self.request('STATUS', seq=1), 'REJECTED\n')   # replayed sequence
        self.assertEqual(self.request('STATUS', seq=3), 'REJECTED\n')   # skipped sequence
        self.assertEqual(self.request('STOP'), 'REJECTED\n')
        self.assertEqual(self.request('UPDATE'), 'REJECTED\n')
        self.assertEqual(self.request('STATUS', mac='A' * 64), 'REJECTED\n')
        self.assertEqual(self.request(None, line='STATUS 2 ' + 'a' * 63 + '\n'), 'REJECTED\n')
        self.assertEqual(self.request(None, line='STATUS 02 ' + 'a' * 64 + '\n'), 'REJECTED\n')
        self.assertEqual(self.request(None, line='; sh 2 ' + 'a' * 64 + '\n'), 'REJECTED\n')
        self.assertTrue(self.request('STATUS').startswith('RESULT 2 '))
        self.assertEqual(self.calls.read_text().split(), ['STATUS', 'STATUS'])

    def test_idle_listener_does_not_wake_and_exits_on_term_or_disable(self):
        before = self.ctx()
        time.sleep(1.5)
        if before is not None:
            self.assertEqual(self.ctx(), before)
        self.proc.send_signal(signal.SIGTERM)
        self.assertEqual(self.proc.wait(timeout=3), 0)
        self.assertIn(b'DIAG_EXIT stop=1', self.proc.stdout.read())
        self.assertFalse((self.ram / 'listener.pid').exists())

    def test_removed_pairing_stops_on_next_wake(self):
        (self.root / 'enabled').unlink()
        try:
            self.request('STATUS')
        except (OSError, IndexError):
            pass
        self.assertEqual(self.proc.wait(timeout=3), 0)

    def ctx(self):
        # Linux only: voluntary context switches stay constant when idle.
        status = Path(f'/proc/{self.proc.pid}/status')
        if not status.exists():
            return None
        return [l for l in status.read_text().splitlines() if 'ctxt_switches' in l]


if __name__ == '__main__':
    unittest.main()
