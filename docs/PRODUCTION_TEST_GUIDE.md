# ============================================================================
# KOVA AGENT — PRODUCTION TESTING GUIDE
# ============================================================================
# Sample Startup: DigiBridge Academy
# "Unlocking digital futures for refugees, one skill at a time."
# Location: Kakuma Refugee Camp, Turkana County, Kenya
# ============================================================================


# THE STARTUP
# ─────────────────────────────────────────────────────────────────────────────

## Company Name
DigiBridge Academy

## Tagline
"Unlocking digital futures for refugees, one skill at a time."

## What It Does
DigiBridge Academy is a social enterprise that provides free digital skills
training (graphic design, web development, data entry, virtual assistance,
freelancing) to refugees aged 16-35 in Kakuma Refugee Camp. Graduates earn
income through remote freelance work on platforms like Upwork, Fiverr, and
direct client contracts — breaking the cycle of aid dependency.

## Why It Exists
- 250,000+ refugees in Kakuma, most with smartphones but no marketable skills
- 80% youth unemployment in the camp
- Internet connectivity exists (Safaricom, Turkana County fiber)
- Global demand for digital freelancers is exploding
- Refugees can earn $200-800/mo freelancing — life-changing in that context

## Revenue Model
- Training is FREE for refugees (funded by grants + donations)
- Revenue: 10% commission on graduate freelance earnings (first 12 months)
- Corporate partnerships: companies hire DigiBridge graduates as remote teams
- Impact investor funding (social returns + financial returns)

## Social Media Goals
- Build awareness and credibility internationally
- Attract donors, grants, and corporate partnerships
- Showcase refugee success stories (counter the "helpless refugee" narrative)
- Recruit volunteer mentors and instructors
- Build a community around digital empowerment


# ============================================================================
# PHASE A: ACCOUNT SETUP & ONBOARDING
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Signup (phone required) → Kova Express onboarding
# ============================================================================

## A1. Sign Up

Navigate to: https://kovaagent-production.up.railway.app/accounts/signup/

Use these credentials:
- Email: hello@digibridge.org (or your real email)
- Password: Use a strong password (16+ chars)
- Full Name: Amara Ochieng
- Phone: Kenyan mobile (e.g. 0712345678) — **required**

What to verify:
  ☐ Signup form submits without errors
  ☐ Phone number field is required
  ☐ No email verification required (disabled in production)
  ☐ You are logged in immediately after signup
  ☐ You're redirected to onboarding (path choice / express wizard)


## A2. Onboarding — Path Choice

What to verify:
  ☐ Intent options visible: sell products, grow on social, or both
  ☐ Optional website/social link field works
  ☐ Choosing an intent advances to Step 1


## A3. Onboarding — Step 1: Business Basics

Fill in:
- Business / company name: DigiBridge Academy
- Website URL (optional): https://digibridge.org
- Industry: Education / Non-Profit (pick the closest available option)
- Content Language: English (or Swahili if testing localization)

What to verify:
  ☐ Phone already on file from signup (not asked again)
  ☐ All fields accept input correctly
  ☐ Magic Fill works if you pasted a link on path choice
  ☐ "Next" advances to Step 2 (brand preview)
  ☐ Progress indicator shows Step 1 of 3


## A4. Onboarding — Step 2: Confirm Brand

What to verify:
  ☐ Preview card shows inferred voice, audience, tone, pillars
  ☐ "Looks good — start my agency" completes onboarding
  ☐ Agency meeting / intelligence chain starts (1–3 min)
  ☐ Sell/commerce users redirect to Snap to Sell (`/products/snap/`)
  ☐ Grow users redirect to Content Studio or Brief
  ☐ Onboarding is marked complete (no repeat redirects)
  ☐ Platform connect is **not** required to finish — optional from `/platforms/` later


# ============================================================================
# PHASE B: EXPLORE THE DASHBOARD — EMPTY STATE TESTING
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Every page loads without errors when no data exists
# ============================================================================

Visit EVERY page from the sidebar and verify it shows a proper empty state
(not a crash or blank page). This is critical — many apps break on empty.

## B1. Overview Section
  ☐ Daily Brief (/brief/) — Should show "no brief yet" or similar empty state

## B2. Content Section
  ☐ Content Studio (/content/studio/) — Empty state: "No posts to review"
  ☐ Queue (/content/queue/) — Empty state: no scheduled/published posts
  ☐ Timeline (/content/calendar/) — Empty calendar or "no scheduled posts"

## B3. Intelligence Section
  ☐ Inbox (/engage/) — Empty state: no interactions yet
  ☐ Agents (/agents/) — All 6 agents listed with toggles
  ☐ Insights (/analytics/) — Empty state: no data yet

## B4. System Section
  ☐ Platforms (/platforms/) — No connected platforms, shows connect buttons
  ☐ Billing (/billing/) — Shows current plan (Jipange / Starter)

## B5. Account
  ☐ Settings (/accounts/settings/) — Your onboarding data should be populated
  ☐ Notification bell — Shows 0 or empty dropdown

What to verify overall:
  ☐ Sidebar navigation works on every page
  ☐ Dark mode renders correctly everywhere
  ☐ No 500 errors, no broken templates, no missing images
  ☐ Responsive: test on mobile viewport (Chrome DevTools → toggle device)


