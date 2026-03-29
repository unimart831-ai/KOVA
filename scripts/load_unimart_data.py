"""
Load Unimart Africa test data into the database.
Run: python scripts/load_unimart_data.py
"""
import os, sys, django, json
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile
from apps.platforms.models import SocialAccount
from apps.agents.models import AgentConfig
from apps.content.models import ContentSeed, Post

User = get_user_model()
user = User.objects.get(email='admin@kova.ai')
now = timezone.now()

# ─── 1. UPDATE USER ─────────────────────────────────────────────────────────
user.full_name = 'Unimart Africa'
user.onboarding_completed = True
user.save()
print('[OK] User updated')

# ─── 2. SET UP BRAND PROFILE ────────────────────────────────────────────────
profile, _ = UserProfile.objects.get_or_create(user=user)
profile.company_name = 'Unimart Africa'
profile.industry = 'ecommerce'
profile.website_url = 'https://unimartafrica.com'
profile.brand_voice = (
    'Young, vibrant, and relatable. We speak like a smart friend who gets campus life. '
    'We use casual but respectful language, occasional slang (campus vibes, hustle, squad), '
    'and emojis. We champion student entrepreneurship, peer-to-peer commerce, and financial empowerment. '
    'Our tone is encouraging, slightly playful, and always inclusive. '
    'We mix English with occasional Swahili/Sheng phrases when targeting East African campuses.'
)
profile.brand_voice_examples = [
    'Your room is full of stuff you dont use anymore. Guess what? Someone on campus NEEDS it. List it on Unimart, make that money. 💰',
    'Finals week hustle is real 📚 but your side hustle doesnt have to stop. Keep your Unimart shop running 24/7 while you study.',
    'From lecture notes to laptops, hoodies to headphones — campus commerce just got an upgrade. Welcome to Unimart Africa. 🚀',
]
profile.target_audience = (
    'University students aged 18-26 across African campuses. Both sellers (student entrepreneurs, '
    'people decluttering, small-scale traders) and buyers (budget-conscious students looking for '
    'affordable goods and services within their campus ecosystem). Primary markets: Kenya, Nigeria, '
    'South Africa, Ghana, Tanzania. Tech-savvy, mobile-first, active on Twitter/X, Instagram, TikTok.'
)
profile.content_pillars = [
    'Student Entrepreneurship & Hustle Culture',
    'Campus Life & Relatable Moments',
    'Product Spotlights & Seller Success Stories',
    'Tips & Hacks (Saving Money, Side Hustles)',
    'Platform Features & How-To Guides',
    'Community & University Partnerships',
]
profile.goals = [
    'Grow brand awareness among university students',
    'Drive app downloads and seller signups',
    'Build a community of student entrepreneurs',
    'Increase marketplace transactions',
    'Establish Unimart as THE campus commerce platform in Africa',
]
profile.posting_frequency = 10
profile.save()
print('[OK] Brand profile set')

# ─── 3. ENSURE CONNECTED PLATFORMS ──────────────────────────────────────────
platforms_data = [
    ('twitter', 'unimart_twitter', 'UnimartAfrica', 'Unimart Africa'),
    ('linkedin', 'unimart_linkedin', 'unimart-africa', 'Unimart Africa'),
    ('instagram', 'unimart_instagram', 'unimartafrica', 'Unimart Africa'),
    ('tiktok', 'unimart_tiktok', 'unimartafrica', 'Unimart Africa'),
]
platform_accounts = {}
for plat, pid, uname, dname in platforms_data:
    acct, _ = SocialAccount.objects.get_or_create(
        user=user, platform=plat, platform_user_id=pid,
        defaults={'username': uname, 'display_name': dname, 'access_token': 'mock', 'is_active': True}
    )
    platform_accounts[plat] = acct
twitter = platform_accounts['twitter']
linkedin = platform_accounts['linkedin']
instagram = platform_accounts['instagram']
tiktok = platform_accounts['tiktok']
print(f'[OK] {SocialAccount.objects.filter(user=user, is_active=True).count()} platforms connected')

