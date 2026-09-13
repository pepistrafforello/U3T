"""Drawing templates for the five canvas facets of the rotation edition.

The shapes are read off the built mesh, not recomputed, so a template is exactly
the surface that exists -- clearance, curtain and trim already accounted for.

Each facet is flat, and on it the pair

    w    = distance along the rotation axis
    rho  = distance out from the rotation axis

is orthonormal, so millimetres on the template are millimetres on the part. The
risers between facets sit at constant rho and therefore occupy *no* width in this
coordinate: laying the facets side by side in rho gives one continuous sheet,
which is `canvas_combined.svg`. That is also what a viewer sees looking along the
motion, the one direction in which the risers are edge-on.

Page coordinates are millimetres with the origin at the top left, and the mapping
back to the part is recorded in templates.json, so artwork drawn anywhere on the
page lands where it was drawn:

    w = page_x + w0        rho = r1 - page_y

    python tools/facet_templates.py
"""
import json
import os
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "templates")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT)

import u3t_generator as g            # noqa: E402
import u3t_rot_generator as r        # noqa: E402

PAD = 6.0          # mm of paper around the shape
SAFE = 1.0         # mm of margin inside the edge that artwork should respect
GRID = 5.0         # mm
CAPTION = 5.0      # mm of room under the shape for the caption


def facet_polygon(mesh, phi, delta):
    """The facet's real surface, as a polygon in its own (w, rho) millimetres."""
    n = r.axis_normal(phi)
    radial = -np.cos(phi) * r.G + np.sin(phi) * r.ZAX
    target = float(n @ r.C) + delta
    tri = mesh.vertices[mesh.faces]
    keep = ((mesh.face_normals @ n > 0.9999) &
            (np.abs(tri.mean(axis=1) @ n - target) < 1e-3))
    if not keep.any():
        return None
    rel = tri[keep] - r.C
    flat = np.stack([rel @ r.E, rel @ radial], axis=-1)
    polys = [Polygon(p) for p in flat if Polygon(p).area > 1e-9]
    out = unary_union(polys).buffer(1e-6).buffer(-1e-6)
    if out.geom_type != "Polygon":
        out = max(out.geoms, key=lambda p: p.area)
    # the boolean leaves a few sub-mm2 slivers in the triangulation; they do not
    # change the area (identical to 0.1 mm2 across a 20x range of face tolerance)
    # but they would print on the template as phantom holes
    keep = [ring for ring in out.interiors if Polygon(ring).area > 1.0]
    return Polygon(out.exterior, keep).simplify(0.01)


def path_d(ring):
    """One SVG path. Shapes arrive already in page millimetres, y running down."""
    return ("M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in np.asarray(ring.coords))
            + " Z")


def write_svg(path, shapes, caption, title, note):
    """shapes: polygons in page millimetres, origin already at (PAD, PAD)."""
    w = max(s.bounds[2] for s in shapes) + PAD
    h = max(s.bounds[3] for s in shapes) + PAD + CAPTION
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" '
         f'height="{h:.2f}mm" viewBox="0 0 {w:.2f} {h:.2f}">',
         f"  <!-- {title}. 1 user unit = 1 mm, origin top left. -->",
         f"  <!-- {note} -->",
         '  <g id="template" fill="none" stroke-width="0.12">']
    for x in np.arange(0.0, w, GRID):
        p.append(f'    <line x1="{x:.2f}" y1="0" x2="{x:.2f}" y2="{h:.2f}" '
                 f'stroke="#ececec"/>')
    for y in np.arange(0.0, h, GRID):
        p.append(f'    <line x1="0" y1="{y:.2f}" x2="{w:.2f}" y2="{y:.2f}" '
                 f'stroke="#ececec"/>')
    for s in shapes:
        p.append(f'    <path d="{path_d(s.exterior)}" stroke="#c0392b" '
                 f'stroke-width="0.25"/>')
        inner = s.buffer(-SAFE)
        for q in ([inner] if inner.geom_type == "Polygon" else list(inner.geoms)):
            if not q.is_empty:
                p.append(f'    <path d="{path_d(q.exterior)}" stroke="#8FB0D8" '
                         f'stroke-width="0.15" stroke-dasharray="1.2,1.2"/>')
    p.append(f'    <text x="{PAD:.2f}" y="{h - 1.4:.2f}" font-family="sans-serif" '
             f'font-size="2.4" fill="#7d8288" stroke="none">{caption}</text>')
    p.append("  </g>")
    p.append('  <g id="artwork">')
    p.append("    <!-- draw here: closed filled paths only, nothing under 0.55 mm -->")
    p.append("  </g>")
    p.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(p) + "\n")


