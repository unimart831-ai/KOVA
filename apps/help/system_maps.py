"""
System flow maps — founder daily reference.
Each map includes audit notes + a Mermaid diagram (print-friendly via /help/system-maps/).
"""

from dataclasses import dataclass, field
from typing import Optional

from apps.help.mermaid_utils import sanitize_mermaid


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
    admin_links: list[tuple[str, str]] = field(default_factory=list)  # (label, admin_dashboard url name)

    def __post_init__(self) -> None:
        self.diagram = sanitize_mermaid(self.diagram)


TAB_ORDER: list[str] = [
    "Foundation",
    "Create",
    "Customers",
    "Business",
    "Partners",
    "Safety",
    "Admin",
    "Settings",
    "Agents",
    "Home",
    "Daily",
    "Reference",
]


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
            "Adapt v2 learning: every 12h — profile mutations live, gated per-plan by adapt_v2_enabled + circuit breaker.",
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
            "Levels: suggest (manual), assisted, auto — gated by ENGAGE_GRADUATED_AUTONOMY_ENABLED.",
            "auto_sent_list allows undo/correct for AI-sent replies.",
        ],
        admin_links=[
            ("Engage overview", "engagement_overview"),
            ("Interaction feed", "interaction_feed"),
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
            "Delivery status webhooks update message state.",
        ],
        admin_links=[
            ("WhatsApp overview", "whatsapp_overview"),
        ],
        diagram="""
flowchart TB
  WH[WhatsApp webhook] --> IN[Inbox]
  IN --> AI{"AI enabled?"}
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
  BL[BookingLink setup] --> PUB["/book/slug/ public"]
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
            "M-Pesa commerce webhooks → Conversion records → Revenue dashboard.",
        ],
        admin_links=[
            ("Products overview", "products_overview"),
            ("Revenue", "revenue_overview"),
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
        title="Onboarding & Auth",
        nav_group="Foundation",
        print_order=18,
        summary="Email signup, Facebook OAuth, phone capture, wizard, 7-day Starter trial, and first-value intelligence chain.",
        audit=[
            "Signup: email/password or Google OAuth (allauth) → OnboardingMiddleware gates app.",
            "Facebook signup/login: /accounts/facebook/signup/ connects Meta early (facebook_oauth.py).",
            "Phone capture: /accounts/onboarding/phone/ required before full app access.",
            "Wizard: brand steps → finish_onboarding (onboarding_flow.py) sets trialing + AgentConfigs.",
            "7-day Starter trial (MPESA_TRIAL_DAYS); Stripe trial for international checkout.",
            "run_onboarding_intelligence: research → seeds → create (force pending) → welcome brief.",
            "Step 3 platforms optional; publishing gated until SocialAccount connected.",
        ],
        admin_links=[
            ("Onboarding funnel", "onboarding_funnel"),
            ("Users", "user_list"),
        ],
        diagram="""
flowchart TB
  subgraph auth["Auth"]
    EM[Email signup]
    GO[Google OAuth]
    FB[Facebook OAuth signup]
  end
  auth --> PH[Phone capture]
  PH --> WIZ[Wizard brand steps]
  WIZ --> FIN[finish_onboarding]
  FIN --> TRIAL[7-day Starter trial]
  FIN --> INT[run_onboarding_intelligence]
  INT --> POSTS[Draft posts in Studio]
  INT --> BRIEF[Welcome DailyBrief]
  POSTS --> VAL[First value: approve in Studio]
