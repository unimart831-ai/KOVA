# Kova Agent — Admin Dashboard Plan

### Complete Platform Management Dashboard (Beyond Django Admin)

**Planning Document | April 2026**

---

## Why We Need This

Django's built-in admin panel is designed for developers — raw database tables, no charts, no real-time data, no business intelligence. Kova needs a dashboard built for **platform operators** — the person watching the business run, diagnosing issues, understanding user behavior, and making decisions.

### What Django Admin Can't Do

| Need | Django Admin | Custom Dashboard |
|------|-------------|-----------------|
| See revenue trends over time | ❌ Raw payment rows | ✅ Charts, MRR calculation, cohort analysis |
| Watch AI agents in real-time | ❌ AgentAction table scroll | ✅ Live agent activity feed with success/fail rates |
| Understand content pipeline health | ❌ Post table with 8 status filters | ✅ Visual pipeline: seeds → drafts → scheduled → published → metrics |
| Spot failing infrastructure | ❌ Nothing | ✅ Celery task health, queue depth, error rates |
| See user journey | ❌ Separate tables | ✅ Single user view: profile → content → billing → agents → engagement |
| Business intelligence | ❌ Counts only | ✅ KPIs, trends, funnel conversion, retention |

---

## Architecture Decision

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Django views + DRF API endpoints | Already in the stack. No new dependencies. |
| **Frontend** | Django templates + HTMX + Tailwind + Chart.js | Consistent with existing UI. No React/Vue overhead. |
| **Real-time updates** | HTMX polling (every 30-60s) | Simple. Channels already installed for future WebSocket upgrade. |
| **Charts** | Chart.js (already in package.json) | Lightweight, well-documented, no new dependencies. |
| **Tables** | HTML tables with HTMX sorting/filtering/pagination | Match existing patterns in the codebase. |

### Access Control

| Role | Access | Implementation |
|------|--------|---------------|
| **Superadmin** | Full dashboard — all users, all data, all controls | `is_superuser=True` |
| **Staff** | Read-only dashboard — view data, no destructive actions | `is_staff=True` |
| **Regular users** | No access — redirected to their own dashboard | Default |

**Middleware check:** All `/admin-dashboard/` routes require `is_staff=True`. A decorator handles this.

---

## Dashboard Structure — The Complete Map

### Navigation Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  KOVA ADMIN DASHBOARD                          [Staff Name] [↗] │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│  📊 Overview │  [Main Content Area]                             │
│  👥 Users    │                                                  │
│  📝 Content  │                                                  │
│  🤖 Agents   │                                                  │
│  📱 Platforms│                                                  │
│  💬 Engage   │                                                  │
│  📈 Analytics│                                                  │
│  💰 Billing  │                                                  │
│  ⚙️ System   │                                                  │
│  📋 Logs     │                                                  │
│              │                                                  │
├──────────────┤                                                  │
│  QUICK STATS │                                                  │
│  Users: 342  │                                                  │
│  Posts: 12.4K│                                                  │
│  MRR: $2,450 │                                                  │
│  Agents: ✅  │                                                  │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## Page 1: Overview Dashboard (Home)

**URL:** `/admin-dashboard/`
**Purpose:** The single screen that tells you if everything is healthy in under 10 seconds.

### Top Row — Key Business Metrics (Cards)

| Card | Data Source | Display |
|------|-----------|---------|
| **Total Users** | `User.objects.count()` | Number + 7-day trend arrow (↑12%) |
| **Active Users (7d)** | Users with posts/seeds in last 7 days | Number + percentage of total |
| **Monthly Recurring Revenue** | Calculated from active subscriptions × plan prices | MRR in USD + KES |
| **Posts Published (Today)** | `Post.objects.filter(status='published', published_at__date=today)` | Number + comparison to yesterday |
| **Agent Success Rate (24h)** | `AgentAction` completed vs failed in last 24h | Percentage with red/green indicator |
| **Active Celery Tasks** | Redis queue inspection | Queue depth + worker status |

### Mid Row — Trend Charts (Chart.js)

**Chart 1: User Growth (Line chart, 30 days)**
- X-axis: Date
- Y-axis: Cumulative users
- Lines: Total users, Active users, Paying users

**Chart 2: Content Pipeline (Stacked bar, 7 days)**
- X-axis: Date
- Stacked bars: Seeds submitted → Posts generated → Posts published → Posts failed
- Shows pipeline throughput per day

**Chart 3: Revenue (Line chart, 30 days)**
- X-axis: Date
- Y-axis: Revenue (KES)
- Lines: M-Pesa payments, Stripe payments, Total MRR
- Annotation: Plan tier breakdown (pie chart overlay)

### Bottom Row — Activity Feeds

**Live Agent Activity (last 20 actions)**

