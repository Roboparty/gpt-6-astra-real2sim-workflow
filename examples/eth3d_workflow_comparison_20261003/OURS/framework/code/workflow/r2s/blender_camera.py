"""Shared pinhole transfer; Blender cameras look down -Z with +Y up."""
from mathutils import Matrix


def apply_camera(scene, camera, spec):
    try:
        from .camera import focal_xy, validate_camera,principal_for_raster
    except ImportError:
        from camera import focal_xy, validate_camera,principal_for_raster
    validate_camera(spec)
    fx, fy = focal_xy(spec); width, height = spec['image_size']
    ratio = fx / fy
    transform = (Matrix(spec['rotation_world_to_cv']).transposed() @ Matrix.Diagonal((1, -1, -1))).to_4x4()
    transform.translation = spec['position']; camera.matrix_world = transform
    data = camera.data; data.type = 'PERSP'; data.sensor_fit = 'HORIZONTAL'; data.sensor_width = 36
    data.lens = fx * 36 / width
    cx,cy=principal_for_raster(spec)
    data.shift_x = (width / 2 - cx) / width
    data.shift_y = (cy - height / 2) * ratio / width
    data.dof.use_dof = False
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.pixel_aspect_x = max(1., 1. / ratio)
    scene.render.pixel_aspect_y = max(1., ratio)
