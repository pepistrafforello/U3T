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
from shapely.geometry import LineString, MultiPolygon, Polygon
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
KEY_RAIL = 6.0       # interior anchor rail behind each key (plan length).
                     # Bounded by the plateau: the rails that start at the
                     # flare (see key_footprints) reach 2.8 mm further in,
                     # and at 8.0 their inboard end left a 0.28 mm wall
                     # against the plateau ramp in the mating part.

MIN_FEATURE = 0.55   # FDM min printable wall/stroke (Xometry: > 0.5 mm)

# ---- the interface plane ----------------------------------------------------
# The parting surface in the middle of the block is where the content lives, and
# a horizontal one costs twice over. It sits 44.7 deg away from perpendicular to
# d, so every feature on it is foreshortened by cos(44.7) = 0.71 across the shear
# direction; and because relief walls must run parallel to d, each raised island
# drifts 0.99 mm sideways per mm of height. A 1.24 mm QR module with 1.2 mm of
# relief therefore ends up with 0.05 mm of itself standing over its own base.
#
# Tilting the plane toward perpendicular removes both. What it costs is width: a
# tilted plane runs out of a 15 mm slab fast, so the canvas stops being a square
# and becomes a band along the level diagonal -- the one direction in which the
# tilted plane stays at constant height.
PLAT_TILT = 30.0     # deg from horizontal; PLAT_TILT_PERP is exactly normal to d
PLAT_Z = 11.0        # z at the middle of the band
PLAT_Z_LO = 8.5      # the band has to stay inside this slice of the slab:
PLAT_Z_HI = 13.5     # above the seam, below the top face, with material either side
PLAT_RAMP = 7.0      # ramp run from the band edge down to the base
PLAT_BASE_Z = 7.0    # base sits below the seam, so it fuses into the slab
PLAT_MARGIN = 8.0    # keep the base this far from the side faces

CONTENT = False      # QR + title relief: off while the content is redesigned
QR_TOP_Z = 12.2      # relief heights, for when it comes back
TXT_TOP_Z = 12.0
QR_BOX = (32.0, 41.0, 68.0, 77.0)
TITLE_BOX = (23.0, 29.0, 77.0, 36.5)
SUB_BOX = (24.0, 21.8, 76.0, 28.0)

QR_PAYLOAD = "Congratulations Francesco! UofT '22"
TITLE = "Francesco Strafforello"
SUBTITLE = "University of Toronto '22"
SIGNATURE = "pepi 2026"

FONT = FontProperties(family="DejaVu Sans", weight="bold")

D = np.array([SHX, SHY, 1.0])
D_HAT = D / np.linalg.norm(D)

# the tilt that would put the interface plane exactly normal to d
PLAT_TILT_PERP = np.degrees(np.arctan(np.hypot(SHX, SHY)))
_TILT = np.radians(PLAT_TILT)
TILT_S = np.tan(_TILT) / np.sqrt(2.0)          # dz per unit of (x + y)
# how wide the band can be before it leaves the slab, as a horizontal projection
PLAT_WID = (min(PLAT_Z_HI - PLAT_Z, PLAT_Z - PLAT_Z_LO) / np.tan(_TILT)
            if PLAT_TILT > 1e-9 else 30.0)
PLAT_WID = min(PLAT_WID, 30.0)
# and how long, before the base of its ramps reaches a side face
PLAT_LEN = ((L / 2 - PLAT_MARGIN) * np.sqrt(2.0)
            - PLAT_RAMP - (PLAT_WID + PLAT_RAMP))

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
    unioned with a rail running KEY_RAIL mm toward the interior: the visible tab
    is then the end of a solid internal rail, so it can never be orphaned when
    the stock box crops away the outside of the leaning prism.

    The rail starts at whichever edge of the trapezoid lies furthest INSIDE the
    block. That edge is not the same one on every face: as z runs over the key,
    the face plane sweeps a strip of the sheared plan, and anything the footprint
    puts inside that strip is what shows up on the face. Only the inboard-most
    edge is guaranteed to sit outside it, so only from there can the rail be made
    any width at all without altering the dovetail the face shows.

    On the two faces d leans into, that edge is the trapezoid's base, giving the
    12 mm rail this design has always had. On the two faces d leans out of, it is
    the flare's top edge, so the rail comes out 20 mm wide and butts against the
    back of the flare -- which is where those two keys were previously left
    standing on air, 0.2 mm thick across 16 mm of width.
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
        depth = [n[0] * u + n[1] * v for (u, v) in uv]
        i1, i0 = sorted(range(len(uv)), key=lambda i: depth[i])[-2:]
        b1, b2 = uv[i0], uv[i1]
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


