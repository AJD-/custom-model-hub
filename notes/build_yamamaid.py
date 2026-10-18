"""Dresses Yama as a maid: source/yama-maid.glb from export/14176, and source/yami-maid.glb for his pet.

    blender -b --factory-startup -P notes/build_yamamaid.py
    blender -b --factory-startup -P notes/build_yamamaid.py -- throne      (Yama on his throne)
    blender -b --factory-startup -P notes/build_yamamaid.py -- chathead    (his dialogue head)

Yama keeps his own skeleton, size and every clip, and his staff, wings, horns and mane. His torso
is recolored black below a sweetheart neckline and shaped into a modest bust, and his thighs are
bare red skin. New geometry, at the game's low-poly density, adds the rest:

- a skirt fitted to his hips by ray-cast, with a ruffled white petticoat under its hem, a white
  waistband tied in a bow at the back and a frilled apron in front. It is weighted from his waist
  down onto his thighs, more the lower it hangs (see SKIRT_BANDS);
- frilled white garter bands round his thighs, with a black bow on each and straps up under the
  skirt;
- a white ruffle along the neckline with a small white bow, and a ruffled white collar with a black
  bow tie;
- black puffed cap sleeves at his shoulders, frilled at their hems;
- a frilled headband between his horns.

His rig is skeletal: every vertex is weighted to up to four bones, and the new geometry is weighted
the same way, the converter blending the weights it can't keep. Colors are set as packed HSL, the
way the game stores them. Blender units are metres, Z up, the model faces +Y, and everything is
fitted in the bind pose, where he stands straight with his arms at his sides.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.normpath(os.path.join(HERE, ".."))
YAMA = os.path.join(PACK, "export", "14176", "yama.glb")
OUT = os.path.join(PACK, "source", "yama-maid.glb")
OUT_PET = os.path.join(PACK, "source", "yami-maid.glb")
CHATHEAD = os.path.join(PACK, "export", "chathead-124", "yama-chathead.glb")
OUT_CHATHEAD = os.path.join(PACK, "source", "yama-chathead-maid.glb")
CHATHEAD_JOINT = "group_15"             # the head's own bone, under the jaw's
CHATHEAD_HORN = {5437}
CHATHEAD_BAND_HEIGHT = 0.38

BODY_PART = "part_00"
EFFECT_PARTS = ("part_01", "part_02")    # his flame effect, which Yami doesn't have


def bones(*ids):
    return {"group_%d" % i for i in ids}


HEAD = "group_88"
NECK = bones(94, 95, 96)
SPINE = bones(97, 98, 99, 100, 102)
CLAVICLES = bones(65, 81)
UPPER_ARMS = bones(64, 80)
THIGHS = bones(5, 11)
LEFT_THIGH, RIGHT_THIGH = "group_5", "group_11"            # -x, +x
TAIL = bones(12, 13, 14, 15, 16, 17)
WING_ROOTS = bones(32, 33, 48, 49)                         # the back between the wings rides these
HIPS = SPINE | THIGHS                                      # what the skirt must clear

# Colors, packed HSL (hue << 10 | saturation << 7 | luminance)
DRESS_BLACK = 0 << 10 | 0 << 7 | 12
DRESS_INSIDE = 0 << 10 | 0 << 7 | 6
WHITE = 0 << 10 | 0 << 7 | 116
WHITE_SHADE = 0 << 10 | 0 << 7 | 102
SKIN_LIGHT = 798                                           # his own reds
SKIN_DARK = 790
HORN = {5436, 5426, 5416, 5408}

# Skirt: from his natural waist out over his hips, in rings of SKIRT_SIDES, fitted in the bind pose
WAIST_Z = 2.78
HEM_Z = 1.72
SKIRT_SIDES = 24
SKIRT_RINGS = (0.0, 0.25, 0.4, 0.7, 0.87, 1.0)   # ring heights, as fractions of the way from waist to hem
SKIRT_FIT = (0.0, 0.25, 0.4, 1.0)       # the rings fitted to him; the rest lie on the lines between
SKIRT_FLARE = 1.35                      # the hem's radius at least this times the waist's
SKIRT_BELL = 0.024                      # how far the rings between bow out from the straight line
HEM_OVER_HIPS = 1.2                    # the hem's radius at least this times the hips'
SKIRT_CLEARANCE = 0.04
WAIST_CLEARANCE = 0.012
WAIST_BONES = {"group_99": 0.5, "group_102": 0.5}          # the waist ring rides between the spine and pelvis
PELVIS = "group_102"
SKIRT_BANDS = ((0.2, 0.0), (0.3, 0.4), (0.55, 0.75), (1.0, 0.95))         # down to this depth (0 waist, 1 hem): how far it follows the thighs
SEATED = False                           # whether the skirt drapes over a seated lap (Yama on his throne)
SEAT_BACK = -0.4                        # seated, sides further back than this (cosine from the front) stay with the pelvis
SKIRT_SOFT = 0.1                        # metres of knee reach over which a skirt side turns from one thigh to the other
SKIRT_FIRST_JOINT = 200                 # the skirt joints are group_200 on, past his bones
PETTICOAT_DROP = 0.14
PETTICOAT_OUT = 0.06
PETTICOAT_SEED = 11
PETTICOAT_TUCK = 0.02
WAISTBAND = 0.08
APRON_SPAN = 2                          # skirt sides either side of the front the apron covers: 60 degrees
APRON_BOTTOM_RING = 3                   # the ring it stops at, 0.7 of the way down
APRON_OFF = 0.028
APRON_FRILL = 0.07
BACK_BOW = 0.13
BACK_TAIL = 0.44

# Garters: a white frilled band round each thigh, a black bow on its front, straps up under the skirt
GARTER_BOTTOM, GARTER_TOP = 1.42, 1.52
GARTER_SIDES = 8
GARTER_OFF = 0.012
GARTER_FRILL = 0.044
GARTER_BOW = 0.05
STRAP_WIDTH = 0.032

# Bust: a modest swell of the chest, a smooth bump forward round each centre
BUST_X, BUST_Z = 0.27, 3.32
BUST_FORWARD = 0.10
BUST_SPREAD_X, BUST_SPREAD_Z = 0.17, 0.15
BUST_BONES = bones(97, 98, 99) | CLAVICLES

# Neckline: a sweetheart over the bust, lower under the arms and across the back. He is bare above it.
NECKLINE = ((0, 3.38), (25, 3.50), (60, 3.48), (95, 3.40), (180, 3.40))   # (degrees from the front, height)
NECK_FRILL = 0.056
NECK_FRILL_OUT = 0.024
NECK_FRILL_STEP = 15
NECK_FRILL_SEED = 13
NECK_BOW = 0.05

# Collar: his mane runs down onto his chest, so the collar is an arc across the top of the chest
# under his jaw, where the mane meets it, ruffled down, with a black bow tie at its centre
COLLAR_Z = 3.74
COLLAR_ARC = 70                         # degrees either side of the front
COLLAR_SIDES = 8                        # across the arc
COLLAR_DROP = 0.05
COLLAR_OUT = 0.035
BOW_SIZE = 0.08
BOW_COLOR = 0 << 10 | 0 << 7 | 6

# Cap sleeves: a black puff over each shoulder, frilled at its hem, along the shoulder to elbow line
SLEEVE_ARMS = (("group_65", "group_64", "group_63"), ("group_81", "group_80", "group_79"))
SLEEVE_RINGS = ((-0.08, 0.0), (0.04, 0.05), (0.18, 0.06), (0.30, 0.01))   # (along shoulder to elbow, puff)
SLEEVE_SIDES = 8
SLEEVE_GAP = 0.012
SLEEVE_FRILL = 0.06
RUFFLE_SEED = 17

# Headband: an arc over the top of the head between the horns, frilled along its top edge
BAND_HEIGHT = 0.16
BAND_GAP = 0.01
BAND_SMOOTH = 3
BAND_ARC = 55
BAND_TILT = 15
BAND_WRAP = 25
BAND_Y = 0.0
BAND_DEPTH = 0.06
BAND_WIDTH = 0.016
FRILL = 0.09
FRILL_LOW = 0.35
FRILL_JITTER = 0.4
FRILL_FOLD = 0.03
FRILL_SEED = 7
BAND_SEGS = 10
BAND_COLOR = 0 << 10 | 0 << 7 | 10
FRILL_COLOR = 0 << 10 | 0 << 7 | 112

# Thighs: his fur trousers are spiky tufts. Each thigh vertex further from the hip to knee line than
# THIGH_SMOOTH of the thigh's vertices at its height is pulled in to that, so the bare thighs are smooth
THIGH_SMOOTH = 0.35
THIGH_BAND = 0.15                       # metres of thigh measured together
KNEES = {"group_5": "group_4", "group_11": "group_10"}

ADDED_PRIORITY = 0                      # render priority of everything built here

# Garment lengths are scaled by K, which is 1 for the boss; BUST_FRONT_Y and BACK_Y say where his
# chest's front and his back begin
K = 1.0
BUST_FRONT_Y = 0.15
BACK_Y = -0.1

# Yama on his throne (NPC 124) is an older, smaller model on a skeleton of his own, seated: the same
# outfit is fitted to him by mapping every height above from the boss's about the hips and scaling
# every length by his size, then measuring against his own body as the boss's is measured
THRONE_K = 0.51                         # his thigh and spine lengths against the boss's
BOSS_HIP_Z, THRONE_HIP_Z = 2.139, 1.161


def use_throne():
    global YAMA, OUT, OUT_PET, BODY_PART, EFFECT_PARTS, HEAD, NECK, SPINE, CLAVICLES, UPPER_ARMS, THIGHS
    global LEFT_THIGH, RIGHT_THIGH, TAIL, WING_ROOTS, HIPS, HORN, WAIST_BONES, PELVIS, BUST_BONES, KNEES
    global SLEEVE_ARMS, K, BUST_FRONT_Y, BACK_Y, NECKLINE, SEATED, SKIRT_FLARE, HEM_OVER_HIPS, SKIRT_BELL
    SEATED = True
    # No bell: a flared front stands off his thighs, so seated it folds up against his belly
    # instead of lying along his lap
    SKIRT_FLARE = 1.0
    HEM_OVER_HIPS = 1.0
    YAMA = os.path.join(PACK, "export", "124", "yama.glb")
    OUT = os.path.join(PACK, "source", "yama-throne-maid.glb")
    OUT_PET = None
    BODY_PART = "part_01"                # part_00 is the throne, left as it is
    EFFECT_PARTS = ()
    HEAD = "group_56"
    NECK = bones(57)
    SPINE = bones(58, 59, 66)
    CLAVICLES = bones(35, 53)
    UPPER_ARMS = bones(34, 52)
    THIGHS = bones(5, 11)
    LEFT_THIGH, RIGHT_THIGH = "group_5", "group_11"
    TAIL = bones(12, 13, 14, 15, 16, 17)
    WING_ROOTS = bones(30, 31, 48, 49)
    HIPS = SPINE | THIGHS
    HORN = HORN | {5434}
    WAIST_BONES = {"group_59": 0.5, "group_66": 0.5}
    PELVIS = "group_66"
    BUST_BONES = bones(58, 59) | CLAVICLES
    KNEES = {"group_5": "group_4", "group_11": "group_10"}
    SLEEVE_ARMS = (("group_35", "group_34", "group_33"), ("group_53", "group_52", "group_51"))

    def z(boss):
        return THRONE_HIP_Z + (boss - BOSS_HIP_Z) * THRONE_K

    names = globals()
    for name in ("WAIST_Z", "HEM_Z", "GARTER_BOTTOM", "GARTER_TOP", "BUST_Z", "COLLAR_Z"):
        names[name] = z(names[name])
    NECKLINE = tuple((a, z(h)) for a, h in NECKLINE)
    SKIRT_BELL = 0.0
    for name in ("SKIRT_CLEARANCE", "WAIST_CLEARANCE", "PETTICOAT_DROP", "PETTICOAT_OUT",
                 "PETTICOAT_TUCK", "WAISTBAND", "APRON_OFF", "APRON_FRILL", "BACK_BOW", "BACK_TAIL", "GARTER_OFF",
                 "GARTER_FRILL", "GARTER_BOW", "STRAP_WIDTH", "BUST_X", "BUST_FORWARD", "BUST_SPREAD_X",
                 "BUST_SPREAD_Z", "NECK_FRILL", "NECK_FRILL_OUT", "NECK_BOW", "COLLAR_DROP", "COLLAR_OUT", "BOW_SIZE",
                 "SLEEVE_GAP", "SLEEVE_FRILL", "BAND_HEIGHT", "BAND_GAP", "BAND_DEPTH", "BAND_WIDTH", "FRILL",
                 "FRILL_FOLD", "THIGH_BAND", "SKIRT_SOFT", "BUST_FRONT_Y", "BACK_Y"):
        names[name] = names[name] * THRONE_K
    K = THRONE_K


def hsl_to_linear(hsl):
    """RsColor.hslToLinear: packed HSL to the linear RGB COLOR_0 carries."""
    h = (hsl >> 10 & 63) / 64.0 + 0.0078125
    s = (hsl >> 7 & 7) / 8.0 + 0.0625
    l = (hsl & 127) / 128.0
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def chan(t):
        t = t + 1 if t < 0 else t - 1 if t > 1 else t
        if 6 * t < 1:
            return p + (q - p) * 6 * t
        if 2 * t < 1:
            return q
        if 3 * t < 2:
            return p + (q - p) * (2 / 3.0 - t) * 6
        return p

    out = []
    for t in (h + 1 / 3.0, h, h - 1 / 3.0):
        c = max(0, min(255, int(chan(t) * 256))) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path, merge_vertices=False, disable_bone_shape=True)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    return arm, sorted([o for o in new if o.type == "MESH"], key=lambda o: o.name)


def weights_of(ob):
    """Each vertex's bones and weights, as {bone name: weight}."""
    names = {g.index: g.name for g in ob.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in ob.data.vertices]


