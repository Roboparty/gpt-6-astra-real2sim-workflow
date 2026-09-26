import sys,json,shutil,hashlib
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');out=Path(w.state['stages']['agent_observe']['directory']);old=R/'case/runs/agent_observe/0003';response=json.loads((old/'response.json').read_text())
for name in response['artifacts']:shutil.copyfile(old/name,out/name)
path=out/'surface_observation.json';data=json.loads(path.read_text());bed=next(r for r in data['regions'] if r['entity']=='bed')
bed['features'][0]['description']='Fine botanical printed linework and wood grain are albedo/illumination ambiguous; do not create relief from these lines.'
bed['features'] += [dict(id='bed_head_panels',description='Exactly two broad rectangular wood headboard infill panels separated by central upright, below open top shelf.',classification='geometry',count=2,depth_cues='Two bounded panel faces and central member visible above pillow; bordering timber occludes their edges.',confidence=.87),dict(id='bed_continuous_duvet',description='One continuous soft duvet drapes over mattress with broad uneven wrinkles and continuous silhouette.',classification='geometry',count=1,depth_cues='Visible side drape, silhouette and shadow transitions support folded continuous sheet volume.',confidence=.95)]
ward=next(r for r in data['regions'] if r['entity']=='wardrobe');image=R/'evidence/bruksvara_hk_0.jpg';shutil.copyfile(image,out/'bruksvara_product.jpg');response['artifacts'].append('bruksvara_product.jpg');ward.update(product_candidate='BRUKSVARA 905.560.47, identity not label verified',manufacturer_image_review='consistent',manufacturer_images=[dict(artifact='bruksvara_product.jpg',url='https://www.ikea.com.hk/dairyfarm/hk/images/788/1178845_PE895737_S4.jpg',sha256=hashlib.sha256(image.read_bytes()).hexdigest())])
atomic_json(path,data);response['reasoning_summary']='Source crop re-inspected: two headboard panels and one continuous folded duvet are explicit geometry; printed/grain lines remain uncertain. All 13 prior targets retained, manufacturer photo now bound to wardrobe candidate. No camera or baseline reset.';atomic_json(out/'response.json',response)
print(w.accept('agent_observe',out/'response.json'))