# ============================================================================
# PHASE C: CONNECT PLATFORMS
# ============================================================================
# Estimated time: 30-60 minutes (creating developer apps + OAuth testing)
# What you're testing: OAuth flow for each platform
#
# PREREQUISITE: You must create developer apps on each platform FIRST,
# then add the credentials to Railway environment variables.
# Kova uses a custom OAuth 2.0 flow (not django-allauth social).
# ============================================================================

Navigate to Platforms (/platforms/)

## C0. How Platform Connections Work

Kova Agent uses custom OAuth 2.0 for each platform. The flow is:
1. User clicks "Connect" → redirected to platform's auth page
2. User authorizes → platform redirects back to Kova with a code
3. Kova exchanges the code for access tokens + fetches profile info
4. Tokens stored in database → platform shows as "Connected"

For this to work, you need:
- A developer app on each platform (provides Client ID + Secret)
- The correct redirect/callback URL registered in each app
- The credentials set as environment variables in Railway


## C1. Create Facebook App (also used for Instagram)

Facebook + Instagram share the same app.

### Step 1: Create the App
1. Go to https://developers.facebook.com/ and log in
2. Click "My Apps" → "Create App"
3. Select app type: "Business" (not Consumer or Gaming)
4. App name: Kova Agent
5. Contact email: your email
6. Business Account: skip if you don't have one

### Step 2: Get Credentials
1. Go to App Settings → Basic
2. Copy App ID → this is your FACEBOOK_APP_ID
3. Click "Show" on App Secret → this is your FACEBOOK_APP_SECRET

### Step 3: Configure OAuth
1. Add product: "Facebook Login for Business"
2. Add product: "Instagram Graph API" (for Instagram support)
3. Go to Facebook Login → Settings → Valid OAuth Redirect URIs, add:
   - https://kovaagent-production.up.railway.app/platforms/callback/facebook/
   - https://kovaagent-production.up.railway.app/platforms/callback/instagram/
   - http://localhost:8000/platforms/callback/facebook/ (for local dev)
   - http://localhost:8000/platforms/callback/instagram/ (for local dev)

### Step 4: Permissions (for testing)
- While in Development Mode, only app admins/testers can use OAuth
- Add yourself as a tester: App Roles → Roles → Add People
- For full public access, submit for App Review (not needed yet)
- Required permissions: pages_manage_metadata, pages_manage_posts,
  pages_read_engagement, instagram_content_publish, instagram_manage_insights
- Note: pages_show_list and instagram_basic are deprecated (v21.0+)
- If using Facebook Login for Business, set FB_LOGIN_CONFIG_ID instead of scopes

### Step 5: Set Railway Env Vars
  FACEBOOK_APP_ID=123456789012345
  FACEBOOK_APP_SECRET=abc123def456...


## C2. Create X (Twitter) App

### Step 1: Create the App
1. Go to https://developer.x.com/ and sign up / log in
2. Create a Project, then create an App inside it
3. Select Free or Basic tier (Free tier allows posting)

### Step 2: Configure User Authentication
1. Go to App Settings → User authentication settings → Set up
2. App permissions: Read and Write
3. Type of app: Web App
4. Callback URI:
   https://kovaagent-production.up.railway.app/platforms/callback/twitter/
5. Website URL: https://kovaagent-production.up.railway.app

### Step 3: Get Credentials
1. Go to Keys and tokens → OAuth 2.0 Client ID and Client Secret
2. Copy Client ID → TWITTER_CLIENT_ID
3. Copy Client Secret → TWITTER_CLIENT_SECRET

### Step 4: Set Railway Env Vars
  TWITTER_CLIENT_ID=xxxxxxxxxxxxxxxx
  TWITTER_CLIENT_SECRET=xxxxxxxxxxxxxxxx

Note: Twitter uses OAuth 2.0 with PKCE (code challenge). Scopes requested:
tweet.read, tweet.write, users.read, offline.access


## C3. Create LinkedIn App

### Step 1: Create the App
1. Go to https://www.linkedin.com/developers/ → Create App
2. App name: Kova Agent
3. LinkedIn Page: associate with any Company Page you own (required)
4. Upload any logo image

### Step 2: Get Credentials
1. Go to the Auth tab
2. Copy Client ID → LINKEDIN_CLIENT_ID
3. Copy Client Secret → LINKEDIN_CLIENT_SECRET

### Step 3: Configure OAuth
1. Under OAuth 2.0 settings → Redirect URLs, add:
   https://kovaagent-production.up.railway.app/platforms/callback/linkedin/
2. Go to Products tab and request access to:
   - "Share on LinkedIn" (for publishing posts)
   - "Sign in with LinkedIn using OpenID Connect"

### Step 4: Set Railway Env Vars
  LINKEDIN_CLIENT_ID=xxxxxxxxxxxxxxxx
  LINKEDIN_CLIENT_SECRET=xxxxxxxxxxxxxxxx

Note: Scopes requested: openid, profile, w_member_social


## C4. Create TikTok App

