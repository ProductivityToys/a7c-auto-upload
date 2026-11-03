#!/usr/bin/env python3
"""Run built text module against the private offline native font runtime only."""
import sys
import argparse,hashlib,json,os,subprocess,uuid,tarfile,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('research','runtime','build','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--archive-input',action='store_true',help='Stream lab inputs into private container tmpfs instead of Docker host bind mounts')
p.add_argument('--bitmap',action='store_true',help='Also execute native owned-buffer bitmap wrapper, offline only')
p.add_argument('--managed',action='store_true',help='Original DDS allocation/free with simulated bitmap memory boundaries')
p.add_argument('--compose',action='store_true',help='Two owned bitmaps; blit and memory boundaries simulated')
p.add_argument('--shared-pool',action='store_true',help='Two private bitmaps in one simulated pool')
p.add_argument('--small-pool',action='store_true',help='Two small private bitmaps in one simulated pool')
p.add_argument('--release-contract',action='store_true',help='Actual native release wrapper with a synthetic retained object; no driver calls')
p.add_argument('--submit-contract',action='store_true',help='Actual DDS submit wrapper, intercepted display/GRM boundaries; no device access')
p.add_argument('--render-contract',action='store_true',help='Original blend selection and command result forwarding; intercepted graphics boundaries')
p.add_argument('--progress-frame',action='store_true',help='Native TextRM + single-source progress frame, simulated front/GPU; offline only')
p.add_argument('--frame-callback-contract',action='store_true',help='Native scene/post-draw ordering; synthetic backend only, no live hook')
p.add_argument('--event-module-contract',action='store_true',help='Actual one-shot event DSO and native dispatch; synthetic objects only')
p.add_argument('--gain-module-contract',action='store_true',help='Actual one-shot gain DSO and native dispatch; original gain intercepted')
p.add_argument('--present-module-contract',action='store_true',help='Actual one-shot post-present DSO; native dispatch and synthetic pixels, no GPU')
p.add_argument('--sync-contract',action='store_true',help='Native finite fence wait/destroy; synthetic registry and condition wait, no GPU')
p.add_argument('--dds-refresh-contract',action='store_true',help='Original DDS refresh and actual native font with one-frame cache; render boundary intercepted, offline only')
p.add_argument('--dds-import-contract',action='store_true',help='Actual passive GOT observer DSO and native DDS calls; no GPU/camera')
a=p.parse_args();r=a.research.resolve();runtime=a.runtime.resolve();build=a.build.resolve();out=a.output.resolve()
if a.gain_module_contract or a.present_module_contract:
    if a.event_module_contract or (a.gain_module_contract and a.present_module_contract):p.error('Choose only one module contract')
    a.event_module_contract=True
contract=a.release_contract or a.submit_contract or a.render_contract or a.progress_frame or a.frame_callback_contract or a.event_module_contract or a.sync_contract or a.dds_refresh_contract or a.dds_import_contract
if contract and (any((a.bitmap,a.managed,a.compose,a.shared_pool,a.small_pool)) or sum((a.release_contract,a.submit_contract,a.render_contract,a.progress_frame,a.frame_callback_contract,a.event_module_contract,a.sync_contract,a.dds_refresh_contract,a.dds_import_contract))>1):
    p.error('Contract experiments are standalone')
if a.small_pool:a.shared_pool=True
if a.shared_pool:a.compose=True
if a.compose:a.managed=True
manifest=json.loads((build/'manifest.json').read_text())
if hashlib.sha256((build/'marker.so').read_bytes()).hexdigest()!=manifest['binaries']['marker.so']:
    raise ValueError('Module hash mismatch')
