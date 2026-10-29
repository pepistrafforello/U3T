# -*- coding: utf-8 -*-
"""Lay out the CDP mark on the fan: the cube on one facet, the word on another.

Moving the rotation axis in to thicken the dovetail halved the canvas -- that is
the trade the axis makes, strip width against wing thickness -- so the fan now has
three usable facets instead of five, and the content is two pieces instead of
three. The cube goes on the widest strip, because it needs width; the word goes on
the longest one, because it needs length.
"""
import json
import os
import re
import sys

import numpy as np
import shapely
from lxml import etree
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from scipy.ndimage import distance_transform_edt, grey_dilation
from shapely.affinity import scale as sc, translate as tr
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from svgelements import SVG, Shape

ROOT = r"C:\Users\StrafforelloGiuseppe\Downloads\U3T-repo"
TPL = os.path.join(ROOT, "docs", "templates")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import svg_content  # noqa: E402

FONT, WEIGHT = "Century Gothic", "bold"
MIN_FEATURE, SAFE, RES = 0.55, 1.0, 0.015
TEXTS = ["\u201380\u2013", "Louis Andre III"]   # en dash: Century Gothic Bold
                                 # has no U+2012 figure dash
MIN_WALL_SLS = 0.8        # the rule the part is actually made to
NS = "{http://www.w3.org/2000/svg}"

meta = {e["facet"]: e for e in json.load(open(os.path.join(TPL, "templates.json")))}


def usable(fid):
    p = Polygon(meta[fid]["page_outlines"][0]).buffer(-SAFE)
    return p if p.geom_type == "Polygon" else max(p.geoms, key=lambda q: q.area)


def inradius(fid):
    """Radius of the largest circle that fits the facet, which is what the cube needs.

    Not the strip width: these facets are slanted, so a bounding box flatters them
    badly -- one of them measured 15.1 mm wide and held an 8.2 mm circle.
    """
    p = usable(fid)
    lo, hi = 0.0, 0.5 * max(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1])
    for _ in range(40):
        mid = (lo + hi) / 2
        if p.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return lo


def pick_facets(n_texts):
    """Cube on the roundest facet; each text on the longest facet still free.

    Picked by measurement every run, because the fan reshapes whenever the axis or
    the trim angle moves and a hard-coded facet number goes quietly stale.
    """
    ids = sorted(k for k in meta if k != "combined")
    cube = max(ids, key=inradius)
    rest = sorted((k for k in ids if k != cube),
                  key=lambda k: meta[k]["length_mm"], reverse=True)
    if len(rest) < n_texts:
        raise SystemExit(f"only {len(rest)} facets free for {n_texts} texts")
    return cube, rest[:n_texts]


def widest(poly, h, step=0.2):
    y0, y1 = poly.bounds[1], poly.bounds[3]
    best, where, y = 0.0, None, y0
    while y + h <= y1 + 1e-9:
        lo, hi, ok = -1e9, 1e9, True
        for yy in np.linspace(y, y + h, 11):
            seg = poly.intersection(box(poly.bounds[0] - 1, yy - 1e-4,
                                        poly.bounds[2] + 1, yy + 1e-4))
            if seg.is_empty:
                ok = False
                break
            lo, hi = max(lo, seg.bounds[0]), min(hi, seg.bounds[2])
        if ok and hi - lo > best:
            best, where = hi - lo, (lo, y, hi, y + h)
        y += step
    return best, where


def glyphs(txt, cap):
    tp = TextPath((0, 0), txt, size=100.0,
                  prop=FontProperties(family=FONT, weight=WEIGHT))
    rings = [Polygon(p).buffer(0) for p in tp.to_polygons() if len(p) >= 3]
    rings = [r for r in rings if r.area > 1e-9]
    rings.sort(key=lambda p: p.area, reverse=True)
    acc = None
    for q in rings:
        acc = q if acc is None else (acc.difference(q)
              if acc.contains(q.representative_point()) else acc.union(q))
    # SVG pages run y downwards; TextPath builds glyphs y upwards
    return sc(acc, xfact=cap / 72.0, yfact=-cap / 72.0, origin=(0, 0))


def narrowest(geom, res=RES):
    """Width of the THINNEST stroke, from the ridge of the distance transform.

    A high percentile measures the fattest glyph instead, which is why dropping a
    'B' from a string once appeared to make its strokes thinner.
    """
    x0, y0, x1, y1 = geom.bounds
    xs = x0 - res + np.arange(int((x1 - x0) / res) + 4) * res
    ys = y0 - res + np.arange(int((y1 - y0) / res) + 4) * res
    X, Y = np.meshgrid(xs, ys)
    m = shapely.contains_xy(geom, X.ravel(), Y.ravel()).reshape(Y.shape)
    if not m.any():
        return 0.0
    dt = distance_transform_edt(m) * res
    ridge = m & (dt >= grey_dilation(dt, size=5) - 1e-9) & (dt > res)
    return 2.0 * np.percentile(dt[ridge], 5) if ridge.any() else 0.0


