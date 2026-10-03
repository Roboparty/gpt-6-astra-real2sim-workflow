"""Portable geometry-recipe replay; this does not replay or approve native agent stages.

blender -b --factory-startup --threads 2 --python replay_builder.py -- --root NEW_DIR
"""
from pathlib import Path
import argparse,sys,shutil,json,hashlib,os
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=a.root.resolve();root.mkdir(parents=True,exist_ok=False)
bundle=Path(__file__).resolve().parent
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['R2S_CPU']='1';os.environ['CUDA_VISIBLE_DEVICES']=''
shutil.copytree(bundle/'framework/code',root/'code')
(root/'inputs').mkdir();shutil.copyfile(bundle/'metadata/input_packet.json',root/'inputs/packet.json')
for name in ['model_from_input.json','v3_layout_corrections.json']:
 shutil.copyfile(bundle/'metadata'/name,root/name)
obs=root/'native_case/runs/agent_observe/0001';obs.mkdir(parents=True)
shutil.copyfile(bundle/'metadata/furniture_observation.json',obs/'furniture_observation.json')
out=root/'models/v3';source_root="Path('/home/wqz/real2sim_agent_compare_20261003/OURS')"
receipts=[]
for name,extra in [('build_scene_v3.py',[]),('prepare_native_assembly.py',['--write'])]:
 source=bundle/'source'/name;raw=source.read_text();assert raw.count(source_root)==1
 program=raw.replace(source_root,'Path('+repr(str(root))+')')
 sys.argv=[str(source),'--',str(out),*extra]
 exec(compile(program,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
 receipts.append(dict(source=name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),adaptation='Only ROOT filesystem relocation; no geometry, camera, label or material parameter change'))
(root/'replay_receipt.json').write_text(json.dumps(dict(kind='asset recipe replay; not native acceptance',sources=receipts,notes=['Original model hash is expected to differ because Blender embeds file paths and save metadata','Validate geometry identity separately if exact reproduction evidence is required','Native protocol rerun additionally needs original allowed RGB/depth and real agent stage reviews']),indent=2))