| Time | Agent | User | Action | Status | Tokens |
|------|-------|------|--------|--------|--------|
| 2m ago | Create | user@email.com | Generated 3 posts from seed | ✅ Completed | 2,400 |
| 5m ago | Engage | user@email.com | Processed 8 interactions | ✅ Completed | 1,200 |
| 12m ago | Research | user@email.com | Found 6 trending topics | ✅ Completed | 3,100 |
| 15m ago | Create | other@email.com | Content generation | ❌ Failed | 0 |

*HTMX auto-refreshes every 30 seconds.*

**Recent Alerts**

| Priority | Alert | Time |
|----------|-------|------|
| 🔴 HIGH | Post publish failed for @user — Facebook token expired | 3m ago |
| 🟡 MEDIUM | Celery worker queue depth > 50 tasks | 10m ago |
| 🟢 LOW | New user signup: business@example.com | 15m ago |

---

## Page 2: User Management

**URL:** `/admin-dashboard/users/`
**Purpose:** Complete visibility into every user — their journey, content, billing, and agents.

### User List Table

| Column | Source | Features |
|--------|--------|----------|
| Email | `User.email` | Sortable, searchable |
| Name | `User.full_name` | Sortable |
| Company | `UserProfile.company_name` | Searchable |
| Industry | `UserProfile.industry` | Filterable (dropdown) |
| Plan | `UserProfile.plan` | Filterable (dropdown), color-coded badge |
| Status | Computed: trial/active/past_due/canceled | Filterable, color-coded |
| Social Accounts | `SocialAccount.objects.filter(user=user, is_active=True).count()` | Number |
| Posts Published | `Post.objects.filter(user=user, status='published').count()` | Number |
| Joined | `User.date_joined` | Sortable |
| Last Active | Last AgentAction or Post created | Sortable |

**Filters sidebar:**
- Plan tier (Starter / Growth / Pro / Agency)
- Subscription status (Trialing / Active / Past Due / Canceled / None)
- Industry
- Joined date range
- Has connected platforms (Yes / No)
- Onboarding completed (Yes / No)

**Bulk actions:**
- Export to CSV
- Send notification to selected users

### User Detail Page

**URL:** `/admin-dashboard/users/<uuid>/`

**Tab 1: Profile**
- All UserProfile fields (read + editable)
- Brand voice, audience, pillars, goals
- Account settings: timezone, daily brief time, auto-approve, auto-engage
- Quick actions: Reset password, Deactivate account, Change plan

**Tab 2: Content**
- Seeds submitted: count, list with status
- Posts by status: draft / approved / scheduled / published / failed / rejected
- Content DNA summary: most-used formats, tones, hooks
- Top performing posts: sorted by engagement_rate
- Publishing timeline chart

**Tab 3: Social Accounts**
- Connected platforms: platform, username, status, token expiry
- Quick actions: Force token refresh, Disconnect
- Error log if any platform has `last_error`

**Tab 4: Agents**
- Agent configs: which agents active, custom instructions
- Agent activity log: filtered to this user
- Token usage summary: total tokens consumed per agent, per day/week/month
- Agent performance: success rate, average duration

**Tab 5: Billing**
- Current plan + subscription status
- Trial end date
- Payment history (M-Pesa and Stripe)
- Billing events
- Revenue from this user (total, monthly)
- Quick actions: Extend trial, Change plan, Issue refund

**Tab 6: Engagement**
- Interactions: total, by type, by sentiment
- Superfans identified for this user
- Auto-reply rate
- Flagged interactions

**Tab 7: Briefs**
- Daily briefs history
- Read/unread status
- Brief quality (trending topics found, recommendations made)

---

## Page 3: Content Management

**URL:** `/admin-dashboard/content/`
**Purpose:** See every piece of content across all users — pipeline health, quality, failures.

### Content Pipeline Overview

```
SEEDS                    POSTS                      PUBLISHED
┌──────────┐     ┌──────────────────┐     ┌──────────────────┐
│ New: 12   │ → → │ Draft: 45        │ → → │ Published: 8,421 │
│ Processing│     │ Pending: 23      │     │ Failed: 156      │
│ Complete: │     │ Approved: 18     │     │                  │
│ Failed: 3 │     │ Scheduled: 31    │     │                  │
└──────────┘     └──────────────────┘     └──────────────────┘
```

### Content Seeds Table

| Column | Source | Features |
|--------|--------|----------|
| User | `ContentSeed.user` | Searchable |
| Idea (truncated) | `ContentSeed.idea[:80]` | Expandable |
| Status | `ContentSeed.status` | Filterable, color-coded |
| Target Platforms | `ContentSeed.target_platforms` | Platform icons |
| Posts Generated | `seed.posts.count()` | Number |
| Created | `ContentSeed.created_at` | Sortable |
| Error | `ContentSeed.error_message` | Shown if failed |

