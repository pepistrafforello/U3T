# U3T — the Unnamed 3D Thingy

**A parametric generator, and its own verification suite, for a family of two-part solids that
look impossible from every side and come apart with a single movement.**

> There is a block made of two different kinds of wood, mated so perfectly that there is no air
> between them. From every side the assembly looks exactly the same: a seam at mid-height with a
> small dovetail key in the middle of each face. The two layers can be separated with one simple
> movement — no glue, no springs, no tricks. The same movement puts them back together. How?

![The block, identical from all four sides](docs/article/images/o_puzzle.png)

The dovetail on the front face says the top cannot be lifted. The dovetail on the side face says it
cannot slide sideways either. Every face you check makes the object more impossible — and yet the
answer is not unique: the puzzle has *infinitely many* solutions, and the interesting ones have
enough room left over to hide a message inside.

This repository holds the code that designs those objects, the code that proves the design is
correct, the print-ready STL files it produces, and the write-ups. The story is told in the
article: [`docs/article/medium-post.md`](docs/article/medium-post.md). The engineering is in
[`docs/The-Unnamed-3D-Thingy.md`](docs/The-Unnamed-3D-Thingy.md).

---

## The idea in one move: shear the world

Suppose the two halves separate by sliding along a fixed oblique direction **d** = (d₁, d₂, 1).
When is a proposed parting surface valid? Change coordinates so that **d** becomes vertical:

```
u = x − d₁·z        v = y − d₂·z        z = z
```

![The shear trick](docs/article/images/d_shear.png)

In sheared space the separating motion is straight up, and a surface can be lifted off vertically
**exactly when it is a single-valued height field** — one z per (u, v), vertical cliffs allowed.
So: draw *anything* in the (u, v) plane, extrude it vertically, shear back. The walls come out
parallel to **d** automatically, and the two parts are separable by construction. No angle checks,
no trial and error.

Two consequences fall out of that one sentence:

* **Every side gets its own private groove.** Because **d** has a component along all three axes,
  each face carries an independent ramp instead of two grooves crossing the whole block — so the
  square is not special: any polygon with three or more sides works.
* **The middle of the block becomes free real estate.** Once the perimeter does the puzzle's work,
  the rest of the hidden interface can be arbitrary artwork: a title, a portrait, a QR code.

The shipped object uses that space for a graduation gift — a title, a subtitle, and a scannable QR
code, none of it visible from outside:

![The hidden interface](docs/article/images/r3_interface.png)

---

## What is in this repository

```
u3t_generator.py        straight edition: builds both parts, then verifies them
u3t_rot_generator.py    rotation edition: same contract, opens by rotating about an external axis
dfm_scan.py             independent minimum-feature scan (the 0.5 mm FDM rule)
u3t_figures.py          figures for the technical document, straight edition
u3t_rot_figures.py      figures for the technical document, rotation edition

stl/                    the six meshes: two printable pairs, plus assembly-oriented copies
verification/           machine-readable verification reports (JSON), regenerated on every build

docs/
  The-Unnamed-3D-Thingy.md    the full write-up: theory, Fusion walkthrough, generator,
                              verification, printing, and the rotation chapter
  original-design-notes.pdf   the notes the project started from, years before it was finished
  figures/                    figures for the write-up (`original/` = extracted from the PDF)
  article/medium-post.md      the article, in Medium's voice
  article/images/             its renders (Blender/Cycles) and diagrams (matplotlib)

tools/
  prep_shots.py           poses the verified STLs and emits the shot list
  blender_render.py       headless Cycles renderer for the photographic figures
  postprocess.py          flatten / crop / montage / sanity-check the renders
  diagrams.py             the clean 2D diagrams used by the article
  make_paste_html.py      article markdown -> HTML page you can paste into Medium
  extract_pdf_figures.py  re-extracts docs/figures/original/ from the PDF
```

Everything writes into `build/` (git-ignored) except the deliverables — STLs, reports, figures —
which land in their committed locations.

---

## Quick start

