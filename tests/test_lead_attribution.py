"""Consent and sanitization regression tests for campaign provenance."""
from src.services.lead_attribution import lead_attribution


def test_no_attribution_when_consent_is_missing_or_not_boolean_true():
    sample = {"utm_source": "facebook", "fbclid": "abc_123"}
    assert lead_attribution(sample) is None
    assert lead_attribution({**sample, "attribution_consent": "yes"}) is None
    assert lead_attribution({**sample, "attribution_consent": False}) is None


def test_opted_in_meta_attribution_is_saved():
    result = lead_attribution({
        "attribution_consent": True,
        "utm_source": "facebook",
        "utm_medium": "paid_social",
        "utm_campaign": "nov-2026",
        "fbclid": "AbC_123-x",
    })
    assert result == {
        "consent": True,
        "utm_source": "facebook",
        "utm_medium": "paid_social",
        "utm_campaign": "nov-2026",
        "fbclid": "AbC_123-x",
        "acquisition_channel": "meta_ads",
    }


def test_invalid_click_ids_and_unbounded_values_are_ignored():
    result = lead_attribution({
        "attribution_consent": True,
        "fbclid": "<script>alert(1)</script>",
        "utm_campaign": "x" * 101,
        "utm_medium": "social",
        "visitor_ip": "192.168.1.2",
    })
    assert result == {"consent": True, "utm_medium": "social"}
