"""Bounded local readiness waiting; never launches a native camera frontend."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
SRC=Path(__file__).resolve().parents[1]
class MonitorReadyTests(unittest.TestCase):
 def test_ready_delay_dead_process_timeout_and_strict_arguments(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);binary=d/'monitor'
   subprocess.run(['cc','-fno-builtin','-DA7C_MONOTONIC_CLOCK='+str(time.CLOCK_MONOTONIC),'-DA7C_READY_DIR="'+str(d)+'"','-DA7C_READY_LEASE_MS=400U','-DA7C_READY_RELAY_MS=400U',str(SRC/'monitor.c'),'-o',str(binary)],check=True)
   def call(kind,pid):return subprocess.run([str(binary),'wait-ready',kind,str(pid)],capture_output=True,timeout=2).returncode
   for kind in ['lease','relay']:
    timer=threading.Timer(.12,lambda:(d/(kind+'.ready')).touch());timer.start();start=time.monotonic()
    self.assertEqual(call(kind,os.getpid()),0);elapsed=time.monotonic()-start;timer.join();self.assertLess(elapsed,.8);self.assertGreaterEqual(elapsed,.1)
    (d/(kind+'.ready')).unlink();self.assertEqual(call(kind,os.getpid()),124)
   self.assertEqual(call('lease',99999999),72)
   for kind,pid in [('other',os.getpid()),('lease','12x'),('lease',1),('lease','9999999999')]:self.assertEqual(call(kind,pid),64)
if __name__=='__main__':unittest.main()
