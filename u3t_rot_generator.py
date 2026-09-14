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
import sys

import numpy as np
import shapely
import shapely.affinity as saff
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from u3t_generator import (
    L, H, BAND_Z, CLR, TITLE, SUBTITLE, SIGNATURE, TITLE_BOX, SUB_BOX,
    buffered, polys_of, text_geometry, fit_into_box, qr_geometry, stock_box,
    clean_thin, content_offset, face_key_profile, FACE_SPECS,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(ROOT, "stl")
REPORTS = os.path.join(ROOT, "verification")
sys.path.insert(0, os.path.join(ROOT, "tools"))
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
# ---- the interface: a sawtooth fan ------------------------------------------
# A single tilted plane is normal to the motion but runs out of a 15 mm slab
# almost at once, which left a canvas 12 mm wide. The fix is many canvases.
#
# The rotation edition makes that unusually clean. A plane through the rotation
# axis is perpendicular to EVERY orbit it meets -- its tangent space at any point
# is spanned by the axis direction and the radius, and the orbit velocity is
# perpendicular to both. So each facet of the fan can be exactly normal to the
# motion everywhere on it, not merely at one point.
#
# In the unwrapped design plan the interface is then a descending staircase in
# radius: facets at constant phase (planes through the axis), separated by risers
# at constant radius (cylinders about the axis). Cylinders about the axis are
# swept by orbits, so the risers are exactly the "cliffs parallel to the motion"
# that the height-field rule already allows.
#
# Depth does not buy area -- the facet run is dz/tan(phi) and the riser run is
# dz*tan(phi), so the split is cos^2(phi) whatever the depth. Depth buys STRIP
# WIDTH, and it is paid for in floor thickness under the canvas and in riser
# height. 9 mm gives five strips of 12.7 to 17.5 mm.
CANVAS_Z_LO = 4.5        # floor: what the bottom part keeps under the canvas
CANVAS_Z_HI = 13.5       # ceiling: the top part keeps 15 - this above it
CANVAS_INSET = 14.0      # keep the canvas this far from the side faces
CANVAS_MAX_LEAN = 45.0   # trim the fan where a riser would overhang more than this

CONTENT_R = True                         # relief from docs/templates/*.svg
QR_TOP_ZR = 12.2
TXT_TOP_ZR = 12.0


def orbit_dir(P):
    """Unit orbit velocity at a real point: the local mating direction."""
    P = np.asarray(P, dtype=float)
    rv = P - C
    rp = rv - (rv @ E) * E
    v = np.cross(E, rp)
    return v / np.linalg.norm(v)


_B_LO = CANVAS_Z_LO - C[2]                 # height of the canvas floor above the axis
_B_HI = CANVAS_Z_HI - C[2]
CANVAS_K = _B_HI / _B_LO                   # radii step by this constant ratio
CANVAS_RHO0 = _B_LO / np.sin(np.radians(CANVAS_MAX_LEAN))   # innermost printable radius


def axis_normal(phi):
    """Normal of the plane through the axis at phase phi: the orbit direction there.

    phi is both the plane's phase around the axis and its tilt from horizontal,
    and the normal points the way the top part moves.
    """
    return np.sin(phi) * G + np.cos(phi) * ZAX


def canvas_rho_max():
    """Largest radius the canvas region reaches, so the fan knows where to stop."""
    lo, hi = CANVAS_INSET, L - CANVAS_INSET
    best = 0.0
    for x, y in ((lo, lo), (lo, hi), (hi, lo), (hi, hi)):
        g = (x - y - (C[0] - C[1])) / SQ2
        for z in (CANVAS_Z_LO, CANVAS_Z_HI):
            best = max(best, float(np.hypot(g, z - C[2])))
    return best


def canvas_facets():
    """(outer radius, phase) per facet, outward from the printable trim radius.

    Each facet spans the full depth: it starts where its plane crosses the floor
    and ends where it crosses the ceiling, which puts the radii in a geometric
    progression of ratio CANVAS_K.
    """
    stop = canvas_rho_max() * CANVAS_K
    out, rho = [], CANVAS_RHO0
    while rho < stop and len(out) < 40:
        out.append((rho * CANVAS_K, np.arcsin(_B_LO / rho)))
        rho *= CANVAS_K
    return out


def axis_cylinder(radius, sections=512):
    """Solid cylinder of that radius about the rotation axis.

    512 sections keeps the chord error under 0.005 mm at these radii, which is an
    order of magnitude inside the clearance.
    """
    cyl = trimesh.creation.cylinder(radius=radius, height=400.0, sections=sections)
    cyl.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], E))
    cyl.apply_translation(C)
    return cyl


