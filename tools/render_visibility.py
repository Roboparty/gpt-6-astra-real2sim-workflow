"""Render collection membership for scene measurement; never use viewport visibility."""
GEOMETRY={'MESH','CURVE','SURFACE','FONT','META'}


def render_members(scene):
    members=set();visited=set()
    def walk(collection):
        if collection.hide_render or collection.as_pointer() in visited:return
        visited.add(collection.as_pointer());members.update(obj.as_pointer() for obj in collection.objects)
        for child in collection.children:walk(child)
    walk(scene.collection)
    return members


def include_instance(instance,members):
    obj=instance.object.original
    if obj.type not in GEOMETRY or obj.hide_render or obj.get('exclude_from_evaluation'):return False
    if instance.is_instance:
        parent=instance.parent.original if instance.parent else None
        if parent is None or parent.hide_render or parent.as_pointer() not in members:return False
        raise ValueError('Visible evaluated instances must be realized before scene measurement; do not guess their collection visibility')
    return obj.as_pointer() in members
