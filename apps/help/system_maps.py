"""
System flow maps — founder daily reference.
Each map includes audit notes + a Mermaid diagram (print-friendly via /help/system-maps/).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemMap:
    slug: str
    title: str
    nav_group: str
    print_order: int
    summary: str
    audit: list[str]
    diagram: str
    daily_tip: str = ""
    tags: list[str] = field(default_factory=list)


SYSTEM_MAPS: list[SystemMap] = [
    SystemMap(
        slug="founder-daily-routine",
        title="Founder Daily Routine",
        nav_group="Daily",
        print_order=1,
        summary="What to open every morning in ~5 minutes.",
        daily_tip="Start at Brief → approve Studio → glance Queue. Everything else is exception handling.",
        tags=["daily", "print-first"],
        audit=[
            "Daily Brief auto-generates every 15 min once local brief time passes (briefs/tasks.py).",
            "Brief aggregates: pipeline counts, Research cache, Analyst performance, Engage stats, products, revenue.",
            "Quick actions deep-link to Studio (pending), Queue (failed), Engage inbox.",
            "User still approves posts unless auto_approve_posts=True on UserProfile.",
        ],
        diagram="""
flowchart TB
  subgraph morning["Every morning — 5 min"]
    B[Home / Daily Brief]
    S[Studio — approve drafts]
    Q[Queue — failed / scheduled]
  end
  subgraph exceptions["Only when alerted"]
    E[Engage Inbox]
    W[WhatsApp Inbox]
    L[Leads hot list]
  end
  B --> S --> Q
  B -.->|alert| E
  B -.->|alert| W
  B -.->|alert| L
""",
    ),
    SystemMap(
        slug="create-to-schedule",
        title="Create → Schedule",
        nav_group="Create",
        print_order=2,
        summary="How content enters the system and lands in Queue / Calendar.",
        daily_tip="Queue is the hub. Everything creative flows here before publish.",
        tags=["daily", "print-first", "core"],
        audit=[
            "Campaigns tab = Voice Campaign UI (/content/voice-campaign/), not /campaigns/ CRUD.",
            "Email Marketing + A/B Tests exist but are secondary paths into posts/queue.",
            "Voice Campaign, Studio, Autopilot all create ContentSeed → Post.",
            "Calendar is read-only schedule view; Queue is operational pipeline.",
            "Publish is automated every 5 min once post is approved + scheduled_at set.",
        ],
        diagram="""
flowchart LR
  subgraph hidden["Hidden until autonomous"]
    C[Campaigns tab]
    EM[Email Marketing]
    AB[A/B Tests]
  end
  subgraph create["Create — automated"]
    VC[Voice Campaign]
    ST[Studio]
    AP[Autopilot]
  end
  subgraph schedule["Schedule — should be passive"]
    CAL[Calendar]
    Q[Queue]
  end
  C -. "manual today · UTM only" .-> Q
  EM -. "manual today" .-> Q
  AB -. "manual today" .-> Q
  VC --> Q
  ST --> Q
  AP --> Q
  Q --> CAL
""",
    ),
    SystemMap(
        slug="six-agent-loop",
        title="6-Agent Intelligence Loop",
        nav_group="Agents",
        print_order=3,
        summary="How the six marketing agents feed each other.",
        daily_tip="Research + Strategist feed Create. Analyst + Adapt close the loop after publish.",
        tags=["daily", "print-first", "core"],
        audit=[
            "Agents: Research, Create, Adapt, Engage, Analyst, Chief Strategist (agents/models.py).",
            "Research: every 12h — trends, optional auto-seed (max 1/12h).",
            "Strategist: every 8h — proactive ContentSeeds + brief narrative.",
            "Engage: every 30min — fetch, analyze, draft replies (auto-send gated by env flag).",
            "Adapt v2 learning: every 12h — profile mutations gated by ADAPT_AGENT_V2_ENABLED.",
            "Emergency pause on UserProfile halts all autonomous agent actions.",
        ],
        diagram="""
