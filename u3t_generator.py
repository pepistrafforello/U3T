"""
U3T ("Unnamed 3D Thingy") generator
-----------------------------------
Builds the two mating parts of a 4-sided U3T with:
  - identical dovetail seam on all four side faces (band at mid-height + trapezoid key)
  - hidden interface carrying a raised plateau, QR code, title and subtitle
  - separation by a single translation along the oblique direction d = (SHX, SHY, 1)

Method: the parting surface is designed as a height field in SHEARED coordinates
(u, v, z) = (x - SHX*z, y - SHY*z, z). In sheared space the separation direction is
vertical, so ANY single-valued height field (vertical-walled prisms included) yields
two parts that separate without collision. The solid "L" (everything below the
interface) is built from vertical extrusions in sheared space, sheared into real
space, then intersected with / subtracted from the exact stock box.

Clearance: L is built twice with +/- CLR offsets (vertical and lateral), giving a
uniform gap between the parts.

Outputs: STL files + verification report.
"""

import json
import os

import numpy as np
import shapely
import shapely.affinity as saff
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(ROOT, "stl")
REPORTS = os.path.join(ROOT, "verification")
os.makedirs(STL, exist_ok=True)
os.makedirs(REPORTS, exist_ok=True)

# ----------------------------- parameters (mm) ------------------------------
L = 100.0            # stock footprint
H = 15.0             # stock height
SHX = 0.7            # shear: separation direction d = (SHX, SHY, 1), ~44.7 deg off vertical
SHY = 0.7
CLR = 0.15           # clearance applied to EACH part (total gap = 2*CLR = 0.3)

BAND_Z = 7.5         # seam height on the side faces

KEY_Z0, KEY_Z1 = 7.5, 11.5   # dovetail key: from band to key top (face coords)
KEY_HW0, KEY_HW1 = 6.0, 10.0  # half-width at band / at top  (flares upward = undercut)
KEY_NECK_Z = 8.3     # straight neck below the flare: the lip starts where its depth
                     # (lean x height above band = 0.7 x 0.8) already exceeds 0.55 mm
KEY_RAIL = 8.0       # interior anchor rail behind each key (plan length)

MIN_FEATURE = 0.55   # FDM min printable wall/stroke (Xometry: > 0.5 mm)

PLAT_TOP_Z = 11.0    # plateau top
PLAT_TOP_HW = 30.0   # plateau top half-width (sheared space, centered at 50,50)
PLAT_BASE_Z = 7.0    # frustum base (below band so it fuses with the slab)
PLAT_BASE_HW = 34.0  # 45-degree ramps: (34.0-30.0)/(11.0-7.0) = 1

QR_TOP_Z = 12.2      # QR relief top (1.2 above plateau)
TXT_TOP_Z = 12.0     # text relief top (1.0 above plateau)
QR_BOX = (32.0, 41.0, 68.0, 77.0)     # (u0, v0, u1, v1) 36x36, toward back
TITLE_BOX = (23.0, 29.0, 77.0, 36.5)
SUB_BOX = (24.0, 21.8, 76.0, 28.0)    # taller than v1 so nominal strokes stay > MIN_FEATURE

QR_PAYLOAD = "Congratulations Francesco! UofT '22"
TITLE = "Francesco Strafforello"
SUBTITLE = "University of Toronto '22"
SIGNATURE = "pepi 2026"

FONT = FontProperties(family="DejaVu Sans", weight="bold")

D = np.array([SHX, SHY, 1.0])
D_HAT = D / np.linalg.norm(D)

SHEAR = np.array([
    [1, 0, SHX, 0],
    [0, 1, SHY, 0],
    [0, 0, 1,   0],
    [0, 0, 0,   1],
], dtype=float)


# ------------------------------- 2D helpers ---------------------------------
def buffered(poly, delta):
    """Mitre-joined offset that keeps corners sharp; drops degenerate results."""
    if abs(delta) < 1e-12:
        return poly
    out = poly.buffer(delta, join_style=2, mitre_limit=8.0)
    return out


def clean_thin(geom, min_w=MIN_FEATURE):
    """Morphological opening: removes necks/slivers thinner than min_w."""
    r = min_w / 2.0
    return geom.buffer(-r).buffer(r)


def close_gaps(geom, min_gap=0.5):
    """Morphological closing: fuses gaps thinner than min_gap (so the complement
    never contains a wall thinner than min_gap)."""
    r = min_gap / 2.0
    return geom.buffer(r).buffer(-r)


