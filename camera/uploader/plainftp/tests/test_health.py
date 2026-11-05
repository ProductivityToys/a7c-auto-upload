"""Health failures affect scheduling/indicator, never video or SD contents."""
from pathlib import Path
import os, re, subprocess, tempfile, unittest

SOURCE = Path(__file__).resolve().parents[1] / 'worker.sh'


class HealthTests(unittest.TestCase):
    def run_shell(self, body):
        functions = ''
        for name in ('ftp_health_mark', 'ftp_health_ready'):
            functions += re.search(r'^' + name + r'\(\) \{\n.*?^}\n', SOURCE.read_text(), re.M | re.S)[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            functions=functions.replace('/sys/class/net/wlan0/ifindex',str(root/'link-index')).replace('/proc/uptime',str(root/'uptime'))
            (root/'uptime').write_text('100.0 0.0\n')
            (root/'link-index').write_text('35\n')
            functions=functions.replace('/setting/a7c-debug/ram/dds-once/native-service',str(root/'native'))
            (root / 'bb').write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; *) exec "$@";; esac\n')
            (root / 'bb').chmod(0o700)
            (root / 'plainftp').write_text('''#!/bin/sh
case "$1" in check|check-fast) ;; *) exit 99;; esac
read password
[ "$password" = only-test-secret ] || exit 99
echo check >> "$TEST_RAM/checks"
echo "$1" >> "$TEST_RAM/check-modes"
if [ -f "$TEST_RAM/advance" ]; then
 read now rest < "$TEST_RAM/uptime"
 advance=$(cat "$TEST_RAM/advance")
 echo "$(( ${now%.*} + advance )).0 0.0" > "$TEST_RAM/uptime"
fi
exit "$(cat "$TEST_RAM/return")"
''')
            (root / 'plainftp').chmod(0o700)
            (root / 'return').write_text('75\n')
            script = f'D={root}\nB=$D/bb\nexport TEST_RAM=$D\n' + functions + '''
HOST=127.0.0.1; PORT=21; USER=test; ROOT=/; FTP_PASSWORD=only-test-secret; FTP_LINK=35
log() { echo "$*" >> "$D/events"; }
''' + body
            result = subprocess.run(['sh', '-e'], input=script, text=True, capture_output=True, timeout=5, env=os.environ.copy())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            files={p.name:p.read_text() for p in root.iterdir() if p.is_file()}
            files['health_events']=''.join(x+'\n' for x in files['events'].splitlines() if x.startswith('FTP_HEALTH '))
            return files

    def test_failure_marks_once_and_retry_increases_to_two_minutes(self):
        files = self.run_shell('''
for expected in 20 40 80 120 120 120 120; do
 if ftp_health_ready; then exit 99; fi
 [ "$FTP_HEALTH_DELAY" = "$expected" ]
done
[ "$(cat "$D/ftp-health")" = error ]
''')
        self.assertEqual(files['checks'].splitlines(), ['check'] * 7)
        self.assertEqual(files['health_events'], 'FTP_HEALTH error\n')

    def test_recovery_clears_mark_and_idle_does_not_repeat_probe(self):
        files = self.run_shell('''
if ftp_health_ready; then exit 99; fi
echo 0 > "$D/return"
ftp_health_ready
[ "$FTP_HEALTH" = healthy ] && [ "$FTP_CHECK_BACKOFF" = 10 ]
ftp_health_ready; ftp_health_ready
''')
        self.assertEqual(files['checks'].splitlines(), ['check', 'check'])
        self.assertEqual(files['ftp-health'], 'healthy\n')
        self.assertEqual(files['health_events'], 'FTP_HEALTH error\nFTP_HEALTH healthy\n')

    def test_wake_requests_fresh_check_even_after_prior_success(self):
        files = self.run_shell('''
echo 0 > "$D/return"; ftp_health_ready
FTP_CHECK_DUE=1; echo 75 > "$D/return"
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH" = error ]
''')
        self.assertEqual(files['checks'].splitlines(), ['check', 'check'])

    def test_network_generation_change_forces_one_check_without_clock_hint(self):
        files=self.run_shell('''
echo 0 > "$D/return"; ftp_health_ready
ftp_health_ready
echo 36 > "$D/link-index"; echo 75 > "$D/return"
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH" = error ] && [ "$FTP_LINK" = 36 ] && [ "$FTP_HEALTH_DELAY" = 1 ]
''')
        self.assertEqual(files['checks'].splitlines(),['check','check'])
        self.assertIn('FTP_LINK_CHANGED 35->36',files['events'])

    def test_connecting_window_is_time_based_not_failure_count(self):
        files=self.run_shell('''
unset FTP_LINK
for now in 100 101 102 103 104 105 106 107 108 109; do
 echo "$now.0 0.0" > "$D/uptime"
 if ftp_health_ready; then exit 99; fi
 [ "$FTP_HEALTH_DELAY" = 1 ] || exit 98
done
echo '110.0 0.0' > "$D/uptime"
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH_DELAY" = 20 ] || exit 97
echo '111.0 0.0' > "$D/uptime"
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH_DELAY" = 40 ] || exit 96
''')
        self.assertEqual(files['checks'].splitlines(),['check']*12)
        self.assertEqual(files['check-modes'].splitlines(),['check-fast']*10+['check']*2)
        self.assertEqual(files['health_events'],'FTP_HEALTH error\n')

    def test_slow_failed_connections_consume_the_same_bounded_window(self):
        files=self.run_shell('''
unset FTP_LINK; echo 4 > "$D/advance"
for expected in 1 1 20; do
 if ftp_health_ready; then exit 99; fi
 [ "$FTP_HEALTH_DELAY" = "$expected" ] || exit 98
done
[ "$FTP_LINK_FAST_UNTIL" = 0 ] || exit 97
''')
        self.assertEqual(files['checks'].splitlines(),['check']*3)
        self.assertEqual(files['check-modes'].splitlines(),['check-fast']*3)
        self.assertIn('FTP_CHECK rc=75 start=100.0 end=104.0',files['events'])

    def test_success_ends_fast_retries_until_next_network_generation(self):
        files=self.run_shell('''
unset FTP_LINK
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH_DELAY" = 1 ] || exit 98
echo 0 > "$D/return"; ftp_health_ready
[ "$FTP_LINK_FAST_UNTIL" = 0 ] || exit 97
FTP_CHECK_DUE=1; echo 75 > "$D/return"
if ftp_health_ready; then exit 99; fi
[ "$FTP_HEALTH_DELAY" = 20 ] || exit 96
''')
        self.assertEqual(files['checks'].splitlines(),['check']*3)
        self.assertEqual(files['check-modes'].splitlines(),['check-fast','check-fast','check'])

    def test_delayed_display_binding_receives_cached_health_without_new_ftp_probe(self):
        files=self.run_shell('''
echo 0 > "$D/return"; ftp_health_ready
mkdir "$D/native"
printf '#!/bin/sh\necho "$1" >> "$TEST_RAM/display-calls"\n' > "$D/native/probe"
chmod 700 "$D/native/probe"
echo 42 > "$D/native/im.pid"; echo 1 > "$D/native/owner"
ftp_health_ready
echo $$ > "$D/native/owner"
ftp_health_ready; ftp_health_ready
''')
        self.assertEqual(files['checks'].splitlines(),['check'])
        self.assertEqual(files['display-calls'].splitlines(),['--service-healthy'])