""",
    ),
    SystemMap(
        slug="platforms-connect",
        title="Platforms Connect",
        nav_group="Foundation",
        print_order=19,
        summary="OAuth connect for Meta IG/FB, TikTok, LinkedIn, and WhatsApp. Tokens refresh every 30 min; plan limits cap account count.",
        audit=[
            "User UI: /platforms/ — connect per provider (KOVA_PLATFORM_SETUP_GUIDE.md).",
            "Meta (shared app): Facebook Pages + Instagram Business via instagram_facebook.py.",
            "TikTok: OAuth Content Posting API via tiktok.py.",
            "LinkedIn: OAuth Posts API via linkedin.py.",
            "WhatsApp: Cloud API or Embedded Signup via whatsapp.py provider.",
            "refresh_expiring_tokens Celery beat every 30 min.",
            "Plan v2 channel ladder: Starter 2, Growth 4 (no WA), Pro/Agency 5 incl. WhatsApp.",
        ],
        admin_links=[
            ("Platform overview", "platform_overview"),
            ("Connected accounts", "platform_accounts"),
        ],
        diagram="""
flowchart LR
  UI["/platforms/ UI"] --> META[Meta OAuth IG + FB]
  UI --> TT[TikTok OAuth]
  UI --> LI[LinkedIn OAuth]
  UI --> WA[WhatsApp Cloud / Embedded]
  META --> SA[(SocialAccount)]
  TT --> SA
  LI --> SA
  WA --> SA
  SA --> TOK[Token refresh 30 min]
  SA --> PUB[publish_post routing]
""",
    ),
    SystemMap(
        slug="platforms-agents-settings",
        title="Platforms, Agents & Settings",
        nav_group="Settings",
        print_order=20,
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
        title="Billing & Plan v2 Gates",
        nav_group="Settings",
        print_order=21,
        summary="7-day Starter trial, M-Pesa STK Push checkout, Stripe international, and PlanEnforcementMiddleware hard caps.",
        audit=[
            "Trial: 7-day Starter limits on finish_onboarding (MPESA_TRIAL_DAYS setting).",
            "M-Pesa: /billing/mpesa/checkout/ → STK Push → webhook → activate_subscription.",
            "Stripe: card checkout with trial for international users.",
            "PLAN_LIMITS in billing/models.py — authoritative caps (KOVA_BUILD_CHECKLIST.md).",
            "PlanEnforcementMiddleware gates: engage, whatsapp, memes, competitors, teams, posts/seeds/tokens.",
            "100% of any cap = hard block with upgrade message; downgrade pauses scheduled posts.",
            "Agency tier sales-only via AgencySalesInquiry contact form.",
        ],
        admin_links=[
            ("Billing overview", "billing_overview"),
            ("Subscriptions", "subscription_management"),
            ("Plan pricing", "plan_pricing"),
            ("Payments", "payment_list"),
        ],
        diagram="""
flowchart LR
  TRIAL[7-day Starter trial] --> PAY{Checkout}
  PAY -->|Kenya| MP[M-Pesa STK Push]
  PAY -->|Intl| ST[Stripe card]
  MP --> ACT[activate_subscription]
  ST --> ACT
  ACT --> PLAN[Plan v2 limits unlocked]
  PLAN --> MW[PlanEnforcementMiddleware]
  MW --> FEAT[Feature gates app-wide]
""",
    ),
    SystemMap(
        slug="hidden-surfaces",
        title="Hidden Surfaces (Founder's Cut)",
        nav_group="Reference",
        print_order=32,
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
    C1["/campaigns/ CRUD"]
    AB["/content/ab-tests/"]
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
        print_order=33,
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
    SystemMap(
        slug="content-pipeline",
        title="Content Pipeline",
        nav_group="Create",
        print_order=23,
        summary="End-to-end path: Studio seeds → Create Agent → Queue → approve → publish_post → platform metrics fetch.",
        audit=[
            "ContentSeed created from Studio, Autopilot, Voice Campaign, Brief action, Snap promote.",
            "generate_from_seed → run_create_agent → Post (pending_approval default).",
            "Queue (/content/queue/): approve_post sets approved/scheduled; batch approve supported.",
            "check_and_publish_due_posts every 5 min → publish_post → provider API.",
            "Content safety gate at approve + publish (CONTENT_SAFETY.md).",
            "fetch_all_recent_metrics every 6h → Insights / Analyst loop.",
        ],
        admin_links=[
            ("Content overview", "content_overview"),
            ("Posts", "post_list"),
            ("Seeds", "seed_list"),
            ("Failed content", "failed_content"),
        ],
        diagram="""
