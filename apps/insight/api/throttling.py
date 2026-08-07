"""
Plan-based API throttling — different rate limits per subscription tier.

Starter/Growth users shouldn't access the API at all (handled by HasAPIAccess permission),
but as a defense-in-depth measure, this throttle also differentiates Pro vs Agency.
"""

from rest_framework.throttling import UserRateThrottle


class PlanBasedThrottle(UserRateThrottle):
    """
    Throttle API requests based on the user's subscription plan.

    Pro:    200 requests/minute
    Agency: 600 requests/minute
    Others: 30 requests/minute (fallback — they shouldn't reach this)
    """

    # Rate table: plan_tier → "requests/period"
    PLAN_RATES = {
        "pro": "200/minute",
        "agency": "600/minute",
    }
    DEFAULT_RATE = "30/minute"

    def get_rate(self):
        request = getattr(self, "request", None)
        if request and request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile:
                return self.PLAN_RATES.get(profile.plan, self.DEFAULT_RATE)
        return self.DEFAULT_RATE

    def allow_request(self, request, view):
        # Store request so get_rate() can access it
        self.request = request
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