```bash
git clone https://github.com/pepistrafforello/U3T.git
cd U3T
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt

python u3t_generator.py         # straight edition: build + verify        (~10 s)
python u3t_rot_generator.py     # rotation edition: build + verify        (~25 s)
python dfm_scan.py              # minimum-feature scan of all four parts  (~45 s)
```

Each generator writes its STLs to `stl/`, its report to `verification/`, and prints the whole
verification suite as it goes:

```
bottom: watertight=True winding=True bodies=1 volume=89932 mm^3 ... -> PASS
top:    watertight=True winding=True bodies=1 volume=56138 mm^3 ... -> PASS
assembled overlap: 0.000000 mm^3 -> PASS
slide along d, t= 0.05: overlap=0.000000 -> PASS
...
slide along d, t=   40: overlap=0.000000 -> PASS
control (straight up), t=1.0: overlap=61.126 mm^3 -> PASS (locks)
control (flat diagonal slide), t=1.0: overlap=341.060 mm^3 -> PASS (locks)
```

Nothing else is needed to print the object — but if you want to regenerate the pictures too, see
[Reproducing the figures](#reproducing-the-figures-and-the-article).

---

## The two editions

Both are 100 × 100 × 15 mm, both show the identical dovetailed seam on all four faces, and both
hide the same interface. They differ only in the motion that opens them — which is the point: two
objects that are indistinguishable from the outside and refuse each other's solution.

| | straight edition | rotation edition |
|---|---|---|
| opening motion | translation along **d** = (0.7, 0.7, 1) | rotation of ≈ 12° about an external axis |
| axis / direction | 44.7° off vertical, diagonal in plan | direction (1, 1, 0)/√2 through (105, −105, −103.5) mm |
| walls | planar, parallel to **d** | patches of cylinders coaxial with the axis |
| generator | `u3t_generator.py` | `u3t_rot_generator.py` |
| print files | `stl/U3T_bottom.stl`, `stl/U3T_top_print.stl` | `stl/U3T_rot_bottom.stl`, `stl/U3T_rot_top_print.stl` |
| report | `verification/verify_report.json` | `verification/verify_report_rot.json` |

![Opening the straight edition](docs/article/images/r3_sequence.png)

![Opening the rotation edition](docs/article/images/rr_sequence.png)

The rotation edition needs three placement rules, all of which the generator's geometry satisfies
and the write-up derives:

1. the axis must run **diagonally in plan**, or orbit planes end up parallel to a face and grooves
   surface where they must not;
2. the **apex plane** — the vertical plane through the axis, where orbits turn around — must miss
   the block, otherwise a flat lid is visited twice by the same orbit and the parts jam (this is
   the silent failure that wrecked the original Blender attempt);
3. the axis must sit **far enough away** that every orbit slope stays printable.

---

## Design parameters

All of them live at the top of the generators, in millimetres. Change one, re-run, and the whole
object — including its proof — is rebuilt.

| parameter | shipped | meaning |
|---|---|---|
| `L`, `H` | 100, 15 | stock footprint and height |
| `SHX`, `SHY` | 0.7, 0.7 | the separation direction **d** = (`SHX`, `SHY`, 1) |
| `CLR` | 0.15 | clearance per part; total gap between the halves is 0.3 |
| `BAND_Z` | 7.5 | height of the seam on the side faces |
| `KEY_Z0`, `KEY_Z1` | 7.5, 11.5 | bottom and top of the dovetail key |
| `KEY_NECK_Z` | 8.3 | straight neck below the flare (manufacturability, see below) |
| `KEY_HW0`, `KEY_HW1` | 6.0, 10.0 | key half-width at the band and at the top (it flares → undercut) |
| `KEY_RAIL` | 8.0 | length of the internal anchor rail behind each key |
| `MIN_FEATURE` | 0.55 | minimum printable wall/stroke enforced on the interface artwork |
| `PLAT_*` | 7.0 … 11.0, ±30/34 | the plateau frustum that carries the payload |
| `QR_BOX`, `TITLE_BOX`, `SUB_BOX` | — | where the payload sits, in sheared plan coordinates |
| `QR_PAYLOAD`, `TITLE`, `SUBTITLE`, `SIGNATURE` | — | the content itself |

Two rules constrain the numbers, and both were learned the hard way:

* **Depth costs lean.** A key `h` mm tall can protrude at most `lean × h` from the face. A
  near-vertical **d** gives wafer-thin keys no matter how you draw them. At 0.7 the design sits
  right at the 45° overhang limit an FDM printer will bridge without supports — which is exactly
  where you want to be.
* **Anchor whatever the crop can orphan.** Each key continues inward as a solid rail, unioned in
  *before* the stock box crops the leaning prism. Skip this and the visible tabs become watertight,
  collision-free, and attached to nothing.

### Making your own

```python
# u3t_generator.py
QR_PAYLOAD = "https://example.com/album"   # shorter URLs -> coarser, easier-to-print modules
TITLE      = "Your Name"
SUBTITLE   = "Your Occasion"
```

then `python u3t_generator.py`. The verification suite re-runs on the new geometry, so a change
that breaks the puzzle property cannot pass silently. For a different polygon, edit the `faces`
table in `key_footprints()` — one entry per side, each with its inward plan direction; the theory
imposes no limit on the number of sides.

---

## Verification: the printed object cannot be flawed by luck

"Be accurate" means *do not trust the construction* — test the meshes that go to the printer. Each
generator attacks its own output before it exits, and writes the results to `verification/`.

| check | straight edition | rotation edition |
|---|---|---|
| bottom part watertight, consistent winding | yes — 89 932 mm³ | yes — 88 380 mm³ |
| top part watertight, consistent winding | yes — 56 138 mm³ | yes — 57 572 mm³ |
| **connected bodies per part** | 1 and 1 | 1 and 1 |
| assembly envelope | exactly 100 × 100 × 15 | exactly 100 × 100 × 15 |
| assembled overlap | 0.000000 mm³ | 0.000000 mm³ |
| overlap through the full opening motion | 0.000000 mm³ at 14 stations, t = 0.05 … 40 mm | 0.000000 mm³ at 12 stations, θ = 0.05° … 25° |
| **control** — pull straight up, 1 / 2 mm | collides: 61.1 / 102.8 mm³ | collides: 128.5 / 227.6 mm³ |
| **control** — flat diagonal slide, 1 / 2 mm | collides: 341.1 / 863.3 mm³ | collides: 416.3 / 926.1 mm³ |
| **control** — the *other* edition's move | — | collides: 282.1 mm³ (straight slide, 2 mm) |
| **control** — reverse rotation, 1° | — | collides: 21 424 mm³ |
| thin-feature scan (`dfm_scan.py`) | no free-standing feature below 0.5 mm | no free-standing feature below 0.5 mm |

The control rows are the puzzle property itself, measured rather than asserted: the naive motions
jam, and the one intended motion sweeps through the entire disassembly without ever touching. The
body-count row exists because it once failed — an early draft with a shallower **d** and no anchor
rails produced keys that were watertight, collision-clean, and *detached*. Watertightness says
nothing about a mesh being in one piece; counting connected components does.

---

## Manufacturability

Geometry can be provably correct and still contain features no nozzle can make. After a
manufacturability review flagged two of them, the generators enforce a minimum-feature policy:

* **Asymmetric clearance on the artwork.** A sliding fit does not need the gap split evenly. The
  raised side keeps its full nominal stroke width (never below `MIN_FEATURE` = 0.55 mm) and the
  cavity absorbs the whole 0.3 mm — otherwise the wall left standing between two neighbouring
  letter cavities can shrink to a tenth of a millimetre. Residual sub-minimum necks are removed by
  a morphological opening; sub-minimum walls between adjacent cavities are fused by a closing
  (`clean_thin`, `close_gaps`, `content_offset` in `u3t_generator.py`).
* **A straight neck under every flare.** The key lip starts only above `KEY_NECK_Z`, where its own
  depth already exceeds 0.55 mm, so the overhanging lip never feathers to nothing at its root.

`dfm_scan.py` re-checks this the way a print shop does — slice the part every 0.45 mm, erode each
slice by 0.249 mm, and report whatever disappears:

```bash
python dfm_scan.py
```

Both top parts come back completely clean. The bottom parts report a handful of patches, all of
them on the sloped edges where the key flanks meet the outer faces: those are tapering edges of
solid material, backed by full-thickness material immediately behind — a chamfer, not a wall. They
print as a slightly rounded lip edge, with no consequence for fit or strength. Every flush dovetail
outline in this family has them.

---

## Printing and assembly

* **Files** — print `stl/U3T_bottom.stl` as oriented and `stl/U3T_top_print.stl` (already flipped
  exterior-side-down); or the `U3T_rot_*` pair for the rotation edition. `U3T_top.stl` and
  `U3T_rot_top.stl` are the assembly-oriented copies, for CAD and inspection.
* **No supports.** The leaning walls sit at 44.7°, right at the classic FDM limit; the ramps are
  gentler; every relief faces up on the bed.
* **Settings** — PLA, 0.2 mm layers (0.12 mm makes a crisper QR), 3 perimeters, ≥ 15 % infill.
  Enable elephant-foot compensation (~0.1 mm) or deburr the first-layer edges: the band and the
  side faces have to mate flush.
* **Fit** — the 0.3 mm total gap is a snug sliding fit on a well-tuned printer. If it binds, sand
  lightly or rebuild with `CLR = 0.20`; for a loose demonstration fit use `CLR = 0.25`.
* **Assembly** — rest the top over the bottom offset by about +10 mm in x and y and lower it along
  the diagonal; it seats flush in one push. Because the lean of **d** breaks the square's symmetry,
  **only one of the four orientations engages** — the solver has to find the motion *and* the
  orientation.
* **The reveal** — relief QR codes scan best under raking light; a soft pencil rubbed flat across
  the module tops makes them scan instantly.

---

## Reproducing the figures and the article

The diagrams are matplotlib; the photographic figures are rendered headlessly in **Blender 5.x**
with Cycles, which has to be installed separately and reachable as `blender`.

```bash
python tools/diagrams.py                  # the 2D diagrams -> docs/article/images/
python tools/prep_shots.py                # pose the STLs -> build/posed, build/shots.json
blender -b --factory-startup -noaudio --python tools/blender_render.py -- \
        build/shots.json build/render_raw
python tools/postprocess.py               # flatten, crop, montage, check -> docs/article/images/
python tools/make_paste_html.py           # -> build/medium-post-paste.html
python u3t_figures.py                     # technical-document figures -> docs/figures/
python u3t_rot_figures.py
```

`postprocess.py` finishes with an automated check on every emitted image (minimum width, and a
non-white content fraction inside sane bounds) and prints `BAD: none` when they all pass.
`make_paste_html.py` produces a local page whose rich-text copy-paste lands cleanly in Medium's
editor, images included.

---

## Documentation

| document | what it is |
|---|---|
| [`docs/The-Unnamed-3D-Thingy.md`](docs/The-Unnamed-3D-Thingy.md) | the complete write-up: the original notes, the proof, a step-by-step Autodesk Fusion walkthrough, the automated pipeline, the verification suite, printing, and the rotation edition |
| [`docs/article/medium-post.md`](docs/article/medium-post.md) | the same story told as an article, for readers rather than builders |
| [`docs/original-design-notes.pdf`](docs/original-design-notes.pdf) | where it began: the unfinished notes, kept for provenance |

---

## Tested environment

Python 3.11.5 on Windows 11, with the versions pinned as comments in
[`requirements.txt`](requirements.txt). The heavy lifting is done by
[`manifold3d`](https://github.com/elalish/manifold) (guaranteed-watertight booleans),
[`trimesh`](https://github.com/mikedh/trimesh) and [`shapely`](https://github.com/shapely/shapely).
Nothing in the pipeline is platform-specific; the only external program is Blender, and only for
the figures.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). A small number of screenshots inside the original
design notes are third-party material and are excluded from that grant; they are itemised in
[`NOTICE`](NOTICE), together with the acknowledgements this project owes.

*The object still has a dovetail on every face, a motion nobody can see, a name hidden in the
middle — and, after all this time, no name of its own.*
