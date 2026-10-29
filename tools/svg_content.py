"""Read artwork drawn on a facet template back into the generator.

The templates in docs/templates are millimeter-true SVG. Draw on them in Inkscape
(or anything that writes SVG), convert everything to closed filled paths, and this
turns the result into the shapely polygons the relief is extruded from.

    python tools/svg_content.py docs/templates/facet_3.svg

Everything outside the layer named `template` is treated as artwork, so the
outline, safe margin, grid and labels that came with the template are ignored and
can be left in place.

Checks, which are the point of running this before a build:
  * closed filled regions only -- an open path or a bare stroke has no area and
    would extrude to nothing
  * every stroke at least MIN_FEATURE wide, and every gap between strokes too
  * nothing outside the facet, and nothing inside the safe margin
"""
import io
import os
import sys

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from svgelements import SVG, Path, Shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import u3t_generator as g            # noqa: E402

FLATNESS = 0.05      # mm: how finely curves are sampled into segments
TEMPLATE_LAYER = "template"


def _rings(shape, flatness=FLATNESS):
    """Flatten one SVG shape into closed rings of millimeter points."""
    path = Path(shape) if not isinstance(shape, Path) else shape
    rings, cur = [], []
    for seg in path.segments():
        name = type(seg).__name__
        if name == "Move":
            if len(cur) >= 3:
                rings.append(cur)
            cur = [(seg.end.x, seg.end.y)]
        elif name == "Close":
            if len(cur) >= 3:
                rings.append(cur)
            cur = []
        else:
            length = seg.length(error=1e-3) or 0.0
            n = max(2, int(np.ceil(length / flatness)))
            for i in range(1, n + 1):
                p = seg.point(i / n)
                cur.append((p.x, p.y))
    if len(cur) >= 3:
        rings.append(cur)
    return rings


def _without_template(svg_path):
    """The file with the template layer removed, so only artwork is left.

    Done on the XML rather than by inspecting the parsed tree: element ancestry is
    an implementation detail of the parser, but "delete the node with this id" is
    not.
    """
    from lxml import etree
    tree = etree.parse(svg_path)
    for node in tree.getroot().iter():
        if node.get("id") == TEMPLATE_LAYER:
            node.getparent().remove(node)
    return io.BytesIO(etree.tostring(tree))


def artwork(svg_path, flatness=FLATNESS):
    """All artwork in the file as one shapely geometry, in page millimeters."""
    svg = SVG.parse(_without_template(svg_path), reify=True, ppi=25.4)
    out, skipped = [], 0
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        rings = _rings(el, flatness)
        if not rings:
            skipped += 1
            continue
        polys = []
        for ring in rings:
            p = Polygon(ring)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty and p.area > 1e-9:
                polys.append(p)
        if not polys:
            skipped += 1
            continue
        # even-odd: a ring inside another punches a hole, as a glyph counter does
        polys.sort(key=lambda q: q.area, reverse=True)
        acc = None
        for q in polys:
            if acc is None:
                acc = q
            elif acc.contains(q.representative_point()):
                acc = acc.difference(q)
            else:
                acc = acc.union(q)
        out.append(acc)
    return unary_union(out) if out else Polygon(), skipped


def narrowest(geom, res=0.015):
    """Width of the thinnest stroke, from the ridge of the distance transform.

    Eroding and measuring the leftover area counts the sharp corner of every
    glyph, so text always looked thin no matter how heavy it was. The ridge of
    the distance transform is the centerline of each stroke, and twice its value
    there is the stroke width; a low percentile finds the narrowest one.
    """
    import numpy as _np
    import shapely as _sh
    from scipy.ndimage import distance_transform_edt, grey_dilation
    x0, y0, x1, y1 = geom.bounds
    xs = x0 - res + _np.arange(int((x1 - x0) / res) + 4) * res
    ys = y0 - res + _np.arange(int((y1 - y0) / res) + 4) * res
    X, Y = _np.meshgrid(xs, ys)
    m = _sh.contains_xy(geom, X.ravel(), Y.ravel()).reshape(Y.shape)
    if not m.any():
        return 0.0
    dt = distance_transform_edt(m) * res
    ridge = m & (dt >= grey_dilation(dt, size=5) - 1e-9) & (dt > res)
    return 2.0 * _np.percentile(dt[ridge], 5) if ridge.any() else 0.0


