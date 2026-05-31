# REACH Lead Automation — Audit & Implementation

**Date:** May 2026  
**Scope:** `kova_agent` Reach section — lead capture, nurture, scoring, navigation.

## Audit summary

REACH previously fragmented leads across Links submissions, walk-ins without CRM bridge, and nurture steps that only sent email. Manual cashier capture did not create leads. Composite scoring existed but was not wired to daily jobs. Navigation duplicated Leads and Reach.

## Implemented (P0)

| Item | Status | Notes |
|------|--------|-------|
| Walk-in → Lead | Done | `customer_phone`, `customer_name` on `WalkInEvent`; cashier UI; `post_save` → `create_lead_from_walkin()` |
| Nurture triggers `from_walk_in`, `from_qr_scan` | Done | Model + `enroll_lead_in_sequences()` |
| Wire `nurture_router` | Done | `process_nurture_steps` uses `route_nurture_step()`; WhatsApp preferred when phone present |
| `SEND_WHATSAPP` action | Done | `NurtureStep.ActionType` |
| Stale-lead automation | Done | `reengage_stale_leads` Celery task + `stale_winback` trigger; daily beat |
| Composite scoring | Done | `score_all_leads` calls `score_and_update_lead()` |
| Default welcome sequence | Done | `ensure_default_nurture_sequences()` on first lead; management command `ensure_welcome_nurture` |

## Implemented (P1)

| Item | Status | Notes |
|------|--------|-------|
| Sidebar Reach consolidation | Done | Single Reach group: Leads, Pipeline, Links, Walk-ins, Automations, Analytics |
| Competitors moved | Done | Under Create → Studio subnav |
| Insights → Performance | Done | Under Snap2sell, links to `/analytics/` insights |
| Submissions merge | Done | `/links/submissions/` → `/leads/?source=form_submission`; note on Links page |

## Implemented (P2)

| Item | Status | Notes |
|------|--------|-------|
| Pipeline kanban | Done | `/leads/pipeline/` by status |
| Lead detail nurture + score | Done | Active enrollment step; composite score card (existing) |

## Migrations to run

```bash
cd kova_agent
python manage.py migrate qr_attribution
python manage.py migrate leads
```

Optional backfill for existing users:

```bash
python manage.py ensure_welcome_nurture
```

## Key files changed

- `apps/qr_attribution/models.py`, `signals.py`, `views.py`, migration `0002_walkin_customer_fields`
- `apps/leads/models.py`, `bridges.py`, `tasks.py`, `signals.py`, `defaults.py`, `nurture_router.py`, migration `0005_reach_nurture_triggers`
- `apps/leads/management/commands/ensure_welcome_nurture.py`
- `apps/leads/views.py`, `urls.py`
- `templates/qr_attribution/cashier.html`, `templates/layouts/app.html`, `templates/leads/*`, `templates/links/page_list.html`
- `apps/links/views.py` (submissions redirect)
- `config/settings/base.py` (Celery beat)
- `tests/test_reach_lead_automation.py`

## Deferred

- **QR scan → Lead bridge** when landing page collects phone (trigger `from_qr_scan` is ready; no auto-lead on scan alone).
- **Drag-and-drop pipeline** (read-only kanban for now).
- **Admin UI** for new `SEND_WHATSAPP` step type in nurture form builder (API accepts `send_whatsapp` via POST).

## Celery beat (new)

- `reengage-stale-leads` — daily, task `leads.reengage_stale_leads`