### Posts Table (The Main Table)

| Column | Source | Features |
|--------|--------|----------|
| User | `Post.user` | Searchable |
| Platform | `Post.social_account.platform` | Filterable (icon) |
| Content (truncated) | `Post.content_text[:100]` | Expandable |
| Status | `Post.status` | Filterable, color-coded |
| Type | `Post.content_type` | Filterable |
| Agent | `Post.generated_by_agent` | Filterable |
| Predicted Score | `Post.predicted_engagement_score` | Sortable |
| Actual Engagement | `post.metrics.engagement_rate` | Sortable |
| Scheduled | `Post.scheduled_at` | Sortable |
| Published | `Post.published_at` | Sortable |

**Filters:** Status, Platform, Agent, Content type, Date range, User, Predicted score range

### Post Detail (Modal or Page)

- Full content text
- Media attachments
- AI reasoning + angle + framework
- Content DNA tags (format, tone, hook type, etc.)
- Predicted vs actual engagement
- Platform post URL (link to live post)
- Full seed → posts → metrics lifecycle view

### Content Analytics Section

**Chart 1: Posts by Status (Donut chart)**
- Draft, Approved, Scheduled, Published, Failed, Rejected breakdown

**Chart 2: Publishing Volume (Bar chart, 30 days)**
- Posts published per day, colored by platform

**Chart 3: Content DNA Analysis (Heatmap)**
- Rows: Format types (story, list, hot_take, meme, etc.)
- Columns: Tone types (inspirational, humorous, educational, etc.)
- Cell color: Average engagement rate for that combo
- Shows which content formulas work best across all users

**Chart 4: Predicted vs Actual Engagement (Scatter plot)**
- X: Predicted score, Y: Actual engagement rate
- Shows how accurate the Analyst Agent's predictions are
- Trendline shows calibration quality

### Failed Content Section

Dedicated view showing all failed seeds and posts with:
- Error messages
- Failure timestamps
- Which user was affected
- Retry actions
- Pattern detection (e.g., "80% of failures are token-related")

---

## Page 4: Agent Operations

**URL:** `/admin-dashboard/agents/`
**Purpose:** Monitor all 6 AI agents across all users — health, performance, cost, errors.

### Agent Health Grid

```
┌─────────────────┬─────────────────┬─────────────────┐
│  🟢 CREATE      │  🟢 ANALYST     │  🟢 RESEARCH    │
│  Success: 98.2% │  Success: 99.1% │  Success: 97.5% │
│  Runs (24h): 84 │  Runs (24h): 84 │  Runs (24h): 12 │
│  Avg: 4.2s      │  Avg: 2.1s      │  Avg: 8.4s      │
│  Tokens: 42K    │  Tokens: 18K    │  Tokens: 36K    │
├─────────────────┼─────────────────┼─────────────────┤
│  🟢 ADAPT       │  🟢 ENGAGE      │  🟡 STRATEGIST  │
│  Success: 99.8% │  Success: 96.3% │  Success: 91.2% │
│  Runs (24h): 31 │  Runs (24h): 48 │  Runs (24h): 3  │
│  Avg: 1.8s      │  Avg: 6.7s      │  Avg: 12.3s     │
│  Tokens: 8K     │  Tokens: 52K    │  Tokens: 28K    │
└─────────────────┴─────────────────┴─────────────────┘

Status: 🟢 > 95% success | 🟡 80-95% | 🔴 < 80%
```

### Agent Action Log (Global)

| Column | Source | Features |
|--------|--------|----------|
| Timestamp | `AgentAction.created_at` | Sortable |
| Agent | `AgentAction.agent_type` | Filterable (tabs) |
| User | `AgentAction.user.email` | Searchable |
| Action | `AgentAction.action_type` | Filterable |
| Status | `AgentAction.status` | Filterable, color-coded |
| Duration | `AgentAction.duration_ms` | Sortable |
| Tokens | `AgentAction.tokens_used` | Sortable |
| Error | `AgentAction.error_message` | Shown if failed |

**Tabs:** All | Create | Analyst | Research | Adapt | Engage | Strategist

### Agent Performance Charts

**Chart 1: Agent Success Rate Over Time (Line chart, 30 days)**
- One line per agent type
- Y-axis: success rate %
- Helps spot degradation trends

**Chart 2: Token Consumption (Stacked area, 30 days)**
- Stacked by agent type
- Y-axis: tokens consumed per day
- Shows cost trends

**Chart 3: Agent Duration Distribution (Box plot)**
- One box per agent
- Shows median, p50, p95, p99 response times
- Detects slow agents

**Chart 4: Agent Errors by Type (Bar chart)**
- Group errors by category: LLM timeout, API error, token expired, rate limited, parsing error
- Helps prioritize engineering fixes

### Token Economics Section

