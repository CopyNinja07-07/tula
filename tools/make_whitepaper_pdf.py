"""Build docs/TULA-Whitepaper.pdf from docs/WHITEPAPER.md with headless Chrome.

    .venv/bin/python tools/make_whitepaper_pdf.py
"""
import subprocess
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """@page{size:A4;margin:18mm 16mm}
body{font:10.3pt/1.5 Inter,-apple-system,"Segoe UI",sans-serif;color:#1b1726}
h1{font-size:21pt;font-weight:600;letter-spacing:-.02em;margin:0 0 4pt}
h2{font-size:13.5pt;margin:16pt 0 6pt;padding-bottom:3pt;border-bottom:2px solid #c9a24b}
h3{font-size:11pt;margin:11pt 0 4pt}
p,li{orphans:3;widows:3}
code{font:8.6pt Menlo,monospace;background:#f3efe6;padding:0 3px;border-radius:3px}
pre{background:#1d1a14;color:#f1ead8;padding:8pt 10pt;border-radius:6px;font-size:7.9pt;line-height:1.4;white-space:pre;page-break-inside:avoid}
pre code{background:none;color:inherit;padding:0}
table{border-collapse:collapse;width:100%;margin:6pt 0 10pt;font-size:8.6pt}
th,td{border:1px solid #ddd5c3;padding:4pt 6pt;text-align:left;vertical-align:top}
th{background:#f6f1e4} tr{page-break-inside:avoid}
blockquote{margin:8pt 0;padding:6pt 10pt;border-left:3px solid #c9a24b;background:#fbf8f0}
a{color:#7a5a12;text-decoration:none}"""


def main() -> None:
    body = markdown.markdown((ROOT / "docs" / "WHITEPAPER.md").read_text(), extensions=["tables", "fenced_code"])
    html = f'<!doctype html><html><head><meta charset="utf-8"><title>TULA Whitepaper</title><style>{CSS}</style></head><body>{body}</body></html>'
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "tula.html"
        page.write_text(html)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                        f"--user-data-dir={tmp}/profile", f"--print-to-pdf={ROOT / 'docs' / 'TULA-Whitepaper.pdf'}",
                        page.as_uri()], check=True, capture_output=True)
    print(ROOT / "docs" / "TULA-Whitepaper.pdf")


if __name__ == "__main__":
    main()