# ─── 4. ACTIVATE ALL AGENTS ─────────────────────────────────────────────────
for agent_type in ['research', 'create', 'adapt', 'engage', 'analyst', 'strategist']:
    a, _ = AgentConfig.objects.get_or_create(user=user, agent_type=agent_type, defaults={'is_active': True})
    if not a.is_active:
        a.is_active = True
        a.save()
print('[OK] All 6 agents activated')

# ─── 5. CLEAR OLD TEST DATA ─────────────────────────────────────────────────
Post.objects.filter(user=user).delete()
ContentSeed.objects.filter(user=user).delete()
print('[OK] Cleared old test data')

# =============================================================================
# SEED 1: Seller Recruitment
# =============================================================================
s1 = ContentSeed.objects.create(
    user=user, status='completed',
    idea='Encourage students to become sellers on Unimart — highlight how easy it is to list products and start earning',
    notes='Focus on zero listing fees, instant setup, and the fact that your customers are literally your classmates',
    target_platforms=['twitter', 'instagram', 'tiktok'],
)
Post.objects.create(
    user=user, seed=s1, social_account=twitter,
    content_text=(
        'You have stuff in your room collecting dust. Someone in your hostel literally wants it. 👀\n\n'
        'List it on Unimart in 60 seconds:\n'
        '📸 Snap a photo\n'
        '💰 Set your price\n'
        '✅ Get paid\n\n'
        'Zero listing fees. Your customers? Your classmates.\n\n'
        'Start selling today → unimartafrica.com\n\n'
        '#UnimartAfrica #CampusHustle #StudentEntrepreneur'
    ),
    content_type='original', status='approved', generated_by_agent='create',
    ai_reasoning='Twitter: concise, action-oriented, emoji bullet points for scanability. Zero fees is the hook. 3-step process removes friction objection.',
    predicted_engagement_score=8.4, scheduled_at=now + timedelta(hours=2),
)
Post.objects.create(
    user=user, seed=s1, social_account=instagram,
    content_text=(
        'Your dorm room is a goldmine and you dont even know it. 💎\n\n'
        'That textbook you finished? Someone needs it.\n'
        'That hoodie you never wear? Its someones grail.\n'
        'Those earphones still in the box? Easy money.\n\n'
        'Unimart connects you with buyers on YOUR campus. No shipping stress, no strangers — '
        'just classmates buying from classmates.\n\n'
        'List your first item in 60 seconds. Link in bio. 🔗\n\n'
        '#UnimartAfrica #SellOnCampus #StudentHustle #CampusLife #AfricanStudents #SideHustle'
    ),
    content_type='original', status='pending_approval', generated_by_agent='create',
    ai_reasoning='Instagram: storytelling format, relatable scenarios students can picture themselves in. Heavy hashtags for explore page.',
    predicted_engagement_score=7.9,
)
Post.objects.create(
    user=user, seed=s1, social_account=tiktok,
    content_text=(
        'POV: You just made KES 2,000 selling old textbooks on Unimart and you didnt even leave your room 🤑\n\n'
        'Your classmates are your customers.\n'
        'Your dorm is your warehouse.\n'
        'Your phone is your shop.\n\n'
        'Download Unimart. Start selling. Get paid.\n\n'
        'Its giving ✨ student entrepreneur energy ✨\n\n'
        '#UnimartAfrica #CampusHustle #StudentLife #MakeMoneyOnline #SideHustle #UniTok'
    ),
    content_type='original', status='pending_approval', generated_by_agent='create',
    ai_reasoning='TikTok: POV hook trending on platform, Gen-Z language (its giving), campus-specific money reference (KES), casual tone.',
    predicted_engagement_score=8.7,
)
print('[OK] Seed 1: Seller recruitment (3 posts)')

