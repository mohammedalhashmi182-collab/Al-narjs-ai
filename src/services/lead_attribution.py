"""Consent-gated, bounded campaign provenance for public lead submissions.

Avoid storing visitor IP, cookies, referrers, or click identifiers until the
visitor explicitly opts into attribution on the submitting form. This module
stores metadata on AcquisitionLead.raw_data so no production migration is needed.
"""
from __future__ import annotations

import re

_UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
_ALLOWED = re.compile(r"^[A-Za-z0-9_ .:/+%\-\u0600-\u06ff]{1,100}$")
_CLICK = re.compile(r"^[A-Za-z0-9_\-]{1,250}$")


def lead_attribution(payload: dict) -> dict | None:
    """Return strictly opt-in attribution, never arbitrary visitor data."""
    if payload.get("attribution_consent") is not True:
        return None

    attrs = {"consent": True}
    for key in _UTM_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and _ALLOWED.fullmatch(value):
            attrs[key] = value

    click_id = payload.get("fbclid")
    if isinstance(click_id, str) and _CLICK.fullmatch(click_id):
        attrs["fbclid"] = click_id

    src = str(attrs.get("utm_source", "")).lower()
    if src in {"facebook", "instagram", "meta", "fb", "ig"}:
        attrs["acquisition_channel"] = "meta_ads"
    elif src:
        attrs["acquisition_channel"] = "campaign"
    return attrs