flowchart TB
  R[Research Agent] --> CR[Create Agent]
  ST[Strategist Agent] --> CR
  CR --> P[Posts published]
  P --> AN[Analyst Agent]
  AN --> AD[Adapt Agent]
  AD --> CR
  P --> EN[Engage Agent]
  EN --> AN
  CR --> BR[Daily Brief]
  ST --> BR
""",
    ),
    SystemMap(
        slug="daily-brief",
        title="Home / Daily Brief",
        nav_group="Home",
        print_order=4,
        summary="How the morning briefing is built and what actions do.",
        audit=[
            "Task: briefs.generate_all_daily_briefs every 15 min.",
            "Gathers pipeline, Research cache, analyze_performance, engagement report, products, revenue.",
            "LLM writes Strategist-voice narrative → DailyBrief model.",
            "brief_action creates ContentSeed ONLY — does not auto-run Create Agent.",
            "Holiday drafts from calendar_intel surface here for approval.",
        ],
        diagram="""
flowchart TB
  subgraph beat["Celery — every 15 min"]
    T[generate_all_daily_briefs]
  end
  subgraph gather["_gather_brief_data"]
    P[Pipeline counts]
    RS[Research cache]
    AN[Analyst performance]
    EG[Engage report]
  end
  T --> gather --> LLM[Strategist LLM narrative]
  LLM --> DB[(DailyBrief)]
  DB --> UI[Home /brief/]
  UI -->|brief_action| SEED[ContentSeed]
  SEED -. "manual: open Studio" .-> ST[Studio generate]
""",
    ),
    SystemMap(
        slug="studio-approval",
        title="Studio → Approve → Publish",
        nav_group="Create",
        print_order=5,
        summary="The default human-in-the-loop content path.",
        audit=[
            "submit_seed → ContentSeed → generate_from_seed → run_create_agent.",
            "Default: Post status pending_approval (auto_approve_posts=False).",
            "approve_post / batch_approve sets schedule → approved/scheduled.",
            "check_and_publish_due_posts every 5 min → publish_post to platforms.",
            "Smart auto-approve possible after 15+ reviewed posts at 80%+ approval rate.",
        ],
        diagram="""
flowchart LR
  subgraph input["Input"]
    IDEA[User idea / voice / brief seed]
  end
  subgraph gen["Automated"]
    SEED[ContentSeed]
    CA[Create Agent]
    IMG[Image gen async]
  end
  subgraph human["Manual today — default"]
    ST[Studio review]
    OK[Approve / edit / reject]
  end
  subgraph pub["Passive schedule"]
    SCH[Adapt: schedule time]
    BEAT[Publish beat 5 min]
    LIVE[Platform APIs]
  end
  IDEA --> SEED --> CA --> ST
  CA --> IMG
  ST --> OK --> SCH --> BEAT --> LIVE
""",
    ),
    SystemMap(
        slug="autopilot-week",
        title="Autopilot Weekly Plan",
        nav_group="Create",
        print_order=6,
        summary="Two-step weekly content planning.",
        audit=[
            "Requires autopilot_enabled on UserProfile.",
            "Step 1: plan_weekly_autopilot → WeeklyContentPlan PENDING_REVIEW.",
            "Step 2: User clicks autopilot_approve → execute_autopilot_plan.",
            "Creates seeds, runs Create Agent; auto-schedules only if auto_approve_posts.",
            "Weekly review email via send_autopilot_review_emails daily check.",
        ],
        diagram="""
flowchart TB
  BEAT[Weekly beat: plan_weekly_autopilot] --> PLAN[WeeklyContentPlan PENDING_REVIEW]
  PLAN --> UI[Autopilot dashboard]
  UI -->|user approves| EXEC[execute_autopilot_plan]
  EXEC --> SEEDS[ContentSeeds created]
  SEEDS --> CA[Create Agent]
  CA -->|auto_approve_posts| Q[Queue scheduled]
  CA -->|default| ST[Studio pending]
