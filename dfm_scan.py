"""Thin-feature scan: flags any horizontal-slice feature thinner than 0.5 mm.

Mimics the printing service's wall-thickness check: every part is sliced at many
heights; per slice, material that vanishes under a 0.25 mm erosion (i.e. any
neck, wall or stroke thinner than ~0.5 mm) is collected and reported.
"""
import os

import numpy as np
import trimesh

STL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")
FILES = ["U3T_bottom.stl", "U3T_top.stl", "U3T_rot_bottom.stl", "U3T_rot_top.stl"]
ERODE, DILATE, MIN_PATCH = 0.249, 0.252, 0.30  # mm, mm, mm^2


def slice_polys(mesh, z):
    to2d = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -z], [0, 0, 0, 1]], float)
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None:
        return []
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full


for fn in FILES:
    mesh = trimesh.load(os.path.join(STL, fn))
    mesh.merge_vertices(); mesh.process(validate=True)
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
    offenders = []
    for z in np.arange(lo + 0.25, hi - 0.15, 0.45):
        for poly in slice_polys(mesh, z):
            opened = poly.buffer(-ERODE).buffer(DILATE)
            thin = poly.difference(opened)
            for g in getattr(thin, "geoms", [thin]):
                if g.area >= MIN_PATCH:
                    b = g.bounds
                    offenders.append((round(float(z), 2), round(g.area, 2),
                                      tuple(round(v, 1) for v in b)))
    print(f"{fn}: {len(offenders)} thin patches >= {MIN_PATCH} mm^2")
    for o in sorted(offenders, key=lambda t: -t[1])[:8]:
        print("   z=%.2f area=%.2f mm^2 bbox=%s" % o)
print("scan done")
