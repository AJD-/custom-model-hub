"""Counts, frame by frame, what passes through the maid Yama's skirt.

    blender -b --factory-startup -P notes/poke_yamamaid.py -- <file.glb> [clip,clip,...]

For each clip (all of them by default), at every other frame, it counts the leg vertices standing
outside the skirt between its waist and hem, and the staff vertices inside it, by casting
horizontally from the skirt's posed centre line through each vertex. A leg vertex counts only if it
sits outside by more than SLACK, and only above the posed hem at its own angle round the skirt
(below it a leg is meant to show). Vertices are his by their heaviest bone; his tail passes out through the skirt's back by
design and isn't counted. It prints each clip's worst frame and the totals.
"""
import math
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

LEGS = {"group_5", "group_11", "group_4", "group_10"}
STAFF = "group_101"
SLACK = 0.01


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    bpy.ops.import_scene.gltf(filepath=args[0], merge_vertices=False, disable_bone_shape=True)
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    arm.animation_data_create()
    body = next(o for o in scene.objects if o.name.startswith("part_00"))
    skirt = next(o for o in scene.objects if o.name.startswith("skirt"))
    names = {g.index: g.name for g in body.vertex_groups}
    heaviest = [names[max(v.groups, key=lambda g: g.weight).group] if v.groups else None for v in body.data.vertices]
    legs = [i for i, g in enumerate(heaviest) if g in LEGS]
    staff = [i for i, g in enumerate(heaviest) if g == STAFF]
    rest = [v.co.copy() for v in skirt.data.vertices]
    # The black shell only: not the white petticoat hanging under the hem, the apron or the bands
    color = skirt.data.color_attributes.active_color
    shell = [p.index for p in skirt.data.polygons
             if max(color.data[li].color[k] for li in p.loop_indices for k in range(3)) < 0.05]
    waist_z = max(p.z for p in rest)
    shell_verts = {i for face in shell for i in skirt.data.polygons[face].vertices}
    hem_rest = min(rest[i].z for i in shell_verts)
    hem_ring = [i for i in shell_verts if rest[i].z < hem_rest + 1e-3]
    clips = args[1].split(",") if len(args) > 1 else sorted(a.name for a in bpy.data.actions)
    totals = {}
    for name in clips:
        action = bpy.data.actions[name]
        arm.animation_data.action = action
        if action.slots:
            arm.animation_data.action_slot = action.slots[0]
        f0, f1 = (int(round(x)) for x in action.frame_range)
        worst = (0, 0, 0, 0)
        sums = [0, 0]
        for f in range(f0, f1 + 1, 2):
            scene.frame_set(f)
            deps = bpy.context.evaluated_depsgraph_get()

            def posed(ob):
                ev = ob.evaluated_get(deps)
                me = ev.to_mesh()
                out = [ev.matrix_world @ v.co for v in me.vertices], [list(p.vertices) for p in me.polygons]
                ev.to_mesh_clear()
                return out

            sv, sf = posed(skirt)
            bvh = BVHTree.FromPolygons(sv, [sf[i] for i in shell])
            top = [sv[i] for i, p in enumerate(rest) if p.z > waist_z - 1e-4]
            axis = sum(top, Vector()) / len(top)
            hem_z = min(sv[i].z for face in shell for i in sf[face])
            hem_at = [(math.atan2(sv[i].x - axis.x, sv[i].y - axis.y), sv[i].z) for i in hem_ring]

            def local_hem(p):
                """The posed hem's height at p's angle round the skirt: a thigh that lifts its side of
                the hem shows below it there, as it should."""
                a = math.atan2(p.x - axis.x, p.y - axis.y)
                near = sorted(hem_at, key=lambda h: abs((h[0] - a + math.pi) % (2 * math.pi) - math.pi))[:2]
                return max(z for _a, z in near)

            def cast(p):
                o = Vector((axis.x, axis.y, p.z))
                d = p - o
                if d.length < 1e-6:
                    return None, 0.0
                far, start = None, o
                for _ in range(12):
                    hit = bvh.ray_cast(start, d.normalized(), 4.0)[0]
                    if hit is None:
                        break
                    far = (hit - o).length
                    start = hit + d.normalized() * 1e-4
                return far, d.length

            bv, _ = posed(body)
            out_legs = 0
            where = []
            for i in legs:
                p = bv[i]
                if not (hem_z + 0.04 < p.z < axis.z - 0.1) or p.z < local_hem(p) + 0.04:
                    continue
                far, dist = cast(p)
                if far is not None and dist > far + SLACK:
                    out_legs += 1
                    a = math.degrees(math.atan2(p.x - axis.x, p.y - axis.y))
                    where.append((round(a / 45) * 45 % 360, (p.z - hem_z) / (axis.z - hem_z), dist - far, heaviest[i]))
            in_staff = 0
            for i in staff:
                p = bv[i]
                if not (hem_z < p.z < axis.z):
                    continue
                far, dist = cast(p)
                if far is not None and dist < far - SLACK:
                    in_staff += 1
            sums[0] += out_legs
            sums[1] += in_staff
            if out_legs + in_staff > worst[0]:
                worst = (out_legs + in_staff, f, out_legs, in_staff)
                worst_where = where
        totals[name] = sums
        if worst[0]:
            by = {}
            for a, h, e, g in worst_where:
                b = by.setdefault((a, g), [0, 9.0, 0.0, 0.0])
                b[0] += 1
                b[1] = min(b[1], h)
                b[2] = max(b[2], h)
                b[3] = max(b[3], e)
            for (a, g), (n, h0, h1, e) in sorted(by.items()):
                print("  %s worst frame: %3d deg (0 front, 90 his left -x? no: +x) %-9s %3d verts up %.2f..%.2f of the skirt, out by up to %.3f"
                      % (name, a, g, n, h0, h1, e))
        print("POKE %s frames %d-%d  legs out %d  staff in %d  worst %s"
              % (name, f0, f1, sums[0], sums[1],
                 "frame %d (legs %d staff %d)" % worst[1:] if worst[0] else "none"))
    print("POKE TOTAL legs out %d staff in %d" % tuple(sum(t[k] for t in totals.values()) for k in range(2)))


main()