out.mkdir(parents=True,exist_ok=False,mode=0o700)
here=Path(__file__).resolve().parent
env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(r/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
cc=['/opt/homebrew/opt/llvm/bin/clang','--target=arm-linux-gnueabi','-mcpu=cortex-a9','-marm',
    '-mfloat-abi=soft','-Os','-fPIC','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror','-c']
fixture=here.parent/'tests/native_text_module_fixture.c'
verified_ranges=[]
if contract:
    fixture=here.parent/'tests'/('native_bitmap_release_fixture.c' if a.release_contract else 'native_render_contract_fixture.c' if a.render_contract else 'native_dds_submit_fixture.c')
    if a.progress_frame:fixture=here.parent/'tests/native_progress_frame_fixture.c'
    if a.frame_callback_contract:fixture=here.parent/'tests/native_frame_callback_fixture.c'
    if a.event_module_contract:fixture=here.parent/'tests/native_event_module_fixture.c'
    if a.gain_module_contract:fixture=here.parent/'tests/native_gain_module_fixture.c'
    if a.present_module_contract:fixture=here.parent/'tests/native_present_module_fixture.c'
    if a.sync_contract:fixture=here.parent/'tests/native_present_sync_fixture.c'
    if a.dds_refresh_contract:fixture=here.parent/'tests/native_dds_refresh_fixture.c'
    if a.dds_import_contract:fixture=here.parent/'tests/native_dds_import_fixture.c'
    from elftools.elf.elffile import ELFFile
    def native_bytes(path,start,size):
        with path.open('rb') as stream:
            elf=ELFFile(stream)
            for segment in elf.iter_segments():
                if segment['p_type']=='PT_LOAD' and segment['p_vaddr']<=start and start+size<=segment['p_vaddr']+segment['p_filesz']:
                    stream.seek(segment['p_offset']+start-segment['p_vaddr'])
                    return stream.read(size)
        raise ValueError('Native range outside file')
    original=r/'evidence/camera-2.00-obj/usr__lib__libObj.so'
    if hashlib.sha256(original.read_bytes()).hexdigest()!='ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd':
        raise ValueError('Original native image mismatch')
    ranges=((0x68dc58,16),(0x68d920,12),(0x6b8c18,60),(0x6b76e8,124),(0x6b7764,4)) if a.release_contract else ((0x68d13c,0x11c),(0x7db394,0x82),(0x7db4a0,0x78))
    if a.render_contract:ranges=((0x7d2090,0x1000),(0x68bc04,0xa4))
    if a.progress_frame:
        # Exact copied font runtime, allowing only the runtime's documented lab
        # relocation/loader edits; frame uses the same rasterizer as --managed.
        ranges=((0x7db2d0,0xd0),(0x7db568,0x40),(0x57d270,0x30))
    if a.frame_callback_contract:ranges=((0x61805a,30),(0x6180d6,0x36),(0x61819c,0x62),(0x61810c,0x1a),(0x61f134,12),(0x7ec744,0x38),(0x7ec70c,0x38),(0x7eafba,14),(0x7eafac,14),(0x7e3a58,0x5c),(0x7e375c,0x58),(0x13b68c0,0x34),(0x13b6648,0x34),(0x89f58c,0x158),(0x350064,8),(0x3ef544,0x44),(0x66de3c,24),(0x66dc04,0x44),(0x7ec7f0,0x38),(0x7e6934,0x78))
    if a.frame_callback_contract:ranges+=((0x672300,0x6c),(0x671b4c,0x150),
        (0x13b68c0,0x140),(0x7ec32c,10),(0x7ecdd2,0x60),
        (0x7ed1ee,0xd0),(0x7efee2,14),(0x802896,0x3e6),
        (0x8069cc,0x2c),(0x809dc0,0x500),(0x800000,0x1000),
        (0x807252,0xd00))
    if a.frame_callback_contract:ranges+=((0x7e4a94,0x91c),(0x7e59b0,0x184),
        (0x7ecf9c,0x5c),(0x7ed1d4,0x1a),(0x802e10,0x30),(0x7eef6c,0x40),(0x7f046c,0x10))
    if a.frame_callback_contract:ranges+=((0x7ec828,0xb8),(0x7ed150,0x84),(0x7ec514,0x128),(0x7ed0cc,0x84),(0x7eaefc,0x38))
    if a.frame_callback_contract and manifest.get('rect_trial'):ranges+=((0x675278,16),)
    if a.frame_callback_contract:ranges+=((0x7eb860,0x2f0),(0x7eb0ae,0x2a),
        (0x7eb528,8),(0x7eb63c,0x26),(0x7e9298,0xb4),
        (0x7e35ec,0x34),(0x13b6408,13*8),(0x7e3874,0x26))
    if a.event_module_contract:ranges=((0x89f58c,0x158),(0x350064,8),(0x3ef544,0x44))
    if a.gain_module_contract:ranges=((0x66de3c,24),(0x675278,16))
    if a.present_module_contract:ranges=((0x66dc04,0x44),(0x7ec7f0,0x38),(0x7e6934,0x78),(0x675084,16),(0x13b68c0,0x34),(0x13b6648,0x34))
    if a.sync_contract:ranges=((0x785670,0x270),(0x7858e0,0x190))
    if a.dds_refresh_contract:ranges=((0x7db750,0x14a),(0x7db5a8,0x94),(0x10c138,12),(0x1007a30,16),(0x57d270,0x30))
    if a.dds_import_contract:ranges=((0x7db4a0,0x78),(0x7db518,0x50),(0x68d13c,0x11c),(0x10c624,12),(0x10be00,12))
    for start,size in ranges:
        exact=native_bytes(original,start,size)
        if exact!=native_bytes(runtime/'libObj.so',start,size):raise ValueError('Lab contract code differs from original')
        verified_ranges.append({'address':hex(start),'size':size,'sha256':hashlib.sha256(exact).hexdigest()})
if a.frame_callback_contract and manifest.get('rect_trial'):cc+=['-DNATIVE_RECT_MODULE_CONTRACT']
if a.frame_callback_contract and manifest.get('rect_series_trial'):cc+=['-DNATIVE_RECT_SERIES_CONTRACT']
if a.frame_callback_contract and manifest.get('rect_upload_trial'):cc+=['-DNATIVE_RECT_UPLOAD_CONTRACT']
if a.frame_callback_contract and manifest.get('rect_service_trial'):cc+=['-DNATIVE_RECT_SERVICE_CONTRACT']
if a.frame_callback_contract and manifest.get('service_no_idle'):cc+=['-DNATIVE_RECT_NO_IDLE_CONTRACT']
if a.frame_callback_contract and manifest.get('service_single_buffer'):cc+=['-DNATIVE_RECT_SINGLE_BUFFER_CONTRACT']
if a.frame_callback_contract and manifest.get('service_lifecycle_ack'):
    for start,size in ((0x930c7c,0x58),):
        exact=native_bytes(original,start,size)
        if exact!=native_bytes(runtime/'libObj.so',start,size):raise ValueError('Native lifecycle sender differs')
        verified_ranges.append({'address':hex(start),'size':size,'sha256':hashlib.sha256(exact).hexdigest()})
    cc+=['-DNATIVE_RECT_LIFECYCLE_ACK_CONTRACT']
if a.present_module_contract:cc+=['-I',str(build)]
if a.present_module_contract and manifest.get('present_sync_trial'):cc+=['-DPRESENT_SYNC_TRIAL']
if a.present_module_contract and manifest.get('present_alias_trial'):cc+=['-DPRESENT_ALIAS_TRIAL']
if a.dds_refresh_contract:
    sys.path.insert(0,str(here.parent))
    from dds_small_text_plan import compile_progress_24
    payloads=[compile_progress_24(i)[1] for i in range(100)]
    (out/'dds_progress_payloads.h').write_text('static const unsigned char progress_payloads[100][8]={'+','.join('{'+','.join(map(str,p))+'}' for p in payloads)+'};\n')
    reference=(r/'tools/native-font-lab-repro-20261023/native-20.raw').read_bytes()
    if hashlib.sha256(reference).hexdigest()!='23fe782354190a7ebcdb02adc304668ec1e43d3b0539a9a46a05a33b68641d47':
        raise ValueError('Previously verified native glyph reference mismatch')
    words=[int.from_bytes(reference[i:i+2],'little') for i in range(0,len(reference),2)]
    (out/'dds_native_reference.h').write_text('static const unsigned short native_reference[]={'+','.join(map(str,words))+'};\n')
    cc+=['-I',str(out)]
if a.bitmap:cc+=['-DA7C_BITMAP_BOUNDARY']
if a.managed:cc+=['-DA7C_MANAGED_BOUNDARY']
if a.compose:cc+=['-DCOMPOSE_TRIAL']
if a.shared_pool:cc+=['-DSHARED_POOL_TRIAL']
if a.small_pool:cc+=['-DSMALL_POOL_TRIAL']
progress_module=a.progress_frame and (manifest['scope'].startswith('Offline single-source native-font frame') or manifest.get('external_redraw',False))
if progress_module:cc+=['-DA7C_PROGRESS_MODULE']
if a.progress_frame and manifest.get('external_redraw'):cc+=['-DA7C_FRAME_EXTERNAL_REDRAW']
subprocess.run(cc+[str(fixture),'-o',str(out/'fixture.o')],check=True)
subprocess.run([str(r/'tools/lld21/lld'),'-flavor','gnu','-m','armelf_linux_eabi','--hash-style=sysv',
               '--dynamic-linker=/lab/ld.so']+(['--export-dynamic'] if a.present_module_contract and manifest.get('present_alias_trial') else [])+['-e','_start',str(runtime/'startup.o'),str(out/'fixture.o'),
               str(runtime/'libc.so.6'),str(runtime/'libdl.so.2'),str(runtime/'libgcc_s.so.1'),'-o',str(out/'fixture')],env=env,check=True)
name='a7c-text-module-'+uuid.uuid4().hex[:10]
cmd=['docker','run','--rm','--init','--pull','never','--name',name,'--platform','linux/arm/v7',
     '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
     '--memory','256m','--cpus','1','--pids-limit','32','--ulimit','core=0']
mounts=((runtime,'/lab'),(runtime/'fonts','/usr/share/app'),(build,'/trial'),(out,'/result'))
image='alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'
archive=None
if a.archive_input:
    # External research disks need not be shared with Docker Desktop. Nothing
    # is copied to internal host storage or left in a persistent container.
    archive=tempfile.TemporaryFile(dir=out)
    def lab_owner(info):
        info.uid=info.gid=0;info.uname=info.gname='';return info
    with tarfile.open(fileobj=archive,mode='w') as tar:
        for src,dst in mounts:
            for child in sorted(src.iterdir()):
                tar.add(child,arcname=dst.lstrip('/')+'/'+child.name,filter=lab_owner)
    archive.seek(0)
    cmd+=['-i']
    for _,dst in mounts:cmd+=['--tmpfs',dst+':rw,exec,nosuid,size=96m']
    cmd+=['--entrypoint','/bin/sh',image,'-c',
          'tar xf - -C / && exec /lab/ld.so --library-path /lab /result/fixture']
else:
    for src,dst in mounts:cmd+=['--mount',f'type=bind,src={src},dst={dst},readonly']
    cmd+=['--entrypoint','/lab/ld.so',image,'--library-path','/lab','/result/fixture']
try:result=subprocess.run(cmd,capture_output=True,timeout=25,stdin=archive)
except subprocess.TimeoutExpired:
    subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL);raise
