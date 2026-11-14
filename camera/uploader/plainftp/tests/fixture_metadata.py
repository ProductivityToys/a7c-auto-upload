"""Independent reference for legacy XML identity tests; never used by the uploader."""
import re,hashlib,xml.etree.ElementTree as ET
def metadata(data):
 if len(data)>16384 or b'<!' in data:raise ValueError('XML size/declaration')
 x=ET.fromstring(data);ns={'m':'urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20'}
 if x.tag!='{'+ns['m']+'}NonRealTimeMeta':raise ValueError('Unknown XML root')
 target=x.find('m:TargetMaterial',ns);dur=x.find('m:Duration',ns);device=x.find('m:Device',ns)
 if target is None or dur is None or device is None:raise ValueError('Missing metadata')
 umid=target.get('umidRef','').upper()
 if not re.fullmatch(r'[0-9A-F]{64}',umid):raise ValueError('Invalid UMID')
 frames=int(dur.get('value','0'))
 if frames<=0 or device.get('modelName')!='ILCE-7C':raise ValueError('Invalid duration/model')
 ends=x.findall('m:LtcChangeTable/m:LtcChange',ns)
 if not any(y.get('status')=='end' and int(y.get('frameCount','-1'))==frames-1 for y in ends):raise ValueError('Missing terminal timecode')
 return {'umid':umid,'duration_frames':frames,'xml_sha256':hashlib.sha256(data).hexdigest()}
