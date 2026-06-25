# KOVA — Investor FAQ

**[COMPANY LEGAL NAME]** · Confidential · [DATE]

Frequently asked questions for angels, Africa-focused VCs, accelerators, and strategic partners. Figures align with **Kova** pricing (KES 1,300/mo) unless noted.

---

## 1. What is KOVA in one sentence?

KOVA is a **Business Intelligence Operating System** — six AI agents plus conversion tools (links, leads, email, WhatsApp) that run an SME's digital marketing for **KES 1,300/month**, with **M-Pesa** billing.

---

## 2. Is the product built or still an MVP?

**Built and live.** Production deployment on Railway with 16 Django modules, 6 agents, 12+ Celery tasks, 9 social integrations, dual billing (M-Pesa + Stripe), partner program, and legal pages. Estimated agency-equivalent build value: **USD 159,000–245,000**. The seed round funds **growth**, not greenfield development.

---

## 3. What are you raising and on what terms?

| Item | Current draft position |
|------|------------------------|
| Amount | **USD 150,000–300,000** (baseline planning at ~USD 200,000) |
| Stage | Seed |
| Instrument | **[SAFE / priced equity / note — TBD with counsel]** |
| Valuation | **[PRE-MONEY VALUATION — TBD]** |
| Option pool | **[X]%** post-money (typical 10–15% — counsel to confirm) |

Term sheet and SHA are **Tier 2** documents — not included in this draft pack.

---

## 4. How will you use the funds?

See `KOVA_Use_of_Funds.md`. Summary at ~USD 200K baseline:

- **40%** — Team (2–3 hires, 12 months)  
- **25%** — Marketing, GTM, Growth Partner activation  
- **15%** — LLM and API costs at 1,000-user scale  
- **10%** — Infrastructure, security, tooling  
- **10%** — Legal, compliance, ODPC, buffer  

---

## 5. What is your pricing and why will SMEs pay?

**Kova plan (June 2026):**

| Tier | KES/mo | USD/mo |
|------|--------|--------|
| **Kova** | **1,300** | **10** |
| Agency | 7,999 | 59 |

**Trial:** 7 days, Kova limits, 5 campaigns.

**Value anchor:** A part-time social manager costs **KES 30,000+/month**; Western tool stacks often exceed **USD 50–200/month** without AI or conversion. KOVA replaces multiple tools at African price points with local payment rails.

---

## 6. What traction do you have today?

- Production platform with verified publishing on Meta properties  
- **14 TEST_BUSINESSES** — structured end-to-end pilot matrix (e-commerce, agency, food, SaaS, real estate, NGO, fintech, education)  
- **Unimart Africa** — founder-operated first customer narrative  
- Growth Partner Program **built** (activation capital in seed budget)  
- Current infrastructure burn ~**KES 3,500–4,500/month** pre-scale  

Update specific user/revenue counts in `[METRICS AS OF DATE]` before each investor meeting.

---

## 7. Who is the customer?

**Primary ICP:** Kenyan SMEs and solopreneurs who depend on social for discovery but cannot hire a marketing team.

**Secondary:** Creative/marketing agencies (Agency tier), NGOs, campus commerce and fintech (Kova plan).

Beachhead playbook: `docs/FIRST_50_CUSTOMERS_PLAYBOOK.md`.

---

## 8. How big is the market?

- **44M+** African MSMEs  
- **~$4.6B** TAM (social + marketing SaaS for SMEs)  
- **SAM:** Digitally active SMEs in Kenya/East Africa  
- **18-month SOM target:** 1,000 paying users in Kenya

---

## 9. Who are competitors and why do you win?

| Competitor type | Limitation | KOVA advantage |
|-----------------|------------|----------------|
| Schedulers (Buffer, etc.) | No AI loop, Western pricing | Full BIOS + M-Pesa |
| AI writers | No publish/engage/CRM | End-to-end execution |
| Agencies | High cost, not scalable | 10–50× cheaper |
| Global suites (HubSpot, etc.) | Price + context mismatch | Built in Nairobi for Africa |

**Moat:** Content DNA compounding, provider abstraction, founder-operator insight, partner distribution.

---

## 10. What is the technology stack and security posture?

- **Stack:** Django, Celery, PostgreSQL, Redis, HTMX, Tailwind, Railway  
- **AI:** OpenRouter LLMs with per-plan token budgets (daily + monthly caps)  
- **Media:** Cloudflare R2  
- **Auth:** OAuth social login, encrypted token storage, RBAC for teams  
- **Resilience:** 3-strike recovery, auto token refresh — see `docs/PLATFORM_RESILIENCE.md`  
- **Safety:** `docs/CONTENT_SAFETY.md`

