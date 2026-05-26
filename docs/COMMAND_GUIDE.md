# Command Guide

> Version: 1.0
> Last Updated: May 2026
> Scope: Command tab, Morning Standup, Moment Mode, and Listen & Launch

---

## 1. What Command Is

`Command` is a new premium operating surface inside Kova.

It was implemented as a **shadow tab**, which means the new experience is live and usable without removing or breaking the existing proven flows in:

- `Home / Brief`
- `Calendar`
- `Listen & Launch` on the original Create side

This gives Kova a safer way to test a more opinionated operating layer before retiring older navigation paths.

The Command surface brings together three high-value workflows:

1. `Morning Standup` - a daily operator digest focused on the one decision only the owner can make.
2. `Moment Mode` - a fast cultural-moment review flow for ready-to-approve campaign packs.
3. `Listen & Launch` - a voice-first and prompt-first launch flow for building cross-channel campaigns.

The goal is not only to add another page. The goal is to make Kova feel like an actual command center:

- more premium
- more focused
- faster to operate
- better at helping the user decide what to do next

---

## 2. Product Intent

The Command work was designed around a few clear principles.

### 2.1 Keep legacy flows intact

No existing feature was deleted as part of this rollout.

The user can still:

- use `Brief` as before
- manage moments from the calendar area
- use the original `Listen & Launch` route under content creation

Command is an additional layer, not a destructive replacement.

### 2.2 Make the new layer feel premium

The Command overview and subpages use:

- large hero sections
- strong visual identity per mode
- subnavigation for a mini-product feel
- metric cards and mode cards
- dedicated workspaces instead of long mixed pages

### 2.3 Put operator decisions first

The Command experience is built around decision velocity:

- What should I do this morning?
- Which cultural pack is ready right now?
- How do I launch a campaign with the least friction?

### 2.4 Use existing proven systems under the hood

Command is not a rewrite of Kova's deeper systems.

It reuses and reorganizes:

- `DailyBrief`
- standup formatting logic
- `HolidayDraft` moment packs
- `VoiceBrief`
- campaign generation tasks
- WhatsApp Status generation
- existing calendar and content routes

This keeps the feature powerful without adding unnecessary duplication.

---

## 3. Navigation and Routes

The Command app is registered as a first-class Django app and exposed under:

- `/command/`
- `/command/standup/`
- `/command/moments/`
- `/command/listen/`

### 3.1 Top-level navigation

`Command` appears in the main sidebar as a top-level destination between `Home` and `Create`.

### 3.2 Command-local navigation

Once a user is inside the Command area, they get a second level of navigation:

- `Overview`
- `Standup`
- `Moments`
- `Listen`

This makes Command behave like a mini-product inside the main product, rather than a single experimental page.

### 3.3 Access guard

Command respects Kova onboarding rules.

If a user has not completed onboarding, the Command views redirect them to onboarding first.

---

## 4. Command Overview Page

Route: `/command/`

The overview page is the premium landing surface for the new Command layer.

### 4.1 Hero Mode

The overview page was intentionally designed to feel more "hero mode" than the normal app pages.

It includes:

- a branded hero block
- a clear statement of what Command is
- emphasis that this is Kova's next operating layer
- reassurance that legacy surfaces still remain live

### 4.2 Summary metrics

The overview surfaces a small set of high-signal metrics:

- `Score`
- `Posts waiting`
- `Moment packs`
- `Recent launches`

These metrics are computed from the shared Command context and serve as a quick operational snapshot.

### 4.3 Entry cards for the three modes

The page contains large cards for:

- `Morning Standup`
- `Moment Mode`
- `Listen & Launch`

Each card communicates:

- what the mode does
- the current quantity relevant to that mode
- a direct entry point into the dedicated subpage

### 4.4 Embedded preview and rollout messaging

The overview also includes:

- a preview of today's standup surface
- rollout notes explaining that Command is live as a shadow surface
- access to the upcoming moments widget
- the shared moment-pack modal

This makes the overview useful both as a landing page and as a status page for the experiment.

---

## 5. Morning Standup

Primary routes:

- `/command/standup/`
- also surfaced inside `/brief/`
- also available through WhatsApp command handling

Morning Standup is the operator digest inside this release.

### 5.1 What Morning Standup does

It converts the daily brief from a passive summary into a tighter operator console.

It highlights:

