"""Read artwork drawn on a facet template back into the generator.

The templates in docs/templates are millimetre-true SVG. Draw on them in Inkscape
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
    """Flatten one SVG shape into closed rings of millimetre points."""
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
    """All artwork in the file as one shapely geometry, in page millimetres."""
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


def check(geom, facet=None, safe=1.0, min_feature=g.MIN_FEATURE):
    """Report what would go wrong before it reaches the printer."""
    problems = []
    parts = list(getattr(geom, "geoms", [geom]))
    parts = [p for p in parts if not p.is_empty]
    if not parts:
        return ["no artwork found: is everything still live text, or stroked only?"]

    thin = geom.difference(geom.buffer(-min_feature / 2).buffer(min_feature / 2))
    if thin.area > 0.05:
        problems.append(f"{thin.area:.2f} mm2 of stroke is thinner than "
                        f"{min_feature} mm and will not print")
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for path in sys.argv[1:]:
        geom, skipped = artwork(path)
        n = len(list(getattr(geom, "geoms", [geom]))) if not geom.is_empty else 0
        print(f"\n{os.path.basename(path)}: {n} filled regions, "
              f"{geom.area:.1f} mm2 of relief"
              + (f", {skipped} shape(s) with no area skipped" if skipped else ""))
        for msg in check(geom):
            print("   ! " + msg)


if __name__ == "__main__":
    main()