### Step 1: Create the App
1. Go to https://developers.tiktok.com/ → Manage apps → Connect an app
2. Select: Configure for Web
3. App name: Kova Agent

### Step 2: Configure OAuth
1. Set Redirect URI:
   https://kovaagent-production.up.railway.app/platforms/callback/tiktok/
2. Add products: Login Kit + Content Posting API

### Step 3: Get Credentials
1. Copy Client Key → TIKTOK_CLIENT_KEY
2. Copy Client Secret → TIKTOK_CLIENT_SECRET

### Step 4: Set Railway Env Vars
  TIKTOK_CLIENT_KEY=xxxxxxxxxxxxxxxx
  TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxx

Note: Scopes requested: user.info.basic, video.publish, video.list


## C5. Callback URL Quick Reference

  Platform   | Callback URL
  -----------|-------------------------------------------------------------
  Facebook   | https://kovaagent-production.up.railway.app/platforms/callback/facebook/
  Instagram  | https://kovaagent-production.up.railway.app/platforms/callback/instagram/
  Twitter/X  | https://kovaagent-production.up.railway.app/platforms/callback/twitter/
  LinkedIn   | https://kovaagent-production.up.railway.app/platforms/callback/linkedin/
  TikTok     | https://kovaagent-production.up.railway.app/platforms/callback/tiktok/

For local development, replace the domain with http://localhost:8000


## C6. Railway Env Vars Summary

All of these go in Railway Dashboard → Your Service → Variables:

  FACEBOOK_APP_ID=
  FACEBOOK_APP_SECRET=
  TWITTER_CLIENT_ID=
  TWITTER_CLIENT_SECRET=
  LINKEDIN_CLIENT_ID=
  LINKEDIN_CLIENT_SECRET=
  TIKTOK_CLIENT_KEY=
  TIKTOK_CLIENT_SECRET=

After adding env vars, Railway auto-redeploys. Wait ~2 minutes.
Connect buttons for unconfigured platforms will be grayed out.


## C7. Test the OAuth Flow (repeat for each platform)

1. Click "Connect" on the platform
2. You'll be redirected to the platform's authorization page
3. Authorize Kova Agent's access
4. You'll be redirected back to Kova

What to verify:
  ☐ OAuth redirect works (no "Invalid App ID" or redirect errors)
  ☐ After callback, platform shows as "Connected" with your handle
  ☐ Username and avatar are pulled correctly
  ☐ "Disconnect" button appears

## C8. Test Disconnect & Reconnect

1. Pick one platform (e.g., LinkedIn)
2. Click "Disconnect"
3. Verify it's removed from connected list
4. Reconnect it

What to verify:
  ☐ Disconnect removes the platform cleanly
  ☐ Reconnecting re-creates it without errors
  ☐ No duplicate entries appear

## C9. Common OAuth Errors

  Error                        | Cause & Fix
  -----------------------------|-------------------------------------------
  "Invalid App ID"             | FACEBOOK_APP_ID not set or wrong value
  "Redirect URI mismatch"      | Callback URL in dev portal doesn't match
  "App not set up"             | Missing user auth config on Twitter
  "Unauthorized"               | App in dev mode, add yourself as tester
  "Invalid scope"              | Platform hasn't approved required permissions


# ============================================================================
# PHASE D: AGENT CONFIGURATION
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Agent listing, toggles, configure links, activity link
# Updated: Sprint 6 added Configure links + Activity Log link
# ============================================================================

Navigate to Agents (/agents/)

## D1. View All Agents
You should see 6 agents:
1. Research Agent 🔍
2. Content Creator Agent ✍️ (this is the active one)
3. Platform Adapter Agent 🔄
4. Engagement Agent 💬
5. Analytics Agent 📊
6. Chief Strategist 🧠

What to verify:
  ☐ All 6 agents display with correct names, icons, descriptions
  ☐ Each has an enable/disable toggle
  ☐ Each agent card has a "Configure" link (→ /agents/<slug>/)
  ☐ "Activity Log" link visible in page header (→ /agents/activity/)

## D2. Toggle Agents
1. Disable the Content Creator Agent
2. Re-enable it

What to verify:
  ☐ Toggle saves immediately (HTMX or form submit)
  ☐ State persists after page refresh
  ☐ Visual feedback confirms ON/OFF state

## D3. Click Configure Link
1. Click "Configure" on the Research Agent card
2. Verify you land on /agents/research/

What to verify:
  ☐ Links to agent detail page (tested in depth in Phase K)
  ☐ No 404 errors

## D4. Click Activity Log Link
1. Go back to /agents/
2. Click "Activity Log" link
3. Verify you land on /agents/activity/

What to verify:
  ☐ Links to activity log page (tested in depth in Phase K)
  ☐ No 404 errors


# ============================================================================
# PHASE E: CONTENT CREATION — THE MAIN EVENT
# ============================================================================
# Estimated time: 15-20 minutes
# What you're testing: Full content pipeline from idea → AI generation → review
# ============================================================================

Navigate to Content Studio (/content/studio/)

## E1. Generate Test Batch #1 — Success Story

Idea:
```
Sarah, a 22-year-old Congolese refugee in Kakuma, just earned her first $500 
on Upwork doing graphic design after completing our 3-month program. She now 
supports her mother and two siblings. This is why DigiBridge exists.
```

