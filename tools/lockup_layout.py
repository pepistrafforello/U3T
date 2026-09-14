# -*- coding: utf-8 -*-
"""Lay out the Terrier CDP lockup on facets 4, 3 and 2, and write the SVGs."""
import json
import os
import sys

import numpy as np
import shapely
from lxml import etree
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from scipy.ndimage import distance_transform_edt, grey_dilation
from shapely.affinity import scale as sc, translate as tr
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from svgelements import SVG, Shape

ROOT = r"C:\Users\StrafforelloGiuseppe\Downloads\U3T-repo"
TPL = os.path.join(ROOT, "docs", "templates")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import svg_content  # noqa: E402

FONT, WEIGHT = "Century Gothic", "bold"
MIN_FEATURE, SAFE, CUBE_MM, RES = 0.55, 1.0, 12.5, 0.015
NS = "{http://www.w3.org/2000/svg}"

meta = {e["facet"]: e for e in json.load(open(os.path.join(TPL, "templates.json")))}


def usable(fid):
    p = Polygon(meta[fid]["page_outlines"][0]).buffer(-SAFE)
    return p if p.geom_type == "Polygon" else max(p.geoms, key=lambda q: q.area)


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
    bw, bb = widest(usable(fid), band)
    lo, hi = 1.0, band
    for _ in range(26):
        mid = (lo + hi) / 2
        g = glyphs(txt, mid)
        if (g.bounds[2] - g.bounds[0]) <= bw:
            lo = mid
        else:
            hi = mid
    g = glyphs(txt, lo)
    gx0, gy0, gx1, gy1 = g.bounds
    g = tr(g, (bb[0] + bb[2]) / 2 - (gx0 + gx1) / 2,
              (bb[1] + bb[3]) / 2 - (gy0 + gy1) / 2)
    return g, lo, bw, narrowest(g)


# ---------------------------------------------------------------- the logo
backup = os.path.join(ROOT, "build", "artwork_backup")
src = sorted(f for f in os.listdir(backup) if f.endswith(".svg"))[-1]
svg = SVG.parse(svg_content._without_template(os.path.join(backup, src)),
                reify=True, ppi=25.4)
parts = []
for el in svg.elements():
    if not isinstance(el, Shape):
        continue
    rings = [Polygon(r).buffer(0) for r in svg_content._rings(el) if len(r) >= 3]
    rings = [r for r in rings if r.area > 1e-9]
    if rings:
        parts.append(unary_union(rings))
sil = unary_union(parts)
sil = Polygon(max(getattr(sil, "geoms", [sil]), key=lambda p: p.area).exterior)
edges = unary_union([p.exterior for p in parts]).intersection(sil.buffer(-0.01))


def hex_vertices(poly):
    """The six corner directions of the rounded hexagon, by angular radius."""
    c = poly.centroid
    ang = np.linspace(-np.pi, np.pi, 1441)[:-1]
    rad = []
    for a in ang:
        far = shapely.geometry.LineString(
            [(c.x, c.y), (c.x + 400 * np.cos(a), c.y + 400 * np.sin(a))])
        it = far.intersection(poly)
        rad.append(it.length if not it.is_empty else 0.0)
    rad = np.array(rad)
    peaks = []
    for i in range(len(ang)):
        w = [(i + k) % len(ang) for k in range(-40, 41)]
        if rad[i] == rad[w].max() and rad[i] > 0:
            if not peaks or min(abs(ang[i] - ang[j]) for j in peaks) > 0.35:
                peaks.append(i)
    peaks.sort(key=lambda i: -rad[i])
    peaks = sorted(peaks[:6], key=lambda i: ang[i])
    return [(ang[i], rad[i]) for i in peaks]


verts = hex_vertices(sil)
print(f"silhouette corners found: {len(verts)} at "
      f"{[round(np.degrees(a)) for a, _ in verts]} degrees")