finally:
    if archive:archive.close()
stdout=result.stdout.decode(errors='replace')
report={'scope':'Offline native TextRM, exact module; not LCD proof','module_sha256':manifest['binaries']['marker.so'],
        'input_transport':'private_tmpfs_archive' if a.archive_input else 'readonly_host_bind',
        'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'exit':result.returncode,
        'stdout':stdout,'stderr':result.stderr.decode(errors='replace'),
        'passed':result.returncode==0 and (('NATIVE_PRESENT_MODULE_OK 18' if manifest.get('present_sync_trial') else 'NATIVE_PRESENT_MODULE_OK 12' if manifest.get('present_alias_trial') else 'NATIVE_PRESENT_MODULE_OK 9') if a.present_module_contract else 'NATIVE_GAIN_MODULE_OK 5' if a.gain_module_contract else 'NATIVE_EVENT_MODULE_OK 3' if a.event_module_contract else 'NATIVE_FRAME_CALLBACK_OK 26' if a.frame_callback_contract else 'NATIVE_PROGRESS_FRAME_OK' if a.progress_frame else 'NATIVE_RENDER_CONTRACT_OK' if a.render_contract else 'NATIVE_DDS_SUBMIT_OK' if a.submit_contract else 'NATIVE_RELEASE_CONTRACT_OK' if a.release_contract else 'MANAGED_BITMAP_BOUNDARY_OK 7' if a.compose else 'MANAGED_BITMAP_BOUNDARY_OK 5' if a.managed else 'TEXT_BITMAP_OK' if a.bitmap else 'TEXT_MODULE_OK') in stdout,
        'bitmap_boundary':a.bitmap,'managed_boundaries_simulated':a.managed,'shared_pool':a.shared_pool,'small_pool':a.small_pool}
