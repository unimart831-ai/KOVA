# Adapt Agent v2 — Real Learning Loop Spec

> Phase 1 Weeks 3-4 of [KOVA_MASTER_PLAN.md](../KOVA_MASTER_PLAN.md).
> Written before code touches the agent. The contract is the spec.
>
> The third and biggest hollow promise. Today the Adapt Agent is a
> scheduler that only mutates `Post.scheduled_at`. The marketing claim is
> *"AI learns and adjusts — auto-promotes winners, retires losers."*
> This spec defines the v2 that makes that claim true.

---

## Goal

Close the third hollow promise. Today the Adapt Agent is a smart
scheduler. The marketing says it's an autonomous learning loop. v2
delivers an actual learning loop:

- **Reads** the user's last 30 days of posts + their content DNA + their
  engagement metrics
- **Decides** which content patterns are working and which aren't
- **Mutates** the user's profile (pillar weights, DNA preferences,
  retirement list, posting frequency) so the Create Agent's *next* posts
  are biased toward winners and away from losers
- **Surfaces** the changes in the Daily Brief in plain English
- **Audits** every mutation so it's reversible

If a user sixty days in opens Kova and asks "what has it learned about
me?" — the answer becomes specific: *"Your transformation Reels get 2.4×
your average. I'm posting more of them. Tuesday mornings outperform —
I've shifted your scheduling there. I retired the long-form testimonial
posts after 5 of them averaged 0.2% engagement."*

That answer is the product.

---

## What the loop reads (inputs)

For each eligible user, every 12h:

1. **Last 30 days of `Post` records** with `status="published"` and a
   non-empty `metrics` JSON (engagement rate calculated). Posts without
   metrics are skipped (not yet measured).
2. **Each post's `content_dna`** — already populated by the Analyst Agent
   at creation time. Shape: `{"format": "question", "tone": "inspirational",
   "topic": "success_story", "has_cta": true, "has_stats": true,
   "length": "short", "pillar": "Transformations"}`.
3. **Each post's `published_at`** — for hour-of-day / day-of-week
   correlations (preserves the legacy scheduling optimiser).
4. **The user's current `UserProfile`** — to know what to compare
   against and what to mutate.
5. **Existing `AgentAction` audit rows** — so a fresh cycle doesn't
   re-promote something already promoted last cycle.

## Eligibility gates (when the loop runs)

A user must pass **all three** to be processed:

| Gate | Threshold |
|---|---|
| Account age | ≥ 7 days since first published post |
| Sample size | ≥ 5 published posts in the last 30 days |
| Adapt enabled | `UserProfile.adapt_paused = False` (default False) |

A user who fails any gate gets logged as "skipped: not enough signal" /
"skipped: paused" and the cycle moves on.

---

## The five decisions Adapt v2 can make

### Decision 1 — PROMOTE a DNA combo

When a content-DNA attribute combination (e.g. `format=question` +
`tone=inspirational`) consistently outperforms the user's median, flag it
as a "preferred pattern" so the Create Agent biases future generations
toward it.

**Triggers when:** combo's mean engagement ≥ **1.5×** user median AND
≥ **3** posts use this combo in the window.

**Mutation:** `UserProfile.dna_preferences["promoted"]` appends
`{"combo": {...}, "boost": 1.5, "set_at": now}`.

**Cap:** at most **3 promotions per cycle**. Avoids thrashing on small
samples.

### Decision 2 — RETIRE a DNA combo

When a combo consistently underperforms, mark it as a "deprioritised
pattern" so the Create Agent excludes it.

**Triggers when:** combo's mean engagement < **0.5×** user median AND
≥ **5** posts use this combo (need more evidence to retire than promote
— false negative on a winner is fine, false positive on a "loser" loses
good content).

**Mutation:** `UserProfile.dna_preferences["retired"]` appends
`{"combo": {...}, "set_at": now}`.

