import sys,json,shutil,os,subprocess,traceback
from pathlib import Path
import xml.etree.ElementTree as ET
import r2s
from r2s.dynamics import export_and_test
scene=Path(sys.argv[1]).resolve();export=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve();out.mkdir(parents=True,exist_ok=False);shutil.copyfile(scene,out/'scene.json');shutil.copyfile(export/'geometry_audit.json',out/'geometry_audit.json');os.symlink(export/'meshes',out/'meshes',target_is_directory=True)
try:
 p=subprocess.run([sys.executable,str(Path(r2s.__file__).parent/'simulation.py'),str(out/'scene.json'),str(out)],capture_output=True,text=True);(out/'static.log').write_text(p.stdout+'\n'+p.stderr)
 if p.returncode:raise RuntimeError('Static preflight failed')
 s=json.loads(scene.read_text());tree=ET.parse(out/'scene.xml');tree.getroot().find('option').set('integrator',s['dynamics']['integrator']);ref=out/'solver_reference.xml';tree.write(ref,encoding='unicode',xml_declaration=True);result=export_and_test(ref,s,out,{'hinges':True,'cloth':True,'soft_bodies':True});result['scope']='Preflight only; final executor export/validate still required';(out/'preflight_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
except Exception as e:
 (out/'preflight_failure.json').write_text(json.dumps({'status':'failed','error':str(e),'traceback':traceback.format_exc()},indent=2));raise