- the user's Kova score
- score delta
- posts pending approval
- "your move" summary
- overnight work summary
- the top decision that requires founder or operator judgment

### 5.2 Standup on Brief home

The original `Brief` home page now includes a premium standup hero partial.

This means the standup concept is not isolated only to Command. It is also improving the original home experience.

The standup hero on `Brief` includes:

- headline
- score and score delta
- pending posts count
- your move
- overnight summary
- "Only you can decide" panel
- quick action links
- WhatsApp hint for retrieving the digest again

### 5.3 Dedicated Standup subpage in Command

The dedicated Command Standup page adds more structure around the same digest.

It includes:

- its own hero section
- the standup hero card
- a `Decision queue`
- quick-path links to related operational surfaces

The Decision queue displays enriched decisions from the brief and gives the user a focused place to act on manual items.

### 5.4 Decision enrichment

Standup decisions are normalized and enriched before display.

This layer maps decision language to likely in-app actions, such as:

- `content queue`
- `content studio`
- `engage inbox`
- `leads`
- `bookings`
- `platforms`
- `analytics`
- `WhatsApp Status`

This means standup is not just descriptive. It actively routes the user to the right place.

### 5.5 WhatsApp support

Morning Standup was also integrated into WhatsApp command handling.

Supported command ideas include:

- `standup`
- `morning`
- `morning standup`

This allows the user to retrieve the morning digest outside the web app.

The WhatsApp action-button layer was also updated so standup can be surfaced as a fast action.

### 5.6 Engagement behavior

When a standup is retrieved from WhatsApp and a brief exists, the brief can be marked as engaged/read.

This helps align standup usage with daily-brief engagement behavior.

---

## 6. Moment Mode

Primary routes and surfaces:

- `/command/moments/`
- the moment-pack modal on `/brief/`
- moment pack status, approve, and dismiss endpoints under the calendar app

Moment Mode is the cultural-moment review workflow added in this release.

### 6.1 What Moment Mode solves

Kova already had calendar intelligence and holiday/event awareness.

Moment Mode turns that intelligence into a more operator-friendly review flow by making it easier to:

- see which moment packs are ready
- open one quickly
- inspect generated posts
- approve or dismiss without getting lost

### 6.2 Dedicated Moments subpage

The Command Moments page gives cultural-moment review its own premium space.

It includes:

- a dedicated hero section
- a `Ready packs` list
- direct links into pack review
- the upcoming moments widget
- the shared modal for reviewing a pack in place

### 6.3 Ready pack behavior

The Command context queries `HolidayDraft` records that are in `DRAFTS_READY` state and shows the first few ready packs in date order.

This gives the user a prioritized list of what can be reviewed now.

### 6.4 Moment pack modal

The modal is a key part of the implementation.

It provides:

- real-time or polling-style pack status
- progress steps while drafts are being prepared
- a compact list of generated posts
- approve action
- dismiss action
- direct link into Studio

This lets the user stay inside the current context instead of bouncing through unrelated pages.

### 6.5 Return-to-surface behavior

Moment approval and dismissal were updated to accept a `next` value.

That matters because it preserves the user's current context:

- if they opened the modal from Brief, they can return to Brief
- if they opened it from Command Moments, they can remain in Command

This is an important usability detail because it makes the new flow feel intentional instead of stitched together.

### 6.6 Approval logic

Approving a moment pack:

- iterates through generated posts
- approves posts that are still draft or pending approval
- updates the pack status to approved
- schedules the approved content

Dismissing a moment pack marks it dismissed without scheduling it.

### 6.7 Relationship to existing Calendar features

Moment Mode does not remove or replace calendar preferences or custom-event management.

Instead, it adds a higher-speed review surface for the most important downstream action:

- deciding whether to approve a ready moment pack

---

## 7. Listen & Launch

Primary routes and surfaces:

- `/command/listen/`
- `/content/voice-campaign/`
- `/content/voice-campaign/transcribe/`

Listen & Launch is the campaign-launch workflow in this release.

### 7.1 What Listen & Launch does

It allows the user to start a campaign from:

- a text prompt
- a live mic recording
- an uploaded voice memo

The generated output is not limited to one channel.

The flow can create:

- social campaign seeds
- queue-ready post generation
- WhatsApp Status drafts
- an email campaign when requested

### 7.2 Dedicated Listen page inside Command

The new Command Listen page gives this flow a premium, voice-first home.

