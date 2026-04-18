"""
Marketplace Partner API endpoints.

All endpoints require X-Kova-Partner-Key authentication.
Operations are scoped to the authenticated marketplace partner.

Endpoints:
    GET  /api/v1/partner/info/                              → marketplace info
    POST /api/v1/partner/sellers/                            → provision seller
    GET  /api/v1/partner/sellers/                            → list sellers
    GET  /api/v1/partner/sellers/<external_id>/              → seller detail
    POST /api/v1/partner/sellers/<external_id>/suspend/      → suspend seller
    POST /api/v1/partner/sellers/<external_id>/activate/     → reactivate seller
    POST /api/v1/partner/sellers/<external_id>/products/sync/ → sync products
    GET  /api/v1/partner/stats/                              → aggregate stats
"""

import secrets

from django.db import IntegrityError, models
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.products.models import Product, ProductCategory

from .partner_auth import MarketplaceAPIKeyAuthentication, IsMarketplacePartner

from apps.partners.models import MarketplacePartner, MarketplaceSellerAccount


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
        ext_id = data["external_seller_id"]

        # Check if seller already provisioned
        existing = mp.seller_accounts.filter(external_seller_id=ext_id).first()
        if existing:
            return Response({
                "status": "already_exists",
                "external_seller_id": ext_id,
                "email": existing.user.email,
                "seller_status": existing.status,
            }, status=status.HTTP_200_OK)

        # Find or create the Kova user
        identity_field = mp.seller_identity_field
        user = None

        if identity_field == "email" and data.get("email"):
            user = User.objects.filter(email__iexact=data["email"]).first()
            if not user:
                user = User.objects.create_user(
                    email=data["email"],
                    username=data["email"],
                    password=secrets.token_urlsafe(16),
                    full_name=data.get("full_name", ""),
                )
        elif identity_field == "phone" and data.get("phone"):
            user = User.objects.filter(phone_number=data["phone"]).first()
            if not user:
                # Phone-based marketplaces: generate placeholder email
                placeholder_email = f"{ext_id}@{mp.slug}.marketplace.kova.co.ke"
                user = User.objects.create_user(
                    email=placeholder_email,
                    username=placeholder_email,
                    password=secrets.token_urlsafe(16),
                    full_name=data.get("full_name", ""),
                    phone_number=data["phone"],
                )
        elif identity_field == "external_id":
            # External-ID based: check if user was already linked
            linked = MarketplaceSellerAccount.objects.filter(
                marketplace=mp, external_seller_id=ext_id,
            ).select_related("user").first()
            if linked:
                user = linked.user
            elif data.get("email"):
                user = User.objects.filter(email__iexact=data["email"]).first()
            if not user:
                email = data.get("email") or f"{ext_id}@{mp.slug}.marketplace.kova.co.ke"
                user = User.objects.create_user(
                    email=email,
                    username=email,
                    password=secrets.token_urlsafe(16),
                    full_name=data.get("full_name", ""),
                )

        if not user:
            return Response(
                {"error": "Could not create or find user for this seller."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set plan on user profile
        profile = user.profile
        profile.plan = mp.seller_default_plan
        profile.save(update_fields=["plan"])

        # Create seller account
        try:
            seller_status = (
                MarketplaceSellerAccount.Status.ACTIVE
                if mp.auto_activate_sellers
                else MarketplaceSellerAccount.Status.INVITED
            )
            seller = MarketplaceSellerAccount.objects.create(
                marketplace=mp,
                user=user,
                external_seller_id=ext_id,
                status=seller_status,
                seller_metadata=data.get("seller_metadata", {}),
                activated_at=timezone.now() if mp.auto_activate_sellers else None,
            )
        except IntegrityError:
            return Response(
                {"error": f"Seller {ext_id} already linked to a different user in this marketplace."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            "status": "provisioned",
            "external_seller_id": ext_id,
            "email": user.email,
            "seller_status": seller.status,
            "plan": profile.plan,
            "auto_activated": mp.auto_activate_sellers,
        }, status=status.HTTP_201_CREATED)


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

            product_data = {
                "name": data["name"],
                "description": data["description"],
                "offering_type": data["offering_type"],
                "stock_status": data["stock_status"],
                "is_featured": data["is_featured"],
                "tags": data["tags"],
                "source": Product.Source.MARKETPLACE,
                "marketplace_partner": mp,
                "last_synced_at": timezone.now(),
                "currency": data["currency"] or mp.default_product_currency,
            }

            if data["price"] is not None:
                product_data["price"] = data["price"]
            if data["quantity"] is not None:
                product_data["quantity"] = data["quantity"]
            if data["product_url"]:
                product_data["product_url"] = data["product_url"]
            if data["additional_images"]:
                product_data["additional_images"] = data["additional_images"]

            if existing:
                for k, v in product_data.items():
                    setattr(existing, k, v)
                existing.save()
                existing.check_low_stock()
                existing.save(update_fields=["stock_status"])
                updated += 1
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

        # Update seller sync stats
        seller.products_synced = Product.objects.filter(
            user=seller.user, marketplace_partner=mp, is_active=True,
        ).count()
        seller.last_product_sync = timezone.now()
        seller.save(update_fields=["products_synced", "last_product_sync"])

        # Trigger Snap to Sell vision if configured
        snap_triggered = False
        if mp.auto_snap_on_sync and created > 0:
            snap_triggered = self._trigger_snap(seller.user, mp)

        resp_status = status.HTTP_201_CREATED if (created or updated) else status.HTTP_400_BAD_REQUEST
        return Response({
            "created": created,
            "updated": updated,
            "errors": errors,
            "snap_triggered": snap_triggered,
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

    def _trigger_snap(self, user, mp):
        """Trigger batch Snap to Sell for newly synced products."""
        try:
            from apps.products.tasks import snap_batch_process
            # Get products synced in the last minute (the ones we just created)
            recent = Product.objects.filter(
                user=user,
                marketplace_partner=mp,
                source=Product.Source.MARKETPLACE,
                last_synced_at__gte=timezone.now() - timezone.timedelta(minutes=2),
            ).values_list("id", flat=True)[:50]

            if recent:
                snap_batch_process.delay(
                    user_id=str(user.pk),
                    product_ids=[str(pid) for pid in recent],
                )
                return True
        except Exception:
            pass
        return False


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
