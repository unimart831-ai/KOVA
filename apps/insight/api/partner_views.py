"""
Marketplace Partner API endpoints.

All endpoints require X-Kova-Partner-Key authentication.
Operations are scoped to the authenticated marketplace partner.

Endpoints:
    GET  /api/v1/partner/info/                              → marketplace info
    POST /api/v1/partner/sellers/                            → provision seller
    POST /api/v1/partner/sellers/bulk/                       → bulk provision sellers
    GET  /api/v1/partner/sellers/                            → list sellers
    GET  /api/v1/partner/sellers/<external_id>/              → seller detail
    POST /api/v1/partner/sellers/<external_id>/suspend/      → suspend seller
    POST /api/v1/partner/sellers/<external_id>/activate/     → reactivate seller
    POST /api/v1/partner/sellers/<external_id>/products/sync/ → sync products
    GET  /api/v1/partner/stats/                              → aggregate stats
"""

from django.db import models
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.partners.seller_provisioning import (
    provision_marketplace_seller,
    provision_result_to_response,
)
from apps.commerce.products.models import Product, ProductCategory

from .partner_auth import MarketplaceAPIKeyAuthentication, IsMarketplacePartner

from apps.core.partners.models import MarketplacePartner, MarketplaceSellerAccount


# ─── Helper: get marketplace from request ────────────────────────────────────

def _get_mp(request) -> MarketplacePartner:
    return request.user.marketplace_partner


def _get_seller_or_404(mp, external_seller_id):
    """Lookup seller by external_seller_id within the marketplace."""
    try:
        return mp.seller_accounts.select_related("user", "user__profile").get(
            external_seller_id=external_seller_id,
        )
    except MarketplaceSellerAccount.DoesNotExist:
        return None


# ─── Serializers ─────────────────────────────────────────────────────────────

class SellerProvisionSerializer(serializers.Serializer):
    """Validates seller provisioning data — fields vary by marketplace config."""
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=30, required=False)
    external_seller_id = serializers.CharField(max_length=255)
    full_name = serializers.CharField(max_length=200, required=False, default="")
    business_name = serializers.CharField(max_length=200, required=False, default="")
    business_url = serializers.URLField(required=False, default="")
    business_description = serializers.CharField(required=False, default="")
    location = serializers.CharField(max_length=200, required=False, default="")
    seller_metadata = serializers.DictField(required=False, default=dict)

    def validate(self, data):
        mp = self.context["marketplace"]
        identity = mp.seller_identity_field

        # Ensure the required identity field is present
        if identity == "email" and not data.get("email"):
            raise serializers.ValidationError(
                {"email": f"This marketplace uses email as seller identity — email is required."}
            )
        if identity == "phone" and not data.get("phone"):
            raise serializers.ValidationError(
                {"phone": f"This marketplace uses phone as seller identity — phone is required."}
            )
        # external_seller_id is always required (enforced by CharField)
        return data


class ProductSyncItemSerializer(serializers.Serializer):
    """Validates a single product in a sync payload."""
    external_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, default="")
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=5, required=False, default="")
    image_url = serializers.URLField(required=False, default="")
    product_url = serializers.URLField(required=False, default="")
    category = serializers.CharField(max_length=100, required=False, default="")
    offering_type = serializers.ChoiceField(
        choices=["product", "service", "digital"], required=False, default="product",
    )
    stock_status = serializers.ChoiceField(
        choices=["in_stock", "low_stock", "out_of_stock", "made_to_order", "unlimited"],
        required=False, default="in_stock",
    )
    quantity = serializers.IntegerField(required=False, allow_null=True, default=None)
    is_featured = serializers.BooleanField(required=False, default=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    additional_images = serializers.ListField(
        child=serializers.URLField(), required=False, default=list,
    )
    # Marketplace-specific product data (UNIMART: condition, old_price, variants, specs, etc.)
    condition = serializers.ChoiceField(
        choices=["new", "used", "refurbished", ""], required=False, default="",
        help_text="Product condition (new/used/refurbished) — stored in marketplace_metadata",
    )
    old_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None,
        help_text="Original price before discount — stored in marketplace_metadata",
    )
    vendor_net_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None,
        help_text="Vendor's net price before platform commission — stored in marketplace_metadata",
    )
    variants = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
        help_text='Product variants. E.g. [{"attribute": "Size", "value": "XL", "additional_price": 100}]',
    )
    specifications = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
        help_text='Product specs. E.g. [{"key": "Material", "value": "Cotton"}]',
    )
    campus_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
        help_text="Campus codes where product is available (UNIMART-style)",
    )
    # Catch-all for marketplace-specific fields
    extra = serializers.DictField(required=False, default=dict)