It includes:

- a hero section
- the shared Listen workspace
- command-local navigation
- links back to the legacy route and Status Studio

### 7.3 Shared Listen workspace

The shared workspace partial powers the actual interaction model.

It includes:

- a prompt textarea
- live microphone recording
- real-time transcription into the prompt field
- duration selector
- checkbox for WhatsApp Status inclusion
- checkbox for email inclusion
- voice memo upload fallback
- recent launches panel
- recent campaigns panel

This makes Listen & Launch feel like a production workspace instead of just a simple form.

### 7.4 Live microphone transcription

The browser-side recorder:

- requests microphone access
- records audio with `MediaRecorder`
- sends audio to the transcription endpoint
- appends the returned text into the prompt box

This is a major usability improvement because it reduces friction between the user's spoken intent and the actual campaign prompt.

### 7.5 Redirect behavior

Submissions from Command Listen redirect back to the dedicated Listen page, usually to the composer anchor.

This keeps the user inside the Command experience after they launch something.

### 7.6 Voice memo handling

For uploaded audio:

- the system validates file type
- enforces a max file size
- creates a `VoiceBrief`
- triggers background processing

This keeps the experience aligned with the existing voice-brief architecture while still making Command feel like its own surface.

### 7.7 Cross-channel output

Listen & Launch was expanded beyond simple social seed creation.

The prompt and voice flows now support:

- social queue generation
- optional email campaign creation
- optional WhatsApp Status generation

This is one of the most important product-level improvements in the release.

### 7.8 WhatsApp Status generation

The campaign-planning and campaign-building path now supports status updates explicitly.

When included, Kova can generate short WhatsApp Status drafts based on the campaign plan.

This matters because:

- WhatsApp is a core channel for many local businesses
- it lets campaigns feel more complete
- it makes voice-first planning more useful for fast-moving operators

### 7.9 Recent launches and recent campaigns

The Listen workspace also acts like a control tower for recent output.

It shows:

- recent voice briefs and their status
- links into created campaigns
- links into related email campaigns where available
- recent campaign list for quick reopening

This helps users trust that the launch flow is doing real work after submission.

---

## 8. Shared Command Context Layer

The Command app uses a shared context builder so all Command pages have a consistent data model.

That shared context includes:

- current or latest daily brief
- standup context
- enriched decisions
- ready moment packs
- upcoming moments
- selected moment-pack id
- recent voice briefs
- recent campaigns
- legacy route references
- transcription endpoint

This is important for maintainability because it prevents each page from recomputing slightly different versions of the same operational data.

---

## 9. Supporting Backend Work

Several supporting implementation pieces were added or upgraded so Command could behave like a real product surface.

### 9.1 New `apps.command` app

The Command implementation has its own app with:

- `urls.py`
- `views.py`
- templates under `templates/command/`

This gives the new surface a clean home instead of scattering all logic into unrelated apps.

### 9.2 Standup utility module

`apps/briefs/standup.py` centralizes standup behavior such as:

- picking the top decision
- enriching decision destinations
- building web standup context
- formatting WhatsApp standup messages
- engagement marking

This prevents standup logic from being duplicated between Brief, Command, and WhatsApp.

### 9.3 Moment pack pipeline status

The calendar side now exposes a pipeline/status layer that the modal can poll.

That enables:

- progress display
- step display
- post preview display
- terminal state handling

### 9.4 Voice transcription endpoint

The content area now exposes a dedicated transcription endpoint for live mic usage.

That endpoint allows the UI to transcribe mic recordings without forcing the user to upload a full voice memo as a traditional form submission.

### 9.5 Campaign task expansion

Campaign task logic was extended to support:

- WhatsApp Status plan output
- status draft creation from plan data
- fallback status generation from a key message if no explicit status updates are returned

This means the Listen & Launch promise is backed by deeper task behavior, not only UI copy.

---

## 10. User Experience Summary by Page

### 10.1 Overview

Best for:

- getting a quick operational picture
- choosing which Command mode to enter
- understanding that Command is a premium shadow layer

### 10.2 Standup

Best for:

- starting the workday
- identifying the highest-value decision
- moving quickly into queue, studio, or status actions

### 10.3 Moments

Best for:

- checking what cultural packs are ready
- reviewing upcoming moments
- approving or dismissing packs from a focused surface

### 10.4 Listen

Best for:

