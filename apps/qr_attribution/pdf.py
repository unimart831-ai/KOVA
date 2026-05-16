"""Print-ready PDF generation for QR codes.

Outputs a single PDF containing three sticker formats so the user can
print whatever fits their use case:

  Page 1: Receipt sticker (5cm x 5cm) — taped to receipts, packaging
  Page 2: Counter sticker (10cm x 10cm) — tills, mirrors, doors
  Page 3: Flyer (A5) — events, handouts

Uses reportlab's built-in QR rendering (no extra `qrcode` dep needed).
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


def _render_qr(c: canvas.Canvas, url: str, x: float, y: float, size: float) -> None:
    """Draw a QR code centred at (x, y) with the given size, in points."""
    qr = QrCodeWidget(url)
    qr_bounds = qr.getBounds()
    qr_w = qr_bounds[2] - qr_bounds[0]
    qr_h = qr_bounds[3] - qr_bounds[1]
    drawing = Drawing(size, size, transform=[
        size / qr_w, 0, 0, size / qr_h, 0, 0,
    ])
    drawing.add(qr)
    renderPDF.draw(drawing, c, x, y)


def _headline_for(qr) -> str:
    """One-line headline based on the landing template."""
    p = qr.landing_payload or {}
    if qr.landing_template == "discount":
        pct = p.get("discount_pct", 10)
        return f"Scan for {pct}% off"
    if qr.landing_template == "menu":
        return "Scan to see our menu"
    if qr.landing_template == "booking":
        return "Scan to book an appointment"
    if qr.landing_template == "follow":
        return "Scan to follow us"
    return (p.get("headline") or "Scan me!")[:80]


def generate_print_pack(qr, public_url: str) -> bytes:
    """Return PDF bytes containing all 3 sticker formats for `qr`.

    `public_url` is the absolute URL (e.g. https://kova.ai/qr/abc123/)
    that the QR encodes. Built by the view with request.build_absolute_uri.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    page_w, page_h = A5
    headline = _headline_for(qr)
    brand = (qr.user.profile.company_name if hasattr(qr.user, "profile")
             else "") or qr.user.full_name or ""

    # ── Page 1: receipt sticker (5cm x 5cm, centred) ──────────────────
    side = 5 * cm
    x = (page_w - side) / 2
    y = (page_h - side) / 2
    qr_size = 4 * cm
    _render_qr(c, public_url, x + (side - qr_size) / 2, y + 0.6 * cm, qr_size)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x + side / 2, y + 0.3 * cm, "Scan me!")
    c.setFont("Helvetica", 5)
    c.drawCentredString(page_w / 2, 0.8 * cm, "RECEIPT STICKER · 5×5cm · cut along edge")
    c.showPage()

    # ── Page 2: counter sticker (10cm x 10cm) ────────────────────────
    side = 10 * cm
    x = (page_w - side) / 2
    y = (page_h - side) / 2
    qr_size = 7 * cm
    _render_qr(c, public_url, x + (side - qr_size) / 2, y + 1.8 * cm, qr_size)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x + side / 2, y + 1.2 * cm, headline)
    c.setFont("Helvetica", 8)
    c.drawCentredString(x + side / 2, y + 0.5 * cm, brand[:60])
    c.setFont("Helvetica", 5)
    c.drawCentredString(page_w / 2, 0.8 * cm, "COUNTER STICKER · 10×10cm · cut along edge")
    c.showPage()

    # ── Page 3: flyer (full A5) ──────────────────────────────────────
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(page_w / 2, page_h - 2.5 * cm, brand[:40] or "Scan for offer")
    qr_size = 10 * cm
    _render_qr(c, public_url, (page_w - qr_size) / 2, page_h - 13 * cm, qr_size)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h - 14 * cm, headline)

    # Body — template-specific
    p = qr.landing_payload or {}
    body_lines = []
    if qr.landing_template == "discount":
        if p.get("terms"):
            body_lines.append(p["terms"][:80])
        if p.get("valid_until"):
            body_lines.append(f"Valid until {p['valid_until']}")
    elif qr.landing_template == "menu":
        if p.get("today_special"):
            body_lines.append(f"Today's special: {p['today_special'][:80]}")
    elif qr.landing_template == "booking":
        body_lines.append("Tap to book in seconds.")
    elif qr.landing_template == "follow":
        if p.get("instagram_handle"):
            body_lines.append(f"@{p['instagram_handle'].lstrip('@')}")
    else:
        if p.get("body"):
            body_lines.append(p["body"][:100])

    c.setFont("Helvetica", 11)
    y = page_h - 15.2 * cm
    for line in body_lines[:3]:
        c.drawCentredString(page_w / 2, y, line)
        y -= 0.7 * cm

    c.setFont("Helvetica", 7)
    c.setFillGray(0.5)
    c.drawCentredString(page_w / 2, 0.8 * cm, "Powered by Kova · kova.ai")
    c.showPage()

    c.save()
    return buf.getvalue()
