#!/usr/bin/env python3
"""
Build PDFs from fundraising markdown drafts.

Usage (from kova_agent repo root):
    python fundraising/scripts/build_pdfs.py

Output: fundraising/pdf/ (mirrors relative paths of .md sources)

Skips: CSV, README placeholders in 01-corporate only if desired.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FUNDRAISING = ROOT / "fundraising"
SRC_ROOT = FUNDRAISING
OUT_ROOT = FUNDRAISING / "pdf"

SKIP_DIRS = {"scripts", "pdf", "__pycache__"}
SKIP_NAMES = set()  # process all .md including README


def discover_markdown() -> list[Path]:
    files: list[Path] = []
    for path in sorted(SRC_ROOT.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        rel = path.relative_to(SRC_ROOT)
        files.append(rel)
    return files


def ensure_out_dir(rel: Path) -> Path:
    out = OUT_ROOT / rel.parent
    out.mkdir(parents=True, exist_ok=True)
    return out


def strip_for_html(md: str) -> str:
    """Light preprocess: remove HTML comment blocks, keep structure."""
    return md


def build_weasyprint(md_path: Path, pdf_path: Path) -> bool:
    try:
        import markdown
        from weasyprint import HTML
    except (ImportError, OSError):
        return False

    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )
    css = """
    @page { size: A4; margin: 2cm; }
    body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.45; color: #111; }
    h1 { font-size: 20pt; margin-top: 0; page-break-after: avoid; }
    h2 { font-size: 14pt; page-break-after: avoid; }
    h3 { font-size: 12pt; }
    table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }
    th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
    th { background: #f5f5f5; }
    blockquote { border-left: 4px solid #ccc; margin-left: 0; padding-left: 1em; color: #444; }
    code { font-size: 9pt; background: #f4f4f4; padding: 2px 4px; }
    pre { background: #f4f4f4; padding: 10px; font-size: 9pt; overflow-wrap: break-word; white-space: pre-wrap; }
    hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
    """
    html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body}</body></html>"""
    HTML(string=html_doc, base_url=str(md_path.parent)).write_pdf(str(pdf_path))
    return True


def build_pandoc(md_path: Path, pdf_path: Path) -> bool:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False
    cmd = [
        pandoc,
        str(md_path),
        "-o",
        str(pdf_path),
        "--pdf-engine=pdflatex",
        "-V",
        "geometry:margin=2cm",
        "-V",
        "fontsize=11pt",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_mdpdf(md_path: Path, pdf_path: Path) -> bool:
    try:
        from mdpdf.pdf_renderer import MarkdownPdf
    except ImportError:
        return False
    try:
        renderer = MarkdownPdf()
        renderer.convert(str(md_path), str(pdf_path))
        return True
    except Exception:
        return False


def build_xhtml2pdf(md_path: Path, pdf_path: Path) -> bool:
    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError:
        return False

    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    html_doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 4px; }}
    </style></head><body>{body}</body></html>"""
    with open(pdf_path, "wb") as out:
        status = pisa.CreatePDF(html_doc, dest=out, encoding="utf-8")
    return not status.err


def main() -> int:
    rel_paths = discover_markdown()
    if not rel_paths:
        print("No markdown files found under fundraising/")
        return 1

    backend: str | None = None
    ok, fail = 0, 0
    methods = [
        ("weasyprint", build_weasyprint),
        ("pandoc", build_pandoc),
        ("mdpdf", build_mdpdf),
        ("xhtml2pdf", build_xhtml2pdf),
    ]

    for rel in rel_paths:
        md_path = SRC_ROOT / rel
        pdf_rel = rel.with_suffix(".pdf")
        pdf_path = OUT_ROOT / pdf_rel
        ensure_out_dir(pdf_rel)

        built = False
        for name, fn in methods:
            if backend is not None and name != backend:
                continue
            if fn(md_path, pdf_path):
                if backend is None:
                    backend = name
                print(f"OK [{name}]: {rel}")
                ok += 1
                built = True
                break

        if not built:
            print(f"FAIL: {rel}", file=sys.stderr)
            fail += 1

    print(f"\nDone: {ok} PDFs, {fail} failures")
    if backend:
        print(f"Backend: {backend}")
    else:
        print(
            "Install a backend: pip install markdown weasyprint",
            file=sys.stderr,
        )
        return 2 if fail else 0
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