if a.event_module_contract:
    report.update(scope='Actual event DSO and native dispatch; synthetic objects, isolated ARM, no camera',native_code_ranges=verified_ranges,live_enabled=False)
if a.sync_contract:
    report.update(scope='Actual native wait/destroy; synthetic TLS/registry/condition boundaries, no GPU/camera',
                  native_code_ranges=verified_ranges,live_enabled=False,
                  passed=result.returncode==0 and 'NATIVE_PRESENT_SYNC_OK 8' in stdout,
                  adapter_sha256=hashlib.sha256((here/'present_sync.h').read_bytes()).hexdigest(),
                  timeout_ns=20000000,creation_simulated=True,
                  limit='Finite condition timeout does not bound native mutex/driver calls or prove LCD visibility.')
if a.dds_refresh_contract:
    report.update(scope='Original DDS effective-slot refresh and actual TextRM; cached glyph routing; submission/logging simulated, no camera or live hook',
                  native_code_ranges=verified_ranges,live_enabled=False,
                  passed=result.returncode==0 and 'NATIVE_DDS_REFRESH_OK' in stdout and 'NATIVE_DDS_PIPELINE_OK 9' in stdout,
                  adapter_sha256=hashlib.sha256((here/'dds_native_refresh.h').read_bytes()).hexdigest(),
                  production_payload_source_sha256=hashlib.sha256((here.parent/'dds_small_text_plan.py').read_bytes()).hexdigest(),
                  limit='Does not validate LCD persistence, GRM lifetime, live hook installation or page-transition cleanup.')