""",
    ),
    SystemMap(
        slug="voice-campaigns",
        title="Voice Campaigns & Campaigns App",
        nav_group="Create",
        print_order=7,
        summary="AI campaign builder from prompt or voice memo.",
        audit=[
            "Sidebar 'Campaigns' → /content/voice-campaign/ (VoiceBrief UI).",
            "Hidden /campaigns/ app: Campaign CRUD + ai_build — linked from voice flow.",
            "build_campaign_from_prompt → Campaign + seeds → generate_from_seed.",
            "Can optionally create EmailCampaign alongside social posts.",
        ],
        diagram="""
flowchart LR
  VC[Voice Campaign UI] --> VB[VoiceBrief / prompt]
  VB --> AI[campaigns.ai_build_campaign]
  AI --> C[Campaign record]
  C --> SEED[ContentSeeds]
  SEED --> POSTS[Posts → Queue]
  C -.-> EC[EmailCampaign optional]
""",
    ),
    SystemMap(
        slug="memes-visual-publisher",
        title="Memes & Visual Publisher",
        nav_group="Create",
        print_order=8,
        summary="Parallel create paths that bypass Studio seeds.",
        audit=[
            "Visual Publisher: media_queue.process_queues every 5 min when queue enabled.",
            "Upload photos → AI captions → Post generated_by_agent=media_queue.",
            "Memes: discover every 3h, adapt every 4h; user approves before to-post.",
            "Memes gated by plan memes_enabled (Pro+).",
        ],
        diagram="""
flowchart TB
  subgraph vp["Visual Publisher"]
    UP[Upload media queue] --> CAP[AI captions]
    CAP --> PUB[publish_post]
  end
  subgraph memes["Memes & Trends"]
    DISC[discover_trending_memes] --> ADAPT[adapt_memes_for_users]
    ADAPT --> REV[User approve]
    REV --> POST[Post → Queue]
  end
""",
    ),
    SystemMap(
        slug="engage-inbox",
        title="Engage Inbox",
        nav_group="Customers",
        print_order=9,
        summary="Social comments, DMs, AI drafts, optional auto-send.",
        audit=[
            "PRO gate: engagement_agent plan limit.",
            "run_engage_cycle every 30 min: fetch → analyze → generate_replies → auto_respond.",
            "Default engage_autonomy_level=suggest — user approves in inbox.",
            "ENGAGE_GRADUATED_AUTONOMY_ENABLED=False blocks actual platform auto-send.",
            "auto_sent_list allows undo/correct for AI-sent replies.",
        ],
        diagram="""
flowchart LR
  BEAT[Engage beat 30 min] --> FETCH[Fetch interactions]
  FETCH --> AN[Analyze sentiment]
  AN --> DRAFT[Generate replies]
  DRAFT --> ROUTE{engage_autonomy_level}
  ROUTE -->|suggest default| INBOX[Inbox — manual send]
  ROUTE -->|auto + env flag| SEND[Platform auto-send]
  SEND --> UNDO[Auto-sent undo/correct]
""",
    ),
    SystemMap(
        slug="whatsapp-customers",
        title="WhatsApp",
        nav_group="Customers",
        print_order=10,
        summary="WhatsApp inbox, status, broadcasts, sequences.",
        audit=[
            "PRO gate: whatsapp_enabled.",
            "Webhook → handle_incoming_message → AI reply (toggle per conversation).",
            "Status Studio: daily status queue generation.",
            "Broadcasts + sequences processed every 30 min.",
            "Channel curation every 6h.",
        ],
        diagram="""
flowchart TB
  WH[WhatsApp webhook] --> IN[Inbox]
  IN --> AI{AI enabled?}
  AI -->|yes| REPLY[Auto draft/send]
  AI -->|no| MAN[Manual reply]
  SS[Status Studio] --> SQ[Daily status queue]
  BC[Broadcasts] --> PROC[Processor 30 min]
  SEQ[Sequences] --> PROC
