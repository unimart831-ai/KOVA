# Kova AI — 14 Test Businesses for Full Platform Testing

> **Pricing source of truth:** Plan tiers, caps, and monthly prices are defined in [KOVA_PLANS_GUIDE.md](./KOVA_PLANS_GUIDE.md) and `apps/billing/models.py` → `PLAN_LIMITS` (Plan v2, May 2026). If this doc disagrees, trust the guide.

> **Purpose:** 14 fictional businesses across different industries to onboard onto Kova and test every feature end-to-end.
> Each business has a unique profile, plan, platforms, and testing focus.

---

## Quick Reference

| # | Business | Category | Plan | Primary Platforms | Key Test Focus |
|---|----------|----------|------|-------------------|----------------|
| 1 | Mara & Moto | E-commerce (Fashion) | Agency | IG, TikTok, Pinterest, FB, WhatsApp | Products, Shopify, Revenue Pixel, WhatsApp Commerce |
| 2 | PixelCraft Studios | Web Design Agency | Pro | LinkedIn, Twitter, Instagram, Threads | Teams, Leads, Campaigns, B2B Content |
| 3 | Elimu Hub | Online Learning | Growth | YouTube, LinkedIn, Twitter, FB | Email Sequences, Subscribers, A/B Testing |
| 4 | Nyama Mama Express | Restaurant / Food | Pro | Instagram, TikTok, WhatsApp, FB | Memes, WhatsApp Orders, Visual Content, Media Queue |
| 5 | CloudStack Africa | SaaS / Tech | Agency | LinkedIn, Twitter, Bluesky, YouTube | API, Competitor Intel, Analytics, Strategist Agent |
| 6 | Makao Homes | Real Estate | Pro | FB, Instagram, WhatsApp, LinkedIn | Lead Capture, WhatsApp Broadcasts, Kova Pages |
| 7 | Coach Amara Fitness | Personal Brand / Fitness | Starter | Instagram, TikTok, Twitter | Starter Plan Limits, Link-in-Bio, Basic Content |
| 8 | Green Roots Foundation | NGO / Non-Profit | Growth | FB, Twitter, LinkedIn, Instagram | Engagement, Email Marketing, Partner Program |
| 9 | Neon Wave Agency | Creative / Marketing Agency | Agency | All 10 Platforms | Multi-Brand Teams, Media Queue, Full Agent Suite |
| 10 | PesaPal Finance | Fintech / Financial Services | Growth | LinkedIn, Twitter, FB, Threads | Compliance Tone, Competitor Tracking, Campaigns |
| 11 | Kakuma Wholesale | Wholesale / Mtumba & Retail | Pro | WhatsApp, FB, TikTok, Instagram | WhatsApp Commerce, Products, Refugee Market, Media Queue |
| 12 | Kawaida Hair & Beauty | Salon & Beauty Services | Growth | WhatsApp, Instagram, Facebook | Salon persona, WhatsApp-first SME, Magic Fill + Industry Pack |
| 13 | Bridge Academy | EdTech / Skills Training (ideation stage) | Growth | LinkedIn, Twitter, Instagram | Distinctive voice style transfer, code-switch (English+Swahili+Sheng), Manual onboarding path |
| 14 | Django Sasa | Developer Education — 30-Day Django Track | Growth | LinkedIn, Facebook, Twitter | Sequential curriculum content, Email sequence backbone, Cohort campaigns, 6-pillar discipline |

---

## Business 1: Mara & Moto

