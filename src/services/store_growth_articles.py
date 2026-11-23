"""Saudi store guides and an explicitly labelled fictional case study."""

ARTICLES = [
    {
        "slug": "whatsapp-automation-for-online-stores",
        "title_ar": "أتمتة واتساب للمتاجر السعودية",
        "title_en": "WhatsApp Automation for Saudi Online Stores",
        "desc_ar": "كيف يفرز فريق المتجر أسئلة الشحن والاستبدال على واتساب، ويختار الرد المناسب، ويعرف متى يسلّم المحادثة لموظف.",
        "desc_en": "Design a WhatsApp inbox workflow for shipping and returns, with approved replies and clear handoffs.",
        "date": "2026-11-23",
        "category_ar": "تشغيل المتاجر",
        "category_en": "Store operations",
        "reading_minutes": 2,
        "keywords": [
            "أتمتة واتساب للمتاجر السعودية",
            "المتاجر السعودية"
        ],
        "body_ar": [
            {
                "h": "ابدأ بسؤال واحد",
                "p": [
                    "راجع آخر أسبوع من الرسائل بعد حذف بيانات العملاء. افصل سؤال «كم يستغرق الشحن؟» عن «وين طلبي؟». الأول يحتاج سياسة منشورة والثاني يحتاج حالة طلب موثوقة."
                ]
            },
            {
                "h": "جهّز الرد المعتمد",
                "p": [
                    "اكتب المدة كما تظهر في سياسة المتجر وحدد المدن والاستثناءات. إذا كانت الوجهة غير واضحة، يكفي أن تسأل العميل عن مدينته قبل اختيار الرد."
                ]
            },
            {
                "h": "حوّل الاستثناء لموظف",
                "p": [
                    "إذا ظهر تأخير أو تعارض في حالة الشحنة، سلّم المحادثة لمسؤول الشحن مع ملخص السؤال وآخر حالة مؤكدة. عيّن شخصاً يتابعها حتى الإغلاق."
                ]
            },
            {
                "h": "اختبر قبل التعميم",
                "p": [
                    "جرّب الردود على محادثات قديمة ثم راجع عينة يومية من الحالات المغلقة."
                ],
                "ul": [
                    "سؤال قبل الشراء",
                    "طلب متأخر",
                    "عنوان ناقص"
                ]
            }
        ],
        "body_en": [
            {
                "h": "Start with one question",
                "p": [
                    "Separate general delivery questions from requests for an individual parcel update. A published shipping policy can answer the former. The latter needs a verified order record."
                ]
            },
            {
                "h": "Write the approved answer",
                "p": [
                    "Keep the delivery window, covered cities and exceptions together. If the destination is unclear, ask for the city before selecting the answer."
                ]
            },
            {
                "h": "Hand off exceptions",
                "p": [
                    "Send late deliveries and contradictory tracking updates to the shipping owner. Pass along the question and last confirmed status so the customer can continue the conversation."
                ]
            },
            {
                "h": "Test on past conversations",
                "p": [
                    "Replay anonymised conversations before using the replies with shoppers. Review closed cases each day for wrong answers or customers returning with the same question."
                ],
                "ul": [
                    "Pre-sale question",
                    "Late parcel",
                    "Incomplete address"
                ]
            }
        ],
        "faq": [
            {
                "q": "هل أبدأ بكل الرسائل؟",
                "a": "ابدأ بأسئلة الشحن العامة حتى تثبت دقة الرد."
            },
            {
                "q": "متى أذكر موعداً محدداً؟",
                "a": "عندما يؤكده مصدر الطلب المعتمد."
            }
        ],
        "faq_en": [
            {
                "q": "Should every message be automated?",
                "a": "Start with general shipping questions and review accuracy first."
            },
            {
                "q": "When can I give a specific date?",
                "a": "Only when the approved order source confirms it."
            }
        ]
    },
    {
        "slug": "ai-customer-service-bot-for-stores",
        "title_ar": "بوت خدمة عملاء بالذكاء الاصطناعي للمتاجر",
        "title_en": "An AI Customer Service Bot for Online Stores",
        "desc_ar": "دليل صاحب المتجر لبناء قاعدة إجابات للبوت واختبار دقتها وتحديد الحالات التي تحتاج تدخلاً بشرياً قبل إطلاقه للزوار.",
        "desc_en": "Build a reliable store support bot with a small knowledge base, escalation rules and a repeatable acceptance test.",
        "date": "2026-11-23",
        "category_ar": "تشغيل المتاجر",
        "category_en": "Store operations",
        "reading_minutes": 2,
        "keywords": [
            "بوت خدمة عملاء بالذكاء الاصطناعي للمتاجر",
            "المتاجر السعودية"
        ],
        "body_ar": [
            {
                "h": "اختر مصادر الإجابة",
                "p": [
                    "اجمع سياسات الشحن والاستبدال وصفحات المنتجات المعتمدة. اكتب على كل مصدر تاريخ مراجعته واسم المسؤول عن تحديثه عند تغير السياسة."
                ]
            },
            {
                "h": "اختبر فهم السؤال",
                "p": [
                    "اسأل عن استبدال هدية باللهجة التي يستخدمها جمهورك. جرّب السؤال نفسه بصياغة مختصرة ثم أضف تفصيلاً يغيّر الحكم مثل فتح العبوة."
                ]
            },
            {
                "h": "حدّد متى يتوقف الرد",
                "p": [
                    "عندما تختلف سياسة الصفحة عن وصف المنتج، يطلب البوت مراجعة الموظف. أرسل للموظف السؤال والمصدرين المتعارضين حتى يصحح السبب."
                ]
            },
            {
                "h": "قِس جودة الحل",
                "p": [
                    "راجع صحة الإجابة واكتمال حل طلب الزائر. قد ينتهي الحوار سريعاً لأن العميل غادر وهو ما زال يحتاج مساعدة."
                ],
                "ul": [
                    "إجابة صحيحة",
                    "إجابة ناقصة",
                    "تحويل ناجح"
                ]
            }
        ],
        "body_en": [
            {
                "h": "Choose answer sources",
                "p": [
                    "Collect approved product pages and support policies. Give each source an owner and a review date so a change in the returns window reaches the bot as well as the storefront."
                ]
            },
            {
                "h": "Test shopper language",
                "p": [
                    "Ask about exchanging a gift using the words your customers use. Try a shorter version, then add a detail such as an opened package that changes the policy decision."
                ]
            },
            {
                "h": "Handle conflicting sources",
                "p": [
                    "If the product page contradicts the policy, route the question to a person. Include both sources in the handoff so the team can fix the underlying discrepancy."
                ]
            },
            {
                "h": "Measure resolution",
                "p": [
                    "Review whether the answer was accurate and whether it resolved the request. A short conversation can also mean the shopper gave up before receiving help."
                ],
                "ul": [
                    "Correct answer",
                    "Partial answer",
                    "Completed handoff"
                ]
            }
        ],
        "faq": [
            {
                "q": "من يحدّث الإجابات؟",
                "a": "صاحب السياسة عند كل تعديل مع إعادة اختبار الأسئلة المتأثرة."
            },
            {
                "q": "هل يعتمد البوت طلب استرداد؟",
                "a": "يسلّم الطلب للموظف المخوّل وفق إجراءات المتجر."
            }
        ],
        "faq_en": [
            {
                "q": "Who maintains answers?",
                "a": "The policy owner updates the source and reruns affected questions."
            },
            {
                "q": "Can the bot approve a refund?",
                "a": "Route the request to the authorised team under the store’s process."
            }
        ]
    },
    {
        "slug": "measure-store-inquiries-to-orders",
        "title_ar": "كيف تقيس تحوّل استفسارات المتجر إلى طلبات؟",
        "title_en": "Measure Store Inquiries That Become Paid Orders",
        "desc_ar": "طريقة عملية لربط الاستفسار بمصدر الزيارة والطلب المدفوع، واحتساب تكلفة العميل المؤهل دون عدّ المحادثة الواحدة مرتين.",
        "desc_en": "Connect referral sources, qualified inquiries and paid orders without double counting repeated conversations.",
        "date": "2026-11-23",
        "category_ar": "تشغيل المتاجر",
        "category_en": "Store operations",
        "reading_minutes": 2,
        "keywords": [
            "كيف تقيس تحوّل استفسارات المتجر إلى طلبات؟",
            "المتاجر السعودية"
        ],
        "body_ar": [
            {
                "h": "عرّف العميل المؤهل",
                "p": [
                    "اكتب شرطاً يستطيع موظفان تطبيقه بالطريقة نفسها. في متجر أثاث مثلاً، قد يكون الاستفسار مؤهلاً عندما يحدد الزائر القطعة ومدينة التسليم ويطلب عرضاً."
                ]
            },
            {
                "h": "اربط مراحل الطلب",
                "p": [
                    "احتفظ بمعرّف داخلي للاستفسار واربط به العرض والطلب عند الدفع. إذا عاد الشخص يسأل عن العرض نفسه، حدّث السجل الأصلي."
                ]
            },
            {
                "h": "احسب التكلفة",
                "p": [
                    "اقسم إنفاق الحملة على عدد الاستفسارات المؤهلة المنسوبة إليها خلال نفس الفترة. إذا كان العدد صفراً فاعرض الإنفاق والعدد كلّاً على حدة."
                ]
            },
            {
                "h": "اقرأ سبب التراجع",
                "p": [
                    "اختر عينة من الاستفسارات التي توقفت قبل الدفع. قارن وقت الرد وتوفر المنتج ووضوح تكلفة التوصيل قبل تغيير الإعلان."
                ],
                "ul": [
                    "مصدر الزيارة",
                    "مرحلة الاستفسار",
                    "مرجع الطلب"
                ]
            }
        ],
        "body_en": [
            {
                "h": "Define qualification",
                "p": [
                    "Write a rule two staff members can apply consistently. For example, a furniture inquiry might qualify when the shopper names the piece, gives a delivery city and asks for a quote."
                ]
            },
            {
                "h": "Link the stages",
                "p": [
                    "Keep an internal inquiry reference and attach the quote and confirmed payment to it. When the same shopper follows up about that quote, update the existing entry."
                ]
            },
            {
                "h": "Calculate the cost",
                "p": [
                    "Divide campaign spend by qualified inquiries attributed to it in the same observation period. When the count is zero, display spend and count separately."
                ]
            },
            {
                "h": "Investigate drop-off",
                "p": [
                    "Inspect a sample of inquiries that stopped before payment. Check reply delays, stock and delivery charges before deciding that the advertisement needs changing."
                ],
                "ul": [
                    "Visit source",
                    "Inquiry stage",
                    "Order reference"
                ]
            }
        ],
        "faq": [
            {
                "q": "كيف أعالج المصدر المجهول؟",
                "a": "ضعه في بند مستقل حتى يتوفر دليل يربطه بالحملة."
            },
            {
                "q": "متى أحسب البيع؟",
                "a": "بعد تأكيد الدفعة وربطها بالطلب."
            }
        ],
        "faq_en": [
            {
                "q": "What about unknown sources?",
                "a": "Keep them separate until attribution is supported by evidence."
            },
            {
                "q": "When should a sale count?",
                "a": "After confirming payment and linking it to the order."
            }
        ]
    },
    {
        "slug": "simulated-store-support-case",
        "title_ar": "دراسة حالة محاكاة لمتجر عطور سعودي",
        "title_en": "Simulated Case Study of a Saudi Perfume Store",
        "desc_ar": "مثال توضيحي لمتجر عطور افتراضي يتابع استفسارات الهدايا والشحن، مع بيانات محاكاة تشرح طريقة القياس من السؤال حتى الحل.",
        "desc_en": "A fictional perfume store shows how to classify gift and delivery questions and interpret a small simulated support batch.",
        "date": "2026-11-23",
        "category_ar": "تشغيل المتاجر",
        "category_en": "Store operations",
        "reading_minutes": 2,
        "keywords": [
            "دراسة حالة محاكاة لمتجر عطور سعودي",
            "المتاجر السعودية"
        ],
        "body_ar": [
            {
                "h": "سياق المحاكاة",
                "p": [
                    "مثال توضيحي. في متجر عطور افتراضي يسأل زائر إن كانت هديته تصل الخميس. يستطيع الفريق تأكيد وجود تغليف الهدايا، أما موعد الوصول فيعتمد على المدينة ووقت تجهيز الطلب."
                ]
            },
            {
                "h": "مسار المحادثة",
                "p": [
                    "يسأل الموظف عن المدينة ثم يراجع جدول التوصيل. إذا لم يجد موعداً مؤكداً يشرح المهلة المنشورة، ويعرض مراجعة مسؤول الشحن قبل أن يدفع العميل."
                ]
            },
            {
                "h": "نتيجة توضيحية",
                "p": [
                    "افترضنا عشرين محادثة اختبار. أجيب عن اثنتي عشرة من السياسة المعتمدة، وحُوّلت ثمانٍ إلى الموظف. نسبة الإجابات المباشرة في العينة ستون بالمئة."
                ]
            },
            {
                "h": "حدود الاستنتاج",
                "p": [
                    "الأرقام مولّدة للشرح. لمعرفة الأثر التجاري، يحتاج المتجر إلى مقارنة فترة فعلية مماثلة وقياس صحة الإجابات والطلبات المدفوعة وحالات التأخير."
                ],
                "ul": [
                    "تحقق من التغليف",
                    "راجع وجهة الشحنة",
                    "وثّق القرار"
                ]
            }
        ],
        "body_en": [
            {
                "h": "Simulation setup",
                "p": [
                    "This fictional exercise follows a perfume shopper asking whether a gift can arrive by Thursday. Gift wrapping is documented, while arrival depends on destination and dispatch time."
                ]
            },
            {
                "h": "Walk through the exchange",
                "p": [
                    "Ask for the city and consult the delivery schedule. If no date is confirmed, explain the published window and offer a shipping review before the customer pays."
                ]
            },
            {
                "h": "Read the sample",
                "p": [
                    "Of twenty invented test conversations, twelve were answered from the approved policy and eight were escalated. Direct answers therefore represent sixty percent of this sample."
                ]
            },
            {
                "h": "Interpret the result",
                "p": [
                    "These figures illustrate the calculation. To measure commercial impact, compare real periods of similar demand and review answer accuracy, paid orders and late deliveries."
                ],
                "ul": [
                    "Verify gift wrapping",
                    "Check the destination",
                    "Record the decision"
                ]
            }
        ],
        "faq": [
            {
                "q": "هل هذه تجربة عميل فعلي؟",
                "a": "هذه محاكاة تعليمية مبنية على سيناريو افتراضي."
            },
            {
                "q": "ما أول خطوة لتكرار الاختبار؟",
                "a": "اختر أسئلة مجهولة الهوية وحدد الإجابة المعتمدة لكل سؤال."
            }
        ],
        "faq_en": [
            {
                "q": "Is this a real customer result?",
                "a": "It is an educational simulation with invented data."
            },
            {
                "q": "How can a team repeat the exercise?",
                "a": "Select anonymised questions and record the approved answer for each one."
            }
        ]
    }
]