""",
    ),
    SystemMap(
        slug="leads-nurture",
        title="Leads & Nurture",
        nav_group="Customers",
        print_order=11,
        summary="CRM, scoring, automated nurture sequences.",
        audit=[
            "Lead sources: links forms, kova_page, WhatsApp, QR, bookings, manual.",
            "process_nurture_steps every 30 min advances enrollments.",
            "score_all_leads daily with auto-enroll into sequences.",
            "Nurture can trigger email steps via emails app.",
        ],
        diagram="""
flowchart LR
  subgraph sources["Lead sources"]
    LF[Link forms]
    KP[Kova Page]
    WA[WhatsApp]
    QR[QR / walk-in]
  end
  sources --> LEAD[(Lead)]
  LEAD --> SCORE[Daily scoring]
  SCORE --> NUR[Nurture sequences 30 min]
  NUR --> EMAIL[Email steps]
""",
    ),
    SystemMap(
        slug="email-marketing",
        title="Email Marketing",
        nav_group="Customers",
        print_order=12,
        summary="Tenant email campaigns, lists, sequences.",
        audit=[
            "auto_email_marketing flag on UserProfile gates automation.",
            "process_email_sequences 30 min; process_scheduled_campaigns 15 min.",
            "sync_leads_to_subscribers daily.",
            "retry_pending_auto_campaigns every 6h for AI-drafted campaigns.",
            "Separate from public blog NewsletterSubscriber (help app).",
        ],
        diagram="""
flowchart TB
  subgraph auto["When auto_email_marketing ON"]
    WEL[Welcome bootstrap on onboarding]
    SEQ[Sequence processor 30 min]
    SCH[Scheduled campaigns 15 min]
  end
  subgraph manual["Manual today"]
    DASH[Email dashboard]
    CAMP[Create campaign]
    SEND[Send / schedule]
  end
  LEADS[Lead sync daily] --> LISTS[Subscriber lists]
  DASH --> CAMP --> SEND
  WEL --> SEQ
""",
    ),
    SystemMap(
        slug="bookings-loop",
        title="Bookings",
        nav_group="Customers",
        print_order=13,
        summary="Public booking links → confirmations → reviews.",
        audit=[
            "Owner creates BookingLink → public /book/slug/.",
            "Booking default confirmed; WhatsApp notifications via signals.",
            "Attribution FKs to post/campaign/QR stored on Booking.",
            "Review requests after completion (reviews app — task exists, not in beat).",
        ],
        diagram="""
flowchart LR
  BL[BookingLink setup] --> PUB[/book/slug/ public]
  PUB --> BK[Booking confirmed]
  BK --> WA[WhatsApp notify]
  BK --> ATTR[Attribution stored]
  BK --> REV[Review request — manual trigger today]
""",
    ),
    SystemMap(
        slug="products-commerce",
        title="Commerce & Snap to Sell",
        nav_group="Business",
        print_order=14,
        summary="Catalog, public shops, M-Pesa payments, Shopify/marketplace sync, Snap to Sell.",
        audit=[
            "Snap to Sell: photo → vision AI → Product + content seeds async.",
            "auto_promote_products daily creates seeds for under-promoted products.",
            "check-stock-alerts daily.",
            "Marketplace sync via partner API → Product source=marketplace.",
        ],
        diagram="""
flowchart LR
  SNAP[Snap to Sell photo] --> AI[Vision AI task]
  AI --> PROD[(Product)]
  PROD --> PROM[auto_promote daily]
  PROM --> SEED[ContentSeed → Studio/Queue]
  STOCK[Stock alerts daily] --> NOTIFY[Notifications]
""",
    ),
    SystemMap(
        slug="revenue-attribution",
        title="Revenue & Attribution",
        nav_group="Business",
        print_order=15,
        summary="Conversions, Shopify, M-Pesa commerce, pixel.",
        audit=[
            "Shopify + M-Pesa webhooks → Conversion records.",
            "Multi-touch ConversionJourney + touchpoints.",
            "Kova Pixel: WebsiteEvent tracking on customer sites.",
            "Monthly report emails via beat; dashboard read-mostly.",
        ],
        diagram="""