Optional Notes:
```
Make it emotional but not pitying. Focus on Sarah's agency and achievement.
Include a call to action for donations/sponsorships.
```

Target Platforms: Select ALL connected platforms

Click "Generate"

What to verify:
  ☐ Generate button shows spinner + "Generating…" text (no page reload!)
  ☐ Processing card appears inline with seed idea text
  ☐ Processing card shows spinner while AI works
  ☐ After completion: status card shows "X posts generated across platforms"
  ☐ Posts appear AUTOMATICALLY below (no page refresh needed!)
  ☐ Posts are grouped under the seed idea header
  ☐ Each post is platform-specific:
    - Twitter post: short, punchy, hashtags, <280 chars
    - TikTok post: video script format with scenes
    - LinkedIn post: professional storytelling, longer form
    - Instagram: visual-first, emoji-rich, hashtag-heavy
    - Facebook: conversational, community-oriented
  ☐ Each post card shows:
    - Platform icon + name
    - "AI" badge
    - Predicted engagement score
    - "Pending Approval" status
    - The AI's strategic angle (blue box)
    - The AI framework used (e.g., "Myth → Truth → Proof")
    - Approve, Reject, Edit, Regenerate buttons


## E2. Generate Test Batch #2 — Impact Data

Idea:
```
We just hit 500 graduates. 73% are now earning income through freelancing.
Average monthly earnings: $340. Total community income generated: $2.1M 
since launch. Zero dollars came from charity — all earned.
```

Notes:
```
Lead with the "earned not given" angle. This challenges the traditional 
aid narrative. Make donors see ROI, not just feel-good stories.
```

Target Platforms: Select ALL

What to verify:
  ☐ Second batch generates while first batch posts are still visible
  ☐ Second seed group appears as a SEPARATE group (not mixed with first)
  ☐ Each group has its own header, strategy, "Approve all" button
  ☐ AI generates genuinely DIFFERENT content from Batch #1
  ☐ The angle and framework should differ per platform AND per batch


## E3. Generate Test Batch #3 — Behind the Scenes

Idea:
```
A day in the life at DigiBridge's Kakuma training center: 30 laptops, 
donated Wi-Fi hotspots, and 60 eager students learning Python. The 
classroom is a converted shipping container. The ambition is Silicon Valley.
```

Target Platforms: Select only 2 platforms (e.g., X + TikTok)

What to verify:
  ☐ Only the 2 selected platforms get posts (not all 5)
  ☐ Platform selection worked correctly
  ☐ Group shows platform count as "2 platforms"


## E4. Generate Test Batch #4 — Thought Leadership

Idea:
```
Hot take: Teaching refugees to code isn't charity — it's the smartest 
investment in the global knowledge economy. Here's why companies should 
be fighting to hire Kakuma's talent, not ignoring it.
```

Notes:
```
Provocative, challenge assumptions. This should spark debate and shares. 
Target the tech industry audience and impact investors.
```

What to verify:
  ☐ AI adapts tone to be more provocative/thought-leadership
  ☐ Content is genuinely different from the success story tone


# ============================================================================
# PHASE F: POST ACTIONS — REVIEW WORKFLOW
# ============================================================================
# Estimated time: 10 minutes
# What you're testing: Approve, reject, edit, regenerate on individual posts
# ============================================================================

## F1. Approve a Single Post (Post Now)

1. Find a Twitter post from Batch #1
2. Click "Approve" dropdown → "Post Now"

What to verify:
  ☐ Post status changes to "Approved" or "Publishing" or "Published"
  ☐ Post moves from studio to Queue
  ☐ Notification appears (bell icon updates)

## F2. Approve a Single Post (Schedule)

1. Find a LinkedIn post from Batch #2
2. Click "Approve" → "30 min" (quick schedule)

What to verify:
  ☐ Post status changes to "Scheduled"
  ☐ Post appears on Queue page with scheduled time
  ☐ Post appears on Timeline/Calendar at correct date

## F3. Approve with Exact Time

1. Find an Instagram post
2. Click "Approve" → Pick exact date/time → "Set"

What to verify:
  ☐ Datetime picker works correctly
  ☐ Post scheduled at exact time you chose
  ☐ Visible on Calendar at that date

## F4. Reject a Post

1. Find a TikTok post you don't like
2. Click "Reject"

What to verify:
  ☐ Post card updates to show "Rejected" status (no page reload)
  ☐ Rejected post is either hidden or visually struck-through
  ☐ Regenerate button should still be available for rejected posts

## F5. Regenerate a Post

1. Find the rejected TikTok post (or any pending post)
2. Click "Regenerate" (🔄 icon)

What to verify:
  ☐ Spinner appears on the card while regenerating
  ☐ AI returns a NEW version (different angle, different hook)
  ☐ Post card updates in-place with new content (no page reload)
  ☐ Status resets to "Pending Approval"
  ☐ New AI angle/framework shown

## F6. Edit a Post

1. Find any pending post
2. Click "Edit"
3. Modify the content text (e.g., fix a hashtag, tweak copy)
4. Save

