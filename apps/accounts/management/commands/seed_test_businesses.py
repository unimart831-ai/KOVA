"""Seed the 14 test businesses from docs/TEST_BUSINESSES.md.

Creates User + UserProfile (+ a handful of representative Products) for each
business so QA / staging can hit the dashboard, agents, and admin panels with
realistic data — without manually walking through the onboarding wizard 14
times.

Idempotent: re-run to update existing test users in place. Passwords are
re-set every run so testers can always log in with the documented default.

Usage:
    python manage.py seed_test_businesses
    python manage.py seed_test_businesses --complete-onboarding
    python manage.py seed_test_businesses --complete-onboarding --run-intelligence
    python manage.py seed_test_businesses --only kawaida,nyama
    python manage.py seed_test_businesses --skip-products
    python manage.py seed_test_businesses --password MyTestPass123!
    python manage.py seed_test_businesses --delete-existing
"""
from __future__ import annotations

from datetime import Decimal, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.industry_packs import apply_pack
from apps.accounts.models import User, UserProfile


# ── Test business data ──────────────────────────────────────────────────────
#
# Each entry has just enough to: (1) create a user + profile that the admin
# Onboarding Funnel can chart, (2) trigger the industry pack so Step 2 review
# fields populate, (3) optionally seed a few representative products.
#
# `path` indicates the onboarding path the business is meant to test (mirrors
# the TEST_AUTOMATION section in the doc). `complete_onboarding` flag is
# applied per-business when --complete-onboarding is passed.

