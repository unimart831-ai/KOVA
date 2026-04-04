# KOVA Agent — Public REST API Reference

**Base URL**: `https://your-domain.com/api/v1/`  
**Version**: v1  
**Format**: JSON  
**Pagination**: 25 results per page (use `?page=2` for next page)

---

## Authentication

Every request must include an API token. Two methods are supported:

### Token Authentication (recommended for external apps)

```
Authorization: Token your-api-token-here
```

**How to get a token:**
1. Go to Django Admin → Auth Token → Tokens → Add
2. Select the user and save
3. Copy the generated token key

**Example request:**
```bash
curl -H "Authorization: Token abc123def456..." \
     https://your-domain.com/api/v1/posts/
```

### Session Authentication (for browser-based JS)

If the user is already logged in via the web UI, requests from the same browser automatically authenticate using the session cookie. Useful for HTMX or fetch() calls from within KOVA's own frontend.

> **Security note**: Session auth requires CSRF tokens for POST/PUT/PATCH/DELETE requests.

---

## Paginated Response Format

All list endpoints return paginated responses:

```json
{
    "count": 42,
    "next": "https://your-domain.com/api/v1/posts/?page=2",
    "previous": null,
    "results": [
        { ... },
        { ... }
    ]
}
```

| Field      | Type    | Description |
|------------|---------|-------------|
| `count`    | integer | Total number of results |
| `next`     | string  | URL for next page (null if last page) |
| `previous` | string  | URL for previous page (null if first page) |
| `results`  | array   | Array of resource objects |

---

## Error Responses

| Status Code | Meaning |
|-------------|---------|
| `400` | Bad Request — invalid data in request body |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — valid token but insufficient permissions |
| `404` | Not Found — resource doesn't exist or doesn't belong to you |
| `405` | Method Not Allowed — wrong HTTP method for this endpoint |

Error body:
```json
{
    "detail": "Authentication credentials were not provided."
}
```

Field-level validation errors:
```json
{
    "idea": ["This field is required."],
    "target_platforms": ["Expected a list of items but got type \"str\"."]
}
```

---

## Endpoints

### 1. Platforms

#### `GET /api/v1/platforms/`

List all connected social accounts (active only).

