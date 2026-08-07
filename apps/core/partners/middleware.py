class ReferralMiddleware:
    """
    Capture referral codes from ?ref=CODE query parameter and store in a cookie.
    This persists the referral attribution for 30 days across page visits.
    """

    COOKIE_NAME = "kova_ref"
    COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref_code = request.GET.get("ref", "").strip()
        response = self.get_response(request)

        # Store new referral code in cookie (don't overwrite existing)
        if ref_code and not request.COOKIES.get(self.COOKIE_NAME):
            response.set_cookie(
                self.COOKIE_NAME,
                ref_code,
                max_age=self.COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=not getattr(request, "is_insecure", True),
            )

        return response