def heaviest(ws):
    return [max(w, key=w.get) if w else None for w in ws]


def paint(ob, faces, hsl):
    """Sets faces (indices) to a packed HSL color, in COLOR_0 and _RS_HSL alike."""
    me = ob.data
    col = me.color_attributes.active_color
    rgb = hsl_to_linear(hsl)
    rs = me.attributes.get("_RS_HSL")
    for i in faces:
        poly = me.polygons[i]
        for li in poly.loop_indices:
            a = col.data[li].color[3]
            col.data[li].color = (*rgb, a)
        if rs is not None:
            if rs.domain == "POINT":
                for vi in poly.vertices:
                    rs.data[vi].value = hsl
            elif rs.domain == "FACE":
                rs.data[i].value = hsl
            else:
                for li in poly.loop_indices:
                    rs.data[li].value = hsl


def face_hsl(ob, i):
    me = ob.data
    rs = me.attributes["_RS_HSL"]
    poly = me.polygons[i]
    if rs.domain == "POINT":
        return int(rs.data[poly.vertices[0]].value)
    if rs.domain == "FACE":
        return int(rs.data[i].value)
    return int(rs.data[poly.loop_indices[0]].value)


def body_bvh(body, on, groups, keep=None):
    """A BVH over the body faces lying wholly on the given bones, in the bind pose; keep, if given,
    also has to accept the face's index."""
    vs = [v.co for v in body.data.vertices]
    faces = [list(f.vertices) for f in body.data.polygons
             if all(on[i] in groups for i in f.vertices) and (keep is None or keep(f.index))]
    return BVHTree.FromPolygons(vs, faces)


