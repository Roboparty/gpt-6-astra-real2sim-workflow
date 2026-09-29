"""Read material graph endpoints across formats; no source or material editing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy

p=argparse.ArgumentParser(description=__doc__)
for key in ('source-model','export-dir','output'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--entity',default='floor');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
if a.output.exists():raise ValueError('Preserve prior report')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for label,path in [('native',a.source_model),('glb',a.export_dir/'scene.glb'),('usdc',a.export_dir/'scene.usdc')]:
    original=sha(path)
    if label=='native':bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if label=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.wm.usd_import(filepath=str(path))
    mats={}
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not (obj.name==a.entity or obj.get('entity_id')==a.entity or obj.get('userProperties:entity_id')==a.entity):continue
        for slot in obj.material_slots:
            mat=slot.material
            if mat is None:continue
            record={'nodes':[],'diffuse_color':list(mat.diffuse_color)}
            if mat.use_nodes:
                record['links']=[[link.from_node.name,link.from_socket.identifier,link.to_node.name,link.to_socket.identifier] for link in mat.node_tree.links]
                for node in mat.node_tree.nodes:
                    r={'type':node.bl_idname,'name':node.name}
                    if node.bl_idname=='ShaderNodeBsdfPrincipled':
                        r['base_color']=list(node.inputs['Base Color'].default_value);r['base_color_linked']=node.inputs['Base Color'].is_linked
                        r['base_color_sources']=[link.from_node.bl_idname for link in node.inputs['Base Color'].links]
                    if node.bl_idname in {'ShaderNodeBump','ShaderNodeNormalMap'}:
                        r['space']=getattr(node,'space',None)
                        r['inputs']={s.name:{'linked':s.is_linked,'value':list(s.default_value) if getattr(s,'type','') in {'RGBA','VECTOR'} else s.default_value}
                                     for s in node.inputs if hasattr(s,'default_value')}
                    if node.bl_idname=='ShaderNodeTexImage' and node.image:
                        im=node.image;r['image']={'name':im.name,'size':list(im.size),'colorspace':im.colorspace_settings.name,'source':im.source,'packed':bool(im.packed_file)}
                    record['nodes'].append(r)
            mats[mat.name]=record
    assert sha(path)==original
    rows.append({'format':label,'model_sha256':original,'materials':mats})
a.output.write_text(json.dumps({'scope':'Material graph declarations only; not a rendered causal proof','entity':a.entity,'formats':rows},indent=2))
print(json.dumps({'formats':[(r['format'],len(r['materials'])) for r in rows]}))
