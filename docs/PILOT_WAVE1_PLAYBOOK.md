# Pilot Wave 1 Playbook

> **Purpose:** Run a focused 30-day pilot with 3 real or test businesses before broader TEST_BUSINESSES rollout.  
> **Admin dashboard:** `/dashboard/pilot/`  
> **CLI status:** `python manage.py pilot_status --wave1`

---

## Wave 1 cohort (3 businesses)

| # | Business | Slug | Why Wave 1 |
|---|----------|------|------------|
| 1 | **Kawaida Hair & Beauty** | `kawaida` | Flagship salon persona — Magic Fill, industry pack, WhatsApp-first SME |
| 2 | **Mara & Moto** | `mara` | E-commerce + Shopify + Pixel + WhatsApp Commerce (Agency tier) |
| 3 | **Nyama Mama Express** | `nyama` | Food / WA orders, memes, media queue (Pro tier) |

Seed all three:

```bash
python manage.py seed_test_businesses --only kawaida,mara,nyama --complete-onboarding
python manage.py pilot_status --wave1
```

Default password: `TestKova2026!` (override with `--password`).

---

## 30-day timeline

### Week 1 — Setup & wedge

| Day | Action | Owner |
|-----|--------|-------|
| 1 | Seed accounts, sign LOI (`fundraising/02-legal/KOVA_Pilot_LOI_TEMPLATE.md`) | Founder |
| 1–2 | Complete onboarding (or `--complete-onboarding` for QA) | Pilot / QA |
| 2–3 | Connect WhatsApp + Instagram per business | Pilot |
| 3–4 | First Snap listing (Kawaida services, Mara products, Nyama menu) | Pilot |
| 5–7 | First publish with CTA link; verify wedge 4/5+ on pilot dashboard | Pilot + Kova |

### Week 2 — Content & leads

| Day | Action |
|-----|--------|
| 8–10 | 5 test seeds per business → approve & schedule posts |
| 11–12 | Lead capture form on Kova Page (Mara, Nyama) or WA booking flow (Kawaida) |
| 13–14 | First automation or nurture enrollment |

### Week 3 — Commerce & polish

| Day | Action |
|-----|--------|
| 15–17 | Studio polish on 2+ products (track credits on pilot dashboard) |
| 18–19 | WhatsApp broadcast or Status Studio test (Pro+ businesses) |
| 20–21 | Review WA reply SLA on `/dashboard/pilot/` |

### Week 4 — Review & case study

| Day | Action |
|-----|--------|
| 22–28 | Full feature pass per `docs/TEST_BUSINESSES.md` feature matrix |
| 29 | Export pilot metrics snapshot (nightly Celery task `accounts.snapshot_pilot_metrics`) |
| 30 | Joint review against success criteria below |

---

## Success criteria (Day 30)

| Metric | Target | Source |
|--------|--------|--------|
| Wedge completion (avg) | **≥ 80%** | `/dashboard/pilot/` aggregate |
| Leads captured (cohort, week 4) | **≥ 3 per business** | Pilot card → leads this week |
| WA reply SLA | **≤ 60 min** avg | `WhatsAppAnalytics.avg_response_time_seconds` |
| Publish success rate | **≥ 90%** | Published vs failed posts (30d) |
| Polish credits | Used without platform pool breach | Per-business card |
| Onboarding | All 3 `pilot_ready` in `pilot_status` | CLI |

**Wave 1 pass:** All 3 businesses hit wedge ≥ 80%, at least 2 of 3 meet leads + publish targets, no critical publish/WA regressions.

---

## Admin tooling

| Tool | URL / command |
|------|----------------|
| Pilot dashboard | `/dashboard/pilot/` |
| Overview summary | `/dashboard/` → Test Business Pilot section |
| Refresh metrics | POST "Refresh metrics" on pilot page |
| Nightly snapshot | Celery beat `snapshot-pilot-metrics` |
| Readiness CLI | `python manage.py pilot_status` |
| LOI template | `fundraising/02-legal/KOVA_Pilot_LOI_TEMPLATE.md` |

---

## Outreach checklist (real pilots)

1. Customize LOI with business legal name, plan tier, and fee.
2. Run `build_pdfs.py` to generate `fundraising/pdf/02-legal/KOVA_Pilot_LOI_TEMPLATE.pdf`.
3. Schedule kick-off within 5 business days of account activation.
4. Add business to `TEST_BUSINESS_REGISTRY` or use live signup with `pilot_status` monitoring.

---

*Kova AI — Wave 1: 3 businesses, 30 days, money-chase metrics.*
