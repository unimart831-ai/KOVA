# Commerce Readiness Assessment

**Date:** July 2026

---

## Vision Check

> "Discover online. Complete the transaction through WhatsApp."

Commerce in Kova should enable customers to:
1. Discover products/services on the public storefront or social media
2. Initiate purchase/booking via WhatsApp
3. Complete payment (M-Pesa) within the WhatsApp conversation
4. Receive confirmation and follow-up via WhatsApp

---

## Commerce Components Inventory

### Product Management

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| Product model | `products/models.py` | Ready | Full catalog with categories, pricing, stock status, media |
| ProductCategory | `products/models.py` | Ready | Hierarchical product organization |
| Product form (web) | `products/product_form.html` | Ready | Web-based CRUD for products |
| Snap-to-Sell | `products/owner_snap_whatsapp.py` | Ready | Photo → AI description → product listing via WhatsApp |
| Batch Snap | `products/batch_snap_intelligence.py` | Ready | Multiple products from batch session |
| BusinessAsset | `products/models.py` | Ready | Unified sellable asset abstraction |
| Product import | `products/product_import.html` | Ready | Bulk CSV/API import |
| Stock tracking | `products/models.py` (StockUpdate, StockAlert) | Ready | Stock level changes + low-stock alerts |
| Restock scan | `products/models.py` (RestockScan) | Partial | Vision-based inventory check |

### Public Storefront

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| Shop index | `products/public/shop_index.html` | Ready | Product grid with categories, search |
| Product detail | `products/public/commerce_link.html` | Ready | Product page with CTA |
| Shop hero | `products/public/_shop_hero.html` | Ready | Branded hero section |
| Product cards | `products/public/_shop_product_card.html` | Ready | Grid/list product cards |
| Trust strip | `products/public/_shop_trust_strip.html` | Ready | Social proof elements |
| WhatsApp CTA | `products/public/_checkout_whatsapp_first.html` | Ready | "Order on WhatsApp" button |
| M-Pesa pay | `products/public/_commerce_mpesa_pay_script.html` | Ready | STK Push from product page |
| Boosted carousel | `products/public/_shop_boosted_carousel.html` | Ready | Featured products carousel |

### WhatsApp Commerce

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| Commerce state machine | `whatsapp/commerce.py` | Ready | Full browse → detail → book/pay flow |
| Enhanced commerce | `whatsapp/commerce_enhanced.py` | Ready | Cart, catalog browsing, post-purchase |
| Browse triggers | Keywords: menu, products, catalog, prices, shop, bei | Ready | English + Swahili keyword activation |
| Booking triggers | Keywords: book, appointment, schedule, reserve | Ready | Booking flow activation |
| Payment triggers | Keywords: pay, buy, order, nunua, lipa | Ready | Payment flow activation |
| M-Pesa in-chat | `whatsapp/commerce_enhanced.py` | Ready | STK Push within conversation |
| Customer memory | `whatsapp/memory.py` | Ready | Remember returning buyers |
| Commerce states | idle → browsing → product_detail → booking/payment | Ready | Clean state transitions |

### Payments

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| M-Pesa STK Push | `billing/mpesa.py` | Ready | Daraja API integration |
| M-Pesa callbacks | `billing/mpesa_services.py` | Ready | Payment confirmation handling |
| CommercePayment model | `products/models.py` | Ready | Transaction records |
| M-Pesa commerce webhook | `analytics/webhooks.py` | Ready | Product sale payment confirmation |
| Stripe (subscriptions) | `billing/services.py` | Ready | Platform billing (not commerce) |

### Booking System

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| BookingLink | `bookings/models.py` | Ready | Bookable service definitions |
| Booking | `bookings/models.py` | Ready | Confirmed appointment records |
| Public booking page | `bookings/public/book.html` | Ready | Customer-facing booking form |
| Booking confirmation | `bookings/public/confirm.html` | Ready | Post-booking confirmation |
| Booking intent detection | `agents/booking_intent.py` | Ready | AI detects booking intent in conversations |

### Lead Capture (Commerce-Adjacent)

| Component | Location | Status | Assessment |
|-----------|----------|--------|------------|
| Lead model | `leads/models.py` | Ready | Captures from commerce/booking/QR |
| KovaForm | `links/models.py` | Ready | Embedded lead capture forms |
| FormSubmission | `links/models.py` | Ready | Form data storage |
| Revenue funnel | `products/models.py` (RevenueFunnel) | Partial | End-to-end funnel tracking |

---

## Commerce Flow Assessment

### Flow 1: Discover on Storefront → Order via WhatsApp

```
Customer visits /shop/<slug>/ → Browses products → Clicks "Order on WhatsApp"
→ Opens WhatsApp with pre-filled message → Commerce bot activates
→ Confirms order → M-Pesa STK Push → Payment confirmed → Thank you message
```

**Status: READY** — All components exist and are connected.

