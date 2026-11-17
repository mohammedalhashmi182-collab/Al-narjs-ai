"""Public comparison pages: /compare/<slug>.

Facts about Al-Narjis come from the catalog and the published policies.
Facts about the other products are limited to what those companies say in
public about the shape of the product, the language of their materials, and
that their prices are in US dollars on their own sites. This module does not
copy those prices, name customers, or state a result.
"""

from __future__ import annotations

from src.services.catalog import PACKAGE_ORDER, PACKAGES


def _sec(heading: str, paragraphs: list[str], bullets: list[str] | None = None) -> dict:
    block: dict = {"h": heading, "p": paragraphs}
    if bullets:
        block["ul"] = bullets
    return block


def public_plans() -> list[dict]:
    """Monthly public plans. Amounts are the catalog display prices."""
    plans = []
    for key in PACKAGE_ORDER:
        pkg = PACKAGES[key]
        plans.append(
            {
                "key": key,
                "name": pkg["name"],
                "name_en": pkg["name_en"],
                "price": pkg["price"],
            }
        )
    return plans


_NARJIS_AR = (
    "النرجس للذكاء الاصطناعي منصة عربية أولاً من الرياض. يأخذ الرئيس التنفيذي الذكي "
    "هدف صاحب المنشأة ويحوله إلى فريق من وكلاء الذكاء الاصطناعي. أدوار الفريق تشمل "
    "خدمة عملاء واتساب، ومتابعة المبيعات، والتسويق."
)
_NARJIS_EN = (
    "Al-Narjis AI is an Arabic-first AI platform from Riyadh. An AI chief executive "
    "takes the owner's goal and turns it into a team of AI agents. The roles include "
    "WhatsApp customer service, sales follow-up, and marketing."
)
_WA_AR = (
    "ربط واتساب للأعمال بمحادثات العميل نفسه ما زال قيد التطوير، كما توضحه صفحة الشراكات. "
    "الجملة السابقة تصف دور الفريق، ولا تقول إن الربط متاح اليوم."
)
_WA_EN = (
    "Connecting a customer's own WhatsApp Business number is still in development, "
    "as the partnerships page states. The sentence above describes the team's role. "
    "It does not say that connection is available today."
)
_LIMIT_AR = (
    "هذه الصفحة وصف لشكل المنتج ومكانه ولغته. ليست ترتيباً، ولا حكماً بأن أحد المنتجين "
    "أنسب لكل منشأة. لا ننشر أسماء عملاء ولا نتائج ولا شعارات، ولا ننسب إلى المنتج الآخر "
    "رقماً أو حصة سوقية."
)
_LIMIT_EN = (
    "This page describes product shape, place, and language. It is not a ranking, "
    "and it is not a claim that one product fits every organization. We do not publish "
    "customer names, results, or logos, and we do not assign the other product a number "
    "or a market share."
)


