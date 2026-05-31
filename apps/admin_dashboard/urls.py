from django.urls import path

from apps.admin_dashboard.views import ab_tests, agents, analytics, billing, blog, bookings, calendar_intel, campaigns, content, costs, emails, engage, feature_usage, help, innovations, leads, llm, logs, media_queue, memes, notifications, onboarding, operations, overview, partners, partials, photoroom, pixel, platforms, products, profile_audit, qr, reel_music, revenue, reviews, seed_quota, system, system_maps, teams, user_health, users, whatsapp

app_name = "admin_dashboard"

urlpatterns = [
    # Overview
    path("", overview.overview, name="overview"),
    path("feature-usage/", feature_usage.feature_usage, name="feature_usage"),

    # Users
    path("users/", users.user_list, name="user_list"),
    path("users/export/", users.user_export_csv, name="user_export"),
    path("users/<uuid:pk>/", users.user_detail, name="user_detail"),
    path("users/<uuid:pk>/change-plan/", users.user_change_plan, name="user_change_plan"),
    path("users/<uuid:pk>/toggle-staff/", users.user_toggle_staff, name="user_toggle_staff"),
    path("users/<uuid:pk>/toggle-active/", users.user_toggle_active, name="user_toggle_active"),
    path("users/<uuid:pk>/delete/", users.user_delete, name="user_delete"),
    path("users/health/", user_health.user_health, name="user_health"),
    path("users/onboarding-funnel/", onboarding.onboarding_funnel, name="onboarding_funnel"),

    # Operations (platform-wide task activity)
    path("operations/", operations.operations_overview, name="operations_overview"),

    # Reel music catalog
    path("reel-music/", reel_music.reel_music_manage, name="reel_music_manage"),
    path("reel-music/upload/", reel_music.reel_music_upload, name="reel_music_upload"),
    path("reel-music/<str:track_id>/replace/", reel_music.reel_music_replace, name="reel_music_replace"),
    path("reel-music/<str:track_id>/delete/", reel_music.reel_music_delete, name="reel_music_delete"),
    path("reel-music/<str:track_id>/preview/", reel_music.reel_music_preview, name="reel_music_preview"),

    # Leads & CRM (REACH automation)
    path("leads/", leads.leads_overview, name="leads_overview"),
    path("leads/nurture/", leads.leads_nurture, name="leads_nurture"),
    path("leads/list/", leads.lead_list, name="lead_list"),

    # Bookings
    path("bookings/", bookings.bookings_overview, name="bookings_overview"),
    path("bookings/list/", bookings.booking_list, name="booking_list"),

    # Reviews
    path("reviews/", reviews.reviews_overview, name="reviews_overview"),
    path("reviews/list/", reviews.review_list, name="review_list"),

    # QR & Walk-ins
    path("qr/", qr.qr_overview, name="qr_overview"),
    path("qr/list/", qr.qr_list, name="qr_list"),

    # Content
    path("content/", content.content_overview, name="content_overview"),
    path("content/posts/", content.post_list, name="post_list"),
    path("content/posts/<uuid:pk>/", content.post_detail, name="post_detail_admin"),
    path("content/seeds/", content.seed_list, name="seed_list"),
    path("content/seed-quotas/", seed_quota.seed_quota_hub, name="seed_quota_hub"),
    path("content/seed-quotas/log/", seed_quota.seed_quota_log, name="seed_quota_log"),
    path("users/<uuid:pk>/seed-quota/", seed_quota.seed_quota_action, name="seed_quota_action"),
    path("content/failed/", content.failed_content, name="failed_content"),

    # Agents
    path("agents/", agents.agent_overview, name="agent_overview"),
    path("agents/log/", agents.agent_log, name="agent_log"),
    path("agents/tokens/", agents.token_economics, name="token_economics"),

    # LLM Configuration
    path("llm/", llm.llm_overview, name="llm_overview"),
    path("llm/update/", llm.llm_update_config, name="llm_update_config"),
    path("llm/task-model/", llm.llm_update_task_model, name="llm_update_task_model"),
    path("llm/plan-models/", llm.llm_update_plan_models, name="llm_update_plan_models"),
    path("llm/rate-limits/", llm.llm_update_rate_limits, name="llm_update_rate_limits"),
    path("llm/apply-preset/", llm.llm_apply_preset, name="llm_apply_preset"),
    path("llm/image-config/", llm.llm_update_image_config, name="llm_update_image_config"),
    path("llm/image-plan-models/", llm.llm_update_image_plan_models, name="llm_update_image_plan_models"),

    # Platforms
    path("platforms/", platforms.platform_overview, name="platform_overview"),
    path("platforms/accounts/", platforms.platform_accounts, name="platform_accounts"),

    # Billing
    path("billing/", billing.billing_overview, name="billing_overview"),
    path("billing/payments/", billing.payment_list, name="payment_list"),
    path("billing/events/", billing.billing_events, name="billing_events"),
    path("billing/subscriptions/", billing.subscription_management, name="subscription_management"),
    path("billing/subscriptions/action/", billing.subscription_action, name="subscription_action"),
    path("billing/bulk-grant/", billing.bulk_grant, name="bulk_grant"),
    path("billing/overrides/", billing.override_log, name="override_log"),
    path("billing/pricing/", billing.plan_pricing, name="plan_pricing"),
    path("billing/pricing/update/", billing.plan_pricing_update, name="plan_pricing_update"),
    path("billing/discounts/", billing.discount_list, name="discount_list"),
    path("billing/discounts/create/", billing.discount_create, name="discount_create"),
    path("billing/discounts/<uuid:pk>/edit/", billing.discount_edit, name="discount_edit"),
    path("billing/discounts/<uuid:pk>/toggle/", billing.discount_toggle, name="discount_toggle"),

    # Cost Economics
    path("costs/", costs.cost_overview, name="cost_overview"),
    path("costs/calculator/", costs.cost_calculator, name="cost_calculator"),

    # Engagement
    path("engage/", engage.engagement_overview, name="engagement_overview"),
    path("engage/interactions/", engage.interaction_feed, name="interaction_feed"),
    path("engage/superfans/", engage.superfan_leaderboard, name="superfan_leaderboard"),

    # HTMX Partials (auto-refresh)
    path("_partials/stat-cards/", partials.partial_stat_cards, name="partial_stat_cards"),
    path("_partials/activity-feed/", partials.partial_activity_feed, name="partial_activity_feed"),
    path("_partials/agent-health/", partials.partial_agent_health, name="partial_agent_health"),

    # System
    path("system/", system.system_health, name="system_health"),
    path("system/errors/", system.error_log, name="error_log"),

    # Logs
    path("logs/", logs.activity_log, name="activity_log"),
    path("logs/export/", logs.log_export_csv, name="log_export"),

    # Analytics
    path("analytics/", analytics.analytics_overview, name="analytics_overview"),
    path("analytics/content-dna/", analytics.content_dna_analysis, name="content_dna_analysis"),
    path("analytics/competitors/", analytics.competitor_overview, name="competitor_overview"),

    # Revenue Attribution
    path("revenue/", revenue.revenue_overview, name="revenue_overview"),
    path("revenue/conversions/", revenue.conversion_list, name="revenue_conversions"),
    path("revenue/shopify/", revenue.shopify_stores_list, name="shopify_stores"),
    path("revenue/shopify/<uuid:pk>/toggle/", revenue.shopify_store_toggle, name="shopify_store_toggle"),
    path("revenue/journeys/", revenue.journey_list, name="revenue_journeys"),

    # Kova Pixel
    path("pixel/", pixel.pixel_overview, name="pixel_overview"),
    path("pixel/events/", pixel.pixel_events, name="pixel_events"),
    path("pixel/users/", pixel.pixel_users, name="pixel_users"),

    # Teams
    path("teams/", teams.teams_overview, name="teams_overview"),
    path("teams/list/", teams.team_list, name="team_list"),
    path("teams/<uuid:pk>/", teams.team_detail, name="team_detail"),

    # A/B Tests
    path("ab-tests/", ab_tests.ab_tests_overview, name="ab_tests_overview"),
    path("ab-tests/list/", ab_tests.ab_test_list_admin, name="ab_test_list_admin"),
    path("ab-tests/<uuid:pk>/", ab_tests.ab_test_detail_admin, name="ab_test_detail_admin"),

    # Emails
    path("emails/", emails.email_overview, name="emails"),
    path("emails/log/", emails.email_log, name="email_log"),
    path("emails/<uuid:pk>/", emails.email_detail, name="email_detail"),
    path("emails/test/", emails.send_test_email, name="email_test"),
    path("emails/broadcast/", emails.send_broadcast, name="email_broadcast"),

    # Partners
    path("partners/", partners.partners_overview, name="partners_overview"),
    path("partners/applications/", partners.application_list, name="partner_applications"),
    path("partners/applications/action/", partners.application_action, name="partner_application_action"),
    path("partners/list/", partners.partner_list, name="partner_list"),
    path("partners/<int:pk>/", partners.partner_detail, name="partner_detail"),
    path("partners/<int:pk>/commissions/pay/", partners.partner_mark_commissions_paid, name="partner_commissions_pay"),
    path("partners/<int:pk>/payouts/<int:request_id>/", partners.partner_payout_action, name="partner_payout_action"),

    # Marketplace Partners
    path("partners/marketplaces/", partners.marketplace_list, name="marketplace_list"),
    path("partners/marketplaces/create/", partners.marketplace_create, name="marketplace_create"),
    path("partners/marketplaces/<int:pk>/", partners.marketplace_detail, name="marketplace_detail"),
    path("partners/marketplaces/<int:pk>/import-sellers/", partners.marketplace_import_sellers, name="marketplace_import_sellers"),
    path("partners/marketplaces/<int:pk>/update/", partners.marketplace_update, name="marketplace_update"),
    path("partners/webhooks/", partners.partners_webhook_logs, name="partners_webhook_logs"),

    # Help Center
    path("help/", help.help_overview, name="help_overview"),
    path("help/articles/", help.help_article_views, name="help_article_views"),
    path("help/log/", help.help_view_log, name="help_view_log"),

    # System Maps (internal ops reference — staff only)
    path("system-maps/", system_maps.system_maps_index, name="system_maps"),
    path("system-maps/print/", system_maps.system_maps_print, name="system_maps_print"),
    path("system-maps/<slug:slug>/", system_maps.system_map_detail, name="system_map"),

    # Blog Studio (Educator agent editorial dashboard)
    path("blog/", blog.blog_studio, name="blog_studio"),
    path("blog/draft-next/", blog.blog_draft_next, name="blog_draft_next"),
    path("blog/suggest-topics/", blog.blog_suggest_topics, name="blog_suggest_topics"),
    path("blog/articles/<uuid:pk>/", blog.blog_article_review, name="blog_article_review"),
    path("blog/articles/<uuid:pk>/publish/", blog.blog_article_publish, name="blog_article_publish"),
    path("blog/articles/<uuid:pk>/unpublish/", blog.blog_article_unpublish, name="blog_article_unpublish"),
    path("blog/articles/<uuid:pk>/delete/", blog.blog_article_delete, name="blog_article_delete"),
    path("blog/topics/<uuid:pk>/draft/", blog.blog_draft_topic, name="blog_draft_topic"),
    path("blog/topics/<uuid:pk>/skip/", blog.blog_skip_topic, name="blog_skip_topic"),

    # Media Queue
    path("media-queue/", media_queue.media_queue_overview, name="media_queue_overview"),
    path("media-queue/<uuid:pk>/", media_queue.media_queue_detail, name="media_queue_detail"),
    path("media-queue/<uuid:pk>/toggle/", media_queue.media_queue_toggle, name="media_queue_toggle"),
    path("media-queue/process-now/", media_queue.media_queue_process_now, name="media_queue_process_now"),

    # Commerce (catalog, shops, payments, integrations)
    path("commerce/", products.commerce_overview, name="commerce_overview"),
    path("commerce/catalog/", products.commerce_catalog, name="commerce_catalog"),
    path("commerce/catalog/<uuid:pk>/", products.commerce_product_detail, name="commerce_product_detail"),
    path("commerce/shops/", products.commerce_shops, name="commerce_shops"),
    path("commerce/payments/", products.commerce_payments, name="commerce_payments"),
    path("commerce/integrations/", products.commerce_integrations, name="commerce_integrations"),
    path("commerce/alerts/", products.commerce_stock_alerts, name="commerce_stock_alerts"),
    path("commerce/stock/", products.commerce_stock_updates, name="commerce_stock_updates"),
    path("commerce/photoroom/", photoroom.photoroom_config, name="commerce_photoroom"),
    # Legacy product URLs (same views)
    path("products/", products.commerce_overview, name="products_overview"),
    path("products/list/", products.commerce_catalog, name="admin_product_list"),
    path("products/alerts/", products.commerce_stock_alerts, name="admin_stock_alerts"),
    path("products/updates/", products.commerce_stock_updates, name="admin_stock_updates"),

    # Campaigns
    path("campaigns/", campaigns.campaigns_overview, name="campaigns_overview"),
    path("campaigns/list/", campaigns.campaign_list_admin, name="admin_campaign_list"),

    # Meme Intelligence
    path("memes/", memes.memes_overview, name="memes_overview"),
    path("memes/list/", memes.meme_list_admin, name="meme_list_admin"),
    path("memes/adaptations/", memes.adaptation_list_admin, name="adaptation_list_admin"),

    # Calendar Intelligence (holiday awareness)
    path("calendar/", calendar_intel.calendar_overview, name="calendar_overview"),
    path("calendar/drafts/", calendar_intel.draft_list_admin, name="calendar_drafts"),
    path("calendar/drafts/<int:pk>/retry/", calendar_intel.draft_retry, name="calendar_draft_retry"),

    # Profile Audits (connected-account health)
    path("profile-audits/", profile_audit.profile_audit_overview, name="profile_audit_overview"),

    # Notifications
    path("notifications/", notifications.notifications_overview, name="notifications_overview"),
    path("notifications/log/", notifications.notification_log, name="notification_log"),

    # WhatsApp
    path("whatsapp/", whatsapp.whatsapp_overview, name="whatsapp_overview"),
    path("whatsapp/conversations/", whatsapp.whatsapp_conversations, name="whatsapp_conversations"),
    path("whatsapp/templates/", whatsapp.whatsapp_templates, name="whatsapp_templates"),
    path("whatsapp/broadcasts/", whatsapp.whatsapp_broadcasts, name="whatsapp_broadcasts"),
    path("whatsapp/sequences/", whatsapp.whatsapp_sequences, name="whatsapp_sequences"),
    path("whatsapp/commerce-receipts/", whatsapp.whatsapp_commerce_receipts, name="whatsapp_commerce_receipts"),
    path("whatsapp/brief-delivery/", whatsapp.whatsapp_brief_delivery, name="whatsapp_brief_delivery"),

    # Innovations
    path("innovations/", innovations.innovations_overview, name="innovations_overview"),
    path("innovations/voice/", innovations.voice_brief_list, name="voice_brief_list"),
    path("innovations/voice/<uuid:pk>/", innovations.voice_brief_detail, name="voice_brief_detail"),
    path("innovations/screenshots/", innovations.screenshot_list, name="screenshot_list"),
    path("innovations/screenshots/<uuid:pk>/", innovations.screenshot_detail, name="screenshot_detail"),
    path("innovations/restock/", innovations.restock_scan_list, name="restock_scan_list"),
    path("innovations/restock/<uuid:pk>/", innovations.restock_scan_detail, name="restock_scan_detail"),
    path("innovations/trends/", innovations.trend_alert_list, name="trend_alert_list"),
    path("innovations/trends/<uuid:pk>/", innovations.trend_alert_detail, name="trend_alert_detail"),
    path("innovations/recycle/", innovations.recycle_list, name="recycle_list"),
    path("innovations/recycle/<uuid:pk>/", innovations.recycle_detail, name="recycle_detail"),
]