def outermost(bvh, origin, direction, reach=2.0):
    """How far out along a ray the last surface it crosses is, or 0 if none. Low-poly bodies are
    open shells, so inside and outside can't be told apart, only the furthest crossing."""
    far, start = 0.0, origin
    for _ in range(16):
        hit = bvh.ray_cast(start, direction, reach)[0]
        if hit is None:
            break
        far = (hit - origin).length
        start = hit + direction * 1e-4
    return far


def facing(verts, f, direction):
    """Face f wound so its normal points along direction."""
    a, b, c = (Vector(verts[i]) for i in f[:3])
    return list(f) if (b - a).cross(c - a).dot(direction) >= 0 else list(reversed(f))


class Mesh:
    """Geometry being built: vertices, faces with a packed HSL color each, and per vertex its bones
    and their weights, {bone name: weight}."""

    def __init__(self):
        self.verts, self.faces, self.colors, self.weights = [], [], [], []
        self.twins = {}

    def add(self, p, weights):
        self.verts.append(Vector(p))
        self.weights.append({weights: 1.0} if isinstance(weights, str) else dict(weights))
        return len(self.verts) - 1

    def twin(self, i):
        """A copy of vertex i for the back of two-sided faces. The export drops a face that reuses
        another's vertices in reverse, so the back needs vertices of its own."""
        if i not in self.twins:
            self.twins[i] = self.add(self.verts[i], self.weights[i])
        return self.twins[i]

    def face(self, f, color, out=None, both=False, inside=None):
        """Adds face f, wound to face out if given; both adds its reverse too, in inside's color."""
        f = facing(self.verts, f, out) if out is not None else list(f)
        self.faces.append(f)
        self.colors.append(color)
        if both:
            self.faces.append([self.twin(i) for i in reversed(f)])
            self.colors.append(color if inside is None else inside)


def new_part(arm, name, mesh, next_rs, part):
    """Puts built geometry on the rig as a part of its own. Faces are triangulated here, as the
    export would, so the per-face lists line up with its faces."""
    colors = [c for q, c in zip(mesh.faces, mesh.colors) for _ in range(len(q) - 2)]
    faces = [t for q in mesh.faces for t in ([list(q)] if len(q) == 3 else
                                              [[q[0], q[1], q[2]], [q[0], q[2], q[3]]])]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in mesh.verts], [], faces)
    me.update()
    col = me.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
    for poly, hsl in zip(me.polygons, colors):
        rgb = hsl_to_linear(hsl)
        for li in poly.loop_indices:
            col.data[li].color = (*rgb, 1.0)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.find("Color")
    rs = me.attributes.new("_RS_VERTEX", "FLOAT", "POINT")
    for i in range(len(mesh.verts)):
        rs.data[i].value = float(next_rs + i)
    me["rsPart"] = part
    me["rsPriority"] = 0
    me["rsRenderPriorities"] = [ADDED_PRIORITY] * len(me.polygons)
    me["rsTransparencies"] = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    groups = {}
    for i, ws in enumerate(mesh.weights):
        total = sum(ws.values())
        for bone, w in ws.items():
            if bone not in groups:
                groups[bone] = ob.vertex_groups.new(name=bone)
            groups[bone].add([i], w / total, "REPLACE")
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    print("BUILT", name, len(mesh.verts), "verts", len(me.polygons), "faces")
    return next_rs + len(mesh.verts)


def nearest_weights(body, ws, on, groups):
    """A lookup from a point to the weights of the nearest body vertex on the given bones."""
    near = [(v.co.copy(), ws[i]) for i, v in enumerate(body.data.vertices) if on[i] in groups]
    tree = KDTree(len(near))
    for i, (co, _w) in enumerate(near):
        tree.insert(co, i)
    tree.balance()
    return lambda p: near[tree.find(p)[1]][1]


def fcurves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def set_action(arm, name):
    arm.animation_data_create()
    action = bpy.data.actions[name]
    arm.animation_data.action = action
    if action.slots:
        arm.animation_data.action_slot = action.slots[0]


def skirt_joints(arm, sectors):
    """Adds the skirt's joints, resting where the pelvis rests, with no parent, and keys them in every
    action: one for each band below the waist (see SKIRT_BANDS) at each of sectors angles round the
    skirt (0 the front, clockwise seen from above, towards +X). Returns {(sector, follow): joint}.

    A joint follows the thighs as far as its band says, turning about his hips as they do. Which
    thigh it follows turns smoothly with its angle: at the sides its own side's, at the front whichever
    thigh is further forward and at the back whichever is further back, as a real skirt is pushed,
    blended between. A fixed mix of both thighs can't do that, and in his idle, with a knee forward,
    the thigh came out through the front. Neighbouring joints differ only a little, so the skirt doesn't
    tear where they meet, and the front and back swap thighs where the legs pass, at the same pose,
    so nothing jumps."""
    names, index = {}, SKIRT_FIRST_JOINT
    for _depth, w in SKIRT_BANDS:
        if w > 0:
            for k in range(sectors):
                names[(k, w)] = "group_%d" % index
                index += 1
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    src = arm.data.edit_bones[PELVIS]
    for name in names.values():
        b = arm.data.edit_bones.new(name)
        b.head, b.tail, b.roll = src.head.copy(), src.tail.copy(), src.roll
    bpy.ops.object.mode_set(mode="OBJECT")
    for name in names.values():
        arm.pose.bones[name].rotation_mode = "QUATERNION"
    hips = [arm.data.bones[LEFT_THIGH].head_local.copy(), arm.data.bones[RIGHT_THIGH].head_local.copy()]
    knees = {LEFT_THIGH: arm.data.bones[KNEES[LEFT_THIGH]].head_local.copy(),
             RIGHT_THIGH: arm.data.bones[KNEES[RIGHT_THIGH]].head_local.copy()}

    def deform(name):
        pb = arm.pose.bones[name]
        return pb.matrix @ pb.bone.matrix_local.inverted()

    def about(m, centre):
        """A motion as where it takes a centre, its rotation and its scale."""
        _loc, rot, scale = m.decompose()
        return m @ centre, rot, scale

    def blend(a, b, w):
        return a[0].lerp(b[0], w), a[1].slerp(b[1], w), a[2].lerp(b[2], w)

    centre = (hips[0] + hips[1]) / 2

    def rightward(k, knee_left, knee_right):
        """How far towards the right thigh (0 left, 1 right) the sector's joints follow: towards
        whichever knee reaches further in the sector's own direction, in his pelvis's frame, blended
        smoothly over SKIRT_SOFT so neighbouring sectors never jump."""
        a = 2 * math.pi * k / sectors
        d = Vector((math.sin(a), math.cos(a), 0.0))
        lead = ((knee_right - centre).dot(d) - (knee_left - centre).dot(d)) / SKIRT_SOFT
        return 1 / (1 + math.exp(-max(min(lead, 50), -50)))

    scene = bpy.context.scene
    for action in list(bpy.data.actions):
        set_action(arm, action.name)
        f0, f1 = (int(round(x)) for x in action.frame_range)
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            pelvis, left, right = deform(PELVIS), deform(LEFT_THIGH), deform(RIGHT_THIGH)
            inverse = pelvis.inverted()
            knee_left = inverse @ left @ knees[LEFT_THIGH]
            knee_right = inverse @ right @ knees[RIGHT_THIGH]
            for (k, w), name in names.items():
                r = rightward(k, knee_left, knee_right)
                hip = hips[0].lerp(hips[1], r)
                thigh = blend(about(left, hip), about(right, hip), r)
                carried = 1.0
                if SEATED:
                    # Seated, his thighs carry the front and sides as his lap; the back sits on the seat
                    a = 2 * math.pi * k / sectors
                    carried = min(max((math.cos(a) - SEAT_BACK) / (1 - SEAT_BACK) * 1.5, 0.0), 1.0)
                moved, rot, scale = blend(about(pelvis, hip), thigh, w * carried)
                motion = Matrix.Translation(moved) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal(scale.to_4d()) \
                    @ Matrix.Translation(-hip)
                pb = arm.pose.bones[name]
                pb.matrix = motion @ pb.bone.matrix_local
                for path in ("location", "rotation_quaternion", "scale"):
                    pb.keyframe_insert(path, frame=f)
        for fc in fcurves(action):
            if any('"%s"' % nm in fc.data_path for nm in names.values()):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    print("SKIRT JOINTS", len(names), "keyed in", len(bpy.data.actions), "clips")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    scene.frame_set(0)
    return names