| Metric | Calculation | Display |
|--------|------------|---------|
| **Total tokens (today)** | Sum of `AgentAction.tokens_used` today | Number |
| **Total tokens (this month)** | Sum for current month | Number |
| **Estimated LLM cost (today)** | tokens × model pricing | USD amount |
| **Estimated LLM cost (this month)** | Monthly total | USD amount |
| **Cost per user** | Total cost / active users | USD amount |
| **Cost per post** | Total cost / posts generated | USD amount |
| **Most expensive agent** | Ranked by total tokens | Agent name + tokens |
| **Most expensive user** | Ranked by total tokens | User email + tokens |

### Agent Configuration Overview

Table showing all users' agent configs:

| User | Create | Analyst | Research | Adapt | Engage | Strategist | Custom Instructions? |
|------|--------|---------|----------|-------|--------|------------|---------------------|
| user@a.com | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | Yes (Create) |
| user@b.com | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | No |

---

## Page 5: Platform Management

**URL:** `/admin-dashboard/platforms/`
**Purpose:** Monitor all connected social accounts — OAuth health, token status, publishing success.

### Connected Accounts Overview

| Metric | Display |
|--------|---------|
| Total connected accounts | Number per platform (pie chart) |
| Active accounts | Number with `is_active=True` |
| Expiring tokens (next 24h) | Count + list — urgent attention needed |
| Accounts with errors | Count + list of `last_error` |

### Platform Accounts Table

| Column | Source | Features |
|--------|--------|----------|
| User | `SocialAccount.user` | Searchable |
| Platform | `SocialAccount.platform` | Filterable (icon) |
| Username | `SocialAccount.username` | Searchable |
| Active | `SocialAccount.is_active` | Filterable, toggle |
| Token Expires | `SocialAccount.token_expires_at` | Sortable, color-coded (red if <24h) |
| Last Error | `SocialAccount.last_error` | Shown if present |
| Last Synced | `SocialAccount.last_synced_at` | Sortable |
| Connected | `SocialAccount.connected_at` | Sortable |
| Posts Published | `post count with status=published` | Number |

**Quick Actions per Account:**
- Force token refresh
- Test connection (publish test → delete)
- Deactivate
- Clear error

### Platform Health Summary

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Twitter  │ Instagram│ Facebook │ TikTok   │ LinkedIn │
│ ────────── │────────── │────────── │────────── │──────────│
│ Accts: 45│ Accts: 52│ Accts: 38│ Accts: 23│ Accts: 31│
│ Active:43│ Active:48│ Active:35│ Active:22│ Active:29│
│ Errors: 2│ Errors: 4│ Errors: 3│ Errors: 1│ Errors: 2│
│ Pub/wk:89│ Pub/wk:72│ Pub/wk:45│ Pub/wk:34│ Pub/wk:28│
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

### Publishing Success Rate by Platform (Chart)

- Bar chart: success vs failure per platform (last 7 days)
- Helps identify if a specific platform's API is problematic

---

## Page 6: Engagement Management

**URL:** `/admin-dashboard/engagement/`
**Purpose:** Monitor community management across all users — interactions, sentiment, superfans.

### Engagement Overview Cards

| Card | Data |
|------|------|
| **Total Interactions (7d)** | Count of Interactions in last 7 days |
| **Sentiment Breakdown** | Positive / Neutral / Negative percentages (donut) |
| **Auto-Reply Rate** | Interactions with `status=AI_REPLIED` / total |
| **Flagged Items** | Count needing human attention |
| **Superfans (total)** | Count by tier (Rising / Loyal / Superfan) |

### Interaction Feed (All Users)

| Column | Source |
|--------|--------|
| Time | `Interaction.created_at` |
| User | `Interaction.user` |
| Platform | `Interaction.social_account.platform` |
| Type | `Interaction.interaction_type` |
| Author | `Interaction.author_name` |
| Content (truncated) | `Interaction.content` |
| Sentiment | `Interaction.sentiment` — color-coded |
| Status | `Interaction.status` |
| AI Reply | `Interaction.ai_suggested_reply` — expandable |

**Filters:** Sentiment, Status, Type, Platform, User, Date range

### Sentiment Trend (Chart)

Line chart over 30 days:
- Lines: Positive %, Neutral %, Negative %
- Helps spot brand-wide sentiment shifts

### Superfan Leaderboard

| Username | User (Brand) | Tier | Interactions | Platforms | Last Sentiment |
|----------|-------------|------|-------------|-----------|---------------|
| @campus_techie | Unimart Africa | Loyal | 12 | Twitter, Instagram | Positive |

---

## Page 7: Analytics & Intelligence

**URL:** `/admin-dashboard/analytics/`
**Purpose:** Platform-wide performance intelligence — content DNA patterns, competitor insights, metrics.

### Performance Metrics Overview