**Cap:** at most **2 retirements per cycle**.

### Decision 3 — REWEIGHT pillars

When a content pillar (one of the user's `content_pillars`) is
consistently performing above or below their median, adjust its
rotation weight so the Strategist + Create agents pull from it more (or
less) often.

**Triggers when:**
- Pillar's mean engagement > **1.3× user median** AND ≥ 5 posts in pillar
  → weight bumps **+0.5** (cap at 2.0)
- Pillar's mean engagement < **0.7× user median** AND ≥ 5 posts in pillar
  → weight drops **-0.5** (floor at 0.2 — never to zero; full retirement
  is a Decision 2 thing)

**Mutation:** `UserProfile.pillar_weights[pillar_name]` updated.
Defaults to 1.0 for every pillar.

**Cap:** at most **2 pillar reweights per cycle**.

### Decision 4 — ADJUST posting frequency

When a user has been hitting their target cadence AND audience growth is
steady, bump it up. When they've been falling short AND engagement is
dropping, bump it down.

**Triggers when:**
- All 4 weeks in the window hit the user's `posting_frequency` target
  AND follower growth > 5% week-over-week 3 weeks running → **+1**
  posts/week (cap at 14)
- 3+ weeks missed the target AND engagement rate dropped 2 weeks running
  → **-1** post/week (floor at 1)

**Mutation:** `UserProfile.posting_frequency` updated.

**Cap:** at most **1 frequency change per cycle** (frequency changes
ripple through scheduling — slow them down).

### Decision 5 — SHIFT optimal posting hours (legacy v1 behaviour, preserved)

The existing Adapt v1 behaviour — aggregate engagement by hour-of-day +
day-of-week, recommend `best_hours` and `best_days` per platform. v2
keeps this intact. The only change: results are also persisted to
`UserProfile.optimal_schedule` (currently they're transient).

---

## Schema changes

Three new fields on `UserProfile`. One new column on `AgentAction` for
audit (or use existing `output_data` JSON).

```python
class UserProfile(models.Model):
    # ── Adapt Agent v2 (Phase 1 W3-4, May 2026) ──
    pillar_weights = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Per-pillar rotation weights (0.2-2.0, default 1.0). Adapt "
            "Agent v2 mutates these based on per-pillar engagement. The "
            "Strategist + Create agents pull from pillars proportionally."
        ),
    )
    dna_preferences = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Promoted / retired Content DNA patterns from the Adapt loop. "
            'Shape: {"promoted": [{"combo": {...}, "boost": 1.5, ...}, ...], '
            '"retired": [{"combo": {...}, "set_at": "..."}, ...]}'
        ),
    )
    optimal_schedule = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Per-platform optimal posting hours/days from Adapt v1's "
            'scheduling optimiser. Shape: {"instagram": {"best_hours": '
            '[9, 18], "best_days": ["mon", "tue"]}, ...}'
        ),
    )
    adapt_paused = models.BooleanField(
        default=False,
        help_text=(
            "If True, Adapt Agent v2 skips this user. Manual override for "
            "users who want to lock their settings in place."
        ),
    )
    adapt_last_run_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of the most recent Adapt cycle for this user.",
    )
```

Reusing existing `AgentAction` rows for the audit trail — no new table
needed. Each Adapt mutation creates an `AgentAction` with:
- `agent_type="adapt"`
- `action_type="promote_dna" | "retire_dna" | "reweight_pillar" | "adjust_frequency" | "shift_schedule"`
- `input_data` — the evidence (mean engagement, sample size, threshold)
- `output_data` — `{"field": "pillar_weights.Transformations", "before": 1.0, "after": 1.5}`

---

## Cadence

| What | When |
|---|---|
| `run-adapt-cycle` task | Every **12 hours** (Celery Beat) |
| Per-user limit | One full cycle per 12h. Skip if `adapt_last_run_at` is within 11h. |
| Eligibility gates | See above — most users skipped on day 1 |

The 12h cadence is a tradeoff: shorter would let it learn faster, longer
would let signals settle. 12h splits the difference and matches the
existing Engage cycle / Strategist cycle drum.

---

## Daily Brief surface

This is what makes "AI learns and adjusts" land for the user. The
Adapt Agent doesn't just mutate silently — every cycle that produces a
change writes a one-line summary into `revenue_attribution`'s sibling
slot for the next Daily Brief.

New field passed to the brief LLM context:

```python
"adapt_summary": {
    "changes_count": 2,
    "promotions": ["Transformations + question hook (2.4× your average)"],
    "retirements": ["Long-form testimonial (5 posts, 0.2% avg)"],
    "frequency_change": None,  # or "+1 posts/week"
    "pillar_changes": ["+0.5 weight on Transformations"],
}
```

LLM prompt instruction (replaces nothing — added as a new line near the
revenue_update line):

```
"adapt_update": If adapt_summary.changes_count > 0, ONE sentence
describing the most impactful change. Format: "I've started
[doing X] — [evidence]." If 0, return empty string. NEVER use
generic phrases like "I'm learning your style"; always name
specifics.
```

---

## Reversibility — the safety mechanism

Every mutation is audit-logged in `AgentAction` with `output_data`
carrying `{"field": ..., "before": ..., "after": ...}`. A user (or admin)
can revert any single change by:

1. Going to **Settings → AI Learning** (new page, simple list view)
2. Seeing recent Adapt actions with "Revert" buttons
3. Clicking Revert → writes the reverse mutation to the UserProfile and
   marks the original AgentAction as reverted

A **"Reset all Adapt mutations"** button at the bottom of that page
iterates every adapt AgentAction in reverse chronological order and
reverts each. Returns the user to their post-onboarding state.

**`adapt_paused = True`** stops future cycles without reverting past
mutations. Users who want "no more changes" but don't want to lose
learned wins use this.

---

## Safety rails — never auto-mutate when

1. **Sample size < threshold** — handled by the per-decision triggers
2. **The user's engagement is uniformly zero** — skip entire cycle (no
   median to compare against). Logged as "skipped: no signal."
3. **More than 10 mutations queued in the last 7 days** — circuit breaker.
   Pause Adapt for this user for 7 days, send a notification to the
   founder. Something is wrong with the data or the thresholds.
4. **A pillar has fewer than 2 posts in the window** — skip Decision 3
   for that pillar. Single posts are noise.
5. **A combo includes a retired-by-user pattern** — never auto-promote
   something the user explicitly killed.

---

## Out of scope for v2

These are real but deferred:

- Multi-user model — every user's loop runs independently. No
  cross-user pattern transfer (e.g. "salons in Nairobi all see X work").
  That's Adapt v3.
- A/B test orchestration — letting Adapt actively spin up new A/B tests
  to probe weak signals. Worth a future sprint but not this one.
- Competitor-aware decisions — using competitor performance data to
  weight pillars. Adapt v3.
- Time-of-week-specific DNA — "questions perform 2× on Tuesdays."
  Possible but increases dimensionality. Defer.
- LLM-driven mutation suggestions — for v2, all mutations are rule-based
  (deterministic, auditable). The LLM only writes the Daily Brief
  summary text.

---

## Acceptance criteria — when is W3-4 done?

- [ ] `run-adapt-cycle` Celery Beat task exists at 12h cadence
- [ ] `UserProfile` has `pillar_weights`, `dna_preferences`,
      `optimal_schedule`, `adapt_paused`, `adapt_last_run_at` (migrated cleanly)
- [ ] All 5 decision classes implemented + tested against the threshold
      table
- [ ] All 4 eligibility gates enforced
- [ ] Mutations land on `UserProfile` (verify in DB)
- [ ] Every mutation creates an `AgentAction` audit row with before/after
- [ ] Daily Brief context now includes `adapt_summary` AND the LLM
      prompt has the new `adapt_update` instruction
- [ ] **Create Agent prompt-builder reads `dna_preferences.promoted`** —
      biases generation toward those combos
- [ ] **Create Agent prompt-builder reads `dna_preferences.retired`** —
      excludes those combos
- [ ] **Strategist Agent** reads `pillar_weights` when choosing which
      pillar to draw from on a given cycle (weighted random)
- [ ] **Adapt v1 behaviour preserved** — `Post.scheduled_at` still gets
      set by the same scheduling logic (now reading from
      `UserProfile.optimal_schedule` instead of computing live)
- [ ] Reset Adapt page at `/accounts/settings/ai-learning/` with revert
      buttons + global reset button
- [ ] Tests cover: eligibility gates, all 5 decision triggers + caps,
      circuit breaker, revert, paused, brief data injection,
      Create/Strategist agents honouring mutations
- [ ] Master Plan checkboxes W3.1 → W3.11 ticked
- [ ] Rename in lifecycle docs from "Optimize posting times" to
      "Learning Loop"

---

## File-level work plan

| Step | File | Change |
|---|---|---|
| W3.1 | this doc | ✓ done |
| W3.2 | `config/settings/base.py` | New Celery Beat entry `run-adapt-cycle` every 12h |
| W3.3-4 | `apps/agents/adapt_agent.py` | Rewrite — eligibility gates + 5 decision functions, each pure given inputs |
| W3.5 | `apps/agents/adapt_agent.py` | `apply_mutations(user, decisions)` — atomic UserProfile updates + AgentAction audit logging |
| W3.6 | `apps/accounts/models.py` + migration | 5 new UserProfile fields |
| W3.7 | `apps/agents/strategist_agent.py` | Read `pillar_weights` when picking pillars |
| W3.7 | `apps/agents/create_agent.py` | Read `dna_preferences.promoted` and `.retired` when building system prompt |
| W3.8 | `apps/briefs/tasks.py` | Inject `adapt_summary` into brief context + add `adapt_update` LLM instruction |
| W3.9 | `apps/agents/adapt_agent.py` | Every mutation creates an `AgentAction` with before/after |
| W3.10 | `apps/accounts/views.py` + new template | `/accounts/settings/ai-learning/` page with revert / pause / reset |
| W3.11 | `tests/test_adapt_v2.py` | New file, ~20 tests covering acceptance criteria |
| Final | `docs/KOVA_LIFECYCLE.md` | Rename Adapt Agent role from "Optimize posting times" to "Learning loop — auto-promotes winning content patterns, retires losers" |

---

## Rollout

Like Engage v2, Adapt v2 lands behind a flag.

`settings.ADAPT_AGENT_V2_ENABLED` (default False) — when False, the new
cycle runs but **mutations are computed-and-logged only, never applied**.
That way the first week of deploy gives us a dataset of "what Adapt v2
WOULD have done" without changing user profiles. We audit those logs,
verify the thresholds are right, then flip the flag for internal test
users (Kawaida / Nyama / Mara), then global.

Two-stage rollout:

1. **Week 1 of W3-4 implementation:** code lands, flag False, internal
   test data accumulates
2. **Week 2:** review the dry-run logs against real outcomes; tune
   thresholds; flip flag on for internal users; observe 5 days; flip
   global

---

## What this spec deliberately does NOT cover

- The UI for the AI-Learning settings page (W3.10) — that's a sub-spec
  if the implementation reveals complexity. For now: a list of recent
  AgentAction rows with one-click revert.
- The LLM model choice for the brief's `adapt_update` line — uses the
  same brief-model the rest of the brief uses
- A "preview mode" for users to see proposed mutations before they
  apply — would be lovely UX, deferred to a later sprint
- Cross-pillar correlation (e.g. "transformations + questions" as a
  joint pattern) — Decision 1 already handles DNA combos which captures
  most of this
