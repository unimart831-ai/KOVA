# KOVA — Fundraising & Legal Drafts

**Version:** 1.0 · **June 2026**  
**Status:** Drafts for founder review — not executed legal documents

---

## Disclaimer

These materials are **drafts for discussion only**. They are **not legal, tax, or investment advice**. All contracts, filings, and investor communications must be reviewed by qualified **Kenyan advocate**, CPA, and investor counsel before signing or distribution.

---

## Folder structure

| Folder | Contents |
|--------|----------|
| `01-corporate/` | Incorporation placeholders (CR12, resolutions) — populate after BRS registration |
| `02-legal/` | Founders agreement, IP assignment, NDA templates; policy drafts |
| `03-financial/` | Cap table template, financial projections template |
| `04-commercial/` | Pricing reference (Plan v2) — see `docs/PLAN_V2_SPEC.md` |
| `05-fundraising/` | Executive summary, one-pager, pitch deck, investor FAQ, use of funds, data room index |
| `06-grants/` | Grant impact narrative template |
| `pdf/` | Generated PDFs (mirror of markdown sources) |
| `scripts/` | PDF build tooling |

---

## Tier 1 documents (draft complete)

| Document | Path |
|----------|------|
| Executive Summary | `05-fundraising/KOVA_Executive_Summary.md` |
| One-Pager | `05-fundraising/KOVA_One_Pager.md` |
| Pitch Deck (slides) | `05-fundraising/KOVA_Pitch_Deck.md` |
| Investor FAQ | `05-fundraising/KOVA_Investor_FAQ.md` |
| Use of Funds | `05-fundraising/KOVA_Use_of_Funds.md` |
| Data Room Index | `05-fundraising/KOVA_Data_Room_Index.md` |
| Founders Agreement (template) | `02-legal/KOVA_Founders_Agreement_TEMPLATE.md` |
| IP Assignment (template) | `02-legal/KOVA_IP_Assignment_TEMPLATE.md` |
| Mutual NDA (template) | `02-legal/KOVA_Mutual_NDA_TEMPLATE.md` |
| Cap Table (template) | `03-financial/KOVA_Cap_Table_TEMPLATE.csv` |

---

## Pricing source of truth (Plan v2)

All fundraising drafts use **Plan v2** pricing (May 2026):

| Tier | KES/mo | USD/mo |
|------|--------|--------|
| Starter (Jipange) | 499 | 4 |
| Growth (Kazi) | 1,499 | 11 |
| Pro (Biashara) | 2,999 | 22 |
| Agency (Wakala) | 7,999 | 59 |

Authoritative spec: `docs/PLAN_V2_SPEC.md`, `apps/billing/models.py`.

---

## How to regenerate PDFs

From the repository root (`kova_agent/`):

```bash
pip install markdown weasyprint
python fundraising/scripts/build_pdfs.py
```

**Fallbacks** (script tries in order):

1. **WeasyPrint** — `pip install markdown weasyprint` (requires GTK on Windows)
2. **Pandoc** — `pandoc input.md -o output.pdf`
3. **mdpdf** — `pip install mdpdf`
4. **xhtml2pdf** — `pip install markdown xhtml2pdf` (works on Windows without GTK)

PDFs are written to `fundraising/pdf/` with the same relative paths as source `.md` files (CSV sources are skipped).

On Windows PowerShell:

```powershell
python fundraising/scripts/build_pdfs.py
```

---

## Related internal docs

- [KOVA Fundraising & Legal Document Checklist](../docs/KOVA_FUNDRAISING_AND_LEGAL_DOCUMENT_CHECKLIST.md)
- [KOVA Business Proposal](../docs/KOVA_BUSINESS_PROPOSAL.md)
- [KOVA Funding Plan](../docs/KOVA_FUNDING_PLAN.md)
- [KOVA Founder Pitch](../docs/KOVA_FOUNDER_PITCH.md)
- [Plan v2 Spec](../docs/PLAN_V2_SPEC.md)

---

*Maintained by KOVA founding team. Advocate review required before signing any legal template.*