---

## 11. How do you handle Meta, WhatsApp, and platform risk?

- **Provider abstraction** — one module per platform; API changes isolated  
- **9-platform diversification** — no single-platform dependency  
- **Compliance pack:** Meta app review, WhatsApp Business policies, data deletion URL live  
- **Human-in-the-loop** default for publishing and replies

---

## 12. How does M-Pesa work and when do you go live?

M-Pesa STK Push integration is **built**; production go-live follows Safaricom merchant onboarding (`docs/MPESA_SETUP.md`). Seed allocation includes M-Pesa production fees and compliance.

---

## 13. What about data protection (Kenya)?

- Live Privacy Policy, Terms, DPA template on platform  
- **Data Protection Act 2019** — ODPC registration path in seed legal budget  
- DPIA summary for AI + OAuth data — Tier 2  
- Customer data not used to train third-party LLMs (per policy)

---

## 14. Who owns the IP?

All founder-built code, docs, and brand assets should transfer to **[COMPANY LEGAL NAME]** via **IP Assignment Deed** (`02-legal/KOVA_IP_Assignment_TEMPLATE.md`) — advocate execution required before close.

---

## 15. What is the cap table today?

See `03-financial/KOVA_Cap_Table_TEMPLATE.csv`. Current draft assumes **[FOUNDER 1]% / [FOUNDER 2]%** with **[OPTION POOL %]** reserved. Pro forma post-money to be modeled at term sheet.

---

## 16. Is there a co-founder? How is governance handled?

- **[DESCRIBE CURRENT FOUNDER STRUCTURE]**  
- **Founders Agreement** template covers equity, **4-year vesting / 1-year cliff**, roles, reserved matters, Nairobi dispute resolution  
- Board structure post-seed: **[TBD — typically 3 seats: 2 founders + 1 investor observer]**

---

## 17. What are unit economics assumptions?

| Metric | Planning assumption (validate in model) |
|--------|----------------------------------------|
| Blended ARPU | KES ~1,300/mo (Kova plan) |
| Gross margin | 70–85% at scale (LLM largest COGS) |
| CAC (founder-led) | Low in Year 1; rises with paid GTM |
| Payback | <6 months target on Kova plan |
| Churn | **[X]% monthly — measure from pilot]** |

Full model: `03-financial/KOVA_Financial_Projections_TEMPLATE.md`, `docs/KOVA_FINANCIAL_AUDIT.md`.

---

## 18. What is the path to 1,000 users?

1. Complete 14-business pilot → public case studies  
2. Activate 50+ Growth Partners  
3. Hire Growth Lead post-close  
4. WhatsApp + Facebook SME campaigns  
5. Incubator and university partnerships  

Timeline: **[TARGET DATE — e.g. Q2 2027]**

---

## 19. Why Kenya first?

- Founder network and M-Pesa infrastructure  
- English + Swahili market testing  
- Regulatory familiarity (BRS, KRA, ODPC)  
- Expansion to Nigeria/SA after Kenya PMF (bridge round)

---

## 20. Are you also pursuing grants?

**Yes, parallel track optional.** Theory of change and impact metrics align with SDG 8/9/10. Template: `06-grants/KOVA_Grant_Impact_Narrative_TEMPLATE.md`. Grant budget can overlap seed GTM — disclose double-funding risk to all funders.

---

## 21. What could kill the company?

| Risk | Mitigation |
|------|------------|
| Platform API shutdown | Multi-platform + abstraction + resilience |
| AI harm/off-brand content | Safety filters, approval flows |
| Slow paid conversion | Pilot proof, partner channel, pricing trials |
| Founder burnout | Seed hires, vesting alignment |
| Regulatory | Advocate-reviewed policies, ODPC registration |

---

## 22. What do you need from investors beyond capital?

- Introductions to **Africa-focused angels and VCs**  
- **Grant** and accelerator program intros (Mastercard Foundation ecosystem, etc.)  
- **Enterprise pilot** intros (banks, telcos, MSME associations)  
- Governance and **financial controls** best practices

---

## 23. How do I get more detail?

1. Sign **Mutual NDA** (`02-legal/KOVA_Mutual_NDA_TEMPLATE.md`)  
2. Request data room access per `KOVA_Data_Room_Index.md`  
3. Schedule live demo: **[DEMO URL / CALENDAR LINK]**

---

*DRAFT FOR DISCUSSION — NOT LEGAL OR INVESTMENT ADVICE — UPDATE METRICS BEFORE EACH SEND*
