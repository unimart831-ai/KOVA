from django.urls import path

from apps.commerce.links.hub import views

# Keep app_name for template {% url 'kova_page:...' %} compatibility after fold into links.
app_name = "kova_page"

urlpatterns = [
    path("<slug:slug>/", views.page_view, name="page"),
    path("<slug:slug>/ask/", views.page_ask, name="ask"),
    path("<slug:slug>/contact/", views.page_contact, name="contact"),
]