flowchart TB
  subgraph inputs["Conversion inputs"]
    SH[Shopify webhook]
    MP[M-Pesa commerce]
    PX[Kova Pixel events]
    QR[QR / walk-in]
  end
  inputs --> CONV[(Conversion)]
  CONV --> REV[Revenue dashboard]
  CONV --> ATTR[Attribution dashboard]
""",
    ),
    SystemMap(
        slug="links-kova-page",
        title="Links & Kova Page",
        nav_group="Business",
        print_order=16,
        summary="Two public page systems for capture.",
        audit=[
            "Links app: /k/slug/ link-in-bio — KovaPage, forms → leads.",
            "Kova Page: /p/slug/ from UserProfile — conversion page.",
            "Both manual setup; clicks/views tracked.",
            "Form submissions can create Lead records.",
        ],
        diagram="""
flowchart LR
  subgraph links["Links /k/"]
    LP[Link page builder] --> PUBK[Public /k/slug/]
    PUBK --> FORM[Form submit → Lead]
  end
  subgraph kpage["Kova Page /p/"]
    PROF[UserProfile page settings] --> PUBP[Public /p/slug/]
    PUBP --> LEAD[Contact → Lead]
  end
""",
    ),
    SystemMap(
        slug="insights-competitors",
        title="Insights & Competitors",
        nav_group="Business",
        print_order=17,
        summary="Performance analytics and competitive intel.",
        audit=[
            "fetch_all_recent_metrics every 6h.",
            "analyze-all-competitors weekly.",
            "detect_top_performers daily → PerformanceRecycle → email drafts.",
            "Competitor tracking plan-gated.",
            "Content Intelligence sub-tab at /analytics/intelligence/.",
        ],
        diagram="""
flowchart LR
  MET[Metrics fetch 6h] --> INS[Insights dashboard]
  INS --> DNA[Content DNA / Analyst]
  COMP[Competitor analyze weekly] --> BRIEF[Surfaces in Brief]
  TOP[Top performers daily] --> REC[Recycle email drafts]
""",
    ),
    SystemMap(
        slug="onboarding-first-value",
        title="Signup → Onboarding → First Value",
        nav_group="Foundation",
        print_order=18,
        summary="New user path from signup to draft posts + brief.",
        audit=[
            "OnboardingMiddleware gates app until onboarding_completed.",
            "finish_onboarding: trial, AgentConfigs, welcome email, intelligence chain.",
            "run_onboarding_intelligence: research → seeds → create (force pending) → welcome brief.",
            "Step 3 platforms optional; publishing gated until connect.",
            "Returning users land on brief:home.",
        ],
        diagram="""
flowchart TB
  SU[Signup / Google OAuth] --> PATH[Path choice]
  PATH --> WIZ[Wizard steps 1-3 brand]
  WIZ --> FIN[finish_onboarding]
  FIN --> INT[run_onboarding_intelligence]
  INT --> POSTS[Draft posts in Studio]
  INT --> BRIEF[Welcome DailyBrief]
  POSTS --> VAL[First value: approve in Studio]
""",
    ),
    SystemMap(
        slug="platforms-agents-settings",
        title="Platforms, Agents & Settings",
        nav_group="Settings",
        print_order=19,
        summary="Foundation controls for the whole system.",
        audit=[
            "Platforms: OAuth connect; refresh_expiring_tokens every 30 min.",
            "Agents control: toggle each agent; activity log.",
            "AI Learning: revert/pause Adapt v2 mutations.",
            "Profile Health audits nightly; Calendar Intel holiday watcher daily.",
            "Emergency pause stops all agent autonomy.",
        ],
        diagram="""
flowchart TB
  PLAT[Platforms OAuth] --> TOK[Token refresh 30 min]
  PLAT --> PA[Profile Health audit daily]
  AG[Agent toggles] --> LOOP[6-agent loops]
  SET[UserProfile flags] --> FLAGS[auto_approve / autopilot / engage level]
  PAUSE[Emergency pause] --> STOP[Halts agents]