**Response** `200 OK`:
```json
{
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "a1b2c3d4-...",
            "platform": "twitter",
            "platform_display": "X (Twitter)",
            "username": "kova_hq",
            "display_name": "KOVA",
            "avatar_url": "https://pbs.twimg.com/...",
            "is_active": true,
            "last_synced_at": "2026-04-05T10:30:00Z",
            "connected_at": "2026-03-15T08:00:00Z"
        }
    ]
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique account ID |
| `platform` | string | Platform key — one of: `twitter`, `linkedin`, `instagram`, `facebook`, `tiktok`, `youtube`, `pinterest`, `threads`, `bluesky` |
| `platform_display` | string | Human-readable platform name |
| `username` | string | Username/handle on the platform |
| `display_name` | string | Profile display name |
| `avatar_url` | string | Profile picture URL |
| `is_active` | boolean | Whether the connection is active |
| `last_synced_at` | datetime | Last successful sync with platform API |
| `connected_at` | datetime | When the account was first connected |

---

### 2. Content Seeds

Seeds are raw ideas that the AI agents turn into platform-specific posts.

#### `GET /api/v1/seeds/`

List all content seeds, newest first.

**Response** `200 OK`:
```json
{
    "count": 15,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "b2c3d4e5-...",
            "idea": "Write about our new feature launch",
            "notes": "Focus on the time-saving benefits",
            "target_platforms": ["twitter", "linkedin"],
            "status": "completed",
            "batch_strategy": "AI-generated strategy text...",
            "brand": null,
            "created_at": "2026-04-05T09:00:00Z",
            "updated_at": "2026-04-05T09:02:30Z"
        }
    ]
}
```

#### `POST /api/v1/seeds/`

Create a new content seed. This triggers the AI Create Agent to generate posts.

**Request body**:
```json
{
    "idea": "5 tips for better remote team communication",
    "notes": "Keep it practical, include a hook",
    "target_platforms": ["twitter", "linkedin"],
    "brand": "c3d4e5f6-..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `idea` | string | **Yes** | The raw content idea or topic |
| `notes` | string | No | Extra instructions for the AI |
| `target_platforms` | array | No | List of platform keys to generate for. Empty = all connected platforms |
| `brand` | uuid | No | Brand ID (for multi-brand teams). Null = user's default voice |
| `batch_strategy` | string | No | Manual strategy override |

**Response** `201 Created`:
```json
{
    "id": "d4e5f6a7-...",
    "idea": "5 tips for better remote team communication",
    "notes": "Keep it practical, include a hook",
    "target_platforms": ["twitter", "linkedin"],
    "status": "new",
    "batch_strategy": "",
    "brand": null,
    "created_at": "2026-04-05T11:00:00Z",
    "updated_at": "2026-04-05T11:00:00Z"
}
```

**Seed status values**:

| Status | Meaning |
|--------|---------|
| `new` | Just created, waiting for AI processing |
| `processing` | AI agents are generating posts from this seed |
| `completed` | Posts have been generated successfully |
| `failed` | Something went wrong during generation |

#### `GET /api/v1/seeds/{id}/`

Retrieve a single seed by ID.

---

### 3. Posts

#### `GET /api/v1/posts/`

List posts, newest first. Supports filtering.

**Query parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by post status (see table below) |
| `platform` | string | Filter by platform key (e.g. `twitter`) |
| `page` | integer | Page number for pagination |

**Examples**:
```bash
# All published posts
GET /api/v1/posts/?status=published

# All scheduled LinkedIn posts
GET /api/v1/posts/?status=scheduled&platform=linkedin

# Page 2 of drafts
GET /api/v1/posts/?status=draft&page=2
```

**Response** `200 OK`:
```json
{
    "count": 28,
    "next": "https://your-domain.com/api/v1/posts/?page=2",
    "previous": null,
    "results": [
        {
            "id": "e5f6a7b8-...",
            "content_text": "🚀 5 ways to improve your remote team communication:\n\n1. Default to async...",
            "content_type": "original",
            "status": "published",
            "platform": "twitter",
            "social_account": "a1b2c3d4-...",
            "social_account_name": "kova_hq",
            "media_urls": [],
            "scheduled_at": "2026-04-05T14:00:00Z",
            "published_at": "2026-04-05T14:00:12Z",
            "platform_post_id": "1908234567890",
            "platform_post_url": "https://twitter.com/kova_hq/status/1908234567890",
            "predicted_engagement_score": 72.5,
            "brand": null,
            "created_at": "2026-04-05T09:02:30Z",
            "updated_at": "2026-04-05T14:00:12Z"
        }
    ]
}
```

**Post status values**:

| Status | Meaning |
|--------|---------|
| `draft` | Created by AI, not yet reviewed |
| `pending_approval` | Submitted for team approval |
| `approved` | Approved, waiting to be scheduled |
| `scheduled` | Scheduled for future publishing |
| `publishing` | Currently being sent to the platform |
| `published` | Live on the platform |
| `failed` | Publishing failed (check error logs) |
| `rejected` | Rejected during approval |

**Content type values**:

| Type | Meaning |
|------|---------|
| `original` | Original content from a seed idea |
| `repurposed` | Adapted from existing content |
| `curated` | Curated from external sources |
| `reply` | A reply to another post/thread |

#### `GET /api/v1/posts/{id}/`

Retrieve a single post by ID.

#### `PATCH /api/v1/posts/{id}/`

Update a post. You can edit the text or reschedule.

**Request body** (include only fields you want to change):
```json
{
    "content_text": "Updated post text here...",
    "scheduled_at": "2026-04-06T10:00:00Z"
}
```

**Editable fields**:

| Field | Type | Description |
|-------|------|-------------|
| `content_text` | string | The post body text |
| `content_type` | string | Content type classification |
| `social_account` | uuid | Target social account ID |
| `media_urls` | array | List of media URLs to attach |
| `scheduled_at` | datetime | When to publish (ISO 8601 format) |
| `brand` | uuid | Brand ID |

**Response** `200 OK`: Returns the full updated post object.

---

### 4. Analytics

#### `GET /api/v1/analytics/summary/`

Get aggregate analytics across all your published posts.

**Response** `200 OK`:
```json
{
    "total_posts": 142,
    "published_posts": 98,
    "scheduled_posts": 12,
    "total_impressions": 245000,
    "total_likes": 8430,
    "total_comments": 1205,
    "total_shares": 3100,
    "avg_engagement_rate": 4.2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_posts` | integer | All posts (any status) |
| `published_posts` | integer | Posts that are live |
| `scheduled_posts` | integer | Posts waiting to publish |
| `total_impressions` | integer | Sum of all impressions |
| `total_likes` | integer | Sum of all likes/reactions |
| `total_comments` | integer | Sum of all comments |
| `total_shares` | integer | Sum of all shares/retweets |
| `avg_engagement_rate` | float | Average engagement rate (%) |

#### `GET /api/v1/analytics/metrics/{post_id}/`

Get detailed metrics for a specific published post.

**Response** `200 OK`:
```json
{
    "id": "f6a7b8c9-...",
    "post_id": "e5f6a7b8-...",
    "likes": 245,
    "comments": 32,
    "shares": 89,
    "impressions": 12400,
    "reach": 8200,
    "clicks": 156,
    "saves": 43,
    "engagement_rate": 4.8,
    "fetched_at": "2026-04-05T16:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Metric record ID |
| `post_id` | uuid | The post these metrics belong to |
| `likes` | integer | Like/reaction count |
| `comments` | integer | Comment count |
| `shares` | integer | Share/retweet count |
| `impressions` | integer | Total times shown in feeds |
| `reach` | integer | Unique accounts that saw the post |
| `clicks` | integer | Link clicks |
| `saves` | integer | Bookmark/save count |
| `engagement_rate` | float | Engagement rate (%) |
| `fetched_at` | datetime | When metrics were last pulled from the platform |

---

### 5. Agents

#### `GET /api/v1/agents/`

List your agent configurations and their status.

**Response** `200 OK`:
```json
{
    "count": 6,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "a7b8c9d0-...",
            "agent_type": "create",
            "agent_type_display": "Content Creator Agent",
            "is_active": true,
            "custom_instructions": "Always include a call-to-action",
            "config": {},
            "created_at": "2026-03-15T08:00:00Z",
            "updated_at": "2026-04-01T12:00:00Z"
        }
    ]
}
```

**Agent type values**:

| Type | Name | What it does |
|------|------|-------------|
| `research` | Research Agent | Trends, competitor tracking, opportunity briefs |
| `create` | Content Creator Agent | Turns seed ideas into platform-native posts |
| `adapt` | Platform Adapter Agent | Smart timing, schedule optimization |
| `engage` | Engagement Agent | Comments, DMs, community management |
| `analyst` | Analytics Agent | Content DNA, A/B testing, performance analysis |
| `strategist` | Chief Strategist | Orchestrates all agents, strategic decisions |

#### `GET /api/v1/agents/actions/`

List recent agent actions (what the AI has been doing).

**Query parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_type` | string | Filter by agent type (e.g. `create`) |

