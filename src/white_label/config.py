"""Operator-managed brand and license configuration for a separate service."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Language = Literal["ar", "en"]

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,62}$")]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Email = Annotated[
    str,
    StringConstraints(
        max_length=254,
        pattern=r"^[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$",
    ),
]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
RIYADH = ZoneInfo("Asia/Riyadh")
RESERVED_DOMAINS = ("alnarjisai.com", "karmaai.online")
DOMAIN_RE = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})"
)


def normalize_domain(value: str) -> str:
    domain = value.lower().removesuffix(".")
    if not value.isascii() or len(domain) > 253 or not DOMAIN_RE.fullmatch(domain):
        raise ValueError("expected an ASCII DNS hostname without a scheme or port")
    return domain


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class Brand(ConfigurationModel):
    name_ar: Label
    name_en: Label
    description_ar: Description
    description_en: Description
    default_language: Language = "ar"
    accent: Color = "#C9A27A"
    logo_png: bool = False
    support_email: Email

    @field_validator("support_email")
    @classmethod
    def reject_mailto_escapes(cls, value: str) -> str:
        if "%" in value:
            raise ValueError("support email must not contain URI escapes")
        return value


class FeatureFlags(ConfigurationModel):
    public_brand_page: bool = False


class License(ConfigurationModel):
    state: Literal["pending", "active", "suspended", "revoked"] = "pending"
    expires_on: date | None = None

    @model_validator(mode="after")
    def require_expiration(self) -> License:
        if self.state == "active" and self.expires_on is None:
            raise ValueError("an active license must have an expiration date")
        return self

    def allows_service_on(self, day: date) -> bool:
        return (
            self.state == "active"
            and self.expires_on is not None
            and day <= self.expires_on
        )


class Tenant(ConfigurationModel):
    tenant_id: Slug
    domain: str
    brand: Brand
    license: License = Field(default_factory=License)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        domain = normalize_domain(value)
        if any(domain == root or domain.endswith("." + root) for root in RESERVED_DOMAINS):
            raise ValueError("the domain belongs to the managed Narjis application")
        return domain


class Manifest(ConfigurationModel):
    mode: Literal["hosted", "standalone"]
    tenants: tuple[Tenant, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_tenant_mapping(self) -> Manifest:
        if self.mode == "standalone" and len(self.tenants) != 1:
            raise ValueError("a standalone deployment must have exactly one tenant")
        if len({tenant.tenant_id for tenant in self.tenants}) != len(self.tenants):
            raise ValueError("tenant IDs must be unique")
        if len({tenant.domain for tenant in self.tenants}) != len(self.tenants):
            raise ValueError("tenant domains must be unique")
        return self

    @classmethod
    def load(cls, path: Path) -> Manifest:
        return cls.model_validate_json(path.read_bytes())
