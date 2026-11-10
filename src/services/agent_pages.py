"""Public copy for /ai-agent/<slug>.

Each page is written for that role. The worked example is an illustration of
the method, not a client, a testimonial, or a result. Prices stay in the
catalog and are rendered by the template.
"""

from __future__ import annotations

from typing import Any

PAGES: dict[str, dict[str, Any]] = {}


def page_for(slug: str) -> dict[str, Any] | None:
    return PAGES.get(slug)


def visible_words(slug: str, lang: str) -> int:
    page = PAGES[slug]
    parts = list(page["paragraphs_ar"] if lang == "ar" else page["paragraphs_en"])
    parts.append(page["example_ar"] if lang == "ar" else page["example_en"])
    for item in page["faq_ar"] if lang == "ar" else page["faq_en"]:
        parts.append(item["q"])
        parts.append(item["a"])
    return len(" ".join(parts).split())


def jsonld(employee: dict, page: dict | None, lang: str, slug: str) -> dict:
    arabic = lang == "ar"
    faqs = []
    if page:
        faqs = page["faq_ar"] if arabic else page["faq_en"]
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Service",
                "name": employee["title_ar"] if arabic else employee["title_en"],
                "description": employee["intro_ar"] if arabic else employee["intro_en"],
                "serviceType": employee.get("dept") if arabic else employee.get("dept_en"),
                "url": f"https://karmaai.online/{lang}/ai-agent/{slug}",
                "provider": {
                    "@type": "Organization",
                    "name": "Al-Narjis AI",
                    "url": "https://karmaai.online",
                },
                "areaServed": "Saudi Arabia",
                "availableLanguage": ["ar", "en"],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
                    }
                    for item in faqs
                ],
            },
        ],
    }


def _faq(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"q": question, "a": answer} for question, answer in pairs]


def _put(
    slug: str,
    paragraphs_ar: tuple[str, ...],
    paragraphs_en: tuple[str, ...],
    example_ar: str,
    example_en: str,
    faq_ar: list[dict[str, str]],
    faq_en: list[dict[str, str]],
) -> None:
    PAGES[slug] = {
        "paragraphs_ar": paragraphs_ar,
        "paragraphs_en": paragraphs_en,
        "example_ar": example_ar,
        "example_en": example_en,
        "faq_ar": faq_ar,
        "faq_en": faq_en,
    }


# Copy is split across modules so each agent stays a full page, not a shared template.
from src.services import agent_page_copy as _copy  # noqa: E402
from src.services import agent_page_copy_b as _copy_b  # noqa: E402
from src.services import agent_page_copy_c as _copy_c  # noqa: E402
from src.services import agent_page_copy_d as _copy_d  # noqa: E402

_copy.register(_put, _faq)
_copy_b.register(_put, _faq)
_copy_c.register(_put, _faq)
_copy_d.register(_put, _faq)

from src.services import agent_page_extra as _extra  # noqa: E402

_extra.extend(PAGES)

from src.services.catalog import EMPLOYEES as _EMPLOYEES  # noqa: E402

_missing = sorted(set(_EMPLOYEES) - set(PAGES))
_extra = sorted(set(PAGES) - set(_EMPLOYEES))
if _missing or _extra:
    raise RuntimeError(f"agent page copy mismatch missing={_missing} extra={_extra}")