# =============================================================================
# SEED 2: Budget Shopping
# =============================================================================
s2 = ContentSeed.objects.create(
    user=user, status='completed',
    idea='Position Unimart as the go-to for budget-conscious students — secondhand deals, affordable finds, no delivery fees on campus',
    notes='Emphasize savings vs retail, the convenience of buying from someone on the same campus',
    target_platforms=['twitter', 'linkedin'],
)
Post.objects.create(
    user=user, seed=s2, social_account=twitter,
    content_text=(
        'Broke but need a laptop for assignments? 💻\n\n'
        'Unimart has verified student sellers on YOUR campus with laptops from KES 15K.\n\n'
        'No sketchy online deals. No delivery fees. Meet your seller at the library.\n\n'
        'Student-to-student commerce, the way it should be.\n\n'
        '→ unimartafrica.com\n\n'
        '#UnimartAfrica #StudentDeals #CampusShopping'
    ),
    content_type='original', status='approved', generated_by_agent='create',
    ai_reasoning='Twitter: opens with relatable pain point (broke student), specific price creates urgency, trust angle (meet at library).',
    predicted_engagement_score=8.1, scheduled_at=now + timedelta(days=1, hours=10),
)
Post.objects.create(
    user=user, seed=s2, social_account=linkedin,
    content_text=(
        'The average African university student spends 40% more than necessary on textbooks, '
        'electronics, and supplies — simply because they dont have access to affordable, '
        'trusted alternatives nearby.\n\n'
        'Unimart Africa is changing that.\n\n'
        'We built a hyperlocal marketplace that connects student buyers with student sellers '
        'on the same campus. The result:\n\n'
        '📚 Textbooks at 50-70% below retail\n'
        '💻 Electronics verified by peer sellers you can meet in person\n'
        '🚫 Zero delivery fees (your seller is in the next hostel)\n'
        '♻️ A circular economy that keeps money within the student community\n\n'
        'Were not just building an app. Were building the infrastructure for campus commerce across Africa.\n\n'
        'Currently live at 3 universities. Expanding to 15 by end of 2026.\n\n'
        '#EdTech #Ecommerce #AfricanStartups #StudentEntrepreneurship #UnimartAfrica'
    ),
    content_type='original', status='approved', generated_by_agent='create',
    ai_reasoning='LinkedIn: data-driven opening for professional audience, bullet points, expansion roadmap signals ambition to investors/partners.',
    predicted_engagement_score=7.6, scheduled_at=now + timedelta(days=1, hours=14),
)
print('[OK] Seed 2: Budget shopping (2 posts)')

# =============================================================================
# SEED 3: Seller Success Story (Amara)
# =============================================================================
s3 = ContentSeed.objects.create(
    user=user, status='completed',
    idea='Share a seller success story — a student who started selling snacks on Unimart and now makes consistent side income',
    notes='Make it feel real and inspirational. Show the journey from first sale to regular income.',
    target_platforms=['twitter', 'instagram'],
)
Post.objects.create(
    user=user, seed=s3, social_account=twitter,
    content_text=(
        'Meet Amara. 2nd year, UoN. 🎓\n\n'
        'She started selling homemade samosas on Unimart 3 months ago "as a joke."\n\n'
        'Month 1: KES 3,200\n'
        'Month 2: KES 8,700\n'
        'Month 3: KES 14,500\n\n'
        'She now supplies 3 hostels and hired a friend to help with deliveries. 📈\n\n'
        'Your campus hustle is waiting. What are you selling?\n\n'
        '#UnimartAfrica #StudentSuccess #CampusEntrepreneur'
    ),
    content_type='original', status='published', generated_by_agent='create',
    ai_reasoning='Twitter: storytelling with specific numbers builds credibility. Progressive revenue shows growth. Ends with CTA question for engagement.',
    predicted_engagement_score=9.1, published_at=now - timedelta(days=2),
    platform_post_url='https://twitter.com/UnimartAfrica/status/123456789',
)
Post.objects.create(
    user=user, seed=s3, social_account=instagram,
    content_text=(
        '🔥 FROM JOKE TO BUSINESS: How Amara turned samosas into a campus empire.\n\n'
        'Amara is a 2nd year student at University of Nairobi. Three months ago, she listed '
        'homemade samosas on Unimart "just to see what would happen."\n\n'
        'Week 1: 12 orders from her own hostel.\n'
        'Month 1: KES 3,200 and a growing reputation.\n'
        'Month 2: Students from OTHER hostels started ordering. Revenue: KES 8,700.\n'
        'Month 3: KES 14,500. She hired a friend. She supplies 3 hostels.\n\n'
        'Amara didnt need a business plan. She didnt need startup capital. She needed a platform '
        'that connects her with hungry students 200 meters away.\n\n'
        'Thats Unimart. 🚀\n\n'
        'Whats YOUR campus hustle? Drop it in the comments 👇\n\n'
        '#UnimartAfrica #StudentEntrepreneur #CampusHustle #AfricanYouth #SellerStory #NairobiStudents #UoN'
    ),
    content_type='original', status='published', generated_by_agent='create',
    ai_reasoning='Instagram: carousel-style storytelling, specific numbers, local university reference, engagement CTA asking for comments.',
    predicted_engagement_score=8.8, published_at=now - timedelta(days=2, hours=3),
    platform_post_url='https://instagram.com/p/unimart_amara_story',
)
print('[OK] Seed 3: Seller success story (2 posts)')