COMPARISONS: list[dict] = [
    {
        "slug": "tidio",
        "name": "Tidio",
        "title_ar": "النرجس وTidio — مقارنة وصفية | النرجس للذكاء الاصطناعي",
        "title_en": "Al-Narjis and Tidio — a factual comparison | Al-Narjis AI",
        "desc_ar": "مقارنة وصفية بين منصة النرجس من الرياض وTidio: اللغة، وشكل المنتج، والأسعار الشهرية بالريال. بلا عملاء مخترعين وبلا أرقام نتائج.",
        "desc_en": "A factual comparison of Al-Narjis, from Riyadh, and Tidio: language, product shape, and monthly prices in SAR. No invented clients and no result figures.",
        "h1_ar": "النرجس مقارنةً بـ Tidio",
        "h1_en": "Al-Narjis compared with Tidio",
        "sections_ar": [
            _sec("ما هي النرجس", [_NARJIS_AR, _WA_AR]),
            _sec("Tidio كما يصفه موقعه العام", [
                "Tidio منتج لخدمة العملاء. يصف موقعه العام الدردشة المباشرة على الموقع، وروبوتات المحادثة، ومكتب المساعدة، ووكيل ذكاء اصطناعي باسم Lyro.",
                "المواد العامة للمنتج بالإنجليزية، وأسعاره منشورة بالدولار الأمريكي على موقع Tidio. هذه الصفحة لا تنقل تلك الأسعار، لأنها تتغير هناك وليست أسعار النرجس.",
            ]),
            _sec("أين يختلف المسار", [
                "Tidio، بحسب وصفه العام، أداة دردشة ودعم على الموقع. النرجس تبدأ من هدف واحد لصاحب المنشأة وتكوّن فريقاً للأدوار المذكورة، والأسعار الشهرية بالريال السعودي في القائمة أدناه.",
                "من يريد ودجة دردشة لموقع قد يجد وصف Tidio العام أقرب إلى حاجته. من يريد فريقاً عربياً يُبنى حول هدفه، بأسعار معلنة بالريال من الرياض، فهذا ما تصفه باقات النرجس.",
                _LIMIT_AR,
            ]),
        ],
        "sections_en": [
            _sec("What Al-Narjis is", [_NARJIS_EN, _WA_EN]),
            _sec("Tidio, as its public site describes it", [
                "Tidio is a customer-service product. Its public site describes live chat on a website, chatbots, a help desk, and an AI agent named Lyro.",
                "The public materials are in English, and the prices are published in US dollars on Tidio's site. This page does not copy those prices. They change there, and they are not Al-Narjis prices.",
            ]),
            _sec("Where the path differs", [
                "As its public description stands, Tidio is a website chat and support tool. Al-Narjis starts from one goal the owner states and staffs a team for the roles above. The monthly prices are in Saudi riyal, in the list below.",
                "A business that wants a chat widget on a website may find Tidio's public description closer to that need. A business that wants an Arabic team built around its goal, with published prices in SAR from Riyadh, is who the Al-Narjis plans describe.",
                _LIMIT_EN,
            ]),
        ],
        "faq_ar": [
            {"q": "هل هذه الصفحة تعرض عملاء؟", "a": "لا. لا أسماء عملاء، ولا نتائج، ولا شعارات."},
            {"q": "هل أسعار Tidio مكتوبة هنا؟", "a": "لا. أسعار Tidio على موقعهم بالدولار الأمريكي. أسعار النرجس بالريال في القائمة على هذه الصفحة."},
            {"q": "هل ربط واتساب للأعمال متاح اليوم؟", "a": "لا. هو قيد التطوير، وصفحة الشراكات هي المرجع."},
        ],
        "faq_en": [
            {"q": "Does this page show customers?", "a": "No. No customer names, no results, and no logos."},
            {"q": "Are Tidio's prices written here?", "a": "No. Tidio's prices are on their site, in US dollars. Al-Narjis prices are in SAR, in the list on this page."},
            {"q": "Is a WhatsApp Business connection available today?", "a": "No. It is in development. The partnerships page is the reference."},
        ],
    },
    {
        "slug": "manychat",
        "name": "ManyChat",
        "title_ar": "النرجس وManyChat — مقارنة وصفية | النرجس للذكاء الاصطناعي",
        "title_en": "Al-Narjis and ManyChat — a factual comparison | Al-Narjis AI",
        "desc_ar": "مقارنة وصفية بين منصة النرجس من الرياض وManyChat: مسارات الرسائل مقابل فريق يُبنى من هدف المالك. بلا عملاء مخترعين وبلا أرقام نتائج.",
        "desc_en": "A factual comparison of Al-Narjis, from Riyadh, and ManyChat: messaging flows against a team built from the owner's goal. No invented clients and no result figures.",
        "h1_ar": "النرجس مقارنةً بـ ManyChat",
        "h1_en": "Al-Narjis compared with ManyChat",
        "sections_ar": [
            _sec("ما هي النرجس", [_NARJIS_AR, _WA_AR]),
            _sec("ManyChat كما يصفه موقعه العام", [
                "ManyChat منتج لأتمتة التسويق عبر المحادثات. يصف موقعه العام مسارات لإنستغرام وفيسبوك ماسنجر وواتساب: رد على كلمة، ومسار، ورسالة جماعية.",
                "المواد العامة بالإنجليزية، والأسعار بالدولار الأمريكي على موقع ManyChat. هذه الصفحة لا تنقل تلك الأسعار.",
            ]),
            _sec("أين يختلف المسار", [
                "ManyChat، بحسب هذا الوصف، بنّاء مسارات للرسائل الاجتماعية. موقعه العام لا يقدّم رئيساً تنفيذياً ذكياً يكوّن فريقاً من هدف صاحب المنشأة، وليس منصة عربية أولاً من الرياض.",
                "النرجس تبدأ من الهدف، ثم فريق لخدمة عملاء واتساب ومتابعة المبيعات والتسويق، بأسعار شهرية بالريال في القائمة أدناه.",
                _LIMIT_AR,
            ]),
        ],
        "sections_en": [
            _sec("What Al-Narjis is", [_NARJIS_EN, _WA_EN]),
            _sec("ManyChat, as its public site describes it", [
                "ManyChat is a chat-marketing product. Its public site describes flows for Instagram, Facebook Messenger, and WhatsApp: a reply to a keyword, a path, and a broadcast.",
                "The public materials are in English, and the prices are in US dollars on ManyChat's site. This page does not copy those prices.",
            ]),
            _sec("Where the path differs", [
                "On that public description, ManyChat is a builder of social-messaging flows. Its public site does not present an AI chief executive that staffs a team from the owner's goal, and it is not an Arabic-first platform from Riyadh.",
                "Al-Narjis starts from the goal, then a team for WhatsApp customer service, sales follow-up, and marketing, with monthly prices in SAR in the list below.",
                _LIMIT_EN,
            ]),
        ],
        "faq_ar": [
            {"q": "هل ManyChat منصة من الرياض؟", "a": "لا. المواد العامة لـ ManyChat بالإنجليزية وأسعارها بالدولار. النرجس من الرياض وأسعارها بالريال."},
            {"q": "هل ننقل أسعار ManyChat؟", "a": "لا. تبقى على موقعهم. القائمة هنا أسعار النرجس فقط."},
            {"q": "هل نعرض نتائج عملاء؟", "a": "لا. لا نتائج ولا أسماء."},
        ],
        "faq_en": [
            {"q": "Is ManyChat a platform from Riyadh?", "a": "No. ManyChat's public materials are in English and its prices are in US dollars. Al-Narjis is from Riyadh and its prices are in SAR."},
            {"q": "Do we copy ManyChat's prices?", "a": "No. They stay on their site. The list here is Al-Narjis prices only."},
            {"q": "Do we show customer results?", "a": "No. No results and no names."},
        ],
    },
    {
        "slug": "intercom-fin",
        "name": "Intercom Fin",
        "title_ar": "النرجس وIntercom Fin — مقارنة وصفية | النرجس للذكاء الاصطناعي",
        "title_en": "Al-Narjis and Intercom Fin — a factual comparison | Al-Narjis AI",
        "desc_ar": "مقارنة وصفية بين منصة النرجس من الرياض وFin من Intercom: وكيل دعم مقابل فريق يُبنى من هدف المالك. بلا عملاء مخترعين وبلا أرقام نتائج.",
        "desc_en": "A factual comparison of Al-Narjis, from Riyadh, and Intercom's Fin: a support agent against a team built from the owner's goal. No invented clients and no result figures.",
        "h1_ar": "النرجس مقارنةً بـ Intercom Fin",
        "h1_en": "Al-Narjis compared with Intercom Fin",
        "sections_ar": [
            _sec("ما هي النرجس", [_NARJIS_AR, _WA_AR]),
            _sec("Fin كما تنشره Intercom", [
                "Intercom شركة في محادثة العملاء. Fin هو وكيل الذكاء الاصطناعي الذي تنشره للرد على أسئلة العملاء، ومن ذلك الاعتماد على مركز مساعدة، إلى جانب صندوق الوارد في Intercom.",
                "المواد العامة بالإنجليزية، والسعر بالدولار الأمريكي على موقع Intercom. هذه الصفحة لا تعيد كتابة سعر Fin.",
            ]),
            _sec("أين يختلف المسار", [
                "Fin، كما تنشره Intercom، وكيل دعم للأسئلة. النرجس منصة من الرياض يحوّل فيها رئيس تنفيذي ذكي هدف المالك إلى فريق يشمل خدمة عملاء واتساب ومتابعة المبيعات والتسويق.",
                "لا نقول إن Fin بلا واجهة عربية، لأن تعريب Intercom قد يتغير. نقول إن النرجس عربية أولاً ومن الرياض، وأسعارها الشهرية بالريال في القائمة أدناه.",
                _LIMIT_AR,
            ]),
        ],
        "sections_en": [
            _sec("What Al-Narjis is", [_NARJIS_EN, _WA_EN]),
            _sec("Fin, as Intercom publishes it", [
                "Intercom is a customer-messaging company. Fin is the AI agent it publishes for answering customer questions, including from a help center, alongside the Intercom inbox.",
                "The public materials are in English, and the price is in US dollars on Intercom's site. This page does not restate Fin's price.",
            ]),
            _sec("Where the path differs", [
                "As Intercom publishes it, Fin is a support agent for questions. Al-Narjis is a platform from Riyadh where an AI chief executive turns the owner's goal into a team that includes WhatsApp customer service, sales follow-up, and marketing.",
                "We do not say Fin has no Arabic interface, because Intercom's localization can change. We do say Al-Narjis is Arabic-first and from Riyadh, with monthly prices in SAR in the list below.",
                _LIMIT_EN,
            ]),
        ],
        "faq_ar": [
            {"q": "هل Fin هو فريق النرجس؟", "a": "لا. Fin وكيل دعم تنشره Intercom. النرجس فريق يُبنى من هدف المالك في الرياض."},
            {"q": "هل سعر Fin مكتوب هنا؟", "a": "لا. سعر Fin على موقع Intercom بالدولار. أسعار النرجس بالريال في القائمة."},
            {"q": "هل ندّعي أن Fin لا يدعم العربية؟", "a": "لا. لا نعرف شكل التعريب في كل تحديث. ما نثبته هنا أن النرجس عربية أولاً ومن الرياض."},
        ],
        "faq_en": [
            {"q": "Is Fin the Al-Narjis team?", "a": "No. Fin is a support agent Intercom publishes. Al-Narjis is a team built from the owner's goal in Riyadh."},
            {"q": "Is Fin's price written here?", "a": "No. Fin's price is on Intercom's site, in US dollars. Al-Narjis prices are in SAR, in the list."},
            {"q": "Do we claim Fin has no Arabic?", "a": "No. We do not know the localization of every release. What this page states is that Al-Narjis is Arabic-first and from Riyadh."},
        ],
    },
]

_BY_SLUG = {item["slug"]: item for item in COMPARISONS}


def get_comparison(slug: str) -> dict | None:
    return _BY_SLUG.get(slug)


def other_comparisons(slug: str) -> list[dict]:
    return [item for item in COMPARISONS if item["slug"] != slug]