def main():
    mesh = trimesh.load(os.path.join(ROOT, "stl", "U3T_rot_bottom.stl"))
    found = []
    for rho_out, phi in r.canvas_facets():
        poly = facet_polygon(mesh, phi, -g.CLR)
        if poly is not None and poly.area >= 5.0:
            found.append((rho_out, phi, poly))

    print(f"{len(found)} facets carry a usable surface\n")
    print("  #   tilt    length    width      area")
    meta, sheets = [], []
    rho_top = max(p.bounds[3] for _, _, p in found)
    w_min = min(p.bounds[0] for _, _, p in found)
    for i, (rho_out, phi, poly) in enumerate(found, start=1):
        x0, y0, x1, y1 = poly.bounds
        print(f" {i:2d}  {np.degrees(phi):5.1f}  {x1-x0:7.1f}  {y1-y0:7.1f}  "
              f"{poly.area:8.0f} mm2")
        # per-facet page: origin PAD in from the facet's own corner
        w0, r1 = x0 - PAD, y1 + PAD
        page = Polygon([(x - w0, r1 - y) for x, y in poly.exterior.coords])
        cap = (f"facet {i} of {len(found)} &#183; {x1-x0:.1f} &#215; {y1-y0:.1f} mm "
               f"&#183; tilt {np.degrees(phi):.1f}&#176; &#183; grid 5 mm &#183; "
               f"min feature 0.55 mm &#183; dashed line = 1 mm safe margin")
        write_svg(os.path.join(OUT, f"facet_{i}.svg"), [page], cap,
                  f"U3T rotation edition, canvas facet {i}",
                  "x runs along the rotation axis; y is radial, and the top edge "
                  "of the shape is the riser.")
        meta.append(dict(facet=i, file=f"facet_{i}.svg", w0=w0, r1=r1,
                         tilt_deg=float(np.degrees(phi)),
                         rho_in=float(y0), rho_out=float(y1),
                         length_mm=float(x1 - x0), width_mm=float(y1 - y0),
                         area_mm2=float(poly.area)))
        # combined page: one frame shared by every facet
        sheets.append(Polygon([(x - (w_min - PAD), (rho_top + PAD) - y)
                               for x, y in poly.exterior.coords]))

    cap = (f"U3T canvas &#183; all {len(found)} facets &#183; "
           f"{sum(s.area for s in sheets):.0f} mm&#178; &#183; horizontal seams are "
           f"risers and cost no width here &#183; grid 5 mm &#183; min feature 0.55 mm")
    write_svg(os.path.join(OUT, "canvas_combined.svg"), sheets, cap,
              "U3T rotation edition, all facets on one continuous sheet",
              "Artwork may cross the seams: viewed along the motion they have "
              "no width.")
    meta.append(dict(facet="combined", file="canvas_combined.svg",
                     w0=w_min - PAD, r1=rho_top + PAD,
                     area_mm2=float(sum(s.area for s in sheets))))
    json.dump(meta, open(os.path.join(OUT, "templates.json"), "w"), indent=1)
    print(f"\ncombined sheet {sum(s.area for s in sheets):.0f} mm2 in {len(sheets)} "
          f"strips -> {OUT}")


if __name__ == "__main__":
    main()