def fit_text(txt, fid, band):
    """Largest cap height at which `txt` fits inside facet `fid`.

    The band is measured at the height the TEXT actually needs, not at the full
    width of the facet. Reserving the whole width makes the usable box far too
    narrow on a tapering strip -- it cost "Louis Andre III" its last 30 % of cap
    height, and with it the 0.8 mm minimum stroke.
    """
    poly = usable(fid)
    lo, hi, best = 1.0, band, None
    for _ in range(30):
        mid = (lo + hi) / 2
        g = glyphs(txt, mid)
        gh = g.bounds[3] - g.bounds[1]
        if gh > band:
            hi = mid
            continue
        bw, bb = widest(poly, gh)
        if bb is not None and (g.bounds[2] - g.bounds[0]) <= bw:
            lo, best = mid, (g, bb, bw)
        else:
            hi = mid
    if best is None:
        raise SystemExit(f"{txt!r} does not fit facet {fid} at any size")
    g, bb, bw = best
    gx0, gy0, gx1, gy1 = g.bounds
    g = tr(g, (bb[0] + bb[2]) / 2 - (gx0 + gx1) / 2,
              (bb[1] + bb[3]) / 2 - (gy0 + gy1) / 2)
    return g, lo, bw, narrowest(g)


CUBE_FACET, TEXT_FACETS = pick_facets(len(TEXTS))
print(f"facets: emblem on {CUBE_FACET} (inscribed circle "
      f"{2 * inradius(CUBE_FACET):.1f} mm)"
      + "".join(f", {t} on {f}" for t, f in zip(TEXTS, TEXT_FACETS)))

# --------------------------------------------------------------- the emblem
def beret_silhouette(size_mm):
    """A stylized military beret, one closed outline, `size_mm` at its widest.

    Drawn rather than built from primitives, because unioning ellipses kept
    producing a loaf: the cue that says beret is the crown OVERHANGING a narrower
    headband, and that step has to be placed, not hoped for. The outline is a unit
    frame with the band's underside on y = 0 -- band, flared crown, stalk -- then
    scaled so the widest dimension matches what the cube emblem used, and centered
    on its own centroid.

    Returns the outline and the crown's center, which is where the dome rides.
    """
    pts = [(0.66, 0.00), (-0.76, 0.00), (-0.80, 0.22), (-1.02, 0.30),
           (-1.10, 0.46), (-1.02, 0.62), (-0.86, 0.76), (-0.56, 0.86),
           (-0.18, 0.92), (0.20, 0.90), (0.54, 0.84), (0.80, 0.72),
           (0.96, 0.56), (1.02, 0.40), (0.94, 0.28), (0.76, 0.22), (0.70, 0.08)]
    sil = Polygon(pts)
    sil = unary_union([sil, Point(0.32, 0.98).buffer(0.11, quad_segs=48)])
    sil = Polygon(max(getattr(sil, "geoms", [sil]), key=lambda q: q.area).exterior)
    sil = sil.buffer(0.05, join_style=1).buffer(-0.05, join_style=1)
    sil = Polygon(max(getattr(sil, "geoms", [sil]), key=lambda q: q.area).exterior)
    k = size_mm / max(sil.bounds[2] - sil.bounds[0], sil.bounds[3] - sil.bounds[1])
    # the template page runs y DOWNWARDS, so the outline is drawn crown-up and
    # then flipped, exactly as the glyph outlines are
    sil = sc(sil, xfact=k, yfact=-k, origin=(0.0, 0.0))
    crown = Point(-0.05 * k, -0.52 * k)
    c = sil.centroid
    return tr(sil, -c.x, -c.y), tr(crown, -c.x, -c.y)


_fc = usable(CUBE_FACET)
_lo, _hi = 0.0, 0.5 * max(_fc.bounds[2] - _fc.bounds[0],
                          _fc.bounds[3] - _fc.bounds[1])
for _ in range(40):
    _mid = (_lo + _hi) / 2
    if _fc.buffer(-_mid).is_empty:
        _hi = _mid
    else:
        _lo = _mid
_centre = _fc.buffer(-_lo * 0.98).representative_point()
EMBLEM_MM = round(2 * _lo * 0.96, 1)

sil_s, _crown = beret_silhouette(EMBLEM_MM)
cx, cy = _centre.x, _centre.y
sil_s = tr(sil_s, cx, cy)
DOME_CX, DOME_CY = _crown.x + cx, _crown.y + cy
_P = np.asarray(sil_s.exterior.coords)
DOME_R = float(np.max(np.hypot(_P[:, 0] - DOME_CX, _P[:, 1] - DOME_CY)))

