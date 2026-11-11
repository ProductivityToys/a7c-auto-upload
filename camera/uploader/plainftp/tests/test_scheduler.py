"""Execute the real shell scheduler against changing native snapshots.

Only media/time/transfer boundaries are simulated. Transport and receipt
validation run separately in test_worker with the real C implementations.
"""
import pathlib
import shlex
import subprocess
import tempfile
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1]


def row(number, size=24, stamp="2026-10-20T11:00:00"):
    return f"C{number:04d}.MP4 {size} C{number:04d}M01.XML 2176 {stamp} {stamp}"


class SchedulerTests(unittest.TestCase):
    def run_steps(self, steps, snapshot_times=None, expected_exit=42, checks=None, prelude="", epilogue=""):
        """Steps are (uptime, card, rows, gate_ok, attempt_result)."""
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            bb = d / "bb"
            bb.write_text("""#!/bin/sh
case "$1:$2" in
 cat:/proc/sys/kernel/random/boot_id) echo simulated-boot;;
 sleep:*) echo "$2" >> "$TEST_RAM/delays";;
 *) exec "$@";;
esac
""")
            bb.chmod(0o700)
            client = d / "plainftp"
            client.write_text("#!/bin/sh\ncase \"$1\" in namespace) echo test-namespace;; check) exit 0;; *) exit 90;; esac\n")
            client.chmod(0o700)
            if checks is not None:
                cases_check = ''.join(f'{i}) code={code};;' for i, code in enumerate(checks, 1))
                client.write_text('''#!/bin/sh
if [ "$1" = namespace ]; then echo test-namespace; exit 0; fi
[ "$1" = check ] || exit 90
n=$(cat "$TEST_RAM/check-count" 2>/dev/null); n=$((${n:-0}+1))
echo "$n" > "$TEST_RAM/check-count"
case "$n" in ''' + cases_check + f'*) code={checks[-1]};; esac\nexit "$code"\n')
            cases = []
            for index, (now, card, rows, ok, result) in enumerate(steps, 1):
                snapshot = d / f"snapshot-{index}"
                snapshot.write_text("".join(r + "\n" for r in rows))
                cases.append(
                    f"{index}) NOW={now}; SNAPSHOT_AT={now if snapshot_times is None else snapshot_times[index-1]}; CARD={shlex.quote(card)}; LETTER=A; "
                    f"attempt_result={result}; cp {shlex.quote(str(snapshot))} "
                    f"\"$D/plain.entries\"; return {0 if ok else 1};;"
                )
            source = (SRC / "worker.sh").read_text()
            functions = source[source.index("prune_rows() {"):source.index(
                "# Optional installation-only handshake")]
            script = f"""B={shlex.quote(str(bb))}
D={shlex.quote(str(d))}
HOST=127.0.0.1; PORT=21; USER=test; ROOT=/; STOP=0; step=0
export TEST_RAM="$D"
{functions}
uptime_seconds() {{ return 0; }}
log() {{ printf '%s\\n' "$1" >> "$D/events"; }}
cache_invalidate() {{ return 0; }}
media_poll() {{ media_gate; }}
usb_media_ready() {{ return 0; }}
scan_hold_start() {{ return 0; }}
scan_hold_stop() {{ return 0; }}
media_gate() {{
 step=$((step+1))
 case "$step" in
 {chr(10).join(cases)}
 *) STOP=1; return 1;;
 esac
}}
plain_attempt() {{
 printf '%s %s %s\\n' "$NOW" "$CARD" "$SOURCE_ROW" >> "$D/attempts"
 if [ "$attempt_result" = skip ]; then ATTEMPT_SKIPPED=1; return 0; fi
 if [ "$attempt_result" = dfail ]; then DISPLAY_FAILED=1; return 0; fi
 return "$attempt_result"
}}
{prelude}
plain_run; run_rc=$?
{epilogue}
exit $run_rc
"""
            p = subprocess.run(["sh"], input=script, text=True, capture_output=True, timeout=5)
            self.assertEqual(p.returncode, expected_exit, p.stderr)
            attempts = (d / "attempts").read_text().splitlines() if (d / "attempts").exists() else []
            delays = list(map(int, (d / "delays").read_text().splitlines())) if (d / "delays").exists() else []
            self.events=(d/"events").read_text() if (d/"events").exists() else ""
            self.known=(d/"plain.known").read_text().splitlines()
            self.checks=int((d/'check-count').read_text()) if (d/'check-count').exists() else None
            self.settle=(d/'settle').read_text().strip() if (d/'settle').exists() else None
            return attempts, delays

    def test_ftp_failure_blocks_sd_scan_then_recovers_without_worker_restart(self):
        a=row(1)
        attempts,delays=self.run_steps([(0,"card",[a],True,"skip"),(1,"card",[a],True,"skip")],checks=[75,75,0])
        self.assertEqual(attempts,["0 card "+a])
        self.assertEqual(delays[:2],[20,40])
        self.assertEqual(self.checks,3)
        self.assertEqual([x for x in self.events.splitlines() if x.startswith('FTP_HEALTH ')],['FTP_HEALTH error','FTP_HEALTH healthy'])

    def test_receipt_lookup_starts_on_first_available_snapshot(self):
        a=row(1)
        attempts,delays=self.run_steps([(0,"card",[a],True,"skip"),(1,"card",[a],True,0)])
        self.assertEqual(attempts,["0 card "+a]);self.assertEqual(delays[0],2)

    def test_first_snapshot_can_select_latest_before_older_receipts(self):
        a,b=row(1),row(9999,stamp="2026-10-21T12:00:00")
        attempts,_=self.run_steps([(0,"card",[b,a],True,"skip"),(1,"card",[b,a],True,"skip")])
        self.assertEqual(attempts,["0 card "+b,"1 card "+a])

    def test_unknown_snapshot_is_not_used_for_receipt_lookup(self):
        a=row(1)
        attempts,_=self.run_steps([(0,"card",[],False,0),(1,"card",[a],True,"skip")])
        self.assertEqual(attempts,["1 card "+a])

    def test_new_clip_preempts_remaining_backlog(self):
        a,b,c=row(1),row(2),row(3)
        attempts,_=self.run_steps([(0,"card",[a,b],True,"skip"),
            (1,"card",[c,b,a],True,"skip"),(2,"card",[c,b,a],True,"skip")])
        self.assertEqual(attempts,["0 card "+a,"1 card "+c,"2 card "+b])
        self.assertEqual(self.known,[a,b,c])

    def test_native_ftp_defers_photos_but_keeps_videos_and_resumes_photos(self):
        jpeg = "DCIM/100MSDCF/DSC00001.JPG 24 - 0 2026-10-20T11:00:00 -"
        raw = jpeg.replace(".JPG", ".ARW")
        video = row(1)
        steps = [(0, "card", [jpeg, raw, video], True, 0),
                 (1, "card", [jpeg, raw, video], True, 0),
                 (2, "card", [jpeg, raw, video], True, 0),
                 (3, "card", [jpeg, raw, video], True, 0)]
        attempts, _ = self.run_steps(steps, prelude="""
PAUSE_NATIVE_FTP=1
discovery_wait() { return 0; }
cat > "$D/discovery" <<'PROBE'
#!/bin/sh
[ "$2" = ftp-master ] || exit 90
n=$(cat "$TEST_RAM/native-reads" 2>/dev/null); n=$((${n:-0}+1))
echo "$n" > "$TEST_RAM/native-reads"
case "$n" in 1|2) echo on;; *) echo off;; esac
PROBE
chmod 700 "$D/discovery"
""")
        self.assertEqual(attempts, ["0 card " + video, "2 card " + jpeg, "3 card " + raw])
        self.assertIn("NATIVE_FTP_PHOTOS on", self.events)
        self.assertIn("NATIVE_FTP_PHOTOS off", self.events)

    def test_native_ftp_unknown_keeps_configured_photo_upload(self):
        photo = "DCIM/100MSDCF/DSC00001.JPG 24 - 0 2026-10-20T11:00:00 -"
        attempts, _ = self.run_steps([(0, "card", [photo], True, 0)],
                                     prelude="PAUSE_NATIVE_FTP=1; discovery_wait() { return 0; }")
        self.assertEqual(attempts, ["0 card " + photo])
        self.assertIn("NATIVE_FTP_PHOTOS unknown", self.events)

    def test_unchanged_success_survives_activity_unknown_gap_and_clock_rollback(self):
        a=row(1)
        for reset in [[(40,"card",[],False,0),(50,"card",[a],True,0)],
                      [(100,"card",[a],True,0)],[(0,"card",[a],True,0)]]:
            with self.subTest(reset=reset):
                attempts,_=self.run_steps([(10,"card",[a],True,"skip"),*reset])
                self.assertEqual(attempts,["10 card "+a])

    def test_changed_or_removed_row_is_rechecked(self):
        a=row(1)
        for changed in [row(1,25),row(1,stamp="2026-10-20T12:00:00")]:
            attempts,_=self.run_steps([(0,"card",[a],True,"skip"),(1,"card",[changed],True,"skip")])
            self.assertEqual(attempts,["0 card "+a,"1 card "+changed])
        attempts,_=self.run_steps([(0,"card",[a],True,"skip"),(1,"card",[],True,0),(2,"card",[a],True,"skip")])
        self.assertEqual(attempts,["0 card "+a,"2 card "+a])

    def test_card_switch_clears_successes_and_rechecks_current_rows(self):
        a,b=row(1),row(2)
        attempts,_=self.run_steps([(0,"card1",[a],True,"skip"),
            (1,"card2",[b,a],True,"skip"),(2,"card2",[b,a],True,"skip"),(3,"card1",[a],True,"skip")])
        self.assertEqual(attempts,["0 card1 "+a,"1 card2 "+b,"2 card2 "+a,"3 card1 "+a])

    def test_failures_keep_exponential_backoff_without_stability_rebuild(self):
        a,b=row(1),row(2)
        attempts,delays=self.run_steps([(0,"card",[a,b],True,1),
            (20,"card",[a,b],True,1),(60,"card",[a,b],True,0),
            (61,"card",[a,b],True,0),(62,"card",[a,b],True,0)])
        self.assertEqual([x.split()[2] for x in attempts],["C0001.MP4"]*3+["C0002.MP4"])
        self.assertEqual(delays[:3],[20,40,2])

    def test_source_wait_never_uses_or_inflates_network_backoff(self):
        a=row(1)
        attempts,delays=self.run_steps([(0,'card',[a],True,1),
            (20,'card',[a],True,75),(21,'card',[a],True,1),
            (61,'card',[a],True,0),(62,'card',[a],True,0)])
        self.assertEqual(len(attempts),4)
        self.assertEqual(delays[:4],[20,1,40,2])

    def test_unknown_native_completion_stops_the_batch(self):
        a=row(1)
        attempts,delays=self.run_steps([(0,"card",[a],True,90)],expected_exit=90)
        self.assertEqual(attempts,["0 card "+a]);self.assertEqual(delays,[])

    def test_successful_upload_and_receipt_skip_both_drain_without_extra_sleep(self):
        a,b=row(1),row(2)
        attempts,delays=self.run_steps([(0,"card",[a,b],True,"skip"),
            (1,"card",[a,b],True,0),(2,"card",[a,b],True,0)])
        self.assertEqual(attempts,["0 card "+a,"1 card "+b]);self.assertEqual(delays,[2,2])
        self.assertEqual(self.known,[a,b])

    def test_display_failure_stops_service_after_completing_the_file(self):
        a,b=row(1),row(2)
        attempts,delays=self.run_steps([(0,"card",[a,b],True,"dfail"),(1,"card",[a,b],True,0)],expected_exit=91)
        self.assertEqual(attempts,["0 card "+a])
        self.assertIn("SERVICE_EXIT display_failed",self.events)
        self.assertEqual(delays,[])

    def test_drained_queue_after_an_upload_shortens_settle_window(self):
        a,b=row(1),row(2)
        for result,expected in ((0,"17"),("skip","1000")):
            with self.subTest(result=result):
                self.run_steps([(0,"card",[a],True,"skip"),(10,"card",[b,a],True,result),(11,"card",[b,a],True,0)],
                               prelude='scan_hold_start() { SETTLE_UNTIL=1000; return 0; }',
                               epilogue='echo "$SETTLE_UNTIL" > "$D/settle"')
                # uptime_seconds is stubbed; NOW comes from the idle snapshot step (11 + 6).
                self.assertEqual(self.settle,expected)

    def test_quiet_fallback_does_not_repeat_successful_receipts(self):
        a=row(1)
        attempts,_=self.run_steps([(0,"card",[a],True,"skip"),
            (30,"card",[a],True,0),(60,"card",[a],True,0)])
        self.assertEqual(attempts,["0 card "+a]);self.assertEqual(self.events.splitlines().count("SCAN_DONE"),1)


