"""Freelance-document identity printed on invoices, terms, and footers.

The operator is a Saudi freelance-document holder and is not VAT-registered.
``FREELANCE_DOC_NUMBER`` and ``FREELANCE_HOLDER_NAME`` override the defaults.
An empty value falls back to the visible placeholder so a missing setting is
obvious. ``SELLER_CR_NUMBER`` still wins when the new document variable is
unset, so an existing deployment keeps the number it already configured.
"""

from __future__ import annotations

import os

DOC_PLACEHOLDER = "{{FREELANCE_DOC_NUMBER}}"
HOLDER_PLACEHOLDER = "{{FREELANCE_HOLDER_NAME}}"
HOLDER_EN_PLACEHOLDER = "{{FREELANCE_HOLDER_NAME_EN}}"


def _env(name: str) -> str | None:
    if name not in os.environ:
        return None
    return os.environ[name].strip()


def freelance_doc_number() -> str:
    explicit = _env("FREELANCE_DOC_NUMBER")
    if explicit is not None:
        return explicit or DOC_PLACEHOLDER
    legacy = _env("SELLER_CR_NUMBER")
    if legacy:
        return legacy
    from src.config.settings import get_settings

    settings = get_settings()
    value = (settings.freelance_doc_number or "").strip() or (settings.seller_cr_number or "").strip()
    return value or DOC_PLACEHOLDER


def freelance_holder_name() -> str:
    explicit = _env("FREELANCE_HOLDER_NAME")
    if explicit is not None:
        return explicit or HOLDER_PLACEHOLDER
    from src.config.settings import get_settings

    value = (get_settings().freelance_holder_name or "").strip()
    return value or HOLDER_PLACEHOLDER


def freelance_holder_name_en() -> str:
    explicit = _env("FREELANCE_HOLDER_NAME_EN")
    if explicit is not None:
        return explicit or HOLDER_EN_PLACEHOLDER
    from src.config.settings import get_settings

    value = (get_settings().freelance_holder_name_en or "").strip()
    return value or HOLDER_EN_PLACEHOLDER