What to verify:
  ☐ Edit page loads with current content pre-filled
  ☐ Changes save correctly
  ☐ Status resets to "Draft" after editing
  ☐ Redirects back to studio or post detail

## F7. Batch Approve All Posts in a Seed Group

1. Find Batch #2's seed group
2. Click "Approve all" (green button on group header)
3. Choose "Smart Queue" from the modal

What to verify:
  ☐ Batch schedule modal appears (animated overlay)
  ☐ All scheduling options displayed correctly
  ☐ Clicking "Smart Queue" approves ALL posts in that group
  ☐ Each post gets a different scheduled time (auto-spaced)
  ☐ All posts now show "Scheduled" status
  ☐ All appear on Queue and Calendar pages


# ============================================================================
# PHASE G: QUEUE & CALENDAR VERIFICATION
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Posts flow correctly through the pipeline
# ============================================================================

## G1. Check Queue Page

Navigate to Queue (/content/queue/)

What to verify:
  ☐ "Scheduled" section shows all scheduled posts
  ☐ Posts grouped by seed (same visual grouping as studio)
  ☐ Scheduled times displayed correctly
  ☐ "Published" section shows any posts that were published ("Post Now")
  ☐ "Failed" section shows any that failed (OAuth errors, etc.)
  ☐ No duplicate posts across sections

## G2. Check Calendar/Timeline Page

Navigate to Timeline (/content/calendar/)

What to verify:
  ☐ Scheduled posts appear on correct dates
  ☐ Within each date, posts are grouped by seed
  ☐ Visual layout makes sense (not cluttered)
  ☐ Unscheduled approved posts shown separately


# ============================================================================
# PHASE H: NOTIFICATIONS
# ============================================================================
# Estimated time: 2 minutes
# What you're testing: Notification generation and display
# ============================================================================

## H1. Check Bell Icon

Look at the top-right notification bell.

What to verify:
  ☐ Unread count badge appears (orange/red number)
  ☐ Click bell → dropdown shows recent notifications
  ☐ Notifications include: "Posts generated", "Post published", etc.

## H2. Full Notifications Page

Click through to the full notifications page (/notifications/)

What to verify:
  ☐ All notifications listed chronologically
  ☐ Each notification has a type icon and readable message
  ☐ Clicking a post-related notification links to the post

## H3. Mark All Read

Click "Mark all as read"

What to verify:
  ☐ Badge count resets to 0
  ☐ Notifications visually marked as read


# ============================================================================
# PHASE I: INSIGHTS & ANALYTICS
# ============================================================================
# Estimated time: 2 minutes
# What you're testing: Analytics page with limited data
# ============================================================================

Navigate to Insights (/analytics/)

What to verify:
  ☐ Page loads without errors
  ☐ If posts have been published:
    - Basic metrics should start populating
    - Top posts section may show the published post(s)
    - Engagement rate shown (may be 0 initially)
  ☐ If no publishing happened: clean empty state, no crashes


# ============================================================================
# PHASE J: DAILY BRIEF — COMMAND CENTER
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Daily Brief generation, display, performance insights
# Added in Sprint 5: Analyst Agent + Content DNA integration
# ============================================================================

Navigate to Daily Brief (/brief/)

## J1. First Visit — Empty or Auto-Generated Brief

What to verify:
  ☐ Page loads without errors
  ☐ If brief exists: displays performance insight, trending topics, suggested posts
  ☐ If no brief yet: shows clean empty state with "no brief generated yet" message
  ☐ Brief card layout uses glassmorphism/gradient styling consistent with rest of UI

## J2. Brief Content Sections

If a brief has been generated (after creating + publishing content), verify:

### Performance Insight Card
  ☐ Shows yesterday's/recent performance summary
  ☐ Engagement data displayed (or "not enough data" if new account)
  ☐ Analyst Agent's analysis rendered as readable prose (not raw JSON)

### Trending Topics
  ☐ Research Agent trending topics displayed with:
    - Topic name/description
    - Urgency badge (🔴 high / 🟡 medium / 🟢 low)
    - Relevance score
    - Suggested content angle
  ☐ Topics are relevant to the user's industry (Education / Non-Profit for DigiBridge)

### Suggested Posts
  ☐ AI-suggested content ideas shown with:
    - Content type badge (e.g., "story", "data", "thought-leadership")
    - Timing recommendation (e.g., "morning", "afternoon")
    - Platform suggestions
  ☐ Suggestions are actionable — user can understand what to create

### Agent Activity Summary
  ☐ Shows what agents have done since last visit
  ☐ Includes agent type icons and action counts

### Content Pipeline Stats
  ☐ Shows pending/scheduled/published post counts
  ☐ Numbers are accurate vs. what you see in Queue

## J3. Content DNA Display

If posts have been created with the Analyst Agent active:
  ☐ Content DNA summary appears in brief (best-performing attributes)
  ☐ Attributes like tone, format, topic category shown
  ☐ "Not enough data" message if fewer than 5 published posts


# ============================================================================
# PHASE K: AGENT ACTIVITY LOG & CONFIGURATION
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Agent activity history, per-agent config, custom instructions
# Added in Sprint 6: Research Agent, Adapt Agent, Activity Log, Agent Detail
# ============================================================================