# ─── Auth classes shortcut ───────────────────────────────────────────────────

PARTNER_AUTH = [MarketplaceAPIKeyAuthentication]
PARTNER_PERM = [IsMarketplacePartner]


# ─── Marketplace Info ────────────────────────────────────────────────────────

class MarketplaceInfoView(APIView):
    """Return marketplace partner info + current stats."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request):
        mp = _get_mp(request)
        return Response({
            "name": mp.name,
            "slug": mp.slug,
            "seller_identity_field": mp.seller_identity_field,
            "seller_default_plan": mp.seller_default_plan,
            "max_sellers": mp.max_sellers,
            "active_sellers": mp.active_sellers_count,
            "total_sellers": mp.total_sellers_count,
            "total_products_synced": mp.total_products_synced,
            "billing_model": mp.billing_model,
            "enforce_marketplace_cta": mp.enforce_marketplace_cta,
            "auto_snap_on_sync": mp.auto_snap_on_sync,
            "product_field_mapping": mp.product_field_mapping,
            "settings": mp.settings,
            "is_sandbox": mp.is_sandbox,
        })


# ─── Seller Provisioning ────────────────────────────────────────────────────

class SellerListCreateView(APIView):
    """
    GET  — list all sellers provisioned by this marketplace
    POST — provision a new seller (creates Kova account if needed)
    """
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request):
        mp = _get_mp(request)
        status_filter = request.query_params.get("status", "").strip()

        sellers = mp.seller_accounts.select_related("user").all()
        if status_filter:
            sellers = sellers.filter(status=status_filter)

        data = []
        for s in sellers[:500]:
            data.append({
                "external_seller_id": s.external_seller_id,
                "email": s.user.email,
                "full_name": s.user.full_name,
                "business_name": s.business_name,
                "business_url": s.business_url,
                "status": s.status,
                "products_synced": s.products_synced,
                "content_generated": s.content_generated,
                "provisioned_at": s.provisioned_at.isoformat(),
                "activated_at": s.activated_at.isoformat() if s.activated_at else None,
                "last_product_sync": s.last_product_sync.isoformat() if s.last_product_sync else None,
                "seller_metadata": s.seller_metadata,
            })
        return Response({"sellers": data, "count": len(data)})

    def post(self, request):
        mp = _get_mp(request)

        if not mp.can_provision_sellers:
            return Response(
                {"error": f"Seller limit reached ({mp.max_sellers}). Contact Kova to increase."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sz = SellerProvisionSerializer(data=request.data, context={"marketplace": mp})
        if not sz.is_valid():
            return Response({"errors": sz.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = sz.validated_data
        result = provision_marketplace_seller(mp, data)
        if not result.ok and result.status == "limit_reached":
            return Response(
                {"error": result.error},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not result.ok:
            return Response(
                provision_result_to_response(result),
                status=result.http_status,
            )

        return Response(
            provision_result_to_response(result),
            status=result.http_status,
        )


class SellerBulkProvisionView(APIView):
    """
    POST — provision up to 100 sellers in one request.

    Body: { "sellers": [ { ...same fields as POST /sellers/... }, ... ] }
    """
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM
    MAX_BATCH = 100

    def post(self, request):
        mp = _get_mp(request)
        raw_sellers = request.data.get("sellers", [])

        if not isinstance(raw_sellers, list) or not raw_sellers:
            return Response(
                {"error": "Provide a 'sellers' array with at least one seller."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_sellers) > self.MAX_BATCH:
            return Response(
                {"error": f"Maximum {self.MAX_BATCH} sellers per bulk request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        summary = {
            "provisioned": 0,
            "already_exists": 0,
            "failed": 0,
        }

        for index, item in enumerate(raw_sellers):
            if not isinstance(item, dict):
                summary["failed"] += 1
                results.append({
                    "index": index,
                    "status": "validation_error",
                    "errors": {"non_field_errors": ["Each seller must be a JSON object."]},
                })
                continue

            sz = SellerProvisionSerializer(data=item, context={"marketplace": mp})
            if not sz.is_valid():
                summary["failed"] += 1
                results.append({
                    "index": index,
                    "external_seller_id": item.get("external_seller_id", ""),
                    "status": "validation_error",
                    "errors": sz.errors,
                })
                continue

            result = provision_marketplace_seller(mp, sz.validated_data)
            payload = provision_result_to_response(result)
            payload["index"] = index

            if result.ok:
                if result.status == "already_exists":
                    summary["already_exists"] += 1
                else:
                    summary["provisioned"] += 1
            else:
                summary["failed"] += 1

            results.append(payload)

        http_status = status.HTTP_201_CREATED if summary["provisioned"] else status.HTTP_200_OK
        if summary["failed"] and not summary["provisioned"] and not summary["already_exists"]:
            http_status = status.HTTP_400_BAD_REQUEST

        return Response({
            "summary": summary,
            "results": results,
        }, status=http_status)


# ─── Seller Detail / Actions ────────────────────────────────────────────────

class SellerDetailView(APIView):
    """Get seller details by marketplace external_seller_id."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request, external_seller_id):
        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)

        products = Product.objects.filter(
            user=seller.user, marketplace_partner=mp, is_active=True,
        ).values_list("external_id", "name", "offering_type", "stock_status")

        return Response({
            "external_seller_id": seller.external_seller_id,
            "email": seller.user.email,
            "full_name": seller.user.full_name,
            "status": seller.status,
            "plan": seller.user.profile.plan,
            "products_synced": seller.products_synced,
            "content_generated": seller.content_generated,
            "seller_metadata": seller.seller_metadata,
            "provisioned_at": seller.provisioned_at.isoformat(),
            "activated_at": seller.activated_at.isoformat() if seller.activated_at else None,
            "last_product_sync": seller.last_product_sync.isoformat() if seller.last_product_sync else None,
            "products": [
                {"external_id": eid, "name": n, "offering_type": ot, "stock_status": ss}
                for eid, n, ot, ss in products
            ],
        })