print(f"beret {EMBLEM_MM} mm across, centered on facet {CUBE_FACET}")
print(f"  raised area {sil_s.area:.1f} mm2, dome radius {DOME_R:.2f} mm")
print(f"  inside the facet: {'yes' if _fc.contains(sil_s) else 'NO'}")
_thin = narrowest(sil_s)
print(f"  thinnest raised feature {_thin:.2f} mm  "
      f"{'OK' if _thin >= MIN_WALL_SLS else 'THIN for SLS'}")


# ---------------------------------------------------------------- the text
laid = []
for _txt, _fid in zip(TEXTS, TEXT_FACETS):
    _fw = usable(_fid)
    _band = round(min(_fw.bounds[3] - _fw.bounds[1],
                      _fw.bounds[2] - _fw.bounds[0]) - 0.6, 1)
    _g, _cap, _bw, _st = fit_text(_txt, _fid, _band)
    laid.append((_fid, _txt, _g))
    print(f"  {_txt:20s} facet {_fid}  box {_bw:5.1f}  cap {_cap:4.2f} mm  "
          f"thinnest {_st:4.2f} mm  "
          f"{'OK' if _st >= MIN_WALL_SLS else 'THIN for SLS'}")
    if _st < MIN_WALL_SLS:
        raise SystemExit(f"{_txt} on facet {_fid} would print at {_st:.2f} mm, "
                         f"under the {MIN_WALL_SLS} mm minimum")


# ---------------------------------------------------------------- write SVGs
def to_paths(geom):
    """One path per polygon, holes as further subpaths of the same path.

    Emitting a hole as its own <path> fills it back in instead of cutting it.
    """
    out = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty or g.geom_type != "Polygon":
            continue
        subs = []
        for ring in [g.exterior] + list(g.interiors):
            pts = np.asarray(ring.coords)
            subs.append("M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z")
        out.append(" ".join(subs))
    return out


def inject(fid, geom, name):
    """Replace the artwork layer wholesale, so re-running is safe."""
    path = os.path.join(TPL, f"facet_{fid}.svg")
    tree = etree.parse(path)
    grp = next(n for n in tree.getroot().iter() if n.get("id") == "artwork")
    for child in list(grp):
        grp.remove(child)
    for d in to_paths(geom):
        etree.SubElement(grp, NS + "path", d=d, fill="#1a1a1a",
                         **{"fill-rule": "evenodd"})
    tree.write(path, encoding="utf-8", xml_declaration=False, pretty_print=True)
    print(f"  wrote {name} -> facet_{fid}.svg")


# The three edges are RIDGES on a cube, not valleys: the pyramid raises them by
# itself where its faces meet. Engraving them as grooves would cut away exactly
# the feature the relief creates, so the artwork is the plain silhouette and the
# grooves survive only as the way the three edge directions were found.
inject(CUBE_FACET, sil_s, "the beret")
for _fid, _txt, _g in laid:
    inject(_fid, _g, _txt)
_used = {CUBE_FACET} | {f for f, _, _ in laid}
for _f in sorted(k for k in meta if k != "combined"):
    if _f not in _used:
        inject(_f, shapely.geometry.GeometryCollection(), "nothing")

# ---------------------------------------------------------- the relief spec
# The cube is not flat: its three faces are the near half of a real cube, cut
# perpendicular to the view direction and squashed. Each face is the plane
# through the apex and two alternating corners of the hexagon, and the surface
# is the lower envelope of the three -- which is exactly what the drawing draws.
# Heights are NOMINAL: each half takes CLR off, so a relief asked for at h stands
# h - 0.15 on the built part. The cube is a third of a true cube of its silhouette,
# which is what makes it read as a solid rather than a hexagon.
RELIEF_TEXT, RELIEF_EMBLEM, RELIEF_RIM = 0.95, 3.15, 0.95
spec = [dict(facet=f, file=f"facet_{f}.svg", kind="flat", height=RELIEF_TEXT)
        for f, _, _ in laid]
spec.append(dict(facet=CUBE_FACET, file=f"facet_{CUBE_FACET}.svg", kind="dome",
                 height=RELIEF_EMBLEM, rim=RELIEF_RIM,
                 center=[DOME_CX, DOME_CY], radius=DOME_R))
with open(os.path.join(TPL, "relief.json"), "w") as fh:
    json.dump(spec, fh, indent=1)
print(f"  relief spec: text {RELIEF_TEXT} mm nominal, dome {RELIEF_EMBLEM} mm "
      f"at the crown falling to {RELIEF_RIM} mm at the rim")