def plat_plane_z(x, y):
    """Height of the interface plane over a real-space plan point."""
    return PLAT_Z - TILT_S * (x + y - L)


def plat_ring(half_len, half_wid, z=None):
    """Corners of a band rectangle in REAL space, aligned to the plan diagonals.

    The long axis is (1, -1): the level direction of the tilted plane, the one
    along which it keeps a constant height. The short axis is (1, 1), where it
    climbs at tan(PLAT_TILT) per millimetre and runs out of slab.
    """
    r2 = np.sqrt(2.0)
    out = []
    for sp, sq in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        px, qy = sp * half_len, sq * half_wid
        x = L / 2 + (px + qy) / r2
        y = L / 2 + (qy - px) / r2
        out.append([x, y, plat_plane_z(x, y) if z is None else z])
    return np.array(out)


def plateau_mesh(delta):
    """The tilted interface band, as a platform, in SHEARED space.

    On the tilted top the clearance has to be taken along the plane normal, which
    is delta / cos(tilt) measured vertically.
    """
    top = plat_ring(PLAT_LEN + delta, PLAT_WID + delta)
    top[:, 2] += delta / np.cos(_TILT)
    base = plat_ring(PLAT_LEN + PLAT_RAMP + delta,
                     PLAT_WID + PLAT_RAMP + delta, z=PLAT_BASE_Z)
    pts = np.vstack([top, base])
    pts[:, 0] -= SHX * pts[:, 2]
    pts[:, 1] -= SHY * pts[:, 2]
    return trimesh.convex.convex_hull(pts)


def build_L(delta, keys, art=()):
    """Solid below the interface, in sheared space, offset by delta (signed)."""
    meshes = []
    # base slab up to the band
    slab = shapely.box(-30, -30, L + 30, L + 30)
    meshes += extrude(slab, -5.0, BAND_Z + delta)
    # four dovetail keys
    for name, q in keys:
        qb = buffered(q, delta)
        meshes += extrude(qb, BAND_Z - 1.0, KEY_Z1 + delta)
    # the tilted interface band
    meshes.append(plateau_mesh(delta))
    # relief on it, when there is any (DFM-safe clearance, see content_offset)
    for geom, z_top in art:
        meshes += extrude(content_offset(geom, delta), PLAT_Z - 0.5, z_top + delta)
    solid = trimesh.boolean.union(meshes, engine="manifold")
    solid.apply_transform(SHEAR)  # sheared space -> real space
    return solid


def plateau_plan(delta=0.0, base=False):
    """Sheared-plan outline of the interface band -- its top face, or its base."""
    if base:
        ring = plat_ring(PLAT_LEN + PLAT_RAMP + delta,
                         PLAT_WID + PLAT_RAMP + delta, z=PLAT_BASE_Z)
    else:
        ring = plat_ring(PLAT_LEN + delta, PLAT_WID + delta)
        ring[:, 2] += delta / np.cos(_TILT)
    ring[:, 0] -= SHX * ring[:, 2]
    ring[:, 1] -= SHY * ring[:, 2]
    return ring[:, :2]


