"""Views that render static legal and policy pages."""

from __future__ import annotations

from typing import TypedDict

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render


class LegalPage(TypedDict):
    template: str
    page_title: str
    page_subtitle: str


LEGAL_PAGES: dict[str, LegalPage] = {
    "privacy": {
        "template": "legal/privacy.html",
        "page_title": "Privacy Policy",
        "page_subtitle": "Last updated: April 9, 2026",
    },
    "terms": {
        "template": "legal/terms.html",
        "page_title": "Terms & Conditions",
        "page_subtitle": "Last updated: April 9, 2026",
    },
    "cookies": {
        "template": "legal/cookies.html",
        "page_title": "Cookie Policy",
        "page_subtitle": "Last updated: April 9, 2026",
    },
    "acceptable-use": {
        "template": "legal/acceptable_use.html",
        "page_title": "Acceptable Use Policy",
        "page_subtitle": "Last updated: April 9, 2026",
    },
    "dpa": {
        "template": "legal/dpa.html",
        "page_title": "Data Processing Agreement",
        "page_subtitle": "Last updated: April 9, 2026",
    },
}


def legal(request: HttpRequest, name: str) -> HttpResponse:
    """
    Render a static legal page for the given policy name.
    """
    page = LEGAL_PAGES.get(name)
    if page is None:
        raise Http404("Unknown legal page.")
    return render(
        request,
        page["template"],
        {
            "page_title": page["page_title"],
            "page_subtitle": page["page_subtitle"],
        },
    )
