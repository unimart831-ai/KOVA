# KOVA — Fundraising & Legal Document Checklist

**Version:** 1.0 · **June 2026**  
**Audience:** Founders, legal counsel, finance, and grant applicants  
**Scope:** Pre-seed / seed / grant readiness for KOVA (Kenya-incorporated SaaS, Africa-first, international investor–eligible)

---

> **Disclaimer — not legal, tax, or investment advice**  
> This checklist is an operational planning tool for KOVA founders and advisors. It is **not** legal advice, tax advice, or a substitute for qualified Kenyan counsel (advocate), a licensed CPA/auditor, or investor counsel. All contracts, filings, and regulatory interpretations must be reviewed by professionals before signing or submission. Laws and funder requirements change — verify against current Kenya **Companies Act 2015**, **Data Protection Act 2019**, **BRS eCitizen** processes, and each investor/grantor's application pack.

---

## 1. Executive Summary — How to Use This Checklist

KOVA is entering a fundraising phase targeting **angel investors, African and diaspora VCs, accelerators, corporate venture, and grant programs** (Mastercard Foundation ecosystem, USAID/Digital Frontiers-style programs, local innovation funds, university incubators, and SDG-aligned foundations).

**Draft pack (Tier 1):** Working copies of executive summary, one-pager, pitch deck, investor FAQ, use of funds, data room index, founders/IP/NDA templates, and cap table CSV live in **[`fundraising/README.md`](../fundraising/README.md)** with PDF export via `python fundraising/scripts/build_pdfs.py`.

This document lists **every document category** you are likely to need — from first coffee chat through term sheet, close, and grant compliance. Items are tiered so you can prioritize under time pressure.

### How to work the list

