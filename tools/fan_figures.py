"""Figures for the rotation edition's sawtooth interface and the relief on it.

Three pictures, all read off the built meshes and the drawn templates rather than
recomputed, so they cannot drift away from what the generator actually makes:

  f3_sections.png  sections across both interfaces -- one tilted band, five facets
  f3_canvas.png    the five strips laid out flat, with whatever is drawn on them
  f3_lockup.png    the Blender shot straight down the motion, flattened onto white

The first two need nothing but the repository. The third needs a render to exist
in build/readme_raw/ (see the README); it is skipped if there is none.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPoly
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import svg_content  # noqa: E402

IMG = os.path.join(ROOT, "docs", "article", "images")
TPL = os.path.join(ROOT, "docs", "templates")
os.makedirs(IMG, exist_ok=True)

TAN, BLUE, INK, SEAM, RAISED = "#D9B677", "#8FB0D8", "#33373d", "#C0392B", "#8a6d2f"


# --------------------------------------------------- sections across the seam
def section(mesh, normal, origin):
    """Cut a mesh with a vertical plane, returned in (in-plane, z) coordinates."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    e1 = np.cross([0.0, 0.0, 1.0], n)
    e1 /= np.linalg.norm(e1)
    to2d = np.eye(4)
    to2d[:3, :3] = np.vstack([e1, [0.0, 0.0, 1.0], n])
    to2d[:3, 3] = -to2d[:3, :3] @ np.asarray(origin, float)
    s = mesh.section(plane_origin=origin, plane_normal=n)
    if s is None:
        return []
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full


def sections_figure():
    cases = [("straight edition — section across the band, on the x = y diagonal",
              "U3T_bottom.stl", "U3T_top.stl", (1.0, -1.0, 0.0)),
             ("rotation edition — section across the fan, on the x + y = 100 diagonal",
              "U3T_rot_bottom.stl", "U3T_rot_top.stl", (1.0, 1.0, 0.0))]
    f, axs = plt.subplots(2, 1, figsize=(11, 4.6), dpi=165, layout="constrained")
    for ax, (title, fb, ft, nrm) in zip(axs, cases):
        for fn, col in ((fb, TAN), (ft, BLUE)):
            m = trimesh.load(os.path.join(ROOT, "stl", fn))
            for poly in section(m, nrm, [50.0, 50.0, 0.0]):
                ax.add_patch(MplPoly(np.asarray(poly.exterior.coords), closed=True,
                                     facecolor=col, edgecolor=INK, lw=0.5))
                for hole in poly.interiors:
                    ax.add_patch(MplPoly(np.asarray(hole.coords), closed=True,
                                         facecolor="white", edgecolor=INK, lw=0.5))
        ax.set_xlim(-73, 73)
        ax.set_ylim(-1.0, 16.0)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=10.5, color=INK, pad=4)
        ax.set_ylabel("z (mm)", fontsize=9.5)
        for sd in ("top", "right"):
            ax.spines[sd].set_visible(False)
        ax.tick_params(labelsize=8.5)
    out = os.path.join(IMG, "f3_sections.png")
    f.savefig(out, facecolor="white")
    plt.close(f)
    print("f3_sections.png")


# ------------------------------------------- the strips, flat, with the artwork
def canvas_figure():
    meta = {e["facet"]: e for e in
            json.load(open(os.path.join(TPL, "templates.json")))}
    comb = meta["combined"]
    f, ax = plt.subplots(figsize=(8.6, 6.6), dpi=175, layout="constrained")
    for ring in comb["page_outlines"]:
        ax.add_patch(MplPoly(np.asarray(ring), closed=True, facecolor=TAN,
                             edgecolor=SEAM, lw=1.0))
    drawn = 0
    for fid in sorted(k for k in meta if k != "combined"):
        m = meta[fid]
        geom, _ = svg_content.artwork(os.path.join(TPL, m["file"]))
        if geom.is_empty:
            continue
        drawn += 1
        dx, dy = m["w0"] - comb["w0"], comb["r1"] - m["r1"]
        for g in getattr(geom, "geoms", [geom]):
            ax.add_patch(MplPoly(np.asarray(g.exterior.coords) + (dx, dy),
                                 closed=True, facecolor=RAISED, edgecolor=INK,
                                 lw=0.4))
            for hole in g.interiors:
                ax.add_patch(MplPoly(np.asarray(hole.coords) + (dx, dy),
                                     closed=True, facecolor=TAN, edgecolor=INK,
                                     lw=0.4))
    bb = unary_union([Polygon(r) for r in comb["page_outlines"]]).bounds
    ax.set_xlim(bb[0] - 3, bb[2] + 3)
    ax.set_ylim(bb[3] + 3, bb[1] - 3)          # y runs down, like the templates
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(f"the five facets laid flat — {comb['area_mm2']:.0f} mm² of canvas, "
                 f"raised artwork in brown, strip seams in red",
                 fontsize=11, color=INK)
    out = os.path.join(IMG, "f3_canvas.png")
    f.savefig(out, facecolor="white")
    plt.close(f)
    print(f"f3_canvas.png  ({drawn} facets carry artwork)")


