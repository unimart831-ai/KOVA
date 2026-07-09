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
    "var(--kova-deep-navy)": "#0f172a",
    "var(--kova-teal)": "#0066FF",
    "var(--kova-teal-dim)": "#0052CC",
    "var(--kova-teal-glow)": "rgba(0, 102, 255, 0.25)",
    "var(--kova-teal-soft)": "rgba(0, 102, 255, 0.12)",
    "var(--kova-white)": "#f8fafc",
    "var(--kova-muted)": "#94a3b8",
    "var(--kova-body)": "#334155",
    "var(--kova-light)": "#f1f5f9",
    "var(--kova-border)": "#e2e8f0",
    "var(--section-title)": "14px",
    "var(--body-sm)": "11px",
    "var(--body-xs)": "10px",
    "var(--hero-size)": "28px",
    'var(--font)': '"Inter", "DM Sans", system-ui, sans-serif',
}


def expand_css_vars(css: str) -> str:
    """xhtml2pdf/reportlab do not support CSS custom properties."""
    for token, value in CSS_VARS.items():
        css = css.replace(token, value)
    return css


def resolve_css_imports(css: str) -> str:
    """Expand local @import statements (e.g. brochure-master.css → brochure-base.css)."""
    lines: list[str] = []
    for line in css.splitlines():
        stripped = line.strip()
        if stripped.startswith('@import url("') and stripped.endswith('");'):
            rel = stripped[len('@import url("') : -3]
            imported = ASSETS / rel
            if imported.exists():
                lines.append(f"/* --- {rel} --- */")
                lines.extend(
                    ln
                    for ln in imported.read_text(encoding="utf-8").splitlines()
                    if not ln.strip().startswith("@import url")
                )
                continue
        if stripped.startswith("@import url"):
            continue
        lines.append(line)
    return "\n".join(lines)


def collect_stylesheets(html: str) -> tuple[str, list[str]]:
    """Return HTML with stylesheet links removed and ordered CSS hrefs."""
    import re

    pattern = re.compile(
        r'<link rel="stylesheet" href="\.\./assets/([^"]+\.css)">\s*'
    )
    hrefs = pattern.findall(html)
    html = pattern.sub("", html)
    return html, hrefs


def inline_css(html: str, html_path: Path) -> str:
    """Embed linked brochure CSS for PDF engines that struggle with relative links."""
    html, hrefs = collect_stylesheets(html)
    if not hrefs:
        return expand_css_vars(html)

    css_parts: list[str] = []
    for href in hrefs:
        css_path = ASSETS / href
        if not css_path.exists():
            continue
        css = css_path.read_text(encoding="utf-8")
        css = resolve_css_imports(css)
        css_offline = "\n".join(
            line
            for line in css.splitlines()
            if not line.strip().startswith("@import url")
        )
        css_parts.append(f"/* --- {href} --- */\n{expand_css_vars(css_offline)}")

    if css_parts:
        style_block = "<style>\n" + "\n\n".join(css_parts) + "\n</style>"
        html = html.replace("</head>", f"{style_block}\n</head>", 1)
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
