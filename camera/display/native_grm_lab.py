#!/usr/bin/env python3
"""Execute original DDS/GRM wrappers with simulated boundaries, OFFLINE ONLY.

Reuses the private output of native_text_lab.py. Does not contact the camera,
drive graphics hardware, or prove framebuffer ownership. No firmware is bundled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from audit_ui_contract import Image, IMAGES

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--research', type=Path, required=True)
p.add_argument('--font-lab', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
research, lab, output = (x.resolve() for x in (a.research, a.font_lab, a.output))
# The lab's copied library must differ from the pinned source ONLY by the exact
# dynamic initialization metadata edits made by native_text_lab.py.
image = Image(research / IMAGES['obj'][0], IMAGES['obj'][1])
try:
    expected = bytearray((research / IMAGES['obj'][0]).read_bytes())
    import struct
    dynamic = image.elf.get_section_by_name('.dynamic')
    for i, tag in enumerate(dynamic.iter_tags()):
        if tag.entry.d_tag in ('DT_INIT', 'DT_FINI'):
            struct.pack_into('<II', expected, dynamic['sh_offset']+8*i, 21, 0)
        if tag.entry.d_tag in ('DT_INIT_ARRAYSZ', 'DT_FINI_ARRAYSZ'):
            struct.pack_into('<I', expected, dynamic['sh_offset']+8*i+4, 0)
    if (lab/'libObj.so').read_bytes() != expected:
        raise ValueError('Lab library does not match the pinned offline copy')
finally:
    image.stream.close()
if not json.loads((lab/'result.json').read_text()).get('passed'):
    raise ValueError('Requires a successful native text lab')
output.mkdir(parents=True, mode=0o700, exist_ok=False)
here = Path(__file__).resolve().parent
cc = ['/opt/homebrew/opt/llvm/bin/clang', '--target=arm-linux-gnueabi',
      '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft', '-Os', '-fPIC',
      '-fno-stack-protector', '-fno-builtin', '-nostdlib', '-c']
fixture = here/'tests/native_grm_arm_fixture.c'
for src, obj in [(fixture, 'fixture.o'), (here.parents[1]/'maintenance/startup.S', 'startup.o')]:
    subprocess.run(cc+[str(src), '-o', str(output/obj)], check=True)
env = os.environ.copy()
env['DYLD_LIBRARY_PATH'] = str(research/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
subprocess.run([str(research/'tools/lld21/lld'), '-flavor', 'gnu', '-m', 'armelf_linux_eabi',
                '--hash-style=sysv', '-z', 'nocombreloc', '--dynamic-linker=/lab/ld.so',
                '-e', '_start', str(output/'startup.o'), str(output/'fixture.o'),
                str(lab/'libc.so.6'), str(lab/'libdl.so.2'), str(lab/'libgcc_s.so.1'),
                '-o', str(output/'fixture')], env=env, check=True)
(output/'fixture').chmod(0o755)
container = 'a7c-grm-lab-'+uuid.uuid4().hex[:12]
cmd = ['docker', 'run', '--rm', '--init', '--pull', 'never', '--name', container,
       '--platform', 'linux/arm/v7', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
       '--security-opt', 'no-new-privileges', '--memory', '256m', '--cpus', '1',
       '--pids-limit', '32', '--ulimit', 'core=0',
       '--mount', f'type=bind,src={lab},dst=/lab,readonly',
       '--mount', f'type=bind,src={output},dst=/probe,readonly',
       '--entrypoint', '/lab/ld.so',
       'alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc',
       '--library-path', '/lab', '/probe/fixture']
try:
    result = subprocess.run(cmd, capture_output=True, timeout=20)
except subprocess.TimeoutExpired:
    subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL)
    raise
stdout = result.stdout.decode(errors='replace')
report = {
    'scope': 'Offline original wrapper execution; target bitmap, locking, reference operations and driver submission simulated. No real compositor, pixels, camera or live hook.',
    'source_sha256': IMAGES['obj'][1],
    'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
    'original_executed_wrappers': ['0x68d13c', '0x7db518'],
    'simulated_boundaries': ['0x75ccf4', '0x75cce4', '0x75cca4', '0x68dc48', '0x68dc58',
                             'GRM_bitmapGetSubRectangle', 'GRM_gpermRectblit'],
    'exit': result.returncode, 'stdout': stdout, 'stderr': result.stderr.decode(errors='replace'),
    'passed': result.returncode == 0 and 'A7C_NATIVE_GRM_BOUNDARY_OK 5' in stdout,
}
(output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
print(stdout)
print(output/'result.json')
if not report['passed']:
    raise SystemExit('Offline GRM boundary experiment failed')
