"""Renders frame strips of the maid Yama's clips, to see what each is and where it goes wrong.

    blender -b --factory-startup -P notes/clips_yamamaid.py -- <file.glb> <out.png> [clip,clip,...] [degrees]

Each row is one clip (all of them by default): FRAMES frames spread through it, seen from the
given angle round him (35, three-quarter on, by default) and centred on his body in that frame,
so clips that fly or fall stay in view. Each row's clip and frames are printed in the same order.
A clip given as clip@frame instead renders that one frame from the front, both sides and behind,
closer in, to look at a problem.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

CELL = 240
FRAMES = 7
TARGET = Vector((0.0, 0.0, 1.0))


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
    glb, out = args[0], args[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False, disable_bone_shape=True)
    for ob in list(scene.objects):          # his flame effect
        if ob.type == "MESH" and ("model_10338" in ob.name or "model_10340" in ob.name):
            bpy.data.objects.remove(ob)
    clips = args[2].split(",") if len(args) > 2 and args[2] else sorted(a.name for a in bpy.data.actions)
    degrees = float(args[3]) if len(args) > 3 else 35.0
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "outdoor.sl"
    scene.display.shading.show_specular_highlight = False
    scene.display.shading.color_type = "VERTEX"
    scene.display.shading.show_backface_culling = True
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.045, 0.042, 0.036)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 1.0                # his palette is dark
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    arm.animation_data_create()
    data = bpy.data.cameras.new("cam")
    data.type = "ORTHO"
    data.ortho_scale = 7.0
    cam = bpy.data.objects.new("cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    body = next(o for o in scene.objects if o.name.startswith("part_00"))

    def aim(view):
        """Points the camera at his body from view degrees round him."""
        a = math.radians(view)
        deps = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(deps)
        me = ev.to_mesh()
        vs = [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
        centre = Vector([(min(p[k] for p in vs) + max(p[k] for p in vs)) / 2 for k in range(3)])
        cam.location = centre + Vector((math.sin(a) * 14, math.cos(a) * 14, 1.6))
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()

    rows = []
    for name in clips:
        if "@" in name:
            name, f = name.split("@")
            action = bpy.data.actions[name]
            arm.animation_data.action = action
            if action.slots:
                arm.animation_data.action_slot = action.slots[0]
            scene.frame_set(int(f))
            data.ortho_scale = 4.4
            cells = []
            for view in (0, 90, 180, 270):
                aim(view)
                cells.append(render(scene, CELL * FRAMES // 4))
            data.ortho_scale = 7.0
            rows.append(np.concatenate(cells, axis=1))
            print("ROW %d clip %s frame %s" % (len(rows), name, f))
            continue
        action = bpy.data.actions[name]
        arm.animation_data.action = action
        if action.slots:
            arm.animation_data.action_slot = action.slots[0]
        f0, f1 = action.frame_range
        cells, frames = [], []
        for k in range(FRAMES):
            f = round(f0 + (f1 - f0) * k / (FRAMES - 1))
            scene.frame_set(f)
            aim(degrees)
            frames.append(f)
            cells.append(render(scene, CELL))
        rows.append(np.concatenate(cells, axis=1))
        print("ROW %d clip %s frames %s" % (len(rows), name, frames))
    arr = np.concatenate(rows[::-1], axis=0)
    img = bpy.data.images.new("out", arr.shape[1], arr.shape[0], alpha=True)
    img.pixels = arr.ravel()
    img.filepath_raw = os.path.abspath(out)
    img.file_format = "PNG"
    img.save()
    print("SHEET", out)


main()