## K1. Agent Activity Log

Navigate to Agent Activity Log (/agents/activity/)

What to verify:
  ☐ Page loads without errors
  ☐ If agents have run: shows chronological list of agent actions
  ☐ Each action shows:
    - Agent type (Research, Analyst, Create, Adapt, etc.)
    - Action name (e.g., "discover_trends", "extract_content_dna")
    - Status (success / failed / pending)
    - Timestamp
    - Tokens used
  ☐ If no activity yet: clean empty state
  ☐ Filtering works (if filter controls are present)

## K2. Agent Control Panel

Navigate to Agents (/agents/)

What to verify:
  ☐ All 6 agents listed with toggles
  ☐ Each agent card has a "Configure" link → goes to /agents/<slug>/
  ☐ "Activity Log" link visible in the header area → goes to /agents/activity/
  ☐ Toggle enable/disable works (HTMX, no page reload)

## K3. Agent Detail Page

Click "Configure" on any agent (e.g., Research Agent)

Navigate to /agents/research/

What to verify:
  ☐ Agent detail page loads without errors
  ☐ Shows agent stats:
    - Total actions (all time)
    - Actions today
    - Total tokens used
  ☐ Custom instructions textarea is present
  ☐ Recent activity feed shows last actions for THIS agent only

## K4. Custom Instructions Editor

1. On the agent detail page, find the custom instructions section
2. Enter custom instructions:
```
Focus on education technology trends and digital skills training 
in East Africa. Prioritize refugee employment and social enterprise 
stories. Avoid generic tech industry trends — keep it niche.
```
3. Save

What to verify:
  ☐ Instructions save without errors (HTMX POST to /agents/<slug>/instructions/)
  ☐ Success feedback appears (toast/flash message)
  ☐ Instructions persist after page refresh
  ☐ Instructions appear in the textarea on reload

## K5. Verify Custom Instructions Affect Output

1. Set custom instructions on Research Agent (as above)
2. Wait for next Daily Brief generation (or trigger manually if possible)
3. Check trending topics in the Daily Brief

What to verify:
  ☐ Trending topics should skew toward education/refugee/East Africa themes
  ☐ Custom instructions are being respected by the agent


# ============================================================================
# PHASE L: CONTENT DNA & ENGAGEMENT PREDICTION
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Content DNA extraction and engagement scoring in pipeline
# Added in Sprint 5: Analyst Agent hooks into content generation
# ============================================================================

## L1. Generate Content and Check DNA

1. Go to Content Studio (/content/studio/)
2. Generate a new batch with any idea
3. After generation completes, check the post cards

What to verify:
  ☐ Each post card shows a predicted engagement score (if available)
  ☐ Score is a number or visual indicator (not raw JSON)
  ☐ Different platforms may get different scores (platform-native prediction)

## L2. Check Content DNA on Post

If you can view post details:
  ☐ Content DNA attributes extracted (tone, format, hooks, themes)
  ☐ DNA is stored correctly (not empty or error JSON)

## L3. Content DNA Summary in Daily Brief

After generating several batches:
  ☐ Daily Brief shows "best performing content attributes" section
  ☐ Attributes reflect actual content you've created
  ☐ Summary is human-readable prose, not raw data


# ============================================================================
# PHASE M: ADAPT AGENT — SMART SCHEDULING
# ============================================================================
# Estimated time: 5 minutes
# What you're testing: Optimal time suggestions and auto-scheduling
# Added in Sprint 6: Adapt Agent integration
# ============================================================================

## M1. Auto-Schedule with Adapt Agent

1. Go to Settings (/accounts/settings/)
2. Turn ON "Auto-approve posts"
3. Save
4. Go to Content Studio
5. Generate a new batch

What to verify:
  ☐ Posts are auto-approved AND auto-scheduled (Adapt Agent picks times)
  ☐ Each post scheduled at a different time (no conflicts)
  ☐ Scheduled times appear reasonable (not 3 AM unless data suggests it)
  ☐ Check Queue page — posts should appear with scheduled times

## M2. No Double-Booking

1. Check the Queue for scheduled posts
2. Verify no two posts for the SAME platform are at the exact same time