1. **Assign an owner** to every Tier 1 item this week (Founder / Legal / Finance / Product).
2. **Mark status** in the [Status Tracker](#10-status-tracker-optional) at the bottom (Not started → Draft → Review → Final).
3. **Build the data room early** — even a Google Drive folder with the [suggested structure](#6-data-room-folder-structure) beats sending attachments ad hoc.
4. **Adapt before rewriting** — several strong internal docs already exist (see [§8 KOVA-specific pointers](#8-kova-specific-pointers--existing-docs-to-adapt)).
5. **Kenya + international dual track** — local investors and grants often want **BRS certificates and KRA PIN**; international angels/VCs want **English-law–style SHA, cap table, and clean IP chain**. Prepare both narratives in one data room.

### Context: what investors and grantors actually ask first

| Stakeholder | First 3 questions | Documents that answer them |
|-------------|-------------------|----------------------------|
| Angel / pre-seed | Why you? Why now? What exists? | Pitch deck, one-pager, demo, founder story |
| Seed VC | Cap table clean? IP owned? Unit economics? | SHA draft, IP assignments, financial model, `KOVA_FINANCIAL_AUDIT.md` |
| Accelerator | Traction? Team gaps? 12-week plan? | Pipeline, TEST_BUSINESSES pilots, hiring plan |
| Grant panel | Theory of change? Beneficiaries? M&E? | Impact narrative, budget, letters of support |
| Corporate / strategic | Risk? Compliance? Integration? | Platform resilience, content safety, Meta/WhatsApp policies |

---

## 2. Tier 1 — Must-Have Before First Investor / Grant Conversation

Complete these **before** sending a deck, applying to an accelerator, or accepting a diligence call.

| # | Document | Why | Owner |
|---|----------|-----|-------|
| 1 | **Elevator pitch + 90-second script** | First impression; aligns team messaging | Founder |
| 2 | **One-pager (PDF, 1 page)** | Forwardable; used in warm intros | Founder |
| 3 | **Pitch deck (10–15 slides)** | Standard for meetings and competitions | Founder |
| 4 | **Executive summary (2–3 pages)** | Pre-read for busy partners | Founder |
| 5 | **Company registration proof** (Certificate of Incorporation, CR12 if applicable) | Proves legal entity; required for contracts and grants | Legal / Founder |
| 6 | **KRA PIN certificate** (company) | Tax identity; payroll, invoicing, grant reporting | Finance |
| 7 | **Cap table (current, fully diluted)** | Every serious investor asks on call #1 | Founder / Finance |
| 8 | **Founders agreement** (or sole-founder governance memo if solo) | Clarifies equity, roles, vesting, IP | Legal |
| 9 | **IP assignment** (founder → company) | Company must own code and brand | Legal |
| 10 | **Privacy policy + Terms** (live URLs) | Platform trust; Meta/TikTok review requirement | Founder / Legal |
| 11 | **Data Protection Act 2019 compliance baseline** (ODPC registration if processing personal data at scale) | Kenya legal requirement for SaaS | Legal |
| 12 | **Use of funds + raise amount** (single page) | "What will you do with $X?" | Finance |
| 13 | **Product demo / live environment** | KOVA is built — show it | Founder / Product |
| 14 | **NDA template** (mutual, short form) | For sharing detailed financials | Legal |

### Tier 1 checklists by category

#### Corporate & legal (Tier 1)

- [ ] **Certificate of Incorporation** (BRS / eCitizen) — *New draft; referenced in seed proposals as planned*
- [ ] **CR12** (list of directors & shareholders) — *New; obtain from BRS after incorporation*
- [ ] **Memorandum & Articles of Association** (or Model Articles adoption) — *New*
- [ ] **Board / shareholder resolutions** (authorize fundraising, signatory powers) — *New*
- [ ] **Company KRA PIN** — *New*
- [ ] **Founders agreement** (equity split, roles, vesting, cliff, good/bad leaver, decision rights) — *New; advocate-reviewed*
- [ ] **IP assignment deed** (all code, docs, domains, social handles → company) — *New*
- [ ] **Trademark search + application** (KOVA name/logo in relevant classes) — *New*
- [ ] **Domain ownership record** (registrar account in company name) — *Verify*
- [ ] **Mutual NDA template** — *New*
- [ ] **Privacy Policy** (live) — **Adapt from:** `templates/pages/privacy.html` (deployed at `/privacy/`)
- [ ] **Terms of Service** (live) — **Adapt from:** `templates/pages/terms.html`
- [ ] **Cookie Policy** — **Adapt from:** `templates/pages/cookies.html`
- [ ] **Acceptable Use Policy** — **Adapt from:** `templates/pages/acceptable_use.html`
- [ ] **Data Processing Agreement (DPA)** template for B2B customers — **Adapt from:** `templates/pages/dpa.html`
- [ ] **Meta Data Deletion Instructions** — **Exists:** `templates/pages/facebook_data_deletion.html`
- [ ] **ODPC registration** (Office of the Data Protection Commissioner) if required for your processing volume — *New; legal review*
- [ ] **Data Protection Impact Assessment (DPIA)** summary for AI + social OAuth data — *New*

#### Financial (Tier 1)

- [ ] **Funding ask one-pager** (amount, instrument, runway months) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md` §Funding Overview
- [ ] **Use of funds table** (personnel, infra, GTM, legal, buffer) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md` §Detailed Seed Round Allocation
- [ ] **3-year financial model** (monthly Y1, quarterly Y2–Y3) — *New spreadsheet; align pricing with Plan v2*
- [ ] **Unit economics summary** (CAC assumptions, ARPU, gross margin, payback) — **Adapt from:** `docs/KOVA_FINANCIAL_AUDIT.md`, `docs/KOVA_BUSINESS_PROPOSAL.md` §Unit Economics
- [ ] **Current burn rate** (monthly opex) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md` §Current Operating Costs
- [ ] **Cap table** (founder shares, options pool, any SAFEs/notes) — *New*
- [ ] **Bank account** in company name + **3–6 months statements** — *New account post-incorporation*

#### Product & tech (Tier 1)

- [ ] **Architecture overview** (1–2 pages + diagram) — **Adapt from:** `docs/system-maps/SYSTEM_AUDIT_AND_FLOWS.md`, `docs/KOVA_BUSINESS_PROPOSAL.md` §Technology
- [ ] **Product screenshots / 2-min demo video** — *New recording*
- [ ] **Security overview** (auth, encryption at rest, secrets, RBAC) — *New; pull from production settings*
- [ ] **Third-party dependency list** (Meta, OpenRouter, Railway, M-Pesa, Stripe, Resend, R2) — **Adapt from:** `docs/KOVA_PLATFORM_SETUP_GUIDE.md`, `docs/KOVA_FINANCIAL_AUDIT.md` §Cost Inventory
- [ ] **Content safety policy** — **Adapt from:** `docs/CONTENT_SAFETY.md`
- [ ] **Platform resilience / risk summary** — **Adapt from:** `docs/PLATFORM_RESILIENCE.md`

#### Commercial (Tier 1)

- [ ] **Pricing & packaging** (aligned to Plan v2) — **Adapt from:** `docs/KOVA_PLANS_GUIDE.md`, `docs/PLAN_V2_SPEC.md`
- [ ] **ICP + beachhead segment definition** — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md` §Market, `docs/FIRST_50_CUSTOMERS_PLAYBOOK.md`
- [ ] **Go-to-market one-pager** — **Adapt from:** `docs/FIRST_50_CUSTOMERS_PLAYBOOK.md`, `docs/KOVA_BUSINESS_PROPOSAL.md` §GTM
- [ ] **Pipeline / waitlist metrics** (even if early) — *New export from admin*
- [ ] **Pilot plan (TEST_BUSINESSES)** — **Adapt from:** `docs/TEST_BUSINESSES.md` (executive summary + 3–5 priority pilots)

#### Fundraising-specific (Tier 1)

- [ ] **Pitch deck (10–15 slides)** — *New slides; narrative from* `docs/KOVA_FOUNDER_PITCH.md`
- [ ] **One-pager PDF** — *New; distill from* `docs/KOVA_BUSINESS_PROPOSAL.md` executive summary
- [ ] **Executive summary (2–3 pp)** — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md` §Executive Summary
- [ ] **Investor FAQ** (10–20 Q&A) — *New; seed from objections in* `docs/KOVA_BUSINESS_PROPOSAL.md` §Risk
- [ ] **Data room index** (table of contents with links) — *New; use §6 structure below*
- [ ] **Cap table pro forma** (post-money at target raise) — *New spreadsheet*

#### Grants (Tier 1 — if applying in parallel)

- [ ] **Organization registration certificates** (incorporation + PIN) — *Same as corporate Tier 1*
- [ ] **Theory of change (1 page)** — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md` §Social Impact & SDG Alignment
- [ ] **Impact metrics framework** (outputs, outcomes, SDG mapping) — *New M&E sheet*
- [ ] **Grant budget narrative** (line items tied to milestones) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md`
- [ ] **Founder CV / bios** — *New formal CVs*
- [ ] **Letters of intent / support** (2–3 partners, MSME associations, incubators) — *New outreach*

#### Compliance & risk (Tier 1)

- [ ] **Meta / WhatsApp partner policy compliance checklist** — **Adapt from:** `docs/KOVA_PLATFORM_SETUP_GUIDE.md` §Legal, `docs/WHATSAPP_STRATEGY_AND_AUDIT.md`
- [ ] **M-Pesa merchant / Paybill compliance notes** — **Adapt from:** `docs/MPESA_SETUP.md` §Go Live
- [ ] **PCI scope memo** (Stripe handles card data; document SAQ-A posture) — *New short memo*
- [ ] **AI / automated decision-making disclosure** (for privacy policy + grant ethics) — *New paragraph for legal pages*

---

## 3. Tier 2 — Required to Close Funding or Grants

These items move from draft to **signed / audited / submitted** between **term sheet** and **money in bank** (or grant award letter).

### Investment close track

| Phase | Documents |
|-------|-----------|
| Term sheet signed | Term sheet, exclusivity (if any), disclosure schedule list |
| Due diligence | Full data room, Q&A log, customer references, tech DD responses |
| Definitive docs | SHA, subscription agreement / stock purchase, board consents, updated AoA (if needed) |
| Post-close | Cap table update, investor reporting cadence, bank KYC for new signatories |

#### Corporate & legal (Tier 2)

- [ ] **Shareholders Agreement (SHA)** — rights, drag/tag, ROFR, board seats, information rights — *New; Kenyan + investor counsel*
- [ ] **Articles of Association amendment** (if investor share classes needed) — *New*
- [ ] **Board composition & charter** — *New*
- [ ] **Director & officer (D&O) indemnities** — *New*
- [ ] **Employee IP assignment + confidentiality** (template for all hires) — *New*
- [ ] **Contractor / consultant agreements** (work-for-hire, IP clause) — *New*
- [ ] **Option / ESOP plan** + **option grant templates** — *New*
- [ ] **409A-style valuation** or **Kenya equivalent fair market value memo** for options — *New*
- [ ] **Material contracts register** (Railway, OpenRouter, Resend, domain, any >$5k/yr) — *New register*
- [ ] **Litigation / claims disclosure** (nil or listed) — *New certificate*
- [ ] **Regulatory licenses** (if any sector-specific; generally not for pure SaaS) — *Confirm with counsel*
- [ ] **VAT registration** (if turnover exceeds threshold or required by customers) — *Finance + KRA*
- [ ] **Withholding tax guidance** for cross-border investor payments — *Tax advisor*

#### Financial (Tier 2)

- [ ] **Audited or reviewed financial statements** (if prior year revenue) — *New; CPA engagement*
- [ ] **Management accounts** (monthly P&L, balance sheet, cash flow) — *New*
- [ ] **Detailed financial model** (sensitivity cases: base / upside / downside) — *Extend Tier 1 model*
- [ ] **Historical bank statements** (12 months) — *Post-incorporation*
- [ ] **Tax compliance certificate** (if available / required) — *KRA*
- [ ] **Payroll records** (PAYE, NHIF/NSSF if employees) — *Finance*
- [ ] **Insurance** (cyber, D&O if board/investors require) — *New*
- [ ] **Financial controls memo** — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md` §Financial Controls & Governance

#### Product & tech (Tier 2)

- [ ] **Technical due diligence pack** (architecture, scalability, backup/DR) — **Adapt from:** `docs/PLATFORM_RESILIENCE.md`, `docs/KOVA_PLATFORM_SETUP_GUIDE.md`
- [ ] **Open-source license inventory** (SBOM or pip/npm audit) — *New export*
- [ ] **Penetration test or vulnerability assessment summary** — *New (lightweight acceptable at seed)*
- [ ] **Incident response plan** — *New*
- [ ] **Business continuity / disaster recovery** (Railway, DB backups, R2) — *New 2-page doc*
- [ ] **Subprocessor list** (for DPA and GDPR-style requests) — *New table*
- [ ] **WhatsApp / Meta Business verification evidence** — **Adapt from:** `docs/WHATSAPP_SETUP_GUIDE.md`, platform admin screenshots

#### Commercial (Tier 2)

- [ ] **Customer contracts / MSAs** (standard B2B terms) — *New template*
- [ ] **LOIs or pilot agreements** (TEST_BUSINESSES partners) — *New signed letters*
- [ ] **Case studies** (2–3, even beta) — *New; Unimart / pilot narratives*
- [ ] **Pricing approval memo** (Plan v2 locked for 12 months) — **Adapt from:** `docs/PLAN_V2_SPEC.md`
- [ ] **Partnership agreements** (Growth Partners, UNIMART, agencies) — **Adapt from:** `docs/GROWTH_PARTNERS_PROGRAM.md`, `docs/UNIMART_VENDOR_ONBOARDING.md`
- [ ] **Churn & retention cohort data** — *New analytics export*
- [ ] **Sales pipeline CRM export** — *New*

#### Fundraising-specific (Tier 2)

- [ ] **Signed term sheet** — *New*
- [ ] **Disclosure schedules** (IP, contracts, litigation, cap table, key persons) — *New*
- [ ] **Investor side letter** (if any special terms) — *New*
- [ ] **Wire instructions + bank KYC pack** — *Finance*
- [ ] **Post-money cap table** (signed by all shareholders) — *New*
- [ ] **Reporting template** (monthly investor update: KPIs, burn, asks) — *New*
- [ ] **Pro forma cap table** (multiple scenarios: $150k / $300k / bridge) — *Extend Tier 1*

#### Grants (Tier 2)

- [ ] **Full grant application** (narrative + budget + logframe) — **Adapt from:** `docs/KOVA_BIOS_SEED_PROPOSAL_FINAL.md`
- [ ] **Detailed budget** (USD + KES, FX assumptions) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md`
- [ ] **Monitoring & evaluation plan** (indicators, data collection, reporting calendar) — *New*
- [ ] **Gender / youth / disability inclusion plan** (if funder requires) — *New*
- [ ] **Environmental & social safeguards** (if required) — *New*
- [ ] **Signed letters of support** (MSME associations, universities, county gov) — *New*
- [ ] **Beneficiary selection criteria** (for subsidized access programs) — *New*
- [ ] **Grant compliance manual** (spending rules, reporting, audit trail) — *New*
- [ ] **Bank details + signatory mandate** for grant disbursement — *Finance*

#### Compliance & risk (Tier 2)

- [ ] **ODPC registration certificate** (if not completed in Tier 1) — *Legal*
- [ ] **Records of processing activities (ROPA)** — *Legal / Product*
- [ ] **Data breach notification procedure** — *New*
- [ ] **Meta App Review approval evidence** (production permissions) — **Adapt from:** `docs/platform-audits/FACEBOOK.md`, setup guide checklists
- [ ] **WhatsApp Business API compliance** (opt-in, template approval, pricing disclosure) — **Adapt from:** `docs/WHATSAPP_TEMPLATES.md`, `docs/WHATSAPP_STRATEGY_AND_AUDIT.md`
- [ ] **Stripe Connect / merchant agreement** (if applicable) — **Adapt from:** `docs/STRIPE_SETUP_GUIDE.md`
- [ ] **Anti-bribery / anti-corruption policy** (for institutional LPs/grants) — *New short policy*
- [ ] **Sanctions / PEP screening** (if institutional investor) — *Finance*

---

## 4. Tier 3 — Nice-to-Have / Stage-Dependent

Prepare when approaching **Series A**, **larger grants ($500k+)**, **enterprise sales**, or **regional expansion**.

### Corporate & legal (Tier 3)

- [ ] **Dual-structure memo** (Kenya HoldCo + US/BVI topco if diaspora VC requires) — *Legal*
- [ ] **Convertible note / SAFE templates** (for future bridge rounds) — *Legal*
- [ ] **Secondary sale policy** — *Legal*
- [ ] **Key person insurance** — *Finance*
- [ ] **International trademark (ARIPO / Madrid)** — *Legal*
- [ ] **Local subsidiary playbook** (Nigeria, South Africa entities) — *Legal*

### Financial (Tier 3)

- [ ] **Big 4 or regional firm audit** (full IFRS) — *CPA*
- [ ] **SOC 2 Type I / Type II roadmap** (if selling to enterprise/regulated clients) — *Product / Security*
- [ ] **Revenue recognition memo** (ASC 606 / IFRS 15 for subscriptions) — *CPA*
- [ ] **FX hedging policy** (USD raise, KES opex) — *Finance*
- [ ] **Board-approved annual budget** — *Finance*

### Product & tech (Tier 3)

- [ ] **Formal SOC 2 control matrix** — *Security*
- [ ] **ISO 27001 gap assessment** — *Security*
- [ ] **AI governance policy** (model selection, bias, human-in-the-loop) — *Product / Legal*
- [ ] **Formal API documentation for partners** — **Adapt from:** `docs/API_REFERENCE.md`
- [ ] **SLA document** (uptime, support tiers) — *Product*
- [ ] **Multi-region deployment plan** — *Engineering*

### Commercial (Tier 3)

- [ ] **Enterprise pricing & security questionnaire responses** — *Sales*
- [ ] **Channel partner program legal pack** — **Adapt from:** `docs/AGENCY_WHITELABEL.md`
- [ ] **Marketplace / UNIMART scale agreement** — **Adapt from:** `docs/MARKETPLACE_PARTNER_SYSTEM.md`
- [ ] **Competitive battle cards** — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md` §Competitive Landscape
- [ ] **International expansion GTM** (NG, ZA) — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md` §Bridge Round
- [ ] **Brand guidelines PDF** — **Adapt from:** `docs/KOVA_BRAND_PLAYBOOK.md`

### Fundraising-specific (Tier 3)

- [ ] **Series A deck** (metrics-heavy: NRR, CAC/LTV, magic number) — *New*
- [ ] **CIM / confidential information memorandum** (for larger rounds) — *New*
- [ ] **Investment memo** (internal, for lead investor) — *New*
- [ ] **Analyst-style market map** — **Adapt from:** `docs/KOVA_MARKET_RESEARCH_SURVEY.md`, `docs/STRATEGIC_MONOPOLY_PLAN.md`
- [ ] **Board deck template** (quarterly) — *New*

### Grants (Tier 3)

- [ ] **Randomized control trial (RCT) or quasi-experimental design** (for rigorous impact grants) — *M&E advisor*
- [ ] **Third-party impact audit** — *External evaluator*
- [ ] **Open data / research publication plan** — *New*
- [ ] **Multi-country grant consortium agreements** — *Legal*

---

## 5. Full Category Checklists (All Tiers)

Use these master lists when building the data room. Check items off as you go.

### 5.1 Corporate & legal

- [ ] Certificate of Incorporation (Kenya Private Limited)
- [ ] CR12 (current directors & shareholders)
- [ ] Memorandum & Articles of Association
- [ ] BRS annual return filings (up to date)
- [ ] Company KRA PIN + individual founder PINs
- [ ] VAT registration & returns (if applicable)
- [ ] Business permit / county single business permit (if required for office)
- [ ] Founders agreement (equity, vesting 4yr/1yr cliff standard)
- [ ] Shareholders Agreement (SHA) — post-term sheet
- [ ] Board resolutions (fundraising, option pool, major contracts)
- [ ] IP assignment (founder → company, dated at incorporation)
- [ ] Trademark applications (Kenya KIPI)
- [ ] Domain WHOIS / registrar ownership proof
- [ ] Mutual NDA + unilateral NDA (for employees)
- [ ] Privacy Policy (`/privacy/`)
- [ ] Terms of Service (`/terms/`)
- [ ] Cookie Policy (`/cookies/`)
- [ ] Acceptable Use Policy
- [ ] Data Processing Agreement (B2B)
- [ ] Data Protection Act 2019 — ODPC registration
- [ ] DPIA (AI + social data)
- [ ] Records of Processing Activities (ROPA)
- [ ] Data breach response plan
- [ ] Employment offer letters + contracts (Kenya Employment Act compliant)
- [ ] Contractor agreements (IP assignment, confidentiality)
- [ ] ESOP / option plan + board approvals
- [ ] Employee handbook (leave, remote work, code of conduct)
- [ ] Anti-harassment & equal opportunity policy
- [ ] Whistleblower / grievance procedure (Tier 3 / larger team)

### 5.2 Financial

- [ ] 3-year model (revenue, COGS, opex, headcount, capex)
- [ ] Unit economics (by plan tier: Starter/Growth/Pro/Agency)
- [ ] Use of funds (aligned to milestones)
- [ ] Current burn + runway calculation
- [ ] Cap table (current + pro forma)
- [ ] Bank statements (3–12 months)
- [ ] Management accounts (monthly)
- [ ] Audited/reviewed statements (when revenue materializes)
- [ ] Tax filings & compliance certificates
- [ ] PAYE / NSSF / NHIF (if employees)
- [ ] Invoice template + company letterhead
- [ ] Expense policy & approval workflow
- [ ] Financial controls & segregation of duties memo
- [ ] Insurance policies (cyber, liability)
- [ ] Payment processor statements (M-Pesa, Stripe)

### 5.3 Product & technology

- [ ] System architecture diagram
- [ ] Agent loop & data flow diagram — **Adapt from:** `docs/system-maps/SYSTEM_AUDIT_AND_FLOWS.md`
- [ ] Infrastructure diagram (Railway, Postgres, Redis, Celery, R2)
- [ ] Security summary (OAuth token storage, encryption, RBAC, admin access)
- [ ] Content safety & moderation — **Adapt from:** `docs/CONTENT_SAFETY.md`
- [ ] Platform resilience decisions — **Adapt from:** `docs/PLATFORM_RESILIENCE.md`
- [ ] Third-party API dependency & rate-limit risks — **Adapt from:** platform audits in `docs/platform-audits/`
- [ ] Open-source license compliance report
- [ ] Backup & recovery procedures
- [ ] Incident response plan
- [ ] Subprocessor / vendor list
- [ ] Product roadmap (12–18 months) — **Adapt from:** `docs/DEVELOPMENT_ROADMAP.md`, `docs/KOVA_BUSINESS_PROPOSAL.md` §Roadmap
- [ ] QA / testing summary — **Adapt from:** `docs/KOVA_TESTING_GUIDE.md`
- [ ] SOC 2 path (Tier 3) — control objectives mapping

### 5.4 Commercial & GTM

- [ ] ICP & personas — **Adapt from:** `docs/FIRST_50_CUSTOMERS_PLAYBOOK.md`
- [ ] Pricing & packaging — **Adapt from:** `docs/KOVA_PLANS_GUIDE.md`, `docs/PLAN_V2_SPEC.md`
- [ ] Competitive positioning — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md`, `docs/KOVA_WHAT_WE_ARE.md`
- [ ] GTM channels & CAC assumptions — **Adapt from:** `docs/FIRST_50_CUSTOMERS_PLAYBOOK.md`
- [ ] TEST_BUSINESSES pilot plan — **Adapt from:** `docs/TEST_BUSINESSES.md`
- [ ] Growth Partners program — **Adapt from:** `docs/GROWTH_PARTNERS_PROGRAM.md`
- [ ] UNIMART / marketplace strategy — **Adapt from:** `docs/UNIMART_KOVA_STRATEGY.md`
- [ ] Outreach templates — **Adapt from:** `docs/KOVA_OUTREACH_EMAILS.md`
- [ ] Customer LOIs / pilot MOUs
- [ ] Case studies & testimonials
- [ ] Pipeline & conversion funnel metrics
- [ ] Churn analysis & retention playbook
- [ ] Agency / white-label terms — **Adapt from:** `docs/AGENCY_WHITELABEL.md`

### 5.5 Fundraising-specific

- [ ] Pitch deck (PDF + editable source)
- [ ] One-pager
- [ ] Executive summary
- [ ] Full business proposal — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md`
- [ ] Funding plan & allocation — **Adapt from:** `docs/KOVA_FUNDING_PLAN.md`
- [ ] Seed proposal (competition format) — **Adapt from:** `docs/KOVA_BIOS_SEED_PROPOSAL_FINAL.md`
- [ ] Founder pitch scripts — **Adapt from:** `docs/KOVA_FOUNDER_PITCH.md`
- [ ] Investor FAQ
- [ ] Data room index (linked)
- [ ] Cap table pro forma (multiple scenarios)
- [ ] Term sheet (template + executed)
- [ ] Due diligence Q&A log
- [ ] Monthly investor update template
- [ ] Demo script & backup video
- [ ] Competition / accelerator application copies (ABH, etc.)

### 5.6 Grants

- [ ] Theory of change diagram
- [ ] Problem statement & evidence (Kenya MSME data) — **Adapt from:** business proposal market section
- [ ] Beneficiary definition & selection criteria
- [ ] SDG alignment matrix — **Adapt from:** `docs/KOVA_BUSINESS_PROPOSAL.md` §Social Impact
- [ ] Impact metrics (outputs/outcomes/impact)
- [ ] M&E plan & data collection tools
- [ ] Grant budget (direct/indirect costs)
- [ ] Budget narrative (justify each line)
- [ ] Organizational capacity statement
- [ ] Founder & key staff CVs
- [ ] Registration certificates (incorporation, PIN, tax)
- [ ] Letters of support (government, NGO, association)
- [ ] Partnership MOUs (implementation partners)
- [ ] Inclusion strategy (women, youth, rural)
- [ ] Safeguarding / PSEAH policy (if required)
- [ ] Audit trail & grant reporting calendar
- [ ] Bank mandate for grant account

### 5.7 Compliance & risk

- [ ] Meta Developer App compliance — **Adapt from:** `docs/KOVA_PLATFORM_SETUP_GUIDE.md`
- [ ] WhatsApp Business Policy alignment — **Adapt from:** `docs/WHATSAPP_STRATEGY_AND_AUDIT.md`
- [ ] Facebook/Instagram data deletion flow — **Exists in product**
- [ ] TikTok / LinkedIn / YouTube API compliance checklists — **Adapt from:** platform setup guide
- [ ] M-Pesa Paybill / Daraja go-live checklist — **Adapt from:** `docs/MPESA_SETUP.md`
- [ ] Stripe PCI SAQ-A scope memo — **Adapt from:** `docs/STRIPE_SETUP_GUIDE.md`
- [ ] Kenya Data Protection Act compliance pack
- [ ] AI-generated content disclosure (platform ToS + user-facing)
- [ ] Content safety enforcement — **Adapt from:** `docs/CONTENT_SAFETY.md`
- [ ] Acceptable use & abuse handling
- [ ] Sanctions / AML (if handling large grant flows)
- [ ] Platform ban / API revocation contingency — **Adapt from:** `docs/PLATFORM_RESILIENCE.md`

---

## 6. Data Room Folder Structure

Suggested Google Drive / Notion / DocSend structure. Use **read-only links** for external parties; keep **executed contracts** in a restricted subfolder.

```
KOVA-Data-Room/
├── 00-Index/
│   ├── DATA_ROOM_INDEX.xlsx          # Document | Status | Owner | Last updated | Link
│   ├── NDA-signed/                   # Counterparty NDAs only
│   └── FAQ_INVESTOR.md
├── 01-Corporate/
│   ├── Incorporation/
│   │   ├── Certificate_of_Incorporation.pdf
│   │   ├── CR12.pdf
│   │   ├── Memorandum_and_Articles.pdf
│   │   └── Board_Resolutions/
│   ├── Cap-Table/
│   │   ├── Cap_Table_Current.xlsx
│   │   └── Cap_Table_Pro_Forma.xlsx
│   ├── Governance/
│   │   ├── Founders_Agreement.pdf
│   │   ├── SHA_Executed.pdf          # post-close
│   │   └── ESOP_Plan.pdf
│   └── Regulatory/
│       ├── KRA_PIN.pdf
│       ├── VAT_Registration.pdf      # if applicable
│       └── ODPC_Registration.pdf
├── 02-Legal/
│   ├── IP/
│   │   ├── IP_Assignment_Deed.pdf
│   │   └── Trademark_Filings/
│   ├── Commercial-Templates/
│   │   ├── MSA_Template.docx
│   │   ├── DPA_Template.pdf
│   │   └── Contractor_Agreement.docx
│   ├── Policies-Live/
│   │   ├── Privacy_Policy.pdf        # export from /privacy/
│   │   ├── Terms_of_Service.pdf
│   │   ├── Acceptable_Use.pdf
│   │   └── Cookie_Policy.pdf
│   ├── Employment/
│   └── Material-Contracts/           # Railway, OpenRouter, etc. (redact secrets)
├── 03-Financial/
│   ├── Model/
│   │   └── KOVA_Financial_Model_vX.xlsx
│   ├── Use_of_Funds.pdf
│   ├── Management_Accounts/
│   ├── Bank_Statements/
│   ├── Tax/
│   └── Audit/                        # when available
├── 04-Product-Tech/
│   ├── Architecture_Overview.pdf
│   ├── Security_Summary.pdf
│   ├── Platform_Resilience.pdf       # from internal doc
│   ├── Content_Safety_Policy.pdf
│   ├── Subprocessors_List.xlsx
│   ├── Open_Source_Inventory.pdf
│   └── Roadmap.pdf
├── 05-Commercial/
│   ├── Pricing_KOVA_Plans_v2.pdf
│   ├── GTM_Plan.pdf
│   ├── TEST_BUSINESSES_Pilot_Summary.pdf
│   ├── Pipeline_Export.csv
│   ├── LOIs_and_Pilots/
│   └── Case_Studies/
├── 06-Fundraising/
│   ├── Pitch_Deck.pdf
│   ├── One_Pager.pdf
│   ├── Executive_Summary.pdf
│   ├── Business_Proposal.pdf       # export KOVA_BUSINESS_PROPOSAL
│   ├── Funding_Plan.pdf
│   └── Due-Diligence-QA.log
├── 07-Grants/                        # optional parallel track
│   ├── Theory_of_Change.pdf
│   ├── Impact_Metrics_M&E.pdf
│   ├── Grant_Budget.xlsx
│   ├── Letters_of_Support/
│   └── CVs/
└── 08-Compliance-Risk/
    ├── Meta_WhatsApp_Compliance.pdf
    ├── MPesa_Compliance_Notes.pdf
    ├── PCI_Memo.pdf
    └── Data_Protection_Pack/
```

---

## 7. Timeline — Week 1 vs Pre–Due Diligence

### Week 1 (immediate — unlock first meetings)

| Day | Focus | Deliverables |
|-----|-------|--------------|
| 1–2 | **Narrative** | Pitch deck v0.9, one-pager, exec summary export from business proposal |
| 2–3 | **Corporate baseline** | Confirm incorporation status; order CR12; open company bank if not done |
| 3–4 | **Cap table + ask** | Cap table v1, use-of-funds one-pager, financial model skeleton |
| 4–5 | **Legal surface** | Verify live legal pages; schedule advocate for founders agreement + IP deed |
| 5–7 | **Demo + pilots** | Record demo video; pick 3 TEST_BUSINESSES for LOI outreach; data room index |

### Weeks 2–4 (before term sheet)

- Founders agreement + IP assignment **signed**
- 3-year model with Plan v2 pricing and `KOVA_FINANCIAL_AUDIT.md` COGS assumptions
- Investor FAQ + pipeline metrics
- Grant theory of change + budget narrative (if grant track active)
- 2–3 letters of support in progress

### Pre–due diligence (term sheet signed → close, typically 4–8 weeks)

- SHA and definitive investment docs with counsel
- Full data room populated per §6
- Management accounts + bank statements
- Material contracts register + disclosure schedules
- Customer references / pilot case studies
- ODPC registration (if not done)
- Option pool creation & board resolutions
- Insurance quotes (cyber, D&O if required)

### Ongoing (post-close / grant award)

- Monthly investor or grant reporting
- Quarterly board packs
- Annual BRS returns + tax filings
- Refresh deck with traction metrics each quarter

---

## 8. KOVA-Specific Pointers — Existing Docs to Adapt

| Document in repo | Use for fundraising | Adapt vs new draft |
|------------------|---------------------|--------------------|
| [`KOVA_BUSINESS_PROPOSAL.md`](./KOVA_BUSINESS_PROPOSAL.md) | Full investor narrative; export sections to PDF | **Adapt** — update traction, team, contact block; sync pricing with Plan v2 |
| [`KOVA_FUNDING_PLAN.md`](./KOVA_FUNDING_PLAN.md) | Use of funds, milestones, hiring, grant section | **Adapt** — reconcile amounts with latest model |
| [`KOVA_FINANCIAL_AUDIT.md`](./KOVA_FINANCIAL_AUDIT.md) | Unit economics, COGS, margin risks for DD | **Adapt** — add investor summary; address top 5 risks in FAQ |
| [`KOVA_FOUNDER_PITCH.md`](./KOVA_FOUNDER_PITCH.md) | Deck narrative & spoken pitch | **Adapt** — do not send as-is; convert to slides |
| [`KOVA_BIOS_SEED_PROPOSAL_FINAL.md`](./KOVA_BIOS_SEED_PROPOSAL_FINAL.md) | Grant / competition format (business canvas) | **Adapt** — verify team names, pricing, registration status |
| [`KOVA_PLANS_GUIDE.md`](./KOVA_PLANS_GUIDE.md) + [`PLAN_V2_SPEC.md`](./PLAN_V2_SPEC.md) | Pricing slide, revenue model | **Adapt** — authoritative for all financial docs |
| [`TEST_BUSINESSES.md`](./TEST_BUSINESSES.md) | Pilot design, case study seeds, product validation | **Adapt** — executive summary + LOI targets |
| [`FIRST_50_CUSTOMERS_PLAYBOOK.md`](./FIRST_50_CUSTOMERS_PLAYBOOK.md) | GTM, CAC, launch ops | **Adapt** — GTM appendix for data room |
| [`KOVA_PLATFORM_SETUP_GUIDE.md`](./KOVA_PLATFORM_SETUP_GUIDE.md) | Tech DD, Meta/legal URLs, env architecture | **Adapt** — redact secrets; add architecture diagram |
| [`PLATFORM_RESILIENCE.md`](./PLATFORM_RESILIENCE.md) | Risk mitigation for investors | **Adapt** — 2-page investor summary |
| [`CONTENT_SAFETY.md`](./CONTENT_SAFETY.md) | Trust & safety / AI moderation | **Adapt** — publish as policy PDF |
| [`system-maps/SYSTEM_AUDIT_AND_FLOWS.md`](./system-maps/SYSTEM_AUDIT_AND_FLOWS.md) | Product architecture overview | **Adapt** — simplify for non-technical readers |
| [`WHATSAPP_STRATEGY_AND_AUDIT.md`](./WHATSAPP_STRATEGY_AND_AUDIT.md) | WhatsApp compliance DD | **Adapt** |
| [`MPESA_SETUP.md`](./MPESA_SETUP.md) / [`STRIPE_SETUP_GUIDE.md`](./STRIPE_SETUP_GUIDE.md) | Payments compliance | **Adapt** — PCI/M-Pesa memos |
| [`GROWTH_PARTNERS_PROGRAM.md`](./GROWTH_PARTNERS_PROGRAM.md) | Distribution / channel strategy | **Adapt** |
| [`UNIMART_KOVA_STRATEGY.md`](./UNIMART_KOVA_STRATEGY.md) | Strategic customer / proof point | **Adapt** — case study + LOI |
| [`KOVA_WHAT_WE_ARE.md`](./KOVA_WHAT_WE_ARE.md) | Messaging consistency across materials | **Adapt** — enforce in deck copy |
| Legal HTML templates (`templates/pages/*.html`) | Live policies | **Adapt** — advocate review + ODPC alignment; export PDF for data room |
| **Pitch deck (slides)** | First meeting | **New draft** |
| **Founders agreement / SHA / IP deed** | Close | **New** — advocate required |
| **Cap table spreadsheet** | Every investor call | **New** |
| **Incorporation certificates (CR12, etc.)** | Entity proof | **New** — BRS |
| **Audited financials** | Later stage | **New** — when revenue warrants |

### Pricing consistency warning

Internal docs show **mixed list prices** (e.g. business proposal cites KES 299 starter; `KOVA_FINANCIAL_AUDIT.md` and Plan v2 cite **KES 499** starter). **Before any investor send**, reconcile all materials to `PLAN_V2_SPEC.md` / `apps/billing/models.py` authoritative limits.

---

## 9. Kenya-Specific Checklist

### Registration & corporate (BRS / eCitizen)

- [ ] **Reserve company name** (avoid conflict with "Kova" trademarks — search KIPI + BRS)
- [ ] **Register Private Limited Company** under Companies Act 2015
- [ ] **Obtain Certificate of Incorporation**
- [ ] **CR12** — register of members and directors (request via BRS; needed for banks and grants)
- [ ] **File initial notices** (registered office, directors) within statutory deadlines
- [ ] **Annual returns** calendar reminder (avoid BRS penalties / strike-off)
- [ ] **Company seal** (if still used by your bank — increasingly optional)

### Tax & statutory (KRA)

- [ ] **Company PIN** application (iTax)
- [ ] **Individual PINs** for directors (if not already)
- [ ] **VAT registration** — mandatory when turnover exceeds threshold; voluntary if invoicing VAT-registered clients
- [ ] **PAYE registration** — when first employee on payroll
- [ ] **Withholding tax** on dividends, professional fees, cross-border payments — confirm with tax advisor
- [ ] **Digital service tax (DST)** — assess applicability for digital marketplace services
- [ ] **Tax compliance certificate** — useful for government grants and some corporate customers

### Data protection (ODPC)

- [ ] **Register as data controller/processor** with Office of the Data Protection Commissioner (ODPC) when required
- [ ] **Appoint Data Protection Officer** (if processing at scale or sensitive data)
- [ ] **Privacy policy** aligned to DPA 2019 principles (lawfulness, purpose limitation, security, cross-border transfer rules)
- [ ] **Data subject rights procedure** (access, erasure — align with in-app deletion flows)
- [ ] **Cross-border transfer assessment** (US/EU subprocessors: OpenRouter, Railway, Stripe, Meta)

### Banking & M-Pesa

- [ ] **Corporate bank account** (KCB, Equity, Stanbic, etc. — requires incorporation docs + CR12 + board resolution)
- [ ] **M-Pesa Paybill / Till** for business collections — **see** `docs/MPESA_SETUP.md` (CR12 often required for go-live)
- [ ] **Signatory mandate** clearly defining who can move funds (critical before taking investment)

### Employment & contractors (Kenya)

- [ ] **Written employment contracts** (Employment Act 2007)
- [ ] **NSSF & NHIF / SHIF registration**
- [ ] **Work permits** — if hiring non-Kenyan citizens
- [ ] **Contractor vs employee classification** review (avoid sham contracting)

### Advocate-reviewed templates (strongly recommended)

Do **not** download generic US templates without Kenya localization. Have a Kenyan advocate review at minimum:

1. Founders agreement  
2. Shareholders agreement  
3. IP assignment deed  
4. Employment and contractor agreements  
5. SHA side letters  
6. Customer MSA and DPA (especially data transfer clauses)

---

## 10. Status Tracker (Optional)

Copy this table to `DATA_ROOM_INDEX.xlsx` or Notion. Update weekly.

| Document | Tier | Status | Owner | Adapt from / Notes |
|----------|------|--------|-------|-------------------|
| Pitch deck (slides) | 1 | Not started | Founder | Narrative: `KOVA_FOUNDER_PITCH.md` |
| One-pager PDF | 1 | Not started | Founder | Distill `KOVA_BUSINESS_PROPOSAL.md` |
| Executive summary | 1 | Draft | Founder | `KOVA_BUSINESS_PROPOSAL.md` §Executive Summary |
| Business proposal (full) | 1 | Draft | Founder | `KOVA_BUSINESS_PROPOSAL.md` — update pricing/traction |
| Funding / use of funds | 1 | Draft | Finance | `KOVA_FUNDING_PLAN.md` |
| Financial model (3-year) | 1 | Not started | Finance | Align to Plan v2 + `KOVA_FINANCIAL_AUDIT.md` |
| Cap table (current) | 1 | Not started | Founder | New spreadsheet |
| Cap table pro forma | 1 | Not started | Finance | New |
| Certificate of Incorporation | 1 | Not started | Legal | BRS — planned in seed proposals |
| CR12 | 1 | Not started | Legal | Post-incorporation |
| Company KRA PIN | 1 | Not started | Finance | iTax |
| Founders agreement | 1 | Not started | Legal | Advocate review required |
| IP assignment deed | 1 | Not started | Legal | Advocate review required |
| SHA | 2 | Not started | Legal | Post-term sheet |
| Privacy Policy (live) | 1 | Final | Legal | `templates/pages/privacy.html` — ODPC review pending |
| Terms of Service (live) | 1 | Final | Legal | `templates/pages/terms.html` |
| DPA template | 1 | Draft | Legal | `templates/pages/dpa.html` |
| ODPC registration | 1 | Not started | Legal | DPA 2019 |
| Financial audit report | 1 | Final | Finance | `KOVA_FINANCIAL_AUDIT.md` — internal, not statutory audit |
| Architecture overview | 1 | Draft | Product | `system-maps/SYSTEM_AUDIT_AND_FLOWS.md` |
| Content safety policy | 1 | Final | Product | `CONTENT_SAFETY.md` |
| Platform resilience summary | 1 | Draft | Product | `PLATFORM_RESILIENCE.md` |
| Pricing / plans guide | 1 | Final | Founder | `KOVA_PLANS_GUIDE.md`, `PLAN_V2_SPEC.md` |
| TEST_BUSINESSES pilot plan | 1 | Draft | Founder | `TEST_BUSINESSES.md` |
| GTM playbook | 1 | Draft | Founder | `FIRST_50_CUSTOMERS_PLAYBOOK.md` |
| Investor FAQ | 1 | Not started | Founder | New |
| Data room index | 1 | Not started | Founder | This checklist §6 |
| Theory of change (grants) | 1 | Draft | Founder | `KOVA_BUSINESS_PROPOSAL.md` §SDG |
| Grant budget narrative | 2 | Draft | Finance | `KOVA_FUNDING_PLAN.md` + `KOVA_BIOS_SEED_PROPOSAL_FINAL.md` |
| Letters of support | 2 | Not started | Founder | New outreach |
| Customer LOIs | 2 | Not started | Founder | TEST_BUSINESSES partners |
| Meta/WhatsApp compliance pack | 1 | Draft | Product | `KOVA_PLATFORM_SETUP_GUIDE.md` |
| M-Pesa compliance notes | 2 | Draft | Finance | `MPESA_SETUP.md` |
| PCI scope memo | 2 | Not started | Finance | `STRIPE_SETUP_GUIDE.md` |
| Bank statements (company) | 2 | Not started | Finance | Requires corporate account |
| Audited financial statements | 3 | Not started | Finance | Future — when revenue material |
| SOC 2 roadmap | 3 | Not started | Product | New |
| ESOP plan | 2 | Not started | Legal | Post-term sheet |

**Status legend:** Not started → Draft → Review (counsel/investor feedback) → Final (signed/live/exported)

---

## 11. Quick Reference — Document Owners

| Owner | Primary responsibilities |
|-------|-------------------------|
| **Founder / CEO** | Deck, narrative, pilots, LOIs, investor relations, data room index |
| **Legal (external advocate)** | Incorporation, founders agreement, SHA, IP, employment templates, ODPC |
| **Finance** | Model, cap table, bank, tax, grant budgets, management accounts |
| **Product / CTO** | Architecture, security, compliance packs, demo, roadmap |
| **Ops / GTM** | Pipeline exports, case studies, Growth Partners, outreach |

---

## 12. Related Internal Documents

- [**Fundraising draft pack**](../fundraising/README.md) — Tier 1 markdown + PDFs (`fundraising/`)
- [KOVA Business Proposal](./KOVA_BUSINESS_PROPOSAL.md)
- [KOVA Funding Plan](./KOVA_FUNDING_PLAN.md)
- [KOVA Financial Audit](./KOVA_FINANCIAL_AUDIT.md)
- [KOVA Founder Pitch](./KOVA_FOUNDER_PITCH.md)
- [KOVA Plans Guide](./KOVA_PLANS_GUIDE.md)
- [TEST_BUSINESSES Pilot Plan](./TEST_BUSINESSES.md)
- [KOVA Platform Setup Guide](./KOVA_PLATFORM_SETUP_GUIDE.md)

---

*Maintained by KOVA founding team. Update after each fundraising milestone, grant submission, or corporate change.*
