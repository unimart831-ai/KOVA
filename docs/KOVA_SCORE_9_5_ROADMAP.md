# KOVA Score 9.5 Roadmap

**Sprint:** June 10, 2026 (P0 implementation)  
**Baseline:** 7.6/10 weighted (`KOVA_SYSTEM_SECTION_RATINGS.md`)  
**Post-sprint estimate:** **8.4 / 10** (see section deltas below)

---

## P0 — Done this sprint

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Growth-tier WhatsApp wedge | **DONE** | `whatsapp_inbox_enabled` on Growth; inbox + utility + nurture; broadcasts Pro+ |
| 2 | QR scan → lead (phone capture) | **DONE** | Landing form + `create_lead_from_qr_scan`; `/qr/<token>/capture/` |
| 3 | Money board daily digest | **DONE** | `briefs.send_money_board_digests` Celery task; opt-in `money_board_digest_enabled` (default off) |
| 4 | Unified needs-reply links | **DONE** | Money board → `?status=escalated` / `?needs_reply=1`; split card when both |
| 5 | Platform resilience Stage 2 | **DONE** | Block approve if token &lt;24h; rate-limit one-click reschedule (+30 min) |
| 6 | Landing + marketing truth | **DONE** | 7+3 platforms; hero CTA "Connect WhatsApp — free trial" |
| 7 | Deploy hardening | **DONE** | `release.sh` already runs `migrate --noinput`; `.env.example` + setup guide notes |
| 8 | Starter Engage trial | **DONE** | 5 auto-replies/week; inbox access; `engage_trial_*` counters on profile |
| 9 | Autopilot UX | **DONE** | "Follow-up autopilot" vs Studio content autopilot; FAQ keyword rows in Settings |
| 10 | Merge Revenue + Performance nav | **DONE** | Single **Results** nav; `_results_tabs.html` (Money / Posts / Attribution) |

**Tests added:** `tests/test_p0_score_sprint.py`; updated `test_nurture_whatsapp_ui.py`, `test_money_board.py` patterns.

**Migrate:** `accounts.0031_money_board_digest_engage_trial` — run `python manage.py migrate` on deploy.

---

## P1 — Partial / quick wins attempted

| Item | Status | Notes |
|------|--------|-------|
| WA nurture step in Automations UI | **DONE** (prior) | Growth can now add `send_whatsapp` nurture steps |
| Channels in sidebar | **DEFERRED** | Still Pro-only subnav; route exists |
| Workspace hidden Starter/Growth | **DEFERRED** | Still under Grow → More |
| E2E wedge checklist after signup | **DEFERRED** | Add to `tests/e2e/test_critical_paths.py` next sprint |
| CI test count doc update | **DEFERRED** | `KOVA_TESTING_GUIDE.md` refresh |

---

## Remaining for 9.5 / 10

### High impact (next sprint)

1. **Production security** — webhook signatures, CSP, secrets audit (cofounder items).
2. **Full wedge E2E** — signup → WA+IG → snap → publish → lead → WA reply.
3. **WebSocket adoption** — Engage real-time; reduce HTMX polling.
4. **Workspace fold** — Today-only for Starter/Growth; hide Command from default IA.
5. **M-Pesa renewal push** — subscription expiry notifications.
6. **Starter Today density** — collapse non-money widgets below fold.

### Medium impact

- Pipeline kanban drag-and-drop
- FB Messenger real-time
- Competitor analytics defer to Pro default
- Admin Celery health panel
- Bandit/pip-audit CI hard-fail when clean

### Score projection to 9.5

| Section | Pre | Post-P0 | Target 9.5 |
|---------|-----|---------|------------|
| WhatsApp | 7.5 | 8.5 | 9.0 |
| REACH | 7.5 | 8.2 | 8.8 |
| Today / money board | 8.0 | 8.7 | 9.2 |
| Engage | 8.0 | 8.4 | 9.0 |
| Landing | 7.5 | 8.2 | 8.5 |
| Platforms / resilience | 7.5 | 8.0 | 9.0 |
| Performance IA | 7.0 | 7.8 | 8.5 |
| Deploy / CI | 7.5 | 7.8 | 8.5 |
| **Weighted overall** | **7.6** | **~8.4** | **9.5** |

Closing the last ~1.1 points requires security hardening, E2E wedge proof, and shop-floor UX simplification (Workspace/Performance noise reduction).

---

## Commit reference

See git log on `main` after push — logical commits grouped by: plan gates, REACH QR, briefs digest, resilience, IA/docs.