- launching campaigns from voice or text
- creating multi-channel plans quickly
- monitoring recent launch activity

---

## 11. Why This Matters Strategically

The Command release is important not just because it adds pages, but because it changes how Kova can be operated.

Before Command, users had strong capabilities spread across different surfaces.

With Command, Kova starts to behave more like a unified operator console.

That creates several product advantages:

- better focus on the next best action
- lower friction between intention and execution
- stronger sense of product identity
- safer experimentation because legacy flows remain live
- clearer separation between "do work" and "configure systems"

This is the beginning of Kova becoming an operating layer, not just a set of tools.

---

## 12. Files Added or Updated

The implementation spans multiple areas.

### Core Command app

- `apps/command/__init__.py`
- `apps/command/urls.py`
- `apps/command/views.py`

### Command templates

- `templates/command/home.html`
- `templates/command/standup.html`
- `templates/command/moments.html`
- `templates/command/listen.html`
- `templates/command/_subnav.html`
- `templates/command/_listen_workspace.html`

### Shared standup and brief improvements

- `apps/briefs/standup.py`
- `apps/briefs/views.py`
- `apps/briefs/whatsapp_buttons.py`
- `apps/briefs/whatsapp_commands.py`
- `templates/briefs/home.html`
- `templates/briefs/_morning_standup.html`

### Moment Mode support

- `apps/calendar_intel/urls.py`
- `apps/calendar_intel/views.py`
- `apps/calendar_intel/moment_pack_pipeline.py`
- `templates/calendar_intel/_moment_pack_modal.html`
- `templates/calendar_intel/partials/_upcoming_widget.html`

### Listen & Launch support

- `apps/content/urls.py`
- `apps/content/views.py`
- `apps/content/tasks.py`
- `apps/campaigns/tasks.py`
- `templates/content/voice_campaign.html`

### App shell integration

- `templates/layouts/app.html`
- `config/settings/base.py`
- `config/urls.py`

### Tests

- `tests/test_command_tab.py`
- `tests/test_morning_standup.py`
- `tests/test_moment_pack.py`
- `tests/test_listen_launch.py`
- `tests/test_brief_whatsapp_commands.py`

---

## 13. Automated Validation

The implementation was covered with focused tests around:

- Command overview rendering
- Command subpage rendering
- Listen redirect behavior
- Morning Standup formatting and normalization
- Moment pack status behavior
- Listen & Launch status-generation support
- WhatsApp standup command handling

Examples of validated behavior include:

- Command overview renders the hero surface
- Standup, Moments, and Listen pages render independently
- launches posted from Command stay inside the Command Listen surface
- standup handles decision payloads safely
- ready moment packs expose correct status data
- WhatsApp Status content can be generated from Listen & Launch plans

---

## 14. Rollout Philosophy

This release follows a deliberate rollout philosophy:

1. Add the premium surface first.
2. Keep the old paths alive.
3. Watch which workflows actually create value.
4. Only retire older surfaces after the new experience proves itself.

That philosophy is visible throughout the implementation:

- links back to legacy surfaces are preserved
- the original Create route still works
- the original Brief still works
- the original calendar controls still work

Command is therefore both a feature release and a product experiment.

---

## 15. Recommended Next Iteration Areas

If Command continues to prove valuable, the strongest next iteration areas are:

### 15.1 Stronger command orchestration

Let users chain actions from one place, for example:

- approve standup decisions
- open and schedule a moment pack
- launch a status-first campaign

### 15.2 Better launch telemetry

Show deeper "what happened after launch" feedback inside Command Listen, such as:

- generated posts count
- email draft count
- status draft count
- publish success or failure summaries

### 15.3 Decision memory

Teach Standup which types of decisions users regularly delay or act on quickly, so the page becomes more personalized over time.

### 15.4 Command-level prioritization

Allow the overview page to order its cards and recommendations based on:

- current business urgency
- pending approvals
- seasonal opportunities
- active campaigns

---

## 16. Bottom Line

The `Command` implementation is a meaningful upgrade to how Kova can be used.

It introduces a premium operator surface without deleting existing functionality, and it packages three strong workflows into one coherent product layer:

- `Morning Standup` for daily decision-making
- `Moment Mode` for cultural-moment approvals
- `Listen & Launch` for fast multi-channel campaign creation

The result is a more premium, more directed, and more operational version of Kova that can be tested safely before broader consolidation.