**Example**:
```bash
GET /api/v1/agents/actions/?agent_type=create
```

**Response** `200 OK`:
```json
{
    "count": 50,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "b8c9d0e1-...",
            "agent_type": "create",
            "action_type": "generate_posts",
            "description": "Generated 3 posts from seed: '5 tips for remote teams'",
            "status": "completed",
            "tokens_used": 2450,
            "model_used": "gpt-4o-mini",
            "duration_ms": 3200,
            "created_at": "2026-04-05T09:02:00Z",
            "completed_at": "2026-04-05T09:02:30Z"
        }
    ]
}
```

**Action status values**:

| Status | Meaning |
|--------|---------|
| `started` | Agent began working |
| `completed` | Finished successfully |
| `failed` | Something went wrong |
| `needs_approval` | Output needs human review before proceeding |

---

### 6. Conversions (Revenue Attribution)

Track revenue and conversion events attributed to your social media posts.

#### `GET /api/v1/conversions/`

List conversion events, newest first.

**Query parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | Filter by conversion type: `click`, `lead`, `sale`, `custom` |

**Response** `200 OK`:
```json
{
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "c9d0e1f2-...",
            "conversion_type": "sale",
            "revenue": "49.99",
            "event_name": "Pro Plan Purchase",
            "post": "e5f6a7b8-...",
            "social_account": "a1b2c3d4-...",
            "utm_source": "twitter",
            "utm_medium": "social",
            "utm_campaign": "spring_launch",
            "utm_content": "e5f6a7b8-...",
            "metadata": {"order_id": "ORD-12345"},
            "created_at": "2026-04-05T15:30:00Z"
        }
    ]
}
```