class SellerSuspendView(APIView):
    """Suspend a seller account (marketplace-initiated)."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def post(self, request, external_seller_id):
        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)
        seller.suspend()
        return Response({"status": "suspended", "external_seller_id": external_seller_id})


class SellerActivateView(APIView):
    """Reactivate a suspended seller account."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def post(self, request, external_seller_id):
        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)
        seller.activate()
        from apps.core.partners.seller_provisioning import on_seller_activated
        on_seller_activated(mp, seller, auto_activated=True, send_welcome=True)
        return Response({"status": "active", "external_seller_id": external_seller_id})


# ─── Product Sync ────────────────────────────────────────────────────────────

class ProductSyncView(APIView):
    """
    Sync products for a seller. Marketplace pushes product data, Kova
    creates or updates products in the seller's catalog.

    Supports marketplace-specific field mapping via product_field_mapping config.
    """
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def post(self, request, external_seller_id):
        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)

        if seller.status != MarketplaceSellerAccount.Status.ACTIVE:
            return Response(
                {"error": f"Seller is {seller.status}, not active. Activate first."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw_products = request.data.get("products", [])
        if not isinstance(raw_products, list) or not raw_products:
            return Response(
                {"error": "Provide a 'products' array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Apply field mapping (marketplace fields → Kova fields)
        mapped_products = [self._apply_field_mapping(mp, item) for item in raw_products]

        # Check per-seller product limit from marketplace settings
        max_per_seller = mp.get_setting("max_products_per_seller", 500)
        current_count = Product.objects.filter(
            user=seller.user, is_active=True,
        ).count()

        created = 0
        updated = 0
        errors = []
        synced_product_ids: list[str] = []

        for i, item_data in enumerate(mapped_products):
            sz = ProductSyncItemSerializer(data=item_data)
            if not sz.is_valid():
                errors.append({"index": i, "errors": sz.errors})
                continue

            data = sz.validated_data
            ext_id = data["external_id"]

            # Upsert: find by external_id + user, or create
            existing = Product.objects.filter(
                user=seller.user, external_id=ext_id,
            ).first()

            # ── Build marketplace_metadata from marketplace-specific fields ──
            meta = dict(data.get("extra", {}))
            if data.get("condition"):
                meta["condition"] = data["condition"]
            if data.get("old_price") is not None:
                meta["old_price"] = float(data["old_price"])
            if data.get("vendor_net_price") is not None:
                meta["vendor_net_price"] = float(data["vendor_net_price"])
            if data.get("variants"):
                meta["variants"] = data["variants"]
            if data.get("specifications"):
                meta["specifications"] = data["specifications"]
            if data.get("campus_codes"):
                meta["campus_codes"] = data["campus_codes"]

            # ── Build enriched description if marketplace opts in ──
            description = data["description"]
            if mp.enrich_descriptions and description:
                enrichment_parts = []
                if data.get("condition") and data["condition"] != "new":
                    enrichment_parts.append(f"Condition: {data['condition']}")
                if data.get("specifications"):
                    specs_str = ", ".join(
                        f"{s.get('key', '')}: {s.get('value', '')}"
                        for s in data["specifications"][:10]
                        if s.get("key") and s.get("value")
                    )
                    if specs_str:
                        enrichment_parts.append(f"Specs: {specs_str}")
                if data.get("variants"):
                    variant_str = ", ".join(
                        f"{v.get('attribute', '')}: {v.get('value', '')}"
                        for v in data["variants"][:10]
                        if v.get("attribute") and v.get("value")
                    )
                    if variant_str:
                        enrichment_parts.append(f"Available in: {variant_str}")
                if enrichment_parts:
                    description = description.rstrip() + "\n\n" + " | ".join(enrichment_parts)

            product_data = {
                "name": data["name"],
                "description": description,
                "offering_type": data["offering_type"],
                "stock_status": data["stock_status"],
                "is_featured": data["is_featured"],
                "tags": data["tags"],
                "source": Product.Source.MARKETPLACE,
                "marketplace_partner": mp,
                "marketplace_metadata": meta,
                "last_synced_at": timezone.now(),
                "currency": data["currency"] or mp.default_product_currency,
            }

            if data["price"] is not None:
                product_data["price"] = data["price"]
            if data["quantity"] is not None:
                product_data["quantity"] = data["quantity"]
            if data["product_url"]:
                product_data["product_url"] = data["product_url"]
            from apps.commerce.products.marketplace_sync import apply_sync_images_to_product_data

            apply_sync_images_to_product_data(product_data, data)

            saved_id = None
            if existing:
                for k, v in product_data.items():
                    setattr(existing, k, v)
                existing.save()
                existing.check_low_stock()
                existing.save(update_fields=["stock_status"])
                updated += 1
                saved_id = str(existing.pk)
            else:
                if current_count + created >= max_per_seller:
                    errors.append({"index": i, "error": f"Per-seller product limit ({max_per_seller}) reached."})
                    continue
                product = Product.objects.create(
                    user=seller.user,
                    external_id=ext_id,
                    **product_data,
                )
                product.check_low_stock()
                product.save(update_fields=["stock_status"])
                created += 1
                saved_id = str(product.pk)

            if saved_id:
                synced_product_ids.append(saved_id)

        # Update seller sync stats
        seller.products_synced = Product.objects.filter(
            user=seller.user, marketplace_partner=mp, is_active=True,
        ).count()
        seller.last_product_sync = timezone.now()
        seller.save(update_fields=["products_synced", "last_product_sync"])

        # Trigger Snap/Autopilot for synced products with images
        snap_triggered = False
        autopilot_queued = 0
        if mp.auto_snap_on_sync and synced_product_ids:
            from apps.commerce.products.marketplace_sync import trigger_marketplace_autopilot

            autopilot_queued = trigger_marketplace_autopilot(seller.user, mp, synced_product_ids)
            snap_triggered = autopilot_queued > 0

        if created or updated:
            from apps.core.partners.webhooks import notify_product_synced

            notify_product_synced(
                mp, seller,
                created=created, updated=updated,
                product_ids=synced_product_ids,
            )

        resp_status = status.HTTP_201_CREATED if (created or updated) else status.HTTP_400_BAD_REQUEST
        return Response({
            "created": created,
            "updated": updated,
            "errors": errors,
            "snap_triggered": snap_triggered,
            "autopilot_queued": autopilot_queued,
        }, status=resp_status)

    def _apply_field_mapping(self, mp, raw_item):
        """
        Apply marketplace-specific field mapping.

        If mp.product_field_mapping = {"title": "name", "sku": "external_id", "amount": "price"},
        then {"title": "iPhone", "sku": "123", "amount": 5000}
        becomes {"name": "iPhone", "external_id": "123", "price": 5000}.

        Unmapped fields pass through as-is (so marketplaces can send Kova-native fields directly).
        """
        mapping = mp.product_field_mapping
        if not mapping:
            return raw_item

        mapped = {}
        for key, value in raw_item.items():
            kova_field = mapping.get(key, key)  # Map or pass through
            mapped[kova_field] = value
        return mapped


# ─── Aggregate Stats ─────────────────────────────────────────────────────────

class MarketplaceStatsView(APIView):
    """Aggregate stats for this marketplace partner."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request):
        mp = _get_mp(request)
        from django.db.models import Count, Sum

        sellers = mp.seller_accounts.all()
        stats = sellers.aggregate(
            total=Count("id"),
            active=Count("id", filter=models.Q(status="active")),
            invited=Count("id", filter=models.Q(status="invited")),
            suspended=Count("id", filter=models.Q(status="suspended")),
            total_products=Sum("products_synced"),
            total_content=Sum("content_generated"),
        )

        products_by_status = (
            Product.objects.filter(marketplace_partner=mp, is_active=True)
            .values("stock_status")
            .annotate(count=Count("id"))
        )

        return Response({
            "marketplace": mp.name,
            "sellers": {
                "total": stats["total"] or 0,
                "active": stats["active"] or 0,
                "invited": stats["invited"] or 0,
                "suspended": stats["suspended"] or 0,
            },
            "products": {
                "total_synced": stats["total_products"] or 0,
                "by_stock_status": {row["stock_status"]: row["count"] for row in products_by_status},
            },
            "content_generated": stats["total_content"] or 0,
            "billing": {
                "model": mp.billing_model,
                "rate_per_seller_kes": float(mp.rate_per_seller_kes),
                "estimated_monthly_kes": float(mp.rate_per_seller_kes * (stats["active"] or 0))
                if mp.billing_model == "per_seller" else float(mp.flat_fee_kes),
            },
        })


class SellerContentView(APIView):
    """List generated/published content for a marketplace seller."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request, external_seller_id):
        from apps.create.content.models import Post

        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)

        status_filter = request.query_params.get("status", "").strip()
        posts = Post.objects.filter(user=seller.user).select_related("product").order_by("-created_at")
        if status_filter:
            posts = posts.filter(status=status_filter)

        limit = min(int(request.query_params.get("limit", 50)), 200)
        data = []
        for post in posts[:limit]:
            data.append({
                "post_id": str(post.pk),
                "status": post.status,
                "platform": post.platform or "",
                "content_preview": (post.content_text or "")[:160],
                "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "platform_post_url": post.platform_post_url or "",
                "product_id": str(post.product_id) if post.product_id else None,
                "external_product_id": post.product.external_id if post.product else "",
            })

        return Response({
            "external_seller_id": seller.external_seller_id,
            "count": len(data),
            "posts": data,
        })


class SellerAnalyticsView(APIView):
    """Basic content analytics for a marketplace seller."""
    authentication_classes = PARTNER_AUTH
    permission_classes = PARTNER_PERM

    def get(self, request, external_seller_id):
        from django.db.models import Count

        from apps.create.content.models import Post

        mp = _get_mp(request)
        seller = _get_seller_or_404(mp, external_seller_id)
        if not seller:
            return Response({"error": "Seller not found"}, status=status.HTTP_404_NOT_FOUND)

        posts = Post.objects.filter(user=seller.user)
        by_status = posts.values("status").annotate(count=Count("id"))
        by_platform = posts.filter(status=Post.Status.PUBLISHED).values("platform").annotate(count=Count("id"))

        return Response({
            "external_seller_id": seller.external_seller_id,
            "products_synced": seller.products_synced,
            "content_generated": seller.content_generated,
            "posts": {
                "total": posts.count(),
                "by_status": {row["status"]: row["count"] for row in by_status},
                "published_by_platform": {row["platform"]: row["count"] for row in by_platform if row["platform"]},
            },
        })
