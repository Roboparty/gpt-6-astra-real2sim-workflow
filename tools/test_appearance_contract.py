"""Negative protocol checks; synthetic fixtures are not a room-quality result."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.appearance import GROUPS, FIXED_VIEWS, observation, materials, check_review
from r2s.contracts import ContractError
from r2s.core import Workflow, atomic_json
from r2s.media import file_hash
from r2s.refinement import limits, write_render_binding


def rejects(action):
    try:
        action()
    except ContractError:
        return
    raise AssertionError('Invalid appearance evidence was accepted')


with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    for i, name in enumerate(['original.png', 'neutral.png', 'source_view.png', 'appearance_neutral.png', *FIXED_VIEWS]):
        Image.new('RGB', (32,32), (i*25, 80, 100)).save(p/name)
    target = {'entity':'bed', 'source_crop_xyxy':[0,0,32,32], 'features':['whole bedding'], 'whole_object':True, 'soft_surface':True,
              'appearance':{k:'fixture observation' for k in ['palette','pattern_layout','direction','scale_evidence','uncertainty']}}
    obs = {'appearance_source':{'path':str(p/'original.png'),'sha256':file_hash(p/'original.png')}, 'appearance_targets':[target],
           'scene_appearance':{k:'fixture' for k in ['global_palette','light_distribution','contrast_hierarchy','uncertainties']}}
    obs['scene_appearance']['coverage'] = {k:{'entities':[], 'absent_reason':'Not present in synthetic fixture'} for k in GROUPS}
    obs['scene_appearance']['coverage']['soft_objects'] = {'entities':['bed']}
    observation(obs, (32,32))
    for mutate in [lambda d:d['scene_appearance']['coverage'].pop('architecture'), lambda d:d['appearance_targets'][0].update(whole_object=False), lambda d:d['appearance_targets'][0]['appearance'].pop('pattern_layout')]:
        bad=copy.deepcopy(obs); mutate(bad); rejects(lambda: observation(bad,(32,32)))
    record={'entity':'bed','material_names':['cotton'],'objects':['quilt'], 'soft_surface':True, 'material_class':'dielectric','parameter_basis':'Labelled fixture prior',
            'pbr_parameters':{'cotton':{'Roughness':.9,'Metallic':0}}, 'texture_scale_m':[1,2], 'evidence':['original.png'],'uncertainty':'fixture',
            'layers':{k:'separate fixture layer' for k in ['macro_pattern','microstructure','folds','illumination']},
            'whole_object_evidence':['original.png','neutral.png'],
            'texture_scope':{'source_kind':'generated','application':'whole_object','mapping':'uv','uv_map':'FabricUV','uncertain_completion':'Unseen print inferred'}}
    mat={'appearance_source_sha256':obs['appearance_source']['sha256'],'materials':[record],'neutral_light_previews':['neutral.png']}
    files=[x.name for x in p.iterdir()]
    materials(mat,obs,(32,32),p,files)
    for mutate in [lambda d:d['materials'][0]['texture_scope'].update(source_kind='original',sample_boxes=[[2,2,8,8]]),
                   lambda d:d['materials'][0]['texture_scope'].update(mapping='world'),
                   lambda d:d['materials'][0]['texture_scope'].update(application='tiled'),
                   lambda d:d['materials'][0]['layers'].pop('illumination'),
                   lambda d:d.update(materials=[]),
                   lambda d:d['materials'][0].update(whole_object_evidence=['missing.png'])]:
        bad=copy.deepcopy(mat);mutate(bad);rejects(lambda:materials(bad,obs,(32,32),p,files))
    tiled=copy.deepcopy(mat);tiled['materials'][0]['texture_scope'].update(application='tiled', repetition_boxes=[[0,0,8,8],[12,12,20,20]],repetition_basis='Two disjoint repeating motifs')
    materials(tiled,obs,(32,32),p,files)
    tiled['materials'][0]['texture_scope']['repetition_boxes'][1]=[2,2,10,10]
    rejects(lambda:materials(tiled,obs,(32,32),p,files))
    entire=copy.deepcopy(mat);entire['materials'][0]['texture_scope'].update(source_kind='original',source_extent='whole_object',sample_boxes=[[0,0,32,32]])
    materials(entire,obs,(32,32),p,files)
    entire['materials'][0]['texture_scope']['sample_boxes']=[[2,2,8,8]]
    rejects(lambda:materials(entire,obs,(32,32),p,files))
    # Preserve comparison identity even after a camera/observation revision.
    atomic_json(p/'case.json',{'id':'fixture','workflow_profile':'quality_v2','mode':'single','inputs':[],'refinement':{}})
    w=Workflow(p);w.state['refinement']={'comparison_protocol':{'fixed':True}, 'agent_review':{'best':{'directory':'best'},'stagnant':2}}
    for stage in ['agent_calibrate','agent_calibrate_room','agent_observe']:
        w.revise(stage,'fixture revision')
        assert w.state['refinement']['agent_review']['best']['directory']=='best'
        assert w.state['refinement']['agent_review']['stagnant']==2
        assert w.state['refinement']['comparison_protocol']=={'fixed':True}
    assert limits({'refinement':{}})['appearance_contract_version']==1
    rejects(lambda:limits({'refinement':{'appearance_contract_version':2}}))
    atomic_json(p/'scene.json',{'camera':{'position':[0,0,0]},'model_version':1})
    (p/'scene.blend').write_bytes(b'protocol fixture, not a model')
    protocol={'fixed':'fixture cameras'};atomic_json(p/'comparison_protocol.json',protocol)
    atomic_json(p/'render_manifest.json',{'comparison_settings':{'fixture':True}})
    packet={'refinement':{'limits':{'appearance_contract_version':1}},'original_input_allowlist':[str(p/'original.png')], 'appearance_targets':[target], 'comparison_protocol':protocol}
    b=write_render_binding(packet,p)
    old=b['protocol_sha256'];atomic_json(p/'scene.json',{'camera':{'position':[1,2,3]},'model_version':2})
    assert write_render_binding(packet,p)['protocol_sha256']==old
    atomic_json(p/'comparison_protocol.json',{'changed':True})
    rejects(lambda:write_render_binding(packet,p));atomic_json(p/'comparison_protocol.json',protocol)
    audit={'model_sha256':b['model_sha256'],'failures':[]};atomic_json(p/'appearance_audit.json',audit)
    def audit_ref():return {'path':str(p/'appearance_audit.json'),'sha256':file_hash(p/'appearance_audit.json')}
    packet.update(stage='agent_review',input_artifacts={'build_render':[audit_ref()]})
    checks={k:{'status':'pass','findings':'synthetic fixture only','evidence':['source_reference.png','source_view.png','appearance_neutral.png',*FIXED_VIEWS]} for k in ['global_composition','material_light_consistency','texture_scope','soft_shape']}
    data={'checks':checks,'appearance_audit_sha256':file_hash(p/'appearance_audit.json'),'per_object':[{'whole_object_findings':'fixture','context_findings':'fixture'}],
          'comparison':{'before':list(FIXED_VIEWS),'after':list(FIXED_VIEWS)}}
    response={'status':'complete','artifacts':[x.name for x in p.iterdir()]}
    check_review(p,response,packet,data,b,None)
    best={'source_sha256':b['source_sha256'],'comparison_images':b['comparison_images'],'target_entities':['bed']}
    check_review(p,response,packet,data,b,best)
    bad=copy.deepcopy(data);bad['comparison']['before']=['comparison_source.png']
    rejects(lambda:check_review(p,response,packet,bad,b,best))
    bad=copy.deepcopy(data);bad['checks']['global_composition']['status']='revise'
    rejects(lambda:check_review(p,response,packet,bad,b,best))
    audit['failures']=['world-coordinate fabric'];atomic_json(p/'appearance_audit.json',audit);packet['input_artifacts']['build_render']=[audit_ref()];data['appearance_audit_sha256']=file_hash(p/'appearance_audit.json')
    rejects(lambda:check_review(p,response,packet,data,b,best))
    check_review(p,{**response,'status':'changes_requested'},packet,data,b,best)
print('PASS scene coverage, sample scope, UV declarations, fixed-view persistence, complete comparisons and failed-audit rejection')
