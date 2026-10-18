"""Measures Yama's body in his bind pose: per height, the extent of each body region's vertices, and
renders the bind pose from four sides with lines every 0.25 m.

    blender -b --factory-startup -P notes/sections_yamamaid.py -- <yama.glb> <sheet.png>

Regions are by each vertex's heaviest bone. Blender units are metres, Z up, the model faces +Y.
"""
import math
import os
import sys
from collections import defaultdict

import bpy
import numpy as np
from mathutils import Vector

REGIONS = {
    "torso": {"group_94", "group_97", "group_98", "group_102", "group_81", "group_65", "group_89", "group_90", "group_91"},
    "shoulder": {"group_81", "group_65"},
    "upper arm": {"group_80", "group_64"},
    "forearm": {"group_79", "group_63"},
    "thigh": {"group_5", "group_11"},
    "knee": {"group_4", "group_10"},
    "head": {"group_88"},
}
CELL = 520


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


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    glb, sheet = args[0], args[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False, disable_bone_shape=True)
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    body = next(o for o in scene.objects if o.type == "MESH" and o.name.startswith("part_00"))
    names = {g.index: g.name for g in body.vertex_groups}
    heaviest = [names[max(v.groups, key=lambda g: g.weight).group] if v.groups else None for v in body.data.vertices]

    for region, bones in REGIONS.items():
        rows = defaultdict(list)
        for v, b in zip(body.data.vertices, heaviest):
            if b in bones:
                rows[round(v.co.z * 10) / 10].append(v.co)
        print("REGION", region)
        for z in sorted(rows, reverse=True):
            ps = rows[z]
            left = [p for p in ps if p.x < 0]
            print("  z %.1f n %3d x %.3f..%.3f y %.3f..%.3f  left-side x %s" % (
                z, len(ps), min(p.x for p in ps), max(p.x for p in ps), min(p.y for p in ps), max(p.y for p in ps),
                "%.3f..%.3f" % (min(p.x for p in left), max(p.x for p in left)) if left else "-"))

    for name in sorted(arm.data.bones.keys(), key=lambda n: int(n.split("_")[1]) if n.startswith("group_") else 999):
        b = arm.data.bones[name]
        print("BONE %-10s parent %-10s head (%.3f %.3f %.3f) tail (%.3f %.3f %.3f)" % (
            name, b.parent.name if b.parent else "-", *b.head_local, *b.tail_local))

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "VERTEX"
    scene.display.shading.show_backface_culling = True
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.045, 0.042, 0.036)
    scene.view_settings.view_transform = "Standard"
    for z10 in range(0, 21):
        z = z10 * 0.25
        me = bpy.data.meshes.new("line")
        me.from_pydata([(-3.5, -3.5, z), (3.5, -3.5, z), (3.5, 3.5, z), (-3.5, 3.5, z)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new("line", me)
        ob.display_type = "WIRE"
        scene.collection.objects.link(ob)
    scene.display.shading.show_object_outline = False
    data = bpy.data.cameras.new("cam")
    data.type = "ORTHO"
    data.ortho_scale = 5.6
    cam = bpy.data.objects.new("cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    target = Vector((0, 0, 2.5))
    cells = []
    for deg in (0, 90, 180):
        a = math.radians(deg)
        cam.location = target + Vector((math.sin(a) * 9, math.cos(a) * 9, 0))
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        cells.append(render(scene, CELL))
    arr = np.concatenate(cells, axis=1)
    img = bpy.data.images.new("out", arr.shape[1], arr.shape[0], alpha=True)
    img.pixels = arr.ravel()
    img.filepath_raw = os.path.abspath(sheet)
    img.file_format = "PNG"
    img.save()
    print("SHEET", sheet)


main()