# =============================================================================
# SEED 4: Back to School Campaign
# =============================================================================
s4 = ContentSeed.objects.create(
    user=user, status='completed',
    idea='Back to school campaign — students returning to campus need supplies, textbooks, dorm essentials. Position Unimart as their first stop.',
    notes='Time-sensitive urgency. Semester starts next week vibe. Tap into the excitement of coming back to campus.',
    target_platforms=['twitter', 'instagram', 'tiktok', 'linkedin'],
)
Post.objects.create(
    user=user, seed=s4, social_account=twitter,
    content_text=(
        'Semester starts Monday. Your checklist: ✅\n\n'
        '📚 Textbooks (50% off retail on Unimart)\n'
        '☕ Kettle (KES 800 from a 4th year whos graduating)\n'
        '🔌 Extension cable (literally everyone is selling one)\n'
        '📝 Lecture notes from last semesters top student\n\n'
        'Everything you need. From students whove been there.\n\n'
        'Shop now → unimartafrica.com\n\n'
        '#BackToSchool #UnimartAfrica #CampusReady'
    ),
    content_type='original', status='draft', generated_by_agent='create',
    ai_reasoning='Twitter: checklist format is highly shareable, specific items + prices, humor (extension cable line), urgency from semester start.',
    predicted_engagement_score=8.3,
)
Post.objects.create(
    user=user, seed=s4, social_account=instagram,
    content_text=(
        '📋 CAMPUS ESSENTIALS CHECKLIST (save this post!)\n\n'
        'Semester is about to start and we know the drill — you need stuff but your account balance '
        'is giving struggle. 😅\n\n'
        'Good news: Unimart has everything you need, sold by students on your campus at STUDENT prices.\n\n'
        '📚 Textbooks — Why pay retail when a 3rd year is selling the same book for half price?\n'
        '💻 Electronics — Laptops, earphones, chargers. All verified sellers you can meet.\n'
        '🏠 Dorm Essentials — Kettles, hangers, storage boxes, bedding.\n'
        '👕 Fashion — Thrift finds, sneakers, hoodies perfect for cold lecture halls.\n'
        '🍕 Food & Snacks — Yes, we have campus chefs and snack sellers too.\n\n'
        'Stop overpaying. Start shopping smart. 🧠\n\n'
        'Link in bio to browse whats available on YOUR campus.\n\n'
        '#UnimartAfrica #BackToSchool #CampusLife #StudentBudget #AfricanStudents #UniEssentials'
    ),
    content_type='original', status='pending_approval', generated_by_agent='create',
    ai_reasoning='Instagram: save-worthy list post (drives saves metric), category breakdown for broad appeal, casual tone with financial empathy.',
    predicted_engagement_score=8.0,
)
Post.objects.create(
    user=user, seed=s4, social_account=tiktok,
    content_text=(
        'Things I bought on Unimart for under KES 5,000 that saved my semester: 🎒\n\n'
        '1. Second-hand laptop charger — KES 500 (retail is 2K, be serious 😂)\n'
        '2. Last semesters textbooks — KES 1,200 for 3 books\n'
        '3. A functioning kettle from a graduating student — KES 800\n'
        '4. Lecture notes from someone who got an A — KES 200 (best investment ever)\n'
        '5. A hoodie that goes with everything — KES 700\n\n'
        'Total: KES 3,400. Saved over KES 12,000. 📉💸\n\n'
        'Unimart Africa. Your campus. Your marketplace.\n\n'
        '#UnimartAfrica #BackToSchool #StudentHacks #BudgetShopping #CampusLife #UniTok'
    ),
    content_type='original', status='pending_approval', generated_by_agent='create',
    ai_reasoning='TikTok: listicle format trending, specific prices add believability, parenthetical commentary adds personality, savings total is payoff.',
    predicted_engagement_score=9.0,
)
Post.objects.create(
    user=user, seed=s4, social_account=linkedin,
    content_text=(
        'Every semester, millions of African university students face the same problem: '
        'they need essentials but cant afford retail prices.\n\n'
        'Textbooks alone can cost a student KES 15,000-25,000 per semester. Most of these books '
        'are used for one semester and then collect dust.\n\n'
        'Unimart Africa created a simple solution: a campus marketplace where students sell to students.\n\n'
        'Our back-to-school data from the last 3 semesters:\n'
        '• Average buyer saves 47% vs retail prices\n'
        '• 89% of transactions happen within 24 hours\n'
        '• Average seller earns KES 4,200/month in side income\n'
        '• 73% of sellers are first-time entrepreneurs\n\n'
        'Were not just saving students money. Were creating a generation of student entrepreneurs '
        'who learn commerce by doing it.\n\n'
        'Back-to-school season is our Super Bowl. This semester, were live at 3 new campuses.\n\n'
        '#Ecommerce #AfricanStartups #EdTech #CircularEconomy #UnimartAfrica'
    ),
    content_type='original', status='scheduled', generated_by_agent='create',
    ai_reasoning='LinkedIn: data-heavy for professional audience, vision framing (entrepreneurs not just buyers), Super Bowl analogy for impact.',
    predicted_engagement_score=7.8, scheduled_at=now + timedelta(days=3, hours=9),
)
print('[OK] Seed 4: Back to school (4 posts)')