def skirt(arm, body, on, next_rs, part):
    """The skirt, its petticoat ruffles, waistband, back bow and apron, as one part."""
    bvh = body_bvh(body, on, HIPS)
    hips = [v.co for v, g in zip(body.data.vertices, on) if g in HIPS and WAIST_Z - 0.5 * K < v.co.z < WAIST_Z]
    cx = (min(p.x for p in hips) + max(p.x for p in hips)) / 2
    cy = (min(p.y for p in hips) + max(p.y for p in hips)) / 2
    n = SKIRT_SIDES
    angles = [2 * math.pi * i / n for i in range(n)]
    zs = [WAIST_Z + (HEM_Z - WAIST_Z) * t for t in SKIRT_RINGS]

    def radial(a):
        return Vector((math.sin(a), math.cos(a), 0.0))

    def need(a, z, clearance=SKIRT_CLEARANCE):
        """How far out the skirt must be at this angle and height, allowing for the chord between
        ring vertices cutting inside the circle."""
        return max(outermost(bvh, Vector((cx, cy, z)), radial(a + d)) for d in (-math.pi / n, 0, math.pi / n)) \
            / math.cos(math.pi / n) + clearance

    # At each angle the fitted rings start at what he needs at their own heights, and wherever the
    # straight line between two of them cuts into him, both are pushed out, each by its share of the
    # shortfall, until nothing cuts in. The waist stays put, fitted close. The hem is also at least
    # SKIRT_FLARE times the waist and HEM_OVER_HIPS times the hips.
    steps = [s / 32 for s in range(1, 33)]

    def clearance(t):
        return WAIST_CLEARANCE + (SKIRT_CLEARANCE - WAIST_CLEARANCE) * min(t / SKIRT_FIT[1], 1.0)

    needs = {t: [need(a, WAIST_Z + (HEM_Z - WAIST_Z) * t, clearance(t)) for a in angles] for t in steps}
    fit = [[need(a, WAIST_Z, WAIST_CLEARANCE) for a in angles]]
    for t in SKIRT_FIT[1:]:
        fit.append([max(r, needs[min(steps, key=lambda x: abs(x - t))][i]) for i, r in enumerate(fit[-1])])
    for _ in range(500):
        short = 0.0
        for t in steps:
            k = min(max(kk for kk in range(len(SKIRT_FIT) - 1) if SKIRT_FIT[kk] < t), len(SKIRT_FIT) - 2)
            u = (t - SKIRT_FIT[k]) / (SKIRT_FIT[k + 1] - SKIRT_FIT[k])
            for i in range(n):
                d = needs[t][i] - (fit[k][i] + (fit[k + 1][i] - fit[k][i]) * u)
                if d > 1e-4:
                    short = max(short, d)
                    if k == 0:
                        fit[1][i] += d / u
                    else:
                        share = (1 - u) ** 2 + u ** 2
                        fit[k][i] += d * (1 - u) / share
                        fit[k + 1][i] += d * u / share
        if short < 1e-4:
            break
    for k in range(2, len(fit)):            # widening all the way down, so the front doesn't bulge
        fit[k] = [max(r, above) for r, above in zip(fit[k], fit[k - 1])]
    hip_rings = fit[-2]
    fit[-1] = [max(r, w * SKIRT_FLARE, h * HEM_OVER_HIPS) for r, w, h in zip(fit[-1], fit[0], hip_rings)]

    def profile(i, t):
        k = max(kk for kk in range(len(SKIRT_FIT) - 1) if SKIRT_FIT[kk] <= t + 1e-9) if t > 0 else 0
        k = min(k, len(SKIRT_FIT) - 2)
        u = (t - SKIRT_FIT[k]) / (SKIRT_FIT[k + 1] - SKIRT_FIT[k])
        bell = SKIRT_BELL * math.sin(math.pi * u) if k == len(SKIRT_FIT) - 2 else 0.0
        return fit[k][i] + (fit[k + 1][i] - fit[k][i]) * u + bell

    radius = [[profile(i, t) for i in range(n)] for t in SKIRT_RINGS]
    for k in range(1, len(zs)):
        for _ in range(2):
            radius[k] = [max(radius[k][i], (radius[k][i - 1] + 2 * radius[k][i] + radius[k][(i + 1) % n]) / 4)
                         for i in range(n)]
    print("SKIRT centre (%.3f %.3f) radius waist %.3f..%.3f hem %.3f..%.3f"
          % (cx, cy, min(radius[0]), max(radius[0]), min(radius[-1]), max(radius[-1])))

    def ring_point(k, i):
        a = angles[i % n]
        return Vector((cx, cy, zs[k])) + radial(a) * radius[k][i % n]

    def surface(a, z):
        """The skirt's surface at an angle and height, on its flat faces."""
        f = (a % (2 * math.pi)) / (2 * math.pi) * n
        i = int(f) % n
        f -= int(f)
        t = (WAIST_Z - z) / (WAIST_Z - HEM_Z)
        k = max(kk for kk in range(len(zs) - 1) if SKIRT_RINGS[kk] <= t + 1e-9) if t > 0 else 0
        k = min(k, len(zs) - 2)
        u = (t - SKIRT_RINGS[k]) / (SKIRT_RINGS[k + 1] - SKIRT_RINGS[k])
        top = ring_point(k, i).lerp(ring_point(k, i + 1), f)
        bottom = ring_point(k + 1, i).lerp(ring_point(k + 1, i + 1), f)
        return top.lerp(bottom, u)

    def out_of(p):
        return Vector((p.x - cx, p.y - cy, 0)).normalized()

    names = skirt_joints(arm, n)

    def weights(p):
        """The waist rides the spine and pelvis; below it each band of each skirt side rides a skirt
        joint of its own (see skirt_joints), the side's nearest."""
        t = min(max((WAIST_Z - p.z) / (WAIST_Z - HEM_Z), 0.0), 1.0)
        w = next(w for depth, w in SKIRT_BANDS if t <= depth + 1e-6)
        if w == 0:
            return WAIST_BONES
        k = int(round(math.atan2(p.x - cx, p.y - cy) / (2 * math.pi) * n)) % n
        return names[(k, w)]

    m = Mesh()

    def add(p):
        return m.add(p, weights(p))

    # The skirt itself, closed inside so it shows from below too
    rows = [[add(ring_point(k, i)) for i in range(n)] for k in range(len(zs))]
    for k in range(len(zs) - 1):
        for i in range(n):
            j = (i + 1) % n
            f = [rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]]
            m.face(f, DRESS_BLACK, out=out_of((m.verts[f[0]] + m.verts[f[2]]) / 2), both=True, inside=DRESS_INSIDE)

    # Petticoat ruffles under the hem: from just inside the hem, out and down, in tips and dips
    rng = random.Random(PETTICOAT_SEED)
    tops, bottoms = [], []
    for j in range(2 * n):
        a = 2 * math.pi * j / (2 * n)
        p = surface(a, HEM_Z)
        o = out_of(p)
        drop = PETTICOAT_DROP * (rng.uniform(0.8, 1.0) if j % 2 == 0 else rng.uniform(0.45, 0.6))
        tops.append(add(p - o * PETTICOAT_TUCK + Vector((0, 0, PETTICOAT_TUCK * 4))))
        bottoms.append(m.add(p + o * PETTICOAT_OUT * (1.0 if j % 2 == 0 else 0.6) - Vector((0, 0, drop)), weights(p)))
    for j in range(2 * n):
        jj = (j + 1) % (2 * n)
        f = [tops[j], tops[jj], bottoms[jj], bottoms[j]]
        m.face(f, WHITE if j % 2 == 0 else WHITE_SHADE, out=out_of((m.verts[f[0]] + m.verts[f[2]]) / 2),
               both=True, inside=WHITE_SHADE)

    # The waistband, standing just off the skirt's top
    upper = [add(surface(a, WAIST_Z + 0.01 * K) + radial(a) * 0.016 * K) for a in angles]
    lower = [add(surface(a, WAIST_Z - WAISTBAND) + radial(a) * 0.016 * K) for a in angles]
    for i in range(n):
        j = (i + 1) % n
        m.face([upper[i], upper[j], lower[j], lower[i]], WHITE, out=radial(angles[i] + math.pi / n))

    # The apron: a panel over the front, frilled round its sides and bottom
    sides = list(range(-APRON_SPAN, APRON_SPAN + 1))
    levels = list(range(APRON_BOTTOM_RING + 1))
    grid = []
    for k in levels:
        row = []
        for c in sides:
            p = ring_point(k, c) if k > 0 else surface(angles[c % n], WAIST_Z - WAISTBAND)
            # Below the top, on the skirt's own ring vertices' weights; the top row hangs under the waistband,
            # so it rides what the skirt does at its height rather than the waist ring's spine
            row.append(m.add(p + radial(angles[c % n]) * APRON_OFF, m.weights[rows[k][c % n]] if k > 0 else weights(p)))
        grid.append(row)
    bottom_z = zs[APRON_BOTTOM_RING]
    for r in range(len(levels) - 1):
        for c in range(len(sides) - 1):
            m.face([grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]], WHITE,
                   out=radial(math.pi * (sides[c] + sides[c + 1]) / n))
    edge = [grid[r][0] for r in range(len(levels))] + grid[-1][1:] + [grid[r][-1] for r in range(len(levels) - 2, -1, -1)]
    bottom = set(grid[-1])
    for e in range(1, len(edge) - 2):
        a, b = m.verts[edge[e]], m.verts[edge[e + 1]]
        mid = (a + b) / 2
        o = out_of(mid)
        if edge[e] in bottom and edge[e + 1] in bottom:
            away = Vector((0, 0, -1))
        else:
            away = Vector((o.y, -o.x, 0))
            if away.x * (mid.x - cx) < 0:
                away = -away
        tip = m.add(mid + away * APRON_FRILL * rng.uniform(0.8, 1.1) + o * 0.008 * K,
                    m.weights[edge[e + 1] if mid.z < bottom_z + 0.04 * K else edge[e]])
        m.face([edge[e], edge[e + 1], tip], WHITE_SHADE, out=o, both=True)

    # The bow at the back, above his tail: two loops either side of a knot, and two tails
    back = surface(math.pi, WAIST_Z - WAISTBAND / 2) + radial(math.pi) * 0.04 * K
    knot = add(back)
    side = Vector((1, 0, 0))
    for s in (-1, 1):
        tip = back + side * s * BACK_BOW
        ring = [add(tip + Vector((0, 0, 0.45 * BACK_BOW))), add(tip + Vector((0, -0.04 * K, 0))),
                add(tip - Vector((0, 0, 0.45 * BACK_BOW))), add(tip + Vector((0, 0.02 * K, 0)))]
        for i in range(4):
            m.face([knot, ring[i], ring[(i + 1) % 4]], WHITE, both=True, inside=WHITE_SHADE)
        root = add(back + side * s * 0.03 * K)
        foot_in = add(back + side * s * 0.07 * K + Vector((0, -0.04 * K, -BACK_TAIL)))
        foot_out = add(back + side * s * 0.16 * K + Vector((0, -0.04 * K, -BACK_TAIL * 0.9)))
        m.face([knot, root, foot_out, foot_in], WHITE_SHADE, both=True)

    return new_part(arm, "skirt", m, next_rs, part)


