"""Billing-related exceptions raised across the app."""


class PlanLimitExceeded(Exception):
    """Raised when a user has hit a hard plan limit (token budget, post quota,
    image quota, etc.). Surfaced to the user as a friendly upgrade prompt
    rather than a 500 — callers are expected to catch this explicitly."""

    def __init__(self, message: str, *, limit_type: str = "", suggested_plan: str = ""):
        super().__init__(message)
        self.message = message
        self.limit_type = limit_type
        self.suggested_plan = suggested_plan
