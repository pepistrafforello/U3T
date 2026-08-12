"""Pose the verified STLs and emit shot definitions for the Blender render pass."""
import json
import os

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STL = os.path.join(ROOT, "stl")
BUILD = os.path.join(ROOT, "build")
WORK = os.path.join(BUILD, "posed")
os.makedirs(WORK, exist_ok=True)

D_HAT = np.array([0.7, 0.7, 1.0]) / np.linalg.norm([0.7, 0.7, 1.0])
E = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
C_AX = np.array([105.0, -105.0, -103.5])

bottom = trimesh.load(os.path.join(STL, "U3T_bottom.stl"))
top = trimesh.load(os.path.join(STL, "U3T_top.stl"))
top_print = trimesh.load(os.path.join(STL, "U3T_top_print.stl"))
r_bottom = trimesh.load(os.path.join(STL, "U3T_rot_bottom.stl"))
r_top = trimesh.load(os.path.join(STL, "U3T_rot_top.stl"))
r_top_print = trimesh.load(os.path.join(STL, "U3T_rot_top_print.stl"))


def save(mesh, name):
    p = os.path.join(WORK, name + ".stl")
    mesh.export(p)
    return p


def slid(mesh, t):
    m = mesh.copy(); m.apply_translation(D_HAT * t); return m


def rotated(mesh, deg):
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), E, point=C_AX))
    return m


paths = {
    "bottom": save(bottom, "bottom"),
    "top": save(top, "top"),
    "top_print": save(top_print, "top_print"),
    "r_bottom": save(r_bottom, "r_bottom"),
    "r_top": save(r_top, "r_top"),
    "r_top_print": save(r_top_print, "r_top_print"),
    "top_ex": save(slid(top, 42), "top_ex"),
    "top_s12": save(slid(top, 12), "top_s12"),
    "top_s30": save(slid(top, 30), "top_s30"),
    "r_top_ex": save(rotated(r_top, 14), "r_top_ex"),
    "r_top_s6": save(rotated(r_top, 6), "r_top_s6"),
    "r_top_s14": save(rotated(r_top, 14), "r_top_s14"),
}


def cam_for(meshes, elev, azim, lens=60.0, margin=1.12, ortho=None):
    pts = np.concatenate([m.bounds for m in meshes])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    c = (lo + hi) / 2
    r = np.linalg.norm(hi - lo) / 2
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    if ortho is not None:
        loc = c + d * 500.0
        return dict(loc=loc.tolist(), target=c.tolist(), type="ORTHO", ortho_scale=ortho)
    fov2 = np.arctan(18.0 / lens)
    dist = r * margin / np.tan(fov2)
    loc = c + d * dist
    return dict(loc=loc.tolist(), target=c.tolist(), type="PERSP", lens=lens)


M = {"bottom": [bottom], "top": [top], "top_print": [top_print],
     "r_bottom": [r_bottom], "r_top": [r_top], "r_top_print": [r_top_print],
     "top_ex": [slid(top, 42)], "top_s12": [slid(top, 12)], "top_s30": [slid(top, 30)],
     "r_top_ex": [rotated(r_top, 14)], "r_top_s6": [rotated(r_top, 6)],
     "r_top_s14": [rotated(r_top, 14)]}

shots = []


def shot(name, parts, elev, azim, res, lens=60.0, margin=1.12, ortho=None):
    meshes = sum((M[p] for p, _ in parts), [])
    shots.append(dict(
        name=name,
        stls=[[paths[p], mat] for p, mat in parts],
        cam=cam_for(meshes, elev, azim, lens=lens, margin=margin, ortho=ortho),
        res=res,
    ))


# straight edition
shot("s_assembled", [("bottom", "tan"), ("top", "blue")], 26, -60, [1600, 1150])
shot("s_exploded", [("bottom", "tan"), ("top_ex", "blue")], 22, -60, [1600, 1300], margin=1.06)
shot("s_bottom", [("bottom", "tan")], 34, -55, [1600, 1150])
shot("s_top_flipped", [("top_print", "blue")], 34, -55, [1600, 1150])
shot("s_interface", [("bottom", "tan")], 76, -90, [1600, 1400], margin=1.05)
for nm, az in (("front", -90), ("right", 0), ("back", 90), ("left", 180)):
    shot(f"s_side_{nm}", [("bottom", "tan"), ("top", "blue")], 0, az, [1500, 300], ortho=108)
for t, nm in ((0, "a"), (12, "b"), (30, "c")):
    key = {0: "top", 12: "top_s12", 30: "top_s30"}[t]
    shot(f"s_seq_{nm}", [("bottom", "tan"), (key, "blue")], 22, -55, [1100, 950], margin=1.06)

# rotation edition
shot("r_bottomv", [("r_bottom", "tan")], 34, -55, [1600, 1150])
shot("r_exploded", [("r_bottom", "tan"), ("r_top_ex", "blue")], 22, -60, [1600, 1300], margin=1.06)
shot("r_interface", [("r_bottom", "tan")], 76, -90, [1600, 1400], margin=1.05)
for nm, az in (("front", -90), ("right", 0), ("back", 90), ("left", 180)):
    shot(f"r_side_{nm}", [("r_bottom", "tan"), ("r_top", "blue")], 0, az, [1500, 300], ortho=108)
for d, nm in ((0, "a"), (6, "b"), (14, "c")):
    key = {0: "r_top", 6: "r_top_s6", 14: "r_top_s14"}[d]
    shot(f"r_seq_{nm}", [("r_bottom", "tan"), (key, "blue")], 22, -55, [1100, 950], margin=1.06)

with open(os.path.join(BUILD, "shots.json"), "w") as f:
    json.dump(shots, f, indent=1)
print(f"{len(shots)} shots, {len(paths)} posed STLs written")