def content_offset(geom, delta):
    """DFM-safe clearance for interface artwork (text, QR).

    The sliding fit does not need a symmetric split: the RAISED side keeps its
    full nominal width (strokes never fall below MIN_FEATURE), and the CAVITY
    side takes the whole clearance (2*delta). Residual sub-minimum necks are
    opened away on the raised side; sub-minimum walls between neighbouring
    cavities are closed (fused) on the cavity side.
    """
    if delta <= 0:
        return clean_thin(geom)
    return close_gaps(geom.buffer(2.0 * delta))


def polys_of(geom):
    """List of shapely Polygons from Polygon/MultiPolygon/GeometryCollection."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and g.area > 1e-6]


def text_geometry(s, size=10.0):
    """Shapely geometry of a text string (even-odd hole handling)."""
    tp = TextPath((0, 0), s, size=size, prop=FONT)
    rings = []
    for pts in tp.to_polygons():
        if len(pts) >= 3:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty and p.area > 1e-9:
                rings.append(p)
    rings.sort(key=lambda r: r.area, reverse=True)
    result = None
    for r in rings:
        if result is None:
            result = r
        elif result.contains(r.representative_point()):
            result = result.difference(r)
        else:
            result = result.union(r)
    return result


def fit_into_box(geom, box):
    """Scale (uniform) + center geometry into (u0, v0, u1, v1)."""
    u0, v0, u1, v1 = box
    gu0, gv0, gu1, gv1 = geom.bounds
    s = min((u1 - u0) / (gu1 - gu0), (v1 - v0) / (gv1 - gv0))
    g = saff.scale(geom, xfact=s, yfact=s, origin=(0, 0))
    gu0, gv0, gu1, gv1 = g.bounds
    dx = (u0 + u1) / 2 - (gu0 + gu1) / 2
    dy = (v0 + v1) / 2 - (gv0 + gv1) / 2
    return saff.translate(g, xoff=dx, yoff=dy)


def qr_geometry():
    """Union of QR module squares fitted into QR_BOX. Returns shapely geometry."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0)
    qr.add_data(QR_PAYLOAD)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    u0, v0, u1, v1 = QR_BOX
    cell = min((u1 - u0), (v1 - v0)) / n
    squares = []
    for r in range(n):
        for c in range(n):
            if m[r][c]:
                # row 0 at the top (largest v)
                x0 = u0 + c * cell
                y1 = v1 - r * cell
                squares.append(shapely.box(x0, y1 - cell, x0 + cell, y1))
    return unary_union(squares), n, cell


# --------------------------- prism / solid helpers ---------------------------
def extrude(geom, z0, z1):
    """Vertical extrusion of shapely geometry from z0 to z1 -> list of meshes.

    Uses manifold3d CrossSection (even-odd fill), which is robust for polygons
    with holes and islands-inside-holes (e.g. QR finder patterns).
    """
    from manifold3d import CrossSection, FillRule
    rings = []
    for p in polys_of(geom):
        rings.append(np.asarray(p.exterior.coords)[:-1])
        for hole in p.interiors:
            rings.append(np.asarray(hole.coords)[:-1])
    if not rings:
        return []
    cs = CrossSection(rings, fillrule=FillRule.EvenOdd)
    man = cs.extrude(z1 - z0)
    mgl = man.to_mesh()
    m = trimesh.Trimesh(
        vertices=np.asarray(mgl.vert_properties, dtype=float)[:, :3],
        faces=np.asarray(mgl.tri_verts, dtype=np.int64),
        process=False,
    )
    m.apply_translation([0, 0, z0])
    if not m.is_volume:
        raise ValueError(f"extrusion is not a volume (z0={z0}, z1={z1})")
    return [m]