**Chart 1: Total Engagement Across All Users (Line chart, 30 days)**
- Lines: Impressions, Likes, Comments, Shares
- Shows platform health

**Chart 2: Average Engagement Rate by Platform (Bar chart)**
- Bars: Twitter, Instagram, Facebook, TikTok, LinkedIn, etc.
- Average engagement_rate from PostMetric

**Chart 3: Content DNA Leaderboard**
- Table showing top 10 content DNA attribute combinations ranked by average engagement
- e.g., `story + inspirational + bold_claim_hook` → avg 8.4/10
- Aggregated across ALL users — platform-wide intelligence

### Competitor Intelligence Summary

| Metric | Data |
|--------|------|
| Total Competitors Tracked | Count across all users |
| Analyses Run (30d) | CompetitorAnalysis count |
| Insights Generated | CompetitorInsight count (unacted) |
| Top Insight Types | Breakdown by type (content_gap, trend_ahead, etc.) |

### Post Metrics Distribution

**Chart:** Histogram of `PostMetric.engagement_rate` across all published posts
- Shows what "normal" engagement looks like
- Helps set benchmarks

---

## Page 8: Billing & Revenue

**URL:** `/admin-dashboard/billing/`
**Purpose:** Complete financial picture — revenue, subscriptions, payments, churn.

### Revenue Dashboard

| Card | Calculation |
|------|-----------|
| **MRR (Monthly Recurring Revenue)** | Sum of active subscriptions × plan price (USD) |
| **MRR (KES)** | Same in Kenyan Shillings |
| **ARR (Annual Run Rate)** | MRR × 12 |
| **Total Revenue (All Time)** | Sum of completed MpesaPayments + Stripe payments |
| **Revenue This Month** | Payments completed this calendar month |
| **Average Revenue Per User (ARPU)** | MRR / paying users |

### Subscription Breakdown

| Plan | Users | Revenue/mo (KES) | Revenue/mo (USD) | % of MRR |
|------|-------|------------------|-------------------|----------|
| Starter (KES 299) | [count] | [amount] | [amount] | [%] |
| Growth (KES 999) | [count] | [amount] | [amount] | [%] |
| Pro (KES 1,999) | [count] | [amount] | [amount] | [%] |
| Agency (KES 2,999) | [count] | [amount] | [amount] | [%] |
| **Trial** | [count] | 0 | 0 | — |
| **Free/None** | [count] | 0 | 0 | — |
| **TOTAL** | [count] | [amount] | [amount] | 100% |

### Revenue Charts

**Chart 1: MRR Growth (Line chart, 12 months or all time)**
- X-axis: Month
- Y-axis: MRR (USD)
- Shows growth trajectory

**Chart 2: Plan Distribution (Donut chart)**
- Segments: Starter, Growth, Pro, Agency, Trial

**Chart 3: Payment Success Rate (Bar chart, 30 days)**
- M-Pesa: completed vs failed vs expired
- Stripe: succeeded vs failed
- Shows payment infrastructure health

**Chart 4: Churn Analysis (Line chart)**
- Monthly churn rate: (canceled subscriptions / total at start of month)
- Trial conversion rate: (converted / expired trials)

### Payments Table

| Column | Source |
|--------|--------|
| Date | `MpesaPayment.created_at` or `BillingEvent.created_at` |
| User | User email |
| Provider | M-Pesa / Stripe |
| Amount | `MpesaPayment.amount` |
| Plan | `MpesaPayment.plan_tier` |
| Status | Completed / Failed / Pending / Expired |
| Receipt | `MpesaPayment.receipt_number` |
| Phone | `MpesaPayment.phone_number` (masked: 254***789) |
| Renewal? | `MpesaPayment.is_renewal` |

**Filters:** Provider, Status, Plan tier, Date range, User

### Subscription Lifecycle

| Metric | Count | Percentage |
|--------|-------|-----------|
| Active subscriptions | [n] | |
| In trial | [n] | |
| Trial → Paid conversion (30d) | [n] | [%] |
| Past due (grace period) | [n] | |
| Canceled (30d) | [n] | |
| Reactivated (30d) | [n] | |

### Billing Events Log

Full audit trail from `BillingEvent` model — every Stripe webhook and M-Pesa callback, processed/unprocessed status, errors.

---

## Page 9: System Health

**URL:** `/admin-dashboard/system/`
**Purpose:** Infrastructure monitoring — Celery, Redis, database, task queues, errors.

### System Status Cards

| Component | Health Check | Display |
|-----------|-------------|---------|
| **Web Server** | Always healthy if page loads | 🟢 Online |
| **Database** | `connection.ensure_connection()` | 🟢 Connected / 🔴 Down |
| **Redis** | `cache.get("health")` or broker ping | 🟢 Connected / 🔴 Down |
| **Celery Worker** | Check heartbeat via `app.control.inspect().active()` | 🟢 Running / 🔴 Stopped |
| **Celery Beat** | Check last beat tick | 🟢 Running / 🟡 Stale / 🔴 Stopped |

