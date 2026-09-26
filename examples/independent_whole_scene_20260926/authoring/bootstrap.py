import json, hashlib, sys, urllib.request, re
from pathlib import Path
ROOT=Path('/home/wqz/real2sim_whole_scene_20260926')
sys.path.insert(0,str(ROOT/'repo/workflow'))
from r2s.core import Workflow, atomic_json
PY='/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python'
BL='/home/wqz/real2sim_fresh_20260921/runtime/blender-4.5.3-linux-x64/blender'
case=ROOT/'case'
cfg=dict(id='ikea_independent_whole_scene_20260926_A',mode='single',branch='A',formal_test=True,workflow_profile='quality_v2',inputs=[dict(path=str(ROOT/'input/01_bedroom.jpg'),sha256='5068deec1cba1e6a167209adca5fb77e4d931db06ed6a3812b9a2b8252d8c866',role='reconstruction')],provenance=dict(kind='real_photograph',status='verified',evidence=['User supplied bedroom original; delegated request explicitly identifies authorized original photograph and SHA256. No independent capture metadata certification.']),physics=dict(hinges=False,cloth=False,soft_bodies=False),refinement=dict(max_revisions=20,max_stagnant=5,max_seconds=43200,surface_contract_version=1,appearance_contract_version=1),stages={'preprocess':{'parameters':{'max_edge':1702}}})
for stage in ['build_geometry','build_render','export','validate','report']:
 cfg['stages'][stage]=dict(command=[PY,'-m','r2s.stage_worker','{packet}'],parameters=dict(blender=BL,threads=4,cuda_visible_devices='6'),timeout_seconds=10800)
if not (case/'case.json').exists(): atomic_json(case/'case.json',cfg)
atomic_json(ROOT/'task_scope.json',dict(repository_commit='9314d6c270b1abf378ef0fbb77b93ad1465f7c1a',source='authorized original only',strategy='A independent geometry',scale_prior='User confirmed longitudinal bed rail 2.0 m; fitting prior, not withheld validation',deliverables=['editable Blender','source comparison','whole-scene and object evidence','neutral lighting','persistent three views','export reload audit','honest unresolved issues'],excluded=['old V5 and bedroom models','old scripts or fitted parameters','ArtVIP geometry','dynamics'],resources=dict(gpu=6,threads=4,root=str(ROOT)),physical_accuracy='not independently verified'))
print(Workflow(case).run())
url='https://www.ikea.com/th/en/p/bruksvara-wardrobe-with-2-doors-and-2-drawers-white-90556047/'
try:
 html=urllib.request.urlopen(url,timeout=40).read().decode()
 (ROOT/'evidence/bruksvara_page.html').write_text(html)
 urls=list(dict.fromkeys(re.findall(r'https://www\.ikea\.com/[^\s"<>]+bruksvara[^\s"<>]+\.(?:jpg|png)',html)))
 print('PRODUCT_IMAGES',urls[:8])
 atomic_json(ROOT/'evidence/product_urls.json',dict(page=url,images=urls[:8]))
 for i,u in enumerate(urls[:2]): urllib.request.urlretrieve(u,ROOT/f'evidence/bruksvara_{i}.jpg')
except Exception as e: print('PRODUCT_FETCH_ERROR',str(e))
