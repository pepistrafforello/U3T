"""Figures for the rotation-edition chapter."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPoly, Arc, FancyArrow
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(ROOT, "docs", "figures")
STL = os.path.join(ROOT, "stl")

SQ2 = np.sqrt(2.0)
E = np.array([1.0, 1.0, 0.0]) / SQ2
C = np.array([105.0, -105.0, -103.5])

TAN = np.array([0.82, 0.66, 0.43])
BLUE = np.array([0.38, 0.55, 0.75])

bottom = trimesh.load(os.path.join(STL, "U3T_rot_bottom.stl"))
top = trimesh.load(os.path.join(STL, "U3T_rot_top.stl"))
top_print = trimesh.load(os.path.join(STL, "U3T_rot_top_print.stl"))


def view_dir(elev, azim):
    e, a = np.radians(elev), np.radians(azim)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def render(ax, items, elev=28, azim=-60):
    light = np.array([-0.3, 0.4, 0.85]); light /= np.linalg.norm(light)
    v = view_dir(elev, azim)
    tris, cols, depth = [], [], []
    for mesh, rgb in items:
        t = mesh.vertices[mesh.faces]
        lam = 0.35 + 0.65 * np.clip(mesh.face_normals @ light, 0, None)
        tris.append(t); cols.append(np.clip(lam[:, None] * rgb[None, :], 0, 1))
        depth.append(t.mean(axis=1) @ v)
    t = np.concatenate(tris); c = np.concatenate(cols)
    o = np.argsort(np.concatenate(depth))
    ax.add_collection3d(Poly3DCollection(t[o], facecolors=c[o], edgecolors="none"))
    allv = np.concatenate([m.vertices for m, _ in items])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    ctr, r = (lo + hi) / 2, (hi - lo).max() * 0.55
    ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r)
    ax.set_zlim(ctr[2] - r * 0.6, ctr[2] + r * 0.6)
    ax.set_box_aspect((1, 1, 0.6)); ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim); ax.set_axis_off()


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


def rotated(mesh, deg):
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), E, point=C))
    return m


# ---- axis / orbit schematic (plane perpendicular to the axis) ---------------
f, ax = plt.subplots(figsize=(9.5, 5.2))
# alpha = signed distance toward the apex plane, z vertical; axis at (0, -103.5)... plot axis at origin-below
ax_a, ax_z = 0.0, -103.5
blk = [(-219.2, 0), (-77.8, 0), (-77.8, 15), (-219.2, 15)]
ax.add_patch(MplPoly(blk, closed=True, facecolor="#f2ead8", edgecolor="k", lw=1.2))
ax.plot([ax_a], [ax_z], marker="o", color="#2b6cb0", ms=6)
ax.annotate("axis A (into the page,\nalong the plan diagonal)", (ax_a, ax_z),
            (30, -95), fontsize=9, color="#2b6cb0")
ax.axvline(0, color="0.6", ls="--", lw=1)
ax.annotate("apex plane x − y = 210\n(misses the block)", (0, 28), (8, 24), fontsize=9, color="0.4")
for rho in (135, 165, 200, 235):
    th = np.linspace(np.pi / 2, np.pi, 120)
    xs = ax_a + rho * np.cos(th); zs = ax_z + rho * np.sin(th)
    keep = (zs > -12) & (zs < 42) & (xs > -250)
    ax.plot(xs[keep], zs[keep], color="#c44536", lw=1.4, alpha=0.85)
ax.annotate("orbits: circles about A — every one\nrises monotonically through the block",
            (-252, 36), fontsize=9, color="#c44536")
ax.add_patch(FancyArrow(-100, 22, 22, 12, width=1.6, color="#2b6cb0"))
ax.text(-96, 44, "separating rotation (~12°)", fontsize=9, color="#2b6cb0")
ax.text(-148, 6, "block (projected)", fontsize=10, ha="center")
ax.set_xlim(-260, 105); ax.set_ylim(-125, 55)
ax.set_aspect("equal"); ax.set_axis_off()
ax.set_title("Rotation edition — axis placement in the plane perpendicular to A", fontsize=11)
f.tight_layout()
f.savefig(os.path.join(FIG, "rot_axis_schematic.png"), dpi=150)
plt.close(f)
print("wrote rot_axis_schematic.png")

# ---- 3D renders -------------------------------------------------------------
fig3d("rot_bottom_iso.png", [(bottom, TAN)],
      title="Rotation edition — bottom part (keys and walls lean along the orbits)")
fig3d("rot_top_underside.png", [(top_print, BLUE)],
      title="Rotation edition — top part flipped (print orientation)")
fig3d("rot_exploded.png", [(bottom, TAN), (rotated(top, 14), BLUE)],
      title="Opened by rotating the top 14° about the external diagonal axis")

f = plt.figure(figsize=(13, 4.6))
for i, d in enumerate((0, 6, 14)):
    ax = f.add_subplot(1, 3, i + 1, projection="3d")
    render(ax, [(bottom, TAN), (rotated(top, d), BLUE)], elev=22, azim=-55)
    ax.set_title(f"rotation = {d}°", fontsize=10)
f.suptitle("One single movement: rotation about A", fontsize=12)
f.tight_layout(pad=0.2)
f.savefig(os.path.join(FIG, "rot_separation_seq.png"), dpi=130)
plt.close(f)
print("wrote rot_separation_seq.png")

# four orthographic side views
def side(ax, elev, azim):
    light = np.array([-0.25, 0.35, 0.9]); light /= np.linalg.norm(light)
    v = view_dir(elev, azim)
    tris, cols, depth = [], [], []
    for mesh, rgb in ((bottom, TAN), (top, BLUE)):
        t = mesh.vertices[mesh.faces]
        lam = 0.45 + 0.55 * np.clip(mesh.face_normals @ light, 0, None)
        tris.append(t); cols.append(np.clip(lam[:, None] * rgb[None, :], 0, 1))
        depth.append(t.mean(axis=1) @ v)
    t = np.concatenate(tris); c = np.concatenate(cols)
    o = np.argsort(np.concatenate(depth))
    ax.add_collection3d(Poly3DCollection(t[o], facecolors=c[o], edgecolors="none"))
    ax.set_xlim(-2, 102); ax.set_ylim(-2, 102); ax.set_zlim(-3, 18)
    ax.set_box_aspect((104, 104, 21), zoom=3.3)
    ax.set_proj_type("ortho"); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()

names = [("front (−y)", 0, -90), ("right (+x)", 0, 0), ("back (+y)", 0, 90), ("left (−x)", 0, 180)]
f = plt.figure(figsize=(10.5, 8.2))
for i, (nm, el, az) in enumerate(names):
    ax = f.add_subplot(4, 1, i + 1, projection="3d")
    side(ax, el, az)
    ax.set_title(nm, fontsize=10, pad=-13)
f.suptitle("Rotation edition — still the same from every side", fontsize=12)
f.subplots_adjust(left=0, right=1, top=0.9, bottom=0, hspace=0)
f.savefig(os.path.join(FIG, "rot_four_sides.png"), dpi=150)
plt.close(f)
print("wrote rot_four_sides.png")

fig3d("rot_interface_top.png", [(bottom, TAN)], elev=88, azim=-90,
      title="Rotation edition — hidden interface (bottom part from above)")

# ---- cross-section ----------------------------------------------------------
def section_2d(mesh, x0=50.0):
    to2d = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, -x0], [0, 0, 0, 1]], float)
    s = mesh.section(plane_origin=[x0, 0, 0], plane_normal=[1, 0, 0])
    p2, _ = s.to_2D(to_2D=to2d)
    return p2.polygons_full

f, ax = plt.subplots(figsize=(11, 3.6))
for poly, col in ((section_2d(bottom), TAN), (section_2d(top), BLUE)):
    for p in poly:
        ax.add_patch(MplPoly(np.asarray(p.exterior.coords), closed=True,
                             facecolor=col, edgecolor="k", lw=0.4))
        for hole in p.interiors:
            ax.add_patch(MplPoly(np.asarray(hole.coords), closed=True,
                                 facecolor="white", edgecolor="k", lw=0.4))
ax.set_xlim(-3, 103); ax.set_ylim(-1.5, 16.5)
ax.set_aspect("equal"); ax.set_xlabel("y (mm)"); ax.set_ylabel("z (mm)")
ax.set_title("Rotation edition — cross-section at x = 50 mm (walls now curve along orbits)")
f.tight_layout()
f.savefig(os.path.join(FIG, "rot_section_x50.png"), dpi=150)
plt.close(f)
print("wrote rot_section_x50.png")

print("all rotation figures done")