# =============================================================================
# SEED 5: Safety & Trust
# =============================================================================
s5 = ContentSeed.objects.create(
    user=user, status='completed',
    idea='Address safety concerns — explain how Unimart verifies student sellers, enables safe campus meetups, and protects buyers',
    notes='Important for parent audience too. Build trust. Mention student ID verification, campus-only transactions, ratings system.',
    target_platforms=['twitter', 'linkedin'],
)
Post.objects.create(
    user=user, seed=s5, social_account=twitter,
    content_text=(
        '"Is it safe to buy from strangers on campus?"\n\n'
        'On Unimart, theyre not strangers. 🤝\n\n'
        '✅ Every seller verified with student ID\n'
        '📍 All transactions happen on campus\n'
        '⭐ Buyer reviews are public\n'
        '🛡️ Dispute resolution built in\n\n'
        'We built Unimart so your parents dont have to worry — and neither do you.\n\n'
        '#UnimartAfrica #SafeCommerce #CampusTrust'
    ),
    content_type='original', status='approved', generated_by_agent='create',
    ai_reasoning='Twitter: opens with the objection directly (builds trust), emoji bullet-point features, emotional close mentioning parents.',
    predicted_engagement_score=7.4, scheduled_at=now + timedelta(days=2, hours=11),
)
Post.objects.create(
    user=user, seed=s5, social_account=linkedin,
    content_text=(
        'Trust is the #1 barrier to peer-to-peer commerce in emerging markets.\n\n'
        'When we launched Unimart Africa, the first question from every university administration was: '
        '"How do you ensure student safety?"\n\n'
        'Heres what we built:\n\n'
        '🔐 Identity Verification — Every seller must verify with a valid student ID. No students, no selling.\n\n'
        '📍 Campus-Only Transactions — Buyers and sellers must be at the same university. '
        'No shipping to unknown locations — your seller is in the next building.\n\n'
        '⭐ Rating System — Every transaction is rated. Low-rated sellers get flagged and reviewed.\n\n'
        '💳 Secure Payments — Money is held in escrow until the buyer confirms receipt. No pay-and-pray.\n\n'
        '🤝 Dispute Resolution — Our student ambassador team at each campus handles disputes within 48 hours.\n\n'
        'The result: Less than 0.3% dispute rate across 12,000+ transactions.\n\n'
        'Trust isnt a feature. Its the foundation.\n\n'
        '#UnimartAfrica #TrustAndSafety #Ecommerce #AfricanStartups #PeerToPeer'
    ),
    content_type='original', status='rejected', generated_by_agent='create',
    ai_reasoning='LinkedIn: authority-building for investors/partners, numbered safety features, hard metric (0.3% dispute rate). Rejected because tone too formal for our brand.',
    predicted_engagement_score=7.2,
)
print('[OK] Seed 5: Safety & trust (2 posts)')

