# KOVA — Use of Funds

**[COMPANY LEGAL NAME]** · Seed Round · [DATE]  
**Confidential — for qualified investors under NDA**

---

## Funding overview

| Item | Detail |
|------|--------|
| **Round** | Seed |
| **Target raise** | USD **150,000 – 300,000** |
| **Planning baseline** | USD **200,000** |
| **Runway** | **12–18 months** |
| **Primary goal** | **1,000 paying users** in Kenya; revenue-generating; regional expansion groundwork |
| **Instrument** | **[SAFE / Priced equity / Convertible note — TBD]** |

**Context:** Product is fully built (estimated USD 159K–245K sweat-equity value). Capital deploys to **team, GTM, AI scale, and compliance** — not core product construction.

---

## Why this amount

| Consideration | Rationale |
|---------------|-----------|
| **USD 150K minimum** | 12 months: 2 hires + infra + marketing + partner activation |
| **USD 300K ideal** | 18-month runway: 3 hires + aggressive GTM + Nigeria/SA prep |
| **Not >USD 300K at this stage** | Product exists; over-raising pre-PMF creates valuation pressure |
| **Not <USD 100K** | Cannot hire; marketing too thin; founder-only bottleneck |

---

## Allocation — USD 200,000 baseline

| Category | % | USD | KES (approx.) | Purpose |
|----------|---|-----|---------------|---------|
| **Team & talent** | 40% | 80,000 | 10.4M | Growth Lead, Customer Success, part-time design/content; payroll taxes |
| **Marketing & GTM** | 25% | 50,000 | 6.5M | Paid social, WhatsApp campaigns, events, partner program incentives, pilot LOIs |
| **LLM & API costs** | 15% | 30,000 | 3.9M | OpenRouter + platform APIs at ~1,000 users; Photoroom studio credits |
| **Infrastructure & tools** | 10% | 20,000 | 2.6M | Railway scale-up, R2, monitoring, security tooling, domains |
| **Legal, compliance, admin** | 10% | 20,000 | 2.6M | Incorporation, founders/IP docs, ODPC, Meta review, accounting, buffer |
| **Total** | 100% | **200,000** | **~26M** | |

*Exchange rate for planning: **[USD/KES RATE]** — update at close.*

---

## Team & talent (40% — USD 80,000)

| Role | Timing | Annual cost (planning) | Notes |
|------|--------|------------------------|-------|
| Growth Lead | Month 1–2 | ~USD 24–30K | GTM, partnerships, partner program |
| Customer Success | Month 3–4 | ~USD 18–24K | Onboarding, pilot support, retention |
| Contract design/content | As needed | ~USD 8–12K | Case studies, deck, ads |
| Founder salary | Minimal | ~USD 12–18K | Stipend only — majority to hires |

**Outcome:** Founder shifts from solo build to **growth + customer success** leadership.

---

## Marketing & GTM (25% — USD 50,000)

| Line item | Budget (USD) | Purpose |
|-----------|--------------|---------|
| Performance ads (Meta, TikTok) | 18,000 | SME targeting — Nairobi + secondary cities |
| WhatsApp / SMS campaigns | 8,000 | Kova-tier funnel; salon, food, retail verticals |
| Partner program activation | 10,000 | Commissions, onboarding kits, partner events |
| Events & incubators | 6,000 | Demo days, university partnerships |
| Pilot incentives & LOIs | 8,000 | 14 TEST_BUSINESSES → 3–5 public case studies |

**KPI:** CAC payback <6 months on Kova plan (KES 1,300/mo).

---

## LLM & API costs (15% — USD 30,000)

Scaled for **~1,000 users** on the Kova plan:

| Tier | Monthly LLM cap (planning) |
|------|---------------------------|
| Kova | 5M tokens |
| Agency | 40M tokens |

Includes OpenRouter inference, vision analysis, WhatsApp template costs, and Photoroom studio polish pool. **Metering enforced** in `apps/agents/budget.py`.

---

## Infrastructure & tools (10% — USD 20,000)

| Service | Notes |
|---------|-------|
| Railway (Web, Worker, Beat, Redis, Postgres) | Scale from ~USD 30/mo to ~USD 500–1,500/mo at 1K users |
| Cloudflare R2 | Media storage growth |
| Resend | Email volume past free tier |
| Monitoring & backups | Uptime, error tracking |
| Domains & SSL | Primary + marketing domains |

Current pre-scale burn: **~USD 28–36/month** (~KES 3,500–4,500).

---

## Legal, compliance & admin (10% — USD 20,000)

| Item | Est. (USD) |
|------|------------|
| Kenya incorporation + BRS fees | 2,000 |
| Advocate — founders agreement, IP, SHA prep | 8,000 |
| ODPC registration + DPIA support | 2,000 |
| Meta app review / business verification | 1,500 |
| M-Pesa production go-live | 1,000 |
| Accounting & tax (KRA) | 3,000 |
| Contingency | 2,500 |

---

## Milestone-linked view (optional tranches)

| Milestone | % release | Evidence |
|-----------|-----------|----------|
| Close + incorporation complete | 30% | Cert of incorporation, bank account |
| 100 paying users | 30% | Billing export, churn report |
| 500 paying users + 25 active partners | 25% | Partner dashboard, case studies |
| 1,000 paying users | 15% | Management accounts, board report |

*Tranche structure subject to investor negotiation.*

---

## Revenue vs burn (summary)

| Period | Paying users (target) | MRR (planning, blended KES 1,400) | Monthly burn (est.) |
|--------|----------------------|-------------------------------------|---------------------|
| Month 6 | 150 | ~KES 210K | ~KES 1.5M |
| Month 12 | 500 | ~KES 700K | ~KES 2.0M |
| Month 18 | 1,000 | ~KES 1.4M | ~KES 2.2M |

Detailed model: `03-financial/KOVA_Financial_Projections_TEMPLATE.md`.

---

## What we will not fund with seed capital

- Greenfield product rebuild (already complete)  
- Large office lease or hardware capex  
- Unrelated ventures or founder personal expenses (beyond modest stipend)  
- Unapproved related-party transactions

---

## Reporting to investors

- **Monthly:** KPI email (users, MRR, churn, burn, cash)  
- **Quarterly:** Board-style update + cap table confirmation  
- **Annual:** Management accounts; path to audited statements when material

---

*Source: adapted from `docs/KOVA_FUNDING_PLAN.md` · Kova KES 1,300 pricing · DRAFT — verify with finance before investor distribution*
