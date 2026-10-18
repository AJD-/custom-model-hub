"""Reports on an exported glb: its parts, their joints and colors, its clips, and renders it.

    blender -b --factory-startup -P notes/probe_yamamaid.py -- <file.glb> <sheet.png> [stand clip]

Prints each part's bounds, joints (by each vertex's heaviest, with vertex counts and bounds) and face colors (packed HSL, with
render priorities), each clip's frame range, and the evaluated bounds at the stand's frame 0. The
sheet is the stand at frame 0 from the front, three-quarter, side and back.
"""
import math
import os
import sys
from collections import Counter, defaultdict

import bpy
import numpy as np
from mathutils import Vector

CELL = 420


def render(scene, size):
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    tmp = os.path.join(bpy.app.tempdir, "cell.png")
    scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
    bpy.data.images.remove(img)
    return px


def save(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("out", w, h, alpha=True)
    img.pixels = arr.ravel()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


def face_hsl(me, i):
    rs = me.attributes.get("_RS_HSL")
    if rs is None:
        return -1
    poly = me.polygons[i]
    if rs.domain == "POINT":
        return int(rs.data[poly.vertices[0]].value)
    if rs.domain == "FACE":
        return int(rs.data[i].value)
    return int(rs.data[poly.loop_indices[0]].value)


def hsl(h):
    return "%5d (h%2d s%d l%3d)" % (h, h >> 10 & 63, h >> 7 & 7, h & 127)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    glb, sheet = args[0], args[1]
    stand = args[2] if len(args) > 2 else None

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False, disable_bone_shape=True)
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    parts = sorted([o for o in scene.objects if o.type == "MESH"], key=lambda o: o.name)

    print("BONES", len(arm.data.bones), "parented", sum(1 for b in arm.data.bones if b.parent))
    for ob in parts:
        me = ob.data
        names = {g.index: g.name for g in ob.vertex_groups}
        vs = [ob.matrix_world @ v.co for v in me.vertices]
        lo = Vector([min(p[k] for p in vs) for k in range(3)])
        hi = Vector([max(p[k] for p in vs) for k in range(3)])
        print("\nPART %s verts %d faces %d bounds (%.3f %.3f %.3f)..(%.3f %.3f %.3f) extras %s"
              % (ob.name, len(me.vertices), len(me.polygons), *lo, *hi,
                 {k: (me[k] if not hasattr(me[k], "__len__") else "[%d]" % len(me[k])) for k in me.keys()}))
        by = defaultdict(list)
        for v, p in zip(me.vertices, vs):
            if v.groups:
                by[names[max(v.groups, key=lambda g: g.weight).group]].append(p)
        for g, ps in sorted(by.items(), key=lambda kv: -sum(p.z for p in kv[1]) / len(kv[1])):
            c = sum(ps, Vector()) / len(ps)
            print("  joint %-10s %4d verts centre (%.3f %.3f %.3f) z %.3f..%.3f"
                  % (g, len(ps), c.x, c.y, c.z, min(p.z for p in ps), max(p.z for p in ps)))
        pri = list(me["rsRenderPriorities"]) if "rsRenderPriorities" in me else [None] * len(me.polygons)
        colors = Counter((face_hsl(me, p.index), pri[p.index]) for p in me.polygons)
        for (h, r), n in colors.most_common():
            zs = [(ob.matrix_world @ p.center).z for p in me.polygons
                  if face_hsl(me, p.index) == h and pri[p.index] == r]
            print("  color %s pri %s faces %3d z %.3f..%.3f" % (hsl(h), r, n, min(zs), max(zs)))

    print()
    for a in bpy.data.actions:
        print("CLIP", a.name, "frames", tuple(a.frame_range))

    arm.animation_data_create()
    if stand:
        action = bpy.data.actions[stand]
        arm.animation_data.action = action
        if action.slots:
            arm.animation_data.action_slot = action.slots[0]
    scene.frame_set(0)
    deps = bpy.context.evaluated_depsgraph_get()
    for ob in parts:
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        vs = [ev.matrix_world @ v.co for v in me.vertices]
        print("POSED %s z %.3f..%.3f x %.3f..%.3f y %.3f..%.3f" % (
            ob.name, min(p.z for p in vs), max(p.z for p in vs), min(p.x for p in vs), max(p.x for p in vs),
            min(p.y for p in vs), max(p.y for p in vs)))
        ev.to_mesh_clear()

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "outdoor.sl"
    scene.display.shading.show_specular_highlight = False
    scene.display.shading.color_type = "VERTEX"
    scene.display.shading.show_backface_culling = True
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.045, 0.042, 0.036)
    scene.view_settings.view_transform = "Standard"
    data = bpy.data.cameras.new("cam")
    data.type = "ORTHO"
    deps = bpy.context.evaluated_depsgraph_get()
    zs = []
    for ob in parts:
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        zs += [(ev.matrix_world @ v.co).z for v in me.vertices]
        ev.to_mesh_clear()
    target = Vector((0, 0, (min(zs) + max(zs)) / 2))
    data.ortho_scale = (max(zs) - min(zs)) * 1.15
    cam = bpy.data.objects.new("cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cells = []
    for deg in (0, 35, 90, 180):
        a = math.radians(deg)
        cam.location = target + Vector((math.sin(a) * 8, math.cos(a) * 8, 0.4))
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        cells.append(render(scene, CELL))
    save(np.concatenate(cells, axis=1), os.path.abspath(sheet))
    print("SHEET", sheet)


main()
