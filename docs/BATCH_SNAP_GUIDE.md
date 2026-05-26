# Batch Snap Guide

> Version: 1.0
> Last Updated: May 2026
> Scope: Batch Snap, Market Day Mode, stall intelligence, and launch bundle flow

---

## 1. What Batch Snap Is

`Batch Snap` is Kova's multi-item snap-to-sell workflow.

Instead of launching one product at a time, the seller can photograph an entire table, rack, pop-up stand, or mixed stall and let Kova process the whole batch in one flow.

Internally, this upgraded experience is described as **Market Day Mode**.

That means Batch Snap is no longer just "bulk upload with AI." It is now a more opinionated selling workflow designed for real market-day behavior:

- walk the table
- take several fast photos
- say prices once in a voice brief
- let Kova identify each item
- auto-name blank rows
- resolve pricing
- generate listing-ready copy
- create platform posts
- open the shop with a stall-level launch bundle

Batch Snap is especially valuable for:

- market sellers
- boutique owners
- new-arrival drops
- clearance tables
- mixed inventory launches
- service portfolios captured in several shots
- digital products shown through multiple screenshots or previews

---

## 2. Product Intent

The upgraded Batch Snap flow was designed around a few clear goals.

### 2.1 Reduce seller effort

The seller should not need to type the full product information for every row.

The system should extract as much as possible from:

- images
- voice price notes
- stall-level context
- repeated defaults

### 2.2 Think in stall terms, not only item terms

Normal product upload logic thinks one listing at a time.

Batch Snap now thinks in terms of a **whole selling surface**:

- one stall
- many items
- one market-day moment
- one collection-level launch story

### 2.3 Support local seller language

The stall intelligence is explicitly tuned for East African selling language, including patterns like:

- `800 bob`
- `bei 1200`
- `sh 500`
- mixed English, Swahili, and Sheng

### 2.4 Turn a batch into a launch, not just a catalog import

The end state is not simply "several products were created."

The end state is:

- the items are listed
- the shop is updated
- launch content exists
- the seller can share the shop immediately

---

## 3. Routes and User Entry Points

The Batch Snap flow is exposed under the product area through these routes:

- `/snap/batch/`
- `/snap/batch/launch/`
- `/snap/batch/transcribe/`
- `/snap/batch/status/`

### 3.1 Main entry page

The main web surface is the Batch Snap page.

This page is the UI where the seller:

- names the stall
- sets optional default pricing
- records a voice brief
- chooses offering type
- walks the table and captures photos
- decides whether to create the launch bundle

### 3.2 Transcription endpoint

The transcription endpoint exists to convert the seller's live-recorded voice brief into text that can feed the stall intelligence logic.

### 3.3 Launch endpoint

The launch endpoint:

- validates the submission
- creates a `BatchSnapSession`
- creates one `Product` per photo
- stores price and context hints
- fires the background processing task

### 3.4 Status endpoint

The status endpoint powers the live progress modal, letting the UI track:

- how many items are complete
- which items are still processing
- whether the stall-level launch bundle is being finalized
- whether the shop is ready

---

## 4. Core User Experience

The Batch Snap page is intentionally different from a normal form-heavy catalog page.

It is designed to match a fast-moving market workflow.

### 4.1 Hero framing

The page explains Batch Snap as `Market Day Mode`.

That framing tells the seller:

- this is for whole-stall selling
- AI will help identify each item
- a stall-level launch can be created when the batch finishes

### 4.2 Stall setup

Before taking photos, the seller can provide stall-level context such as:

- `stall_title`
- `default_price`
- `default_currency`
- voice or typed notes
- whether the stall launch bundle should be created

These values are important because they act as shared context for all items in the batch.

### 4.3 Voice price brief

The page supports a live mic-based voice brief.

This is one of the most important usability upgrades in the feature.

The seller can say something like:

> "Everything 800 bob, XL dresses 1200, Kawaida market today."

That voice note is then transcribed and used to build structured stall context.

### 4.4 Offering type support

The seller can launch a batch as:

- `product`
- `service`
- `digital`

This matters because the downstream AI prompts change depending on what kind of thing is being sold.

### 4.5 Walk & snap mode

The interface supports a "walk & snap" pattern where the camera can reopen after each capture.

This reduces friction when the seller is physically moving around a table or rack.

### 4.6 Optional per-item naming

Each row can include a typed name, but the UI intentionally makes names optional.

If the seller leaves a row blank, Kova can still identify the item from the image and replace placeholder names automatically.

### 4.7 Optional per-item pricing

Each row can also include a price, but that price can be omitted if:

- a default price was set at the stall level
- the voice brief provided a default price
- the image itself contains a visible price tag

### 4.8 Launch bundle toggle

The seller can choose whether Kova should also "open the stall" by creating the extra launch assets:

- collection post idea
- showcase reel
- seller WhatsApp notification if configured

---

## 5. Data Model: `BatchSnapSession`

The heart of the upgraded Batch Snap flow is the `BatchSnapSession` model.

This model represents one full stall launch.

### 5.1 Why the session model exists

Without a session model, Batch Snap would just be several unrelated products created at the same time.

The session model allows Kova to treat the batch as one real event:

- one stall title
- one voice transcript
- one set of stall notes
- one set of pricing rules
- one status lifecycle
- one shop URL
- one launch bundle

### 5.2 Important session fields

The session stores:

- `stall_title`
- `voice_transcript`
- `stall_notes`
- `stall_context`
- `offering_type`
- `default_price`
- `default_currency`
- `launch_bundle`
- `status`
- `product_count`
- `items_processed`
- `shop_url`
- `bundle_post_ids`
- `whatsapp_message`
- `whatsapp_sent`
- `error_message`
- `bundle_seed`

### 5.3 Session status lifecycle

The session supports a clear lifecycle:

- `processing`
- `finalizing`
- `completed`
- `failed`

This lifecycle is what makes the live progress modal and the launch-bundle sequencing possible.

### 5.4 Product linking

Each product created from the batch stores:

- `batch_snap_session`
- `batch_index`

That gives Kova a reliable way to:

- reconstruct the batch
- preserve item order
- aggregate batch status later

---

## 6. Stall Intelligence

The upgraded Batch Snap flow adds a dedicated intelligence layer in `batch_snap_intelligence.py`.

This is one of the key innovations in the feature.

### 6.1 What stall intelligence does

It turns a seller's voice or text brief into structured context that downstream AI agents can use consistently.

Instead of each item being analyzed in isolation, the whole batch gets a shared selling context.

### 6.2 `parse_stall_brief`

This function converts seller input into structured stall context.

It tries to capture things like:

- stall title
- stall tagline
- market context
- pricing rules
- category hints
- size or variant hints
- language mix
- Swahili phrases
- words to avoid
- campaign tone
- WhatsApp hook
- collection angle

### 6.3 LLM-first, heuristic fallback

The parsing logic is designed with two levels:

1. LLM-based structured parsing when model access is available
2. regex/heuristic fallback when the LLM is unavailable

This matters because the feature remains functional even when the richer AI parsing path is not available.

### 6.4 Local-language support

The parser explicitly recognizes market-style local phrasing such as:

- `bei`
- `bob`
- `sh`
- `shilingi`
- mixed Swahili/English selling language

This makes the feature more practical for real sellers rather than only for formal typed input.

### 6.5 Tone and campaign direction

The stall context also influences tone through values like:

- `energetic_market_day`
- `premium_boutique`
- `clearance_urgency`
- `wholesale`

This means downstream content generation can feel more specific to the selling moment.

---

## 7. Item-Level AI Processing

Once the session is created, the background task processes each linked product one by one.

### 7.1 Batch-aware vision prompts

Each item is analyzed with a **batch-aware** vision prompt, not a generic single-product prompt.

That prompt includes:

- offering type
- current item index
- total batch size
- shared stall context
- already-identified sibling item names
- whether the seller's current name is just a placeholder

This is important because it reduces duplicate naming and makes each item feel like part of a coherent stall.