flowchart LR
  SEED[ContentSeed] --> CA[Create Agent]
  CA --> POST[Post pending]
  POST --> Q[Queue review]
  Q --> APP[approve_post]
  APP --> SCH[scheduled_at set]
  SCH --> BEAT[Publish beat 5 min]
  BEAT --> PUB[publish_post]
  PUB --> LIVE[Platform APIs]
  LIVE --> MET[Metrics fetch 6h]
""",
    ),
    SystemMap(
        slug="reels-stories-carousel",
        title="Reels, Stories & Carousel",
        nav_group="Create",
        print_order=24,
        summary="Format-specific publishing: motion reels (compose + upload), 9:16 Stories (Meta), multi-slide carousels.",
        audit=[
            "post_format routes publish: feed, reel, story, carousel (STORIES_PUBLISHING.md).",
            "Reels: compose_reel_video task → rupload to Meta/TikTok; retry_reel in Studio/Queue.",
            "Stories: Instagram STORIES container + FB photo_stories/video_stories APIs.",
            "Carousel: carousel_slides JSON; one image per slide; update_carousel_slides in Studio.",
            "Queue filter by format; same approve → publish_post pipeline.",
            "Reel music catalog managed in admin /dashboard/reel-music/.",
        ],
        admin_links=[
            ("Posts", "post_list"),
            ("Reel music", "reel_music_manage"),
        ],
        diagram="""
flowchart TB
  subgraph formats["Post formats"]
    FEED[Feed post]
    REEL[Reel — compose_reel_video]
    STORY[Story 9:16 — publish_story]
    CAR[Carousel slides]
  end
  formats --> Q[Queue approve]
  Q --> PUB[publish_post]
  PUB --> META[Meta IG/FB APIs]
  PUB --> TT[TikTok video]
  REEL --> RUP[rupload.facebook.com]
""",
    ),
    SystemMap(
        slug="reach-walk-in",
        title="REACH — QR & Walk-ins",
        nav_group="Customers",
        print_order=25,
        summary="Walk-in QR scan → attribution → Lead → nurture sequences → sales pipeline. Admin tracks QR codes and walk-in events.",
        audit=[
            "QR codes: owner creates tracked QR → public scan → WalkInEvent + Lead attribution.",
            "Lead sources include QR, walk-in, kova_page, WhatsApp, bookings, link forms.",
            "process_nurture_steps every 30 min advances enrollments.",
            "score_all_leads daily with auto-enroll into sequences.",
            "Admin: /dashboard/qr/ for walk-in stats; /dashboard/leads/ for pipeline.",
        ],
        admin_links=[
            ("QR overview", "qr_overview"),
            ("QR list", "qr_list"),
            ("Leads overview", "leads_overview"),
            ("Nurture", "leads_nurture"),
        ],
        diagram="""
flowchart LR
  QR[Tracked QR code] --> SCAN[Walk-in scan]
  SCAN --> WI[WalkInEvent]
  WI --> LEAD[(Lead)]
  LEAD --> SCORE[Daily scoring]
  SCORE --> NUR[Nurture 30 min]
  NUR --> PIPE[Pipeline / hot list]
  NUR --> EMAIL[Email steps]
""",
    ),
    SystemMap(
        slug="partners-marketplace",
        title="Partners & Marketplace",
        nav_group="Partners",
        print_order=26,
        summary="Marketplace Partner API: API key auth, seller provision, CSV import, self-serve join link, outbound webhooks.",
        audit=[
            "MarketplacePartner: API key (X-Kova-Partner-Key) created in admin; shown once.",
            "REST: /api/v1/partner/ — provision seller, sync products (UNIMART_VENDOR_ONBOARDING.md).",
            "provision_marketplace_seller → user account + welcome email + webhook.",
            "CSV import: import_sellers_csv / import_products_csv management + admin UI.",
            "Self-serve join: provision_vendor_self_serve for open/pending vendor signup.",
            "Webhook logs: /dashboard/partners/webhooks/.",
        ],
        admin_links=[
            ("Marketplaces", "marketplace_list"),
            ("Partner webhooks", "partners_webhook_logs"),
            ("Growth partners", "partners_overview"),
        ],
        diagram="""
