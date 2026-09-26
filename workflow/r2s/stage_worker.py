"""Generic executable stages for any Agent-produced canonical scene + packed Blender file."""
import json,sys,subprocess,shutil,os
from pathlib import Path
from .core import atomic_json
from .contracts import scene_check,ContractError
from .evaluation import glb_check

packet_path=Path(sys.argv[1]).resolve();packet=json.loads(packet_path.read_text());out=Path(packet['output_directory']);stage=packet['stage'];params=packet['parameters'];package=Path(__file__).parent
from .structure import file_sha
atomic_json(out/'execution_implementation.json',{'stage':stage,'worker_sha256':file_sha(Path(__file__)),'implementation_files':{p.name:file_sha(p) for p in sorted(package.glob('*.py'))},'scope':'Actual imported worker snapshot; children are bound to this workflow by core.execute.'})
def find_artifact(names,preferred=None):
    stages=list(packet['input_artifacts'])
    if preferred:stages=sorted(stages,key=lambda x:preferred.index(x) if x in preferred else len(preferred))
    for dep in stages:
        for a in packet['input_artifacts'][dep]:
            if Path(a['path']).name in names:return Path(a['path'])
    raise ContractError('Missing upstream artifact '+str(names))
def run(argv):
    env=os.environ.copy()
    if 'cuda_visible_devices' in params:env['CUDA_VISIBLE_DEVICES']=str(params['cuda_visible_devices'])
    r=subprocess.run(argv,capture_output=True,text=True,shell=False,env=env);(out/(Path(argv[0]).stem+'_subprocess.log')).write_text(r.stdout+'\n'+r.stderr)
    if r.returncode:raise RuntimeError('Subprocess failed: '+str(r.returncode))
def artifact_list():return [str(p.relative_to(out)) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in {'packet.json','response.json','record.json','stdout.log','stderr.log'}]
if stage in {'build_render','build_geometry'}:
    preferred=['agent_calibrate_lighting','agent_materials','agent_review_geometry','agent_model']
    blend=find_artifact({'model.blend','scene.blend'},preferred);scene=find_artifact({'scene.json'},preferred);shutil.copyfile(scene,out/'scene.json')
    from .appearance import enabled as holistic_enabled
    if holistic_enabled(packet):
        obs=packet.get('appearance_observation')
        if not obs or file_sha(obs['path'])!=obs['sha256']:raise ContractError('Missing accepted whole-scene observation')
        shutil.copyfile(obs['path'],out/'appearance_observation.json')
        if stage=='build_render':
            materials=find_artifact({'material_calibration.json'},['agent_materials'])
            shutil.copyfile(materials,out/'material_calibration.json')
            accepted=find_artifact({'model.blend'},['agent_materials'])
            run([params['blender'],'-b',str(accepted),'-t',str(params.get('threads',4)),'--python-exit-code','12','--python',str(package/'blender_appearance.py'),'--',str(out/'accepted_material_state.json')])
    from .surfaces import enabled, realization
    if enabled(packet):
        model_dir=find_artifact({'surface_realization.json'},['agent_model']).parent
        # Validate and carry the accepted source evidence; later material/light
        # stages cannot substitute a new surface declaration.
        model_files=[str(p.relative_to(model_dir)) for p in model_dir.rglob('*') if p.is_file()]
        obs,real=realization(model_dir,model_files)
        names={'surface_observation.json','surface_realization.json'}
        for region in obs['regions']:
            names.add(region['source_crop'])
            names.update(e['artifact'] for e in region.get('manufacturer_images',[]))
        from .structure import evidence_file
        for name in names:
            source=evidence_file(model_dir,name,model_files);target=out/name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    scene=out/'scene.json'
    run([params['blender'],'-b',str(blend),'-t',str(params.get('threads',4)),'--python-exit-code','12','--python',str(package/'blender_metadata.py'),'--',str(scene),'update',str(out/'metadata_sync.json')])
    if stage=='build_geometry':
        from .structure import file_sha
        atomic_json(out/'model_binding.json',{'model_sha256':file_sha(blend),'scene_sha256':file_sha(scene),'model_version':json.loads(scene.read_text()).get('model_version')})
        run([params['blender'],'-b',str(blend),'-t',str(params.get('threads',8)),'--python-exit-code','12','--python',str(package/'blender_structure.py'),'--',str(scene),str(out)])
        from PIL import Image
        audit=json.loads((out/'structural_audit.json').read_text());Image.open(packet['original_input_allowlist'][0]).crop(audit['source_crop_xyxy']).save(out/'furniture_original_crop.png')
        binding=json.loads((out/'model_binding.json').read_text());binding['structural_audit_sha256']=file_sha(out/'structural_audit.json');binding['original_crop_sha256']=file_sha(out/'furniture_original_crop.png');atomic_json(out/'model_binding.json',binding)
    run([params['blender'],'-b',str(blend),'-t',str(params.get('threads',8)),'--python-exit-code','12','--python',str(package/'blender_render.py'),'--',str(out)])
    if packet.get('refinement'):
        from .refinement import write_render_binding
        write_render_binding(packet,out)