#### `POST /api/v1/conversions/`

Log a new conversion event. Call this from your website's backend when a conversion happens.

**Request body**:
```json
{
    "conversion_type": "sale",
    "revenue": "49.99",
    "event_name": "Pro Plan Purchase",
    "post": "e5f6a7b8-...",
    "social_account": "a1b2c3d4-...",
    "utm_source": "twitter",
    "utm_medium": "social",
    "utm_campaign": "spring_launch",
    "utm_content": "e5f6a7b8-...",
    "metadata": {"order_id": "ORD-12345"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `conversion_type` | string | No (default: `click`) | One of: `click`, `lead`, `sale`, `custom` |
| `revenue` | decimal | No (default: `0`) | Revenue amount in dollars (e.g. `"49.99"`) |
| `event_name` | string | No | Custom label for the event |
| `post` | uuid | No | ID of the KOVA post that led to this conversion |
| `social_account` | uuid | No | Social account the traffic came from |
| `utm_source` | string | No | UTM source parameter |
| `utm_medium` | string | No | UTM medium parameter |
| `utm_campaign` | string | No | UTM campaign parameter |
| `utm_content` | string | No | UTM content parameter (recommended: use post ID) |
| `metadata` | object | No | Any extra data (order ID, customer segment, etc.) |

**Conversion type values**:

| Type | When to use |
|------|------------|
| `click` | User clicked a link in your post |
| `lead` | User signed up, subscribed, or filled a form |
| `sale` | User made a purchase |
| `custom` | Any other event you want to track |

**Response** `201 Created`: Returns the created conversion object.

---

## Integration Examples

### Python

```python
import requests

API_URL = "https://your-domain.com/api/v1"
TOKEN = "your-api-token-here"
HEADERS = {"Authorization": f"Token {TOKEN}"}

# List published posts
response = requests.get(f"{API_URL}/posts/?status=published", headers=HEADERS)
posts = response.json()["results"]

for post in posts:
    print(f"[{post['platform']}] {post['content_text'][:80]}...")

# Create a new content seed
seed_data = {
    "idea": "How AI is changing social media marketing in 2026",
    "target_platforms": ["twitter", "linkedin"],
}
response = requests.post(f"{API_URL}/seeds/", json=seed_data, headers=HEADERS)
print(f"Seed created: {response.json()['id']}")

# Log a conversion
conversion = {
    "conversion_type": "sale",
    "revenue": "79.00",
    "utm_source": "linkedin",
    "utm_campaign": "ai_marketing_post",
    "post": "e5f6a7b8-...",
    "metadata": {"plan": "growth"},
}
requests.post(f"{API_URL}/conversions/", json=conversion, headers=HEADERS)
```

### JavaScript (fetch)

```javascript
const API_URL = "https://your-domain.com/api/v1";
const TOKEN = "your-api-token-here";