flowchart TB
  ADMIN[Admin create MarketplacePartner] --> KEY[API key issued]
  KEY --> API["/api/v1/partner/ REST"]
  API --> PROV[provision_marketplace_seller]
  PROV --> USER[Kova user + plan]
  PROV --> WH[Outbound webhook]
  CSV[CSV import sellers/products] --> PROV
  JOIN[Self-serve join link] --> PROV
""",
    ),
    SystemMap(
        slug="growth-partners-referral",
        title="Growth Partners & Referrals",
        nav_group="Partners",
        print_order=27,
        summary="Referral program: partner applies, gets referral code, referred users sign up via ReferralMiddleware cookie.",
        audit=[
            "Partner application → admin approve → Partner record + referral_code.",
            "ReferralMiddleware captures ?ref= code on signup.",
            "Referral model tracks signed_up_at, activated_at, commission eligibility.",
            "Admin: /dashboard/partners/ — overview, applications, commissions, payouts.",
            "Separate from Marketplace Partner API (different Partner models).",
        ],
        admin_links=[
            ("Partners overview", "partners_overview"),
            ("Applications", "partner_applications"),
            ("Partner list", "partner_list"),
        ],
        diagram="""
flowchart LR
  APP[Partner application] --> REV[Admin review]
  REV --> PART[Partner + referral_code]
  PART --> LINK[?ref= signup link]
  LINK --> SIGN[New user signup]
  SIGN --> REF[(Referral record)]
  REF --> ACT[Activation on subscribe]
  ACT --> COMM[Commission tracking]
""",
    ),
    SystemMap(
        slug="agency-sales",
        title="Agency Sales Inquiries",
        nav_group="Partners",
        print_order=28,
        summary="Public Agency/Wakala contact form → AgencySalesInquiry → admin review and status workflow.",
        audit=[
            "Agency plan is sales-only (not public checkout) — KOVA_BUILD_CHECKLIST.md.",
            "Public form creates AgencySalesInquiry with status NEW.",
            "Admin: /dashboard/billing/sales-inquiries/ — list, filter, staff notes.",
            "Status workflow: NEW → CONTACTED → QUALIFIED → CLOSED/WON/LOST.",
            "Nav badge shows new inquiry count (admin_nav context processor).",
        ],
        admin_links=[
            ("Sales inquiries", "sales_inquiry_list"),
            ("Billing overview", "billing_overview"),
        ],
        diagram="""
flowchart LR
  FORM[Agency contact form] --> INQ[(AgencySalesInquiry NEW)]
  INQ --> ADMIN[Admin review]
  ADMIN --> CONTACT[Staff contacts prospect]
  CONTACT --> PLAN[Manual Agency plan grant]
  ADMIN --> STATUS[Status: WON / LOST]
""",
    ),
    SystemMap(
        slug="content-safety",
        title="Content Safety",
        nav_group="Safety",
        print_order=29,
        summary="Snap upload, post approval, and publish gates block policy violations before they reach platforms.",
        audit=[
            "CONTENT_SAFETY_ENABLED (default True in prod) — OpenRouter vision/text moderation.",
            "Gates: snap_launch, snap_to_sell_analyze, approve_post_for_user, publish_post.",
            "Blocked posts: status=blocked, never calls Meta; user sees policy message.",
            "ContentSafetyIncident audit log → admin review queue.",
            "Admin: dismiss, confirm violation, suspend user, pause auto-publish globally.",
        ],
        admin_links=[
            ("Safety overview", "content_safety_overview"),
            ("Review queue", "content_safety_review"),
        ],
        diagram="""
