"""Record distribution hashes without including environment paths or inputs."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'.git','__pycache__','node_modules','.venv','.pytest_cache'}
files=[]
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or EXCLUDE.intersection(p.relative_to(ROOT).parts) or p.name=='manifest.json':continue
    b=p.read_bytes();files.append({'path':p.relative_to(ROOT).as_posix(),'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
result={'package':'Krea2 Character Sheet Designer','version':'0.2.0','date_utc':'2026-10-05',
 'sources':{'qwen':'604ec0c6ea4046a3460e2c662d41f564870c15d8','qwen_layout_image':'f627413028f2c2e05b75ed2b09a30947dea1fec6','h3':'bf792c652a9f50e895409e49fce667fef0f73c25','identity_edit':'86f886dac23013d88996e3a2e99093ba44d322fb','comfyui_schema':'5c460d8172fe30761ff67c0df3d5643bb74e0d70'},
 'canonical_workflow':{'path':'workflows/Krea2_Layout_Reference_Designer.json',
  'source_filename':'Krea2_Layout_Reference_Designer_wf.json',
  'source_sha256':'cd15879da50979467637eeae41dc5d94cec099b4cb5bfdf4a02f925f40ba8e14',
  'source_bytes_preserved':True},
 'verification_scope':'CPU / JavaScript / jsdom / HTTP / static workflow; no real ComfyUI or GPU', 'files':files}
(ROOT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(files),'files recorded')
