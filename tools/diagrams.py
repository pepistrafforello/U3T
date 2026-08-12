"""Clean 2D diagrams for the Medium post (no in-image titles; captions live in the post)."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPoly, FancyArrow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "article", "images")
os.makedirs(IMG, exist_ok=True)
sys.path.insert(0, ROOT)

TAN = "#D9B677"
TAN_DK = "#B08D4F"
BLUE = "#8FB0D8"
SEAM = "#C0392B"
INK = "#33373d"
DIM = "#6b7076"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})


def dimline(ax, p1, p2, text, toff, fs=10):
    ax.annotate("", p1, p2, arrowprops=dict(arrowstyle="<->", color=DIM, lw=1.1))
    ax.text(*toff, text, fontsize=fs, color=INK, ha="center")


# ---- 1. face seam profile ----------------------------------------------------
f, ax = plt.subplots(figsize=(9.6, 3.4), dpi=170)
seam = [(0, 7.5), (44, 7.5), (44, 8.3), (40, 11.5), (60, 11.5), (56, 8.3), (56, 7.5), (100, 7.5)]
bot_poly = [(0, 0), (100, 0), (100, 7.5), (56, 7.5), (56, 8.3), (60, 11.5), (40, 11.5),
            (44, 8.3), (44, 7.5), (0, 7.5)]
top_poly = [(0, 7.5), (44, 7.5), (44, 8.3), (40, 11.5), (60, 11.5), (56, 8.3), (56, 7.5),
            (100, 7.5), (100, 15), (0, 15)]
ax.add_patch(MplPoly(bot_poly, closed=True, facecolor=TAN, edgecolor="none"))
ax.add_patch(MplPoly(top_poly, closed=True, facecolor=BLUE, edgecolor="none"))
ax.plot(*zip(*seam), color=SEAM, lw=2.4, solid_capstyle="round")
ax.add_patch(MplPoly([(0, 0), (100, 0), (100, 15), (0, 15)], closed=True,
                     facecolor="none", edgecolor=INK, lw=1.4))
dimline(ax, (-4, 0), (-4, 7.5), "7.5", (-9.5, 3.2))
dimline(ax, (44, 6.1), (56, 6.1), "12", (50, 4.4))
dimline(ax, (40, 12.6), (60, 12.6), "20", (50, 13.3))
dimline(ax, (104, 7.5), (104, 11.5), "4.0", (109.5, 9.0))
ax.text(50, 2.0, "bottom part", ha="center", color="#5c4a26", fontsize=11)
ax.text(20, 12.6, "top part", ha="center", color="#2d4a6b", fontsize=11)
ax.set_xlim(-16, 116); ax.set_ylim(-1.8, 16.8)
ax.set_aspect("equal"); ax.set_axis_off()
f.tight_layout(pad=0.2)
f.savefig(os.path.join(IMG, "d_face_profile.png"), facecolor="white")
plt.close(f)
print("d_face_profile")

# ---- 2. the shear trick ------------------------------------------------------
f, axs = plt.subplots(1, 2, figsize=(10.6, 3.5), dpi=170)
prof = [(0, 7.5), (14, 7.5), (14, 11), (22, 11), (24, 12.2), (28, 12.2), (28, 11),
        (40, 11), (42, 12.2), (46, 12.2), (46, 11), (58, 11), (60, 12.2), (64, 12.2),
        (64, 11), (80, 11), (86, 7.5), (100, 7.5)]
for ax, sh in ((axs[0], 0.7), (axs[1], 0.0)):
    X = lambda u, z: u + sh * z
    box = [(X(0, 0), 0), (X(100, 0), 0), (X(100, 15), 15), (X(0, 15), 15)]
    ax.add_patch(MplPoly(box, closed=True, facecolor="#eef1f5", edgecolor=INK, lw=1.2))
    ax.plot([X(u, z) for u, z in prof], [z for _, z in prof], color=SEAM, lw=2)
    for u0 in (20, 50, 80):
        ax.add_patch(FancyArrow(X(u0, 16.5), 16.5, sh * 4.5, 4.5, width=0.5,
                                color="#2b6cb0", length_includes_head=True, head_width=1.8))
    ax.set_xlim(-4, 118); ax.set_ylim(-2, 24)
    ax.set_aspect("equal"); ax.set_axis_off()
axs[0].text(56, -5.5, "real space — everything leans along d", ha="center", fontsize=10.5, color=INK)
axs[1].text(50, -5.5, "sheared space — d is vertical, any height field works", ha="center",
            fontsize=10.5, color=INK)
for ax in axs:
    ax.set_ylim(-7.5, 24)
f.tight_layout(pad=0.3)
f.savefig(os.path.join(IMG, "d_shear.png"), facecolor="white")
plt.close(f)
print("d_shear")

# ---- 3. sheared-plan layout --------------------------------------------------
import u3t_generator as g
from shapely.geometry import Polygon as ShPoly

f, ax = plt.subplots(figsize=(7.6, 7.6), dpi=150)
ax.add_patch(MplPoly([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True,
                     facecolor="#faf7f0", edgecolor=INK, lw=1.5))
sh = 15 * 0.7
ax.add_patch(MplPoly([(-sh, -sh), (100 - sh, -sh), (100 - sh, 100 - sh), (-sh, 100 - sh)],
                     closed=True, facecolor="none", edgecolor="#9aa0a6", ls=(0, (5, 4)), lw=1.2))
for hw, col in ((g.PLAT_BASE_HW, "#dde6f2"), (g.PLAT_TOP_HW, "#c6d6ea")):
    ax.add_patch(MplPoly([(50 - hw, 50 - hw), (50 + hw, 50 - hw), (50 + hw, 50 + hw),
                          (50 - hw, 50 + hw)], closed=True, facecolor=col,
                         edgecolor="#7d8aa0", lw=0.9))
for name, q in g.key_footprints():
    ax.add_patch(MplPoly(np.asarray(q.exterior.coords), closed=True,
                         facecolor="#e8b64c", edgecolor="#8a6d2f", lw=1.0))
qr_geom, _, _ = g.qr_geometry()
for geom in [qr_geom, g.fit_into_box(g.text_geometry(g.TITLE), g.TITLE_BOX),
             g.fit_into_box(g.text_geometry(g.SUBTITLE), g.SUB_BOX)]:
    for p in g.polys_of(geom):
        ax.add_patch(MplPoly(np.asarray(p.exterior.coords), closed=True,
                             facecolor="#41454c", edgecolor="none"))
        for h in p.interiors:
            ax.add_patch(MplPoly(np.asarray(h.coords), closed=True,
                                 facecolor="#c6d6ea", edgecolor="none"))
ax.annotate("stock footprint at z = 0", (2, 102.5), fontsize=9.5, color=INK)
ax.annotate("same footprint sheared to z = 15", (-11.5, -14.8), fontsize=9.5, color="#9aa0a6")
ax.annotate("key + anchor rail", (58, -7.2), fontsize=9.5, color="#8a6d2f")
ax.set_xlim(-16, 116); ax.set_ylim(-18, 112)
ax.set_aspect("equal")
ax.set_xlabel("u = x − 0.7 z  (mm)", fontsize=10)
ax.set_ylabel("v = y − 0.7 z  (mm)", fontsize=10)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(labelsize=9, color=DIM)
f.tight_layout(pad=0.4)
f.savefig(os.path.join(IMG, "d_plan.png"), facecolor="white")
plt.close(f)
print("d_plan")

# ---- 4. rotation axis schematic ---------------------------------------------
f, ax = plt.subplots(figsize=(9.2, 4.6), dpi=170)
ax_a, ax_z = 0.0, -103.5
ax.add_patch(MplPoly([(-219.2, 0), (-77.8, 0), (-77.8, 15), (-219.2, 15)], closed=True,
                     facecolor=TAN, edgecolor=INK, lw=1.2, alpha=0.85))
ax.plot([ax_a], [ax_z], marker="o", color="#2b6cb0", ms=7)
ax.axvline(0, color="#9aa0a6", ls=(0, (5, 4)), lw=1.1)
for rho in (135, 165, 200, 235):
    th = np.linspace(np.pi / 2, np.pi, 160)
    xs = ax_a + rho * np.cos(th); zs = ax_z + rho * np.sin(th)
    keep = (zs > -14) & (zs < 44) & (xs > -252)
    ax.plot(xs[keep], zs[keep], color=SEAM, lw=1.5, alpha=0.9)
ax.add_patch(FancyArrow(-97, 24, 20, 11.5, width=1.7, color="#2b6cb0",
                        length_includes_head=True, head_width=5.5))
ax.text(-238, 38, "orbits — every one rises\nmonotonically through the block",
        fontsize=9.5, color=SEAM)
ax.text(-72, 42, "separating rotation ≈ 12°", fontsize=9.5, color="#2b6cb0")
ax.text(5, 20, "apex plane x − y = 210\n(misses the block)", fontsize=9.5, color="#7d8288")
ax.text(8, -101, "axis A — horizontal, along the plan\ndiagonal, ~147 mm out and 104 mm down",
        fontsize=9.5, color="#2b6cb0")
ax.text(-148.5, 6, "block (projected)", fontsize=10.5, ha="center", color="#5c4a26")
ax.set_xlim(-262, 118); ax.set_ylim(-122, 52)
ax.set_aspect("equal"); ax.set_axis_off()
f.tight_layout(pad=0.2)
f.savefig(os.path.join(IMG, "d_axis.png"), facecolor="white")
plt.close(f)
print("d_axis")

# ---- 5. cross-sections from the shipped STLs --------------------------------
def section_2d(mesh, x0=50.0):
    to2d = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, -x0], [0, 0, 0, 1]], float)
    s = mesh.section(plane_origin=[x0, 0, 0], plane_normal=[1, 0, 0])
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full


for stem, files in (("d_section_straight", ("U3T_bottom.stl", "U3T_top.stl")),
                    ("d_section_rot", ("U3T_rot_bottom.stl", "U3T_rot_top.stl"))):
    bot_m = trimesh.load(os.path.join(ROOT, "stl", files[0]))
    top_m = trimesh.load(os.path.join(ROOT, "stl", files[1]))
    f, ax = plt.subplots(figsize=(10.6, 2.6), dpi=170)
    for polys, col in ((section_2d(bot_m), TAN), (section_2d(top_m), BLUE)):
        for p in polys:
            ax.add_patch(MplPoly(np.asarray(p.exterior.coords), closed=True,
                                 facecolor=col, edgecolor=INK, lw=0.5))
            for h in p.interiors:
                ax.add_patch(MplPoly(np.asarray(h.coords), closed=True,
                                     facecolor="white", edgecolor=INK, lw=0.5))
    ax.set_xlim(-2.5, 102.5); ax.set_ylim(-1.2, 16.2)
    ax.set_aspect("equal")
    ax.set_xlabel("y (mm)", fontsize=10); ax.set_ylabel("z (mm)", fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9, color=DIM)
    f.tight_layout(pad=0.3)
    f.savefig(os.path.join(IMG, stem + ".png"), facecolor="white")
    plt.close(f)
    print(stem)

print("2D figures done")
