from django.urls import path

from apps.admin_dashboard.views import ab_tests, agents, analytics, billing, content, engage, logs, overview, partials, platforms, system, teams, users

app_name = "admin_dashboard"

urlpatterns = [
    # Overview
    path("", overview.overview, name="overview"),

    # Users
    path("users/", users.user_list, name="user_list"),
    path("users/export/", users.user_export_csv, name="user_export"),
    path("users/<uuid:pk>/", users.user_detail, name="user_detail"),
    path("users/<uuid:pk>/change-plan/", users.user_change_plan, name="user_change_plan"),
    path("users/<uuid:pk>/toggle-staff/", users.user_toggle_staff, name="user_toggle_staff"),

    # Content
    path("content/", content.content_overview, name="content_overview"),
    path("content/posts/", content.post_list, name="post_list"),
    path("content/posts/<uuid:pk>/", content.post_detail, name="post_detail_admin"),
    path("content/seeds/", content.seed_list, name="seed_list"),
    path("content/failed/", content.failed_content, name="failed_content"),

    # Agents
    path("agents/", agents.agent_overview, name="agent_overview"),
    path("agents/log/", agents.agent_log, name="agent_log"),
    path("agents/tokens/", agents.token_economics, name="token_economics"),

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

    # Teams
    path("teams/", teams.teams_overview, name="teams_overview"),
    path("teams/list/", teams.team_list, name="team_list"),
    path("teams/<uuid:pk>/", teams.team_detail, name="team_detail"),

    # A/B Tests
    path("ab-tests/", ab_tests.ab_tests_overview, name="ab_tests_overview"),
    path("ab-tests/list/", ab_tests.ab_test_list_admin, name="ab_test_list_admin"),
    path("ab-tests/<uuid:pk>/", ab_tests.ab_test_detail_admin, name="ab_test_detail_admin"),
]
