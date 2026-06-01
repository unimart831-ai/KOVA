# KOVA Marketing Brochures

Print-ready HTML brochures for **live demos** and **handouts to SMB owners** (Kenya / Africa).

**Brand:** Dark navy/charcoal + teal (`#00d4aa`) · professional SaaS · Inter / DM Sans.

---

## Contents

| File | Purpose | Pages |
|------|---------|-------|
| **`html/KOVA_Complete_Guide_2Page.html`** | **Premium all-in-one demo handout — every product area** | **2 × A4** |
| `html/KOVA_Product_Overview.html` | Full product + problem/solution + pricing snapshot | 2 × A4 |
| `html/KOVA_For_Business_Owners.html` | SMB benefits, use cases, getting started | 2 × A4 |
| `html/KOVA_WhatsApp_REACH_Email.html` | Three conversion pillars + plan limits | 2 × A4 |
| `html/KOVA_Plans_And_Pricing.html` | Plan v2 comparison tables | 2 × A4 |
| `html/KOVA_Snap_To_Sell_Leavebehind.html` | Half-sheet leave-behind (print 2-up) | 1 × A4 half |

Shared styles: `assets/brochure-base.css` · premium 2-pager: `assets/brochure-master.css` · optional icons: `assets/icons.svg`.

---

## Preview (browser)

Open any HTML file locally (double-click or):

```powershell
cd a:\SYSTEMS_2026\SOCIAL_FUTURE\kova_agent\marketing\brochures\html
start KOVA_Product_Overview.html
```

Use **Print → Save as PDF** (Chrome/Edge) as a fallback if the build script cannot run. Enable **Background graphics** for gradients.

---

## Generate PDFs

From `kova_agent/` root:

```powershell
pip install xhtml2pdf
# Optional (better rendering): pip install weasyprint
python marketing/brochures/scripts/build_brochure_pdfs.py
```

Output: `marketing/brochures/pdf/*.pdf` (6 files when all HTML sources build).

**Backends** (script tries in order):

1. **xhtml2pdf** — `pip install xhtml2pdf` (Windows-friendly; CSS inlined automatically)
2. **WeasyPrint** — `pip install weasyprint` (GTK required on Windows; best gradients)

Same pattern as `fundraising/scripts/build_pdfs.py`.

### Best-quality PDF for Complete Guide

`KOVA_Complete_Guide_2Page.html` uses CSS Grid, gradients, and geometric patterns. **xhtml2pdf may degrade layout** (grid collapse, missing gradients). For premium print runs:

1. Open `html/KOVA_Complete_Guide_2Page.html` in Chrome or Edge
2. **Print → Save as PDF** — enable **Background graphics**
3. Paper: A4 portrait, margins Default or None

Use the build-script PDF for quick sharing; use browser Print → PDF for demo handouts.

---

## Print tips

- Paper: **A4** portrait, double-sided for 2-page brochures
- Margins: `@page` 10mm (base brochures) · 12mm (`KOVA_Complete_Guide_2Page`)
- Tri-fold guides: faint panel lines on screen only (`.no-print`)
- Leave-behind: print `KOVA_Snap_To_Sell_Leavebehind.html` — 2 copies per sheet, cut horizontally
- QR placeholders: replace `[QR: kova.page]` with real QR art before mass print

---

## Copy sources

- `fundraising/05-fundraising/KOVA_One_Pager.md`, Executive Summary
- `docs/KOVA_PLANS_GUIDE.md` / Plan v2 (499 / 1499 / 2999 / 7999 KES)
- `docs/KOVA_USER_GUIDE_WHATSAPP_REACH_EMAIL.md`
- `docs/KOVA_BUSINESS_PROPOSAL.md`

Contact placeholders: `hello@kova.page`, `+254 XXX XXX XXX`.

**Disclaimer:** Pricing subject to change; see kova.page.

---

## Contact & footer

All brochures include: **kova.page** · hello@kova.page · Kenya-first · M-Pesa · WhatsApp Business
