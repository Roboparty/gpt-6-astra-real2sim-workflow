"""Run in a fresh Blender process: blender -b model.blend -P this.py -- scene.json protocol.json outdir.

Render visible entity masks with the Object Index pass. Never save the loaded blend.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r2s.contracts import digest


def file_record(path):
    path = Path(path).resolve()
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            sha.update(chunk)
    return {'path': str(path), 'sha256': sha.hexdigest()}


def set_camera(scene, spec):
    data = bpy.data.cameras.new('geometry_feedback_camera')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    camera.location = spec['position']
    rotation = Matrix(spec['rotation_world_to_cv'])
    camera.rotation_euler = (rotation.transposed() @ Matrix.Diagonal((1, -1, -1))).to_euler()
    width, height = spec['image_size']
    data.type = 'PERSP'
    data.sensor_fit = 'HORIZONTAL'
    data.sensor_width = 36
    data.lens = spec['focal_px'] * 36 / width
    data.shift_x = (width / 2 - spec['principal_point'][0]) / width
    data.shift_y = (spec['principal_point'][1] - height / 2) / width
    data.dof.use_dof = False
    data.clip_start = spec.get('clip_start_m', .001)
    data.clip_end = spec.get('clip_end_m', 10000.)
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    bpy.context.view_layer.update()
    # Test the actual Blender projection; input floats alone are not render evidence.
    errors = []
    for u, v in [(width/2, height/2), (0, 0), (width, 0), (0, height), (width, height)]:
        ray = Vector(((u-spec['principal_point'][0])/spec['focal_px'],
                      (v-spec['principal_point'][1])/spec['focal_px'], 1))
        world = Vector(spec['position']) + rotation.transposed() @ ray
        projected = world_to_camera_view(scene, camera, world)
        errors.append(math.hypot(projected.x*width-u, (1-projected.y)*height-v))
    if max(errors) > .01:
        raise ValueError('Actual Blender camera differs from protocol by more than 0.01 px: ' + str(errors))
    return {'position': list(camera.matrix_world.translation),
            'rotation_world_to_cv': [list(row) for row in Matrix.Diagonal((1, -1, -1)) @ camera.matrix_world.to_3x3().transposed()],
            'focal_px': data.lens * width / data.sensor_width,
            'principal_point': [width/2-data.shift_x*width, height/2+data.shift_y*width],
            'image_size': [scene.render.resolution_x, scene.render.resolution_y],
            'resolution_percentage': scene.render.resolution_percentage,
            'clip_start_m': data.clip_start, 'clip_end_m': data.clip_end,
            'maximum_projection_error_px': max(errors)}


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if len(args) != 3:
        raise ValueError('Expected -- scene.json protocol.json outdir')
    scene_path, protocol_path, output = (Path(p).resolve() for p in args)
    if not bpy.data.filepath or not Path(bpy.data.filepath).is_file():
        raise ValueError('Load the saved input model.blend before running this script')
    model = file_record(bpy.data.filepath)
    spec = json.loads(scene_path.read_text(encoding='utf-8-sig'))
    protocol = json.loads(protocol_path.read_text(encoding='utf-8-sig'))
    if protocol.get('schema') != 'real2sim.geometry-feedback-protocol/1.0' or not protocol.get('views'):
        raise ValueError('Invalid geometry protocol')
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'candidate.json').exists():
        raise ValueError('Use a new output directory; previous candidate evidence must be retained')
    scene = bpy.context.scene
    expected = sorted({obj['id'] for view in protocol['views'] for obj in view['objects']})
    if len(expected) > 32767:
        raise ValueError('Too many entities for Blender Object Index')
    indices = {name: index+1 for index, name in enumerate(expected)}
    members = {name: [] for name in expected}
    transparent = set()
    for obj in scene.objects:
        owner = obj.get('entity_id', obj.get('furniture_id', obj.name))
        obj.pass_index = indices.get(owner, 0)
        if owner in members and obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            members[owner].append({'name': obj.name, 'hide_render': obj.hide_render})
        for slot in obj.material_slots:
            material = slot.material
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type in {'BSDF_TRANSPARENT', 'BSDF_GLASS', 'VOLUME_PRINCIPLED', 'VOLUME_SCATTER'}:
                    transparent.add(material.name)
                if node.type == 'BSDF_PRINCIPLED' and (node.inputs['Alpha'].default_value < 1 or
                        node.inputs.get('Transmission Weight') and node.inputs['Transmission Weight'].default_value > 0):
                    transparent.add(material.name)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.seed = 0
    scene.render.use_motion_blur = False
    scene.render.film_transparent = False
    scene.render.use_multiview = False
    scene.render.use_compositing = True
    scene.render.use_sequencer = False
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    # All geometry remains; opaque materials make mask semantics explicit even for glass.
    override = bpy.data.materials.new('geometry_feedback_opaque_override')
    override.use_nodes = True
    principled = override.node_tree.nodes.get('Principled BSDF')
    principled.inputs['Base Color'].default_value = (.5, .5, .5, 1)
    principled.inputs['Roughness'].default_value = 1
    layer = bpy.context.view_layer
    for other in scene.view_layers:
        other.use = other == layer
    layer.material_override = override
    layer.use_pass_object_index = True
    world = bpy.data.worlds.new('geometry_feedback_world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    scene.world = world
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_node = tree.nodes.new('CompositorNodeRLayers')
    render_node.layer = layer.name
    composite = tree.nodes.new('CompositorNodeComposite')
    tree.links.new(render_node.outputs['Image'], composite.inputs['Image'])
    views = []
    for view_index, view in enumerate(protocol['views']):
        readback = set_camera(scene, view['camera'])
        file_nodes, object_records = [], []
        for object_index, obj in enumerate(view['objects']):
            record = {'id': obj['id'], 'landmarks': []}
            if 'mask' in obj:
                prefix = f'view_{view_index:04d}_object_{object_index:04d}_'
                if list(output.glob(prefix + '*.png')):
                    raise ValueError('Refusing to overwrite an existing mask: ' + prefix)
                mask = tree.nodes.new('CompositorNodeIDMask')
                mask.index = indices[obj['id']]
                mask.use_antialiasing = False
                tree.links.new(render_node.outputs['IndexOB'], mask.inputs['ID value'])
                writer = tree.nodes.new('CompositorNodeOutputFile')
                writer.base_path = str(output)
                writer.format.file_format = 'PNG'
                writer.format.color_mode = 'BW'
                writer.format.color_depth = '8'
                writer.file_slots[0].path = prefix
                tree.links.new(mask.outputs['Alpha'], writer.inputs[0])
                file_nodes.append((mask, writer, prefix, record))
            object_records.append(record)
        preview = output / f'view_{view_index:04d}_opaque_clay.png'
        scene.render.filepath = str(preview)
        bpy.ops.render.render(write_still=True)
        for mask, writer, prefix, record in file_nodes:
            paths = list(output.glob(prefix + '*.png'))
            if len(paths) != 1:
                raise ValueError('Missing or ambiguous compositor mask output: ' + prefix)
            record['mask'] = file_record(paths[0])
            tree.nodes.remove(mask)
            tree.nodes.remove(writer)
        views.append({'id': view['id'], 'camera': view['camera'], 'camera_readback': readback,
                      'render': file_record(preview), 'objects': object_records})
    if file_record(bpy.data.filepath) != model:
        raise ValueError('Input blend changed during rendering')
    candidate = {'schema': 'real2sim.geometry-feedback-candidate/1.0', 'protocol_sha256': digest(protocol),
                 'model': model, 'scene': file_record(scene_path), 'views': views,
                 'reconstruction_source_sha256': spec.get('reconstruction_source_sha256',
                    [view['source']['sha256'] for view in protocol['views']]),
                 'renderer': {'script': file_record(__file__), 'blender_version': bpy.app.version_string,
                              'engine': scene.render.engine, 'mask_method': 'Object Index plus IDMask, antialiasing disabled',
                              'entity_members': members, 'opaque_override': True,
                              'possibly_transparent_materials_overridden': sorted(transparent),
                              'source_usage_declaration': 'scene.json' if 'reconstruction_source_sha256' in spec else
                                  'conservative fallback: every protocol source counted as used; heldout will fail',
                              'limitations': ['Opaque silhouettes, including glass; source annotations must follow this convention.',
                                              'Landmark bindings are not implemented; requested landmarks remain missing and fail evaluation.',
                                              'Usage declarations require workflow input-ledger verification; renderer cannot prove historical independence.']}}
    (output / 'candidate.json').write_text(json.dumps(candidate, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print('GEOMETRY_FEEDBACK_RENDER_COMPLETE', str(output / 'candidate.json'))


if __name__ == '__main__':
    main()