flowchart TB
  SNAP[Snap upload] --> CHK{Moderation check}
  CHK -->|safe| PROD[Product / content gen]
  CHK -->|unsafe| BLOCK1[Block upload]
  APP[approve_post] --> CHK2{Safety gate}
  CHK2 -->|unsafe| INC[ContentSafetyIncident]
  PUB[publish_post] --> CHK3{Final gate}
  CHK3 -->|unsafe| BLOCK2[Post blocked]
  INC --> ADMIN[Admin review queue]
  ADMIN --> ACT[Dismiss / suspend / pause publish]
""",
    ),
    SystemMap(
        slug="admin-dashboard-overview",
        title="Admin Dashboard",
        nav_group="Admin",
        print_order=30,
        summary="Staff-only /dashboard/ — user ops, content, billing, partners, system health, and this System Map reference.",
        audit=[
            "Entry: /dashboard/ overview with stat cards + activity feed (staff_required).",
            "Sections: Users, Content, Agents, Billing, Partners, Engage, WhatsApp, System.",
            "HTMX partials auto-refresh stat cards and agent health.",
            "Global search: /dashboard/search/ across users, posts, partners, sales inquiries.",
            "System Map tab documents all Kova workflows for internal ops.",
        ],
        admin_links=[
            ("Dashboard home", "overview"),
            ("Operations", "operations_overview"),
            ("System health", "system_health"),
            ("Global search", "global_search"),
        ],
        diagram="""
flowchart TB
  STAFF[Staff login] --> DASH["/dashboard/ overview"]
  DASH --> USR[Users + onboarding funnel]
  DASH --> CNT[Content + safety + agents]
  DASH --> BILL[Billing + sales inquiries]
  DASH --> PTN[Partners + marketplace]
  DASH --> SYS[System health + logs]
  DASH --> MAP[System Map workflows]
""",
    ),
    SystemMap(
        slug="autopilot-agent-loop",
        title="Autopilot & Agent Loop",
        nav_group="Agents",
        print_order=31,
        summary="Research → Strategist → Create → publish → Analyst → Adapt closes the intelligence loop.",
        audit=[
            "Six agents: Research, Create, Adapt, Engage, Analyst, Chief Strategist.",
            "Research every 12h — trends, optional auto-seed (max 1/12h).",
            "Strategist every 8h — proactive ContentSeeds + brief narrative.",
            "Autopilot: plan_weekly_autopilot → user approves → execute_autopilot_plan.",
            "Adapt v2 learning every 12h — profile mutations gated by ADAPT_AGENT_V2_ENABLED.",
            "Emergency pause on UserProfile halts all autonomous agent actions.",
        ],
        admin_links=[
            ("Agent overview", "agent_overview"),
            ("Agent log", "agent_log"),
            ("Token economics", "token_economics"),
        ],
        diagram="""
flowchart TB
  R[Research 12h] --> CR[Create Agent]
  ST[Strategist 8h] --> CR
  AP[Autopilot weekly plan] --> CR
  CR --> P[Posts published]
  P --> AN[Analyst Agent]
  AN --> AD[Adapt Agent 12h]
  AD --> CR
  P --> EN[Engage Agent 30m]
  EN --> AN
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


def ordered_tab_groups() -> list[tuple[str, list[SystemMap]]]:
    """Return nav groups in TAB_ORDER for the System Map UI."""
    grouped = maps_by_group()
    ordered: list[tuple[str, list[SystemMap]]] = []
    seen: set[str] = set()
    for name in TAB_ORDER:
        if name in grouped:
            ordered.append((name, grouped[name]))
            seen.add(name)
    for name in sorted(grouped.keys()):
        if name not in seen:
            ordered.append((name, grouped[name]))
    return ordered


def resolve_admin_links(map_obj: SystemMap) -> list[dict[str, str]]:
    """Resolve admin_dashboard URL names to paths for templates."""
    from django.urls import NoReverseMatch, reverse

    resolved: list[dict[str, str]] = []
    for label, url_name in map_obj.admin_links:
        try:
            resolved.append({
                "label": label,
                "url": reverse(f"admin_dashboard:{url_name}"),
            })
        except NoReverseMatch:
            continue
    return resolved