### Celery Task Monitor

**Scheduled Tasks (from Beat)**

| Task | Schedule | Last Run | Next Run | Last Status | Last Duration |
|------|----------|----------|----------|-------------|---------------|
| check-and-publish-due-posts | every 60s | 30s ago | in 30s | ✅ | 1.2s |
| run-engage-cycle | every 30m | 12m ago | in 18m | ✅ | 45s |
| fetch-all-recent-metrics | every 6h | 2h ago | in 4h | ✅ | 23s |
| run-daily-research | every 12h | 5h ago | in 7h | ✅ | 1m 12s |
| run-strategy-cycle | every 8h | 3h ago | in 5h | ✅ | 2m 8s |
| generate-daily-briefs | every 15m | 8m ago | in 7m | ✅ | 15s |
| refresh-expiring-tokens | every 30m | 22m ago | in 8m | ✅ | 3s |
| check-mpesa-subscriptions | daily | 14h ago | in 10h | ✅ | 5s |
| analyze-all-competitors | weekly | 3d ago | in 4d | ✅ | 4m 32s |

### Task Queue Depth

| Queue | Pending | Active | Reserved | Failed (24h) |
|-------|---------|--------|----------|-------------|
| default | [n] | [n] | [n] | [n] |
| high_priority | [n] | [n] | [n] | [n] |

### Error Tracking

**Recent Errors (Last 24h)**

| Time | Task / View | User | Error Type | Message (truncated) |
|------|------------|------|-----------|---------------------|
| 2m ago | publish_post | user@a.com | FacebookAPIError | Token expired for page... |
| 15m ago | generate_from_seed | user@b.com | LLMTimeoutError | OpenRouter timeout after 30s... |

**Error Trend (Chart):** Errors per hour over last 48 hours. Spot spikes.

### Database Stats

| Metric | Value |
|--------|-------|
| Total Users | [n] |
| Total Posts | [n] |
| Total Interactions | [n] |
| Total Agent Actions | [n] |
| Database size | [MB] |
| Largest table | [table name + row count] |

### LLM Provider Status

| Provider | Model | Status | Avg Latency | Errors (24h) |
|----------|-------|--------|-------------|-------------|
| OpenRouter | deepseek/deepseek-v3.2 | 🟢 | 2.1s | 0 |
| Together.ai | FLUX.1-krea-dev (Growth) | 🟢 | 5.2s | 0 |
| Together.ai | FLUX.1.1-pro (Pro/Agency) | 🟢 | 6.8s | 0 |
| HuggingFace | FLUX.1-schnell (fallback) | 🟢 | 8.1s | 2 |
| Pollinations | flux (last resort) | 🟢 | 9.5s | 0 |

### Image Generation Configuration (LLM Overview Tab)

Configurable from Admin Dashboard → LLM Config → Image Generation Configuration:

| Setting | Description | Default |
|---------|-------------|---------|
| **Image Enabled** | Global kill-switch for all image generation | ✅ On |
| **Default Provider** | Primary image provider | Together.ai |
| **Default Model** | Fallback model if plan config missing | FLUX.1-schnell |
| **Per-Plan Model Routing** | Which FLUX model each plan uses | Starter→schnell, Growth→krea-dev, Pro/Agency→FLUX.1.1-pro |
| **Fallback Chain** | Ordered provider list if primary fails | Together → HuggingFace → Pollinations |

### Image Generation Stats (Cost Economics Page)

New image stats bar on Cost Economics dashboard:

| Metric | Source | What It Shows |
|--------|--------|--------------|
| **Images Generated (30d)** | `Post.media_status = "generated"` | Total AI images created |
| **Failed** | `Post.media_status = "failed"` | Generation failures |
| **Pending** | `Post.media_status = "pending"` | Currently queued |
| **Image Cost (30d)** | Per-plan count × PLAN_IMAGE_COST | Actual estimated spend |
| **Avg Cost/Image** | Total cost ÷ generated count | Blended rate across plans |

---

## Page 10: Logs & Audit Trail

**URL:** `/admin-dashboard/logs/`
**Purpose:** Searchable log of everything that's happened in the system.

### Unified Activity Log

Every significant event in one chronological stream:

| Time | Category | User | Event | Details |
|------|----------|------|-------|---------|
| 2m ago | Agent | user@a.com | Create Agent: generated 3 posts | Seed: "Launch announcement" |
| 5m ago | Billing | user@b.com | M-Pesa payment completed | KES 999, Growth plan |
| 8m ago | Content | user@a.com | Post published to Twitter | Post ID, URL |
| 12m ago | Auth | new@user.com | New user registered | Via email |
| 15m ago | Platform | user@c.com | Facebook token refreshed | Expires in 60d |
| 20m ago | System | — | Celery Beat tick | 3 tasks dispatched |