### 7.2 Placeholder-name replacement

If a seller leaves a row unnamed or uses a placeholder like:

- `Listing 1`
- `Product 3`
- `Untitled`

Kova can detect that the name is only a placeholder and replace it with an AI-derived product name from the image.

### 7.3 Description and SEO enrichment

If an item does not yet have a good description, the AI analysis can fill it in.

The task also runs commerce SEO copy support so the listing is more ready for marketplace and shop presentation.

### 7.4 Tag enrichment

Suggested tags from the AI analysis are merged into the product so the item is better categorized and easier to reuse in later content workflows.

---

## 8. Pricing Logic

Pricing resolution is one of the most important parts of Batch Snap because many sellers do not want to type the same price repeatedly.

The price resolver uses a clear precedence order.

### 8.1 Price priority order

The final item price is resolved in this order:

1. visible detected tag price from the image
2. per-item price entered in the form
3. stall-level default price from the voice brief
4. stall-level bulk/default fallback
5. existing product price if already present

### 8.2 Why this matters

This design matches real stall behavior:

- if the tag is visible, trust the tag
- if the seller typed a row price, use that
- otherwise, apply the stall default

That reduces repetitive data entry while still preserving item-level accuracy where needed.

### 8.3 Currency behavior

The session also stores a default currency, and pricing can propagate that currency to products when default rules are applied.

---

## 9. Content Generation per Item

Batch Snap does not stop at catalog creation.

For each processed item, Kova also creates a content-generation seed.

### 9.1 Per-item seed creation

Each product gets a `ContentSeed` with:

- the enriched product context
- campaign angle
- audience hints
- features
- market-day tone
- stall context references

### 9.2 Why the seed layer matters

This keeps Batch Snap connected to the rest of Kova's content system.

It means the output is not locked inside the products feature. It can flow into:

- post drafting
- queue generation
- carousel logic
- reel generation
- broader marketing automation

### 9.3 Market-day-aware copy generation

The seed idea builder pushes the downstream content toward:

- same-day freshness
- specific item focus
- local buyer trust
- non-generic tone

This is a major difference from a bland catalog importer.

---

## 10. Stall Launch Bundle

One of the strongest parts of the upgraded Batch Snap flow is that the whole stall can be finalized as one launch bundle.

This happens in `finalize_batch_snap_session`.

### 10.1 What the launch bundle creates

When `launch_bundle` is enabled, Kova can create:

- a collection-level `ContentSeed`
- a showcase reel
- a seller WhatsApp-ready message
- a final shop URL

### 10.2 Shop URL generation

The finalizer resolves the seller's shop page slug and builds the shop URL.

That URL becomes the core destination the seller can share after the batch is processed.

### 10.3 Collection-level campaign copy

Kova generates a stall-wide launch package that can include:

- collection post idea
- reel caption
- reel hook text
- seller WhatsApp message
- hashtags

This is designed to announce the whole batch as a live selling event, not just several separate items.

### 10.4 Showcase reel

If enough images are available and supported platforms are connected, Kova creates a reel-style launch bundle using several of the batch item images.

This helps the whole stall feel like a coordinated drop.

### 10.5 Seller WhatsApp ping

If WhatsApp credentials and the user's phone number are configured, the finalizer can send a WhatsApp template-based seller notification that the stall is live.

This is a seller-facing operational confirmation, not a buyer broadcast.

---

## 11. Live Pipeline Status

Batch Snap includes a dedicated progress modal and batch-level status builder.

### 11.1 Why the pipeline modal matters

Batch Snap is a multi-step AI workflow. Without clear progress, the seller would not know whether:

- items are still processing
- content is still being created
- the stall launch bundle is still being finalized

### 11.2 Aggregated batch status

The batch status helper aggregates all linked products and produces:

- total item count
- completed count
- processing count
- failed count
- high-level steps
- detailed item log
- progress percentage
- session status
- final shop URL when available

### 11.3 Step model

The pipeline summary includes major stages such as:

- stall snap launched
- AI identifying each item
- writing posts for each item
- opening your stall

