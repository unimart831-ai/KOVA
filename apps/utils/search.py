"""
PostgreSQL full-text search utilities.

Provides weighted, ranked full-text search across any model with text fields.
Falls back to icontains for SQLite (development).
"""

from django.db import connection
from django.db.models import Q, Value, F, FloatField
from django.db.models.functions import Coalesce


def is_postgres():
    return connection.vendor == "postgresql"


def full_text_search(queryset, query, fields, weights=None):
    """
    Perform full-text search on a queryset.

    Args:
        queryset: Django QuerySet to search
        query: Search string from user
        fields: List of field names to search (e.g., ["name", "description"])
        weights: Optional dict mapping field names to PostgreSQL weights
                 ('A', 'B', 'C', 'D'). 'A' is highest priority.

    Returns:
        Filtered and ranked QuerySet (by relevance for Postgres,
        unranked for SQLite fallback).
    """
    if not query or not query.strip():
        return queryset.none()

    query = query.strip()

    if not is_postgres():
        q_filter = Q()
        for field in fields:
            q_filter |= Q(**{f"{field}__icontains": query})
        return queryset.filter(q_filter)

    from django.contrib.postgres.search import (
        SearchQuery,
        SearchRank,
        SearchVector,
    )

    if weights is None:
        weights = {}

    default_weight_order = ["A", "B", "C", "D"]
    vector = None
    for i, field in enumerate(fields):
        weight = weights.get(field, default_weight_order[min(i, 3)])
        field_vector = SearchVector(field, weight=weight)
        vector = field_vector if vector is None else vector + field_vector

    search_query = SearchQuery(query, search_type="websearch")

    return (
        queryset.annotate(
            search_rank=SearchRank(vector, search_query),
        )
        .filter(search_rank__gt=0.0)
        .order_by("-search_rank")
    )


def search_posts(user, query):
    """Search user's posts by content text."""
    from apps.content.models import Post

    return full_text_search(
        Post.objects.filter(user=user),
        query,
        fields=["content_text", "first_comment"],
        weights={"content_text": "A", "first_comment": "B"},
    ).select_related("social_account")


def search_products(user, query):
    """Search user's products by name and description."""
    from apps.products.models import Product

    return full_text_search(
        Product.objects.filter(user=user, is_active=True),
        query,
        fields=["name", "description"],
        weights={"name": "A", "description": "B"},
    ).select_related("category")


def search_leads(user, query):
    """Search user's leads by name, email, and notes."""
    from apps.leads.models import Lead

    return full_text_search(
        Lead.objects.filter(user=user),
        query,
        fields=["email", "first_name", "last_name", "notes"],
        weights={"email": "A", "first_name": "A", "last_name": "A", "notes": "C"},
    )


def search_help_articles(query):
    """Search published help articles."""
    from apps.help.models import Article

    return full_text_search(
        Article.objects.filter(status="published"),
        query,
        fields=["title", "excerpt", "content"],
        weights={"title": "A", "excerpt": "B", "content": "C"},
    )
