"""Why the dovetail lost its flare: the wing, measured before and after.

The flare's lateral wings are the only material at that width, and on two of the
four faces nothing backs them but the FACE SHADOW -- the strip of the design plan
the side face sweeps as z runs over the key. A wing at lateral offset w first
exists at the height the flare reaches w, and from there its depth grows at the
lean, about a third of a millimeter per millimeter of height. It therefore needs
2.4 mm of key above it to reach the 0.8 mm an SLS machine can build, and the key
is 5.5 mm tall in total. No flare clears that on those two faces, at any numbers.

Run after a build; it reads the STLs rather than recomputing anything.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "article", "images")
os.makedirs(IMG, exist_ok=True)
TAN, INK, RED, GREEN = "#D9B677", "#33373d", "#C0392B", "#2E7D5B"
LIMIT = 0.8

FACES = {"front": (np.array([0, 1.0, 0]), lambda u, z: [u, 0.0, z]),
         "back":  (np.array([0, -1.0, 0]), lambda u, z: [u, 100.0, z]),
         "left":  (np.array([1.0, 0, 0]), lambda u, z: [0.0, u, z]),
         "right": (np.array([-1.0, 0, 0]), lambda u, z: [100.0, u, z])}


def depth_map(mesh, face, us, zs):
    """Material depth behind the face, on a (u, z) grid."""
    inw, at = FACES[face]
    out = np.zeros((len(zs), len(us)))
    for i, z in enumerate(zs):
        o = np.array([at(u, z) for u in us]) - inw * 1e-3
        hp, ir, _ = mesh.ray.intersects_location(o, np.tile(inw, (len(us), 1)),
                                                 multiple_hits=False)
        if not len(ir):
            continue
        o2 = hp + inw * 1e-3
        hp2, ir2, _ = mesh.ray.intersects_location(
            o2, np.tile(inw, (len(o2), 1)), multiple_hits=False)
        d = np.zeros(len(o2))
        d[ir2] = np.linalg.norm(hp2 - o2[ir2], axis=1)
        out[i, ir] = d
    return out


def main():
    old = os.path.join(ROOT, "build", "cube_trials", "h3_U3T_rot_bottom.stl")
    new = os.path.join(ROOT, "stl", "U3T_rot_bottom.stl")
    if not os.path.exists(old):
        print(f"no 'before' mesh at {old} -- skipping the comparison")
        return
    us = np.arange(37.0, 63.01, 0.3)
    zs = np.arange(7.55, 13.21, 0.1)
    f, axs = plt.subplots(1, 2, figsize=(13.2, 5.0), dpi=165, layout="constrained")
    for ax, (tag, path) in zip(axs, (("printed — flared dovetail", old),
                                     ("reshaped — straight tenon", new))):
        m = trimesh.load(path)
        m.merge_vertices(); m.process(validate=True)
        D = depth_map(m, "back", us, zs)
        live = D > 0.02
        bad = live & (D < LIMIT)
        ax.pcolormesh(us, zs, np.where(live, np.minimum(D, 3.0), np.nan),
                      cmap="YlOrBr", vmin=0, vmax=3.0, shading="nearest")
        ys, xs = np.where(bad)
        ax.scatter(us[xs], zs[ys], s=5, c=RED, lw=0, label=f"under {LIMIT} mm")
        thin_mm2 = bad.sum() * 0.3 * 0.1
        mn = D[live].min() if live.any() else 0.0
        ax.set_title(f"{tag}\nback face — thinnest {mn:.2f} mm, "
                     f"{thin_mm2:.1f} mm² under {LIMIT} mm",
                     fontsize=10.5, color=INK)
        ax.set_xlabel("across the face (mm)", fontsize=9)
        ax.set_ylabel("z (mm)", fontsize=9)
        ax.set_aspect("equal"); ax.tick_params(labelsize=8)
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    out = os.path.join(IMG, "f4_key_wing.png")
    f.savefig(out, facecolor="white")
    print("f4_key_wing.png")


if __name__ == "__main__":
    main()