def small_bow(m, knot, size, color, weights, inside, facing_dir=Vector((0, 1, 0))):
    """Two flattened pyramids either side of a knot, thin enough to show from either side."""
    across = facing_dir.cross(Vector((0, 0, 1))).normalized()
    k = m.add(knot, weights)
    for side in (-1, 1):
        tip = knot + across * side * size
        ring = [m.add(tip + Vector((0, 0, 0.55 * size)), weights), m.add(tip + facing_dir * 0.3 * size, weights),
                m.add(tip + Vector((0, 0, -0.55 * size)), weights), m.add(tip - facing_dir * 0.2 * size, weights)]
        for i in range(4):
            m.face([k, ring[i], ring[(i + 1) % 4]], color, both=True, inside=inside)


def garters(arm, body, on, next_rs, part):
    """A white band round each thigh, frilled along its top, with a black bow on its front, and two
    black straps from it up under the skirt, on the thigh's own bone."""
    m = Mesh()
    rng = random.Random(5)
    for thigh in (LEFT_THIGH, RIGHT_THIGH):
        bvh = body_bvh(body, on, {thigh})
        pts = [v.co for v, g in zip(body.data.vertices, on) if g == thigh]
        sign = 1 if sum(p.x for p in pts) > 0 else -1

        def centre(z):
            # The thigh's vertices near the height, or the nearest few where its rings are coarse
            near = [p for p in pts if abs(p.z - z) < 0.12 * K]
            if len(near) < 8:
                near = sorted(pts, key=lambda p: abs(p.z - z))[:8]
            return Vector((sum(p.x for p in near) / len(near), sum(p.y for p in near) / len(near), z))

        def around(a, z, off):
            c = centre(z)
            d = Vector((math.sin(a), math.cos(a), 0))
            return c + d * ((outermost(bvh, c, d, 1.0) or 0.16 * K) / math.cos(math.pi / GARTER_SIDES) + off)

        angles = [2 * math.pi * i / GARTER_SIDES for i in range(GARTER_SIDES)]
        lo = [m.add(around(a, GARTER_BOTTOM, GARTER_OFF), thigh) for a in angles]
        hi = [m.add(around(a, GARTER_TOP, GARTER_OFF), thigh) for a in angles]
        for i in range(GARTER_SIDES):
            j = (i + 1) % GARTER_SIDES
            mid = (angles[i] + math.pi / GARTER_SIDES)
            m.face([lo[i], lo[j], hi[j], hi[i]], WHITE, out=Vector((math.sin(mid), math.cos(mid), 0)))
            tip = m.add(around(mid, GARTER_TOP, GARTER_OFF + 0.008 * K) + Vector((0, 0, GARTER_FRILL * rng.uniform(0.6, 1.0))), thigh)
            m.face([hi[i], hi[j], tip], WHITE_SHADE, out=Vector((math.sin(mid), math.cos(mid), 0)), both=True)
        bow_angle = sign * math.pi / 6
        front = around(bow_angle, (GARTER_BOTTOM + GARTER_TOP) / 2, GARTER_OFF + 0.02 * K)
        small_bow(m, front, GARTER_BOW, DRESS_BLACK, thigh, DRESS_BLACK,
                  Vector((math.sin(bow_angle), math.cos(bow_angle), 0)))
        for a in (0.0, sign * math.pi / 2):          # front, and outer side
            d = Vector((math.cos(a), -math.sin(a), 0)) * STRAP_WIDTH / 2
            b0, b1 = around(a, GARTER_TOP, GARTER_OFF + 0.004 * K), around(a, HEM_Z + 0.12 * K, GARTER_OFF + 0.004 * K)
            f = [m.add(b0 - d, thigh), m.add(b0 + d, thigh), m.add(b1 + d, thigh), m.add(b1 - d, thigh)]
            m.face(f, DRESS_BLACK, out=Vector((math.sin(a), math.cos(a), 0)), both=True)
    return new_part(arm, "garters", m, next_rs, part)