def canvas_solid(delta):
    """Everything under the fan, as a union of wedges.

    With the surface a descending staircase phi(rho), the solid below it is

        U_k [ cylinder(rho <= rho_k+1) AND half-space(phi <= phi_k) ]

    because for a point at radius rho the first qualifying wedge is the one whose
    band contains it, and every later wedge admits only a lower phase. Clearance
    is a true perpendicular gap on both surfaces: facets are normal to the motion
    so their planes shift along their own normal, and cylinders are parallel to
    it so theirs shift in radius.
    """
    wedges = []
    for rho_out, phi in canvas_facets():
        n = axis_normal(phi)
        wedges.append(cap_plane(axis_cylinder(rho_out + delta), C + n * delta, n))
    return trimesh.boolean.union(wedges, engine="manifold")


def facet_frame(fid):
    """(phase, radial unit vector) of one facet, by index from the inside out."""
    _, phi = canvas_facets()[fid - 1]
    return phi, -np.cos(phi) * G + np.sin(phi) * ZAX


def relief_solids(delta):
    """The artwork, raised off its facet along the motion.

    Each facet is normal to the motion, so a relief that is a height field over
    the facet is automatically one in the design plan: no angle to check. Flat
    artwork gets one cap plane parallel to the facet; the cube gets three, tilted
    to meet at its apex, and the lower envelope of those three is the near half of
    a cube squashed onto the surface.
    """
    import json as _json
    from svg_content import artwork as _artwork

    tpl = os.path.join(ROOT, "docs", "templates")
    spec_path = os.path.join(tpl, "relief.json")
    if not os.path.exists(spec_path):
        return []
    meta = {e["facet"]: e for e in
            _json.load(open(os.path.join(tpl, "templates.json")))}
    out = []
    for item in _json.load(open(spec_path)):
        fid = item["facet"]
        geom, _ = _artwork(os.path.join(tpl, item["file"]))
        if geom.is_empty:
            continue
        m = meta[fid]
        phi, radial = facet_frame(fid)
        n = axis_normal(phi)

        def to_wr(px, py):
            return px + m["w0"], m["r1"] - py

        def lift(px, py):
            w, rho = to_wr(px, py)
            return tuple(C + w * E + rho * radial)

        # the artwork keeps its nominal width; the cavity takes the whole gap
        fp = geom_preimage(content_offset(geom, delta), lift, seg=1.0)
        solid = prism(fp, 1, 28, 14)
        if item["kind"] == "flat":
            base = C + (m["w0"] + 0.0) * E          # any point on the facet plane
            origin = C + n * (float(n @ C) * 0.0)   # plane through C at phase phi
            solid = cap_plane(solid, C + n * (item["height"] + delta), n)
        else:
            apex_w, apex_r = to_wr(*item["apex"])
            apex = (C + apex_w * E + apex_r * radial
                    + n * (item["height"] + delta))
            for k in range(len(item["corners"])):
                c0 = item["corners"][k]
                c1 = item["corners"][(k + 1) % len(item["corners"])]
                # a cube seen down its diagonal has a hexagonal silhouette
                # whose corners ALTERNATE in height: the three the edges run to
                # sit at half the apex height, the three between them at zero.
                # Each face is the plane through the apex and two of the former,
                # and it then meets the corner between them at exactly zero.
                half = 0.5 * item["height"]
                p0 = np.array(lift(*c0)) + n * (half + delta)
                p1 = np.array(lift(*c1)) + n * (half + delta)
                nk = np.cross(p0 - apex, p1 - apex)
                nk = nk / np.linalg.norm(nk)
                if nk @ n < 0:
                    nk = -nk
                solid = cap_plane(solid, apex, nk)
        out.append(solid)
    return out


def canvas_footprint():
    """Design-plan footprint of the canvas.

    The curtain around it is parallel to the motion, so it drifts along the orbits
    as it descends -- about 7 mm over the 9 mm of depth. Pre-imaging the region at
    BOTH the floor and the ceiling and intersecting is exact (the drift is
    monotonic in z), and saves having to pad the inset by guesswork.
    """
    reg = shapely.box(CANVAS_INSET, CANVAS_INSET, L - CANVAS_INSET, L - CANVAS_INSET)
    # trim to the printable radius: the cylinder rho = CANVAS_RHO0 meets the floor
    # along the line y - x = m, and its pre-image is that one curve
    gt = np.sqrt(max(CANVAS_RHO0 ** 2 - _B_LO ** 2, 0.0))
    m_trim = SQ2 * gt - (C[0] - C[1])       # the line y - x = m it cuts at the floor
    big = 400.0
    keep = Polygon([(-big, -big + m_trim), (big, big + m_trim),
                    (big, big + 2 * big), (-big, -big + 2 * big)])
    lo = geom_preimage(reg.intersection(keep), lambda x, y: (x, y, CANVAS_Z_LO), seg=2.0)
    hi = geom_preimage(reg, lambda x, y: (x, y, CANVAS_Z_HI), seg=2.0)
    return lo.intersection(hi)


