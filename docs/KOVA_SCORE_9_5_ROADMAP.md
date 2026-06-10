# KOVA Score 9.5 Roadmap

**Sprint:** June 10–11, 2026 (P0 + Phase 2)  
**Baseline:** 7.6/10 weighted (`KOVA_SYSTEM_SECTION_RATINGS.md`)  
**Post-P0 estimate:** **8.4 / 10**  
**Post-Phase 2 estimate:** **~8.9 / 10** (see section deltas below)

---

## P0 — Done (June 10 sprint)

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Growth-tier WhatsApp wedge | **DONE** | `whatsapp_inbox_enabled` on Growth; inbox + utility + nurture; broadcasts Pro+ |
| 2 | QR scan → lead (phone capture) | **DONE** | Landing form + `create_lead_from_qr_scan`; `/qr/<token>/capture/` |
| 3 | Money board daily digest | **DONE** | `briefs.send_money_board_digests` Celery task; opt-in `money_board_digest_enabled` |
| 4 | Unified needs-reply links | **DONE** | Money board → `?status=escalated` / `?needs_reply=1` |
| 5 | Platform resilience Stage 2 | **DONE** | Block approve if token &lt;24h; rate-limit one-click reschedule |
| 6 | Landing + marketing truth | **DONE** | 7+3 platforms; hero CTA "Connect WhatsApp — free trial" |
| 7 | Deploy hardening | **DONE** | `release.sh` migrate; `.env.example` notes |
| 8 | Starter Engage trial | **DONE** | 5 auto-replies/week; `engage_trial_*` counters |
| 9 | Autopilot UX | **DONE** | Follow-up vs content autopilot labels; FAQ rows |
| 10 | Merge Revenue + Performance nav | **DONE** | Single **Results** nav |

**Migrate (P0):** `accounts.0031_money_board_digest_engage_trial`

---

## Phase 2 — Done June 11, 2026

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | WhatsApp Channels in sidebar | **DONE** | Pro+ subnav link → `whatsapp:channel_dashboard` |
| 2 | Workspace hidden Starter/Growth | **DONE** | Grow → More → Workspace only for Pro/Agency |
| 3 | E2E wedge checklist after signup | **DONE** | `tests/e2e/test_critical_paths.py::TestWedgeChecklistOnToday` |
| 4 | CI test count doc | **DONE** | `KOVA_TESTING_GUIDE.md` §31 updated (~960 pytest + 14 E2E) |
| 5 | Engage WebSocket real-time | **DONE** | `engage_new` push on new interactions; `kova-realtime.js` refresh |
| 6 | Outage queue hold | **DONE** | `check_and_publish_due_posts` + `publish_post` skip/hold when `is_outage` |
| 7 | Proactive token reconnect WS | **DONE** | `warn_expiring_tokens` → `token_warning` WebSocket + in-app notification |
| 8 | Hide coming-soon platforms | **DONE** | Collapsed "More platforms on the way" on `/platforms/` |
| 9 | Teams link for Pro (5 cap) | **DONE** | Settings subnav with `(5 max)` badge |
| 10 | Cookie/consent banner | **DONE** (prior) | `base.html` GDPR banner with essential/all |
| 11 | Starter Today density | **DONE** | Collapsible "Daily brief & insights" below money board |
| 12 | Platform picker sort | **PARTIAL** | Coming-soon hidden; wedge-priority sort deferred |
| 13 | FB Messenger real-time | **DEFERRED** | No Messenger inbox surface yet — Phase 3 |
| 14 | M-Pesa renewal push | **DEFERRED** | Billing task exists as TODO in `MPESA_SETUP.md` |
| 15 | Full wedge E2E (snap→publish→lead) | **DEFERRED** | Needs mock Meta + publish fixtures — Phase 3 |
| 16 | Production security hardening | **DEFERRED** | Cofounder audit items — separate security sprint |

**Tests added:** `tests/test_phase2_score_sprint.py` (8 tests); E2E wedge test in `test_critical_paths.py`.

**Migrate:** None new for Phase 2.

---

