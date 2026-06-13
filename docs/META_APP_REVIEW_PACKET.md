# Meta App Review Submission Packet — Kova Agent

> **Purpose:** Everything needed to pass Meta App Review for Instagram + Facebook
> publishing/engagement and the WhatsApp Business Platform. This is the real
> critical path to onboarding our first real (non-test) user.
>
> **Owner:** Founder · **Status:** Not submitted · **Last updated:** Jun 2026
>
> **Source of truth for scopes:** `apps/platforms/providers/instagram_facebook.py`
> (`FB_SCOPES`). If you change scopes there, update this doc and re-submit.

---

## 0. The dependency chain (do these in order)

```
1. Registered legal company  (Kenya Ltd / sole prop with docs)
        ↓
2. Meta Business Manager + Business Verification  (needs the company docs)
        ↓
3. App configured (URLs, use cases, test users) + Advanced Access requests
        ↓
4. Screencasts recorded (one per permission group) → submit
        ↓
5. Approved → flip app to Live mode → real users can connect
```

**Until step 5, run the dev-mode pilot:** add pilot businesses as app
*testers/roles* in the App Dashboard. Testers get full real permissions with
**no review required**, so we gather the case study while review is pending.

---

## 1. Pre-submission checklist

- [ ] Company legally registered; registration documents scanned (PDF)
- [ ] Meta Business Manager created
- [ ] **Business Verification** submitted and approved (Settings → Business Info)
- [ ] App created under the verified Business (type: Business)
- [ ] App icon (1024×1024), category, and long description set
- [ ] Privacy Policy URL set → `https://<domain>/privacy/`
- [ ] User Data Deletion set → **Callback URL** `https://<domain>/platforms/facebook/data-deletion/`
      (instructions page: `https://<domain>/legal/facebook-data-deletion/`)
- [ ] App Domains + Valid OAuth Redirect URIs include `https://<domain>/platforms/callback/facebook/` and `.../instagram/`
- [ ] Facebook Login for Business: a **Configuration** created; its `config_id` set as `FB_LOGIN_CONFIG_ID` in prod env (or rely on classic `FB_SCOPES` fallback)
- [ ] At least one **test user / role** added (the pilot businesses)
- [ ] A screencast tool ready (Loom / OBS) and a clean demo account with real content
- [ ] Data Handling questions answered (we store tokens encrypted via Fernet — see `apps/platforms/encryption.py`)

---

## 2. App configuration values (copy-paste)

| Setting | Value |
|---|---|
| Privacy Policy URL | `https://<domain>/privacy/` |
| Terms of Service URL | `https://<domain>/terms/` |
| User Data Deletion — Callback | `https://<domain>/platforms/facebook/data-deletion/` |
| User Data Deletion — Instructions | `https://<domain>/legal/facebook-data-deletion/` |
| Deletion status URL pattern | `https://<domain>/legal/facebook-data-deletion/status/<code>/` |
| OAuth redirect (Facebook) | `https://<domain>/platforms/callback/facebook/` |
| OAuth redirect (Instagram) | `https://<domain>/platforms/callback/instagram/` |
| Graph API version in use | `v25.0` |

> Verify the deletion callback responds before submitting:
> `GET https://<domain>/platforms/facebook/data-deletion/probe/`

---

## 3. Permissions requested — justification table

These are the scopes in `FB_SCOPES`. Each needs Advanced Access + a justification
+ a screencast showing it used **in the product** (not just described).

| Permission | Why Kova needs it (reviewer justification) | Where demonstrated |
|---|---|---|
| `public_profile`, `email` | Create/link the user's Kova account on connect | Connect flow → account created |
| `business_management` *(add if prompted)* | Access the Business's Pages/IG assets the user manages | Connect → asset picker |
| `pages_show_list` *(if prompted)* | List the Pages the user can choose to manage in Kova | `/platforms/facebook/<id>/select-page/` |
| `pages_manage_metadata` | Read Page profile + subscribe to webhooks for engagement | Profile audit + engage sync |
| `pages_manage_posts` | Publish/schedule the content the user approves in Studio | `/content/studio/` → `/content/queue/` publish |
| `pages_read_engagement` | Read post performance + incoming comments to surface in app | `/engage/` inbox + Performance |
| `pages_manage_engagement` | Post the AI-drafted reply the user approves to a comment | `/engage/` → approve reply |
| `pages_messaging` | Read + reply to Page (Messenger) conversations in the inbox | `/engage/` DM thread |
| `read_insights` | Show Page/post analytics in the user's dashboard | Performance / analytics views |
| `instagram_content_publish` | Publish the approved post/carousel/reel to the user's IG | `/content/studio/` → publish to IG |
| `instagram_manage_insights` | Show IG post + account insights to the user | Performance views |
| `instagram_manage_comments` | Read IG comments + post the user-approved reply | `/engage/` IG comment thread |
| `instagram_manage_messages` | Read + reply to IG DMs in the unified inbox | `/engage/` IG DM thread |

