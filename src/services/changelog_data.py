"""Changelog entries shown on /changelog.

The dates and facts below are taken from git history on main. They are not
a forecast. ``CHANGELOG.md`` is the Keep a Changelog copy of the same notes.
"""

from __future__ import annotations

from typing import TypedDict


class Item(TypedDict):
    ar: str
    en: str


class Section(TypedDict):
    kind: str
    items: list[Item]


class Release(TypedDict):
    version: str
    date: str
    sections: list[Section]


# kind -> (Arabic heading, English heading)
KINDS: dict[str, tuple[str, str]] = {
    "added": ("أُضيف", "Added"),
    "changed": ("تغيّر", "Changed"),
    "fixed": ("أُصلح", "Fixed"),
}


RELEASES: list[Release] = [
    {
        "version": "1.0.0",
        "date": "2026-11-12",
        "sections": [
            {
                "kind": "added",
                "items": [
                    {
                        "ar": "مرجع عام للواجهة البرمجية على /docs والمواصفة على /openapi.json. المرجع يقتصر على مسارات العميل، بلا مسارات الإدارة أو المالك أو الخطافات.",
                        "en": "A public API reference at /docs and the spec at /openapi.json. It lists customer routes only, with no admin, owner, or webhook routes.",
                    },
                    {
                        "ar": "صفحة حالة على /status ونقطة JSON على /api/status لحالة الموقع و/health والبوابة والوكلاء.",
                        "en": "A status page at /status and a JSON feed at /api/status for the site, /health, the portal, and the agents.",
                    },
                    {
                        "ar": "صفحة ما الجديد، وصفحة مستوى الخدمة (مسودة بانتظار اعتماد المالك)، وصفحة الشراكات والتكاملات مع عرض العلامة البيضاء.",
                        "en": "A what's-new page, a service-level page (a draft until the owner approves the figures), and a partnerships page with the white-label offer.",
                    },
                    {
                        "ar": "المسار /signup صار يحوّل إلى التسجيل في بوابة العميل على /portal.",
                        "en": "/signup now redirects to signup in the customer portal at /portal.",
                    },
                ],
            },
            {
                "kind": "changed",
                "items": [
                    {
                        "ar": "الدفع للزائر صار عبر Moyasar بالبطاقة (مدى وفيزا وماستركارد). أُلغي تحويل الضيف البنكي. التحقق من خطاف Moyasar مقبول. (9 نوفمبر و12 نوفمبر 2026)",
                        "en": "Guest checkout is Moyasar card payment (mada, Visa, and Mastercard). Guest bank transfer is gone. Moyasar webhook verification is accepted. (9 and 12 November 2026)",
                    },
                    {
                        "ar": "تحسينات الظهور في البحث: صفحة لكل وكيل، روابط اللغة البديلة، ملف llms.txt، وإصلاح تحويل الصفحات الإنجليزية. (11 نوفمبر 2026)",
                        "en": "Search improvements: a page per agent, hreflang alternates, llms.txt, and a fix for English locale redirects. (11 November 2026)",
                    },
                    {
                        "ar": "ست صفحات خدمات عامة (أتمتة، روبوتات محادثة، تصميم، واجهات، محتوى، ترجمة) نُشرت في 17 أكتوبر 2026.",
                        "en": "Six public service pages (automation, chatbots, design, UI, content, and translation) shipped on 17 October 2026.",
                    },
                    {
                        "ar": "الفريق المعروض على الموقع 39 وكيلاً، يقودهم الرئيس التنفيذي الذكي. العدد يُقرأ من السجل الحي وليس من قائمة ثابتة في هذه الصفحة.",
                        "en": "The public roster is 39 agents, led by the AI CEO. The count is read from the live catalog, not from a hard-coded list on this page.",
                    },
                ],
            },
        ],
    },
]
