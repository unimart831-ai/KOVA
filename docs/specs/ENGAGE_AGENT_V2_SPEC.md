# Engage Agent v2 — Graduated Autonomy Spec

> Phase 1 Week 2 of [KOVA_MASTER_PLAN.md](../KOVA_MASTER_PLAN.md).
> Written before code touches the providers. The contract is the spec.

## Goal

Close the second hollow promise: *"AI runs your customer conversations."*
Today the Engage Agent is a suggestion engine on social media — it queues
every reply for human approval. Only WhatsApp auto-sends, and only at
confidence ≥ 0.8. This spec extends graduated auto-send to Instagram,
Facebook, and LinkedIn comments + DMs, plan-tier-gated, with a real
correction loop.

## What "graduated autonomy" means precisely

The Engage Agent produces a reply + a confidence score. **The user's
`engage_autonomy_level` and the message's confidence score together
determine the routing.** Four levels:

| Level | Auto-send threshold | Draft threshold | Below |
|---|---|---|---|
| `OFF`        | never | never | always queue for review |
| `SUGGEST`    | never | always | every AI reply queued; no autonomy |
| `GRADUATED`  | ≥ 0.85 | 0.50 – 0.85 | < 0.50 escalate |
| `AGGRESSIVE` | ≥ 0.70 | 0.40 – 0.70 | < 0.40 escalate |

Social thresholds are **stricter than WhatsApp** by design:
- WhatsApp auto-send fires at 0.80; social is 0.85.
- Reason: a bad WhatsApp reply hits one customer privately. A bad
  public comment reply on Instagram is screenshot-able forever.

## Plan tier gating

| Plan | Max level | Default level for new users |
|---|---|---|
| Starter (KES 299) | `SUGGEST` | `SUGGEST` |
| Growth (KES 999)  | `GRADUATED` | `SUGGEST` |
| Pro (KES 1,999)   | `GRADUATED` | `GRADUATED` |
| Agency (KES 2,999)| `AGGRESSIVE` | `GRADUATED` |

Existing users with `auto_engage=True` migrate to `SUGGEST` (no surprise
auto-sends — they opt up explicitly). With `auto_engage=False` migrate to
`OFF`.

## Confidence scoring — how it's computed

For every inbound social comment / DM, the Engage LLM returns JSON:

```json
{
  "reply": "Open till 11pm tonight 🙏",
  "confidence": 0.92,
  "reasoning": "Direct factual question with hours in brand profile",
  "action": "reply" | "escalate" | "no_reply",
  "intent": "hours" | "booking" | "pricing" | "complaint" | "praise" | "spam" | "other"
}
```

Confidence is **clamped to [0.0, 1.0]** in the task code (same as WhatsApp).

`action="escalate"` and `action="no_reply"` override the level/threshold
routing — the LLM can opt OUT of replying even when confidence is high.

## Safety rails — NEVER auto-send regardless of confidence

These are hard floors. If any apply, the reply queues for human review
even at confidence 1.0:

| Rail | Why |
|---|---|
| `intent == "complaint"` | Risk of public escalation; needs human empathy |
| `intent == "pricing"` and post has no `cta_url` | Don't quote prices we haven't sanctioned |
| `intent == "spam"` | Don't engage; don't auto-block either (false positives) |
| Reply length > 400 chars | Long replies signal LLM uncertainty in 90% of cases |
| First message in conversation AND no prior brand engagement | Cold first contact deserves a human |
| Contains regex `/refund|return|money back|broken|defective/i` | Always human |
| Contact wrote in a language Kova hasn't seen from this brand | Risk of culturally mistuned reply |

The safety check runs **after** the LLM call, on the reply text + intent.
A safety hit logs `safety_blocked` on the Reply record so we can audit
false positives later.

## Schema change — `auto_engage` → `engage_autonomy_level`

The current boolean is misleading (the audit found it auto-queues, not
auto-sends). Replace with an enum.

