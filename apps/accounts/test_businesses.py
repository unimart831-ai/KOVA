"""Registry of the 14 TEST_BUSINESSES pilot accounts (docs/TEST_BUSINESSES.md)."""

from __future__ import annotations

WAVE1_SLUGS = frozenset({"kawaida", "mara", "nyama"})

WA_REPLY_SLA_SECONDS = 3600  # 1 hour — money-chase target

TEST_BUSINESS_REGISTRY: list[dict] = [
    {"slug": "mara", "email": "mara@kovatest.local", "company_name": "Mara & Moto", "plan": "agency", "wave": 1},
    {"slug": "pixelcraft", "email": "kai@pixelcraftstudios.com", "company_name": "PixelCraft Studios", "plan": "pro", "wave": None},
    {"slug": "elimu", "email": "team@elimuhub.co.ke", "company_name": "Elimu Hub", "plan": "growth", "wave": None},
    {"slug": "nyama", "email": "orders@nyamamamaexpress.co.ke", "company_name": "Nyama Mama Express", "plan": "pro", "wave": 1},
    {"slug": "cloudstack", "email": "founder@cloudstackafrica.com", "company_name": "CloudStack Africa", "plan": "agency", "wave": None},
    {"slug": "makao", "email": "sales@makaohomes.co.ke", "company_name": "Makao Homes", "plan": "pro", "wave": None},
    {"slug": "amara", "email": "coach@amarafit.co.ke", "company_name": "Coach Amara Fitness", "plan": "starter", "wave": None},
    {"slug": "greenroots", "email": "info@greenrootsfoundation.org", "company_name": "Green Roots Foundation", "plan": "growth", "wave": None},
    {"slug": "neonwave", "email": "kai@neonwave.agency", "company_name": "Neon Wave Agency", "plan": "agency", "wave": None},
    {"slug": "pesapal", "email": "team@pesapalfinance.co.ke", "company_name": "PesaPal Finance", "plan": "growth", "wave": None},
    {"slug": "kakuma", "email": "orders@kakumawholesale.co.ke", "company_name": "Kakuma Wholesale", "plan": "pro", "wave": None},
    {"slug": "kawaida", "email": "bookings@kawaidabeauty.co.ke", "company_name": "Kawaida Hair & Beauty", "plan": "growth", "wave": 1},
    {"slug": "bridge", "email": "hello@bridgeacademy.co.ke", "company_name": "Bridge Academy", "plan": "growth", "wave": None},
    {"slug": "django", "email": "hello@djangosasa.co.ke", "company_name": "Django Sasa", "plan": "growth", "wave": None},
]

TEST_BUSINESS_EMAILS = [b["email"] for b in TEST_BUSINESS_REGISTRY]
TEST_BUSINESS_SLUGS = [b["slug"] for b in TEST_BUSINESS_REGISTRY]
REGISTRY_BY_SLUG = {b["slug"]: b for b in TEST_BUSINESS_REGISTRY}
REGISTRY_BY_EMAIL = {b["email"]: b for b in TEST_BUSINESS_REGISTRY}