""",
    ),
    SystemMap(
        slug="billing-plan-gates",
        title="Billing & Plan Gates",
        nav_group="Settings",
        print_order=20,
        summary="Trial, M-Pesa, and feature enforcement.",
        audit=[
            "14-day trial on onboarding finish.",
            "M-Pesa STK primary; check_mpesa_subscriptions daily.",
            "PlanEnforcementMiddleware gates: engage, whatsapp, memes, competitors, teams, limits.",
            "Downgrade pauses scheduled posts.",
        ],
        diagram="""
flowchart LR
  TRIAL[14-day trial] --> PAY[M-Pesa checkout]
  PAY --> ACT[activate_subscription]
  ACT --> PLAN[Plan limits unlocked]
  PLAN --> MW[PlanEnforcementMiddleware]
  MW --> FEAT[Feature gates app-wide]
""",
    ),
    SystemMap(
        slug="hidden-surfaces",
        title="Hidden Surfaces (Founder's Cut)",
        nav_group="Reference",
        print_order=21,
        summary="Features reachable by URL but not primary sidebar.",
        audit=[
            "/campaigns/ — Campaign CRUD (not sidebar; voice-campaign is).",
            "/content/ab-tests/ — A/B tests.",
            "/calendar/preferences/ — Calendar Intel (not content calendar).",
            "/profile-health/ — Profile audits.",
            "/analytics/pixel/ — Kova Pixel setup.",
            "/reviews/ — Review requests (Brief actions).",
            "WhatsApp templates/channels — sub-routes under WhatsApp.",
        ],
        diagram="""
flowchart TB
  subgraph hidden["Not in primary nav"]
    C1[/campaigns/ CRUD]
    AB[/content/ab-tests/]
    CI[Calendar Intel prefs]
    PH[Profile Health]
    PX[Analytics Pixel]
    RV[Reviews]
  end
  hidden -.-> BRIEF[Linked from Brief / Settings / Platforms]
""",
    ),
    SystemMap(
        slug="celery-beat-schedule",
        title="Background Jobs (Celery Beat)",
        nav_group="Reference",
        print_order=22,
        summary="What runs without you clicking.",
        audit=[
            "5 min: publish due posts, media queues.",
            "15 min: daily briefs, scheduled email campaigns.",
            "30 min: engage cycle, nurture, email sequences, token refresh, WA broadcasts.",
            "6-12h: research, strategy, adapt, metrics, memes.",
            "Daily: stock alerts, auto-promote, holiday watcher, profile audits, lead scoring.",
            "Weekly: autopilot plan, competitor analysis.",
        ],
        diagram="""
flowchart TB
  subgraph fast["Every 5-15 min"]
    PUB[Publish posts]
    BRIEF[Daily Brief]
    EMAIL[Email campaigns]
  end
  subgraph medium["Every 30 min"]
    ENG[Engage]
    NUR[Lead nurture]
    TOK[OAuth refresh]
  end
  subgraph slow["6h - daily - weekly"]
    RES[Research 12h]
    STR[Strategy 8h]
    ADP[Adapt 12h]
    HOL[Holiday watcher daily]
    AUTO[Autopilot weekly]
  end
""",
    ),
]


def get_map(slug: str) -> Optional[SystemMap]:
    for m in SYSTEM_MAPS:
        if m.slug == slug:
            return m
    return None


def maps_by_group() -> dict[str, list[SystemMap]]:
    groups: dict[str, list[SystemMap]] = {}
    for m in sorted(SYSTEM_MAPS, key=lambda x: x.print_order):
        groups.setdefault(m.nav_group, []).append(m)
    return groups


def daily_print_maps() -> list[SystemMap]:
    """Maps tagged for daily wall print — pin these first."""
    daily = [m for m in SYSTEM_MAPS if "daily" in m.tags or "print-first" in m.tags]
    return sorted(daily, key=lambda x: x.print_order)