```python
class EngageAutonomyLevel(models.TextChoices):
    OFF        = "off",        "Off — no AI replies"
    SUGGEST    = "suggest",    "Suggest — AI drafts, I approve every one"
    GRADUATED  = "graduated",  "Graduated — auto-send safe replies, queue tricky ones"
    AGGRESSIVE = "aggressive", "Aggressive — auto-send aggressively (Agency only)"

# UserProfile
engage_autonomy_level = models.CharField(
    max_length=20,
    choices=EngageAutonomyLevel.choices,
    default=EngageAutonomyLevel.SUGGEST,
    help_text="How much social media autonomy to give the Engage Agent.",
)
```

Migration (`accounts/0015_…`):
1. Add `engage_autonomy_level` column with default `SUGGEST`
2. Data migration:
   - `auto_engage=True` → `engage_autonomy_level=SUGGEST` (NOT graduated — explicit opt-in required for autonomy)
   - `auto_engage=False` → `engage_autonomy_level=OFF`
3. **Do NOT drop `auto_engage` in this migration.** Keep it as deprecated for two release cycles so admin tools / old API clients don't break. Mark with `deprecated=True` doctring.

## Undo + correction loop

This is what makes graduated autonomy honest. Every auto-sent reply is
trackable, undoable, and produces a learning signal when the user
corrects it.

### Data model

```python
class EngageReply(models.Model):  # new
    interaction       = ForeignKey(Interaction)
    sent_text         = TextField()
    confidence        = FloatField()
    autonomy_level    = CharField()   # snapshot at send time
    safety_flags      = JSONField(default=list)
    sent_at           = DateTimeField(auto_now_add=True)
    can_undo_until    = DateTimeField()  # sent_at + 5 minutes
    undone_at         = DateTimeField(null=True)
    correction_text   = TextField(blank=True)   # what user would have said
    correction_reason = CharField(blank=True)   # tone | facts | length | other
```

### UI behavior

On the Inbox / Conversations screen:
- Auto-sent replies appear with a green "AI sent" badge + a "Was this right?" inline action
- "Was this right?" expands a small form: ✅ Yes / ✏️ I would have said this instead → free-text + reason dropdown
- The form is editable until `can_undo_until`; after that the reply is "in the wild" and only the correction-without-undo flow remains

### Undo semantics by platform

| Platform | Real undo possible? | What we do |
|---|---|---|
| WhatsApp | Yes (delete-for-everyone within 2 hours) | Call delete API; mark `undone_at` |
| Instagram comments | No (delete comment is permanent) | Call delete-comment API; mark `undone_at` |
| Instagram DMs | Delete-for-me only | Mark `undone_at` locally; warn user the recipient still sees it |
| Facebook comments | Yes (delete comment) | Call delete-comment API; mark `undone_at` |
| LinkedIn comments | Yes (delete comment) | Call delete-comment API; mark `undone_at` |

### Learning signal

When `correction_text` is provided:
1. Stored on the conversation as a few-shot example (last 5 corrections
   are appended to the Engage Agent's system prompt for replies to that
   contact)
2. Aggregated weekly: if a brand has ≥ 3 corrections with reason="tone",
   the brand profile's `tone_attributes` get flagged for review in the
   Daily Brief
3. Fed into Adapt Agent v2 (W3-4) as a signal — corrections lower the
   weight of the LLM patterns that produced them

## Platform scope for v2

| Platform | Comments | DMs | Notes |
|---|---|---|---|
| Instagram | ✅ | ✅ | Most volume for SMEs |
| Facebook | ✅ | ✅ | Page-managed only (not personal profiles) |
| LinkedIn | ✅ | ⚠️ later | DM API requires LinkedIn Sales Navigator scopes; defer |
| Twitter / X | ⚠️ later | ⚠️ later | API costs + lower SME volume; defer |
| TikTok | ❌ | ❌ | DM API is gated; comments only via webhook (defer) |
| WhatsApp | already shipped | already shipped | Existing pattern stays |

**v2 scope = IG + FB comments + DMs only.** LinkedIn DMs, Twitter, TikTok
are W2-followup items.

