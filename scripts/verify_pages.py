import os, sys, django
sys.path.insert(0, r'A:\SYSTEMS_2026\SOCIAL_FUTURE\kova_agent')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
User = get_user_model()
c = Client()
user = User.objects.get(email='admin@kova.ai')
c.force_login(user)

pages = [
    ('/content/studio/', 'Studio'),
    ('/content/queue/', 'Queue'),
    ('/content/calendar/', 'Calendar'),
    ('/agents/', 'Agents'),
    ('/platforms/', 'Platforms'),
]
for url, name in pages:
    r = c.get(url, follow=True)
    size = len(r.content)
    print(f'[{r.status_code}] {name:12} ({size:,} bytes)')

# Spot checks
r = c.get('/content/studio/')
html = r.content.decode()
has_unimart = 'Unimart' in html or 'campus' in html
has_approve = 'Approve' in html or 'approve' in html
print(f'  Studio has Unimart content: {has_unimart}')
print(f'  Studio has approve buttons: {has_approve}')

r = c.get('/content/queue/')
html = r.content.decode()
has_queued = 'Unimart' in html or 'campus' in html
print(f'  Queue has posts: {has_queued}')

r = c.get('/content/calendar/')
html = r.content.decode()
has_scheduled = len(html) > 11000
print(f'  Calendar has scheduled content: {has_scheduled} ({len(html)} bytes)')