**Category:** E-commerce — Fashion & Lifestyle
**Plan:** Agency (KES 7,999/mo)
**Website:** maraandmoto.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Mara & Moto |
| Industry | Fashion & Lifestyle |
| Target Audience | Urban Kenyan women 22-35, fashion-forward, mobile-first shoppers |
| Brand Voice | Bold, confident, Nairobi street-style energy — like your stylish best friend who always knows what's trending |
| Tone | Playful, aspirational, unapologetic |
| Content Pillars | New arrivals & lookbooks, Style tips & outfit inspo, Behind-the-scenes (production, fabric sourcing), Customer spotlights, Seasonal campaigns (Jamhuri Day, Valentine's, Back-to-School) |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| Instagram | @maraandmoto | Product shots, Reels, Stories |
| TikTok | @maraandmoto | Try-on hauls, style hacks, trending sounds |
| Pinterest | Mara & Moto | Lookbook boards, outfit inspiration |
| Facebook | Mara & Moto | Product launches, community engagement |
| WhatsApp | +254 712 345 001 | Order updates, VIP customer broadcasts |

### Products to Add (10+)

| Product | Price (KES) | Stock | Category |
|---------|-------------|-------|----------|
| Ankara Midi Skirt | 2,500 | 45 | Bottoms |
| Denim Crop Jacket | 3,800 | 20 | Outerwear |
| Beaded Statement Necklace | 1,200 | 100 | Accessories |
| Silk Wrap Dress | 4,500 | 15 | Dresses |
| Canvas Tote - "Nairobi Nights" | 1,800 | 60 | Bags |
| Linen Wide-Leg Trousers | 3,200 | 30 | Bottoms |
| Kitenge Print Headwrap | 800 | 200 | Accessories |
| Block Heel Sandals | 3,500 | 25 | Shoes |
| Graphic Tee - "Made in Kenya" | 1,500 | 80 | Tops |
| Oversized Sunglasses | 2,000 | 50 | Accessories |

### Features to Test

- [ ] **Product Catalog** — Add all 10 products with images, categories, stock levels
- [ ] **Shopify Integration** — Connect store, test order webhook → conversion tracking
- [ ] **Kova Pixel** — Install on maraandmoto.co.ke, track page_view, add_to_cart, purchase events
- [ ] **Revenue Attribution** — UTM-tagged posts → pixel click → Shopify order → multi-touch attribution
- [ ] **WhatsApp Commerce** — VIP broadcast to repeat buyers, order confirmation sequences
- [ ] **WhatsApp Status Studio** — Daily product teasers via Status
- [ ] **Media Queue** — Instagram product photo queue (3x daily)
- [ ] **Meme Intelligence** — Fashion meme adaptations (trending audio + product placement)
- [ ] **AI Image Generation** — Product lifestyle images
- [ ] **Email Marketing** — New arrival newsletters, abandoned cart sequences
- [ ] **Stock Alerts** — Set low stock threshold (10 units), test alert generation
- [ ] **Campaigns** — "Jamhuri Day Sale" campaign linking posts + emails + products

### Test Seeds to Create

1. "New Ankara collection drop — 5 pieces, each under KES 3,000"
2. "How to style one wrap dress 4 ways for different occasions"
3. "Customer spotlight: @amani_styles wearing our Kitenge headwrap"
4. "Behind the scenes at our Gikomba fabric sourcing trip"
5. "Flash sale: 24 hours, 30% off all accessories"

---

## Business 2: PixelCraft Studios

**Category:** Web Design & Development Agency
**Plan:** Pro (KES 2,999/mo)
**Website:** pixelcraftstudios.com

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | PixelCraft Studios |
| Industry | Web Design & Digital Agency |
| Target Audience | Kenyan SMEs, startups, and established businesses needing websites, apps, and digital presence |
| Brand Voice | Expert but approachable — we simplify tech jargon. Think senior developer explaining things at a coffee shop |
| Tone | Professional, educational, confident, slightly witty |
| Content Pillars | Web design tips & trends, Client case studies & transformations, Tech education (SEO, UX, performance), Agency life & team culture, Industry insights (East African tech scene) |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| LinkedIn | PixelCraft Studios | Case studies, thought leadership, hiring posts |
| Twitter | @pixelcraftke | Tech tips, industry commentary, threads |
| Instagram | @pixelcraftstudios | Portfolio showcases, team culture, Reels |
| Threads | @pixelcraftstudios | Quick takes, tech opinions |

### Features to Test

- [ ] **Teams** — Create team with 4 members: CEO (owner), designer (editor), developer (editor), strategist (admin)
- [ ] **Brands** — Create 2 client brands under the team: "FreshMart Groceries" and "Safari Tours Kenya"
- [ ] **Lead Capture** — Lead form on Kova Page: "Get a Free Website Audit"
- [ ] **Kova Pages** — Portfolio page with links to case studies, Calendly, and social profiles
- [ ] **Campaigns** — "Q2 Website Refresh" campaign targeting existing clients
- [ ] **Content Creation** — B2B content: LinkedIn articles, Twitter threads, Instagram carousels
- [ ] **Competitor Intelligence** — Track 3 competitors: Jenga Digital, Savannah Digital, Scope Digital
- [ ] **AI Agents** — Research Agent for tech trends, Create Agent for blog-to-social repurposing
- [ ] **A/B Testing** — Test "technical" vs "simplified" language in LinkedIn posts
- [ ] **Email Marketing** — Monthly newsletter to client list (200 subscribers)

### Test Seeds to Create

1. "5 signs your business website is losing you customers (and how to fix each one)"
2. "Case study: How we rebuilt FreshMart's e-commerce site and increased orders by 180%"
3. "The real cost of a cheap website vs a professional one — a breakdown"
4. "Our design process from brief to launch — the 6-step PixelCraft method"
5. "East Africa's tech scene is booming — here's what SMEs need to know for 2026"

---

## Business 3: Elimu Hub

**Category:** Online Learning Platform
**Plan:** Growth (KES 1,499/mo)
**Website:** elimuhub.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Elimu Hub |
| Industry | EdTech / Online Learning |
| Target Audience | Kenyan university students and young professionals (18-28) looking to learn digital skills, freelancing, and career development |
| Brand Voice | Encouraging big-sibling energy — "I've been where you are, here's the shortcut." Relatable, no pretension |
| Tone | Motivational, practical, conversational, culturally aware (mixes English and Sheng naturally) |
| Content Pillars | Free learning tips & mini-lessons, Student success stories, Career advice & job market insights, Course launches & promotions, Study motivation & productivity hacks |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| YouTube | Elimu Hub | Tutorials, mini-courses, student testimonials |
| LinkedIn | Elimu Hub | Career advice, course announcements |
| Twitter | @elimuhub | Study tips, threads, industry commentary |
| Facebook | Elimu Hub | Community engagement, event announcements |

### Features to Test

- [ ] **Email Sequences** — 7-day "Welcome to Elimu" drip sequence for new subscribers
- [ ] **Email Lists** — Segment: "Free users", "Paid students", "Course completers"
- [ ] **Smart Lists** — Auto-add subscribers tagged "completed_course" to alumni list
- [ ] **A/B Testing** — Test motivational hooks vs practical hooks on Twitter
- [ ] **Subscriber Growth** — Track email subscriber count toward Growth plan limit (2,500)
- [ ] **Content Seeds** — Educational content optimized for each platform
- [ ] **Analytics** — Track which content types drive most course signups
- [ ] **Kova Pages** — "Free Resources" page with course links and email signup form
- [ ] **Lead Capture** — "Download Free Career Guide" form → lead created → enrolled in sequence
- [ ] **Daily Brief** — Verify brief shows subscriber growth and content performance

### Test Seeds to Create

1. "5 free tools every Kenyan freelancer needs to start earning online today"
2. "I went from zero clients to 50K/month freelancing — here's the exact path"
3. "Stop applying for jobs the old way. Here's what actually works in 2026"
4. "New course drop: 'Data Analysis with Python' — from zero to job-ready in 8 weeks"
5. "Study hack: The Pomodoro technique, but make it Kenyan (with ugali breaks)"

---

## Business 4: Nyama Mama Express

**Category:** Restaurant / Food & Beverage
**Plan:** Pro (KES 2,999/mo)
**Website:** nyamamamaexpress.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Nyama Mama Express |
| Industry | Restaurant / Food Delivery |
| Target Audience | Nairobi food lovers 20-40, office workers ordering lunch, weekend dinner crowd, food enthusiasts |
| Brand Voice | Warm, mouth-watering, proudly Kenyan — like a chef who loves what they cook and wants you to taste everything |
| Tone | Fun, appetizing, community-driven, occasionally cheeky |
| Content Pillars | Daily specials & menu highlights, Behind-the-kitchen content, Food culture & Kenyan cuisine stories, Customer reviews & UGC, Weekend & event catering promos |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| Instagram | @nyamamamaexpress | Food photography, Reels (cooking process), Stories (daily specials) |
| TikTok | @nyamamamaexpress | Cooking videos, food ASMR, trending challenges |
| WhatsApp | +254 712 345 004 | Order taking, menu sharing, loyalty broadcasts |
| Facebook | Nyama Mama Express | Menu updates, event catering, community posts |

### Products to Add (Menu Items)

| Item | Price (KES) | Category |
|------|-------------|----------|
| Nyama Choma Platter (500g) | 1,200 | Grills |
| Pilau Rice + Kachumbari | 450 | Rice Dishes |
| Ugali + Sukuma + Beef Stew | 400 | Traditional |
| Chicken Tikka Wrap | 550 | Wraps |
| Smoky BBQ Ribs | 1,500 | Grills |
| Chapati Platter (4 pcs) | 200 | Sides |
| Passion Fruit Juice (500ml) | 150 | Drinks |
| Chocolate Lava Cake | 350 | Desserts |

### Features to Test

- [ ] **Meme Intelligence** — Food memes, trending audio + Kenyan food culture
- [ ] **WhatsApp Ordering** — Inbox for order conversations, AI-assisted replies
- [ ] **WhatsApp Broadcasts** — "Weekend Special" broadcasts to VIP list
- [ ] **WhatsApp Status Studio** — Daily menu specials via Status (auto-scheduled)
- [ ] **WhatsApp Drip Sequences** — New customer welcome sequence (menu → delivery areas → loyalty program)
- [ ] **Media Queue** — Instagram food photo queue (lunch + dinner posts)
- [ ] **AI Image Generation** — Food styling images for menu items
- [ ] **Engagement** — Reply to food reviews, handle complaints with care
- [ ] **Kova Pixel** — Track menu views → order conversions on website
- [ ] **Products** — Full menu catalog with category organization

### Test Seeds to Create

1. "Friday Nyama Choma special — 500g platter with 2 sides for only KES 999"
2. "Watch our chef prepare the perfect pilau from scratch — the secret is in the spice mix"
3. "Customer review: 'Best ugali in Westlands, no debate' — thank you @foodie_nancy!"
4. "Catering for your office team? We do corporate lunch packages starting KES 350/person"
5. "Chapati hack: Why our chapatis are fluffier than your auntie's (sorry, auntie)"

---

## Business 5: CloudStack Africa

**Category:** SaaS / B2B Technology
**Plan:** Agency (KES 7,999/mo)
**Website:** cloudstackafrica.com

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | CloudStack Africa |
| Industry | Cloud Infrastructure / SaaS |
| Target Audience | CTOs, VP Engineering, DevOps leads at mid-to-large East African companies; funded startups scaling infrastructure |
| Brand Voice | Authoritative thought leader — data-driven, zero fluff. Like a trusted CTO advisor who's seen every scaling challenge |
| Tone | Technical but accessible, confident, forward-looking, occasionally contrarian |
| Content Pillars | Cloud infrastructure insights, African tech ecosystem analysis, Engineering best practices, Product updates & case studies, Developer education & tutorials |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| LinkedIn | CloudStack Africa | Thought leadership, case studies, hiring |
| Twitter | @cloudstackafr | Tech commentary, threads, developer tips |
| Bluesky | @cloudstack.africa | Alt-tech community, developer culture |
| YouTube | CloudStack Africa | Webinar recordings, tutorials, demos |

### Features to Test

- [ ] **REST API** — Full API integration testing (Agency plan enables API access)
- [ ] **Competitor Intelligence** — Track: AWS Africa, Azure Africa, Safaricom Cloud, Liquid Intelligent Technologies
- [ ] **Strategist Agent** — Full strategy cycle: market analysis → content strategy → seed creation
- [ ] **Analytics Deep Dive** — Content DNA extraction, engagement prediction, performance correlation
- [ ] **Revenue Attribution** — Blog → demo request → conversion tracking
- [ ] **A/B Testing** — Technical depth vs executive summary on LinkedIn
- [ ] **Teams** — Engineering (3 writers), Marketing (2), CEO — test all roles
- [ ] **Campaigns** — "CloudStack Summit 2026" — multi-platform event campaign
- [ ] **Email Marketing** — Developer newsletter (5,000 subscribers), event invite sequences
- [ ] **Lead Capture** — "Get a Cloud Cost Audit" form on Kova Page

### Test Seeds to Create

1. "Why 73% of East African startups are over-provisioning cloud resources — and what to do about it"
2. "We migrated SafariBank's entire infrastructure to our platform in 72 hours. Here's how"
3. "The real cost of downtime in Africa: $12,000/minute average. Is your DR plan ready?"
4. "CloudStack vs AWS Africa: honest comparison from someone who's deployed on both"
5. "Announcing CloudStack Summit 2026 — the largest cloud infrastructure event in East Africa"

---

## Business 6: Makao Homes

**Category:** Real Estate
**Plan:** Pro (KES 2,999/mo)
**Website:** makaohomes.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Makao Homes |
| Industry | Real Estate / Property |
| Target Audience | Kenyan middle-class families and young professionals (28-45) looking to buy or rent homes in Nairobi, Kiambu, and Machakos |
| Brand Voice | Trustworthy guide through the biggest purchase of your life — knowledgeable, patient, never pushy |
| Tone | Warm, reassuring, informative, transparent about pricing |
| Content Pillars | Property listings & virtual tours, Home buying education, Market insights & price trends, Neighborhood guides, Customer move-in stories |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| Facebook | Makao Homes | Listings, community engagement, live virtual tours |
| Instagram | @makaohomes | Property photos, Reels (walkthroughs), Stories |
| WhatsApp | +254 712 345 006 | Inquiry handling, viewing scheduling, document sharing |
| LinkedIn | Makao Homes | Market analysis, company updates |

### Features to Test

- [ ] **Lead Capture** — "Find Your Dream Home" form (budget, bedrooms, location) → lead created with tags
- [ ] **Lead CRM** — Track leads through: new → contacted → viewing_scheduled → offer_made → closed
- [ ] **WhatsApp Broadcasts** — "New listings this week" broadcast to active leads
- [ ] **WhatsApp Drip Sequences** — Buyer education sequence: financing → legal process → inspection tips → offer strategy
- [ ] **Kova Pages** — 3 pages: Main portfolio, "Kilimani Properties", "Syokimau Plots"
- [ ] **Engagement** — Reply to property inquiries on Instagram/Facebook
- [ ] **Campaigns** — "Syokimau Phase 3 Launch" multi-channel campaign
- [ ] **Email Marketing** — Monthly "Property Market Update" newsletter
- [ ] **Analytics** — Track which property types get most engagement
- [ ] **Memes** — Real estate memes (house hunting humor, Nairobi rent jokes)

### Test Seeds to Create

1. "New listing: 3-bedroom apartment in Kilimani — KES 15M, 24/7 security, rooftop pool"
2. "First-time buyer? Here's every cost beyond the purchase price that nobody tells you about"
3. "Syokimau vs Athi River in 2026: Which one gives better value? Full comparison"
4. "Client story: The Kamaus went from renting in Umoja to owning in Syokimau in 18 months"
5. "Is now a good time to buy? Nairobi property market analysis for April 2026"

---

## Business 7: Coach Amara Fitness

**Category:** Personal Brand / Health & Fitness
**Plan:** Starter (KES 499/mo)
**Website:** (none — uses Kova Page as main link)

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Coach Amara Fitness |
| Industry | Health, Fitness & Wellness |
| Target Audience | Kenyan women 25-40 who want to get fit but feel intimidated by gym culture. Beginners and busy professionals |
| Brand Voice | Your hype-woman in the gym — energetic, relatable, body-positive. "You showed up, that's already winning" |
| Tone | Motivational, inclusive, fun, no shame |
| Content Pillars | Workout routines (home + gym), Nutrition tips (Kenyan foods), Transformation stories, Mindset & consistency motivation, Q&A and myth-busting |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| Instagram | @coachamara | Workout Reels, transformation posts, Stories |

*Note: Starter plan allows only 1 social account*

### Features to Test (Starter Plan Limits)

- [ ] **Starter plan enforcement** — Only 1 platform, 15 posts/month, 5 seeds/month
- [ ] **Content Creation** — Test hitting the 15-post monthly ceiling
- [ ] **Seed Limits** — Test hitting the 5-seed monthly ceiling
- [ ] **Agents** — Only Create + Analyst available (verify others are locked)
- [ ] **Kova Pages** — 1 page only (link-in-bio): coaching program link, free guide, social links
- [ ] **Lead Capture** — 10 leads max: "Join My 30-Day Challenge" form
- [ ] **Products** — 5 max: coaching packages (1-on-1, group, challenge)
- [ ] **Email** — 50 subscribers max: weekly motivation email
- [ ] **No WhatsApp** — Verify WhatsApp features are blocked
- [ ] **No Memes** — Verify meme features are blocked
- [ ] **No A/B Testing** — Verify A/B test creation is blocked
- [ ] **No Teams** — Verify team creation is blocked
- [ ] **Upgrade prompts** — Verify upgrade CTAs appear when limits hit
- [ ] **Daily Brief** — Verify brief works on Starter

### Products to Add

| Product | Price (KES) | Type |
|---------|-------------|------|
| 1-on-1 Coaching (Monthly) | 8,000 | Service |
| Group Fitness Program (6 weeks) | 3,500 | Service |
| 30-Day Home Workout Challenge | 1,500 | Digital |
| Custom Meal Plan | 2,000 | Digital |
| Resistance Band Set | 2,500 | Product |

### Test Seeds to Create

1. "10-minute morning workout you can do before your 8am meeting — no equipment needed"
2. "What I eat in a day — healthy Kenyan meals that actually taste good and keep you full"
3. "Transformation Tuesday: Jane lost 12kg in 4 months with home workouts only"
4. "Stop doing 100 sit-ups for abs. Here's what actually works (3 exercises)"
5. "30-Day Challenge starts Monday! Link in bio to join 🔥"

---

## Business 8: Green Roots Foundation

**Category:** NGO / Non-Profit
**Plan:** Growth (KES 1,499/mo)
**Website:** greenrootsfoundation.org

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Green Roots Foundation |
| Industry | Environmental Conservation / Non-Profit |
| Target Audience | Environmentally conscious Kenyans 20-45, potential donors (diaspora + corporate CSR), volunteers, policy makers |
| Brand Voice | Passionate storyteller with data — "Here's the problem, here's the proof, here's how YOU can help today" |
| Tone | Urgent but hopeful, emotionally compelling, evidence-based, community-focused |
| Content Pillars | Impact stories (trees planted, communities served), Environmental education, Volunteer spotlights, Donation campaigns, Policy advocacy & awareness |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| Facebook | Green Roots Foundation | Community stories, event promotion, donation drives |
| Twitter | @greenrootsorg | Advocacy, data points, threads on environmental issues |
| LinkedIn | Green Roots Foundation | Corporate partnerships, impact reports, thought leadership |

*Note: Growth plan allows 3 social accounts*

### Features to Test

- [ ] **Growth plan limits** — 3 platforms, 60 posts/month, 30 seeds/month
- [ ] **Engagement** — Community replies, volunteer coordination, donor thank-yous
- [ ] **Email Marketing** — Monthly impact newsletter (2,500 subscriber limit)
- [ ] **Email Sequences** — Donor welcome sequence: thank you → impact update → next campaign
- [ ] **Smart Lists** — Auto-segment: "monthly_donors", "one_time_donors", "volunteers"
- [ ] **Campaigns** — "Plant 10,000 Trees by June" campaign
- [ ] **Partner Program** — Test as a Kova partner (NGO referral use case)
- [ ] **A/B Testing** — Emotional appeal vs data-driven appeal for donation posts
- [ ] **Analytics** — Track which stories drive most engagement and donations
- [ ] **Kova Pages** — 3 pages: Main, "Donate", "Volunteer"
- [ ] **Leads** — Volunteer signups (100 lead limit on Growth)

### Test Seeds to Create

1. "We planted 2,000 trees in Karura Forest last month. Here's the before and after"
2. "Kenya loses 12,000 hectares of forest annually. Here's what that means for your water supply"
3. "Meet Wanjiku — she volunteers every Saturday and has planted 500 trees this year"
4. "Corporate partner spotlight: How Safaricom's CSR team helped us reach 50,000 trees"
5. "KES 500 plants 10 trees. That's less than your Friday dinner. Donate today"

---

## Business 9: Neon Wave Agency

**Category:** Creative & Marketing Agency (Multi-Brand)
**Plan:** Agency (KES 7,999/mo)
**Website:** neonwave.agency

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Neon Wave Agency |
| Industry | Creative & Marketing Agency |
| Target Audience | Brands and businesses across East Africa looking for social media management, content creation, and brand strategy |
| Brand Voice | Creative rebels with a strategy — bold, trend-setting, slightly irreverent. "We don't follow trends, we set them" |
| Tone | Creative, confident, edgy, culturally sharp |
| Content Pillars | Campaign showcases & case studies, Marketing trend commentary, Creative process & behind-the-scenes, Industry hot takes, Team culture & hiring |

### Platforms to Connect (All 10 — Agency Plan)

| Platform | Handle |
|----------|--------|
| Twitter | @neonwaveke |
| LinkedIn | Neon Wave Agency |
| Instagram | @neonwave.agency |
| Facebook | Neon Wave Agency |
| TikTok | @neonwaveagency |
| YouTube | Neon Wave Agency |
| Pinterest | Neon Wave Agency |
| Threads | @neonwave.agency |
| Bluesky | @neonwave.agency |
| WhatsApp | +254 712 345 009 |

### Team Structure (Test All Roles)

| Member | Email | Role | Responsibility |
|--------|-------|------|---------------|
| Kai Mwangi (Founder) | kai@neonwave.agency | Owner | Strategy, billing, overall management |
| Zara Odhiambo | zara@neonwave.agency | Admin | Team management, brand assignments |
| Derek Njeru | derek@neonwave.agency | Editor | Content creation, scheduling |
| Aisha Wambui | aisha@neonwave.agency | Editor | Design, media queue management |
| Brian Kimani | brian@neonwave.agency | Viewer | Client reporting, read-only access |

### Client Brands (Under Team)

| Brand | Industry | Voice |
|-------|----------|-------|
| Savanna Safaris | Tourism | Adventurous, breathtaking, bucket-list energy |
| TechBridge Academy | Education | Smart, youthful, opportunity-focused |
| Brew & Bite Café | F&B | Cozy, artisanal, Instagram-worthy |

### Features to Test

- [ ] **All 10 Platforms** — Connect and post to every platform
- [ ] **Teams** — Full team with 5 members across all 4 roles
- [ ] **Multi-Brand** — 3 client brands with different voices, platforms, content
- [ ] **Role Permissions** — Verify owner/admin/editor/viewer access for each action
- [ ] **Media Queue** — Separate queues per brand per platform
- [ ] **All 6 AI Agents** — Research, Create, Adapt, Engage, Analyst, Strategist
- [ ] **WhatsApp Suite** — Full suite: inbox, Status, broadcasts, sequences, channels
- [ ] **Meme Intelligence** — Cross-brand meme adaptations
- [ ] **Unlimited Posts** — Verify no post limit on Agency plan
- [ ] **Unlimited Seeds** — Verify no seed limit
- [ ] **Campaigns** — Multi-brand campaigns
- [ ] **AI Images** — 500/month limit testing
- [ ] **Email Marketing** — Unlimited subscribers, per-brand newsletters
- [ ] **REST API** — API access for external tool integration
- [ ] **Admin Dashboard** — Full admin view of agency operations

### Test Seeds to Create

1. "How Neon Wave turned a local coffee shop into Nairobi's most Instagrammed café — case study"
2. "Marketing budgets in 2026: Where East African brands should actually put their money"
3. "We're hiring! Looking for a crazy-talented video editor who bleeds creativity"
4. "Hot take: Most Kenyan brands are still posting like it's 2019. Here's what's changed"
5. "Behind the scenes of the Savanna Safaris rebrand — from boring to breathtaking"

---

## Business 10: PesaPal Finance

**Category:** Fintech / Financial Services
**Plan:** Growth (KES 1,499/mo)
**Website:** pesapalfinance.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | PesaPal Finance |
| Industry | Fintech / Personal Finance |
| Target Audience | Young Kenyan professionals 25-38 managing their first real income — saving, investing, M-Pesa power users, SACCO members |
| Brand Voice | The financially literate friend you wish you had — clear, trustworthy, makes money talk simple. Never condescending |
| Tone | Educational, trustworthy, encouraging, jargon-free |
| Content Pillars | Personal finance tips (saving, budgeting, debt), Investment education (SACCOs, MMFs, stocks), M-Pesa & mobile money optimization, Financial product comparisons, Money mindset & financial literacy |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| LinkedIn | PesaPal Finance | Professional finance content, partnerships, thought leadership |
| Twitter | @pesapalfinance | Quick tips, threads, market commentary |
| Facebook | PesaPal Finance | Community education, longer posts, user questions |

*Note: Growth plan allows 3 social accounts*

### Features to Test

- [ ] **Compliance-Sensitive Content** — Test that AI-generated content avoids financial advice disclaimers issues
- [ ] **Brand Voice Strictness** — Financial content must be accurate, no hype, no unrealistic promises
- [ ] **Competitor Intelligence** — Track: M-Shwari, KCB M-Pesa, Faulu, Branch
- [ ] **A/B Testing** — Educational tone vs action-oriented tone on Twitter
- [ ] **Campaigns** — "Financial Literacy Month" April campaign
- [ ] **Email Marketing** — Weekly "Money Monday" newsletter
- [ ] **Email Sequences** — "Start Your Investment Journey" 5-email sequence
- [ ] **Analytics** — Which financial topics get most saves/shares (high-intent signals)
- [ ] **Kova Pages** — Financial tools page: calculator links, free budget template, newsletter signup
- [ ] **Lead Capture** — "Get Your Free Budget Template" form
- [ ] **Content DNA** — Extract what makes financial content perform (data? stories? comparisons?)
- [ ] **Daily Brief** — Monitor engagement spikes around market events

### Test Seeds to Create

1. "The 50/30/20 rule adapted for Kenyan salaries — a realistic breakdown for someone earning KES 80K"
2. "M-Pesa vs bank savings account: Where should your emergency fund actually sit?"
3. "I invested KES 5,000/month in an MMF for 2 years. Here's exactly how much I made"
4. "SACCO vs Money Market Fund vs Treasury Bills — which is right for YOUR situation?"
5. "5 money mistakes I see Kenyan millennials make every single month (and the fixes)"

---

## Business 11: Kakuma Wholesale

**Category:** Wholesale & Retail — Mtumba, Bales & New Products
**Plan:** Pro (KES 2,999/mo)
**Website:** kakumawholesale.co.ke

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Kakuma Wholesale |
| Industry | Wholesale / Retail Trade |
| Target Audience | Small traders, shop owners, and retailers in Kakuma Refugee Camp and Kalobeyei Settlement looking for affordable wholesale stock; also targets individual buyers wanting quality clothes, shoes, and household goods at wholesale prices |
| Brand Voice | Straight-talking wholesaler — honest about quality, transparent on pricing, no hidden costs. Like a trusted supplier who picks the best bales for you. Mixes English, Swahili, and basic French (for Congolese community) |
| Tone | Direct, trustworthy, practical, community-oriented |
| Content Pillars | New stock arrivals & bale openings, Price lists & wholesale deals, Sourcing trips (Gikomba/Kamkunji/Eastleigh behind-the-scenes), Customer success stories (traders who grew their shops), Transport & delivery updates (Nairobi → Kakuma route), Quality grading guides (Grade A vs B vs mixed bales) |

### Business Context

Kakuma Wholesale bridges Nairobi's biggest markets to one of East Africa's largest refugee settlements:

**Source Markets (Nairobi):**
- **Gikomba Market** — East Africa's largest mtumba (second-hand clothing) market. Source of bales, individual pieces, and sorted grades
- **Kamkunji Market** — New products hub: shoes, bags, electronics, hardware, household goods
- **Eastleigh ("Little Mogadishu")** — Wholesale hub for new clothing, fabrics, perfumes, electronics. Somali-run wholesale network with direct import connections

**Destination Markets:**
- **Kakuma Refugee Camp** — 250,000+ residents, vibrant market economy, high demand for affordable clothing and goods
- **Kalobeyei Settlement** — 40,000+ residents, growing commercial area, newer market with less competition
- **Kakuma Town** — Host community, shops and market stalls serving both refugees and locals

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|--------------|
| WhatsApp | +254 712 345 011 | Order taking, price lists, stock alerts, delivery updates, customer groups |
| Facebook | Kakuma Wholesale | Product photos, stock arrivals, community engagement, live bale openings |
| TikTok | @kakumawholesale | Bale opening videos, Gikomba sourcing trips, packing & transport content |
| Instagram | @kakumawholesale | Product showcases, before/after (bale → sorted stock), customer spotlights |

### Products to Add (15+)

| Product | Price (KES) | Min Order | Category |
|---------|-------------|-----------|----------|
| Mtumba Bale — Ladies Dresses (45kg) | 8,500 | 1 bale | Bales |
| Mtumba Bale — Men's Shirts (45kg) | 7,000 | 1 bale | Bales |
| Mtumba Bale — Kids Clothing (45kg) | 6,500 | 1 bale | Bales |
| Mtumba Bale — Jeans Mixed (45kg) | 12,000 | 1 bale | Bales |
| Mtumba Bale — T-Shirts (45kg) | 5,500 | 1 bale | Bales |
| Sorted Grade A Dresses (per piece) | 150 | 50 pcs | Sorted Mtumba |
| Sorted Grade A Men's Trousers (per piece) | 200 | 50 pcs | Sorted Mtumba |
| New Canvas Shoes (Kamkunji) | 350 | 12 pairs | New — Shoes |
| New Sneakers Assorted (Eastleigh) | 800 | 6 pairs | New — Shoes |
| New School Shoes (Kamkunji) | 450 | 12 pairs | New — Shoes |
| New Ladies Sandals (Eastleigh) | 250 | 12 pairs | New — Shoes |
| New Bedsheets Set (Eastleigh) | 500 | 10 sets | New — Household |
| Ankara Fabric (6 yards) | 350 | 20 pcs | New — Fabrics |
| Men's Boxer Shorts Pack (3pc) | 200 | 24 packs | New — Undergarments |
| Kids School Bags (Kamkunji) | 300 | 12 pcs | New — Accessories |

### Features to Test

- [ ] **Products Catalog** — Full inventory with wholesale pricing, minimum orders, and source market tags
- [ ] **WhatsApp Commerce** — Primary sales channel: order taking via chat, price list broadcasts, stock alert messages
- [ ] **WhatsApp Broadcasts** — "New Stock Arrived" alerts to trader groups, weekly price lists
- [ ] **WhatsApp Groups** — Separate groups: Kakuma Traders, Kalobeyei Traders, Bulk Buyers
- [ ] **Media Queue** — TikTok bale-opening queue, Instagram product showcase queue
- [ ] **Facebook Live Integration** — Live bale openings with real-time ordering
- [ ] **AI Image Generation** — Product display images, price list graphics
- [ ] **Content DNA** — What wholesale content drives the most inquiries (bale openings? price lists? transport updates?)
- [ ] **Campaigns** — "Back to School" campaign (school shoes, bags, uniforms), "Festive Season Stock-Up" campaign
- [ ] **Meme Intelligence** — Trader humor memes, hustle culture content for the Kakuma market scene
- [ ] **Multi-Language Content** — English + Swahili + French content generation for diverse refugee community
- [ ] **Analytics** — Track which products get most WhatsApp inquiries, which content drives bulk orders
- [ ] **Delivery Tracking Content** — "Your goods are on the way" stories showing Nairobi → Kakuma transport

### Test Seeds to Create

1. "New mtumba bales just landed from Gikomba — Grade A ladies dresses, men's shirts, and kids' clothes. DM to order before they finish 🔥"
2. "Bale opening video: Watch what's inside this 45kg jeans bale we picked up from Gikomba this morning. Grade A quality, zero rejects"
3. "Kamkunji price update: School shoes KES 450/pair (minimum 12 pairs), school bags KES 300. Back-to-school stock available now"
4. "Our Nairobi → Kakuma delivery just arrived! 15 bales of mtumba + 200 pairs of shoes from Eastleigh. Traders, come to our store or WhatsApp to reserve"
5. "How our customer Amina grew her shop in Kalobeyei from 2 bales/month to 10 bales/month in 6 months. Her secret? She focused on sorted Grade A pieces"
6. "Eastleigh wholesale haul: New bedsheets, ankara fabrics, and men's underwear packs — all at Nairobi wholesale prices, delivered to Kakuma"
7. "Price list update for this week (Swahili): Orodha ya bei — nguo za mtumba na bidhaa mpya. Piga simu au WhatsApp kuorder"

### Unique Testing Angles

- **Remote/Rural Commerce:** Tests Kova's ability to serve businesses operating in areas with intermittent internet
- **WhatsApp-First Business:** WhatsApp is the primary platform — more important than any social media
- **Multilingual Content:** Content must work in English, Swahili, and French for the Kakuma community
- **Supply Chain Content:** Sourcing (Nairobi) → Transport → Delivery (Kakuma) is a content story arc
- **Wholesale Pricing:** Tests product catalog with bulk pricing, minimum order quantities
- **Community Trust Building:** In refugee camp markets, trust is everything — content must build reputation
- **Price-Sensitive Audience:** Every shilling matters — content must always lead with value and pricing

---

## Business 12: Kawaida Hair & Beauty

**Category:** Salon & Beauty Services
**Plan:** Growth (KES 1,499/mo)
**Website:** kawaidabeauty.co.ke
**Location:** Eastlands, Nairobi

This is **Kova's flagship persona** — the Eastlands salon owner referenced in the
seed proposal and Business Canvas. Kawaida exercises every Tier-1/Tier-2
onboarding automation we shipped: Magic Fill from Instagram, industry pack
defaults, smart Kenya signup defaults, the WhatsApp completion ping.

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Kawaida Hair & Beauty |
| Industry | Salon & Beauty Services (`salon_beauty`) |
| Target Audience | Working women aged 22–40 in Eastlands, South B, Embakasi, and Donholm; busy professionals booking around work hours; brides-to-be |
| Brand Voice | Warm and confident — like the senior stylist you trust to know what works for your hair. Mixes English and Swahili naturally ("twende, kuna deal mzuri") |
| Tone | Warm, approachable, playful, confident |
| Content Pillars | Transformations & before/after, Service spotlights (braids, treatments, bridal), Beauty tips & care advice (especially for natural and relaxed hair), Behind-the-scenes / team, Client love & testimonials |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| WhatsApp | +254 712 345 012 | Booking confirmations, price lists, daily availability, VIP broadcasts |
| Instagram | @kawaidabeauty | Transformation Reels, service photos, Stories |
| Facebook | Kawaida Hair & Beauty | Community engagement, promotions, page reviews |

*Growth plan allows 3 social accounts — perfect fit*

### Products / Services to Add

| Service | Price (KES) | Duration | Category |
|---------|-------------|----------|----------|
| Box Braids (Medium) | 3,500 | 4 hrs | Braiding |
| Knotless Braids (Long) | 5,000 | 6 hrs | Braiding |
| Cornrows + Beads | 1,500 | 2 hrs | Braiding |
| Silk Press (Natural Hair) | 2,500 | 2 hrs | Styling |
| Deep Conditioning Treatment | 1,200 | 1 hr | Hair Care |
| Bridal Hair & Makeup Package | 12,000 | 3 hrs | Bridal |
| Wash + Blow Dry | 800 | 1 hr | Styling |
| Manicure + Gel Polish | 1,000 | 1 hr | Nails |

### Features to Test (Tier-1/Tier-2 Automation FOCUS)

- [ ] **Path Choice — Magic Fill** — Pick "Auto-fill from social" → connect Instagram → verify bio, profile pic, website pre-filled
- [ ] **Industry Pack — Salon defaults** — Verify warm/approachable/playful tones applied, WhatsApp CTA defaulted, 5 posts/week cadence set
- [ ] **Smart Kenya Signup Defaults** — Verify timezone=Africa/Nairobi, country=KE, M-Pesa phone auto-set from signup
- [ ] **Express onboarding** — Path choice (intent + link) → phone (OAuth) → Step 1 basics → Step 2 confirm → agency meeting. Platform connect is **deferred** (not a wizard blocker).
- [ ] **Step 2 Review Page** — Verify all sections (Voice, Content, Visuals, Goals, Autonomy, CTA) pre-filled
- [ ] **WhatsApp Completion Ping** — Verify the WhatsApp template message lands on signup phone (if template configured)
- [ ] **Admin Funnel — Path Choice Panel** — Salon should show under "Magic Fill" in admin dashboard
- [ ] **Admin Funnel — Industry Mix** — Salon should appear in top 10 industries
- [ ] **Admin Funnel — Country Mix** — KE should dominate
- [ ] **Growth plan limits** — 3 platforms, 60 posts/month, 30 seeds/month
- [ ] **WhatsApp Booking** — Inbox conversations for appointment requests
- [ ] **WhatsApp Broadcasts** — Weekend availability broadcasts to client list
- [ ] **AI Image Generation** — Hair transformation photos, service price cards
- [ ] **Memes** — Salon humor (braid pain memes, post-salon glow content)
- [ ] **Email Marketing** — Monthly "What's New" newsletter (max 2,500 subscribers on Growth)

### Test Seeds to Create

1. "Knotless braids in 4 hours flat — book your weekend slot, slots filling fast 🔥"
2. "Before & after: Wanjiku came in with damaged hair, left glowing. Our deep treatment + silk press combo, KES 3,700"
3. "Bridal season is here — book your bridal trial 2 weeks before the big day. Package includes hair, makeup & touch-up kit"
4. "Salon truth: Your braids should last 8 weeks, not 3. Here's what we do differently (and why your scalp will thank you)"
5. "Twende! Saturday flash deal: Cornrows + beads KES 1,200 (normally 1,500). Walk-ins from 8am, WhatsApp +254 712 345 012 to book"

### Unique Testing Angles

- **Flagship Persona:** This is the salon owner the marketing materials describe. If onboarding works smoothly for Kawaida, the Kova promise holds.
- **WhatsApp-First Service Business:** Bookings, broadcasts, conversations — all WhatsApp. Validates that our WhatsApp-first reorder pays off.
- **Magic Fill End-to-End:** The ONE business where the test plan explicitly walks through Magic Fill. If anything regresses, this catches it.
- **Industry Pack Validation:** The salon_beauty pack is the most opinionated (5 posts/week, WhatsApp CTA, warm tones). Easy to spot regressions.
- **Code-Switching Content:** Tests AI voice on mixed English/Swahili — the way real Eastlands SMEs actually communicate.

---

## Business 13: Bridge Academy

**Category:** EdTech / Skills Training — Ideation Stage
**Plan:** Growth (KES 1,499/mo)
**Website:** (none yet — development started, no public site)

Bridge Academy is a pre-launch venture focused on practical, mission-based skills
training for Kenyans 18–30 who feel let down by traditional education. The product
is in active development but not ready for demo. The marketing voice, however,
is already very clear — and that's what this test account exercises.

**Why this business is unusual:** the voice is the test target, not the wizard
flow. Bridge has no live social presence (nothing for Magic Fill to read) and
no shippable website (nothing for URL inference to scrape). It walks through
the wizard manually, leans entirely on `brand_voice_examples` to lock in style,
and then validates that the AI agents can write in that style across content
and campaigns.

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Bridge Academy |
| Industry | Education (`education`) |
| Stage | Ideation — development started, demo not ready |
| Target Audience | Kenyans 18–30 disillusioned by traditional education; looking for practical skills that pay; many in towns with patchy internet and limited bandwidth |
| Brand Voice | Direct, story-first, brutally honest with care. Mixes English with Swahili and Sheng naturally. Anti-credentialism, pro-action. Skills over grades. Every post grounded in a concrete Kenyan scene. Sharp aphorisms close each idea. |
| Tone | Confident, educational, bold, approachable |
| Content Pillars | Peer learning in action, Mission-based outcomes (receipts, not theory), Accessibility & low-bandwidth wins, Digital learner profiles → global opportunities, Skills > credentials hot takes |

### The Four Product Pillars (also content pillars)

1. **Peer learning network** — show how knowledge spreads laterally between learners; the kid in Kibera who taught 12 others Canva in a weekend
2. **Mission-based learning** — practical outcomes over theory; "30 days, one client, KES 5,000 paid. Here's the project he shipped."
3. **Low-bandwidth system** — works on patchy 2G/3G; designed for towns where uni-style platforms time out
4. **Digital profile for learners** — portfolio, not transcript; opens doors to global opportunities

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| LinkedIn | Bridge Academy | Long-form posts in the Elvis-W. style — thought leadership, founder POV, learner stories |
| Twitter | @bridgeacademyke | Punchy threads, hot takes on Kenyan education, daily one-liners |
| Instagram | @bridge.academy | Photo-led posts of real learners; carousel posts breaking down the long-form points |

*Growth plan allows 3 social accounts — perfect fit*

### Brand Voice Examples (CRITICAL — this is what trains the AI)

These are seeded onto the profile via `seed_test_businesses` so the agents have
real exemplars to pattern-match. The AI should produce content that reads in
this voice — short paragraphs, code-switching, concrete Kenyan places, sharp
closers, signing off with the founder's first name where it fits.

> *"You sat in a lecture hall for 4 years memorizing definitions. Bridge will teach you to land your first paying client in 30 days. The market does not grade on papers. It grades on what you ship."*

> *"Peer learning is not a buzzword on our deck. It is how Mary in Eastleigh learned video editing — from another student in Embu she had never met. The teacher and the learner sharing one Zoom screen and a Canva project. That is the model."*

> *"Your transcript says you got an A in microeconomics. Cool. Now show me what you have built. That is the only question the market is asking in 2026."*

> *"Low bandwidth is not a problem to apologize for. It is a constraint to design around. Bridge runs on 2G. That is on purpose. Because the next great Kenyan freelancer is not in Kilimani. She is in Garissa. She is in Kakuma. She is in Marsabit. And Bridge meets her where she is."*

### Features to Test (Voice & Pre-Launch FOCUS)

- [ ] **Brand Voice Examples** — Verify the 4 examples are saved on the profile and surface in the Step 2 review page
- [ ] **AI Voice Match** — Generate 5 posts from seeds; check the output reads like Elvis-W. (short paragraphs, code-switch, concrete scenes, no corporate-speak)
- [ ] **Manual Onboarding Path** — Confirm the manual route works when both Magic Fill and URL inference are unavailable
- [ ] **Industry Pack — education** — Verify defaults applied; check that the bolder bespoke `brand_voice` overrides the pack's softer default tones
- [ ] **Code-Switch Content** — Verify AI keeps English/Swahili/Sheng mix in generated posts (not pure English, not pure Swahili)
- [ ] **Pre-Launch Mode** — Test the platform with no products, no website, no live socials — does it still feel useful?
- [ ] **Content Pillars** — Verify the 5 pillars seed the AI's topic axes correctly
- [ ] **Daily Brief** — Should be sparse pre-launch (nothing to measure yet); does the dashboard handle this gracefully?
- [ ] **Industry Pack Collision** — Two `education` businesses (Elimu Hub and Bridge Academy) with deliberately different voices. Confirm Step 2 Review lets users diverge.

### Test Seeds to Create

1. "You do not need a degree to change your life. You need 30 days and discipline. Bridge teaches what universities skip."
2. "Mary learned video editing from a stranger in Embu. They never met. That is peer learning. That is Bridge."
3. "Your CV is dead. Your portfolio is alive. Bridge gives you the second one."
4. "The kid in Garissa with one bar of internet just landed a client in Lisbon. Low bandwidth is not a limitation here. It is the design."
5. "Stop waiting for HELB. Stop waiting for January. Stop waiting for a lecturer to give you permission. Open YouTube. Pick a skill. Start today. Bridge is for the ones who already did."

### Unique Testing Angles

- **Voice Style Transfer:** The strongest test of whether Kova's AI can match a distinctive non-corporate voice given strong `brand_voice_examples`.
- **Pre-Launch Use Case:** Bridge has no website, no products, no socials connected. Stress-tests the platform for founders who use Kova as part of going to market — not after launch.
- **Code-Switching Content:** Specifically tests AI handling of English + Swahili + Sheng mix, the way the founder actually writes.
- **Manual Path Validation:** The cleanest test of the manual onboarding path — Bridge can't use Magic Fill (no socials) or URL inference (no site). If the manual flow doesn't feel good here, it doesn't feel good for any new founder.
- **Industry Pack Collision:** Pairs with Elimu Hub. Both `education`, deliberately different voices, both Growth plan. Validates that strong voice examples override pack defaults.

---

## Business 14: Django Sasa

**Category:** Developer Education — 30-Day Django Track
**Plan:** Growth (KES 1,499/mo)
**Website:** (none yet — link-in-bio acts as homepage)
**Tagline:** *Sasa = "now" in Swahili. Start today, not someday.*

Django Sasa is a curriculum-driven developer-education account: every social
post is **Day N of a 30-day Django track**, in dependency order, restarted
every 30 days as a fresh cohort. This test business validates **sequential /
curriculum-style content** — the hardest content pattern to keep on the
rails as AI generates posts over weeks.

The unique testing angle: most accounts publish topic-random content. Django
Sasa publishes topic-ORDERED content. If Kova's pillar discipline,
campaigns, and email sequences work together correctly here, they work for
any course / cohort / curriculum-based educator.

### Brand Profile

| Field | Value |
|-------|-------|
| Company Name | Django Sasa |
| Industry | Education (`education`) |
| Stage | Pre-launch (no website, link-in-bio is the homepage) |
| Target Audience | Aspiring African developers 18–32 who want a real, sequenced path into Django backend work — not random YouTube tutorials. CS students who graduated but feel they cannot ship. Self-taught coders stuck at "I built a to-do app, now what?" |
| Brand Voice | Senior dev who teaches like Elvis W. Direct, practical, shows code, no theory dumps. Every post grounded in a numbered day of a real curriculum. Every post ends with **"Tomorrow we cover X."** That single closing line is what keeps followers on the track. |
| Tone | Confident, educational, direct, practical |
| Content Pillars | **Six modules of the 30-day track** (one pillar per 5-day module — this discipline is what stops the AI from inventing random Django tips) |

### The 30-Day Curriculum (mapped to the 6 content pillars)

| Days | Pillar | Topics covered |
|------|--------|---------------|
| 1–5 | **Foundations** | install Django, project vs app, settings.py, runserver, virtualenv |
| 6–10 | **Models & ORM** | define models, migrations, admin registration, querysets, relationships |
| 11–15 | **Views & URLs** | function views, class-based views, URL routing, namespacing, redirects |
| 16–20 | **Templates** | DTL, template inheritance, static files, filters, includes |
| 21–25 | **Forms & Auth** | Django forms, model forms, validation, login/signup, permissions |
| 26–30 | **Ship It** | testing, env vars, Postgres, deploy to Railway, post-deploy debugging |

### Platforms to Connect

| Platform | Handle | Content Type |
|----------|--------|-------------|
| LinkedIn | Django Sasa | Numbered carousel lessons (5-10 slides), code screenshots, professional tone |
| Facebook | Django Sasa | Same numbered lessons as LinkedIn but as image + caption; community Q&A in comments |
| Twitter | @djangosasa | Threads for the long lessons; one-liners for hot takes; daily "Day N just dropped" |

*Growth plan allows 3 social accounts — perfect fit*

### The Three Mechanisms That Keep Followers On Track

1. **Numbered Curriculum (the spine).** Every post titled "Django Day N — [topic]". Followers always know what day they're on.
2. **Restart Cycle (the discovery fix).** Every 30 days, Day 1 comes around again. A follower who joins on Day 17 waits 13 days for the next Day 1. Framed as "Cohort N starting Monday" — urgency + community.
3. **Email Sequence (the on-rails delivery).** When a user opts in via link-in-bio, they enter a **30-email drip** delivering Days 1–30 *in order from their signup date*, not from where the public feed currently is. **Social is the recruitment funnel; email is the curriculum.**

### Daily Cadence (7 posts/week)

| Day | Post type | Format |
|-----|-----------|--------|
| Mon–Fri | Numbered lesson (Day N) | Carousel on LinkedIn, image+caption on FB, thread on Twitter |
| Sat | "This week we covered Days X–Y" recap | Single image with checklist |
| Sun | "Stuck on Day N? Common bug + fix" or learner Q&A | Text + code screenshot |

### Brand Voice Examples (CRITICAL — the AI pattern lock)

> *"Django Day 7. URLs and routing.*
>
> *Stop hardcoding `/products/1/` into your templates. That's how your app breaks the day a designer changes a path.*
>
> *Name your URLs. `path('products/<int:pk>/', detail, name='product_detail')`.*
>
> *Now in your templates: `{% url 'product_detail' pk=product.id %}`. Done.*
>
> *Tomorrow we cover URL namespacing — what happens when two apps both have a 'detail' view."*

> *"Django Day 14. Template inheritance.*
>
> *If you are copying the same nav into every page you are doing it wrong. There is a reason Django teaches DRY.*
>
> *Make a `base.html`. Put your nav there. Then in `product_list.html`:*
>
> *`{% extends 'base.html' %}{% block content %}…{% endblock %}`.*
>
> *That is it.*
>
> *Tomorrow: static files. The reason your CSS keeps not loading."*

> *"Django Day 22. Model forms.*
>
> *You are not supposed to write `forms.CharField()` for every field on your model. That is what `ModelForm` is for.*
>
> *Subclass it. Point at your model. Pick the fields. Django writes the form for you.*
>
> *`class ProductForm(forms.ModelForm): class Meta: model = Product; fields = ['name', 'price', 'description']`.*
>
> *Tomorrow: validation. How to refuse a form before it ruins your data."*

> *"Django Day 29. Deploy to Railway.*
>
> *Stop calling your app done because it works on localhost. localhost is not a market. Railway is.*
>
> *Push to GitHub. Connect repo to Railway. Add Postgres. Set `DEBUG=False`. Set `ALLOWED_HOSTS`. Hit deploy.*
>
> *If it crashes, read the logs. Do not panic. Logs always tell you what broke.*
>
> *Tomorrow we wrap the track with post-deploy debugging — the 5 errors every Django dev sees their first week in production."*

### Features to Test (Curriculum-Style Content FOCUS)

- [ ] **Six-Pillar Discipline** — Generate 30 seeds in one batch. Verify each gets assigned to ONE of the 6 module pillars in cycle order, not random
- [ ] **Brand Voice Examples** — Verify AI-generated posts include the closing "Tomorrow we cover X" line
- [ ] **Email Sequences** — Build the 30-email Django drip; verify Day-1 user gets Day 1 on signup day 1, Day 2 on signup day 2, etc., regardless of which Day the public feed is on
- [ ] **Campaigns** — Create "Django Sasa — Cohort 1" campaign holding 30 posts; verify analytics attribute signups to the cohort
- [ ] **Posting Cadence (7/wk)** — Verify the Mon–Fri lesson / Sat recap / Sun Q&A rhythm is producible by the AI when given the structure
- [ ] **A/B Testing** — Test two different Day-1 hooks; lock the winner into the canonical Day 1 for future cohorts
- [ ] **Daily Brief** — Verify the brief tells the founder which Day drops today + which cohort it belongs to
- [ ] **Lead Capture** — "Get the free 30-Day Django Track in your inbox" form → enrols subscriber in email sequence
- [ ] **Kova Pages** — Link-in-bio page lists all 30 Days + email signup
- [ ] **Industry Pack Collision (3-way)** — Three education businesses now (Elimu Hub, Bridge Academy, Django Sasa). All Growth plan. All `education` industry. Three very different voices. Confirms voice examples decisively override pack defaults.

### Test Seeds to Create (Days 1, 7, 14, 21, 29 — one per pillar)

1. **Day 1 — Foundations:** "Install Django. Make your first project. Run the server. See the green rocket. That is the entire goal of today. Tomorrow we cover the difference between a project and an app."
2. **Day 7 — Views & URLs:** "Stop hardcoding URLs. Name them. `{% url 'product_detail' pk=product.id %}`. Tomorrow we cover URL namespacing."
3. **Day 14 — Templates:** "Stop copy-pasting your nav into every page. Use `{% extends 'base.html' %}`. Tomorrow: static files."
4. **Day 22 — Forms & Auth:** "Stop writing `forms.CharField()` for every model field. ModelForm exists. Use it. Tomorrow: validation."
5. **Day 29 — Ship It:** "localhost is not a market. Deploy to Railway. Tomorrow we wrap the track with post-deploy debugging."

### Unique Testing Angles

- **Curriculum/Sequential Content:** The hardest content pattern. If pillar discipline + email sequences + campaigns work here, they work for any educator running a course on Kova.
- **Email-Backboned Content:** Most accounts use email as a side channel. Django Sasa makes email the SPINE and social the funnel. Tests whether Kova actually treats email as a first-class output.
- **Cohort Campaign Cycle:** Tests campaigns as 30-day repeating containers, not one-off promos.
- **Voice Discipline:** Every post must close with "Tomorrow we cover X." Tests whether AI respects a brand-mandated closer.
- **3-Way Industry Pack Collision:** Elimu Hub + Bridge Academy + Django Sasa = three Growth-plan education businesses with deliberately different voices. Strongest validation that voice examples override pack defaults.

---

## Onboarding Sequence

### Phase 1: Setup (Day 1)

1. **Bulk-seed accounts (recommended):** run `python manage.py seed_test_businesses`.
   This creates all 14 users with the right plan, profile (industry, voice,
   audience, pillars, tones, goals, CTA, brand colors), and a starter set of
   products. Pass `--complete-onboarding` to skip the wizard entirely for
   businesses you don't need to manually walk through.
2. **Manual onboarding (for QA coverage of the new wizard):** sign up each
   business through the public UI to exercise express onboarding end-to-end.
   The new flow is:
   * **Path-choice screen** — pick Magic Fill (auto-fill from a social account),
     URL inference (paste a website), or manual setup.
   * **Step 1 — Basics:** company name, industry, audience, key offerings,
     timezone, website. If Magic Fill or URL inference fired, fields arrive
     pre-populated.
   * **Step 2 — Review your brand:** merged voice + visuals + goals + autonomy
     + CTA. Industry pack values are already filled in; the user skims and
     edits anything off.
   * **Step 2 — Confirm brand** (preview card, not a long form).
   * **Agency meeting** — completion page polls intelligence chain.
   * **Platform connect** — optional anytime from Platforms (not a wizard step).
   Phase 1 of the test plan only takes one or two businesses through the
   manual route; the rest go through `seed_test_businesses`.
3. Connect platforms per the tables above (OAuth — still required even when
   the rest of the profile was bulk-seeded).

### Phase 2: Content & Products (Day 2-3)

4. Add products for Mara & Moto (10), Nyama Mama (8), Coach Amara (5)
5. Create Kova Pages for businesses that need them (7 businesses)
6. Add lead capture forms to relevant pages
7. Set up email subscriber lists and import test subscribers

### Phase 3: AI & Content (Day 4-5)

8. Create 5 test seeds per business (50 total)
9. Let AI generate posts from seeds
10. Review, edit, approve, and schedule posts
11. Test A/B testing for Growth+ plans
12. Enable and configure all available AI agents per business

### Phase 4: Advanced Features (Day 6-7)

13. Set up WhatsApp for Pro/Agency businesses (Mara & Moto, Nyama Mama, Makao, Neon Wave, Kakuma Wholesale)
14. Configure meme preferences for Pro+ businesses
15. Add competitors for tracking (CloudStack, PesaPal)
16. Set up media queues for visual-heavy businesses
17. Create campaigns for businesses with active promotions

### Phase 5: Full System Test (Day 8-10)

18. Run all Celery tasks and verify outputs
19. Test webhook integrations (Stripe, M-Pesa, Resend, Shopify)
20. Verify plan limit enforcement at every tier
21. Test team role permissions (Neon Wave)
22. Install Kova Pixel and test revenue attribution (Mara & Moto, CloudStack)
23. Run partner program test (Green Roots applies, gets approved, shares referral code)
24. Test admin dashboard with data from all 11 businesses

---

## Onboarding Automation (Tier 1 / Tier 2)

The features below were added during the onboarding rework and are not exercised
by the per-business feature lists above. Run through this section explicitly to
confirm the new automation paths work end-to-end and surface correctly in the
admin Onboarding Funnel.

### Path Choice

Each new user lands on a 3-option screen before Step 1:

| Path | Test with business | Expected admin marker |
|------|---------------------|------------------------|
| Magic Fill (auto-fill from social) | **Kawaida Hair & Beauty** (#12), **Mara & Moto** (#1), **Nyama Mama** (#4) | `path_choice_magic` |
| URL inference (paste a website) | **CloudStack Africa** (#5), **PixelCraft Studios** (#2), **Elimu Hub** (#3) | `path_choice_url` |
| Manual setup | **Kakuma Wholesale** (#11), **Coach Amara** (#7) | `path_choice_manual` |

Verify in admin `/admin/users/onboarding-funnel/` → **Path choice** panel shows
the counts and percentages.

### Magic Fill (profile_audit → UserProfile)

- [ ] Connect Instagram for Kawaida → audit pulls bio, profile pic, website, phone
- [ ] Connect Facebook Page for Nyama Mama → audit pulls category, hours, address
- [ ] Connect LinkedIn for PixelCraft → audit pulls org description, website
- [ ] Verify admin marker: `magic_fill_applied:<platform>` recorded per audit success
- [ ] Verify provider breakdown panel shows IG / FB / LinkedIn counts

### URL Inference (paste a URL → LLM fills fields)

- [ ] CloudStack: paste `cloudstackafrica.com` → industry inferred as `saas`, voice + pillars filled
- [ ] PixelCraft: paste `pixelcraftstudios.com` → industry inferred as `agency`
- [ ] PesaPal: paste `pesapalfinance.co.ke` → industry inferred as `finance`
- [ ] Verify malformed URLs return a friendly error (404, no scheme, etc.)
- [ ] Verify admin marker: `url_inference_applied` recorded

### Industry Pack Defaults

Each business should see its industry-specific defaults applied after Step 1.
Spot-check at least these:

| Business | Industry | Expected pack defaults |
|----------|---------|------------------------|
| Kawaida | `salon_beauty` | WhatsApp CTA, 5 posts/wk, warm/playful tones, "Transformations & before/after" pillar |
| Nyama Mama | `food_restaurant` | Phone CTA, 6 posts/wk, warm/playful tones, "Menu highlights" pillar |
| Coach Amara | `health` | WhatsApp CTA, 3 posts/wk, empathetic/educational tones |
| Mara & Moto | `fashion_beauty` | Link CTA, 5 posts/wk, bold/playful tones, vibrant visuals |
| Makao Homes | `real_estate` | WhatsApp CTA, 4 posts/wk, confident/professional tones |
| Kakuma | `wholesale_retail` | WhatsApp CTA, 4 posts/wk, approachable tones |

- [ ] Verify admin marker: `industry_pack_applied:<industry>` recorded
- [ ] Verify "Industry pack — applied" stat shows count + % of completed users
- [ ] Verify "Industry mix (top 10)" panel shows the 14-business distribution

### Smart Kenya Defaults (signup)

All 14 businesses use Kenyan phone numbers, so all should auto-set:

- [ ] `user.timezone == "Africa/Nairobi"`
- [ ] `profile.country == "KE"`
- [ ] `profile.mpesa_phone` matches the signup phone
- [ ] Verify "Country mix" panel shows **KE** dominating (should be 14/14)

### Wizard Structure

- [ ] Confirm wizard is **3 steps**, not 4 (progress bar shows "Step X of 3")
- [ ] Step 2 is a single "Confirm your brand" preview page (not a long legacy form)
- [ ] African timezones surfaced at top of the timezone dropdown in Step 1
- [ ] Mid-flow OAuth callback returns user to `?step=2` (magic fill handoff)
- [ ] Signup requires phone number; OAuth users land on `/accounts/onboarding/phone/` first

### WhatsApp Completion Ping

- [ ] Verify `KOVA_ONBOARDING_TEMPLATE_NAME` env var is set in test env
- [ ] Complete onboarding for Kawaida (Kenyan phone) → verify WhatsApp template
      message arrives on the signup phone
- [ ] Complete onboarding for a user with no phone → verify no error, soft no-op
- [ ] Check logs for "Onboarding ping sent to ..." or skip message

### Admin Onboarding Funnel — End-to-End

After running the full test cohort, the admin funnel at
`/admin/users/onboarding-funnel/` should show:

- [ ] **Funnel** — drop-off: Signup → Phone → Intent → Step 1 → Step 2 confirm → Agency chain
- [ ] **Top summary line** — median time-to-complete in minutes
- [ ] **Path choice** — Magic / URL / Manual / Unknown breakdown
- [ ] **Automation hits** — Magic Fill providers, URL inference count, industry pack hits
- [ ] **Industry mix** — top 10 industries
- [ ] **Country mix** — KE dominant
- [ ] **Stuck users** — empty (or accurate if you intentionally break a celery worker to test)
- [ ] **Wizard abandoners** — accurate if you sign up + abandon a test user >24h

---

## Commerce sandbox (M-Pesa, Shopify, Kova Pixel)

Live M-Pesa and Shopify need production credentials. For local / staging test businesses use:

| Business | Commerce focus | Dev setup |
|----------|----------------|-----------|
| **Mara & Moto** | Shopify + Pixel + M-Pesa commerce | `MPESA_ENVIRONMENT=sandbox`, test phone `254708374149`; Shopify dev store + OAuth from **Analytics → Revenue**; Pixel snippet from **Analytics → Pixel** |
| **Nyama Mama** | WhatsApp orders + M-Pesa | Sandbox STK for subscription tests; WA Cloud API env vars for order flows |
| **CloudStack** | B2B revenue attribution | Pixel on marketing site; optional Shopify for demo SKUs |

**Kova Pixel (all tiers):** After login → Analytics → Pixel — copy the snippet; no extra env vars. Events appear in Revenue dashboard once the snippet fires on a page you control.

**Shopify OAuth callback:** `{SITE_URL}/analytics/revenue/shopify/oauth/callback/` — must match your dev store app settings.

**QR → Lead (walk-in):** Preferred path is the **cashier UI** (`/walkin/<slug>/`) where staff tap attribution source and optionally enter `customer_phone` — this creates a REACH lead automatically. QR scan landing pages are offer/display only; phone capture on scan is not required for testing.

---

| Feature | Mara&Moto | PixelCraft | Elimu | Nyama | CloudStack | Makao | Amara | GreenRoots | NeonWave | PesaPal | KakumaWS | Kawaida | Bridge | Django |
|---------|:---------:|:----------:|:-----:|:-----:|:----------:|:-----:|:-----:|:----------:|:--------:|:-------:|:--------:|:-------:|:------:|:------:|
| **Plan** | Agency | Pro | Growth | Pro | Agency | Pro | Starter | Growth | Agency | Growth | Pro | Growth | Growth | Growth |
| Content Creation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Products | ✅ | | | ✅ | | | ✅ | | | | ✅ | ✅ | | |
| Shopify + Pixel | ✅ | | | | ✅ | | | | | | | | | |
| Revenue Attribution | ✅ | | | | ✅ | | | | | | | | | |
| WhatsApp Full | ✅ | | | ✅ | | ✅ | | | ✅ | | ✅ | ✅ | | |
| Memes | ✅ | | | ✅ | | ✅ | | | ✅ | | ✅ | ✅ | | |
| Teams | | ✅ | | | ✅ | | | | ✅ | | | | | |
| Multi-Brand | | | | | | | | | ✅ | | | | | |
| Lead Capture | | ✅ | ✅ | | | ✅ | ✅ | ✅ | | ✅ | | ✅ | ✅ | ✅ |
| Email Marketing | ✅ | ✅ | ✅ | | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | | ✅ | ✅ | ✅ |
| Email Sequences | | | ✅ | ✅ | | | | ✅ | | ✅ | | | ✅ | ✅ |
| Campaigns | ✅ | ✅ | | | ✅ | ✅ | | ✅ | ✅ | ✅ | ✅ | | | ✅ |
| A/B Testing | ✅ | ✅ | ✅ | | ✅ | | | ✅ | ✅ | ✅ | | | ✅ | ✅ |
| Competitor Intel | | ✅ | | | ✅ | | | | | ✅ | | | | |
| Media Queue | ✅ | | | ✅ | | | | | ✅ | | ✅ | ✅ | | |
| AI Images | ✅ | | | ✅ | | | | | ✅ | | ✅ | ✅ | | |
| All 6 Agents | ✅ | | | | ✅ | | | | ✅ | | | | | |
| REST API | | | | | ✅ | | | | ✅ | | | | | |
| Kova Pages | | ✅ | ✅ | | ✅ | ✅ | ✅ | ✅ | | ✅ | | | ✅ | ✅ |
| Partner Program | | | | | | | | ✅ | | | | | | |
| Plan Limits | | | ✅ | | | | ✅ | ✅ | | ✅ | | ✅ | ✅ | |
| Starter Ceiling | | | | | | | ✅ | | | | | | | |
| Multi-Language | | | | | | | | | | | ✅ | ✅ | ✅ | |
| Wholesale/Bulk | | | | | | | | | | | ✅ | | | |
| **Path Choice — Magic** | ✅ | | | ✅ | | ✅ | | | | | | ✅ | | |
| **Path Choice — URL** | | ✅ | ✅ | | ✅ | | | ✅ | | ✅ | | | | |
| **Path Choice — Manual** | | | | | | | ✅ | | | | ✅ | | ✅ | ✅ |
| **Industry Pack** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Smart KE Defaults** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Salon Persona** | | | | | | | | | | | | ✅ | | |
| **WhatsApp Completion Ping** | | | | ✅ | | ✅ | | | | | ✅ | ✅ | | |
| **Voice Style Transfer** | | | | | | | | | | | | | ✅ | ✅ |
| **Pre-Launch / Ideation** | | | | | | | | | | | | | ✅ | ✅ |
| **Industry Pack Collision** | | | ✅ | | | | | | ✅ | | | | ✅ | ✅ |
| **Sequential / Curriculum Content** | | | | | | | | | | | | | | ✅ |
| **Email Sequence Backbone** | | | ✅ | | | | | ✅ | | ✅ | | | | ✅ |
| **Cohort Campaign Cycle** | | | | | | | | | | | | | | ✅ |

**Every feature is covered by at least 2 businesses. Every plan tier is tested by at least 2 businesses. Every Tier-1/Tier-2 onboarding automation is exercised by at least 1 business. Sequential / curriculum content, email-backboned content, and cohort campaign cycles are covered by Django Sasa.**

---

*Kova AI — 14 businesses, 4 plan tiers, every feature tested.*
