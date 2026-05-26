# Segment Roadmap

This roadmap expands Kova from a strong social-commerce engine into a segment-aware operator for the full African SME spectrum:

- physical product sellers
- service businesses
- digital product businesses
- professionals and creators growing through social platforms

The goal is not to dilute commerce. The goal is to make the same intelligence choose the right path to value for each user type.

## Product Principle

Every user should feel that Kova understands:

1. what they actually offer
2. how people convert in their business
3. what a valuable next action looks like

For one user that is:

- buy
- order
- restock

For another it is:

- book
- inquire
- apply

For another it is:

- download
- enroll
- subscribe

And for a professional it may be:

- reply
- connect
- join the list
- book a call

## Strategic Modes

Kova should work through four operating modes:

### 1. Merchant mode

Best for:

- physical products
- retail
- boutiques
- market sellers
- wholesalers

Core outcome:

- convert attention into product sales

### 2. Service mode

Best for:

- agencies
- consultants
- salons
- wellness businesses
- clinics
- real estate
- professional services

Core outcome:

- convert attention into bookings, consultations, and quotes

### 3. Digital mode

Best for:

- templates
- guides
- subscriptions
- SaaS-lite products
- courses
- digital downloads

Core outcome:

- convert attention into access, enrollment, and digital delivery

### 4. Expert mode

Best for:

- LinkedIn-first professionals
- X-first commentators and creators
- coaches
- analysts
- educators
- experts building authority online

Core outcome:

- convert attention into authority, audience growth, leads, and inbound opportunities

## Phase 1: Segment-Aware Intelligence

Status: started

Goal:

- stop wrong-fit defaults
- teach the planning and creation layers what kind of business they are serving

Delivered in this phase:

- shared segment helper for merchant, service, digital, and expert modes
- creator playbook no longer forced into fashion/beauty defaults
- Create Agent prompt now adapts CTA framing for product vs service vs digital offers
- Campaign planning now includes audience, goals, offerings, and business-mode context
- Autopilot strategist planning now includes business-mode context and mode-aware fallback topics

Next additions inside Phase 1:

- propagate segment context into Strategist Agent and Daily Brief prompts
- fix product-first copy on public commerce surfaces where service/digital wording should change
- add visible proof-of-value language by segment

## Phase 2: Fulfillment-Aware Selling

Goal:

- make Kova understand not just promotion, but the correct fulfillment path

Work:

### Service fulfillment

- connect service offers to booking outcomes
- unify service catalog items with booking links
- let replies and CTAs point to booking, quote, consult, or schedule

### Digital fulfillment

- add first-class digital delivery
- support post-payment access or delivery flows
- let CTAs and post-purchase flows reflect instant access or enrollment

### CTA intelligence

- choose CTA by offer type and business mode
- examples:
  - `Shop now`
  - `Book a session`
  - `Download now`
  - `Apply here`
  - `Join the list`

## Phase 3: Segment-Specific Surfaces

Goal:

- make each segment feel explicitly served in the UX

Work:

### Merchant surfaces

- deepen stock, restock, bundle, and launch intelligence

### Service surfaces

- add booking-led offer flows, service proof, and no-show recovery

### Digital surfaces

- add digital launch and delivery workflows

### Expert surfaces

- introduce a true expert-growth experience for LinkedIn/X-led users
- focus on:
  - authority building
  - thought leadership
  - profile growth
  - inbound opportunities
  - conversation-to-lead conversion

## Phase 4: Proof of Value by Segment

Goal:

- every user should see why Kova is worth paying for in the language of their own business

Examples:

- merchant: products listed, posts launched, sales influenced, stock saved
- service business: bookings won, no-shows prevented, consultations generated
- digital seller: signups, downloads, enrollments, repeat campaigns
- expert: leads captured, profile growth, authority wins, replies converted to opportunity

## Guardrails

To avoid messing up what already works:

1. do not delete proven commerce flows while segment support is still expanding
2. prefer shared intelligence layers before creating separate app silos
3. keep stock logic physical-only
4. keep routes stable unless a replacement is clearly better
5. add regression tests whenever a prompt or CTA rule becomes segment-aware

## Definition of Success

Kova wins when a user can say:

- "It understands what I sell."
- "It knows how my business converts."
- "It tells me the next move that matters."
- "I can see the value every week."
