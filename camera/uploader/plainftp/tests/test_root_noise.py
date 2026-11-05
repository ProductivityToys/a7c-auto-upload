"""An unreadable SD root listing must be retried, never stop the worker."""
from pathlib import Path
import re, subprocess, tempfile, unittest

SRC = Path(__file__).resolve().parents[1]


class RootNoiseTests(unittest.TestCase):
    def run_load(self, exists_codes, body='receipt_load; echo "rc=$?"'):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'codes').write_text(''.join(f'{c}\n' for c in exists_codes))
            stubs = {
                'sd-monitor': 'echo root >> "$D/calls"; echo listing',
                'plainftp': 'case "$1" in slot) echo CFA800;; match-row) exit 10;; esac',
                'local-media': 'n=$(cat "$D/n" 2>/dev/null); n=$((${n:-0}+1)); echo $n > "$D/n"; '
                               'code=$(sed -n "${n}p" "$D/codes"); [ -n "$code" ] || code=$(tail -1 "$D/codes"); exit $code',
            }
            for name, text in stubs.items():
                (d / name).write_text('#!/bin/sh\nD=' + str(d) + '\n' + text + '\n'); (d / name).chmod(0o700)
            src = (SRC / 'worker.sh').read_text()
            funcs = ''.join(re.search(r'^' + n + r'\(\) \{\n.*?^}\n', src, re.M | re.S)[0]
                            for n in ('receipt_root_fresh', 'receipt_root', 'receipt_load'))
            script = f'''D={d}; B=; DRIVE=A; HOST=h; PORT=21; USER=u; ROOT=/; IDENTITY=x; SIZE=1; CARD=c
log() {{ echo "$1" >> "$D/events"; }}
timed() {{ shift; "$@"; }}
uptime_seconds() {{ NOW=100; }}
{funcs}
{body}
'''
            p = subprocess.run(['sh'], input=script, capture_output=True, text=True, timeout=5)
            events = (d / 'events').read_text().split('\n') if (d / 'events').exists() else []
            calls = (d / 'calls').read_text().count('root') if (d / 'calls').exists() else 0
            return p.stdout.strip(), [e for e in events if e], calls

    def test_noise_rereads_root_once_then_succeeds(self):
        out, events, roots = self.run_load([75, 10, 10])
        self.assertEqual(out, 'rc=10')
        self.assertEqual(events, ['SD_ROOT_UNREADABLE retry=fresh'])
        self.assertEqual(roots, 2)

    def test_persistent_noise_is_retryable_not_fatal(self):
        out, events, roots = self.run_load([75])
        self.assertEqual(out, 'rc=75')
        self.assertEqual(events, ['SD_ROOT_UNREADABLE retry=fresh', 'SD_ROOT_UNREADABLE'])
        self.assertEqual(roots, 2)

    def test_genuine_conflict_still_stops(self):
        self.assertEqual(self.run_load([90])[0], 'rc=90')

    def test_attempt_and_receipt_store_map_noise_to_backoff_code(self):
        src = (SRC / 'worker.sh').read_text()
        self.assertIn('    75) result=76;;', src)
        self.assertIn('[ "$receipt_rc" != 75 ] || return 76', src)
        # plain_run treats any code other than 0/75/90 as backoff-and-retry.
        run = re.search(r'^plain_run\(\) \{\n.*?^}\n', src, re.M | re.S)[0]
        self.assertIn('*) backoff=$((backoff*2)); delay=$backoff;;', run)


if __name__ == '__main__':
    unittest.main()