def cap_plane(mesh, origin, normal):
    """Intersect a solid with the half-space under an arbitrary plane."""
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    box = trimesh.creation.box(extents=[500.0, 500.0, 500.0])
    box.apply_translation([0.0, 0.0, -250.0])            # top face on local z = 0
    box.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], n))
    box.apply_translation(np.asarray(origin, dtype=float))
    return trimesh.boolean.intersection([mesh, box], engine="manifold")


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
INWARD = {"front": (0.0, 1.0), "right": (-1.0, 0.0),
          "back": (0.0, -1.0), "left": (1.0, 0.0)}


def inward_plan_dir(name):
    """Unit vector in the DESIGN plan that points into the block, for this face.

    The bend map is not linear, so this is measured rather than assumed: take a
    point in the middle of the face at band height and the same point 1 mm
    inside, pre-image both, and normalise the difference. Over the 20 x 4.5 mm
    of one key, with the axis 185 mm away, that direction is constant to well
    under the clearance.
    """
    lift, n = FACE_LIFT[name], INWARD[name]
    a = np.array(lift(50.0, BAND_Z), dtype=float)
    b = a + np.array([n[0], n[1], 0.0])
    q = preimage_plan(np.vstack([a, b]))
    d = q[1] - q[0]
    return d / np.linalg.norm(d)


def anchor_edge(name):
    """Which horizontal edge of the face trapezoid lies furthest INSIDE the block.

    The straight edition's face-shadow rule, carried across the bend map. As z
    runs over the key the side face sweeps a band of the design plan, and only
    material inboard of it is invisible from outside; the rail therefore has to
    start on whichever trapezoid edge sits furthest in. Because the orbits leave
    the block through two of the four faces and enter through the other two,
    that is the base edge on one pair and the flare's top edge on the other.
    """
    lift = FACE_LIFT[name]
    q = preimage_plan(np.array([lift(50.0, KEY_Z0R), lift(50.0, KEY_Z1R)], float))
    n = inward_plan_dir(name)
    return "base" if q[0] @ n > q[1] @ n else "top"


def rail_box(name, hw, depth):
    """Real-plan rectangle, half-width hw, running `depth` inward from a face.

    Its outer edge sits exactly in the face plane, so when it is pre-imaged at
    the anchor edge's own height it butts that edge exactly -- same real points,
    same pre-image, no sliver and no gap to bridge.
    """
    a, b = 50.0 - hw, 50.0 + hw
    if name == "front":
        return shapely.box(a, 0.0, b, depth)
    if name == "back":
        return shapely.box(a, 100.0 - depth, b, 100.0)
    if name == "left":
        return shapely.box(0.0, a, depth, b)
    return shapely.box(100.0 - depth, a, 100.0, b)


def key_footprints_rot(delta):
    """Design-plan footprints of the four keys (face trapezoid + anchor rail)."""
    trap2d = Polygon([(50 - KEY_HW0R, KEY_Z0R), (50 + KEY_HW0R, KEY_Z0R),
                      (50 + KEY_HW0R, KEY_NECK_ZR), (50 + KEY_HW1R, KEY_Z1R),
                      (50 - KEY_HW1R, KEY_Z1R), (50 - KEY_HW0R, KEY_NECK_ZR)])
    out = []
    for name, lift in FACE_LIFT.items():
        tb = buffered(trap2d, delta)
        trap = geom_preimage(tb, lift, seg=1.0)
        # take the anchor edge off the OFFSET trapezoid, so the rail lands on it
        # exactly at either clearance; a mitred offset moves a flare corner by
        # more than delta, so these cannot be predicted from the nominal numbers
        zz = [c[1] for c in tb.exterior.coords]
        z_rail = min(zz) if anchor_edge(name) == "base" else max(zz)
        xs = [c[0] for c in tb.exterior.coords if abs(c[1] - z_rail) < 1e-9]
        hw = (max(xs) - min(xs)) / 2.0
        rlift = (lambda zr: (lambda x, y: (x, y, zr)))(z_rail)
        rail = geom_preimage(rail_box(name, hw, KEY_RAIL_R + delta), rlift, seg=1.0)
        fp = unary_union([trap, rail])
        if fp.geom_type != "Polygon":
            raise ValueError(f"{name}: key footprint came apart into "
                             f"{len(fp.geoms)} pieces")
        out.append((name, fp))
    return out


