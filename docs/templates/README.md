# Drawing on the U3T canvas

Five templates, one per facet of the rotation edition's sawtooth interface, plus
one sheet carrying all five. They are **millimeter-true SVG**: one user unit is
one millimeter, and a millimeter on the page is a millimeter on the printed part.

| file | size | area | tilt |
|---|---|---|---|
| `facet_1.svg` | 41.3 x 8.5 mm | 182 mm2 | 62.0 deg |
| `facet_2.svg` | 88.6 x 13.1 mm | 876 mm2 | 53.5 deg |
| `facet_3.svg` | 88.0 x 14.4 mm | 964 mm2 | 47.0 deg |
| `facet_4.svg` | 47.9 x 15.8 mm | 422 mm2 | 41.8 deg |
| `facet_5.svg` | 7.0 x 2.8 mm | 10 mm2 | 37.3 deg |
| `canvas_combined.svg` | - | **2455 mm2** | all five |

Five facets. How many there are, and how much of the central area they cover,
is set by CANVAS_MAX_LEAN in the generator: it trims the canvas at the radius
where a facet would lean past it. Beware the widths -- these strips are
slanted, so a bounding box overstates the room. Size round artwork to the
inscribed circle, which is what tools/lockup_layout.py does.

The shapes are read off the built mesh, so they are exactly the surface that
exists — clearance, curtain and printable-angle trim already taken off. The
outline is the real edge; the dashed line 1 mm inside it is the margin artwork
should respect.

## Which sheet to draw on

`canvas_combined.svg` is usually the one you want. On it the five facets sit in
their true relative positions, and **the seams between them cost no width**: the
risers stand at a constant radius from the rotation axis, so they are edge-on when
you look along the opening motion and have no apparent width from that direction.
Artwork may run across a seam and will read as continuous — from that one
direction. From any other angle the surface reads as a louvre and the seams show.

Use the individual `facet_N.svg` files when each strip carries something of its
own — a line of text per strip, say — and you would rather not think about the
seams at all.

The strips taper: 38 → 76 → **95** → 77 → 39 mm. The middle one is the big
canvas; the two ends are small triangles.

## Tool

**Inkscape** (free, SVG-native, millimeters throughout). Affinity Designer or
Illustrator work equally well. Avoid anything that thinks in pixels.

Open the template, draw in the `artwork` layer, leave the `template` layer alone —
it is stripped automatically on import, so the outline, grid and caption can stay.

## The rules that matter

The artwork is extruded into relief, so it has to be **area**, not lines:

1. **Everything must end as closed, filled paths.**
   - Text → `Path ▸ Object to Path` (Shift+Ctrl+C). Live text imports as nothing.
   - Strokes → `Path ▸ Stroke to Path` (Ctrl+Alt+C). A stroke with no fill has no
     area and would extrude to nothing.
   - Overlapping shapes → `Path ▸ Union` (Ctrl++), so they cannot punch
     accidental holes in each other.
2. **Nothing thinner than 0.55 mm** — neither a stroke nor the gap between two
   strokes. Below that the nozzle cannot make it, and neighbouring shapes fuse.
   At this size that means bold weights and no hairline serifs.
3. **Stay inside the dashed margin.**
4. Keep it in millimeters. The template already is; do not rescale it.

Nothing needs mirroring: this artwork sits on the bottom part and is read
face-on when the block is opened.

## Checking before it is built

```bash
python tools/svg_content.py docs/templates/canvas_combined.svg
```

It reports how many filled regions it found and how much relief area, and it
flags thin strokes, thin gaps, and anything outside the facet or in the margin.
Run it before asking for a rebuild — it catches the "everything was still live
text" mistake in one second rather than after a print.

## How it maps back

`templates.json` records, per template, the offsets that put page millimeters back
on the part:

    w   = page_x + w0          (distance along the rotation axis)
    rho = r1 - page_y          (distance out from the axis)

Both are true distances on the facet, which is what makes the template
millimeter-true. You should not need this, but it is there so that nothing about
the mapping is hidden.