const headers = {
  "Authorization": `Token ${TOKEN}`,
  "Content-Type": "application/json",
};

// Get analytics summary
const res = await fetch(`${API_URL}/analytics/summary/`, { headers });
const stats = await res.json();
console.log(`Published: ${stats.published_posts}, Likes: ${stats.total_likes}`);

// Create a seed from your app
const seed = await fetch(`${API_URL}/seeds/`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    idea: "Behind-the-scenes of our product launch",
    notes: "Make it authentic and relatable",
  }),
});
console.log("Seed ID:", (await seed.json()).id);
```

### cURL

```bash
# Get your connected platforms
curl -s -H "Authorization: Token abc123..." \
  https://your-domain.com/api/v1/platforms/ | python -m json.tool

# Get analytics summary
curl -s -H "Authorization: Token abc123..." \
  https://your-domain.com/api/v1/analytics/summary/

# Create a seed
curl -X POST \
  -H "Authorization: Token abc123..." \
  -H "Content-Type: application/json" \
  -d '{"idea": "Top 3 mistakes in social media marketing"}' \
  https://your-domain.com/api/v1/seeds/

# Log a sale conversion
curl -X POST \
  -H "Authorization: Token abc123..." \
  -H "Content-Type: application/json" \
  -d '{"conversion_type": "sale", "revenue": "149.00", "utm_source": "twitter"}' \
  https://your-domain.com/api/v1/conversions/
```

### Website Conversion Tracking (server-side)

Add this to your website's order confirmation / thank-you page backend:

```python
# In your Django/Flask/Express checkout success handler:
import requests

KOVA_API = "https://your-domain.com/api/v1"
KOVA_TOKEN = os.environ["KOVA_API_TOKEN"]

def on_purchase_complete(order):
    """Report the conversion back to KOVA for attribution."""
    # Extract UTM params that were stored when user landed
    requests.post(
        f"{KOVA_API}/conversions/",
        headers={"Authorization": f"Token {KOVA_TOKEN}"},
        json={
            "conversion_type": "sale",
            "revenue": str(order.total),
            "event_name": f"Order #{order.id}",
            "utm_source": order.utm_source,      # e.g. "twitter"
            "utm_medium": order.utm_medium,       # e.g. "social"
            "utm_campaign": order.utm_campaign,   # e.g. "spring_launch"
            "utm_content": order.utm_content,     # e.g. the KOVA post UUID
            "metadata": {
                "order_id": str(order.id),
                "product": order.product_name,
            },
        },
    )
```

---

## UTM Parameter Convention

When KOVA generates links in posts, use this UTM structure for accurate attribution:

| Parameter | Value | Example |
|-----------|-------|---------|
| `utm_source` | Platform name | `twitter`, `linkedin` |
| `utm_medium` | Always `social` | `social` |
| `utm_campaign` | Your campaign name | `spring_launch` |
| `utm_content` | KOVA Post UUID | `e5f6a7b8-1234-5678-...` |

**Example link in a post**:
```
https://yoursite.com/pricing?utm_source=twitter&utm_medium=social&utm_campaign=spring_launch&utm_content=e5f6a7b8-1234-5678
```

This lets you trace: **which post → on which platform → drove which sale**.

---

## Rate Limits

Currently no hard rate limits are enforced. Be reasonable:
- Read endpoints: up to 60 requests/minute
- Write endpoints: up to 20 requests/minute

Abuse will result in token revocation.

---

## Plan Availability

| Feature | Starter | Growth | Pro | Agency |
|---------|---------|--------|-----|--------|
| API Access | ❌ | ❌ | ✅ | ✅ |
| Token Auth | — | — | 1 token | Unlimited |
| Conversion Tracking | ❌ | ❌ | ✅ | ✅ |
| Revenue Dashboard | ❌ | ❌ | ✅ | ✅ |
