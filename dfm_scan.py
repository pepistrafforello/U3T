"""Thin-feature scan: flags horizontal-slice features thinner than the process rule.

Mimics the printing service's wall-thickness check: every part is sliced at many
heights; per slice, material that vanishes under an erosion of half the minimum
wall (i.e. any neck, wall or stroke thinner than that minimum) is collected.

It scans at BOTH rules, because the rule is a property of the process and not of
the design:

    FDM  0.50 mm   what the first pair was printed to
    SLS  0.80 mm   what Xometry's partner quoted, and what the SLS print needed

That distinction is not pedantry. The design was verified to 0.55 mm, printed in
SLS, and came back with two keys missing: the dovetail's lateral wings were
0.0-1.1 mm, which clears 0.5 mm comfortably and fails 0.8 mm. Everything in that
band was invisible to this scan while it only knew one number.

A patch here is a question, not a verdict -- a horizontal slice cuts every oblique
surface into slivers. For each one, ask whether solid material lies BEHIND it;
tools/ has the ray-based measurement that answers that properly.
"""
import os

import numpy as np
import trimesh

STL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")
FILES = ["U3T_bottom.stl", "U3T_top.stl", "U3T_rot_bottom.stl", "U3T_rot_top.stl"]
RULES = {"FDM 0.50 mm": 0.249, "SLS 0.80 mm": 0.400}
MIN_PATCH = 0.10      # mm^2
# MIN_PATCH was 0.30: large enough to let a 0.2 mm x 16 mm unsupported
# ledge on two of the keys read as a handful of small patches that were
# waved through as chamfer edges. It is now well below anything that can
# be dismissed by eye.


def slice_polys(mesh, z):
    to2d = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -z], [0, 0, 0, 1]], float)
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None:
        return []
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full


for rule, erode in RULES.items():
    print(chr(10) + f"===== {rule} " + "=" * 50)
    for fn in FILES:
        mesh = trimesh.load(os.path.join(STL, fn))
        mesh.merge_vertices(); mesh.process(validate=True)
        lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
        offenders, total = [], 0.0
        for z in np.arange(lo + 0.25, hi - 0.15, 0.45):
            for poly in slice_polys(mesh, z):
                opened = poly.buffer(-erode).buffer(erode + 0.003)
                thin = poly.difference(opened)
                for g in getattr(thin, "geoms", [thin]):
                    if g.area >= MIN_PATCH:
                        b = g.bounds
                        offenders.append((round(float(z), 2), round(g.area, 2),
                                          tuple(round(v, 1) for v in b)))
                        total += g.area
        print(f"  {fn:22s} {len(offenders):4d} patches >= {MIN_PATCH} mm^2, "
              f"{total:7.1f} mm^2 total")
        for o in sorted(offenders, key=lambda t: -t[1])[:5]:
            print("       z=%5.2f area=%6.2f mm^2 bbox=%s" % o)
print(chr(10) + "scan done")
