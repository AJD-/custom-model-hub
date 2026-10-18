"""Renders the maid Yama: a preview sheet, and optionally a 128 x 128 icon.

    blender -b --factory-startup -P notes/render_yamamaid.py -- <file.glb> <sheet.png> [icon.png]

The sheet's top row is the stand at frame 0 from the front, three-quarter, side and back. Under it
are close-ups of the bodice and the skirt from either side of the front, then frames through the
stand and the walk, seen three-quarter on. His effect part, a transparent flame the preview would
draw solid, is left out.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

CELL = 480
COLS = 4
TARGET = Vector((0.0, 0.0, 2.25))
FULL = 6.4
CLOSE = 2.6
VIEWS = [0, 35, 90, 180]                # degrees around Z from the front (+Y)
CLOSE_VIEWS = [-30, 30]
CLOSE_TARGETS = (Vector((0, 0.3, 3.05)), Vector((0, 0.3, 1.75)))
STAND, WALK = "12140", "12141"


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


def aim(cam, degrees, target, distance=12.0, lift=0.8):
    a = math.radians(degrees)
    cam.location = target + Vector((math.sin(a) * distance, math.cos(a) * distance, lift))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def use(arm, name):
    action = bpy.data.actions[name]
    arm.animation_data.action = action
    if action.slots:
        arm.animation_data.action_slot = action.slots[0]
    return action


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    glb, sheet = args[0], args[1]
    icon = args[2] if len(args) > 2 else None

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False, disable_bone_shape=True)
    for ob in list(scene.objects):          # his flame effect
        if ob.type == "MESH" and ("model_10338" in ob.name or "model_10340" in ob.name):
            bpy.data.objects.remove(ob)
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
    data.ortho_scale = FULL
    cam = bpy.data.objects.new("cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    rows = []
    use(arm, STAND)
    scene.frame_set(0)
    cells = []
    for v in VIEWS:
        aim(cam, v, TARGET)
        cells.append(render(scene, CELL))
    rows.append(np.concatenate(cells, axis=1))
    data.ortho_scale = CLOSE
    cells = []
    for v in CLOSE_VIEWS:
        for target in CLOSE_TARGETS:
            aim(cam, v, target, lift=1.2)
            cells.append(render(scene, CELL))
    rows.append(np.concatenate(cells, axis=1))
    data.ortho_scale = FULL
    aim(cam, 35, TARGET)
    for name in (STAND, WALK):
        f0, f1 = use(arm, name).frame_range
        cells = []
        for k in range(COLS):
            scene.frame_set(round(f0 + (f1 - f0) * k / COLS))
            cells.append(render(scene, CELL))
        rows.append(np.concatenate(cells, axis=1))
    save(np.concatenate(rows[::-1], axis=0), os.path.abspath(sheet))
    print("SHEET", sheet)

    if icon:
        use(arm, STAND)
        scene.frame_set(0)
        scene.render.film_transparent = True
        data.ortho_scale = 3.4
        aim(cam, 15, Vector((0, 0.3, 2.9)), lift=0.8)
        save(render(scene, 128), os.path.abspath(icon))
        print("ICON", icon)


main()
