from pathlib import Path
import bpy,numpy as np,json,hashlib
from mathutils import Matrix
r=Path(__file__).resolve().parent;inp=r/'synthetic_inputs';inp.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=0;sc.view_settings.gamma=1
G=np.array([[0,-1,0,3],[1,0,0,-2],[0,0,1,.2],[0,0,0,1.]])
def material(name,color,transparent=False):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');shader=n.new('ShaderNodeBsdfTransparent' if transparent else 'ShaderNodeEmission');shader.inputs['Color'].default_value=(*color,1);m.node_tree.links.new(shader.outputs[0],out.inputs[0]);return m
base=material('author_neutral_emission',(.1,.1,.1));red=material('author_red_marker',(1,0,0));blue=material('author_blue_marker',(0,0,1));clear=material('author_transparent_sheet',(1,1,1),True)
verts=[];faces=[];mids=[]
def quad(points,mat):
 s=len(verts);verts.extend(points);faces.append(tuple(range(s,s+4)));mids.append(mat)
for y,cx,mi in [(4,-2,1),(-4,2,2)]:
 xs=[-10,cx-.3,cx+.3,10];zs=[-10,.7,1.3,10]
 for i in range(3):
  for j in range(3):quad([(xs[i],y,zs[j]),(xs[i+1],y,zs[j]),(xs[i+1],y,zs[j+1]),(xs[i],y,zs[j+1])],mi if i==j==1 else 0)
for x in [-10,10]:quad([(x,-4,-10),(x,4,-10),(x,4,10),(x,-4,10)],0)
for z in [-10,10]:quad([(-10,-4,z),(10,-4,z),(10,4,z),(-10,4,z)],0)
mesh=bpy.data.meshes.new('analytic_shell');mesh.from_pydata(verts,[],faces);mesh.update();ob=bpy.data.objects.new('cube_shell',mesh);sc.collection.objects.link(ob);ob.matrix_world=Matrix(G.tolist())
for m in [base,red,blue]:mesh.materials.append(m)
for p,mi in zip(mesh.polygons,mids):p.material_index=mi
mesh=bpy.data.meshes.new('transparent_panel');mesh.from_pydata([(-2.5,0,.5),(-1.5,0,.5),(-1.5,0,1.5),(-2.5,0,1.5)],[],[(0,1,2,3)]);mesh.materials.append(clear);ob=bpy.data.objects.new('visible_transparent_panel',mesh);sc.collection.objects.link(ob);ob.matrix_world=Matrix(G.tolist())
coll=bpy.data.collections.new('hidden_proxy_collection');sc.collection.children.link(coll);coll.hide_render=True
bpy.ops.mesh.primitive_cube_add();ob=bpy.context.object;ob.name='hidden_proxy';ob.matrix_world=Matrix(G.tolist())@Matrix.Translation((0,-1,0))@Matrix.Diagonal((20,.1,20,1))
for c in list(ob.users_collection):c.objects.unlink(ob)
coll.objects.link(ob)
light=bpy.data.lights.new('author_light','POINT');light.energy=30;ob=bpy.data.objects.new('author_light',light);sc.collection.objects.link(ob);ob.location=(3,-2,2)
bpy.ops.wm.save_as_mainfile(filepath=str(r/'model.blend'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();(r/'freeze.json').write_text(json.dumps(dict(model_sha256=sha(r/'model.blend'),model_from_input=G.tolist(),quality_status='synthetic fixture only')))
poses=[];Ks=[];sizes=[];rays=[];depths=[];targets=[]
for i,(C,R,size,K) in enumerate([([-2,-2,1],[[1,0,0],[0,0,1],[0,-1,0]],[160,120],[[150,0,73.5],[0,120,56.5],[0,0,1]]),([2,2,1],[[-1,0,0],[0,0,-1],[0,-1,0]],[180,130],[[130,0,90.2],[0,160,61.8],[0,0,1]])]):
 T=np.eye(4);T[:3,:3]=R;T[:3,3]=C;K=np.array(K,float);W,H=size;u,v=np.meshgrid((np.arange(160)+.5)*W/160-.5,(np.arange(120)+.5)*H/120-.5);ray=np.c_[(u.ravel()-K[0,2])/K[0,0],(v.ravel()-K[1,2])/K[1,1],np.ones(u.size)];d=np.full(u.size,6.)
 world=ray@T[:3,:3].T;t=(0-C[1])/world[:,1];pts=C+world*t[:,None];hit=(t>0)&(t<6)&(pts[:,0]>=-2.5)&(pts[:,0]<=-1.5)&(pts[:,2]>=.5)&(pts[:,2]<=1.5);d[hit]=t[hit]
 poses.append(T);Ks.append(K);sizes.append(size);rays.append(ray);depths.append(d);targets.append(dict(index=i,expected_patch_centroid_integer_output=[(K[0,2]+.5)*640/W-.5,(K[1,2]+.5)*round(H*640/W)/H-.5],transparent_depth_pixels=int(hit.sum())))
np.savez(inp/'truth_grid.npz',depth=np.array(depths),rays=np.array(rays),poses=np.array(poses))
np.save(inp/'laser_sample.npy',np.array([[-2,4,1],[2,-4,1],[10,0,0],[-10,0,0],[0,0,10],[0,0,-10]],np.float32))
views=[]
for i in range(31):
 j=i%2;views.append(dict(frame_id=f'synthetic_{i:03d}',role='reconstruction' if i<29 else 'heldout',T_world_camera=poses[j].tolist(),K=Ks[j].tolist(),image_size=sizes[j],path='synthetic-placeholder-no-real-photograph'))
(inp/'views.json').write_text(json.dumps(views));(r/'analytic_expectations.json').write_text(json.dumps(dict(gauge=G.tolist(),cameras=targets,scope='Entirely generated synthetic fixture. File laser_sample.npy contains6analytic shell points, no acquired data.',materials=[m.name for m in [base,red,blue,clear]],light='author_light'),indent=2))
print('SYNTHETIC_FIXTURE_CREATED')