# =============================================================================
# SEED 6: Meme — Types of Sellers (NEW — ready for AI generation)
# =============================================================================
s6 = ContentSeed.objects.create(
    user=user, status='new',
    idea='Create a fun meme-style post about the types of sellers you find on Unimart — the snack dealer, the textbook plug, the thrift king, the tech guy, the baked goods queen',
    notes='Keep it super relatable and funny. The kind of post students screenshot and share in WhatsApp groups. Add personality to each type.',
    target_platforms=['twitter', 'instagram', 'tiktok'],
)
print('[OK] Seed 6: Meme types of sellers (ready for AI generation)')

# =============================================================================
# SEED 7: University Expansion Announcement (NEW — ready for AI generation)
# =============================================================================
s7 = ContentSeed.objects.create(
    user=user, status='new',
    idea='Announce Unimart Africa expansion to 5 new universities across Nigeria and Kenya — LASU, Covenant, KU, Moi, JKUAT',
    notes='Big announcement energy. Tag the universities. Make students at those campuses excited to sign up. Include early seller incentives.',
    target_platforms=['twitter', 'linkedin', 'instagram'],
)
print('[OK] Seed 7: University expansion announcement (ready for AI generation)')

# =============================================================================
# SUMMARY
# =============================================================================
total_seeds = ContentSeed.objects.filter(user=user).count()
total_posts = Post.objects.filter(user=user).count()
by_status = {}
for p in Post.objects.filter(user=user):
    by_status[p.status] = by_status.get(p.status, 0) + 1

completed_seeds = ContentSeed.objects.filter(user=user, status='completed').count()
new_seeds = ContentSeed.objects.filter(user=user, status='new').count()

print('')
print('=' * 50)
print('  UNIMART AFRICA TEST DATA LOADED')
print('=' * 50)
print(f'  Seeds:     {total_seeds} ({completed_seeds} completed, {new_seeds} ready for AI)')
print(f'  Posts:     {total_posts}')
for status, count in sorted(by_status.items()):
    print(f'    {status}: {count}')
print(f'  Platforms: {SocialAccount.objects.filter(user=user, is_active=True).count()}')
print(f'  Agents:    {AgentConfig.objects.filter(user=user, is_active=True).count()} active')
print('=' * 50)