def key_footprints():
    """Sheared-plan footprints of the four face keys (nominal), WITH anchor rails.

    Face trapezoid corners are defined in real 3D on each face, then projected to
    sheared plan coordinates (u, v) = (x - SHX*z, y - SHY*z). Each trapezoid is
    unioned with a rail of the same width running KEY_RAIL mm toward the interior:
    the visible tab is then the end of a solid internal rail, so it can never be
    orphaned when the stock box crops away the outside of the leaning prism.
    """
    c = L / 2.0
    quads = []
    z0, zn, z1, w0, w1 = KEY_Z0, KEY_NECK_Z, KEY_Z1, KEY_HW0, KEY_HW1
    # corners: base edge (b1, b2 at z0), neck (at zn), then flare top; the neck
    # keeps the lip depth above MIN_FEATURE everywhere. n = inward plan dir
    faces = {
        "front": ([(c - w0, 0, z0), (c + w0, 0, z0), (c + w0, 0, zn),
                   (c + w1, 0, z1), (c - w1, 0, z1), (c - w0, 0, zn)], (0, 1)),
        "right": ([(L, c - w0, z0), (L, c + w0, z0), (L, c + w0, zn),
                   (L, c + w1, z1), (L, c - w1, z1), (L, c - w0, zn)], (-1, 0)),
        "back":  ([(c - w0, L, z0), (c + w0, L, z0), (c + w0, L, zn),
                   (c + w1, L, z1), (c - w1, L, z1), (c - w0, L, zn)], (0, -1)),
        "left":  ([(0, c - w0, z0), (0, c + w0, z0), (0, c + w0, zn),
                   (0, c + w1, z1), (0, c - w1, z1), (0, c - w0, zn)], (1, 0)),
    }
    for name, (corners, n) in faces.items():
        uv = [(x - SHX * z, y - SHY * z) for (x, y, z) in corners]
        trap = Polygon(uv)
        if not trap.is_valid:
            trap = trap.buffer(0)
        b1, b2 = uv[0], uv[1]
        rail = Polygon([
            b1, b2,
            (b2[0] + n[0] * KEY_RAIL, b2[1] + n[1] * KEY_RAIL),
            (b1[0] + n[0] * KEY_RAIL, b1[1] + n[1] * KEY_RAIL),
        ])
        q = unary_union([trap, rail])
        if not q.is_valid:
            q = q.buffer(0)
        quads.append((name, q))
    return quads


def frustum_mesh(delta):
    """Plateau frustum (sheared space) as convex hull of 8 points, offset by delta."""
    hw_t = PLAT_TOP_HW + delta
    hw_b = PLAT_BASE_HW + delta
    zt = PLAT_TOP_Z + delta
    zb = PLAT_BASE_Z  # base stays buried below the band
    c = L / 2.0
    pts = []
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            pts.append([c + s1 * hw_b, c + s2 * hw_b, zb])
            pts.append([c + s1 * hw_t, c + s2 * hw_t, zt])
    return trimesh.convex.convex_hull(np.array(pts))


def build_L(delta, qr_geom, title_geom, sub_geom, keys):
    """Solid below the interface, in sheared space, offset by delta (signed)."""
    meshes = []
    # base slab up to the band
    slab = shapely.box(-30, -30, L + 30, L + 30)
    meshes += extrude(slab, -5.0, BAND_Z + delta)
    # four dovetail keys
    for name, q in keys:
        qb = buffered(q, delta)
        meshes += extrude(qb, BAND_Z - 1.0, KEY_Z1 + delta)
    # plateau frustum (45-degree ramps)
    meshes.append(frustum_mesh(delta))
    # QR relief (DFM-safe asymmetric clearance, see content_offset)
    meshes += extrude(content_offset(qr_geom, delta), PLAT_TOP_Z - 0.5, QR_TOP_Z + delta)
    # text reliefs
    meshes += extrude(content_offset(title_geom, delta), PLAT_TOP_Z - 0.5, TXT_TOP_Z + delta)
    meshes += extrude(content_offset(sub_geom, delta), PLAT_TOP_Z - 0.5, TXT_TOP_Z + delta)
    solid = trimesh.boolean.union(meshes, engine="manifold")
    solid.apply_transform(SHEAR)  # sheared space -> real space
    return solid


def stock_box():
    t = trimesh.transformations.translation_matrix([L / 2, L / 2, H / 2])
    return trimesh.creation.box(extents=[L, L, H], transform=t)