**Filters:** Category, User, Date range, Search text

### Export Capabilities

- Export any log or table as CSV
- Date range filtering for all exports
- Useful for: investor reporting, debugging, compliance

---

## Implementation Plan

### App Structure

```
apps/
  admin_dashboard/
    __init__.py
    apps.py
    urls.py
    views/
      __init__.py
      overview.py       # Home dashboard
      users.py          # User management
      content.py        # Content pipeline
      agents.py         # Agent operations
      platforms.py       # Platform management
      engagement.py     # Engagement monitoring
      analytics.py      # Analytics & intelligence
      billing.py        # Revenue & billing
      system.py         # Infrastructure health
      logs.py           # Audit trail
    templatetags/
      __init__.py
      dashboard_tags.py # Custom template tags (format numbers, badges, etc.)
    middleware.py       # Staff-only access enforcement
    utils.py            # Shared calculations (MRR, churn, etc.)
    context_processors.py # Sidebar stats

templates/
  admin_dashboard/
    base.html           # Dashboard layout (sidebar + topbar)
    overview.html
    users/
      list.html
      detail.html
    content/
      list.html
      seeds.html
      failed.html
    agents/
      overview.html
      log.html
    platforms/
      list.html
    engagement/
      overview.html
    analytics/
      overview.html
    billing/
      overview.html
      payments.html
    system/
      health.html
      tasks.html
      errors.html
    logs/
      activity.html
    components/          # Reusable HTMX partials
      stat_card.html
      chart_container.html
      data_table.html
      pagination.html
      filters.html
      badge.html
      alert_feed.html
```

### URL Structure

```python
# apps/admin_dashboard/urls.py
app_name = 'admin_dashboard'

urlpatterns = [
    # Overview
    path('', views.overview, name='overview'),

    # Users
    path('users/', views.user_list, name='user_list'),
    path('users/<uuid:pk>/', views.user_detail, name='user_detail'),
    path('users/<uuid:pk>/change-plan/', views.user_change_plan, name='user_change_plan'),
    path('users/<uuid:pk>/extend-trial/', views.user_extend_trial, name='user_extend_trial'),
    path('users/export/', views.user_export_csv, name='user_export'),

    # Content
    path('content/', views.content_overview, name='content_overview'),
    path('content/seeds/', views.seed_list, name='seed_list'),
    path('content/posts/', views.post_list, name='post_list'),
    path('content/posts/<uuid:pk>/', views.post_detail, name='post_detail_admin'),
    path('content/failed/', views.failed_content, name='failed_content'),
    path('content/dna/', views.content_dna, name='content_dna'),

    # Agents
    path('agents/', views.agent_overview, name='agent_overview'),
    path('agents/log/', views.agent_log, name='agent_log'),
    path('agents/tokens/', views.token_economics, name='token_economics'),
    path('agents/configs/', views.agent_configs, name='agent_configs'),

    # Platforms
    path('platforms/', views.platform_overview, name='platform_overview'),
    path('platforms/accounts/', views.platform_accounts, name='platform_accounts'),
    path('platforms/<uuid:pk>/refresh/', views.force_token_refresh, name='force_refresh'),

    # Engagement
    path('engagement/', views.engagement_overview, name='engagement_overview'),
    path('engagement/interactions/', views.interaction_list, name='interaction_list'),
    path('engagement/superfans/', views.superfan_list, name='superfan_list'),

    # Analytics
    path('analytics/', views.analytics_overview, name='analytics_overview'),
    path('analytics/content-dna/', views.content_dna_analysis, name='content_dna_analysis'),
    path('analytics/competitors/', views.competitor_overview, name='competitor_overview'),

    # Billing
    path('billing/', views.billing_overview, name='billing_overview_admin'),
    path('billing/payments/', views.payment_list, name='payment_list'),
    path('billing/subscriptions/', views.subscription_list, name='subscription_list'),
    path('billing/events/', views.billing_event_list, name='billing_event_list'),
    path('billing/export/', views.billing_export_csv, name='billing_export'),

    # System
    path('system/', views.system_health, name='system_health'),
    path('system/tasks/', views.celery_tasks, name='celery_tasks'),
    path('system/errors/', views.error_log, name='error_log'),
    path('system/database/', views.database_stats, name='database_stats'),

    # Logs
    path('logs/', views.activity_log, name='activity_log'),
    path('logs/export/', views.log_export_csv, name='log_export'),

    # HTMX Partials
    path('_partials/stat-cards/', views.partial_stat_cards, name='partial_stat_cards'),
    path('_partials/activity-feed/', views.partial_activity_feed, name='partial_activity_feed'),
    path('_partials/agent-health/', views.partial_agent_health, name='partial_agent_health'),
    path('_partials/revenue-chart/', views.partial_revenue_chart, name='partial_revenue_chart'),
]
```

