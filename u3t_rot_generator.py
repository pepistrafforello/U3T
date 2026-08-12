"""
U3T rotation edition
--------------------
Same puzzle contract as the straight edition (identical dovetail seam on all four
faces, hidden QR + title interface), but the two parts separate by a ROTATION
about an external axis — the "extrusion along a curve of constant curvature"
from the original notes, done exactly.

Axis A: direction e = (1,1,0)/sqrt(2), through C = (105, -105, -103.5).
 - orbit planes are perpendicular to e, i.e. parallel to no side face;
 - the apex plane (vertical plane through A: x - y = 210) misses the block, so
   every orbit rises monotonically inside the block -> any horizontal plane is
   crossed once per orbit and flat band / plateau / relief tops remain valid;
 - the axis is far enough away that orbit slopes stay in ~43..61 deg over every
   wall-bearing region (printable walls, decent key depth on all four faces).

Construction: identical pipeline to u3t_generator, with the linear shear
replaced by the cylindrical "bend map" (vertical design lines <-> orbits) and
every footprint defined as the PRE-IMAGE of its true real-space position, so
face seams and interface content land exactly where designed.
"""

import json
import os

import numpy as np
import shapely
import shapely.affinity as saff
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from u3t_generator import (
    L, H, BAND_Z, CLR, TITLE, SUBTITLE, SIGNATURE, TITLE_BOX, SUB_BOX,
    buffered, polys_of, text_geometry, fit_into_box, qr_geometry, stock_box,
    clean_thin, content_offset,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(ROOT, "stl")
REPORTS = os.path.join(ROOT, "verification")
os.makedirs(STL, exist_ok=True)
os.makedirs(REPORTS, exist_ok=True)

# ------------------------------ rotation setup -------------------------------
SQ2 = np.sqrt(2.0)
E = np.array([1.0, 1.0, 0.0]) / SQ2      # axis direction
G = np.array([1.0, -1.0, 0.0]) / SQ2     # horizontal, perpendicular to axis
ZAX = np.array([0.0, 0.0, 1.0])
C = np.array([105.0, -105.0, -103.5])    # axis point: apex plan line x - y = 210

KEY_Z0R, KEY_Z1R = 7.5, 12.0             # key: band -> top (4.5 mm tall)
KEY_NECK_ZR = 8.8                        # neck before the flare: the shallow (far)
                                         # faces have depth ratio ~0.44, so the lip
                                         # starts at 0.44 x 1.3 = 0.57 mm depth
KEY_HW0R, KEY_HW1R = 6.0, 10.0           # same widths as the straight edition
KEY_RAIL_R = 8.0
PLAT_TOP_ZR = 11.0                       # plateau top (real plane)
PLAT_SQ = (20.0, 20.0, 80.0, 80.0)       # plateau square in REAL plan at z=11
QR_TOP_ZR = 12.2
TXT_TOP_ZR = 12.0


def preimage_plan(P):
    """Real 3D points (N,3) -> design plan (N,2): anchor of each orbit at z=0."""
    P = np.asarray(P, dtype=float)
    r = P - C
    w = r @ E
    a = r @ G
    b = P[:, 2] - C[2]
    rho = np.hypot(a, b)
    phib = np.arcsin(np.clip(-C[2] / rho, -1.0, 1.0))  # angle at z = 0
    base = (C + w[:, None] * E
            + rho[:, None] * (-np.cos(phib)[:, None] * G + np.sin(phib)[:, None] * ZAX))
    assert np.max(np.abs(base[:, 2])) < 1e-6
    return base[:, :2]


def bend(mesh):
    """Design space (U, V, S) -> real space: vertical lines become orbits."""
    U, V, S = mesh.vertices[:, 0], mesh.vertices[:, 1], mesh.vertices[:, 2]
    w0 = ((U - C[0]) + (V - C[1])) / SQ2
    a0 = ((U - C[0]) - (V - C[1])) / SQ2
    b0 = -C[2]
    rho0 = np.hypot(a0, b0)
    phi0 = np.arctan2(b0, -a0)
    phi = phi0 + S / rho0
    verts = (C + w0[:, None] * E
             + rho0[:, None] * (-np.cos(phi)[:, None] * G + np.sin(phi)[:, None] * ZAX))
    mesh.vertices = verts
    return mesh


def ring_preimage(coords2d, lift):
    """2D ring coords -> lift to 3D via `lift(t1, t2) -> (x,y,z)` -> design plan ring."""
    pts = np.array([lift(t1, t2) for (t1, t2) in coords2d])
    return preimage_plan(pts)


def geom_preimage(geom, lift, seg=None):
    """Shapely geometry -> pre-imaged shapely geometry in the design plan."""
    if seg is not None:
        geom = shapely.segmentize(geom, seg)
    out = []
    for p in polys_of(geom):
        shell = ring_preimage(np.asarray(p.exterior.coords)[:-1], lift)
        holes = [ring_preimage(np.asarray(h.coords)[:-1], lift) for h in p.interiors]
        q = Polygon(shell, holes)
        if not q.is_valid:
            q = q.buffer(0)
        out.append(q)
    return unary_union(out)


def prism(design_geom, s0, s1, ndiv):
    """Vertical design prism with subdivided walls -> bent real solid (uncapped)."""
    from manifold3d import CrossSection, FillRule
    rings = []
    for p in polys_of(design_geom):
        rings.append(np.asarray(p.exterior.coords)[:-1])
        for h in p.interiors:
            rings.append(np.asarray(h.coords)[:-1])
    cs = CrossSection(rings, fillrule=FillRule.EvenOdd)
    man = cs.extrude(s1 - s0, n_divisions=ndiv)
    mgl = man.to_mesh()
    m = trimesh.Trimesh(
        vertices=np.asarray(mgl.vert_properties, dtype=float)[:, :3],
        faces=np.asarray(mgl.tri_verts, dtype=np.int64), process=False)
    m.apply_translation([0, 0, s0])
    return bend(m)


def cap(mesh, cap_z):
    """Intersect a bent solid with the half-space z <= cap_z (exact flat top)."""
    t = trimesh.transformations.translation_matrix([50, 50, (cap_z - 70) / 2])
    box = trimesh.creation.box(extents=[400, 400, cap_z + 70], transform=t)
    return trimesh.boolean.intersection([mesh, box], engine="manifold")


# ------------------------------ footprints -----------------------------------
FACE_LIFT = {
    "front": lambda t, z: (t, 0.0, z),
    "right": lambda t, z: (100.0, t, z),
    "back":  lambda t, z: (t, 100.0, z),
    "left":  lambda t, z: (0.0, t, z),
}
RAIL_RECT = {  # real-plan rails at band height, running inward from each face
    "front": shapely.box(44, -1, 56, KEY_RAIL_R),
    "right": shapely.box(100 - KEY_RAIL_R, 44, 101, 56),
    "back":  shapely.box(44, 100 - KEY_RAIL_R, 56, 101),
    "left":  shapely.box(-1, 44, KEY_RAIL_R, 56),
}


def key_footprints_rot(delta):
    """Design-plan footprints of the four keys (face trapezoid + anchor rail)."""
    trap2d = Polygon([(50 - KEY_HW0R, KEY_Z0R), (50 + KEY_HW0R, KEY_Z0R),
                      (50 + KEY_HW0R, KEY_NECK_ZR), (50 + KEY_HW1R, KEY_Z1R),
                      (50 - KEY_HW1R, KEY_Z1R), (50 - KEY_HW0R, KEY_NECK_ZR)])
    plan_lift = lambda x, y: (x, y, BAND_Z)
    out = []
    for name, lift in FACE_LIFT.items():
        trap = geom_preimage(buffered(trap2d, delta), lift, seg=1.0)
        rail = geom_preimage(buffered(RAIL_RECT[name], delta), plan_lift, seg=1.0)
        out.append((name, unary_union([trap, rail])))
    return out


def build_L_rot(delta, qr_geom, title_geom, sub_geom):
    lift11 = lambda x, y: (x, y, PLAT_TOP_ZR)
    meshes = []
    # band slab: below the band the interface is the exact flat plane z = 7.5+delta,
    # so the slab is a plain straight box (bending it would only add cap-sag error;
    # the bent features descend below the band and fuse into it)
    t = trimesh.transformations.translation_matrix([50, 50, BAND_Z + delta - 20])
    meshes.append(trimesh.creation.box(extents=[220, 220, 40], transform=t))
    # keys + rails
    for name, fp in key_footprints_rot(delta):
        meshes.append(cap(prism(fp, 1, 28, 14), KEY_Z1R + delta))
    # plateau (orbit-swept curtain walls, flat top at z = 11)
    plat = geom_preimage(buffered(shapely.box(*PLAT_SQ), delta), lift11, seg=2.0)
    meshes.append(cap(prism(plat, 1, 28, 14), PLAT_TOP_ZR + delta))
    # QR and text reliefs (footprints pre-imaged from the z = 11 content plane;
    # DFM-safe asymmetric clearance via content_offset)
    meshes.append(cap(prism(geom_preimage(content_offset(qr_geom, delta), lift11),
                            6, 26, 10), QR_TOP_ZR + delta))
    for tg in (title_geom, sub_geom):
        meshes.append(cap(prism(geom_preimage(content_offset(tg, delta), lift11),
                                6, 26, 10), TXT_TOP_ZR + delta))
    return trimesh.boolean.union(meshes, engine="manifold")


# --------------------------------- build -------------------------------------
def main():
    print("preparing 2D artwork (real plan)...")
    qr_geom, qr_n, qr_cell = qr_geometry()
    print(f"  QR: {qr_n}x{qr_n} modules, {qr_cell:.2f} mm/module")
    title_geom = fit_into_box(text_geometry(TITLE), TITLE_BOX)
    sub_geom = fit_into_box(text_geometry(SUBTITLE), SUB_BOX)

    B = stock_box()
    print("building lower solid (bottom offset)...")
    L_lo = build_L_rot(-CLR, qr_geom, title_geom, sub_geom)
    print("building lower solid (top offset)...")
    L_hi = build_L_rot(+CLR, qr_geom, title_geom, sub_geom)

    print("boolean: bottom / top ...")
    bottom = trimesh.boolean.intersection([B, L_lo], engine="manifold")
    top = trimesh.boolean.difference([B, L_hi], engine="manifold")

    # signature on the underside (exterior face: no motion constraint)
    sig = text_geometry(SIGNATURE)
    sig = saff.scale(sig, xfact=-1, yfact=1, origin=(0, 0))
    sig = clean_thin(fit_into_box(sig, (35.0, 85.0, 65.0, 91.0)))
    from manifold3d import CrossSection, FillRule
    rings = []
    for p in polys_of(sig):
        rings.append(np.asarray(p.exterior.coords)[:-1])
        for h in p.interiors:
            rings.append(np.asarray(h.coords)[:-1])
    man = CrossSection(rings, fillrule=FillRule.EvenOdd).extrude(1.6)
    mgl = man.to_mesh()
    sig_m = trimesh.Trimesh(
        vertices=np.asarray(mgl.vert_properties, dtype=float)[:, :3],
        faces=np.asarray(mgl.tri_verts, dtype=np.int64), process=False)
    sig_m.apply_translation([0, 0, -1.0])
    bottom = trimesh.boolean.difference([bottom, sig_m], engine="manifold")

    print(f"bottom: {len(bottom.faces)} faces, top: {len(top.faces)} faces")
    bottom.export(os.path.join(STL, "U3T_rot_bottom.stl"))
    top.export(os.path.join(STL, "U3T_rot_top.stl"))
    top_p = top.copy()
    flip = trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0], point=[50, 50, 7.5])
    top_p.apply_transform(flip)
    top_p.apply_translation([0, 0, -top_p.bounds[0][2]])
    top_p.export(os.path.join(STL, "U3T_rot_top_print.stl"))

    # ------------------------------ verification ------------------------------
    report = {}
    print("\n--- verification (rotation edition) ---")
    ok_all = True
    for name, m in (("bottom", bottom), ("top", top)):
        wt, wc = m.is_watertight, m.is_winding_consistent
        bodies = len(m.split(only_watertight=True))
        vol = float(m.volume)
        ok = wt and wc and bodies == 1 and vol > 0
        ok_all &= ok
        report[name] = dict(watertight=wt, winding=wc, bodies=bodies,
                            volume_mm3=round(vol, 1), bounds=m.bounds.tolist())
        print(f"{name}: watertight={wt} winding={wc} bodies={bodies} "
              f"volume={vol:.0f} mm^3 bounds={np.round(m.bounds, 2).tolist()} "
              f"-> {'PASS' if ok else 'FAIL'}")

    def inter_vol(a, b):
        m = trimesh.boolean.intersection([a, b], engine="manifold")
        return float(m.volume) if len(m.faces) else 0.0

    v0 = inter_vol(bottom, top)
    ok_all &= v0 < 1e-6
    print(f"assembled overlap: {v0:.6f} mm^3 -> {'PASS' if v0 < 1e-6 else 'FAIL'}")
    report["assembled_overlap_mm3"] = v0

    rot = {}
    for deg in (0.05, 0.1, 0.25, 0.5, 1, 2, 4, 7, 10, 15, 20, 25):
        R = trimesh.transformations.rotation_matrix(np.radians(deg), E, point=C)
        tp = top.copy(); tp.apply_transform(R)
        v = inter_vol(bottom, tp)
        rot[deg] = v
        ok = v < 1e-6
        ok_all &= ok
        print(f"rotate about A, theta={deg:>5} deg: overlap={v:.6f} -> "
              f"{'PASS' if ok else 'FAIL'}")
    report["rotation_about_A"] = rot
    report["separation_pass"] = ok_all

    controls = {}
    tests = [("straight up 1mm", None, np.array([0, 0, 1.0]), 1.0),
             ("straight up 2mm", None, np.array([0, 0, 1.0]), 2.0),
             ("flat diagonal 1mm", None, np.array([1, 1, 0]) / SQ2, 1.0),
             ("flat diagonal 2mm", None, np.array([1, 1, 0]) / SQ2, 2.0),
             ("straight-d slide 2mm", None, np.array([0.7, 0.7, 1.0]) / 1.4036, 2.0),
             ("straight-d slide 5mm", None, np.array([0.7, 0.7, 1.0]) / 1.4036, 5.0),
             ("reverse rotation 1deg", -1.0, None, None)]
    for label, deg, vec, t in tests:
        tp = top.copy()
        if deg is not None:
            tp.apply_transform(trimesh.transformations.rotation_matrix(
                np.radians(deg), E, point=C))
        else:
            tp.apply_translation(vec * t)
        v = inter_vol(bottom, tp)
        controls[label] = v
        print(f"control ({label}): overlap={v:.3f} mm^3 -> "
              f"{'PASS (locks)' if v > 1e-3 else 'FAIL (should collide)'}")
    report["negative_controls_mm3"] = controls

    with open(os.path.join(REPORTS, "verify_report_rot.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("\ndone. STLs in", STL)


if __name__ == "__main__":
    main()