class PruneBatchTests(unittest.TestCase):
    def test_grep_error_preserves_previous_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=pathlib.Path(tmp);(d/'checked').write_text(row(1)+'\n')
            (d/'plain.entries').write_text(row(2)+'\n')
            bb=d/'bb';bb.write_text('#!/bin/sh\n[ "$1" != grep ] || exit 2\nexec "$@"\n');bb.chmod(0o700)
            source=(SRC/'worker.sh').read_text()
            function=source[source.index('prune_rows() {'):source.index('\nscan_update() {')]
            p=subprocess.run(['sh'],input=f'D={shlex.quote(str(d))}; B={shlex.quote(str(bb))}\n'+function+'\nprune_rows "$D/checked"\n',text=True,capture_output=True,timeout=3)
            self.assertEqual(p.returncode,90)
            self.assertEqual((d/'checked').read_text(),row(1)+'\n')
            self.assertFalse((d/'checked.next').exists())

    def test_large_intersection_uses_one_grep_and_preserves_exact_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=pathlib.Path(tmp)
            current=[row(i) for i in range(1,501)]
            (d/'plain.entries').write_text('\n'.join(current)+'\n')
            # Includes an obsolete size, removed file, and an exact duplicate.
            (d/'checked').write_text('\n'.join(current[::2]+[row(2,size=25),row(700),current[0]])+'\n')
            bb=d/'bb';bb.write_text('#!/bin/sh\necho "$1" >> "'+str(d/'calls')+'"\nexec "$@"\n');bb.chmod(0o700)
            source=(SRC/'worker.sh').read_text()
            function=source[source.index('prune_rows() {'):source.index('\nscan_update() {')]
            script=f'D={shlex.quote(str(d))}; B={shlex.quote(str(bb))}\n'+function+'\nprune_rows "$D/checked"\n'
            p=subprocess.run(['sh'],input=script,text=True,capture_output=True,timeout=3)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual((d/'checked').read_text().splitlines(),current[::2]+[current[0]])
            self.assertEqual((d/'calls').read_text().splitlines(),['grep','mv'])
            (d/'plain.entries').write_text('')
            p=subprocess.run(['sh'],input=script,text=True,capture_output=True,timeout=3)
            self.assertEqual(p.returncode,0,p.stderr);self.assertEqual((d/'checked').read_text(),'')
            # Do not invoke the camera's match-all empty-pattern behavior.
            self.assertEqual((d/'calls').read_text().splitlines(),['grep','mv'])
            (d/'plain.entries').write_text(current[0]+'\n')
            p=subprocess.run(['sh'],input=script,text=True,capture_output=True,timeout=3)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual((d/'calls').read_text().splitlines(),['grep','mv'])



