"""Close renders of a glb, posed or at rest, for fitting.

    blender -b --factory-startup -P notes/closeup_yamamaid.py -- <glb> <out.png> <x,y,z> <scale> [clip@frame | rest] [hide,...]

Objects whose names contain any of hide are left out, as the throne. Four views round the target - front, three-quarter, side and back - orthographic at the given scale.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

CELL = 480


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
    target = Vector([float(c) for c in args[2].split(",")])
    scale = float(args[3])
    pose = args[4] if len(args) > 4 else "rest"
    hide = args[5].split(",") if len(args) > 5 else []

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False, disable_bone_shape=True)
    for ob in list(scene.objects):
        if ob.type == "MESH" and ("model_10338" in ob.name or "model_10340" in ob.name
                                   or any(h in ob.name for h in hide)):
            bpy.data.objects.remove(ob)
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    arm.animation_data_create()
    if pose == "rest":
        arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.matrix_basis.identity()
        scene.frame_set(0)
    else:
        clip, frame = pose.split("@")
        action = bpy.data.actions[clip]
        arm.animation_data.action = action
        if action.slots:
            arm.animation_data.action_slot = action.slots[0]
        scene.frame_set(int(frame))

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
    data = bpy.data.cameras.new("cam")
    data.type = "ORTHO"
    data.ortho_scale = scale
    cam = bpy.data.objects.new("cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cells = []
    for deg in (0, 35, 90, 180):
        a = math.radians(deg)
        cam.location = target + Vector((math.sin(a) * 12, math.cos(a) * 12, 0.5))
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        cells.append(render(scene, CELL))
    arr = np.concatenate(cells, axis=1)
    img = bpy.data.images.new("out", arr.shape[1], arr.shape[0], alpha=True)
    img.pixels = arr.ravel()
    img.filepath_raw = os.path.abspath(out)
    img.file_format = "PNG"
    img.save()
    print("SHEET", out)


main()