> **Note on messaging permissions** (`pages_messaging`, `instagram_manage_messages`):
> reviewers scrutinize these hardest. Show a **real human approving the reply**
> (suggest-mode), not silent automation, and state that auto-send is opt-in and
> gated. This matches our actual Engage default and is the honest framing.

---

## 4. Screencast scripts (record one per group)

Use a **test-user account** with a real Page + IG Business account that has a few
posts and at least one comment/DM. Narrate each step out loud or with captions.

### Screencast A — Connect + Publish (covers content_publish, manage_posts)
1. Log in to Kova at `https://<domain>/`.
2. Go to **Platforms** (`/platforms/`) → click **Connect Facebook/Instagram**.
3. Complete Facebook Login, grant permissions, select the Page + IG account.
4. Show the connected account appears in `/platforms/`.
5. Go to **Studio** (`/content/studio/`), open an AI-drafted post, click **Approve**.
6. Show it scheduled in **Queue** (`/content/queue/`), then show the **live post**
   on the actual Facebook Page and Instagram profile.

### Screencast B — Engagement (covers manage_comments, manage_engagement, read_engagement)
1. From a second device, leave a comment on the test Page/IG post.
2. In Kova **Engage** (`/engage/`), show the comment appears in the inbox.
3. Show the AI-drafted reply suggestion; click **Approve/Send**.
4. Show the reply now visible under the comment on Facebook/Instagram.

### Screencast C — Messaging (covers pages_messaging, instagram_manage_messages)
1. From a second device, send a DM to the Page / IG account.
2. In Kova **Engage** (`/engage/`), open the conversation thread.
3. Show the suggested reply, approve it, and show it delivered in Messenger/IG DM.
4. Explicitly say: "Auto-send is off by default; a human approves each reply."

### Screencast D — Insights (covers read_insights, manage_insights)
1. Open the Performance/analytics view.
2. Show real follower/reach/engagement numbers pulled from the connected account.

### Screencast E — Data deletion (compliance)
1. Visit `/legal/facebook-data-deletion/` and show the instructions.
2. Trigger a deletion (or show the callback probe responding) and the status page.

---

## 5. Reviewer test instructions (paste into the submission form)

```
Test account:
  URL: https://<domain>/
  Email: reviewer@<domain>
  Password: <set a stable reviewer password>

This account is pre-connected to a Facebook Page + Instagram Business account
with sample content. To test:
1. Go to /platforms/ to see the connected accounts (or reconnect).
2. Go to /content/studio/ to approve and publish a post (Screencast A).
3. Go to /engage/ to view comments/DMs and approve a reply (Screencasts B & C).
4. Analytics are under the Performance tab (Screencast D).

Notes:
- Kova is an AI social media assistant for small businesses. All content and
  replies are drafted by AI and approved by the human user (approve-first).
- Auto-send is opt-in and disabled by default.
```

---

## 6. WhatsApp Business Platform (separate track)

| Step | Detail |
|---|---|
| WABA | Create a WhatsApp Business Account under the verified Business |
| Phone number | Add + verify a number not tied to a personal WhatsApp |
| Display name | Submit business display name for approval |
| Message templates | Submit each template in `docs/WHATSAPP_TEMPLATES.md` per category |
| Webhook | Point to our WhatsApp webhook; verify token set in env |
| Permissions | `whatsapp_business_messaging`, `whatsapp_business_management` |

> Service (user-initiated) conversations need no template. **Business-initiated
> (marketing/utility) messages require an approved template** — submit early,
> approval can take 24–48h and bounces on policy wording.

---

## 7. Common rejection reasons → how we avoid them

| Rejection | Avoidance |
|---|---|
| "Couldn't reproduce permission use" | Screencast must show the permission *working in-product*, end to end, on a real asset |
| "Business not verified" | Finish Business Verification before requesting Advanced Access |
| Messaging permissions denied | Show human-in-the-loop approval; state auto-send is opt-in/off by default |
| Privacy policy inaccessible | Confirm `/privacy/` loads publicly (no login wall) |
| Data deletion not working | Confirm callback responds (use the `/probe/` endpoint) |
| Login fails for reviewer | Use a stable reviewer password; keep the test account connected |
| Scope mismatch | `FB_SCOPES` in code must equal the permissions requested in the dashboard |

---

## 8. After approval

- [ ] Flip app to **Live** mode
- [ ] Confirm a brand-new (non-test) account can connect IG + FB end to end
- [ ] Remove temporary reviewer access if desired
- [ ] Update `KOVA_Executive_Summary.md` traction line to "Meta-approved; public onboarding live" (only once true)
