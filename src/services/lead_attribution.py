"""Consent-gated campaign provenance for website leads."""

from __future__ import annotations

import re

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
_UTM_VALUE = re.compile(r"[A-Za-z0-9_ .:+\-/\u0600-\u06ff]{1,100}")
_META_CLICK_ID = re.compile(r"[A-Za-z0-9_-]{1,512}")
_META_SOURCES = {"facebook", "instagram", "meta", "fb", "ig"}
_PAID_MEDIA = {"paid", "paid_social", "paid-social", "cpc", "ppc", "cpm", "ads"}


def lead_attribution(payload: dict) -> dict | None:
    """Save normalized campaign labels and the Meta click id when the visitor consented."""
    if payload.get("attribution_consent") is not True:
        return None

    fields = {}
    for key in UTM_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and _UTM_VALUE.fullmatch(value) and value.strip():
            fields[key] = value.strip()

    click_id = payload.get("fbclid")
    if isinstance(click_id, str) and _META_CLICK_ID.fullmatch(click_id):
        fields["fbclid"] = click_id.strip()
        fields["meta_click"] = True
    if not fields:
        return None

    source = fields.get("utm_source", "").lower()
    medium = fields.get("utm_medium", "").lower()
    if source in _META_SOURCES or fields.get("meta_click"):
        # A click ID or organic Meta source alone is not evidence of an ad.
        fields["acquisition_channel"] = "meta_ads" if medium in _PAID_MEDIA else "meta"
    else:
        fields["acquisition_channel"] = "campaign"
    return {"consent": True, **fields}


def attribution_summary(raw_data: dict | None) -> dict | None:
    """Return campaign fields to the owner API, including a consented click id."""
    fields = raw_data.get("attribution") if isinstance(raw_data, dict) else None
    if not isinstance(fields, dict) or fields.get("consent") is not True:
        return None
    keys = (*UTM_KEYS, "fbclid", "acquisition_channel", "meta_click")
    return {key: fields[key] for key in keys if key in fields}
