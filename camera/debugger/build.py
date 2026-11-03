"""Build debug-only variants against the exact camera ABI; binaries stay on external disk."""
from pathlib import Path
import subprocess,os,json,hashlib
from elftools.elf.elffile import ELFFile
src=Path(__file__).resolve().parent.parent/'uploader'
r=Path('/Volumes/ExtWorkspace/a7c-ftp-research/tools');out=r/'debug-build';out.mkdir(exist_ok=True)
env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(r/'lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
manifest={}
for name,source,flags in [('launcher','launcher',['-DPROBE_DIR="/setting/a7c-debug"','-DCLAIM_FILE="/tmp_network/a7c-debug.claim"']),('live','launcher',['-DPROBE_DIR="/setting/a7c-debug"','-DCLAIM_FILE="/tmp_network/a7c-debug.claim"','-DMAX_UPTIME=100000000']),('listener','../debugger/listener',[]),('probe','monitor',['-DDEBUG_STATE_ONLY']),('net','net',['-DFTP_PORT="21215"']),('lease','lease',['-DLEASE_DIR="/setting/a7c-debug/ram"','-DLEASE_NO_DUMP'])]:
 obj=out/(name+'.o');binary=out/(name+('.so' if name in ('launcher','live') else '.elf'))
 shared=name in ('launcher','live')
 subprocess.run(['/opt/homebrew/opt/llvm/bin/clang','--target=arm-linux-gnueabi','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fno-stack-protector','-fno-builtin','-fPIC' if shared else '-fno-pic','-nostdlib',*flags,'-c',str(src/(source+'.c')),'-o',str(obj)],check=True)
 common=[str(r/'lld21/lld'),'-flavor','gnu','-m','armelf_linux_eabi','--hash-style=sysv','-z','noexecstack']
 if shared:args=['-shared','-z','defs','-init=worker_init',str(obj)]
 else:
  deps=[str(r.parent/'evidence/camera-2.00-boot/lib__libc-2.11.2.so'),str(r.parent/'evidence/camera-2.00-boot/lib__librt-2.11.2.so')]
  if name=='lease':deps.insert(0,str(r.parent/'evidence/camera-2.00-power/usr__lib__libosal_uipc.so'))
  args=['--dynamic-linker=/lib/ld-linux.so.3','--allow-shlib-undefined','-e','_start',str(r/'a7c_probe_start.S.o'),str(obj),*deps]
 subprocess.run(common+args+['-o',str(binary)],env=env,check=True)
 with binary.open('rb') as f:
  elf=ELFFile(f);assert elf['e_machine']=='EM_ARM'
  if shared:
   assert not any(t.entry.d_tag in ('DT_NEEDED','DT_TEXTREL') for t in elf.get_section_by_name('.dynamic').iter_tags())
   assert elf.get_section_by_name('.dynsym').num_symbols()==1
 manifest[name]={'bytes':binary.stat().st_size,'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'flags':flags}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