if a.dds_import_contract:
    report.update(scope='Actual passive GOT observer DSO and original DDS raster/submit; graphics boundaries simulated; no camera',
                  native_code_ranges=verified_ranges,live_enabled=False,
                  passed=result.returncode==0 and 'NATIVE_DDS_IMPORT_OK' in stdout and 'DDS_IMPORT_PAIR_OK 5' in stdout and 'NATIVE_DDS_BINDINGS_OK 2' in stdout,
                  adapter_sha256=hashlib.sha256((here/'dds_import_handoff.h').read_bytes()).hexdigest(),
                  limit='Resolved/lazy binding exercised in isolated processes. External camera recovery and renderer transaction still untested.')
if a.gain_module_contract:
    report.update(scope='Actual gain DSO and native single-load dispatcher; original gain intercepted after validation, isolated ARM, no GPU/camera',original_gain_intercepted=True)
if a.gain_module_contract and manifest.get('gain_scope_trial'):
    report['passed'] &= 'NATIVE_GAIN_SCOPE_OK 11' in stdout
    report['gain_scope_trial']=True
if a.present_module_contract:
    report.update(scope='Actual post-present DSO and native dispatch; synthetic front, bottom/original completion intercepted, no GPU/camera',original_completion_intercepted=True,glyph_sha256=manifest['glyph_sha256'])
