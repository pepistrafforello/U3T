"""Render the article markdown to a local HTML page for clean pasting into Medium.

Medium's editor accepts pasted rich text: open the generated page in a browser,
select all, copy, paste into a new Medium story. Text, headings, blockquotes and
emphasis survive; each image lands as a real Medium image you can then caption.
"""
import os
import re

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "article", "medium-post.md")
IMG = os.path.join(ROOT, "docs", "article", "images")
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)

body = markdown.markdown(open(SRC, encoding="utf-8").read(), extensions=["smarty"])
# the markdown references images/… relative to the article; make them absolute so
# the preview page renders from anywhere on disk
body = re.sub(r'src="images/', 'src="file:///%s/' % IMG.replace("\\", "/"), body)

page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>U3T — paste into Medium</title>
<style>
 body {{ max-width: 740px; margin: 40px auto; font-family: Georgia, serif;
        font-size: 19px; line-height: 1.55; color: #222; }}
 img {{ max-width: 100%; }}
 blockquote {{ border-left: 3px solid #222; margin-left: 0; padding-left: 18px; color: #444; }}
 h1, h2 {{ font-family: "Segoe UI", Arial, sans-serif; }}
 em {{ color: #555; }}
</style></head><body>
{body}
</body></html>
"""
out = os.path.join(BUILD, "medium-post-paste.html")
open(out, "w", encoding="utf-8").write(page)
print("written:", out)
print("images referenced:", len(re.findall(r"<img", page)))
