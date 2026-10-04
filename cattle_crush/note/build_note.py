"""Render note/research_note.html to note/research_note.pdf (US Letter) and report the page count.

Usage: python note/build_note.py      (requires pymupdf, see requirements-note.txt)
Figures are read from results/figures/ (produced by python run_all.py).
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "note" / "research_note.html"
PDF = ROOT / "note" / "research_note.pdf"
CSS = """
* { font-family: sans-serif; }
body { font-size: 8.6pt; line-height: 1.26; color: #111111; }
h1 { font-size: 13.5pt; margin: 0 0 2pt 0; }
h2 { font-size: 10.5pt; margin: 7pt 0 2pt 0; color: #1a1a1a; }
p { margin: 0 0 4pt 0; text-align: justify; }
p.sub { font-size: 8pt; color: #444444; margin-bottom: 5pt; }
p.cap { font-size: 7.6pt; color: #444444; margin: 1pt 0 5pt 0; text-align: left; }
ul { margin: 0 0 3pt 12pt; padding: 0; }
li { margin: 0 0 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0 5pt 0; font-size: 7.8pt; }
th { border-bottom: 1px solid #444444; border-top: 1px solid #444444; text-align: left; padding: 1.5pt 3pt; }
td { border-bottom: 1px solid #dddddd; padding: 1.5pt 3pt; vertical-align: top; }
div.box { border: 1px solid #999999; padding: 4pt 6pt; margin: 3pt 0 5pt 0; background-color: #f6f6f6; }
div.pending { border: 1.5px solid #b45309; background-color: #fff7ed; }
code { font-family: monospace; font-size: 7.8pt; }
img { display: block; margin: 2pt auto 0 auto; }
"""


def build() -> int:
    story = pymupdf.Story(html=HTML.read_text(), user_css=CSS, archive=pymupdf.Archive(str(ROOT / "results" / "figures")))
    page = pymupdf.paper_rect("letter")
    frame = page + (50, 46, -50, -46)
    writer = pymupdf.DocumentWriter(str(PDF))
    more, n = 1, 0
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(frame)
        story.draw(device)
        writer.end_page()
        n += 1
    writer.close()
    doc = pymupdf.open(str(PDF))                      # page numbers
    for i, p in enumerate(doc, start=1):
        p.insert_text((page.width / 2 - 10, page.height - 24), f"{i} / {len(doc)}", fontsize=7.5, color=(0.35, 0.35, 0.35))
    doc.saveIncr()
    return len(doc)


if __name__ == "__main__":
    pages = build()
    print(f"{PDF.relative_to(ROOT)}: {pages} pages (limit 5)")
