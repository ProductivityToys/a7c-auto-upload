#!/usr/bin/env python3
"""Assemble native display upgrade from a verified deployed release and our ELF build.
No credentials or Sony binaries are included. Does not access the camera.
"""
import argparse,hashlib,json,zipfile
from pathlib import Path
APP=Path(__file__).resolve().parents[3]
def sha(b):return hashlib.sha256(b).hexdigest()
def assemble(base,build,output):
    m=json.loads((build/'manifest.json').read_text())
    assert m['rect_service_trial'] and m['path']=='/tmp_bt/a70.so'
    for n,h in m['binaries'].items():assert sha((build/n).read_bytes())==h,n
    for n,h in m['sources'].items():assert sha((APP/n).read_bytes())==h,n
    with zipfile.ZipFile(base) as z:
        old=json.loads(z.read('manifest.json'))
        payload={n[len('payload/'):]:z.read(n) for n in old['files'] if n.startswith('payload/')}
        for n,b in payload.items():assert sha(b)==old['files']['payload/'+n]['sha256'],n
    rollback={n[len('display/'):]:b for n,b in payload.items() if n.startswith('display/')}
    roles={'native-start.sh':'native-start.sh','consumer.sh':'native-consumer.sh','action.sh':'native-action.sh','stage.sh':'stage.sh'}
    for name,source in roles.items():payload['display/'+name]=(Path(__file__).parent/source).read_bytes()
    payload['display/native-probe']=(build/'module-probe').read_bytes()
    payload['display/native-module.so']=(build/'marker.so').read_bytes()
    deps=dict(line.split()[::-1] for line in payload['display/native.sha256'].decode().splitlines())
    for name,h in m['dependencies'].items():
        path='/'+Path(name).name.replace('__','/')
        if path in deps:assert deps[path]==h
        deps[path]=h
    assert len(deps)==9
    payload['display/native.sha256']=''.join(f'{h} {n}\n' for n,h in sorted(deps.items())).encode()
    names=[n for n in payload if n.startswith('display/') and n.split('/')[-1] not in ('manifest','enabled','stage.sh','stage.sha256')]
    assert len(names)==16
    payload['display/manifest']=''.join(f'{sha(payload[n])} {n.split("/")[-1]}\n' for n in sorted(names)).encode()
    payload['display/stage.sha256']=(sha(payload['display/stage.sh'])+'\n').encode()
    output.mkdir(mode=0o700)
    for kind,files in [('payload',payload),('rollback/display',rollback)]:
        for n,b in files.items():
            p=output/kind/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);p.chmod(0o600)
    report={'version':'0.4.0-home.1','base':'0.3.8-home.1','build':str(build),'payload':{n:sha(b) for n,b in payload.items()},'rollback':{n:sha(b) for n,b in rollback.items()},'native_binary_redistribution':False}
    (output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(assemble(a.base,a.build,a.output),indent=2))