def headband(arm, body, on, next_rs, part):
    """A frilled band over the top of the head between the horns, closed so it shows from both
    sides: a wedge whose front and back meet in a line against the head. It hugs the mane: at each
    angle its base stands BAND_GAP off the head's outermost surface, smoothed."""
    bvh = body_bvh(body, on, {HEAD}, keep=lambda f: face_hsl(body, f) not in HORN)
    head_verts = [v.co for v, g in zip(body.data.vertices, on) if g == HEAD]
    xs = [p.x for p in head_verts]
    half = (max(xs) - min(xs)) / 2
    mid = (max(xs) + min(xs)) / 2
    top = max(p.z for p in head_verts if abs(p.x - mid) < half * 0.25)
    centre = Vector((mid, sum(p.y for p in head_verts) / len(head_verts) + BAND_Y, top - BAND_HEIGHT))

    def tilt(t):
        return Matrix.Rotation(math.radians(BAND_TILT + BAND_WRAP * (t / BAND_ARC) ** 2), 3, "X")

    def reach_at(t):
        a = math.radians(t)
        out = tilt(t) @ Vector((math.sin(a), 0, math.cos(a)))
        return out, max(outermost(bvh, centre + tilt(t) @ Vector((0, y, 0)), out, 1.0)
                        for y in (BAND_DEPTH / 2, -BAND_DEPTH / 2))

    grid = [-BAND_ARC + 2 * BAND_ARC * i / BAND_SEGS for i in range(BAND_SEGS + 1)]
    reach = [reach_at(t)[1] for t in grid]
    hits = [i for i, r in enumerate(reach) if r > 0]
    for i, r in enumerate(reach):
        if r == 0:
            lo = max((j for j in hits if j < i), default=min(hits))
            hi = min((j for j in hits if j > i), default=max(hits))
            reach[i] = reach[lo] if lo == hi else reach[lo] + (reach[hi] - reach[lo]) * (i - lo) / (hi - lo)
    for _ in range(BAND_SMOOTH):
        reach = [max(reach[i], (reach[max(i - 1, 0)] + 2 * reach[i] + reach[min(i + 1, BAND_SEGS)]) / 4)
                 for i in range(BAND_SEGS + 1)]
    radius = [r + BAND_GAP for r in reach]
    print("HEADBAND centre (%.3f %.3f %.3f) inner radius %.3f..%.3f" % (*centre, min(radius), max(radius)))

    def at(t, out, y):
        f = min(max((t - grid[0]) / (grid[1] - grid[0]), 0), BAND_SEGS - 1e-9)
        i = int(f)
        r = radius[i] + (radius[min(i + 1, BAND_SEGS)] - radius[i]) * (f - i)
        a = math.radians(t)
        return centre + tilt(t) @ Vector((math.sin(a) * (r + out), y, math.cos(a) * (r + out)))

    m = Mesh()
    n = BAND_SEGS + 1
    step = 2 * BAND_ARC / BAND_SEGS
    ts = [-BAND_ARC + step * i for i in range(n)]
    rng = random.Random(FRILL_SEED)
    edge = []
    for i, t in enumerate(ts):
        if i in (0, BAND_SEGS):
            edge.append((t, 0.0, 0.0))
        elif i % 2:
            edge.append((t + rng.uniform(-FRILL_JITTER, FRILL_JITTER) * step,
                         FRILL * rng.uniform(FRILL_LOW, 1.0), rng.uniform(-FRILL_FOLD, FRILL_FOLD)))
        else:
            edge.append((t, FRILL * rng.uniform(0.0, 0.2), rng.uniform(-FRILL_FOLD, FRILL_FOLD) * 0.3))
    base = [m.add(at(t, 0, 0), HEAD) for t in ts]
    band_f = [m.add(at(t, BAND_WIDTH * 4, BAND_DEPTH / 2), HEAD) for t in ts]
    band_b = [m.add(at(t, BAND_WIDTH * 4, -BAND_DEPTH / 2), HEAD) for t in ts]
    outf = [m.add(at(t, BAND_WIDTH * 4 + h, BAND_DEPTH / 2 + fold), HEAD) for t, h, fold in edge]
    outb = [m.add(at(t, BAND_WIDTH * 4 + h, -BAND_DEPTH / 2 + fold), HEAD) for t, h, fold in edge]
    for i in range(BAND_SEGS):
        j = i + 1
        fwd = tilt(ts[i]) @ Vector((0, 1, 0))
        up = tilt(ts[i]) @ Vector((math.sin(math.radians(ts[i])), 0, math.cos(math.radians(ts[i]))))
        # The black band against the head, then the white frill above it
        m.face([base[i], band_f[i], band_f[j], base[j]], BAND_COLOR, out=fwd)
        m.face([base[j], band_b[j], band_b[i], base[i]], BAND_COLOR, out=-fwd)
        m.face([band_f[i], outf[i], outf[j], band_f[j]], FRILL_COLOR, out=fwd)
        m.face([band_b[j], outb[j], outb[i], band_b[i]], FRILL_COLOR, out=-fwd)
        m.face([outf[i], outb[i], outb[j], outf[j]], FRILL_COLOR, out=up)
    m.face([base[0], band_b[0], band_f[0]], BAND_COLOR, out=tilt(ts[0]) @ Vector((-1, 0, 0)))
    m.face([base[-1], band_f[-1], band_b[-1]], BAND_COLOR, out=tilt(ts[-1]) @ Vector((1, 0, 0)))
    return new_part(arm, "headband", m, next_rs, part)


def neckline_z(degrees):
    """The neckline's height at an angle round the chest from the front, either side."""
    a = abs((degrees + 180) % 360 - 180)
    for (a0, z0), (a1, z1) in zip(NECKLINE, NECKLINE[1:]):
        if a <= a1:
            return z0 + (z1 - z0) * (a - a0) / (a1 - a0)
    return NECKLINE[-1][1]


def chest_axis(body, on):
    """The chest's centre line, round which the neckline is measured, in x and y: the middle of its
    bounds."""
    lo, hi = min(z for _a, z in NECKLINE), max(z for _a, z in NECKLINE)
    pts = [v.co for v, g in zip(body.data.vertices, on) if g in SPINE | CLAVICLES and lo - 0.1 * K < v.co.z < hi + 0.1 * K]
    return Vector(((min(p.x for p in pts) + max(p.x for p in pts)) / 2,
                   (min(p.y for p in pts) + max(p.y for p in pts)) / 2, 0.0))