## Phase 3 — Done June 11, 2026

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Full wedge E2E (snap→publish→lead→WA) | **DONE** | `tests/test_phase3_score_sprint.py::TestFullWedgeFlowMocked` + `tests/e2e/test_wedge_flow.py` |
| 2 | CI hardening (bandit/pip-audit) | **DONE** | Bandit hard-fails CI; pip-audit warns (deps may have advisories) — `KOVA_TESTING_GUIDE` §31 |
| 3 | M-Pesa renewal warnings | **DONE** | `billing/renewal_notifications.py` — email + in-app; Celery `check_mpesa_subscriptions` |
| 4 | Platform picker wedge sort | **DONE** | WA → IG → FB first on `/platforms/` (`WEDGE_PLATFORM_ORDER`) |
| 5 | FB Messenger MVP | **DONE** | `engage:messenger_threads` — thin MVP via DM inbox pipeline (polling, not real-time WS) |
| 6 | Webhook signature enforcement | **DONE** | WA/Resend/M-Pesa reject unsigned in production |
| 7 | CSP improvements | **DONE** (partial) | `wss:` in `CSP_CONNECT_SRC`; `unsafe-inline` styles deferred (Alpine/HTMX risk) |
| 8 | Secrets audit / env-gate | **DONE** | CI grep; `MPESA_PASSKEY` default empty; prod webhook secrets documented |
| 9 | Staff role granularity | **DONE** | `User.is_support_staff` — read-only admin; POST blocked unless superuser |
| 10 | Unified needs-reply inbox | **DONE** | `engage:unified_inbox` — WA escalated + social in one queue |
| 11 | Money proved this week KPI | **DONE** | Today money board — `revenue_stat` card above chase board |
| 12 | Agency client-switcher UX | **DONE** | Sidebar brand `<select>` for multi-brand agency teams |
| 13 | Partner health dashboard slice | **DONE** | `/dashboard/partners/health/` — webhook failures, stale sync |

**Tests added:** `tests/test_phase3_score_sprint.py` (10 tests); E2E `tests/e2e/test_wedge_flow.py`.

**Migrate:** `accounts.0032_user_is_support_staff`

### Deferred (Phase 4+)

| Item | Reason |
|------|--------|
| FB Messenger real-time WebSocket | MVP polling via Engage Agent cycle sufficient for 9.5; Meta Page webhooks not wired |
| Pipeline kanban drag-and-drop | Out of Phase 3 scope |
| Studio + Queue tab merge | Phase 4 IA |
| Admin Celery health panel | Ops nice-to-have |
| Full CSP remove `unsafe-inline` | Requires Alpine/HTMX nonce audit — breakage risk |

### Score projection (post-Phase 3)

| Section | Post-P2 | Post-P3 | Target 9.5 |
|---------|---------|---------|------------|
| WhatsApp | **8.8** | **8.9** | 9.0 |
| REACH | 8.2 | 8.2 | 8.8 |
| Today / money board | **9.0** | **9.2** | 9.2 |
| Engage | **8.8** | **9.0** | 9.0 |
| Landing | 8.2 | 8.2 | 8.5 |
| Platforms / resilience | **8.6** | **8.9** | 9.0 |
| Performance IA | 7.8 | 7.8 | 8.5 |
| Teams | **7.6** | **8.0** | 8.0 |
| Workspace IA | **7.0** | 7.0 | 7.5 |
| Deploy / CI | **8.0** | **8.4** | 8.5 |
| Admin / partners | 8.5 | **8.7** | 9.0 |
| **Weighted overall** | **~8.9** | **~9.4** | **9.5** |

---

## Remaining for 9.5 / 10 (Phase 4+)

- Pipeline kanban drag-and-drop
- Studio + Queue tab merge
- FB Messenger real-time (Meta Page webhooks)
- Admin Celery health panel
- REACH 8.8+ (nurture UI, pipeline DnD)

---

## Commit reference

Phase 2 commits: sidebar IA (Channels, Workspace gate, Teams Pro), Engage WS, outage hold, token WS warnings, Starter Today compact, tests + docs.

Phase 3 commits: security hardening, unified inbox, M-Pesa renewal, wedge E2E tests, platform sort, Messenger MVP, agency switcher, partner health, docs.
