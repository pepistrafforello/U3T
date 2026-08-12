"""Extract the embedded images of the original design notes into docs/figures/original/.

Only needed to reproduce that folder from docs/original-design-notes.pdf; the
extracted PNGs are committed, so a normal checkout never has to run this.

    python tools/extract_pdf_figures.py        (requires pypdf)
"""
import os

from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "original-design-notes.pdf")
OUT = os.path.join(ROOT, "docs", "figures", "original")
os.makedirs(OUT, exist_ok=True)

reader = PdfReader(SRC)
count = 0
for pno, page in enumerate(reader.pages, start=1):
    for ino, img in enumerate(page.images):
        ext = os.path.splitext(img.name)[1] or ".png"
        name = f"p{pno:02d}_{ino}{ext}"
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(img.data)
        count += 1
        print(name, len(img.data) // 1024, "KB")
print("total:", count)