That makes the batch feel like a real orchestrated operation instead of a black box.

### 11.4 Terminal behavior

The status layer knows whether the process is still running or in a terminal state, which helps the modal behave correctly once the stall is ready.

---

## 12. End-to-End Processing Flow

The full Batch Snap flow works like this:

1. The seller opens `/snap/batch/`.
2. They optionally name the stall and set default pricing.
3. They optionally record a voice brief.
4. They choose `product`, `service`, or `digital`.
5. They take up to 10 photos.
6. Kova creates a `BatchSnapSession`.
7. Kova creates one linked `Product` per photo.
8. The background task parses the stall brief into structured context.
9. Each product is analyzed with a batch-aware vision prompt.
10. Kova replaces placeholder names where needed.
11. Kova resolves pricing using tags, form values, and stall defaults.
12. Kova enriches descriptions, tags, and SEO copy.
13. Kova creates one `ContentSeed` per item.
14. Kova triggers downstream content generation.
15. If launch bundle is enabled, Kova finalizes the stall:
    - builds collection-level copy
    - creates a showcase reel
    - resolves the shop URL
    - optionally pings the seller on WhatsApp
16. The batch status modal reflects progress until the stall is ready.

---

## 13. Differences from Snap to Sell

It is important to understand how Batch Snap differs from regular `Snap to Sell`.

### 13.1 Snap to Sell

`Snap to Sell` is best for:

- one product
- one main listing
- more focused product-by-product enrichment

### 13.2 Batch Snap

`Batch Snap` is best for:

- several items at once
- fast stall or table capture
- one shared selling moment
- launch-level coordination

### 13.3 Why both exist

The two flows serve different seller behaviors:

- `Snap to Sell` is the hero path for one item
- `Batch Snap` is the market-day path for many items

They complement each other instead of competing.

---

## 14. Tests and Validation

The Batch Snap upgrade includes focused test coverage around the most important logic.

### 14.1 Intelligence tests

Validation covers:

- heuristic price extraction
- stall brief fallback behavior
- placeholder-name detection
- batch-aware prompt construction
- price resolution precedence

### 14.2 Why these tests matter

These are high-risk areas because they directly affect:

- what items get called
- what price they are listed at
- whether the batch feels trustworthy

### 14.3 Examples of validated behavior

The tests verify behaviors such as:

- `"Everything 800 bob"` produces a `default_price`
- a seller-provided stall title survives fallback parsing
- placeholder item names are recognized correctly
- sibling names are injected into prompts to reduce duplicate naming
- visible tag prices override defaults

---

## 15. Important Files

### Core intelligence

- `apps/products/batch_snap_intelligence.py`

### Session and status

- `apps/products/models.py`
- `apps/products/migrations/0012_batchsnapsession.py`
- `apps/products/batch_snap_pipeline.py`

### Views and routes

- `apps/products/views.py`
- `apps/products/urls.py`

### Background orchestration

- `apps/products/tasks.py`

### UI

- `templates/products/snap_batch.html`
- `templates/products/_batch_snap_pipeline_modal.html`

### Tests

- `tests/test_batch_snap_market_day.py`

---

## 16. Strategic Value

The Batch Snap upgrade matters because it moves Kova closer to real field selling behavior.

It is not just a catalog feature.

It is an operational commerce workflow that understands:

- one-day selling events
- quick inventory capture
- repeated pricing patterns
- local market language
- launch coordination

It makes Kova more useful for sellers who do not have time to sit and manually build every listing one by one.

That is what makes Batch Snap powerful: it turns a walk around a stall into a live shop opening.

---

## 17. Bottom Line

The upgraded `Batch Snap` flow works as a market-day operating system for stall launches.

It combines:

- a seller-friendly capture interface
- stall-level voice intelligence
- batch-aware item identification
- smart pricing resolution
- per-item content generation
- a final stall launch bundle

The result is a flow where a seller can move from "I have a whole table to sell today" to "my shop is live and I have launch content" with dramatically less effort than a manual listing workflow.
