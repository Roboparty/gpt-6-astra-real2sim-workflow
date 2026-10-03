import sys,pathlib,tempfile,copy,json
from PIL import Image
sys.path.insert(0,sys.argv[1]);from r2s.appearance import materials
from r2s.contracts import ContractError
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp)
 for n in ['a.png','b.png']:Image.new('RGB',(16,16),'white').save(p/n)
 obs={'appearance_source':{'sha256':'fixture'},'appearance_targets':[{'entity':'fixture','soft_surface':False}]}
 row={'entity':'fixture','material_names':['M'],'objects':['panel'],'soft_surface':False,'layers':{k:'fixture' for k in ['macro_pattern','microstructure','folds','illumination']},'material_class':'dielectric','parameter_basis':'fixture','pbr_parameters':{'M':{'Roughness':.5,'Metallic':0}},'whole_object_evidence':['a.png','b.png'],'texture_scope':{'source_kind':'generated','application':'local','mapping':'per_node','uncertain_completion':'fixture','node_mappings':{'M':{'Photo':{'mapping':'uv','uv_map':'UV'},'Noise':{'mapping':'world'}}}}}
 def run(r):materials({'appearance_source_sha256':'fixture','materials':[r]},obs,(16,16),p,['a.png','b.png'])
 run(row);count=1
 for mutate in [lambda x:x['texture_scope'].update(node_mappings={}),lambda x:x['texture_scope']['node_mappings'].update(Extra={}),lambda x:x['texture_scope']['node_mappings']['M']['Photo'].pop('uv_map'),lambda x:x['texture_scope']['node_mappings']['M']['Photo'].update(uv_map=''),lambda x:x['texture_scope']['node_mappings']['M']['Noise'].update(mapping='unknown'),lambda x:x['texture_scope']['node_mappings']['M']['Noise'].update(uv_map='UV'),lambda x:x.update(soft_surface=True)]:
  bad=copy.deepcopy(row);mutate(bad)
  try:run(bad)
  except ContractError:count+=1
  else:raise AssertionError('Invalid per-node schema accepted')
 soft=copy.deepcopy(row);soft['soft_surface']=True;soft['texture_scope']['node_mappings']['M']['Noise']={'mapping':'uv','uv_map':'UV'};run(soft);count+=1
 print('PASS_PER_NODE_SCHEMA',count)