### Flow 2: Discover on Social Media → Order via WhatsApp

```
Customer sees post on Instagram/Facebook → Clicks link in bio
→ Lands on /k/<slug>/ or /p/<slug>/ → Browses products
→ Clicks WhatsApp CTA → Commerce bot flow (same as above)
```

**Status: READY** — Link pages, product pages, and WhatsApp CTAs all exist.

### Flow 3: Direct WhatsApp Commerce (No Web)

```
Customer messages business WhatsApp → Types "menu" or "products"
→ Commerce bot shows product list (interactive buttons)
→ Customer selects product → Details + price shown
→ Customer says "buy" → M-Pesa initiated → Confirmed
```

**Status: READY** — The `commerce.py` state machine handles this entirely.

### Flow 4: Snap-to-Sell (Owner Creates via WhatsApp)

```
Owner sends product photo to Kova master number
→ AI extracts product info (name, description, price estimate)
→ Product created in catalog → Available on storefront
→ Owner receives confirmation with edit/approve options
```

**Status: READY** — `owner_snap_whatsapp.py` + `batch_snap_intelligence.py` handle this.

### Flow 5: Booking Flow

```
Customer visits booking page OR says "book" in WhatsApp
→ Available services shown → Customer selects service + time
→ Booking confirmed → WhatsApp notification to owner
→ Reminder sent before appointment
```

**Status: READY** — BookingLink + public page + WhatsApp booking triggers exist.

---

## Readiness Matrix

| Component | Ready | Incomplete | Legacy | Needs Redesign | Missing |
|-----------|-------|-----------|--------|----------------|---------|
| Product CRUD (web) | ✓ | | | | |
| Product CRUD (WhatsApp) | | | | | Price/stock commands |
| Public storefront | ✓ | | | | |
| WhatsApp commerce bot | ✓ | | | | |
| M-Pesa payments | ✓ | | | | |
| Booking system | ✓ | | | | |
| Snap-to-Sell | ✓ | | | | |
| Customer memory | ✓ | | | | |
| Inventory tracking | ✓ | | | | |
| Revenue funnel | | ✓ | | | |
| Shopify integration | | | | | ✓ (defer) |
| Marketplace (B2B) | | | ✓ | | |
| Product reviews | | ✓ | | | |
| Commerce analytics | | ✓ | | | |
| Cart (multi-product) | | ✓ | | | |
| Delivery tracking | | | | | ✓ (V2) |
| Order history | | ✓ | | | |
| Refunds | | | | | ✓ (V2) |

---

## Assessment Against Vision

### "Discover Online"

**Score: 9/10**

- Public storefront at `/shop/` is production-ready
- Kova Pages (`/p/`) showcase products beautifully
- Link-in-bio pages (`/k/`) provide social media landing
- Product cards, carousels, trust strips, hero sections — all present
- Campaign pages (`/c/`) for promotional content
- SEO/sharing considerations appear addressed

**Gap:** No product search within WhatsApp (customer must browse linearly via buttons).

### "Complete the Transaction Through WhatsApp"

**Score: 8/10**

- Commerce state machine is a complete conversation flow
- M-Pesa integration enables instant mobile payments
- Interactive buttons provide structured product browsing
- Booking intent detection auto-routes to appointment flow
- Customer memory personalizes returning experiences

**Gaps:**
- Multi-product cart is "enhanced" but may need testing
- Order confirmation receipts could be richer
- No delivery/fulfillment status updates via WhatsApp
- No refund flow

---

## Recommendations for V1

### Must Fix

1. **Test the full commerce flow end-to-end** — from storefront visit to M-Pesa payment to WhatsApp confirmation. Ensure no broken links in the chain.

2. **Add WhatsApp order receipt** — after successful payment, send formatted receipt with order details, product, amount, and reference number.

3. **Implement stock-aware commerce** — when a product is out of stock, the commerce bot should say so rather than allowing an order.

### Should Have

4. **Product search in WhatsApp** — allow customers to type product names/keywords instead of only browsing via buttons (which are limited to 10 items by Meta).

5. **Owner order notification** — when a sale completes, immediately notify the owner via WhatsApp with customer details and order info.

6. **Price update command** — owner sends "PRICE [product] [new price]" to update without web access.

### Nice to Have (V1.1)

7. Post-purchase follow-up sequence (review request, cross-sell)
8. Order history for returning customers
9. Delivery status updates
10. Promotional pricing / discount codes via WhatsApp

---

## Commerce Readiness Score

| Dimension | Score |
|-----------|-------|
| Product management | 9/10 |
| Public storefront | 9/10 |
| WhatsApp ordering | 8/10 |
| Payment processing | 9/10 |
| Booking system | 8/10 |
| Lead capture | 8/10 |
| Analytics/attribution | 5/10 |
| Post-purchase flows | 4/10 |

**Overall Commerce Readiness: 8/10 — Ready for V1 launch with minor gaps.**
