"""Figures for the follow-up article (docs/article/medium-followup.md).

One of them compares the shipped geometry against the geometry that preceded the
re-anchored rails. Those "before" meshes are not in the working tree; pull them
out of git first, into any directory, and pass it as the first argument:

    mkdir -p build/before
    git show <commit-before-the-fix>:stl/U3T_bottom.stl     > build/before/U3T_bottom.stl
    git show <commit-before-the-fix>:stl/U3T_rot_bottom.stl > build/before/U3T_rot_bottom.stl
    python tools/followup_figs.py build/before

Emits f2_spread.png (how far the four faces disagree, before and after) and
f2_shadow.png (the face shadow, and which trapezoid edge each rail may start on).
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPoly

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "article", "images")
sys.path.insert(0, ROOT)

import u3t_generator as g            # noqa: E402
import u3t_rot_generator as r        # noqa: E402

BEFORE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "before")

# validated 2-slot categorical palette (dataviz reference instance, light mode:
# node scripts/validate_palette.js "#2a78d6,#eb6834" --mode light --pairs all)
SER_BEFORE, SER_AFTER = "#2a78d6", "#eb6834"
SURFACE, INK, MUTED = "#fcfcfb", "#0b0b0b", "#52514e"
GRID = "#e3e2dd"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5})


# ----------------------------------------------------------------- the chart
def spread_profile(path, z_top):
    """How far apart the four faces put the dovetail outline, height by height."""
    mesh = trimesh.load(path)
    zs = np.arange(g.BAND_Z + 0.4, z_top - g.CLR - 0.05, 0.1)
    prof = g.face_key_profile(mesh, zs)
    out = []
    for i, z in enumerate(zs):
        v = [prof[nm][i] for nm, *_ in g.FACE_SPECS]
        if any(x[0] is None for x in v):
            continue
        out.append((z, max(max(x[0] for x in v) - min(x[0] for x in v),
                           max(x[1] for x in v) - min(x[1] for x in v))))
    return np.array(out)


def chart():
    panels = [("Straight edition", "U3T_bottom.stl", g.KEY_Z1),
              ("Rotation edition", "U3T_rot_bottom.stl", r.KEY_Z1R)]
    f, axs = plt.subplots(1, 2, figsize=(10.6, 4.2), dpi=170, sharey=True,
                          layout="constrained")
    f.patch.set_facecolor(SURFACE)
    for k, (ax, (title, stl, ztop)) in enumerate(zip(axs, panels)):
        ax.set_facecolor(SURFACE)
        before = spread_profile(os.path.join(BEFORE, stl), ztop)
        after = spread_profile(os.path.join(ROOT, "stl", stl), ztop)
        x0, x1 = before[0, 0], before[-1, 0]

        ax.axhline(0.05, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
        for data, color, label in ((before, SER_BEFORE, "before"),
                                   (after, SER_AFTER, "after")):
            ax.plot(data[:, 0], data[:, 1], color=color, lw=2, zorder=3,
                    solid_capstyle="round", label=label)

        # direct labels: the peak for "before", the flat run for "after"
        i = int(np.argmax(before[:, 1]))
        ax.annotate(f"before — peak {before[i, 1]:.2f} mm",
                    (before[i, 0], before[i, 1]), textcoords="offset points",
                    xytext=(9, -3), ha="left", va="top", fontsize=9.5, color=INK,
                    zorder=5)
        ax.annotate(f"after — never above {after[:, 1].max():.2f} mm",
                    (after[-1, 0], after[-1, 1]), textcoords="offset points",
                    xytext=(0, 14), ha="right", va="bottom", fontsize=9.5,
                    color=INK, zorder=5,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.9,
                                    shrinkA=0, shrinkB=3))
        if k == 0:
            ax.text(x0, 0.075, "0.05 mm — what the suite now enforces",
                    fontsize=8.5, color=MUTED, ha="left", va="bottom", zorder=5)

        ax.set_title(title, fontsize=11.5, color=INK, pad=6)
        ax.set_xlabel("height up the face  (mm)", fontsize=10, color=MUTED)
        ax.set_xlim(x0 - 0.15, x1 + 0.15)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=9.5)
    axs[0].set_ylabel("disagreement between\nthe four faces  (mm)", fontsize=10,
                      color=MUTED)
    axs[0].set_ylim(-0.05, 1.12)
    axs[0].legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper left",
                  handlelength=1.6, borderpad=0.2)
    f.savefig(os.path.join(IMG, "f2_spread.png"), facecolor=SURFACE)
    plt.close(f)
    print("f2_spread")


# --------------------------------------------------------------- the diagram
TAN, SEAM, DINK = "#D9B677", "#C0392B", "#33373d"
SHADOW_FILL, OLD = "#f2e3e1", "#C0392B"


def _key_plan(face):
    """Trapezoid, old rail and new rail in (lateral, inboard) sheared-plan mm.

    `inboard` is measured from the inboard edge of the face shadow, so both kinds
    of face can be drawn on one axis: the shadow is always [-flare, 0], and the
    region a rail may legally occupy is always >= 0.
    """
    sh, c = g.SHX, 50.0
    z0, zn, z1 = g.KEY_Z0, g.KEY_NECK_Z, g.KEY_Z1
    w0, w1 = g.KEY_HW0, g.KEY_HW1
    pts = [(c - w0, z0), (c + w0, z0), (c + w0, zn),
           (c + w1, z1), (c - w1, z1), (c - w0, zn)]
    if face == "into":                        # the base edge is the inboard one
        def W(z):
            return sh * (z0 - z)
        anchor_z, anchor_hw = z0, w0
    else:                                     # the flare top is
        def W(z):
            return sh * (z - z1)
        anchor_z, anchor_hw = z1, w1
    trap = [(x - sh * z, W(z)) for (x, z) in pts]
    du = -sh * anchor_z
    new_rail = [(c - anchor_hw + du, 0.0), (c + anchor_hw + du, 0.0),
                (c + anchor_hw + du, 6.0), (c - anchor_hw + du, 6.0)]
    duo = -sh * z0                            # the old rail always started at the base
    old_rail = [(c - w0 + duo, W(z0)), (c + w0 + duo, W(z0)),
                (c + w0 + duo, W(z0) + 8.0), (c - w0 + duo, W(z0) + 8.0)]
    return trap, old_rail, new_rail


def diagram():
    f, axs = plt.subplots(1, 2, figsize=(10.6, 4.4), dpi=170, layout="constrained")
    titles = ("a face d leans into  (front, left)",
              "a face d leans out of  (back, right)")
    notes = ("same edge, same width — the new rail\nis only 2 mm shorter",
             "the old rail ran through the shadow: 0.6 mm of it\n"
             "showed on the face, and the flare tip above it\n"
             "had nothing behind it")
    flare = g.SHX * (g.KEY_Z1 - g.KEY_Z0)
    for k, (ax, face, title, note) in enumerate(zip(axs, ("into", "out"),
                                                    titles, notes)):
        trap, old_rail, new_rail = _key_plan(face)
        cu = float(np.mean([p[0] for p in trap]))

        ax.axhspan(-flare, 0, color=SHADOW_FILL, zorder=1)
        ax.axhline(0, color=SEAM, lw=1.2, zorder=4)
        ax.axhline(-flare, color=SEAM, lw=1.2, zorder=4)
        for poly in (new_rail, trap):
            ax.add_patch(MplPoly(poly, closed=True, facecolor=TAN,
                                 edgecolor="#8a6d2f", lw=1.3, zorder=3))
        ax.add_patch(MplPoly(old_rail, closed=True, facecolor="none", edgecolor=OLD,
                             lw=1.6, ls=(0, (5, 3)), zorder=5))

        ax.text(cu, -flare - 1.3, "the face shadow — this strip is what the face shows",
                fontsize=9.5, color=SEAM, ha="center", va="top", zorder=6)
        ax.text(cu, 9.6, note, fontsize=9.5, color=OLD, ha="center", va="bottom",
                zorder=6)
        if k == 0:
            ax.annotate("", (cu - 17.5, 7.0), (cu - 17.5, 0.3),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.2))
            ax.text(cu - 18.4, 3.6, "into the block", fontsize=9, color=MUTED,
                    rotation=90, ha="right", va="center")
        ax.set_title(title, fontsize=11.5, color=DINK, pad=6)
        ax.set_xlim(cu - 19.5, cu + 14.5)
        ax.set_ylim(-flare - 4.4, 14.4)
        ax.set_aspect("equal")
        ax.set_axis_off()
    f.savefig(os.path.join(IMG, "f2_shadow.png"), facecolor="white")
    plt.close(f)
    print("f2_shadow")


if __name__ == "__main__":
    chart()
    diagram()