# --------------------------------- build -------------------------------------
def main():
    print("preparing 2D artwork...")
    qr_geom, qr_n, qr_cell = qr_geometry()
    print(f"  QR: {qr_n}x{qr_n} modules, {qr_cell:.2f} mm/module")
    title_geom = fit_into_box(text_geometry(TITLE), TITLE_BOX)
    sub_geom = fit_into_box(text_geometry(SUBTITLE), SUB_BOX)
    keys = key_footprints()

    B = stock_box()

    print("building lower solid (bottom offset)...")
    L_lo = build_L(-CLR, qr_geom, title_geom, sub_geom, keys)
    print("building lower solid (top offset)...")
    L_hi = build_L(+CLR, qr_geom, title_geom, sub_geom, keys)

    print("boolean: bottom = stock INTERSECT L(-clr)")
    bottom = trimesh.boolean.intersection([B, L_lo], engine="manifold")
    print("boolean: top = stock MINUS L(+clr)")
    top = trimesh.boolean.difference([B, L_hi], engine="manifold")

    # signature engraved on the underside (mirrored so it reads from below)
    sig = text_geometry(SIGNATURE)
    sig = saff.scale(sig, xfact=-1, yfact=1, origin=(0, 0))
    sig = clean_thin(fit_into_box(sig, (35.0, 85.0, 65.0, 91.0)))
    sig_m = extrude(sig, -1.0, 0.6)
    bottom = trimesh.boolean.difference([bottom] + sig_m, engine="manifold")

    print(f"bottom: {len(bottom.faces)} faces, top: {len(top.faces)} faces")

    bottom.export(os.path.join(STL, "U3T_bottom.stl"))
    top.export(os.path.join(STL, "U3T_top.stl"))
    # print-ready top: flipped 180 deg about x through the part center
    top_p = top.copy()
    flip = trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0], point=[L / 2, L / 2, H / 2])
    top_p.apply_transform(flip)
    top_p.apply_translation([0, 0, -top_p.bounds[0][2]])
    top_p.export(os.path.join(STL, "U3T_top_print.stl"))

    # ------------------------------ verification ------------------------------
    report = {}
    print("\n--- verification ---")
    for name, m in (("bottom", bottom), ("top", top)):
        wt = m.is_watertight
        wc = m.is_winding_consistent
        vol = float(m.volume)
        bnd = m.bounds.tolist()
        # every part must be ONE connected solid: floating fragments (e.g. an
        # unanchored key tab) are watertight too, so check the body count
        bodies = len(m.split(only_watertight=True))
        ok = wt and wc and vol > 0 and bodies == 1
        report[name] = dict(watertight=wt, winding=wc, volume_mm3=round(vol, 1),
                            bodies=bodies, bounds=bnd)
        print(f"{name}: watertight={wt} winding={wc} bodies={bodies} volume={vol:.0f} mm^3 "
              f"bounds={np.round(m.bounds, 2).tolist()} -> {'PASS' if ok else 'FAIL'}")

    both = np.vstack([bottom.bounds, top.bounds])
    env = [both.min(axis=0).tolist(), both.max(axis=0).tolist()]
    print(f"assembly envelope: {np.round(env, 3).tolist()} (target [0,0,-1eng]..[100,100,15])")
    report["envelope"] = env

    def inter_vol(a, b):
        try:
            m = trimesh.boolean.intersection([a, b], engine="manifold")
            return float(m.volume) if len(m.faces) else 0.0
        except Exception:
            return 0.0

    v0 = inter_vol(bottom, top)
    print(f"assembled overlap: {v0:.6f} mm^3 -> {'PASS' if v0 < 1e-6 else 'FAIL'}")
    report["assembled_overlap_mm3"] = v0

    # separation along +d must be collision-free at every stage
    sep = {}
    all_ok = True
    for t in (0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 12, 16, 20, 30, 40):
        tp = top.copy()
        tp.apply_translation(D_HAT * t)
        v = inter_vol(bottom, tp)
        sep[t] = v
        ok = v < 1e-6
        all_ok &= ok
        print(f"slide along d, t={t:>5}: overlap={v:.6f} -> {'PASS' if ok else 'FAIL'}")
    report["separation_along_d"] = sep
    report["separation_pass"] = all_ok

    # negative controls: the puzzle must NOT open with naive moves
    controls = {}
    for label, vec, ts in (
        ("straight up", np.array([0, 0, 1.0]), (1.0, 2.0)),
        ("flat diagonal slide", np.array([1, 1, 0.0]) / np.sqrt(2), (1.0, 2.0)),
    ):
        for t in ts:
            tp = top.copy()
            tp.apply_translation(vec * t)
            v = inter_vol(bottom, tp)
            controls[f"{label} t={t}"] = v
            print(f"control ({label}), t={t}: overlap={v:.3f} mm^3 -> "
                  f"{'PASS (locks)' if v > 1e-3 else 'FAIL (should collide)'}")
    report["negative_controls_mm3"] = controls

    with open(os.path.join(REPORTS, "verify_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("\ndone. STLs in", STL)


if __name__ == "__main__":
    main()
