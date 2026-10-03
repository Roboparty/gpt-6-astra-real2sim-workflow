"""Structural room boxes in world metres, independent of decorative visual bounds.

room.openings contains {wall, bounds: [u_min, u_max, z_min, z_max]}.
u is world X for front/back, world Y for left/right. These are apertures in
the wall only; glazing, frames and doors keep their own collision entities.
Only the axis-aligned canonical room and declared rectangular openings are
supported. Nonempty room.collision_proxies is rejected: arbitrary/nonrectangular
walls require independent surface-coverage validation before being enabled.
"""
import math
import numpy as np

SURFACES = ('floor', 'ceiling', 'wall_back', 'wall_front', 'wall_left', 'wall_right')


def room_openings(room):
    openings = room.get('openings', [])
    for opening in openings:
        wall = opening['wall']
        if wall not in SURFACES[2:]:
            raise ValueError('Opening must name a room wall: ' + str(wall))
        a, b, c, d = opening['bounds']
        axis = 'x' if wall in ('wall_back', 'wall_front') else 'y'
        if not (all(math.isfinite(v) for v in (a, b, c, d)) and
                room[axis + '_min'] <= a < b <= room[axis + '_max'] and
                0 <= c < d <= room['height']):
            raise ValueError('Opening bounds outside wall: ' + str(opening))
    return openings


def shell_boxes(room, surface):
    xm, xM, ym, yM, h, t = [float(room[k]) for k in
                            ('x_min', 'x_max', 'y_min', 'y_max', 'height', 'thickness')]
    if not (all(math.isfinite(v) for v in (xm, xM, ym, yM, h, t)) and
            xm < xM and ym < yM and min(h, t) > 0):
        raise ValueError('Invalid room collision dimensions')
    if surface not in SURFACES:
        raise ValueError('Unknown room surface: ' + surface)
    openings = room_openings(room)
    if room.get('collision_proxies'):
        raise ValueError('room.collision_proxies is unsupported: use the axis-aligned canonical room and openings; nonrectangular walls require independent coverage validation')
    def box(position, dimensions):
        return dict(shape='box', position=position, dimensions=dimensions,
                    yaw=0, source='canonical_room_surface')
    if surface in ('floor', 'ceiling'):
        z = -t / 2 if surface == 'floor' else h + t / 2
        return [box([(xm+xM)/2, (ym+yM)/2, z], [xM-xm, yM-ym, t])]
    along_x = surface in ('wall_back', 'wall_front')
    lo, hi = (xm, xM) if along_x else (ym, yM)
    holes = [o['bounds'] for o in openings if o['wall'] == surface]
    # Partition only at aperture edges; no convex hull can bridge an opening.
    us = sorted({lo, hi} | {v for a, b, _, _ in holes for v in (a, b)})
    zs = sorted({0., h} | {v for _, _, c, d in holes for v in (c, d)})
    normal = {'wall_back': yM+t/2, 'wall_front': ym-t/2,
              'wall_left': xm-t/2, 'wall_right': xM+t/2}[surface]
    result = []
    for a, b in zip(us, us[1:]):
        for c, d in zip(zs, zs[1:]):
            u, z = (a+b)/2, (c+d)/2
            if any(ha < u < hb and hc < z < hd for ha, hb, hc, hd in holes):
                continue
            result.append(box([u, normal, z] if along_x else [normal, u, z],
                              [b-a, t, d-c] if along_x else [t, b-a, d-c]))
    if not result:
        raise ValueError('Opening removes entire required wall: ' + surface)
    return result


def box_in_entity_frame(box, entity):
    """Invert arbitrary audited root pose without rotating the world box itself."""
    q = np.asarray(entity['root_quaternion_wxyz'], float)
    if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) < 1e-12:
        raise ValueError('Invalid shell root quaternion')
    w, x, y, z = q / np.linalg.norm(q)
    rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    position = rotation.T @ (np.asarray(box['position']) - entity['root_position'])
    # q_local = conjugate(q_root) * q_world_yaw.
    c, s = math.cos(box.get('yaw', 0)/2), math.sin(box.get('yaw', 0)/2)
    quat = [w*c+z*s, -x*c-y*s, -y*c+x*s, w*s-z*c]
    return position.tolist(), quat
