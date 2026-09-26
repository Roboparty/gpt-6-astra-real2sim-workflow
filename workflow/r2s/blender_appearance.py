"""Actual shader/UV inspection and persistent comparison cameras. Run inside Blender."""
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def scalar(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    try:
        return list(value)
    except TypeError:
        return getattr(value, 'name', str(value))


def tree_state(tree, stack=()):
    if tree is None:
        return None
    if tree.name in stack:
        raise ValueError('Recursive shader group')
    nodes = []
    for node in sorted(tree.nodes, key=lambda n: n.name):
        row = {'name': node.name, 'type': node.bl_idname, 'mute': node.mute,
               'inputs': [(s.identifier, scalar(s.default_value)) for s in node.inputs if hasattr(s, 'default_value')]}
        for key in ('operation', 'blend_type', 'uv_map', 'attribute_name', 'projection', 'projection_blend', 'extension', 'interpolation', 'vector_type', 'object',
                    'noise_dimensions', 'noise_type', 'normalize', 'wave_type', 'bands_direction', 'rings_direction', 'wave_profile',
                    'gradient_type', 'voronoi_dimensions', 'distance', 'feature', 'distribution', 'subsurface_method'):
            if hasattr(node, key):
                row[key] = scalar(getattr(node, key))
        if hasattr(node, 'color_ramp'):
            row['ramp'] = [(e.position, list(e.color)) for e in node.color_ramp.elements]
            row['ramp_settings'] = {k:getattr(node.color_ramp,k) for k in ('interpolation','color_mode','hue_interpolation')}
        if getattr(node, 'node_tree', None):
            row['group'] = tree_state(node.node_tree, stack + (tree.name,))
        if getattr(node, 'image', None):
            im = node.image
            path = Path(bpy.path.abspath(im.filepath))
            row['image'] = {'name': im.name, 'colorspace': im.colorspace_settings.name,
                            'sha256': hashlib.sha256(im.packed_file.data).hexdigest() if im.packed_file else sha(path) if path.is_file() else 'unpacked:' + im.source}
        nodes.append(row)
    return {'nodes': nodes, 'links': sorted((l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier) for l in tree.links)}


def snapshot():
    objects = [o for o in bpy.context.scene.objects if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'} and not o.hide_render]
    used = {s.material.name: s.material for o in objects for s in o.material_slots if s.material}
    return {'materials': {n: digest({'tree': tree_state(m.node_tree) if m.use_nodes else None, 'color': list(m.diffuse_color)}) for n, m in sorted(used.items())},
            'assignments': {o.name: [s.material.name if s.material else None for s in o.material_slots] for o in objects}}


def vector_sources(socket, seen=None):
    """Trace the actual connected graph. Unknown/group coordinates fail closed for UV claims."""
    seen = set() if seen is None else seen
    result = set()
    for link in socket.links:
        node = link.from_node
        key = (node.name, link.from_socket.identifier)
        if key in seen:
            continue
        seen.add(key)
        if node.type == 'UVMAP':
            result.add(('uv', node.uv_map))
        elif node.type == 'TEX_COORD':
            result.add(({'UV': 'uv', 'Object': 'object'}.get(link.from_socket.name, 'other'), ''))
        elif node.type == 'NEW_GEOMETRY':
            result.add(('world', ''))
        elif node.type == 'GROUP':
            result.add(('unverified_group', ''))
        else:
            for value in node.inputs:
                if value.is_linked:
                    result.update(vector_sources(value, seen))
    return result


def audit(out, accepted=None):
    out = Path(out)
    data = json.loads((out/'material_calibration.json').read_text())
    failures = []
    covered = set()
    for row in data['materials']:
        scope = row['texture_scope']
        for name in row['objects']:
            obj = bpy.context.scene.objects.get(name)
            if obj is None or obj.hide_render:
                failures.append('Missing visible material object: ' + name)
                continue
            owner = obj.get('entity_id', obj.get('furniture_id', obj.name))
            if owner != row['entity']:
                failures.append('Material object belongs to another entity: ' + name)
            if any(m.type in {'CLOTH','SOFT_BODY'} for m in obj.modifiers) and not row['soft_surface']:
                failures.append('Deforming cloth/soft body cannot declare a rigid mapping: ' + name)
            slots = {s.material.name: s.material for s in obj.material_slots if s.material}
            if not set(row['material_names']) <= slots.keys():
                failures.append('Material declaration differs from actual slots: ' + name)
            for matname in row['material_names']:
                if matname not in slots:
                    continue
                covered.add((name, matname))
                mat = slots[matname]
                nodes = list(mat.node_tree.nodes) if mat.use_nodes else []
                # Inspect connected shader nodes; unused editor experiments do not affect output.
                reachable = set()
                def visit(node):
                    if node.name in reachable:
                        return
                    reachable.add(node.name)
                    for value in node.inputs:
                        for link in value.links:
                            visit(link.from_node)
                for node in nodes:
                    if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                        visit(node)
                principled = [n for n in nodes if n.name in reachable and n.type == 'BSDF_PRINCIPLED']
                if len(principled) != 1:
                    failures.append('Appearance adapter requires one active Principled shader: ' + matname)
                else:
                    declared = row['pbr_parameters'].get(matname, {})
                    for key in ('Roughness', 'Metallic'):
                        socket = principled[0].inputs[key]; expected = declared.get(key)
                        if socket.is_linked:
                            if expected != 'linked': failures.append('PBR record must report linked input: ' + matname + '/' + key)
                        elif not isinstance(expected, (float, int)) or abs(expected-socket.default_value) > 1e-5:
                            failures.append('PBR record differs from actual shader: ' + matname + '/' + key)
                    metallic = principled[0].inputs['Metallic']
                    if row['material_class'] == 'dielectric' and (metallic.is_linked or metallic.default_value > .05):
                        failures.append('Dielectric material uses metallic reflectance: ' + matname)
                textures = [n for n in nodes if n.name in reachable and n.type.startswith('TEX_') and n.type != 'TEX_COORD']
                if scope['application'] == 'constant' and textures:
                    failures.append('Constant material contains an active texture: ' + matname)
                if any(n.type == 'GROUP' and n.name in reachable for n in nodes):
                    failures.append('Shader group requires explicit audit adapter: ' + matname)
                for node in textures:
                    coords = vector_sources(node.inputs['Vector']) if 'Vector' in node.inputs else {('other', '')}
                    if scope['mapping'] == 'uv':
                        uvname = scope.get('uv_map', '')
                        if not coords or any(kind != 'uv' or uv not in ('', uvname) for kind, uv in coords):
                            failures.append('Declared UV material uses other coordinates: ' + matname)
                    elif scope['mapping'] in {'object', 'world'} and (not coords or any(kind != scope['mapping'] for kind, _ in coords)):
                        failures.append('Actual texture coordinates differ from declaration: ' + matname)
                    if node.type == 'TEX_IMAGE' and scope['application'] == 'local' and node.extension == 'REPEAT':
                        failures.append('Local source sample still repeats outside its support: ' + matname)
                    if node.type == 'TEX_IMAGE' and scope['application'] == 'whole_object' and node.extension == 'REPEAT':
                        failures.append('Whole-object image must use EXTEND/CLIP; declare and justify tiling separately: ' + matname)
                if row['soft_surface'] and textures and scope['mapping'] != 'uv':
                    failures.append('Soft texture does not follow surface UV: ' + name)
                if scope['mapping'] == 'uv':
                    deps = bpy.context.evaluated_depsgraph_get(); ev = obj.evaluated_get(deps); mesh = ev.to_mesh()
                    try:
                        layer = mesh.uv_layers.get(scope.get('uv_map', '')) if mesh else None
                        if not layer or not len(layer.data):
                            failures.append('Missing evaluated UV map: ' + name)
                        elif any(not (-1e10 < v < 1e10) for loop in layer.data for v in loop.uv):
                            failures.append('Nonfinite evaluated UV map: ' + name)
                        elif all((loop.uv-layer.data[0].uv).length < 1e-8 for loop in layer.data):
                            failures.append('Collapsed evaluated UV map: ' + name)
                        if layer and (not mesh.uv_layers.active or mesh.uv_layers.active.name != layer.name):
                            if any(('uv', '') in vector_sources(n.inputs['Vector']) for n in textures if 'Vector' in n.inputs):
                                failures.append('Implicit UV reads a different active map: ' + name)
                    finally:
                        ev.to_mesh_clear()
    current = snapshot()
    required = {(o, m) for o, mats in current['assignments'].items() for m in mats if m}
    if required - covered:
        failures.append('Unreviewed visible material assignments: ' + str(sorted(required-covered)))
    if any(not mats or None in mats for mats in current['assignments'].values()):
        failures.append('Visible geometry has no declared material')
    if accepted is not None and current != accepted:
        failures.append('Lighting changed accepted material nodes or assignments; revise materials')
    result = {'model_sha256': sha(bpy.data.filepath), 'status': 'failed' if failures else 'passed', 'failures': failures,
              'material_state': current, 'scope': 'Actual node/coordinate/UV/assignment checks; visual pattern representativeness and physical albedo still need image review.'}
    (out/'appearance_audit.json').write_text(json.dumps(result, indent=2))
    return result


def comparison_views(out, scene, packet):
    from viewpoints import diagnostic_focus, safe_camera_position
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    protocol = packet.get('comparison_protocol')
    if protocol is None:
        r = scene['room']; xm, xM, ym, yM, h = [r[k] for k in ('x_min','x_max','y_min','y_max','height')]
        focus = diagnostic_focus(scene)
        views = [{'name': 'source', 'matrix_world': [list(row) for row in sc.camera.matrix_world],
                  'lens': sc.camera.data.lens, 'shift_x': sc.camera.data.shift_x, 'shift_y': sc.camera.data.shift_y,
                  'width': sc.render.resolution_x, 'height': sc.render.resolution_y}]
        for name, pos in [('wide', (xM-(xM-xm)*.12, ym+(yM-ym)*.12, h*.73)), ('reverse', (xm+(xM-xm)*.2, yM-(yM-ym)*.08, h*.65))]:
            p = Vector(safe_camera_position(scene, pos)); rot = (focus-p).to_track_quat('-Z','Y').to_matrix().to_4x4(); rot.translation = p
            views.append({'name': name, 'matrix_world': [list(row) for row in rot], 'lens': 22., 'shift_x': 0., 'shift_y': 0., 'width': 960, 'height': 640})
        protocol = {'schema': 'real2sim.fixed-views/1', 'views': views,
                    'settings': {k: getattr(sc.view_settings, k) for k in ('view_transform','look','exposure','gamma','use_white_balance','temperature','tint') if hasattr(sc.view_settings,k)},
                    'resolution_percentage': sc.render.resolution_percentage, 'engine': sc.render.engine, 'samples': sc.cycles.samples,
                    'pixel_aspect_x': sc.render.pixel_aspect_x, 'pixel_aspect_y': sc.render.pixel_aspect_y, 'film_transparent': sc.render.film_transparent,
                    'frame': sc.frame_current, 'world_coordinate_gauge': 'Preserve the initial world frame through camera/room revisions'}
    if {v['name'] for v in protocol['views']} != {'source','wide','reverse'} or len(protocol['views']) != 3:
        raise ValueError('Fixed comparison protocol requires exactly source/wide/reverse')
    original_camera = sc.camera
    settings = {k: getattr(sc.render, k) for k in ('resolution_x','resolution_y','resolution_percentage','engine','filepath','use_border','use_crop_to_border','pixel_aspect_x','pixel_aspect_y','film_transparent','use_compositing','use_sequencer')}
    view = {k: getattr(sc.view_settings,k) for k in protocol['settings']}; samples = sc.cycles.samples; frame = sc.frame_current
    curve_mapping=sc.view_settings.use_curve_mapping
    camdata = bpy.data.cameras.new('fixed_comparison'); cam = bpy.data.objects.new('fixed_comparison',camdata); sc.collection.objects.link(cam)
    try:
        sc.camera = cam; sc.frame_set(protocol['frame']); sc.render.engine = protocol['engine']; sc.cycles.samples = protocol['samples']
        sc.render.resolution_percentage = protocol['resolution_percentage']; sc.render.use_border = False; sc.render.use_crop_to_border = False
        sc.render.use_compositing=False;sc.render.use_sequencer=False;sc.view_settings.use_curve_mapping=False
        for key in ('pixel_aspect_x','pixel_aspect_y','film_transparent'): setattr(sc.render,key,protocol[key])
        for k, v in protocol['settings'].items():
            setattr(sc.view_settings,k,v)
        for spec in protocol['views']:
            cam.matrix_world = Matrix(spec['matrix_world']); camdata.sensor_fit = 'HORIZONTAL'; camdata.sensor_width = 36
            camdata.lens = spec['lens']; camdata.shift_x = spec['shift_x']; camdata.shift_y = spec['shift_y']
            sc.render.resolution_x = spec['width']; sc.render.resolution_y = spec['height']
            sc.render.filepath = str(Path(out)/('comparison_'+spec['name']+'.png')); bpy.ops.render.render(write_still=True)
        (Path(out)/'comparison_protocol.json').write_text(json.dumps(protocol,indent=2))
    finally:
        sc.camera = original_camera; sc.frame_set(frame); sc.cycles.samples = samples
        for k,v in settings.items(): setattr(sc.render,k,v)
        for k,v in view.items(): setattr(sc.view_settings,k,v)
        sc.view_settings.use_curve_mapping=curve_mapping
        bpy.data.objects.remove(cam,do_unlink=True); bpy.data.cameras.remove(camdata)


def neutral_view(out, scene, filename='appearance_neutral.png'):
    """Full-scene material inspection with a controlled world and camera-side light."""
    from viewpoints import diagnostic_focus
    sc=bpy.context.scene;world=sc.world;exposure=sc.view_settings.exposure;filepath=sc.render.filepath
    lights={o:o.hide_render for o in sc.objects if o.type=='LIGHT'}
    neutral=bpy.data.worlds.new('appearance_neutral_world');neutral.use_nodes=True
    neutral.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
    neutral.node_tree.nodes['Background'].inputs['Strength'].default_value=.2
    data=bpy.data.lights.new('appearance_neutral_light','AREA');data.energy=400;data.size=3
    lamp=bpy.data.objects.new(data.name,data);sc.collection.objects.link(lamp)
    try:
        for light in lights:light.hide_render=True
        sc.world=neutral;sc.view_settings.exposure=0
        lamp.location=sc.camera.location;lamp.rotation_euler=(diagnostic_focus(scene)-lamp.location).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=str(Path(out)/filename);bpy.ops.render.render(write_still=True)
    finally:
        sc.world=world;sc.view_settings.exposure=exposure;sc.render.filepath=filepath
        for light,hidden in lights.items():light.hide_render=hidden
        bpy.data.objects.remove(lamp,do_unlink=True);bpy.data.lights.remove(data);bpy.data.worlds.remove(neutral)


if __name__ == '__main__':
    # Read-only snapshot of the *accepted* material-stage .blend, produced by the worker.
    target = Path(sys.argv[sys.argv.index('--')+1])
    target.write_text(json.dumps(snapshot(),indent=2))
