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

## Remaining for 9.5 / 10 (Phase 3+)

### High impact

1. **Production security** — webhook signatures, CSP, secrets audit.
2. **Full wedge E2E** — signup → WA+IG → snap → publish → lead → WA reply.
3. **M-Pesa renewal push** — subscription expiry notifications.
4. **Pipeline kanban drag-and-drop**
5. **Studio + Queue tab merge** — single Publish surface

### Medium impact

- FB Messenger real-time
- Competitor analytics defer to Pro default (sidebar already gated)
- Admin Celery health panel
- Bandit/pip-audit CI hard-fail when clean
- Platform connect picker wedge-priority sort

### Score projection

| Section | Pre | Post-P0 | Post-P2 | Target 9.5 |
|---------|-----|---------|---------|------------|
| WhatsApp | 7.5 | 8.5 | **8.8** | 9.0 |
| REACH | 7.5 | 8.2 | 8.2 | 8.8 |
| Today / money board | 8.0 | 8.7 | **9.0** | 9.2 |
| Engage | 8.0 | 8.4 | **8.8** | 9.0 |
| Landing | 7.5 | 8.2 | 8.2 | 8.5 |
| Platforms / resilience | 7.5 | 8.0 | **8.6** | 9.0 |
| Performance IA | 7.0 | 7.8 | 7.8 | 8.5 |
| Teams | 7.0 | 7.0 | **7.6** | 8.0 |
| Workspace IA | 6.0 | 6.0 | **7.0** | 7.5 |
| Deploy / CI | 7.5 | 7.8 | **8.0** | 8.5 |
| **Weighted overall** | **7.6** | **~8.4** | **~8.9** | **9.5** |

Closing the last ~0.6 points requires security hardening, full wedge E2E proof, and M-Pesa renewal UX.

---

## Commit reference

Phase 2 commits: sidebar IA (Channels, Workspace gate, Teams Pro), Engage WS, outage hold, token WS warnings, Starter Today compact, tests + docs.