BUSINESSES: list[dict] = [
    # ── 1. Mara & Moto — Agency, fashion, Magic Fill path ────────────
    {
        "slug": "mara",
        "email": "mara@kovatest.local",
        "phone": "0712345001",
        "full_name": "Mara Wanjiru",
        "company_name": "Mara & Moto",
        "industry": "fashion_beauty",
        "plan": "agency",
        "website_url": "https://maraandmoto.co.ke",
        "target_audience": "Urban Kenyan women 22-35, fashion-forward, mobile-first shoppers",
        "brand_voice": "Bold, confident, Nairobi street-style energy — like your stylish best friend who always knows what's trending.",
        "key_offerings": ["Ankara dresses", "Denim & outerwear", "Statement accessories"],
        "path": "magic",
        "products": [
            ("Ankara Midi Skirt", "2500"),
            ("Denim Crop Jacket", "3800"),
            ("Beaded Statement Necklace", "1200"),
        ],
    },
    # ── 2. PixelCraft Studios — Pro, agency, URL inference ───────────
    {
        "slug": "pixelcraft",
        "email": "kai@pixelcraftstudios.com",
        "phone": "0712345002",
        "full_name": "Kai Otieno",
        "company_name": "PixelCraft Studios",
        "industry": "agency",
        "plan": "pro",
        "website_url": "https://pixelcraftstudios.com",
        "target_audience": "Kenyan SMEs, startups, and established businesses needing websites and digital presence.",
        "brand_voice": "Expert but approachable — we simplify tech jargon. Senior developer explaining things at a coffee shop.",
        "key_offerings": ["Website design", "Mobile apps", "SEO & performance"],
        "path": "url",
        "products": [],
    },
    # ── 3. Elimu Hub — Growth, education, URL inference ──────────────
    {
        "slug": "elimu",
        "email": "team@elimuhub.co.ke",
        "phone": "0712345003",
        "full_name": "Achieng Otieno",
        "company_name": "Elimu Hub",
        "industry": "education",
        "plan": "growth",
        "website_url": "https://elimuhub.co.ke",
        "target_audience": "Kenyan university students and young professionals (18-28) learning digital skills.",
        "brand_voice": "Encouraging big-sibling energy — \"I've been where you are, here's the shortcut.\" Mixes English and Sheng naturally.",
        "key_offerings": ["Online courses", "Career mentoring", "Free learning resources"],
        "path": "url",
        "products": [],
    },
    # ── 4. Nyama Mama Express — Pro, food, Magic Fill path ───────────
    {
        "slug": "nyama",
        "email": "orders@nyamamamaexpress.co.ke",
        "phone": "0712345004",
        "full_name": "Mama Akinyi",
        "company_name": "Nyama Mama Express",
        "industry": "food_restaurant",
        "plan": "pro",
        "website_url": "https://nyamamamaexpress.co.ke",
        "target_audience": "Nairobi food lovers 20-40, office workers, weekend dinner crowd.",
        "brand_voice": "Warm, mouth-watering, proudly Kenyan — chef who loves what they cook and wants you to taste everything.",
        "key_offerings": ["Nyama choma", "Pilau & traditional dishes", "Office catering"],
        "path": "magic",
        "products": [
            ("Nyama Choma Platter (500g)", "1200"),
            ("Pilau Rice + Kachumbari", "450"),
            ("Chicken Tikka Wrap", "550"),
            ("Chapati Platter (4 pcs)", "200"),
        ],
    },
    # ── 5. CloudStack Africa — Agency, saas, URL inference ───────────
    {
        "slug": "cloudstack",
        "email": "founder@cloudstackafrica.com",
        "phone": "0712345005",
        "full_name": "Thabo Mensah",
        "company_name": "CloudStack Africa",
        "industry": "saas",
        "plan": "agency",
        "website_url": "https://cloudstackafrica.com",
        "target_audience": "CTOs, VP Engineering, DevOps leads at mid-to-large East African companies.",
        "brand_voice": "Authoritative thought leader — data-driven, zero fluff. Trusted CTO advisor who's seen every scaling challenge.",
        "key_offerings": ["Managed cloud infrastructure", "Migration services", "DevOps consulting"],
        "path": "url",
        "products": [],
    },
    # ── 6. Makao Homes — Pro, real estate, Magic Fill path ───────────
    {
        "slug": "makao",
        "email": "sales@makaohomes.co.ke",
        "phone": "0712345006",
        "full_name": "Catherine Njoroge",
        "company_name": "Makao Homes",
        "industry": "real_estate",
        "plan": "pro",
        "website_url": "https://makaohomes.co.ke",
        "target_audience": "Kenyan middle-class families and young professionals (28-45) looking to buy or rent.",
        "brand_voice": "Trustworthy guide through the biggest purchase of your life — knowledgeable, patient, never pushy.",
        "key_offerings": ["Property sales", "Rental listings", "Home buying education"],
        "path": "magic",
        "products": [],
    },
    # ── 7. Coach Amara Fitness — Starter, fitness, manual path ───────
    {
        "slug": "amara",
        "email": "coach@amarafit.co.ke",
        "phone": "0712345007",
        "full_name": "Amara Kimani",
        "company_name": "Coach Amara Fitness",
        "industry": "health",
        "plan": "starter",
        "website_url": "",
        "target_audience": "Kenyan women 25-40 who want to get fit but feel intimidated by gym culture.",
        "brand_voice": "Your hype-woman in the gym — energetic, relatable, body-positive. \"You showed up, that's already winning.\"",
        "key_offerings": ["1-on-1 coaching", "Group fitness program", "30-day home challenge"],
        "path": "manual",
        "products": [
            ("1-on-1 Coaching (Monthly)", "8000"),
            ("Group Fitness Program (6 weeks)", "3500"),
        ],
    },
    # ── 8. Green Roots Foundation — Growth, nonprofit, URL inference ─
    {
        "slug": "greenroots",
        "email": "info@greenrootsfoundation.org",
        "phone": "0712345008",
        "full_name": "Daniel Mutua",
        "company_name": "Green Roots Foundation",
        "industry": "nonprofit",
        "plan": "growth",
        "website_url": "https://greenrootsfoundation.org",
        "target_audience": "Environmentally conscious Kenyans 20-45, diaspora donors, corporate CSR teams, volunteers.",
        "brand_voice": "Passionate storyteller with data — \"Here's the problem, here's the proof, here's how YOU can help today.\"",
        "key_offerings": ["Tree planting programs", "Community workshops", "Donor partnerships"],
        "path": "url",
        "products": [],
    },
    # ── 9. Neon Wave Agency — Agency, agency, Magic Fill (all 10) ────
    {
        "slug": "neonwave",
        "email": "kai@neonwave.agency",
        "phone": "0712345009",
        "full_name": "Kai Mwangi",
        "company_name": "Neon Wave Agency",
        "industry": "agency",
        "plan": "agency",
        "website_url": "https://neonwave.agency",
        "target_audience": "Brands and businesses across East Africa looking for social media management and brand strategy.",
        "brand_voice": "Creative rebels with a strategy — bold, trend-setting, slightly irreverent. \"We don't follow trends, we set them.\"",
        "key_offerings": ["Social media management", "Brand strategy", "Content creation"],
        "path": "magic",
        "products": [],
    },
    # ── 10. PesaPal Finance — Growth, finance, URL inference ─────────
    {
        "slug": "pesapal",
        "email": "team@pesapalfinance.co.ke",
        "phone": "0712345010",
        "full_name": "Sharon Karimi",
        "company_name": "PesaPal Finance",
        "industry": "finance",
        "plan": "growth",
        "website_url": "https://pesapalfinance.co.ke",
        "target_audience": "Young Kenyan professionals 25-38 managing their first real income — saving, investing, M-Pesa power users.",
        "brand_voice": "The financially literate friend you wish you had — clear, trustworthy, makes money talk simple. Never condescending.",
        "key_offerings": ["Personal finance content", "Investment education", "Budgeting templates"],
        "path": "url",
        "products": [],
    },
    # ── 11. Kakuma Wholesale — Pro, wholesale, manual path ───────────
    {
        "slug": "kakuma",
        "email": "orders@kakumawholesale.co.ke",
        "phone": "0712345011",
        "full_name": "Said Mohamed",
        "company_name": "Kakuma Wholesale",
        "industry": "wholesale_retail",
        "plan": "pro",
        "website_url": "https://kakumawholesale.co.ke",
        "target_audience": "Small traders and shop owners in Kakuma Refugee Camp and Kalobeyei Settlement; bulk buyers across northern Kenya.",
        "brand_voice": "Straight-talking wholesaler — honest about quality, transparent on pricing, no hidden costs. Mixes English, Swahili, and basic French.",
        "key_offerings": ["Mtumba bales", "New shoes from Kamkunji", "Eastleigh wholesale stock"],
        "path": "manual",
        "products": [
            ("Mtumba Bale — Ladies Dresses (45kg)", "8500"),
            ("Mtumba Bale — Jeans Mixed (45kg)", "12000"),
            ("New Canvas Shoes (Kamkunji)", "350"),
        ],
    },
    # ── 12. Kawaida Hair & Beauty — Growth, salon, Magic Fill ────────
    #     The flagship persona from the seed proposal. Exercises every
    #     Tier 1/2 automation we shipped.
    {
        "slug": "kawaida",
        "email": "bookings@kawaidabeauty.co.ke",
        "phone": "0712345012",
        "full_name": "Wanjiku Mwenda",
        "company_name": "Kawaida Hair & Beauty",
        "industry": "salon_beauty",
        "plan": "growth",
        "website_url": "https://kawaidabeauty.co.ke",
        "target_audience": "Working women aged 22-40 in Eastlands, South B, Embakasi; busy professionals booking around work hours; brides-to-be.",
        "brand_voice": "Warm and confident — like the senior stylist you trust to know what works for your hair. Mixes English and Swahili naturally.",
        "key_offerings": ["Box braids & knotless", "Silk press & treatments", "Bridal hair & makeup"],
        "path": "magic",
        "products": [
            ("Box Braids (Medium)", "3500"),
            ("Knotless Braids (Long)", "5000"),
            ("Silk Press (Natural Hair)", "2500"),
            ("Bridal Hair & Makeup Package", "12000"),
        ],
    },
    # ── 13. Bridge Academy — Growth, education, manual (pre-launch) ──
    #     Ideation-stage EdTech. No website, no live socials, no products.
    #     Tests AI voice style transfer via brand_voice_examples — the
    #     primary mechanism Kova has for matching a distinctive voice.
    {
        "slug": "bridge",
        "email": "hello@bridgeacademy.co.ke",
        "phone": "0712345013",
        "full_name": "Brian Mokaya",
        "company_name": "Bridge Academy",
        "industry": "education",
        "plan": "growth",
        "website_url": "",  # ideation stage — no live site yet
        "target_audience": "Kenyans 18-30 disillusioned by traditional education; looking for practical skills that pay; many in towns with patchy internet.",
        "brand_voice": (
            "Direct, story-first, brutally honest with care. Mixes English with "
            "Swahili and Sheng naturally. Anti-credentialism, pro-action. Skills "
            "over grades. Every post grounded in a concrete Kenyan scene. Sharp "
            "aphorisms close each idea. Short paragraphs, lots of white space, "
            "single-sentence lines for emphasis."
        ),
        "key_offerings": [
            "Mission-based skill courses (30-90 days to first paying client)",
            "Peer learning network (learners teach learners)",
            "Digital learner profiles for global opportunities",
        ],
        "brand_voice_examples": [
            "You sat in a lecture hall for 4 years memorizing definitions. Bridge will teach you to land your first paying client in 30 days. The market does not grade on papers. It grades on what you ship.",
            "Peer learning is not a buzzword on our deck. It is how Mary in Eastleigh learned video editing — from another student in Embu she had never met. The teacher and the learner sharing one Zoom screen and a Canva project. That is the model.",
            "Your transcript says you got an A in microeconomics. Cool. Now show me what you have built. That is the only question the market is asking in 2026.",
            "Low bandwidth is not a problem to apologize for. It is a constraint to design around. Bridge runs on 2G. That is on purpose. Because the next great Kenyan freelancer is not in Kilimani. She is in Garissa. She is in Kakuma. She is in Marsabit. And Bridge meets her where she is.",
        ],
        "content_pillars": [
            "Peer learning in action (real learner-to-learner stories)",
            "Mission-based outcomes — receipts not theory",
            "Accessibility & low-bandwidth wins",
            "Digital learner profiles -> global opportunities",
            "Skills > credentials hot takes",
        ],
        "path": "manual",
        "products": [],
    },
    # ── 14. Django Sasa — Growth, education, manual (curriculum-driven) ─
    #     Sequential 30-day Django teaching account. Tests pillar
    #     discipline, email sequences as a curriculum backbone, cohort
    #     campaigns, and the "every post ends with Tomorrow we cover X"
    #     brand-mandated closer.
    {
        "slug": "django",
        "email": "hello@djangosasa.co.ke",
        "phone": "0712345014",
        "full_name": "Faith Nyokabi",
        "company_name": "Django Sasa",
        "industry": "education",
        "plan": "growth",
        "website_url": "",  # link-in-bio is the homepage at this stage
        "target_audience": (
            "Aspiring African developers 18-32 who want a sequenced path "
            "into Django backend work, not random YouTube tutorials. CS "
            "graduates who feel they cannot ship. Self-taught coders stuck "
            "at 'I built a to-do app, now what?'"
        ),
        "brand_voice": (
            "Senior dev who teaches like Elvis W. Direct, practical, shows "
            "code, no theory dumps. Every post grounded in a numbered day of "
            "a real curriculum. Every post ends with \"Tomorrow we cover X.\" "
            "That closing line is non-negotiable — it is what keeps followers "
            "on the track."
        ),
        "key_offerings": [
            "30-Day Django Track (free, delivered via email)",
            "Django Cohort Program (paid, live sessions + code review)",
            "1-on-1 Django code review",
        ],
        # Six pillars matching the six 5-day modules of the curriculum.
        # This discipline is what stops the AI from inventing random
        # Django tips. Every generated post must fit into one of these.
        "content_pillars": [
            "Foundations (Days 1-5) — install Django, project vs app, settings, runserver, virtualenv",
            "Models & ORM (Days 6-10) — define models, migrations, admin, querysets, relationships",
            "Views & URLs (Days 11-15) — function views, class views, URL routing, namespacing, redirects",
            "Templates (Days 16-20) — DTL, template inheritance, static files, filters, includes",
            "Forms & Auth (Days 21-25) — forms, model forms, validation, login/signup, permissions",
            "Ship It (Days 26-30) — testing, env vars, Postgres, deploy to Railway, post-deploy debugging",
        ],
        "brand_voice_examples": [
            (
                "Django Day 7. URLs and routing.\n\n"
                "Stop hardcoding /products/1/ into your templates. That's how your app breaks "
                "the day a designer changes a path.\n\n"
                "Name your URLs. path('products/<int:pk>/', detail, name='product_detail').\n\n"
                "Now in your templates: {% url 'product_detail' pk=product.id %}. Done.\n\n"
                "Tomorrow we cover URL namespacing — what happens when two apps both have a 'detail' view."
            ),
            (
                "Django Day 14. Template inheritance.\n\n"
                "If you are copying the same nav into every page you are doing it wrong. There is a "
                "reason Django teaches DRY.\n\n"
                "Make a base.html. Put your nav there. Then in product_list.html:\n"
                "{% extends 'base.html' %}{% block content %}…{% endblock %}.\n\n"
                "That is it.\n\n"
                "Tomorrow: static files. The reason your CSS keeps not loading."
            ),
            (
                "Django Day 22. Model forms.\n\n"
                "You are not supposed to write forms.CharField() for every field on your model. "
                "That is what ModelForm is for.\n\n"
                "Subclass it. Point at your model. Pick the fields. Django writes the form for you.\n\n"
                "class ProductForm(forms.ModelForm):\n"
                "    class Meta:\n"
                "        model = Product\n"
                "        fields = ['name', 'price', 'description']\n\n"
                "Tomorrow: validation. How to refuse a form before it ruins your data."
            ),
            (
                "Django Day 29. Deploy to Railway.\n\n"
                "Stop calling your app done because it works on localhost. localhost is not a market. "
                "Railway is.\n\n"
                "Push to GitHub. Connect repo to Railway. Add Postgres. Set DEBUG=False. Set ALLOWED_HOSTS. "
                "Hit deploy.\n\n"
                "If it crashes, read the logs. Do not panic. Logs always tell you what broke.\n\n"
                "Tomorrow we wrap the track with post-deploy debugging — the 5 errors every Django dev "
                "sees their first week in production."
            ),
        ],
        "path": "manual",
        "products": [],
    },
]