def weld(mesh):
    """Fuse vertices the STL file cannot tell apart, and drop what that degenerates.

    STL stores float32, whose grid spacing at 100 mm is 7.6e-6 mm. The boolean
    kernel leaves the occasional vertex pair far below that -- harmless in double
    precision, fatal on the way out: both land on the same point once written, and
    every face that used both tears open. That is how the flipped print copy of the
    rotation top shipped with six non-manifold edges while the mesh it was copied
    from verified watertight.

    So repair at the precision the file will have, not above it: quantise to the
    output grid FIRST, then merge exactly. Welding at a chosen tolerance instead
    is guesswork at the same order as the grid -- 1e-5 mm looked safe until a 5 mm
    cube relief slipped a pair through it.

    Dropping ONLY faces that gain a repeated vertex index is what makes this safe:
    such a face contributes a doubled edge that cancels, so it cannot open a hole.
    Dropping slivers by area instead can, and does.

    A rigid transform puts the vertices back off the grid, so anything re-oriented
    for printing has to be welded again after the move, not before.
    """
    m = mesh.copy()
    m.vertices = m.vertices.astype(np.float32).astype(np.float64)
    m.merge_vertices()
    f = m.faces
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])
    m.update_faces(keep)
    m.remove_unreferenced_vertices()
    return m


def stock_box():
    t = trimesh.transformations.translation_matrix([L / 2, L / 2, H / 2])
    return trimesh.creation.box(extents=[L, L, H], transform=t)


# ------------------------------ face fidelity --------------------------------
FACE_SPECS = (("front", 1, 0.0, +1), ("right", 0, L, -1),
              ("back", 1, L, -1), ("left", 0, 0.0, +1))


def face_key_profile(mesh, zs, eps=1e-4):
    """Lateral extent of material at each side face, height by height.

    All four faces of a U3T must show the same dovetail -- that is the premise of
    the whole object, and until now nothing in this suite tested it. An anchor
    rail that broke the surface of two faces by up to 0.56 mm shipped because of
    that gap.

    The probe sits eps inside the face and must stay there: the key flanks lean,
    so measuring even 0.01 mm deep already reads 0.06 mm wider on the two faces
    d leans out of than on the two it leans into. That is the lean, not a defect.
    """
    prof = {}
    for name, ax, fv, sgn in FACE_SPECS:
        lat, rows = 1 - ax, []
        for z in zs:
            sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            lo = hi = None
            if sec is not None:
                to2d = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                                 [0, 0, 1, -z], [0, 0, 0, 1]], float)
                p2, _ = sec.to_2D(to_2D=to2d)
                a, b = [0.0, 0.0], [0.0, 0.0]
                a[ax] = b[ax] = fv + sgn * eps
                a[lat], b[lat] = -10.0, L + 10.0
                line = LineString([tuple(a), tuple(b)])
                xs = []
                for pg in p2.polygons_full:
                    it = pg.intersection(line)
                    for g in getattr(it, "geoms", [it]):
                        if not g.is_empty and g.geom_type == "LineString":
                            xs.extend(np.asarray(g.coords)[:, lat])
                if xs:
                    lo, hi = float(min(xs)), float(max(xs))
            rows.append((lo, hi))
        prof[name] = rows
    return prof


def nominal_half_width(z):
    """Half-width of the designed dovetail on the face, at height z."""
    if z <= KEY_NECK_Z:
        return KEY_HW0
    return KEY_HW0 + (KEY_HW1 - KEY_HW0) * (z - KEY_NECK_Z) / (KEY_Z1 - KEY_NECK_Z)