# ------------------------------------------------------- the render, if present
def lockup_figure(name="lk_wide", pad=26):
    raw = os.path.join(ROOT, "build", "readme_raw", name + ".png")
    if not os.path.exists(raw):
        print(f"f3_lockup.png  skipped — no {raw}")
        return
    from PIL import Image
    im = Image.open(raw).convert("RGBA")
    box = im.getchannel("A").getbbox()
    if box:
        im = im.crop(box)
    out = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad), "white")
    out.paste(im, (pad, pad), im)
    out.save(os.path.join(IMG, "f3_lockup.png"))
    print("f3_lockup.png", out.size)


def shots(out=None):
    """Compose the Blender shot: straight down the motion, framed on the artwork.

    Written as a separate step because rendering it needs Blender. See the README.
    """
    sys.path.insert(0, ROOT)
    import u3t_rot_generator as r

    meta = {e["facet"]: e for e in
            json.load(open(os.path.join(TPL, "templates.json")))}
    lo_w, hi_w, lo_r, hi_r = 1e9, -1e9, 1e9, -1e9
    for fid in sorted(k for k in meta if k != "combined"):
        g, _ = svg_content.artwork(os.path.join(TPL, meta[fid]["file"]))
        if g.is_empty:
            continue
        m = meta[fid]
        x0, y0, x1, y1 = g.bounds
        lo_w, hi_w = min(lo_w, x0 + m["w0"]), max(hi_w, x1 + m["w0"])
        lo_r, hi_r = min(lo_r, m["r1"] - y1), max(hi_r, m["r1"] - y0)
    if lo_w > hi_w:
        print("shots: nothing is drawn on the templates")
        return

    # frame on the facet the artwork straddles the middle of
    mid_rho = (lo_r + hi_r) / 2
    mid = min((k for k in meta if k != "combined"),
              key=lambda k: abs((meta[k]["rho_in"] + meta[k]["rho_out"]) / 2 - mid_rho))
    phi, radial = r.facet_frame(mid)
    n = r.axis_normal(phi)
    center = r.C + (lo_w + hi_w) / 2 * r.E + (lo_r + hi_r) / 2 * radial

    res, lens = [1600, 1180], 70.0
    need = max((hi_w - lo_w) * 1.12, (hi_r - lo_r) * 1.12 * res[0] / res[1])
    dist = need / 2 / np.tan(np.arctan(18.0 / lens))

    # light that grazes the facet, so the relief casts along itself
    graze = -0.30 * n + 0.80 * r.E + 0.52 * radial
    graze /= np.linalg.norm(graze)

    work = os.path.join(ROOT, "build", "review")
    os.makedirs(work, exist_ok=True)
    stl = os.path.join(work, "lock_bot.stl")
    trimesh.load(os.path.join(ROOT, "stl", "U3T_rot_bottom.stl")).export(stl)

    shot = dict(name="lk_wide", stls=[[stl, "tan"]],
                cam=dict(loc=(center + n * dist).tolist(), target=center.tolist(),
                         type="PERSP", lens=lens),
                res=res, sun=(-graze).tolist())
    out = out or os.path.join(ROOT, "build", "shots_readme.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump([shot], fh, indent=1)
    print(f"shots -> {out}  (framed {need:.0f} mm wide, camera {dist:.0f} mm back)")


if __name__ == "__main__":
    if "--shots" in sys.argv:
        shots()
    else:
        sections_figure()
        canvas_figure()
        lockup_figure()