elif stage=='export':
    preferred=['agent_physics','agent_review','build_render','agent_calibrate_lighting','agent_materials','agent_model']
    blend=find_artifact({'model.blend','scene.blend'},preferred);scene=find_artifact({'scene.json'},preferred);shutil.copyfile(scene,out/'scene.json')
    run([params['blender'],'-b',str(blend),'-t',str(params.get('threads',8)),'--python-exit-code','12','--python',str(package/'blender_export.py'),'--',str(out/'scene.json'),str(out)])
elif stage=='validate':
    geometry=find_artifact({'geometry_audit.json'});src=geometry.parent
    for p in src.rglob('*'):
        if p.is_file() and p.name not in {'packet.json','response.json','record.json','stdout.log','stderr.log'}:
            q=out/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    scene=json.loads((out/'scene.json').read_text());checks={'scene':scene_check(scene),'glb':glb_check(out/'scene.glb',['floor','ceiling','wall_back','wall_front','wall_left','wall_right'])}
    run([sys.executable,str(package/'simulation.py'),str(out/'scene.json'),str(out)])
    checks['simulation']=json.loads((out/'simulation_audit.json').read_text());checks['geometry']=json.loads((out/'geometry_audit.json').read_text());atomic_json(out/'validation.json',checks)
    from .dynamics import export_and_test
    checks['dynamics']=export_and_test(out/'scene.xml',scene,out,packet.get('physics_options',{}));atomic_json(out/'validation.json',checks)
elif stage=='report':
    val=find_artifact({'validation.json'});review=find_artifact({'review.json'});data=json.loads(val.read_text());visual=json.loads(review.read_text());result={'case_id':packet['case_id'],'workflow_profile':packet.get('workflow_profile','legacy_v1'),'technical_validation':data['simulation']['status'],'visual_acceptance':visual.get('decision','not_evaluated_by_quality_v2'),'validation':data,'visual_review':visual,'scope':'Engineering integrity, visual likeness and physical truth are separate verdicts.'}
    if 'agent_review_physics' in packet['input_artifacts']:result['physics_review']=json.loads(find_artifact({'physics_review.json'}).read_text())
    atomic_json(out/'report.json',result)
    (out/'report.md').write_text('# Real2Sim result\n\nCase: '+packet['case_id']+'\n\nGeometry and simulation checks: '+data['simulation']['status']+'\n\nFull detailed result: report.json. Visual model and exports are in '+str(val.parent)+'.\n\nIndependent metric and novel-view accuracy require separately held-out real measurements/images.\n')
else:raise ContractError('Unsupported executable stage: '+stage)
atomic_json(out/'response.json',{'status':'complete','artifacts':artifact_list(),'evidence':['checked executable stage outputs'],'reasoning_summary':'Completed '+stage+' without changing evidence-backed object placement.'})