PLAN_TO_TIER = {
    "starter": UserProfile.PlanTier.STARTER,
    "growth": UserProfile.PlanTier.GROWTH,
    "pro": UserProfile.PlanTier.PRO,
    "agency": UserProfile.PlanTier.AGENCY,
}


class Command(BaseCommand):
    help = (
        "Seed the 14 test businesses from docs/TEST_BUSINESSES.md. "
        "Idempotent — re-run to update existing test users in place."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--complete-onboarding", action="store_true",
            help="Mark each seeded user as onboarding_completed=True (skip wizard).",
        )
        parser.add_argument(
            "--run-intelligence", action="store_true",
            help="With --complete-onboarding, fire the agency first-meeting intelligence "
                 "chain (research → seeds → content → brief). Default for agency-plan seeds.",
        )
        parser.add_argument(
            "--skip-products", action="store_true",
            help="Don't create the per-business sample product catalogue.",
        )
        parser.add_argument(
            "--only", default="",
            help="Comma-separated business slugs to seed (default: all 14). "
                 "E.g. --only kawaida,nyama,kakuma",
        )
        parser.add_argument(
            "--password", default="TestKova2026!",
            help="Password to set on every seeded user (default: TestKova2026!).",
        )
        parser.add_argument(
            "--delete-existing", action="store_true",
            help="Hard-delete any existing test user with the same email before "
                 "re-seeding. Use with care.",
        )

    def handle(self, *args, **options):
        only = {s.strip().lower() for s in options["only"].split(",") if s.strip()}
        password = options["password"]
        complete = options["complete_onboarding"]
        run_intelligence = options["run_intelligence"]
        skip_products = options["skip_products"]
        delete_existing = options["delete_existing"]

        targets = [b for b in BUSINESSES if not only or b["slug"] in only]
        if not targets:
            self.stdout.write(self.style.WARNING(f"No businesses matched --only={options['only']}"))
            return

        path_markers = {"magic": "path_choice_magic", "url": "path_choice_url", "manual": "path_choice_manual"}

        created_count = 0
        updated_count = 0
        product_count = 0

        for biz in targets:
            with transaction.atomic():
                user, was_created = self._create_or_update_user(
                    biz, password=password, delete_existing=delete_existing,
                )
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

                profile = self._populate_profile(user, biz)

                # Industry pack — same call the wizard makes on Step 1 save.
                # apply_pack is idempotent so it's safe on re-runs.
                apply_pack(profile, biz["industry"])

                # Record path-choice marker so the admin funnel shows the test
                # cohort lit up across all 3 paths.
                marker = path_markers.get(biz["path"])
                if marker:
                    profile.record_onboarding_step(marker)

                # Optionally fast-forward through the wizard.
                if complete:
                    self._complete_onboarding(
                        user, profile, biz,
                        run_intelligence=run_intelligence or biz["plan"] == "agency",
                    )

                if not skip_products and biz["products"]:
                    product_count += self._create_products(user, biz["products"])

            symbol = "+" if was_created else "~"
            self.stdout.write(
                f"  {symbol} {biz['slug']:11s}  {user.email:40s}  "
                f"plan={biz['plan']}  industry={biz['industry']}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done — {created_count} created, {updated_count} updated, "
            f"{product_count} products seeded."
        ))
        self.stdout.write(f"Default password: {password}")
        if complete:
            self.stdout.write(self.style.NOTICE(
                "All users marked onboarding_completed — they'll skip the wizard on next login."
            ))
            if run_intelligence:
                self.stdout.write(self.style.NOTICE(
                    "Agency intelligence chain queued for agency-plan seeds "
                    "(and any --run-intelligence targets)."
                ))
        else:
            self.stdout.write(
                "Users have NOT completed onboarding — they'll land on the path-choice screen "
                "and can walk through the new wizard."
            )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _create_or_update_user(self, biz: dict, *, password: str, delete_existing: bool):
        email = biz["email"]

        if delete_existing:
            User.all_objects.filter(email=email).delete()

        existing = User.objects.filter(email=email).first()
        if existing:
            existing.set_password(password)
            existing.full_name = biz["full_name"]
            existing.phone_number = biz["phone"]
            existing.timezone = "Africa/Nairobi"  # Smart-default mimicry
            existing.is_active = True
            existing.save()
            return existing, False

        user = User.objects.create_user(
            username=biz["slug"],
            email=email,
            password=password,
            full_name=biz["full_name"],
            phone_number=biz["phone"],
        )
        user.timezone = "Africa/Nairobi"
        user.save(update_fields=["timezone"])
        return user, True

    def _populate_profile(self, user, biz: dict) -> UserProfile:
        # The post_save signal already created the profile.
        profile = user.profile
        profile.company_name = biz["company_name"]
        profile.industry = biz["industry"]
        profile.plan = PLAN_TO_TIER[biz["plan"]]
        profile.website_url = biz["website_url"]
        profile.target_audience = biz["target_audience"]
        profile.brand_voice = biz["brand_voice"]
        profile.key_offerings = list(biz["key_offerings"])

        # Optional fields — only present on businesses that need them. Bridge
        # Academy uses brand_voice_examples to make AI match a distinctive
        # non-corporate voice, and content_pillars to override the
        # education-pack defaults with venture-specific themes.
        if biz.get("brand_voice_examples"):
            profile.brand_voice_examples = list(biz["brand_voice_examples"])
        if biz.get("content_pillars"):
            profile.content_pillars = list(biz["content_pillars"])

        # Smart-default mimicry from signup
        profile.country = "KE"
        profile.mpesa_phone = biz["phone"]

        if biz["plan"] == "agency":
            profile.is_agency_approved = True
            profile.subscription_status = "active"
            if not profile.current_period_end:
                profile.current_period_end = timezone.now() + timedelta(days=30)

        profile.save()
        return profile

    def _complete_onboarding(
        self, user, profile: UserProfile, biz: dict, *, run_intelligence: bool = False,
    ) -> None:
        """Fast-forward through the wizard — stamps every step marker and
        flips `onboarding_completed`. Optionally queues agency intelligence."""
        from apps.utils import fire_task

        for marker in (
            "step_1_completed",
            "step_2_completed",
            "step_3_completed",
            "step_4_completed",
        ):
            profile.record_onboarding_step(marker)
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])

        if run_intelligence:
            from apps.agents.onboarding_tasks import run_onboarding_intelligence

            profile.onboarding_intelligence_started_at = timezone.now()
            profile.save(update_fields=["onboarding_intelligence_started_at"])
            profile.record_onboarding_step("intelligence_started")
            fire_task(run_onboarding_intelligence, str(user.pk))

    def _create_products(self, user, products: list[tuple[str, str]]) -> int:
        """Create a small representative catalogue per business."""
        from apps.products.models import Product

        created = 0
        for name, price in products:
            obj, was_created = Product.objects.get_or_create(
                user=user,
                name=name,
                defaults={
                    "price": Decimal(price),
                    "currency": "KES",
                    "offering_type": (
                        Product.OfferingType.SERVICE
                        if user.username in {"amara", "kawaida"}
                        else Product.OfferingType.PRODUCT
                    ),
                },
            )
            if was_created:
                created += 1
        return created
