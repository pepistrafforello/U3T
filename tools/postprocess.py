"""Flatten Blender renders onto white, crop, montage, and sanity-check."""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "build", "render_raw")
IMG = os.path.join(ROOT, "docs", "article", "images")
os.makedirs(IMG, exist_ok=True)


def label_font(size=34):
    """A plain sans label font, wherever this happens to run."""
    import matplotlib.font_manager as fm
    for cand in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            pass
    try:
        return ImageFont.truetype(
            fm.findfont(fm.FontProperties(family="DejaVu Sans")), size)
    except Exception:
        return ImageFont.load_default()


FONT = label_font(34)
INK = (70, 74, 80)


def flatten(name, pad=36):
    im = Image.open(os.path.join(RAW, name + ".png")).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    im = im.crop(bbox)
    out = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad), "white")
    out.paste(im, (pad, pad), im)
    return out


PRODUCED = []


def save(im, name):
    im.save(os.path.join(IMG, name + ".png"))
    PRODUCED.append(name)
    print(name, im.size)


def montage_row(names, labels, out, target_h=None, gap=26, label_h=52):
    ims = [flatten(n, pad=18) for n in names]
    h = target_h or min(i.height for i in ims)
    ims = [i.resize((round(i.width * h / i.height), h), Image.LANCZOS) for i in ims]
    W = sum(i.width for i in ims) + gap * (len(ims) - 1)
    canvas = Image.new("RGB", (W, h + label_h), "white")
    d = ImageDraw.Draw(canvas)
    x = 0
    for im, lab in zip(ims, labels):
        canvas.paste(im, (x, 0))
        tw = d.textlength(lab, font=FONT)
        d.text((x + (im.width - tw) / 2, h + 6), lab, fill=INK, font=FONT)
        x += im.width + gap
    save(canvas, out)


def montage_col(names, labels, out, gap=22, label_w=0):
    ims = [flatten(n, pad=16) for n in names]
    w = max(i.width for i in ims)
    ims = [i.resize((w, round(i.height * w / i.width)), Image.LANCZOS) for i in ims]
    label_h = 50
    H = sum(i.height + label_h for i in ims) + gap * (len(ims) - 1)
    canvas = Image.new("RGB", (w, H), "white")
    d = ImageDraw.Draw(canvas)
    y = 0
    for im, lab in zip(ims, labels):
        tw = d.textlength(lab, font=FONT)
        d.text(((w - tw) / 2, y + 4), lab, fill=INK, font=FONT)
        canvas.paste(im, (0, y + label_h))
        y += im.height + label_h + gap
    save(canvas, out)


# singles
for src, dst in [("s_assembled", "r3_assembled"), ("s_exploded", "r3_exploded"),
                 ("s_bottom", "r3_bottom"), ("s_top_flipped", "r3_top_flipped"),
                 ("s_interface", "r3_interface"), ("r_bottomv", "rr_bottom"),
                 ("r_exploded", "rr_exploded"), ("r_interface", "rr_interface")]:
    save(flatten(src), dst)

# montages
montage_col([f"s_side_{n}" for n in ("front", "right", "back", "left")],
            ["front", "right", "back", "left"], "r3_sides")
montage_col([f"r_side_{n}" for n in ("front", "right", "back", "left")],
            ["front", "right", "back", "left"], "rr_sides")
montage_row([f"s_seq_{n}" for n in "abc"], ["slide 0 mm", "slide 12 mm", "slide 30 mm"],
            "r3_sequence", target_h=760)
montage_row([f"r_seq_{n}" for n in "abc"], ["rotation 0°", "rotation 6°", "rotation 14°"],
            "rr_sequence", target_h=760)

# sanity checks on every image this script produced (the o_*.png screenshots
# recovered from the original notes are not ours to judge, so they are skipped)
import numpy as np
bad = []
for fn in sorted(n + ".png" for n in PRODUCED):
    im = Image.open(os.path.join(IMG, fn)).convert("RGB")
    a = np.asarray(im)
    nonwhite = float((a.min(axis=2) < 245).mean())
    if im.width < 900 or not (0.02 < nonwhite < 0.95):
        bad.append((fn, im.size, round(nonwhite, 3)))
    print(f"check {fn}: {im.size}, content={nonwhite:.2f}")
print("BAD:", bad if bad else "none")