if a.frame_callback_contract:
    report.update(scope='Offline original GraphicsEngine post-draw ordering and setters; synthetic engine/backend, no camera or installed callback',native_code_ranges=verified_ranges,live_enabled=False)
    report['passed'] &= 'NATIVE_RECT_POST_OK' in stdout and 'NATIVE_RECT_STATE_OK' in stdout
    report['passed'] &= 'NATIVE_RECT_BAR_OK' in stdout
    report['passed'] &= 'NATIVE_RECT_QUEUE_OK' in stdout and 'NATIVE_RECT_OWNED_SCOPE_OK' in stdout
    report['passed'] &= 'NATIVE_RECT_BACKEND_OK cases=10' in stdout
    report['rect_backend_fixture_sha256']=hashlib.sha256((here.parent/'tests/native_rect_backend.h').read_bytes()).hexdigest()
    if manifest.get('rect_trial'):
        report['passed'] &= ('NATIVE_RECT_SERVICE_OK 26' if manifest.get('rect_service_trial') else 'NATIVE_RECT_SERIES_OK 21' if manifest.get('rect_series_trial') else 'NATIVE_RECT_MODULE_OK 18') in stdout
        if manifest.get('rect_service_trial'):
            report['passed'] &= 'NATIVE_RECT_LIFECYCLE_OK' in stdout
            report['passed'] &= 'NATIVE_FTP_MARK_OK error=102 recovered=100' in stdout
            submits=0 if manifest.get('service_no_idle') else 1000
            idle_line=f'IDLE_ABLATION frames=1000 native_submits={submits} original_forwards=1000'
            idle_passed=idle_line in stdout
            report['passed'] &= idle_passed
            report['service_ablation']={
                'idle_indicator':not manifest.get('service_no_idle',False),
                'double_buffer':not manifest.get('service_single_buffer',False),
                'passed':idle_passed,
                'observed_idle_frames':1000 if idle_passed else None,
                'observed_native_submits':submits if idle_passed else None,
                'observed_original_forwards':1000 if idle_passed else None,
                'gpu_completion_simulated':True,
                'ring_rollover_tested':False}
        report['rect_module_trial']=True
        report['rect_module_fixture_sha256']=hashlib.sha256((here.parent/'tests/native_rect_module_contract.h').read_bytes()).hexdigest()
    report['rect_fixture_sha256']=hashlib.sha256((here.parent/'tests/native_rect_boundary.h').read_bytes()).hexdigest()
    report['rect_state_fixture_sha256']=hashlib.sha256((here.parent/'tests/native_rect_state.h').read_bytes()).hexdigest()
    report['rect_bar_sha256']=hashlib.sha256((here/'native_rect_bar.h').read_bytes()).hexdigest()
    report['rect_queue_fixture_sha256']=hashlib.sha256((here.parent/'tests/native_rect_queue.h').read_bytes()).hexdigest()
    report['event_handoff_sha256']=hashlib.sha256((here/'event_handoff.h').read_bytes()).hexdigest()
    report['frame_series_sha256']=hashlib.sha256((here/'frame_series.h').read_bytes()).hexdigest()
    report['frame_handoff_sha256']=hashlib.sha256((here/'frame_handoff.h').read_bytes()).hexdigest()
    report['expected_isolated_null_call_signal']=11
    report['observer_core_sha256']=hashlib.sha256((here/'frame_observer.h').read_bytes()).hexdigest()
if a.release_contract:
    report.update(scope='Offline native release semantics, synthetic object and actual mutex/refcount; no driver or final destruction',native_code_ranges=verified_ranges)
if a.submit_contract:
    report.update(scope='Offline original DDS descriptor/return semantics and candidate adapter; display, locking and GPU boundaries simulated; not rendering proof',native_code_ranges=verified_ranges,
                  adapter_sha256=hashlib.sha256((here/'native_submit.h').read_bytes()).hexdigest())
if a.render_contract:
    report.update(scope='Offline original blend decision and completion result; graphics/resource boundaries intercepted, no driver or pixel rendering',native_code_ranges=verified_ranges)
if a.progress_frame:
    report.update(scope='Offline native font and candidate single-source frame; ownership/front/GPU simulated, not LCD or driver safety proof',native_code_ranges=verified_ranges,
                  source_sha256={name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in ('native_progress_frame.h','native_submit.h')},
                  boundary_fixture_sha256=hashlib.sha256((here.parent/'tests/managed_bitmap_boundary.h').read_bytes()).hexdigest(),
                  module_lifecycle_tested=progress_module,managed_boundaries_simulated=True,live_enabled=False)
    if progress_module:report['passed'] &= 'NATIVE_PROGRESS_MODULE_OK' in stdout
if a.managed:report['boundary_fixture_sha256']=hashlib.sha256((here.parent/'tests'/('owned_blit_boundary.h' if a.compose else 'managed_bitmap_boundary.h')).read_bytes()).hexdigest()
if report['passed'] and not contract:
    pixels=bytes.fromhex(stdout.split('PIXELS ')[1].splitlines()[0])
    (out/'native-20.raw').write_bytes(pixels)
    report['matches_previous_native_pixels']=pixels==(runtime/'native-20.raw').read_bytes()
    report['passed'] &= report['matches_previous_native_pixels']
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS' if report['passed'] else 'FAIL',out/'result.json')
raise SystemExit(0 if report['passed'] else 1)