class SelectionBatchTests(unittest.TestCase):
    def run_selection(self, entries, checked, known, fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            d=pathlib.Path(tmp)
            for name, rows in [('entries',entries),('checked',checked),('known',known)]:
                (d/('plain.'+name)).write_text(''.join(r+'\n' for r in rows))
            bb=d/'bb';bb.write_text('#!/bin/sh\necho "$1" >> "$TEST_RAM/calls"\n'+('if [ "$1" = grep ]; then exit 2; fi\n' if fail else '')+'exec "$@"\n');bb.chmod(0o700)
            source=(SRC/'worker.sh').read_text();functions=source[source.index('rows_missing_from() {'):source.index('plain_run() {')]
            script=f'D={shlex.quote(str(d))}; B={shlex.quote(str(bb))}\n'+functions+'\nchoose_row; rc=$?; printf "%s\\n%s\\n%s\\n" "$rc" "$priority" "$chosen"\n'
            p=subprocess.run(['sh'],input=script,text=True,capture_output=True,env=dict(__import__('os').environ,TEST_RAM=str(d)),timeout=3)
            self.assertEqual(p.returncode,0,p.stderr)
            return p.stdout.splitlines(),(d/'calls').read_text().splitlines() if (d/'calls').exists() else []
    def test_large_known_backlog_uses_two_differences_and_latest_fallback(self):
        rows=[row(i) for i in range(500,0,-1)]
        result,calls=self.run_selection(rows,rows[:1],rows)
        self.assertEqual(result,['0','recheck',rows[1]])
        self.assertEqual(calls.count('grep'),2)
    def test_new_file_preempts_unchecked_older_files_without_dropping_them(self):
        old,new=row(1),row(2)
        result,_=self.run_selection([new,old],[],[old]);self.assertEqual(result,['0','new_or_changed',new])
        result,_=self.run_selection([new,old],[new],[new,old]);self.assertEqual(result,['0','recheck',old])
    def test_empty_sets_are_explicit_and_all_checked_is_idle(self):
        old=row(1)
        result,calls=self.run_selection([old],[],[]);self.assertEqual(result,['0','new_or_changed',old]);self.assertNotIn('grep',calls)
        result,_=self.run_selection([old],[old],[old]);self.assertEqual(result,['0','recheck',''])
    def test_difference_error_never_selects_a_row(self):
        old=row(1);result,_=self.run_selection([old],[row(2)],[old],fail=True)
        self.assertEqual(result[0],'90');self.assertEqual(result[2],'')


if __name__ == "__main__":
    unittest.main()
