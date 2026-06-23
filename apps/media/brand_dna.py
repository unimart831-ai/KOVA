"""
Unified Brand DNA — single source of truth for all media outputs.

Feeds Photoroom scene packs, Bannerbear templates, Fal prompts, and local graphics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from apps.accounts.models import UserProfile


@dataclass(frozen=True)
class BrandDNA:
  brand_name: str = ""
  primary_color: str = "#0d8474"
  accent_color: str = "#14b8a6"
  secondary_color: str = "#0f172a"
  logo_url: str = ""
  visual_style: str = "photography"
  business_model: str = "product"
  brand_voice: str = ""
  cta_style: str = "shop_now"
  image_style: str = "clean_studio"
  industry: str = ""
  country: str = ""

  def palette(self) -> dict[str, str]:
    return {
      "primary": self.primary_color,
      "accent": self.accent_color,
      "secondary": self.secondary_color,
      "text": "#ffffff",
    }

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  def flux_style_suffix(self) -> str:
    parts = [
      f"brand colors {self.primary_color} and {self.accent_color}",
      f"{self.visual_style} aesthetic",
      f"{self.image_style.replace('_', ' ')}",
    ]
    if self.industry:
      parts.append(f"{self.industry} industry")
    return ", ".join(parts)

  def kling_motion_hint(self) -> str:
    model = self.business_model
    if model == "service":
      return "smooth before-to-after transformation, professional salon lighting"
    if model == "professional":
      return "subtle parallax portfolio showcase, premium agency feel"
    if self.industry in ("food_restaurant",):
      return "appetizing food motion, steam and warm lighting"
    return "elegant product motion, soft studio lighting, subtle zoom"

  def bannerbear_modifications(
    self,
    *,
    title: str = "",
    subtitle: str = "",
    price: str = "",
    image_url: str = "",
    cta: str = "",
  ) -> list[dict[str, str]]:
    mods: list[dict[str, str]] = []
    if title:
      mods.append({"name": "title", "text": title[:120]})
    if subtitle:
      mods.append({"name": "subtitle", "text": subtitle[:200]})
    if price:
      mods.append({"name": "price", "text": price[:40]})
    if image_url:
      mods.append({"name": "photo", "image_url": image_url})
    if cta:
      mods.append({"name": "cta", "text": cta[:40]})
    mods.append({"name": "primary_color", "color": self.primary_color})
    if self.logo_url:
      mods.append({"name": "logo", "image_url": self.logo_url})
    return mods


_CTA_BY_MODEL = {
  UserProfile.BusinessModel.PRODUCT: "shop_now",
  UserProfile.BusinessModel.SERVICE: "book_now",
  UserProfile.BusinessModel.PROFESSIONAL: "learn_more",
}

_IMAGE_STYLE_BY_VISUAL = {
  "photography": "clean_studio",
  "minimal": "minimal_flat",
  "bold": "high_contrast",
  "luxury": "luxury_editorial",
  "playful": "vibrant_social",
  "dark_moody": "dark_moody",
  "auto": "clean_studio",
}


def resolve_brand_dna(user, profile=None) -> BrandDNA:
  """Build BrandDNA from profile, agency brand, and commerce tokens."""
  from apps.products.commerce_seo import brand_name
  from apps.teams.branding import get_commerce_branding

  profile = profile or getattr(user, "profile", None)
  commerce = get_commerce_branding(user, profile) if user else {}
  name = ""
  if profile:
    try:
      name = brand_name(profile, user)
    except Exception:
      name = (profile.company_name or "").strip()

  primary = commerce.get("theme_primary_color") or "#0d8474"
  accent = primary
  secondary = "#0f172a"
  logo = commerce.get("logo_url") or ""

  if profile:
    colors = profile.brand_colors or []
    if colors and not commerce.get("theme_primary_color"):
      primary = str(colors[0]).strip() or primary
    if len(colors) >= 2:
      accent = str(colors[1]).strip() or accent
    if len(colors) >= 3:
      secondary = str(colors[2]).strip() or secondary
    if not logo and profile.brand_logo_url:
      logo = profile.brand_logo_url.strip()

  visual = (getattr(profile, "visual_style", None) or "photography").strip()
  business_model = getattr(profile, "business_model", UserProfile.BusinessModel.PRODUCT) or UserProfile.BusinessModel.PRODUCT
  cta_style = _CTA_BY_MODEL.get(business_model, "shop_now")

  return BrandDNA(
    brand_name=name,
    primary_color=primary,
    accent_color=accent,
    secondary_color=secondary,
    logo_url=logo,
    visual_style=visual,
    business_model=business_model,
    brand_voice=(getattr(profile, "brand_voice", None) or "")[:500],
    cta_style=cta_style,
    image_style=_IMAGE_STYLE_BY_VISUAL.get(visual, "clean_studio"),
    industry=(getattr(profile, "industry", None) or ""),
    country=(getattr(profile, "country", None) or ""),
  )