What to verify:
  ☐ Adapt Agent avoids scheduling conflicts
  ☐ Different platforms CAN be at the same time (that's fine)
  ☐ Same platform posts are spaced apart

## M3. Turn Off Auto-Approve

1. Go back to Settings
2. Turn OFF "Auto-approve posts"
3. Save
4. Generate another batch

What to verify:
  ☐ Posts go back to "Pending Approval" status (not auto-scheduled)
  ☐ Auto-schedule is only active when auto-approve is ON


# ============================================================================
# PHASE N: INBOX / ENGAGEMENT
# ============================================================================
# Estimated time: 2 minutes
# What you're testing: Empty inbox state
# ============================================================================

Navigate to Inbox (/engage/)

What to verify:
  ☐ Empty inbox state displays cleanly
  ☐ No errors (interactions are platform-synced, so empty is expected)


# ============================================================================
# PHASE O: SETTINGS VERIFICATION
# ============================================================================
# Estimated time: 3 minutes
# What you're testing: Profile/settings persistence and editing
# ============================================================================

Navigate to Settings (/accounts/settings/)

## O1. Verify Onboarding Data Persisted
  ☐ Full name: Amara Ochieng
  ☐ Company: DigiBridge Academy
  ☐ Website: https://digibridge.org
  ☐ Brand voice: The full paragraph you entered
  ☐ Target audience: The full description you entered
  ☐ Industry: Education / Non-Profit
  ☐ Goals: All 5 you selected
  ☐ Posting frequency: 7

## O2. Modify Settings
1. Change timezone to Africa/Nairobi (EAT, UTC+3)
2. Change daily brief time to 07:00
3. Upload a profile avatar (any image)
4. Save

What to verify:
  ☐ All changes save without errors
  ☐ Avatar displays in sidebar (bottom-left user menu)
  ☐ Timezone applies to post scheduling times

## O3. Toggle Autonomy Settings
1. Turn ON auto-approve posts
2. Save
3. Turn it back OFF
4. Save

What to verify:
  ☐ Toggle saves correctly each time
  ☐ Setting persists across page reloads


# ============================================================================
# PHASE P: EDGE CASES & STRESS TESTS
# ============================================================================
# Estimated time: 10 minutes
# What you're testing: The platform doesn't break under unusual input
# ============================================================================

## P1. Empty Idea Submission
1. Go to Content Studio
2. Leave the idea field blank
3. Click Generate

What to verify:
  ☐ Validation error appears (not a 500 error)
  ☐ No empty seed is created

## P2. Very Long Idea
Submit an idea that's 2000+ characters (paste a long paragraph).

What to verify:
  ☐ Content generates successfully (AI handles long input)
  ☐ No truncation errors

## P3. Special Characters
Idea: Use emoji, quotes, ampersands, angle brackets:
```
Sarah's <first> "sale" was $500 & she said "I can't believe it!" 🎉🇰🇪
50% of graduates earn >$300/month — that's REAL impact ❤️‍🔥
```

What to verify:
  ☐ Special characters don't break the form or template rendering
  ☐ AI generates content incorporating the characters properly

## P4. Rapid-Fire Generation
1. Submit an idea
2. While it's still processing, submit ANOTHER idea

What to verify:
  ☐ Both processing cards appear
  ☐ Both generate successfully (no race condition)
  ☐ Posts from both appear grouped separately

## P5. Regenerate Multiple Times
1. Click Regenerate on the same post 3 times in a row

What to verify:
  ☐ Each regeneration produces different content
  ☐ No errors on consecutive regenerations
  ☐ Post card updates correctly each time

## P6. Mobile Responsiveness
Use Chrome DevTools (F12 → Toggle Device → iPhone 14 Pro or similar)

Test on mobile viewport:
  ☐ Content Studio form is usable
  ☐ Post cards stack vertically and are readable
  ☐ Group headers don't overflow
  ☐ Batch schedule modal fits screen
  ☐ Sidebar collapses or becomes a hamburger menu
  ☐ All buttons are tappable (not too small)


# ============================================================================
# BONUS CONTENT IDEAS FOR DIGIBRIDGE TESTING
# ============================================================================
# Use these to generate more batches and thoroughly test AI variety.
# ============================================================================

## Idea 5: Donor Transparency
```
Every dollar donated to DigiBridge this quarter: $45,000 received. 
$38,000 on instructor salaries and equipment. $4,200 on internet 
connectivity. $2,800 admin. $0 on luxury. Full breakdown in our 
quarterly transparency report — link in bio.
```

## Idea 6: Mentor Call-to-Action
```
We need 10 volunteer mentors who can give 2 hours/week on Zoom.
Skills needed: Python, UI/UX design, copywriting, digital marketing.
You'll be paired with a refugee mentee who is HUNGRY to learn.
Apply at digibridge.org/mentor
```

## Idea 7: Industry Challenge / Debate
```
Unpopular opinion: International aid organizations should be training
refugees in high-income digital skills instead of distributing food 
packages forever. Dependency isn't compassion. Self-sufficiency is.
Let's debate.
```

## Idea 8: Celebration / Milestone
```
🎓 CLASS OF 2026 GRADUATION DAY 🎓
47 refugees just completed our intensive web development bootcamp.
12 already have their first clients. 8 earned $100+ in their first week.
To every donor, mentor, and partner who made this possible: THANK YOU.
```

## Idea 9: Behind the Technology
```
Our training center in Kakuma runs on 3 refurbished servers, 30 donated 
Chromebooks, and 2 Starlink dishes. Total tech budget: $12,000. Comparable 
coding bootcamp in Nairobi charges $5,000 per student. We trained 47 
students for $255 each. Let that sink in.
```

## Idea 10: Hiring Pipeline
```
HIRING ALERT for tech companies: Our latest cohort of 15 junior developers
is ready for remote work. Skills: HTML/CSS, JavaScript, React, Python, Git.
They work in East African timezone. Rates start at $15/hr. Quality is real.
Portfolio reviews available at digibridge.org/hire
```


# ============================================================================
# TEST COMPLETION CHECKLIST
# ============================================================================

## Core Flows (Phase A-C)
  ☐ Signup → login (no email verification)
  ☐ Express onboarding completed (path → Step 1 → Step 2 confirm)
  ☐ All sidebar pages load without errors (empty states)
  ☐ Platform OAuth connection (at least 2 platforms)
  ☐ Platform disconnect + reconnect
  ☐ Agent listing + toggle + configure links

## Content Pipeline (Phase E-F)
  ☐ Idea submission with spinner (no page reload)
  ☐ Processing card appears inline
  ☐ Posts appear automatically when done (no refresh)
  ☐ Posts are platform-specific (not identical copies)
  ☐ Posts grouped by seed idea
  ☐ Multiple batches stay separate
  ☐ Partial platform selection works (2 of 5)

## Post Actions (Phase F)
  ☐ Approve single post (Post Now)
  ☐ Approve single post (Quick Schedule)
  ☐ Approve single post (Exact Time)
  ☐ Reject a post
  ☐ Regenerate a post (new content, spinner works)
  ☐ Edit a post
  ☐ Batch approve all in a seed group

## Pipeline Verification (Phase G)
  ☐ Approved posts appear in Queue
  ☐ Scheduled posts appear on Calendar/Timeline
  ☐ Published posts move to "Published" section in Queue
  ☐ Failed posts show in "Failed" section with error info

## Daily Brief & Intelligence (Phase J — Sprint 5+6)
  ☐ Daily Brief page loads without errors
  ☐ Performance insight card displays (or clean empty state)
  ☐ Trending topics show with urgency/relevance badges
  ☐ Suggested posts show with content type + timing badges
  ☐ Agent activity summary present
  ☐ Content pipeline stats accurate
  ☐ Content DNA summary visible (after enough content generated)

## Agent Activity & Configuration (Phase K — Sprint 6)
  ☐ Agent Activity Log loads (/agents/activity/)
  ☐ Activity entries show agent type, action, status, tokens, timestamp
  ☐ Agent Detail page loads for each agent (/agents/<slug>/)
  ☐ Agent stats displayed (total actions, today, tokens)
  ☐ Custom instructions editor works (save + persist)
  ☐ Recent activity feed shows per-agent actions
  ☐ Configure links on agent cards work
  ☐ Activity Log link from agent control page works

## Content DNA & Prediction (Phase L — Sprint 5)
  ☐ Posts show predicted engagement scores after generation
  ☐ Content DNA attributes extracted on generated posts
  ☐ Content DNA summary appears in Daily Brief

## Smart Scheduling (Phase M — Sprint 6)
  ☐ Auto-approve ON → posts auto-scheduled by Adapt Agent
  ☐ No double-booking (same platform, same time)
  ☐ Auto-approve OFF → posts back to pending approval
  ☐ Scheduled times are reasonable (Adapt Agent picks good times)

## Supporting Features (Phase H-I, N-O)
  ☐ Notifications generate + display + mark-read
  ☐ Settings save and persist
  ☐ Avatar upload works
  ☐ Analytics page loads (even if empty)
  ☐ Inbox page loads (empty state)

## Edge Cases (Phase P)
  ☐ Empty form submission blocked
  ☐ Special characters handled
  ☐ Mobile responsive
  ☐ Concurrent generation works
  ☐ Consecutive regenerations work

# ============================================================================
# AFTER TESTING: WHAT TO LOOK FOR
# ============================================================================

## Red Flags (Must Fix Before Launch)
- Any 500 error on any page
- OAuth failing ("Invalid App ID", tokens not saving, redirects broken)
- Posts generating identical content across platforms
- HTMX not working (page reloads instead of inline updates)
- Posts not appearing after generation (refresh required)
- Batch approve not scheduling all posts
- Mobile layout completely broken
- Daily Brief page crashes (500 error)
- Agent Activity Log page crashes
- Agent Detail page returns 404 for valid slugs
- Custom instructions not saving (data loss)
- Auto-schedule creating duplicate time slots (double-booking)

## Yellow Flags (Fix Soon)
- Slow generation (>30 seconds per batch)
- Poor AI content quality (generic, not brand-voice aligned)
- Regenerate producing nearly identical content
- Missing empty states on any page
- Notification count not updating in real-time
- Daily Brief content feels generic (Research Agent not respecting industry)
- Content DNA always empty (Analyst Agent not extracting)
- Engagement prediction scores all identical
- Agent activity log shows no entries after running content pipeline
- Custom instructions not affecting agent output
- Adapt Agent scheduling everything at the same time

## Green Signals (Ship It)
- All pages load cleanly in empty and populated states
- Content is platform-native and brand-voice aligned
- Full HTMX flow works: idea → spinner → processing → posts appear
- Approve/reject/edit/regenerate all work inline
- Queue and Calendar reflect scheduled posts accurately
- OAuth connect/disconnect cycles cleanly
- Daily Brief shows meaningful insights and trending topics
- Content DNA extracts relevant attributes from generated content
- Engagement prediction varies by platform and content type
- Agent Activity Log records all agent actions with tokens/timing
- Agent Detail pages show accurate per-agent stats
- Custom instructions visibly influence agent behavior
- Auto-schedule picks sensible, conflict-free times
- Research Agent trends are relevant to user's niche