def check(geom, facet=None, safe=1.0, min_feature=g.MIN_FEATURE):
    """Report what would go wrong before it reaches the printer."""
    problems = []
    parts = list(getattr(geom, "geoms", [geom]))
    parts = [p for p in parts if not p.is_empty]
    if not parts:
        return ["no artwork found: is everything still live text, or stroked only?"]

    stroke = narrowest(geom)
    if stroke < min_feature:
        problems.append(f"thinnest stroke is {stroke:.2f} mm, under the "
                        f"{min_feature} mm minimum")
    gaps = geom.buffer(min_feature / 2).buffer(-min_feature / 2).difference(geom)
    if gaps.area > 0.05:
        problems.append(f"{gaps.area:.2f} mm2 of gap between strokes is under "
                        f"{min_feature} mm; neighbouring shapes will fuse")
    if facet is not None:
        outside = geom.difference(facet)
        if outside.area > 1e-3:
            problems.append(f"{outside.area:.2f} mm2 falls outside the facet")
        margin = geom.difference(facet.buffer(-safe))
        if margin.area > 1e-3:
            problems.append(f"{margin.area:.2f} mm2 sits inside the {safe} mm "
                            f"safe margin at the edge")
    return problems


def facet_of(svg_path):
    """The drawable region for this template, from templates.json, or None."""
    import json
    meta_path = os.path.join(ROOT, "docs", "templates", "templates.json")
    if not os.path.exists(meta_path):
        return None
    name = os.path.basename(svg_path)
    for entry in json.load(open(meta_path)):
        if entry.get("file") == name and entry.get("page_outlines"):
            strips = [Polygon(ring) for ring in entry["page_outlines"]]
            merged = unary_union(strips)
            # On the combined sheet the seams between strips are internal: the
            # surface continues across them, stepped, and artwork is meant to
            # cross. Close the sub-millimeter gaps the clearance leaves between
            # adjacent strips so the margin applies to the outer edge only.
            if len(strips) > 1:
                merged = merged.buffer(0.4).buffer(-0.4)
            return merged
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for path in sys.argv[1:]:
        geom, skipped = artwork(path)
        shapes, regions = count_shapes(path), (
            len(list(getattr(geom, "geoms", [geom]))) if not geom.is_empty else 0)
        print(f"\n{os.path.basename(path)}")
        print(f"  {shapes} drawn shape(s) -> {regions} separate raised region(s), "
              f"{geom.area:.1f} mm2 of relief"
              + (f"; {skipped} with no area skipped" if skipped else ""))
        if not geom.is_empty:
            x0, y0, x1, y1 = geom.bounds
            print(f"  occupies {x1-x0:.1f} x {y1-y0:.1f} mm at page "
                  f"({x0:.1f}, {y0:.1f})")
        if shapes > regions and regions:
            print(f"  note: {shapes} shapes merged into {regions}. Relief has one "
                  f"height, so color and opacity do not survive -- overlapping "
                  f"shapes become a single raised blob.")
        facet = facet_of(path)
        if facet is None:
            print("  (no facet outline on file for this template, "
                  "so containment is unchecked)")
        for msg in check(geom, facet=facet):
            print("   ! " + msg)


def count_shapes(svg_path):
    """How many shapes the artist actually drew."""
    from svgelements import SVG as _SVG, Shape as _Shape
    svg = _SVG.parse(_without_template(svg_path), reify=True, ppi=25.4)
    return sum(1 for el in svg.elements() if isinstance(el, _Shape))


if __name__ == "__main__":
    main()
