# KOVA — Financial Projections (Template)

**[COMPANY LEGAL NAME]** · [DATE] · **Plan v2 pricing**

> Populate monthly Year 1, quarterly Years 2–3 in spreadsheet. This markdown template defines assumptions — export to Excel for investor model.

---

## Pricing assumptions (Plan v2)

| Tier | KES/mo | USD/mo | Mix % (Y1 planning) |
|------|--------|--------|---------------------|
| Starter | 499 | 4 | 25% |
| Growth | 1,499 | 11 | 50% |
| Pro | 2,999 | 22 | 20% |
| Agency | 7,999 | 59 | 5% |

**Blended ARPU (planning):** KES **~1,400/month** (~USD 11)

**Trial:** 7 days, Starter limits; target trial→paid **10–15%**

---

## User growth (fill in)

| Month | New signups | Paying users | Churn % | Net paying |
|-------|-------------|--------------|---------|------------|
| M1 | [ ] | [ ] | [ ] | [ ] |
| M6 | [ ] | 150 | [ ] | [ ] |
| M12 | [ ] | 500 | [ ] | [ ] |
| M18 | [ ] | 1,000 | [ ] | [ ] |

---

## Revenue (KES)

| Line | Formula |
|------|---------|
| MRR | Paying users × blended ARPU |
| ARR | MRR × 12 |
| Partner revenue | [X]% of referred MRR — Growth Partner Program |

---

## Cost of goods sold (COGS)

| Item | Driver | Y1 estimate |
|------|--------|-------------|
| LLM (OpenRouter) | Tokens per plan caps | [ ]% of revenue |
| WhatsApp / Meta API | Pro/Agency usage | [ ] |
| Photoroom / vision | Studio polish credits | [ ] |
| Payment fees | M-Pesa + Stripe % | ~3–5% of revenue |

**Target gross margin:** 70–85% at 500+ users

---

## Operating expenses (opex)

| Category | M1–6 (USD/mo) | M7–12 | M13–18 |
|----------|---------------|-------|--------|
| Team | [ ] | [ ] | [ ] |
| Marketing | [ ] | [ ] | [ ] |
| Infrastructure | [ ] | [ ] | [ ] |
| Legal & admin | [ ] | [ ] | [ ] |

**Seed burn baseline:** see `KOVA_Use_of_Funds.md` (~USD 200K over 12–18 months)

---

## Cash flow summary

| Metric | M12 target | M18 target |
|--------|------------|------------|
| Cash balance | [ ] | [ ] |
| Monthly burn | [ ] | [ ] |
| Runway (months) | [ ] | [ ] |
| Break-even MRR | [ ] | [ ] |

---

## Scenario tabs (spreadsheet)

1. **Base** — 1,000 users @ M18  
2. **Conservative** — 50% slower acquisition, 8% monthly churn  
3. **Upside** — Partner channel 30% of signups, 5% churn  

---

## Sources

- `docs/KOVA_FINANCIAL_AUDIT.md` — cost inventory  
- `docs/KOVA_FUNDING_PLAN.md` — revenue vs burn  
- `docs/PLAN_V2_SPEC.md` — caps and metering  

---

*DRAFT — Not audited — Finance to validate before investor send*