def neckline(arm, body, ws, on, next_rs, part):
    """The bodice's top: a white ruffle round the neckline and a small white bow at its centre, then
    a ruffled white collar round the neck with a black bow tie. Each vertex takes the weights of the
    body vertex nearest it."""
    groups = SPINE | CLAVICLES | NECK
    bvh = body_bvh(body, on, groups)
    near = nearest_weights(body, ws, on, groups)
    chest = chest_axis(body, on)
    rng = random.Random(NECK_FRILL_SEED)
    m = Mesh()

    def add(p):
        return m.add(p, near(p))

    def out(a):
        return Vector((math.sin(math.radians(a)), math.cos(math.radians(a)), 0.0))

    def reach(a, z, axis=chest, tree_=bvh):
        return outermost(tree_, Vector((axis.x, axis.y, z)), out(a), 1.5)

    steps = list(range(-180, 180, NECK_FRILL_STEP))
    halves = [a + h for a in steps for h in (0, NECK_FRILL_STEP / 2)]
    reach_at = {a: reach(a, neckline_z(a)) for a in halves}
    known = [a for a in halves if reach_at[a] > 0]
    for a in halves:
        if reach_at[a] == 0:
            before = max((b for b in known if b < a), default=known[-1])
            after = min((b for b in known if b > a), default=known[0])
            reach_at[a] = (reach_at[before] + reach_at[after]) / 2

    def at(a, dz, off):
        return Vector((chest.x, chest.y, neckline_z(a) + dz)) + out(a) * (reach_at[a] + off)

    base = [add(at(a, -0.012 * K, 0.012 * K)) for a in steps]
    top = []
    for i, a in enumerate(halves):
        tip = i % 2 == 0
        height = NECK_FRILL * (rng.uniform(0.75, 1.0) if tip else rng.uniform(0.35, 0.5))
        top.append(add(at(a, height, 0.012 * K + NECK_FRILL_OUT * (1.0 if tip else 0.6))))
    count = len(steps)
    for i in range(count):
        j = (i + 1) % count
        t0, t1, t2 = top[2 * i], top[2 * i + 1], top[(2 * i + 2) % (2 * count)]
        shade = WHITE if i % 2 == 0 else WHITE_SHADE
        for f in ([base[i], t0, t1], [base[i], t1, base[j]], [base[j], t1, t2]):
            centre = sum((m.verts[x] for x in f), Vector()) / 3
            m.face(f, shade, out=Vector((centre.x - chest.x, centre.y - chest.y, 0)), both=True, inside=WHITE_SHADE)
    small_bow(m, at(0, -0.004 * K, 0.032 * K), NECK_BOW, WHITE, near(at(0, 0, 0)), WHITE_SHADE)

    # The collar: an arc across the top of the chest under the jaw, ruffled down and out, with the
    # bow tie at its centre
    sides = [-COLLAR_ARC + 2 * COLLAR_ARC * i / COLLAR_SIDES for i in range(COLLAR_SIDES + 1)]
    reach_collar = [reach(a, COLLAR_Z) for a in sides]
    known = [r for r in reach_collar if r > 0]
    reach_collar = [r if r > 0 else max(known) for r in reach_collar]
    print("NECKLINE chest (%.3f %.3f) collar z %.3f reach %.3f..%.3f"
          % (chest.x, chest.y, COLLAR_Z, min(reach_collar), max(reach_collar)))

    def collar_at(a, r, dz, off):
        return Vector((chest.x, chest.y, COLLAR_Z + dz)) + out(a) * (r + off)

    ring = [add(collar_at(a, r, 0.024 * K, 0.016 * K)) for a, r in zip(sides, reach_collar)]
    hem = []
    for i in range(2 * COLLAR_SIDES + 1):
        a = -COLLAR_ARC + COLLAR_ARC * i / COLLAR_SIDES
        r = (reach_collar[i // 2] + reach_collar[min(i // 2 + (i % 2), COLLAR_SIDES)]) / 2
        tip = i % 2 == 0
        hem.append(add(collar_at(a, r, -COLLAR_DROP * (1.0 if tip else 0.6),
                                 0.016 * K + COLLAR_OUT * (1.0 if tip else 0.7))))
    for i in range(COLLAR_SIDES):
        h0, h1, h2 = hem[2 * i], hem[2 * i + 1], hem[2 * i + 2]
        for f in ([ring[i], h0, h1], [ring[i], h1, ring[i + 1]], [ring[i + 1], h1, h2]):
            centre = sum((m.verts[x] for x in f), Vector()) / 3
            m.face(f, WHITE, out=Vector((centre.x - chest.x, centre.y - chest.y, 0)), both=True, inside=WHITE_SHADE)
    front = collar_at(0, reach_collar[COLLAR_SIDES // 2], 0.0, 0.016 * K + COLLAR_OUT * 0.6)
    small_bow(m, front + Vector((0, 0.02 * K, 0)), BOW_SIZE, BOW_COLOR, near(front), BOW_COLOR)
    return new_part(arm, "neckline", m, next_rs, part)


def basis(axis):
    """Two unit vectors at right angles to axis and each other."""
    a = axis.normalized()
    u = a.cross(Vector((0, 1, 0)) if abs(a.y) < 0.9 else Vector((1, 0, 0))).normalized()
    return u, a.cross(u)


def ruffle(m, centre, axis, radius, toward, length, flare, sides, weights, rng):
    """A ring of ruffles round an axis: from a ring of the given radius, tips and dips reaching along
    toward (+1 or -1 along the axis) and leaning out by flare, shown inside and out."""
    u, w = basis(axis)
    a = axis.normalized() * toward

    def spoke(t):
        return u * math.cos(t) + w * math.sin(t)

    ring = [m.add(centre + spoke(2 * math.pi * i / sides) * radius, weights) for i in range(sides)]
    rim = []
    for i in range(2 * sides):
        tip = i % 2 == 0
        t = math.pi * i / sides
        k = rng.uniform(0.8, 1.0) if tip else rng.uniform(0.45, 0.6)
        rim.append(m.add(centre + a * length * k + spoke(t) * (radius + flare * (1.0 if tip else 0.6)), weights))
    for i in range(sides):
        j = (i + 1) % sides
        r0, r1, r2 = rim[2 * i], rim[2 * i + 1], rim[(2 * i + 2) % (2 * sides)]
        for f in ([ring[i], r0, r1], [ring[i], r1, ring[j]], [ring[j], r1, r2]):
            mid = sum((m.verts[x] for x in f), Vector()) / 3 - centre
            m.face(f, WHITE if i % 2 == 0 else WHITE_SHADE, out=mid - axis.normalized() * mid.dot(axis.normalized()),
                   both=True, inside=WHITE_SHADE)


def sleeves(arm, body, on, next_rs, part):
    """The puffed cap sleeves over his shoulders, on the upper arms' bones, frilled at their hems.
    The top ring rides the collarbone half, so the sleeve doesn't tear from the shoulder."""
    rng = random.Random(RUFFLE_SEED)
    m = Mesh()
    bones_ = arm.data.bones
    verts = [(v.co, g) for v, g in zip(body.data.vertices, on)]
    for clavicle, upper, elbow in SLEEVE_ARMS:
        top, bottom = bones_[upper].head_local, bones_[elbow].head_local
        axis = bottom - top
        u, w = basis(axis)
        flesh = [co for co, g in verts if g == upper]

        def reach(t, span=0.12):
            """How far the arm reaches from the line near a point along it: most of the way out, so a
            stray tuft doesn't balloon the sleeve."""
            c = top + axis * max(t, 0.02)
            near = sorted(((co - c) - axis.normalized() * (co - c).dot(axis.normalized())).length
                          for co in flesh if abs((co - c).dot(axis.normalized())) < span * axis.length)
            return near[int(len(near) * 0.85)] if near else 0.25 * K

        rings = []
        for k, (t, puff) in enumerate(SLEEVE_RINGS):
            c = top + axis * t
            r = reach(t) / math.cos(math.pi / SLEEVE_SIDES) + SLEEVE_GAP + puff * K
            weights = {upper: 0.5, clavicle: 0.5} if k == 0 else upper
            rings.append([m.add(c + (u * math.cos(2 * math.pi * i / SLEEVE_SIDES) + w * math.sin(2 * math.pi * i / SLEEVE_SIDES)) * r,
                                weights) for i in range(SLEEVE_SIDES)])
        print("SLEEVE", upper, "radius", " ".join("%.3f" % ((m.verts[ring[0]] - (top + axis * t)).length)
                                                  for ring, (t, _p) in zip(rings, SLEEVE_RINGS)))
        for k in range(len(rings) - 1):
            for i in range(SLEEVE_SIDES):
                j = (i + 1) % SLEEVE_SIDES
                f = [rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]]
                mid = sum((m.verts[x] for x in f), Vector()) / 4 - top
                m.face(f, DRESS_BLACK, out=mid - axis.normalized() * mid.dot(axis.normalized()),
                       both=True, inside=DRESS_INSIDE)
        t_hem, _ = SLEEVE_RINGS[-1]
        hem_r = (m.verts[rings[-1][0]] - (top + axis * t_hem)).length
        ruffle(m, top + axis * t_hem, axis, hem_r * 0.95, 1, SLEEVE_FRILL, 0.024 * K, SLEEVE_SIDES, upper, rng)
    return new_part(arm, "sleeves", m, next_rs, part)


def smooth_thighs(arm, body, on):
    """Pulls the spiky fur tufts of his thighs in towards the hip to knee line, so the bare skin reads
    as a smooth thigh: no vertex further out than THIGH_SMOOTH of its band's vertices."""
    moved = 0
    for thigh, knee in KNEES.items():
        top, bottom = arm.data.bones[thigh].head_local, arm.data.bones[knee].head_local
        a = (bottom - top).normalized()
        members = [v for v, g in zip(body.data.vertices, on) if g == thigh]

        def split(co):
            d = co - top
            along = d.dot(a)
            return along, d - a * along

        bands = {}
        for v in members:
            along, out = split(v.co)
            bands.setdefault(int(along // THIGH_BAND), []).append(out.length)
        caps = {k: sorted(r)[int(len(r) * THIGH_SMOOTH)] for k, r in bands.items()}
        for v in members:
            along, out = split(v.co)
            cap = caps[int(along // THIGH_BAND)]
            if out.length > cap:
                v.co = top + a * along + out.normalized() * cap
                moved += 1
        print("THIGH", thigh, "caps", " ".join("%.3f" % caps[k] for k in sorted(caps)))
    print("THIGHS pulled in", moved, "vertices")


def shape_bust(body, on):
    """Swells the chest into a modest bust: front chest vertices pushed forward, most at each
    centre, fading smoothly away from it."""
    moved = 0
    for v, g in zip(body.data.vertices, on):
        if g not in BUST_BONES or v.co.y < BUST_FRONT_Y:
            continue
        push = 0.0
        for side in (-1, 1):
            dx = (v.co.x - side * BUST_X) / BUST_SPREAD_X
            dz = (v.co.z - BUST_Z) / BUST_SPREAD_Z
            push = max(push, math.exp(-(dx * dx + dz * dz)))
        if push > 0.02:
            v.co.y += BUST_FORWARD * push
            moved += 1
    print("BUST moved", moved, "vertices")


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    scene.render.fps_base = 1.0

    arm, parts = import_glb(YAMA)
    arm.animation_data_create()
    arm.animation_data.action = None
    scene.frame_set(0)
    body = next(o for o in parts if o.name.startswith(BODY_PART))
    ws = weights_of(body)
    on = heaviest(ws)
    next_rs = 1 + max(int(round(d.value)) for o in parts for d in o.data.attributes["_RS_VERTEX"].data)
    next_part = 1 + max(int(o.data["rsPart"]) for o in parts)

    # His torso as the bodice: black below the neckline; his thighs bare red skin
    me = body.data
    chest = chest_axis(body, on)
    paints = {"dress": [], "skin light": [], "skin dark": []}
    for p in me.polygons:
        gs = {on[v] for v in p.vertices}
        h = face_hsl(body, p.index)
        z = p.center.z
        if gs <= THIGHS:
            lum = h & 127
            paints["skin dark" if lum < 10 else "skin light"].append(p.index)
        elif (gs <= SPINE | CLAVICLES and not gs & NECK) or (
                gs <= SPINE | CLAVICLES | WING_ROOTS | UPPER_ARMS and p.center.y < BACK_Y and abs(p.center.x) < 0.6 * K):
            # The front by its bones; the back between the wings by where it is, as it rides the wings
            a = math.degrees(math.atan2(p.center.x - chest.x, p.center.y - chest.y))
            if z < neckline_z(a):
                paints["dress"].append(p.index)
    colors = {"dress": DRESS_BLACK, "skin light": SKIN_LIGHT, "skin dark": SKIN_DARK}
    for k, faces in paints.items():
        paint(body, faces, colors[k])
        print("PAINTED", k, len(faces))
    shape_bust(body, on)
    smooth_thighs(arm, body, on)

    next_rs = skirt(arm, body, on, next_rs, next_part)
    next_rs = garters(arm, body, on, next_rs, next_part + 1)
    next_rs = headband(arm, body, on, next_rs, next_part + 2)
    next_rs = neckline(arm, body, ws, on, next_rs, next_part + 3)
    next_rs = sleeves(arm, body, on, next_rs, next_part + 4)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    export(OUT)
    if OUT_PET is None:
        return

    # Yami is his geometry at pet size, without the boss's flame effect. His original vertex numbers,
    # carried by _RS_VERTEX, have to run on without a gap where the effect was, or the converter
    # can't weld by them and welds by position instead
    for ob in [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(EFFECT_PARTS)]:
        bpy.data.objects.remove(ob)
    meshes = [o.data for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]
    used = sorted({int(round(d.value)) for me in meshes for d in me.attributes["_RS_VERTEX"].data})
    compact = {v: i for i, v in enumerate(used)}
    for me in meshes:
        for d in me.attributes["_RS_VERTEX"].data:
            d.value = float(compact[int(round(d.value))])
    export(OUT_PET)


def build_chathead():
    """Yama's dialogue head - the one NPC 124 has, which the dialogue's NPC 123 turns into - with
    the frilled headband between his horns. Its emotes are the game's own."""
    global HEAD, HORN, BAND_HEIGHT
    HEAD = CHATHEAD_JOINT
    HORN = HORN | CHATHEAD_HORN
    # His mane rises to a spike on top, so the band's centre is measured from well below it, at his
    # horns, to arc over the head between them rather than perch on the spike
    BAND_HEIGHT = CHATHEAD_BAND_HEIGHT
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 50
    scene.render.fps_base = 1.0
    arm, parts = import_glb(CHATHEAD)
    arm.animation_data_create()
    arm.animation_data.action = None
    scene.frame_set(0)
    head = parts[0]
    on = heaviest(weights_of(head))
    next_rs = 1 + max(int(round(d.value)) for d in head.data.attributes["_RS_VERTEX"].data)
    # The headband is a part of its own, so the head becomes part 0 for the converter to keep its
    # faces first
    head.data["rsPart"] = 0
    headband(arm, head, on, next_rs, 1)
    os.makedirs(os.path.dirname(OUT_CHATHEAD), exist_ok=True)
    export(OUT_CHATHEAD)


def export(path):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_yup=True,
        export_vertex_color="ACTIVE",
        export_attributes=True,
        export_extras=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=False,
        export_draco_mesh_compression_enable=False,
        export_def_bones=False,
        export_leaf_bone=False,
    )
    print("WROTE", path)


if __name__ == "__main__":
    subject = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "chathead" in subject:
        build_chathead()
    else:
        if "throne" in subject:
            use_throne()
        build()