# --------------------------------- build -------------------------------------
def main():
    top = plat_ring(PLAT_LEN, PLAT_WID)
    band_w = 2 * PLAT_WID / np.cos(_TILT)
    print(f"interface plane: {PLAT_TILT:.1f} deg from horizontal "
          f"({PLAT_TILT_PERP - PLAT_TILT:.1f} deg short of normal to d)")
    print(f"  band {2 * PLAT_LEN:.0f} x {band_w:.1f} mm along the plan diagonal, "
          f"z {top[:, 2].min():.2f} .. {top[:, 2].max():.2f}")
    print(f"  relief drift {np.tan(np.radians(PLAT_TILT_PERP - PLAT_TILT)):.3f} mm "
          f"per mm of height (was {np.hypot(SHX, SHY):.3f})")

    art = []
    if CONTENT:
        print("preparing 2D artwork...")
        qr_geom, qr_n, qr_cell = qr_geometry()
        print(f"  QR: {qr_n}x{qr_n} modules, {qr_cell:.2f} mm/module")
        art = [(qr_geom, QR_TOP_Z),
               (fit_into_box(text_geometry(TITLE), TITLE_BOX), TXT_TOP_Z),
               (fit_into_box(text_geometry(SUBTITLE), SUB_BOX), TXT_TOP_Z)]
    else:
        print("content: none (interface left blank)")
    keys = key_footprints()

    B = stock_box()

    print("building lower solid (bottom offset)...")
    L_lo = build_L(-CLR, keys, art)
    print("building lower solid (top offset)...")
    L_hi = build_L(+CLR, keys, art)

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

    bottom, top = weld(bottom), weld(top)
    print(f"welded: bottom {len(bottom.faces)} faces, top {len(top.faces)} faces")
    bottom.export(os.path.join(STL, "U3T_bottom.stl"))
    top.export(os.path.join(STL, "U3T_top.stl"))
    # print-ready top: flipped 180 deg about x through the part center
    top_p = top.copy()
    # exact 180 deg flip about the x axis through the seam: y -> 2*cy - y,
    # z -> 2*cz - z. Writing it out avoids the 1e-16 terms that
    # rotation_matrix(pi, ...) carries, which survive into float32 STL and
    # collapse vertex pairs into non-manifold edges.
    flip = np.array([[1.0, 0.0, 0.0, 0.0],
                     [0.0, -1.0, 0.0, L],
                     [0.0, 0.0, -1.0, H],
                     [0.0, 0.0, 0.0, 1.0]])
    top_p.apply_transform(flip)
    top_p.apply_translation([0, 0, -top_p.bounds[0][2]])
    top_p = weld(top_p)              # the move put the vertices back off the grid
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

    # what reaches the printer is the FILE, not the mesh in memory: STL is
    # float32, so an export can collapse vertex pairs that were distinct in
    # double precision and open non-manifold edges. Re-read every file.
    report["files"] = {}
    for fn in ("U3T_bottom.stl", "U3T_top.stl", "U3T_top_print.stl"):
        f = trimesh.load(os.path.join(STL, fn))
        wt, wc = f.is_watertight, f.is_winding_consistent
        bodies = len(f.split(only_watertight=True))
        ok = wt and wc and bodies == 1
        
        report["files"][fn] = dict(watertight=wt, winding=wc, bodies=bodies)
        print(f"file {fn}: watertight={wt} winding={wc} bodies={bodies} "
              f"-> {'PASS' if ok else 'FAIL'}")

    # the four faces must show the same dovetail, or it is not this puzzle
    zs = np.arange(BAND_Z + 0.5, KEY_Z1 - CLR - 0.05, 0.1)
    prof = face_key_profile(bottom, zs)
    spread = 0.0
    dev = 0.0
    for i, z in enumerate(zs):
        vals = [prof[nm][i] for nm, *_ in FACE_SPECS]
        if any(v[0] is None for v in vals):
            spread = float("inf")
            continue
        los = [v[0] for v in vals]
        his = [v[1] for v in vals]
        spread = max(spread, max(los) - min(los), max(his) - min(his))
        hw = nominal_half_width(z)
        for lo, hi in vals:
            dev = max(dev, abs(lo - (L / 2 - hw)), abs(hi - (L / 2 + hw)))
    face_ok = spread <= 0.05
    print(f"face fidelity: spread between the four faces {spread:.3f} mm -> "
          f"{'PASS' if face_ok else 'FAIL'}")
    print(f"               widest gap to the nominal trapezoid {dev:.3f} mm "
          f"(the {CLR:.2f} clearance, read horizontally across an oblique flank)")
    report["face_spread_mm"] = spread
    report["face_deviation_mm"] = dev

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