### Data Points Summary

Every data point the dashboard accesses:

| Model | Records Displayed | Aggregations |
|-------|------------------|-------------|
| **User** | List, detail, count, growth | Daily signups, active rate, retention |
| **UserProfile** | Plan, industry, subscription status | Plan distribution, churn |
| **Post** | List, detail, pipeline counts | By status, by platform, by agent, by DNA |
| **ContentSeed** | List, status counts | Success rate, throughput |
| **SocialAccount** | List, token health | By platform, error rate |
| **AgentConfig** | Config grid per user | Activation rates |
| **AgentAction** | Log, health metrics | Success rate, duration, tokens, by type |
| **PostMetric** | Engagement data | Avg by platform, by DNA, distribution |
| **Interaction** | Feed, sentiment | Volume, sentiment trend, auto-reply rate |
| **Superfan** | Leaderboard | Tier distribution |
| **Competitor** | List, analysis status | Coverage |
| **CompetitorAnalysis** | Analysis log | Analysis frequency |
| **CompetitorInsight** | Insight list | By type, acted-on rate |
| **DailyBrief** | Brief list, read status | Read rate, generation success |
| **Notification** | Count, read rate | Volume, type distribution |
| **MpesaPayment** | Payment log, amounts | Revenue, success rate, plan breakdown |
| **BillingEvent** | Audit trail | Event volume, error rate |
| **MediaAttachment** | Media count, storage | Storage usage |
| **Celery Beat** | Task schedules, last run | Task health, queue depth |

**Total: 20 models × multiple views = 100% system coverage**

---

## Build Phases

### Phase 1: Foundation + Overview (First Build)

| Task | Details | Estimate |
|------|---------|----------|
| Create `admin_dashboard` app | App config, middleware, URL registration | Small |
| Dashboard base template | Sidebar, topbar, layout, Tailwind styling | Medium |
| Overview page | 6 stat cards, 3 charts, activity feed, alerts | Medium |
| Staff access middleware | Decorator + middleware for `is_staff` check | Small |

**Deliverable:** A working home dashboard with key metrics at a glance.

### Phase 2: Users + Content

| Task | Details |
|------|---------|
| User list with search/filter/sort | Paginated table with HTMX |
| User detail (7 tabs) | Complete user profile view |
| Content pipeline overview | Seed → Post → Publish funnel view |
| Post list with filters | Status, platform, agent, date range |
| Content DNA analysis page | Engagement heatmap by DNA attributes |
| Failed content view | Error diagnosis table |

**Deliverable:** Full user management + content visibility.

### Phase 3: Agents + Platforms

| Task | Details |
|------|---------|
| Agent health grid | 6-agent status cards with success rates |
| Agent action log | Searchable, filterable log |
| Token economics | Cost calculations and charts |
| Platform accounts table | Token health, publishing stats |
| Platform health summary | Per-platform success rates |

**Deliverable:** Agent monitoring + platform infrastructure visibility.

### Phase 4: Billing + Engagement

| Task | Details |
|------|---------|
| Revenue dashboard | MRR, ARR, ARPU calculations |
| Subscription breakdown table | Plan distribution, status counts |
| Payment logs | M-Pesa + Stripe transactions |
| Churn analysis | Trial conversion, cancellation rates |
| Engagement overview | Sentiment trends, auto-reply rates |
| Superfan leaderboard | Cross-user superfan view |

**Deliverable:** Financial intelligence + community health.

### Phase 5: System + Logs

| Task | Details |
|------|---------|
| System health checks | DB, Redis, Celery, LLM provider status |
| Celery task monitor | Beat schedule, last run, queue depth |
| Error log | Aggregated errors with pattern detection |
| Unified activity log | Cross-model chronological feed |
| CSV export endpoints | For users, payments, logs |

**Deliverable:** Infrastructure monitoring + audit trail.

---

## Summary

| Metric | Coverage |
|--------|---------|
| **Pages** | 10 main pages + detail views |
| **Models covered** | 20/20 (100%) |
| **Views needed** | ~40 view functions |
| **Templates needed** | ~30 templates + 10 partials |
| **Charts** | ~15 Chart.js visualizations |
| **Tables** | ~12 data tables with search/filter/sort |
| **HTMX partials** | ~8 auto-refreshing components |
| **New dependencies** | 0 (uses existing stack: Django + HTMX + Tailwind + Chart.js) |

**Every piece of data in the system — every user, post, agent action, payment, interaction, metric, competitor insight, brief, notification, and Celery task — is visible, searchable, and actionable from this dashboard.**

---

*Plan ready. Awaiting approval to begin Phase 1 implementation.*