## Test plan

A test passes only if it asserts a routing decision based on the level +
confidence + safety rails.

### Unit tests
- `_route_reply(level=SUGGEST, confidence=0.99)` → `queue_for_review`
- `_route_reply(level=GRADUATED, confidence=0.86, safety_flags=[])` → `auto_send`
- `_route_reply(level=GRADUATED, confidence=0.86, safety_flags=["complaint"])` → `queue_for_review`
- `_route_reply(level=GRADUATED, confidence=0.49)` → `escalate`
- `_route_reply(level=AGGRESSIVE, confidence=0.71)` → `auto_send`
- `_route_reply(level=OFF, confidence=0.99)` → `queue_for_review` (never auto)

### Plan tier tests
- Starter user setting `engage_autonomy_level=GRADUATED` → 403 / form error
- Growth user setting `engage_autonomy_level=AGGRESSIVE` → 403
- Agency user setting any level → 200

### Migration tests
- Existing user with `auto_engage=True` migrates to `SUGGEST` (NOT graduated)
- Existing user with `auto_engage=False` migrates to `OFF`

### Safety rail tests
- Reply > 400 chars → blocked regardless of confidence
- Intent "complaint" → blocked
- Reply mentioning "refund" → blocked

### Undo loop tests
- Auto-sent reply creates EngageReply with `can_undo_until = sent_at + 5min`
- User submits correction within window → `undone_at` set + correction stored
- User submits correction after window → no undo, correction still stored

## Rollout

1. Land code behind a settings flag `ENGAGE_GRADUATED_AUTONOMY_ENABLED`
   (default False) so prod isn't auto-replying day one
2. Enable on internal test accounts (Kawaida, Nyama, Mara) for 7 days
3. Audit: zero false-positive auto-sends out of 100 graduated decisions
4. Enable flag globally
5. Email users who had `auto_engage=True` informing them they need to
   manually upgrade from SUGGEST to GRADUATED to get auto-send

## What this spec deliberately does NOT cover

- LinkedIn DMs (scope deferred)
- Twitter / TikTok (scope deferred)
- Multi-language detection beyond what's already on WhatsApp (its
  `_detect_language` ports over but isn't extended)
- The Adapt Agent's learning loop integration (corrections feed it but
  the consumer side is W3-4 work, not W2)
- A new "Inbox" page split between AI-handled / Needs-you — that's W3-4
  Phase 1 work but logically depends on this spec landing first

## Acceptance criteria (when is W2 done?)

- [ ] `engage_autonomy_level` field exists, migrated cleanly
- [ ] `_route_reply()` helper used by all incoming-message handlers
- [ ] IG, FB comments + DMs all go through `_route_reply`
- [ ] Safety rails enforced
- [ ] `EngageReply` table + undo UI working on 1 platform end-to-end (Facebook chosen — has full delete API)
- [ ] Plan-tier gating enforced on the Settings form
- [ ] Tests cover routing, tier gating, migration, safety, undo
- [ ] Settings flag default False; internal test users opted in
- [ ] Master Plan checkboxes W2.1 → W2.7 ticked

## File-level work plan

| Step | File | Change |
|---|---|---|
| W2.1 | `apps/agents/engage_agent.py` | Add confidence to LLM JSON schema for social (already on WhatsApp); add `_route_reply()` helper |
| W2.2 | `apps/accounts/models.py` + migration | Add `engage_autonomy_level` enum field; deprecate `auto_engage` |
| W2.3 | `apps/engage/tasks.py` (or wherever incoming handlers live) | Call `_route_reply()` instead of always queuing |
| W2.4 | `apps/accounts/forms.py` settings form | Plan-tier-gated dropdown |
| W2.5 | New `apps/engage/models.py:EngageReply` + UI | Undo + correction form |
| W2.6 | Data migration in W2.2 | auto_engage → engage_autonomy_level |
| W2.7 | `tests/test_engage_autonomy.py` | New file, ~12 tests covering acceptance criteria |