scale = CUBE_MM / max(sil.bounds[2] - sil.bounds[0], sil.bounds[3] - sil.bounds[1])
sil_s = sc(sil, xfact=scale, yfact=scale, origin="centroid")
# the three structural edges of the cube: centre to alternating corners. Pick
# the triple that matches the drawing's own internal lines.
best = None
for off in (0, 1):
    segs = []
    for k in range(off, len(verts), 2):
        a, r = verts[k]
        segs.append(shapely.geometry.LineString(
            [(sil.centroid.x, sil.centroid.y),
             (sil.centroid.x + 0.86 * r * np.cos(a),
              sil.centroid.y + 0.86 * r * np.sin(a))]))
    cand = unary_union(segs)
    score = cand.buffer(1.5).intersection(edges).length
    print(f"  triple offset {off}: {len(segs)} edges, match {score:.0f} mm")
    if best is None or score > best[0]:
        best = (score, cand)
edges = best[1]
edg_s = sc(edges, xfact=scale, yfact=scale, origin=sil.centroid)
f3 = usable(3)
cx, cy = f3.centroid.x, f3.centroid.y
sil_s = tr(sil_s, cx - sil_s.centroid.x, cy - sil_s.centroid.y)
edg_s = tr(edg_s, cx - edg_s.centroid.x, cy - edg_s.centroid.y)
groove = edg_s.buffer(MIN_FEATURE / 2, cap_style=2, join_style=2)
cube = sil_s.difference(groove)

print(f"logo {CUBE_MM} mm (scaled {scale:.3f}x), centred on facet 3")
print(f"  raised area {cube.area:.1f} mm2 in "
      f"{len(list(getattr(cube, 'geoms', [cube])))} islands, "
      f"grooves {groove.intersection(sil_s).area:.1f} mm2")
print(f"  inside the facet: {'yes' if f3.contains(sil_s) else 'NO'}")
print(f"  thinnest raised feature {narrowest(cube):.2f} mm")

# ---------------------------------------------------------------- the text
top, cap1, bw1, st1 = fit_text("Terrier CDP", 4, 8.0)
bot, cap2, bw2, st2 = fit_text("Titan Technologies", 2, 6.0)
for label, fid, cap, bw, st in (("Terrier CDP", 4, cap1, bw1, st1),
                                ("Titan Technologies", 2, cap2, bw2, st2)):
    print(f"  {label:20s} facet {fid}  box {bw:5.1f}  cap {cap:4.2f} mm  "
          f"thinnest {st:4.2f} mm  {'OK' if st >= MIN_FEATURE else 'THIN'}")


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


inject(4, top, "Terrier CDP")
# The three edges are RIDGES on a cube, not valleys: the pyramid raises them by
# itself where its faces meet. Engraving them as grooves would cut away exactly
# the feature the relief creates, so the artwork is the plain silhouette and the
# grooves survive only as the way the three edge directions were found.
inject(3, sil_s, "the cube silhouette")
inject(2, bot, "Titan Technologies")

# ---------------------------------------------------------- the relief spec
# The cube is not flat: its three faces are the near half of a real cube, cut
# perpendicular to the view direction and squashed. Each face is the plane
# through the apex and two alternating corners of the hexagon, and the surface
# is the lower envelope of the three -- which is exactly what the drawing draws.
RELIEF_TEXT, RELIEF_CUBE = 0.8, 1.1
chosen = [a for k, (a, _) in enumerate(verts) if k % 2 == 0]
corners = [[cx + scale * r * np.cos(a), cy + scale * r * np.sin(a)]
           for a, (_, r) in zip(chosen, [verts[k] for k in range(0, len(verts), 2)])]
spec = [
    dict(facet=4, file="facet_4.svg", kind="flat", height=RELIEF_TEXT),
    dict(facet=3, file="facet_3.svg", kind="pyramid", height=RELIEF_CUBE,
         apex=[cx, cy], corners=corners),
    dict(facet=2, file="facet_2.svg", kind="flat", height=RELIEF_TEXT),
]
with open(os.path.join(TPL, "relief.json"), "w") as fh:
    json.dump(spec, fh, indent=1)
print(f"  relief spec: text {RELIEF_TEXT} mm, cube apex {RELIEF_CUBE} mm, "
      f"corners at {[round(np.degrees(a)) for a in chosen]} deg")
