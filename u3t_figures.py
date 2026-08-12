"""Render figures for the completed U3T document (from generated STLs + parameters)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPoly, FancyArrow
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(ROOT, "docs", "figures")
STL = os.path.join(ROOT, "stl")
os.makedirs(FIG, exist_ok=True)

SHX = SHY = 0.7
D_HAT = np.array([0.7, 0.7, 1.0]) / np.linalg.norm([0.7, 0.7, 1.0])

TAN = np.array([0.82, 0.66, 0.43])      # bottom part (light wood)
BLUE = np.array([0.38, 0.55, 0.75])     # top part

bottom = trimesh.load(os.path.join(STL, "U3T_bottom.stl"))
top = trimesh.load(os.path.join(STL, "U3T_top.stl"))
top_print = trimesh.load(os.path.join(STL, "U3T_top_print.stl"))


def view_dir(elev, azim):
    e, a = np.radians(elev), np.radians(azim)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def render(ax, items, elev=28, azim=-60, ortho=True):
    """items: list of (mesh, rgb). Painter-sorted shaded Poly3DCollection."""
    tris, cols, depth = [], [], []
    light = np.array([-0.3, 0.4, 0.85])
    light = light / np.linalg.norm(light)
    v = view_dir(elev, azim)
    for mesh, rgb in items:
        t = mesh.vertices[mesh.faces]
        n = mesh.face_normals
        lam = 0.35 + 0.65 * np.clip(n @ light, 0, None)
        c = np.clip(lam[:, None] * rgb[None, :], 0, 1)
        tris.append(t)
        cols.append(c)
        depth.append(t.mean(axis=1) @ v)
    t = np.concatenate(tris)
    c = np.concatenate(cols)
    order = np.argsort(np.concatenate(depth))
    pc = Poly3DCollection(t[order], facecolors=c[order], edgecolors="none")
    ax.add_collection3d(pc)
    allv = np.concatenate([m.vertices for m, _ in items])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    ctr, rng = (lo + hi) / 2, (hi - lo)
    r = rng.max() * 0.55
    ax.set_xlim(ctr[0] - r, ctr[0] + r)
    ax.set_ylim(ctr[1] - r, ctr[1] + r)
    ax.set_zlim(ctr[2] - r * 0.6, ctr[2] + r * 0.6)
    ax.set_box_aspect((1, 1, 0.6))
    if ortho:
        ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def fig3d(name, items, elev=28, azim=-60, title=None, figsize=(9, 6.5)):
    f = plt.figure(figsize=figsize)
    ax = f.add_subplot(111, projection="3d")
    render(ax, items, elev, azim)
    if title:
        ax.set_title(title, fontsize=11)
    f.tight_layout(pad=0.1)
    f.savefig(os.path.join(FIG, name), dpi=140)
    plt.close(f)
    print("wrote", name)


# ---- 3D renders -------------------------------------------------------------
fig3d("gen_bottom_iso.png", [(bottom, TAN)],
      title="Bottom part — band, four keys, plateau with QR + title (print orientation)")
fig3d("gen_top_underside.png", [(top_print, BLUE)],
      title="Top part flipped — matching cavities (print orientation)")

t2 = top.copy(); t2.apply_translation(D_HAT * 42)
fig3d("gen_exploded.png", [(bottom, TAN), (t2, BLUE)],
      title="Exploded along the extrusion direction d = (0.7, 0.7, 1)")

fig3d("gen_assembled.png", [(bottom, TAN), (top, BLUE)],
      title="Assembled U3T — 100 × 100 × 15 mm")

# separation sequence
f = plt.figure(figsize=(13, 4.6))
for i, t in enumerate((0, 12, 30)):
    ax = f.add_subplot(1, 3, i + 1, projection="3d")
    tt = top.copy(); tt.apply_translation(D_HAT * t)
    render(ax, [(bottom, TAN), (tt, BLUE)], elev=22, azim=-55)
    ax.set_title(f"slide = {t} mm", fontsize=10)
f.suptitle("One single movement: translation along d", fontsize=12)
f.tight_layout(pad=0.2)
f.savefig(os.path.join(FIG, "gen_separation_seq.png"), dpi=130)
plt.close(f)
print("wrote gen_separation_seq.png")

# four orthographic side views
names = [("front", 0, -90), ("right", 0, 0), ("back", 0, 90), ("left", 0, 180)]
f = plt.figure(figsize=(12, 7.2))
for i, (nm, el, az) in enumerate(names):
    ax = f.add_subplot(2, 2, i + 1, projection="3d")
    render(ax, [(bottom, TAN), (top, BLUE)], elev=el, azim=az)
    ax.set_title(nm, fontsize=11)
f.suptitle("The assembly looks the same from every side", fontsize=13)
f.tight_layout(pad=0.2)
f.savefig(os.path.join(FIG, "gen_four_sides.png"), dpi=130)
plt.close(f)
print("wrote gen_four_sides.png")

# hidden interface, top-down
fig3d("gen_interface_top.png", [(bottom, TAN)], elev=88, azim=-90,
      title="The hidden interface (bottom part, viewed from above)")

# ---- cross-section ----------------------------------------------------------
def section_2d(mesh, x0=50.0):
    to2d = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, -x0], [0, 0, 0, 1]], float)
    s = mesh.section(plane_origin=[x0, 0, 0], plane_normal=[1, 0, 0])
    if s is None:
        return []
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full

f, ax = plt.subplots(figsize=(11, 3.6))
for poly, col in ((section_2d(bottom), TAN), (section_2d(top), BLUE)):
    for p in poly:
        xy = np.asarray(p.exterior.coords)
        ax.add_patch(MplPoly(xy, closed=True, facecolor=col, edgecolor="k", lw=0.4))
        for hole in p.interiors:
            ax.add_patch(MplPoly(np.asarray(hole.coords), closed=True,
                                 facecolor="white", edgecolor="k", lw=0.4))
ax.set_xlim(-3, 103); ax.set_ylim(-1.5, 16.5)
ax.set_aspect("equal"); ax.set_xlabel("y (mm)"); ax.set_ylabel("z (mm)")
ax.set_title("Cross-section at x = 50 mm — band, keys, plateau ramps, QR relief, 0.3 mm gap")
f.tight_layout()
f.savefig(os.path.join(FIG, "gen_section_x50.png"), dpi=150)
plt.close(f)
print("wrote gen_section_x50.png")

# ---- 2D schematic: face seam profile with dimensions ------------------------
f, ax = plt.subplots(figsize=(9, 4.2))
ax.add_patch(MplPoly([(0, 0), (100, 0), (100, 15), (0, 15)], closed=True,
                     facecolor="#f2ead8", edgecolor="k", lw=1.2))
seam = [(0, 7.5), (44, 7.5), (44, 8.3), (40, 11.5), (60, 11.5), (56, 8.3), (56, 7.5), (100, 7.5)]
ax.plot(*zip(*seam), color="crimson", lw=2.2)
key = [(44, 7.5), (56, 7.5), (56, 8.3), (60, 11.5), (40, 11.5), (44, 8.3)]
ax.add_patch(MplPoly(key, closed=True, facecolor="#e8b64c", edgecolor="crimson", lw=1.5))
for (x1, y1, x2, y2, txt, off) in [
    (0, 7.5, 0, 0, "7.5", (-7, 3.6)),
    (44, 7.5, 56, 7.5, "12", (48.8, 6.1)),
    (40, 11.5, 60, 11.5, "20", (48.8, 12.2)),
    (100, 7.5, 100, 11.5, "4.0", (101.5, 9.1)),
]:
    ax.annotate("", (x1, y1), (x2, y2), arrowprops=dict(arrowstyle="<->", color="0.25", lw=1))
    ax.text(*off, txt, fontsize=10, color="0.15")
ax.plot([100, 100], [7.5, 11.5], color="0.25", lw=1)
ax.text(50, 2.8, "bottom part", ha="center", fontsize=11)
ax.text(50, 13.6, "top part", ha="center", fontsize=11)
ax.text(50, 9.0, "key", ha="center", fontsize=9)
ax.set_xlim(-14, 112); ax.set_ylim(-2.5, 17.5)
ax.set_aspect("equal"); ax.set_axis_off()
ax.set_title("Face seam profile — identical on all four sides (mm)")
f.tight_layout()
f.savefig(os.path.join(FIG, "gen_face_profile.png"), dpi=150)
plt.close(f)
print("wrote gen_face_profile.png")

# ---- 2D schematic: shear concept --------------------------------------------
f, axs = plt.subplots(1, 2, figsize=(11, 4.2))
for ax, sheared in ((axs[0], False), (axs[1], True)):
    sh = 0.0 if sheared else 0.55   # draw the d tilt in real space only
    def X(u, z):  # map sheared u,z -> drawing coords
        return u + sh * z
    # stock outline
    box = [(X(0, 0), 0), (X(100, 0), 0), (X(100, 15), 15), (X(0, 15), 15)]
    ax.add_patch(MplPoly(box, closed=True, facecolor="#eef1f5", edgecolor="k", lw=1.1))
    # interface: band + key + plateau + QR teeth (schematic)
    prof = [(0, 7.5), (14, 7.5), (14, 11), (20, 11), (22, 12.2), (26, 12.2), (26, 11),
            (40, 11), (42, 12.2), (46, 12.2), (46, 11), (60, 11), (62, 12.2), (66, 12.2),
            (66, 11), (80, 11), (86, 7.5), (100, 7.5)]
    ax.plot([X(u, z) for u, z in prof], [z for _, z in prof], color="crimson", lw=2)
    # d arrows
    for u0 in (18, 50, 82):
        if sheared:
            ax.add_patch(FancyArrow(u0, 16.5, 0, 5, width=0.35, color="#2b6cb0"))
        else:
            ax.add_patch(FancyArrow(X(u0, 16.5), 16.5, 0.55 * 5, 5, width=0.35, color="#2b6cb0"))
    ax.set_title("real space — parts slide along oblique d" if not sheared
                 else "sheared space — d becomes vertical;\nany height field works", fontsize=10)
    ax.set_xlim(-5, 118); ax.set_ylim(-2, 25)
    ax.set_aspect("equal"); ax.set_axis_off()
f.suptitle("The shear trick:  (u, v) = (x − 0.7·z,  y − 0.7·z)", fontsize=12)
f.tight_layout()
f.savefig(os.path.join(FIG, "gen_shear_concept.png"), dpi=150)
plt.close(f)
print("wrote gen_shear_concept.png")

# ---- 2D schematic: sheared-plan layout --------------------------------------
import sys
sys.path.insert(0, ROOT)
import u3t_generator as g

f, ax = plt.subplots(figsize=(8.5, 8.5))
ax.add_patch(MplPoly([(-6, -6), (106, -6), (106, 106), (-6, 106)], closed=True,
                     facecolor="#f7f4ec", edgecolor="none"))
ax.add_patch(MplPoly([(0, 0), (100, 0), (100, 15 * 0), (0, 0)], closed=True))  # no-op
# stock footprint at z=0 and its sheared position at z=15
ax.add_patch(MplPoly([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True,
                     facecolor="none", edgecolor="k", lw=1.4))
sh = 15 * 0.7
ax.add_patch(MplPoly([(-sh, -sh), (100 - sh, -sh), (100 - sh, 100 - sh), (-sh, 100 - sh)],
                     closed=True, facecolor="none", edgecolor="0.55", ls="--", lw=1.1))
# plateau
for hw, col in ((g.PLAT_BASE_HW, "#cdd8e8"), (g.PLAT_TOP_HW, "#b3c6de")):
    ax.add_patch(MplPoly([(50 - hw, 50 - hw), (50 + hw, 50 - hw),
                          (50 + hw, 50 + hw), (50 - hw, 50 + hw)], closed=True,
                         facecolor=col, edgecolor="0.3", lw=0.8))
# keys
for name, q in g.key_footprints():
    xy = np.asarray(q.exterior.coords)
    ax.add_patch(MplPoly(xy, closed=True, facecolor="#e8b64c", edgecolor="0.2", lw=0.9))
# QR + text footprints
qr_geom, _, _ = g.qr_geometry()
for p in g.polys_of(qr_geom):
    ax.add_patch(MplPoly(np.asarray(p.exterior.coords), closed=True,
                         facecolor="0.25", edgecolor="none"))
    for h in p.interiors:
        ax.add_patch(MplPoly(np.asarray(h.coords), closed=True,
                             facecolor="#b3c6de", edgecolor="none"))
for txt, box in ((g.TITLE, g.TITLE_BOX), (g.SUBTITLE, g.SUB_BOX)):
    geom = g.fit_into_box(g.text_geometry(txt), box)
    for p in g.polys_of(geom):
        ax.add_patch(MplPoly(np.asarray(p.exterior.coords), closed=True,
                             facecolor="0.25", edgecolor="none"))
        for h in p.interiors:
            ax.add_patch(MplPoly(np.asarray(h.coords), closed=True,
                                 facecolor="#b3c6de", edgecolor="none"))
ax.annotate("stock footprint at z = 0", (2, 101.5), fontsize=9)
ax.annotate("footprint sheared to z = 15", (-5, -10.5), fontsize=9, color="0.45")
ax.annotate("key prisms + anchor rails (z 7.5 → 11.5)", (55, -6.2), fontsize=9)
ax.annotate("45° ramps", (17, 15.5), fontsize=9, color="0.25")
ax.set_xlim(-15, 115); ax.set_ylim(-15, 115)
ax.set_aspect("equal")
ax.set_xlabel("u = x − 0.7 z (mm)"); ax.set_ylabel("v = y − 0.7 z (mm)")
ax.set_title("Sheared-plan layout of the parting surface")
f.tight_layout()
f.savefig(os.path.join(FIG, "gen_plan_layout.png"), dpi=140)
plt.close(f)
print("wrote gen_plan_layout.png")

print("all figures done")
