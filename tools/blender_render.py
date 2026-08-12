"""Headless Blender (5.x) renderer for the U3T Medium figures.

Blender is an external dependency (5.x tested); it is not installed by pip.

Usage, from the repository root:
  blender -b --factory-startup -noaudio --python tools/blender_render.py --           build/shots.json build/render_raw [name_filter]

`name_filter` is an optional substring: only shots whose name contains it are
rendered (handy for re-shooting a single figure).
"""
import json
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SHOTS_JSON, OUT_DIR = argv[0], argv[1]
FILTER = argv[2] if len(argv) > 2 else None
os.makedirs(OUT_DIR, exist_ok=True)

COLORS = {  # linear RGB
    "tan": (0.585, 0.368, 0.147, 1.0),
    "blue": (0.119, 0.262, 0.522, 1.0),
}


def make_material(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.6
    return mat


def import_stl(path):
    before = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=path)
    except AttributeError:
        bpy.ops.import_mesh.stl(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.samples = 64
    scn.cycles.use_denoising = True
    scn.cycles.device = "CPU"
    scn.render.film_transparent = True
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGBA"
    scn.view_settings.view_transform = "Standard"
    # world fill light
    world = bpy.data.worlds.new("World")
    scn.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs[1].default_value = 0.55
    # key light
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    scn.collection.objects.link(sun)
    sun.data.energy = 2.6
    sun.data.angle = 0.30
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = Vector((-0.45, 0.32, -1.0)).normalized().to_track_quat("-Z", "Y")
    # rim light for edge definition
    rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "SUN"))
    scn.collection.objects.link(rim)
    rim.data.energy = 0.9
    rim.data.angle = 0.5
    rim.rotation_mode = "QUATERNION"
    rim.rotation_quaternion = Vector((0.55, -0.5, -0.7)).normalized().to_track_quat("-Z", "Y")
    return scn


shots = json.load(open(SHOTS_JSON))
for shot in shots:
    if FILTER and FILTER not in shot["name"]:
        continue
    scn = clear_scene()
    mats = {k: make_material(k, v) for k, v in COLORS.items()}
    for path, matname in shot["stls"]:
        for obj in import_stl(path):
            obj.data.materials.clear()
            obj.data.materials.append(mats[matname])
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scn.collection.objects.link(cam)
    scn.camera = cam
    c = shot["cam"]
    cam.location = Vector(c["loc"])
    if c["type"] == "ORTHO":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = c["ortho_scale"]
    else:
        cam_data.lens = c.get("lens", 60.0)
        cam_data.sensor_width = 36.0
    cam_data.clip_end = 5000.0
    direction = Vector(c["target"]) - cam.location
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    scn.render.resolution_x, scn.render.resolution_y = shot["res"]
    scn.render.filepath = os.path.join(OUT_DIR, shot["name"] + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", shot["name"], flush=True)
print("ALL DONE")
