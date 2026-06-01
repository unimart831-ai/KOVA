#!/usr/bin/env python3
"""
Build print-ready PDFs from KOVA marketing brochure HTML.

Usage (from kova_agent repo root):
    python marketing/brochures/scripts/build_brochure_pdfs.py

Output: marketing/brochures/pdf/*.pdf

Backends (first success wins, same order as fundraising/scripts/build_pdfs.py):
  1. WeasyPrint (best CSS/gradients; needs GTK on Windows)
  2. xhtml2pdf (Windows-friendly fallback)
"""

from __future__ import annotations

import sys
from pathlib import Path

BROCHURES = Path(__file__).resolve().parents[1]
HTML_DIR = BROCHURES / "html"
PDF_DIR = BROCHURES / "pdf"
ASSETS = BROCHURES / "assets"


def discover_html() -> list[Path]:
    return sorted(HTML_DIR.glob("*.html"))


CSS_VARS = {
    "var(--kova-navy)": "#0c1222",
    "var(--kova-charcoal)": "#151d2e",
    "var(--kova-slate)": "#1e293b",
    "var(--kova-teal)": "#00d4aa",
    "var(--kova-teal-dim)": "#00a888",
    "var(--kova-teal-glow)": "rgba(0, 212, 170, 0.25)",
    "var(--kova-white)": "#f8fafc",
    "var(--kova-muted)": "#94a3b8",
    "var(--kova-body)": "#334155",
    "var(--kova-light)": "#f1f5f9",
    "var(--kova-border)": "#e2e8f0",
    'var(--font)': '"Inter", "DM Sans", system-ui, sans-serif',
}


def expand_css_vars(css: str) -> str:
    """xhtml2pdf/reportlab do not support CSS custom properties."""
    for token, value in CSS_VARS.items():
        css = css.replace(token, value)
    return css


def inline_css(html: str, html_path: Path) -> str:
    """Embed brochure-base.css for PDF engines that struggle with relative links."""
    css_path = ASSETS / "brochure-base.css"
    if not css_path.exists():
        return html
    css = css_path.read_text(encoding="utf-8")
    css_offline = "\n".join(
        line for line in css.splitlines() if not line.strip().startswith("@import url")
    )
    css_offline = expand_css_vars(css_offline)
    link_tag = '<link rel="stylesheet" href="../assets/brochure-base.css">'
    if link_tag in html:
        html = html.replace(
            link_tag,
            f"<style>\n{css_offline}\n</style>",
        )
    return expand_css_vars(html)


def build_weasyprint(html_path: Path, pdf_path: Path) -> bool:
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return False

    try:
        html = inline_css(html_path.read_text(encoding="utf-8"), html_path)
        HTML(string=html, base_url=str(html_path.parent)).write_pdf(str(pdf_path))
        return True
    except Exception:
        return False


def build_xhtml2pdf(html_path: Path, pdf_path: Path) -> bool:
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return False

    try:
        html = inline_css(html_path.read_text(encoding="utf-8"), html_path)
        with open(pdf_path, "wb") as out:
            status = pisa.CreatePDF(
                html,
                dest=out,
                encoding="utf-8",
                path=str(html_path.parent),
            )
        return not status.err
    except Exception:
        return False


def main() -> int:
    files = discover_html()
    if not files:
        print(f"No HTML files in {HTML_DIR}", file=sys.stderr)
        return 1

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    backend: str | None = None
    ok, fail = 0, 0
    methods = [
        ("xhtml2pdf", build_xhtml2pdf),
        ("weasyprint", build_weasyprint),
    ]

    for html_path in files:
        pdf_path = PDF_DIR / f"{html_path.stem}.pdf"
        built = False
        for name, fn in methods:
            if fn(html_path, pdf_path):
                if backend is None:
                    backend = name
                print(f"OK [{name}]: {pdf_path.name}")
                ok += 1
                built = True
                break
        if not built:
            print(f"FAIL: {html_path.name}", file=sys.stderr)
            fail += 1

    print(f"\nDone: {ok} PDFs, {fail} failures -> {PDF_DIR}")
    if backend:
        print(f"Backend: {backend}")
    else:
        print(
            "Install: pip install weasyprint   OR   pip install xhtml2pdf",
            file=sys.stderr,
        )
        return 2 if fail else 0
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