def build_L_rot(delta, art=()):
    meshes = []
    # band slab: below the band the interface is the exact flat plane z = 7.5+delta,
    # so the slab is a plain straight box (bending it would only add cap-sag error;
    # the bent features descend below the band and fuse into it)
    t = trimesh.transformations.translation_matrix([50, 50, BAND_Z + delta - 20])
    meshes.append(trimesh.creation.box(extents=[220, 220, 40], transform=t))
    # keys + rails
    for name, fp in key_footprints_rot(delta):
        meshes.append(cap(prism(fp, 1, 28, 14), KEY_Z1R + delta))
    outer = trimesh.boolean.union(meshes, engine="manifold")

    # The canvas floor sits below the seam, so the fan is not a plateau that can be
    # stacked on the slab: each facet climbs from below the seam to above it, so
    # the canvas is a BUMP over roughly its outer two thirds and a WELL over its
    # inner third. Its footprint boundary is therefore a cliff, and a cliff needs
    # clearance like any other sliding wall -- left shared, the two parts graze
    # each other the moment the faceted orbit surfaces rotate out of register.
    #
    # The clearance cannot have one sign, because a bump must shrink where a well
    # must grow. Splitting the cliff into the material the fan ADDS above the slab
    # and the material it CUTS below does it: the additive half takes the footprint
    # offset by delta, the subtractive half by -delta, and each is then correct on
    # its own side with no case analysis.
    fan = canvas_solid(delta)
    fp = canvas_footprint()
    add = prism(buffered(fp, delta), -8, 28, 24)
    sub = prism(buffered(fp, -delta), -8, 28, 24)
    built = trimesh.boolean.union(
        [outer, trimesh.boolean.intersection([fan, add], engine="manifold")],
        engine="manifold")
    built = trimesh.boolean.difference(
        [built, trimesh.boolean.difference([sub, fan], engine="manifold")],
        engine="manifold")
    if CONTENT_R:
        rel = relief_solids(delta)
        if rel:
            built = trimesh.boolean.union([built] + rel, engine="manifold")
    return built


# --------------------------------- build -------------------------------------
def main():
    fac = canvas_facets()
    print(f"interface: a fan of {len(fac)} planes through the rotation axis, each one "
          f"exactly normal to the orbits it meets")
    print(f"  floor z={CANVAS_Z_LO}, ceiling z={CANVAS_Z_HI}, radii stepping by "
          f"{CANVAS_K:.4f}, trimmed at {CANVAS_MAX_LEAN:.0f} deg of riser lean")
    widths = [ro - ro / CANVAS_K for ro, _ in fac]
    tilts = [np.degrees(p) for _, p in fac]
    print(f"  strips {min(widths):.1f} to {max(widths):.1f} mm wide, "
          f"tilts {min(tilts):.1f} to {max(tilts):.1f} deg "
          f"(= the lean of each riser)")
    art = []
    if CONTENT_R:
        print("preparing 2D artwork (real plan)...")
        qr_geom, qr_n, qr_cell = qr_geometry()
        print(f"  QR: {qr_n}x{qr_n} modules, {qr_cell:.2f} mm/module")
        art = [(qr_geom, QR_TOP_ZR),
               (fit_into_box(text_geometry(TITLE), TITLE_BOX), TXT_TOP_ZR),
               (fit_into_box(text_geometry(SUBTITLE), SUB_BOX), TXT_TOP_ZR)]
    else:
        print("content: none (interface left blank)")

    B = stock_box()
    print("building lower solid (bottom offset)...")
    L_lo = build_L_rot(-CLR, art)
    print("building lower solid (top offset)...")
    L_hi = build_L_rot(+CLR, art)

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

    # the four faces must show the same dovetail, or it is not this puzzle
    zs = np.arange(BAND_Z + 0.5, KEY_Z1R - CLR - 0.05, 0.1)
    prof = face_key_profile(bottom, zs)
    spread = 0.0
    for i, z in enumerate(zs):
        vals = [prof[nm][i] for nm, *_ in FACE_SPECS]
        if any(v[0] is None for v in vals):
            spread = float("inf")
            continue
        spread = max(spread,
                     max(v[0] for v in vals) - min(v[0] for v in vals),
                     max(v[1] for v in vals) - min(v[1] for v in vals))
    face_ok = spread <= 0.05
    ok_all &= face_ok
    print(f"face fidelity: spread between the four faces {spread:.3f} mm -> "
          f"{'PASS' if face_ok else 'FAIL'}")
    report["face_spread_mm"] = spread

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
