"""Public service pages for /services/<slug>.

The Arabic copy expands the owner-supplied drafts in the service-pages brief.
It adds explanation of the same steps, limits, and privacy notes. It does not
add clients, testimonials, prices, statistics, or offers.

English copy is a translation of that same text so /en/ pages stay in English.
"""

from __future__ import annotations

AREA_SERVED = [
    {"@type": "Country", "name": "Saudi Arabia"},
    {"@type": "Country", "name": "United Arab Emirates"},
    {"@type": "Country", "name": "Kuwait"},
    {"@type": "Country", "name": "Bahrain"},
    {"@type": "Country", "name": "Qatar"},
    {"@type": "Country", "name": "Oman"},
]


def _sec(heading: str, paragraphs: list[str], bullets: list[str] | None = None) -> dict:
    block: dict = {"h": heading, "p": paragraphs}
    if bullets:
        block["ul"] = bullets
    return block


SERVICES: list[dict] = [
    {
        "slug": "automation",
        "name_ar": "أتمتة الأعمال",
        "name_en": "Business automation",
        "title_ar": "أتمتة الأعمال بالذكاء الاصطناعي في السعودية | النرجس",
        "title_en": "Business automation with AI in Saudi Arabia | Al-Narjis",
        "desc_ar": "نصمم لمنشأتك سير عمل مؤتمتًا يربط أنظمتك ويقلل المهام اليدوية المتكررة، بحلول تراعي بيئة العمل السعودية وأنظمة حماية البيانات.",
        "desc_en": "We design an automated workflow for your organization that connects your systems and reduces repetitive manual work, with solutions that respect the Saudi workplace and data-protection rules.",
        "h1_ar": "أتمتة الأعمال بالذكاء الاصطناعي",
        "h1_en": "Business automation with AI",
        "card_ar": "سير عمل يربط أنظمتك ويقلل المهام اليدوية المتكررة، مع بقاء القرار عند فريقك.",
        "card_en": "A workflow that connects your systems and cuts repetitive manual work, while decisions stay with your team.",
        "related": ["chatbots", "content-writing"],
        "sections_ar": [
            _sec("", [
                "تقضي فرق العمل في كثير من المنشآت وقتًا طويلًا في مهام متكررة: نسخ البيانات بين الأنظمة، وإعداد التقارير الدورية، ومتابعة الطلبات والفواتير، والرد على الاستفسارات المتشابهة. هذه المهام ضرورية، لكنها تستهلك جهدًا كان يمكن توجيهه إلى ما يصنع قيمة حقيقية للعميل. في النرجس نساعد المنشآت في المملكة العربية السعودية والخليج على تحويل هذه الأعمال الروتينية إلى سير عمل مؤتمت، واضح، وقابل للمراجعة.",
                "الأتمتة هنا ليست استبدالًا للفريق، وليست وعدًا بأن كل إجراء في المنشأة سيختفي من يومه. هي ترتيب للخطوات التي تتكرر بشكلها نفسه، حتى ينفّذها النظام وفق قاعدة متفق عليها، ويبقى الموظف في الموضع الذي يحتاج حكمًا أو اعتمادًا. نبدأ من طريقة عملكم الحالية، لا من أداة جاهزة نفرضها عليكم.",
            ]),
            _sec("ما المقصود بأتمتة الأعمال؟", [
                "أتمتة الأعمال هي استخدام البرمجيات وأدوات الذكاء الاصطناعي لتنفيذ خطوات محددة تلقائيًا وفق قواعد متفق عليها. قد تكون الأتمتة بسيطة، مثل إرسال إشعار عند وصول طلب جديد، وقد تكون أعمق، مثل قراءة مستند وارد واستخراج بياناته وتسجيلها في النظام المناسب ثم إحالته للموظف المختص للاعتماد. المهم أن يبقى الإنسان في موضع القرار، وأن تتولى الأنظمة التنفيذ المتكرر.",
                "الفرق بين الأتمتة المفيدة والفوضى الرقمية هو وضوح القاعدة. إذا كانت الخطوة تُنجز بالطريقة نفسها في كل مرة، ويمكن وصفها بجملة يفهمها من يعمل عليها اليوم، فهي مرشحة جيدة. أما إذا كانت الخطوة تتغير بحسب علاقة العميل أو تقدير المدير، فنتركها للإنسان ونؤتمت ما حولها: جمع المعلومات، وترتيبها، وتذكير صاحب القرار.",
                "في بيئة العمل السعودية يكثر التنقل بين البريد والنماذج والجداول وطلبات الاعتماد. الأتمتة الجيدة لا تطلب منكم هجر هذه الأدوات دفعة واحدة. تربط ما يمكن ربطه، وتوثق ما لا يمكن ربطه، حتى يعرف الفريق أين تنتهي الآلة وأين تبدأ مراجعته.",
            ]),
            _sec("كيف نعمل معك؟", [
                "لا نبدأ ببناء سير العمل قبل أن نفهم الإجراء كما يجري اليوم. الخطة التالية هي ترتيب العمل، لا قائمة أدوات.",
                "فهم الإجراءات الحالية: نجلس مع فريقك لنفهم كيف تسير الأعمال اليوم، وأين تتكرر الخطوات، وأين تحدث الأخطاء أو التأخير. نطلب أمثلة حقيقية من آخر فترة عمل، لا وصفًا نظريًا، لأن الفجوة بين الدليل المكتوب والممارسة اليومية هي غالبًا مكان التعطل.",
                "تحديد الأولويات: لا نؤتمت كل شيء دفعة واحدة؛ بل نبدأ بالإجراءات الأوضح أثرًا والأقل تعقيدًا. الإجراء الواضح هو الذي له بداية ونهاية ومالك داخل الفريق. إن كان الأثر كبيرًا والتعقيد منخفضًا، فهو أول مرشح. وإن كان الأثر ضبابيًا، نؤجله حتى تتضح القاعدة.",
                "التصميم والبناء: نصمم سير العمل ونربط الأدوات التي تستخدمها منشأتك قدر الإمكان، مع توثيق كل خطوة. التوثيق جزء من التسليم، لا ملحقًا يُكتب لاحقًا. يقرأ منه الموظف الجديد ماذا يحدث عند وصول طلب، ومن يعتمد، وماذا يفعل النظام إذا نقص حقل.",
                "الاختبار مع فريقك: نجرب الحل على حالات فعلية بمشاركة المستخدمين قبل اعتماده. الاختبار هنا ليس عرضًا داخليًا عندنا، بل تشغيلًا على أمثلة من عملكم، حتى يظهر الاستثناء قبل أن يعتمد الفريق على المسار.",
                "التسليم والتدريب: نسلم الحل مع شرح واضح لطريقة استخدامه ومراقبته وتعديله. نشرح أين ينظر المسؤول ليعرف أن السير يعمل، وكيف يوقف خطوة إذا تغيّرت السياسة، ومن يملك صلاحية التعديل.",
            ]),
            _sec("أمثلة على ما يمكن أتمتته", [
                "الأمثلة التالية أنماط شائعة في المنشآت، لا قائمة مغلقة ولا وعدًا بأن كل بند يناسبكم. نختار منها ما يطابق إجراءاتكم بعد الدراسة.",
            ], [
                "استقبال الطلبات من النماذج والبريد وتوزيعها على الفرق المختصة.",
                "استخراج البيانات من المستندات والفواتير وتنظيمها.",
                "إعداد تقارير دورية وإرسالها لأصحاب العلاقة.",
                "تذكيرات المتابعة والمواعيد والمهام الداخلية.",
                "ربط أدوات العمل المختلفة لتقليل الإدخال اليدوي المكرر.",
            ]),
            _sec("الخصوصية وحماية البيانات", [
                "نتعامل مع بيانات منشأتك بمسؤولية، ونصمم الحلول بحيث تجمع ما يلزم فقط من البيانات، مع مراعاة نظام حماية البيانات الشخصية في المملكة وسياسات منشأتك الداخلية. ونناقش معك منذ البداية أين تُخزَّن البيانات ومن يملك صلاحية الوصول إليها.",
                "هذا النقاش يسبق البناء. إذا كان الإجراء لا يحتاج رقم هوية أو محتوى رسالة كاملة، لا نطلب تخزينهما «للاحتياط». وإذا كانت السياسة الداخلية عندكم أضيق من الحد النظامي، نلتزم بالأضيق. ونوضح أي خطوة ترسل بياناتًا إلى أداة خارجية قبل تفعيلها، حتى يكون الاعتماد قرارًا منكم لا مفاجأة بعد التشغيل.",
            ]),
            _sec("لماذا النرجس؟", [
                "نحن شركة سعودية من الرياض، نفهم لغة السوق المحلي وطبيعة الإجراءات في المنشآت السعودية، ونجمع بين خبرة الأتمتة وخدمات المحتوى والتصميم، مما يتيح لك حلًا متكاملًا بدل التنسيق بين جهات متعددة. ونحرص على الوضوح: نشرح ما يمكن للأتمتة فعله وما لا يمكنها، دون وعود مبالغ فيها.",
                "إن كان جزء من الإجراء محتوى يقرأه العميل، يمكن أن يُكتب مع خدمة كتابة المحتوى. وإن كان جزء منه ردًا متكررًا على سؤال واحد، فموضعه بوت المحادثة لا سير داخلي صامت. نفصل بين الاثنين حتى لا يختلط مسار الموظف بمسار العميل.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "Teams in many organizations spend a long time on repetitive work: copying data between systems, preparing periodic reports, following up orders and invoices, and answering questions that look the same. The work matters, but it uses effort that could go to what actually creates value for the customer. At Al-Narjis we help organizations in Saudi Arabia and the Gulf turn that routine into a workflow that is automated, clear, and open to review.",
                "Automation here is not a replacement for the team. It orders the steps that repeat in the same form, under an agreed rule, and the person stays where judgment or approval is required. We start from how you work today.",
            ]),
            _sec("What does business automation mean?", [
                "Business automation is the use of software and AI tools to carry out defined steps automatically, under rules you have agreed. It can be simple, such as a notice when a new request arrives, or deeper, such as reading an incoming document, extracting its data, recording it in the right system, and handing it to the right person for approval. What matters is that the human stays at the point of decision, and the systems take the repetitive execution.",
                "The difference between useful automation and digital clutter is a clear rule. If a step is done the same way every time, it is a good candidate. If it changes with a customer's relationship or a manager's judgment, we leave it to a person and automate what surrounds it: gathering the information, arranging it, and reminding the person who decides.",
            ]),
            _sec("How we work with you", [
                "We do not build the workflow before we understand the procedure as it actually runs. The plan below is an order of work, not a catalogue of tools.",
                "Understanding the current procedure: we sit with your team to see how work moves today, where steps repeat, and where delay shows up. We ask for real recent examples, not a theoretical description.",
                "Setting priorities: we do not automate everything at once. We start where the effect is clearest and the complexity is lowest. A clear procedure has a beginning, an end, and an owner. If the effect is vague, we wait until the rule is clear.",
                "Design and build: we design the workflow, connect the tools you already use where that is possible, and document every step. A new colleague should be able to read what happens when a request arrives and who approves it.",
                "Testing with your team: we try the solution on real cases with the people who will use it, before it is adopted, so the exception appears before the team relies on the path.",
                "Handover and training: we deliver the solution with a clear explanation of how to use it, watch it, and change it, including how to stop a step if policy changes.",
            ]),
            _sec("Examples of what can be automated", [
                "The examples below are common patterns in organizations. They are not a closed list, and they are not a promise that every item fits you. We choose from them what matches your procedures after the study.",
            ], [
                "Receiving requests from forms and email and routing them to the right teams.",
                "Extracting data from documents and invoices and organizing it.",
                "Preparing periodic reports and sending them to the people who need them.",
                "Reminders for follow-up, appointments, and internal tasks.",
                "Connecting different work tools so the same data is not typed twice.",
            ]),
            _sec("Privacy and data protection", [
                "We treat your organization's data responsibly. We design the solution so it collects only the data the procedure needs, with regard to the Personal Data Protection Law in the Kingdom and your own internal policies. From the start we discuss where the data is stored and who is allowed to reach it.",
                "That discussion comes before the build. If the procedure does not need a piece of data, we do not store it just in case. If your internal policy is stricter than the legal minimum, we follow the stricter rule, and we explain any step that sends data to an external tool before it is switched on.",
            ]),
            _sec("Why Al-Narjis?", [
                "We are a Saudi company from Riyadh. We understand local procedures, and we combine automation with content and design so you are not coordinating several parties. We explain what automation can do and what it cannot, without inflated promises.",
                "If part of the procedure is text a customer reads, it can be written with the content service. If part of it is a repeated answer to one question, that belongs to a chatbot, not to a silent internal flow. We keep the two apart so the employee's path and the customer's path do not blur.",
            ]),
        ],
        "faq_ar": [
            {"q": "هل تحتاج منشأتي إلى أنظمة معينة لتبدأ الأتمتة؟", "a": "لا يشترط ذلك. نبدأ بدراسة الأدوات التي تستخدمها حاليًا ونقترح الحل الأنسب لها. إن كانت الأداة الحالية تكفي، نبني عليها. وإن كانت تعيق الإجراء، نقول ذلك قبل أن نطلب استبدالها."},
            {"q": "هل ستستبدل الأتمتة الموظفين؟", "a": "الهدف تخفيف المهام المتكررة عن فريقك ليتفرغ للأعمال التي تحتاج إلى خبرة بشرية وقرار. الاعتماد، والاستثناء، والعلاقة مع العميل تبقى عند الإنسان."},
            {"q": "كم يستغرق تنفيذ مشروع أتمتة؟", "a": "يختلف ذلك بحسب حجم الإجراءات وتعقيدها، ونوضح لك خطة زمنية بعد دراسة احتياجك. لا نعلن مدة ثابتة قبل أن نرى الإجراء."},
            {"q": "كيف تحمون بيانات منشأتي؟", "a": "نلتزم بجمع الحد الأدنى من البيانات اللازمة، ونراعي نظام حماية البيانات الشخصية وسياسات منشأتك. ونحدد معك مكان التخزين وصلاحية الوصول قبل البناء."},
            {"q": "كيف أبدأ؟", "a": "تحدث مع بوت النرجس في الموقع أو راسلنا عبر البريد الإلكتروني، وسنتواصل معك لفهم احتياجك."},
        ],
        "faq_en": [
            {"q": "Does my organization need specific systems before automation can start?", "a": "No. We start by studying the tools you already use and propose what fits them. If the current tool is enough, we build on it. If it blocks the procedure, we say so before asking you to replace it."},
            {"q": "Will automation replace employees?", "a": "The aim is to lift repetitive tasks off your team so people can spend time on work that needs human experience and a decision. Approval, exceptions, and the customer relationship stay with a person."},
            {"q": "How long does an automation project take?", "a": "It depends on the size and complexity of the procedures. We give you a time plan after we have studied the need. We do not announce a fixed duration before we have seen the procedure."},
            {"q": "How do you protect my organization's data?", "a": "We collect only the data the procedure needs, and we respect the Personal Data Protection Law and your own policies. We agree storage and access with you before the build."},
            {"q": "How do I start?", "a": "Talk to the Al-Narjis bot on the site, or email us, and we will come back to you to understand the need."},
        ],
    },
    {
        "slug": "chatbots",
        "name_ar": "بوتات المحادثة الذكية",
        "name_en": "Intelligent chatbots",
        "title_ar": "بوتات محادثة ذكية بالعربية للمنشآت في السعودية | النرجس",
        "title_en": "Arabic chatbots for organizations in Saudi Arabia | Al-Narjis",
        "desc_ar": "نبني بوتات محادثة تفهم العربية واللهجة السعودية، تجيب عملاءك على مدار الساعة وتحيل الحالات المعقدة لفريقك.",
        "desc_en": "We build chatbots that understand Arabic and the Saudi dialect, answer your customers around the clock, and hand complex cases to your team.",
        "h1_ar": "بوتات المحادثة الذكية بالعربية",
        "h1_en": "Intelligent chatbots in Arabic",
        "card_ar": "بوت يفهم العربية واللهجة السعودية، ويجيب من معلوماتكم المعتمدة، ويحيل ما لا يعرفه.",
        "card_en": "A bot that understands Arabic and the Saudi dialect, answers from your approved information, and hands over what it does not know.",
        "related": ["automation", "content-writing"],
        "sections_ar": [
            _sec("", [
                "يتوقع العملاء اليوم إجابة سريعة في أي وقت، سواء سألوا عن خدمة أو حالة طلب أو موعد. وكثير من هذه الأسئلة متكرر، يمكن الإجابة عنه بدقة إذا كانت المعلومات منظمة. في النرجس نصمم بوتات محادثة ذكية تفهم العربية الفصحى واللهجة السعودية، وتعتمد على معلومات منشأتك المعتمدة، لتجيب عملاءك بوضوح ولطف.",
                "البوت الذي نبنيه ليس صفحة عامة تجيب عن كل شيء. هو واجهة لمعلومات وافقتم عليها: دليل الخدمة، والسياسة، والأسئلة التي يتكرر طرحها. إذا خرج السؤال عن هذا النطاق، يتوقف البوت عن التخمين. هذا الحد هو ما يجعله صالحًا للمنشأة، لا مجرد تجربة محادثة.",
            ]),
            _sec("ما الذي يقدمه بوت المحادثة لمنشأتك؟", [
                "القيمة في تخفيف السؤال المتكرر عن الموظف، لا في إخفاء الموظف عن العميل. هذه الاستخدامات هي ما نبنيه عادة، بعد أن نتفق على النص المعتمد.",
            ], [
                "إجابة الأسئلة الشائعة عن خدماتك وسياساتك في أي وقت.",
                "جمع بيانات الاستفسار الأساسية قبل تحويله للموظف المختص.",
                "توجيه العميل إلى الصفحة أو الخدمة المناسبة.",
                "دعم أكثر من لغة عند الحاجة، كالعربية والإنجليزية.",
                "تحويل الحالات المعقدة أو الحساسة إلى فريقك البشري.",
            ]),
            _sec("بوت يتحدث بلسان منشأتك", [
                "نحرص على أن يعكس البوت هوية منشأتك ونبرتها: رسميًا حين يلزم، وودودًا حين يناسب. ونبني إجاباته على مصادر تعتمدها أنت، كدليل الخدمات والسياسات والأسئلة الشائعة، حتى لا يقدم معلومات غير دقيقة. وحين لا يجد البوت إجابة موثوقة، يعترف بذلك ويحيل السؤال إلى فريقك بدل التخمين.",
                "النبرة ليست زينة تُضاف في النهاية. نحدد معكم الكلمات التي تستخدمونها والكلمات التي لا تريدون ظهورها، ومتى يكون الرد مختصرًا ومتى يحتاج تفصيلًا. المصدر المعتمد يُراجع قبل الإطلاق، لأن البوت سيعيد هذا النص مرات كثيرة. خطأ صغير في السياسة يتضاعف مع كل محادثة.",
                "الإحالة إلى الإنسان جزء من التصميم لا حالة فشل. نحدد الأسئلة التي لا يجوز للبوت أن يحسمها: شكوى، أو استثناء، أو طلب خارج النص المعتمد. في هذه الحالات يوضح البوت أنه مساعد آلي، ويجمع ما يلزم ليفهم الموظف السياق، ثم يسلّم المحادثة.",
            ]),
            _sec("مراحل العمل", [
                "جمع المعرفة: نجمع معك المعلومات التي سيعتمد عليها البوت وننظمها. إن كانت المعرفة مبعثرة بين ملفات قديمة وردود موظفين، فأول عمل هو توحيدها في مصدر واحد تستطيعون تحديثه.",
                "تصميم المحادثة: نحدد سيناريوهات الأسئلة ونبرة الحديث ومتى يتم التحويل للبشر. السيناريو الجيد له مسار سعيد ومسار حين لا يعرف البوت، حتى لا يعلق العميل في حلقة.",
                "البناء والربط: نبني البوت ونربطه بموقعك أو القنوات المتفق عليها. الربط بقناة إضافية نناقشه على حدة، ولا نفترض قناة لم تتفقوا عليها.",
                "الاختبار: نختبر البوت بأسئلة واقعية بالفصحى واللهجة المحلية. الاختبار يشمل السؤال الواضح والسؤال الناقص والسؤال الخارج عن النطاق.",
                "المتابعة والتحسين: نراجع المحادثات المجهولة الهوية لتحسين الإجابات باستمرار. المراجعة تبحث عن السؤال الذي تكرر بلا جواب موثوق، لا عن تتبع شخص بعينه.",
            ]),
            _sec("الخصوصية والشفافية", [
                "يوضح البوت للمستخدم أنه مساعد آلي، ولا يجمع إلا البيانات اللازمة لخدمة الاستفسار. ونصمم الحل بما يراعي نظام حماية البيانات الشخصية في المملكة، مع إمكانية إعداد سياسة الاحتفاظ بالبيانات بما يناسب منشأتك.",
                "نسأل قبل الإطلاق: ما الذي يُحفظ، ولأي غرض، ولكم من الوقت، ومن يطّلع عليه. إن كان الاستفسار يُحل دون اسم أو رقم، لا نجعل هذه الحقول إلزامية. والعميل يرى أنه يتحدث إلى مساعد آلي منذ البداية، لا بعد أن يرسل بياناته.",
            ]),
            _sec("تجربة عملية", [
                "يمكنك تجربة ما نقدمه مباشرة: بوت النرجس الموجود في موقعنا مثال حي على بوتات المحادثة التي نبنيها. اسأله عن خدماتنا وتعرف على طريقة عمله. هو يجيب من معلومات الموقع، ويحوّلك إلى البريد حين لا يملك جوابًا موثوقًا.",
                "هذه التجربة توضح الشكل، لا أنها نسخة من بوت منشأتك. بوتكم يُبنى على معرفتكم ونبرتكم وحدودكم. ما تستعيرونه من المثال هو السلوك: جواب واضح حين تُوجد المعلومة، وإحالة صادقة حين لا تُوجد.",
            ]),
            _sec("لماذا النرجس؟", [
                "لأننا فريق سعودي يفهم طريقة حديث العملاء في المملكة، ونهتم بجودة اللغة العربية في كل إجابة، ونصمم البوت ليكون مساعدًا موثوقًا لا مصدرًا للالتباس. نقرأ الجملة كما يقرأها عميل في الرياض، لا كما تخرجها أداة بلا مراجعة.",
                "وإذا كان خلف السؤال المتكرر إجراء داخلي متعب، كتسجيل الطلب ثم توزيعه، فذلك عمل الأتمتة لا عمل البوت وحده. نربط الخدمتين حين يكون الربط أوضح من بناء واجهتين لا تتكلمان.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "Customers now expect a quick answer at any hour, whether they ask about a service, an order, or an appointment. Many of those questions repeat, and they can be answered accurately when the information is organized. At Al-Narjis we design intelligent chatbots that understand formal Arabic and the Saudi dialect, and that rely on information your organization has approved, so they answer your customers clearly and politely.",
                "The bot we build is a front for information you have accepted: the service guide, the policy, and the questions people ask again and again. If the question leaves that scope, the bot stops guessing.",
            ]),
            _sec("What a chatbot gives your organization", [
                "The value is taking the repeated question off the employee, not hiding the employee from the customer. These are the uses we usually build, after the approved text is agreed.",
            ], [
                "Answers to common questions about your services and policies at any time.",
                "Collection of the basic enquiry details before it is passed to the right person.",
                "Direction of the customer to the right page or service.",
                "Support for more than one language when you need it, such as Arabic and English.",
                "Handover of complex or sensitive cases to your human team.",
            ]),
            _sec("A bot that speaks in your organization's voice", [
                "We take care that the bot reflects your identity and tone: formal when it should be, warmer when that fits. We build its answers on sources you approve, such as the service guide, the policies, and the frequently asked questions, so it does not present inaccurate information. When it does not find a reliable answer, it says so and hands the question to your team instead of guessing.",
                "Tone is not decoration added at the end. We agree the words you use, the words you do not want, and when a reply should be short. The approved source is reviewed before launch, because the bot will repeat it. Handover to a person is part of the design: a complaint, an exception, or a request outside the approved text is passed on, with enough context for the employee.",
            ]),
            _sec("Stages of the work", [
                "Gathering the knowledge: we collect the information the bot will rely on and put it in one source you can update.",
                "Designing the conversation: we set the scenarios, the tone, and when a person takes over, including a path for when the bot does not know, so the customer is not stuck in a loop.",
                "Build and connection: we build the bot and connect it to your site or to channels you have agreed. We do not assume a channel you have not agreed.",
                "Testing: we test with realistic questions in formal Arabic and in the local dialect, including the incomplete question and the question that is out of scope.",
                "Follow-up: we review anonymized conversations for questions that kept arriving without a reliable answer. The review is not a way to track a named person.",
            ]),
            _sec("Privacy and transparency", [
                "The bot tells the user it is an automated assistant, and it collects only the data the enquiry needs. We design the solution with regard to the Personal Data Protection Law in the Kingdom, and the retention policy can be set to suit your organization.",
                "Before launch we ask what is stored, for what purpose, for how long, and who can see it. If the enquiry can be resolved without a name or a number, we do not make those fields mandatory. The customer sees that they are talking to an automated assistant from the start, not after they have sent their details.",
            ]),
            _sec("A working example", [
                "You can try what we offer directly. The Al-Narjis bot on our site is a live example of the chatbots we build. Ask it about our services and see how it behaves. It answers from the site's information, and it hands you to email when it does not have a reliable answer.",
                "That trial shows the shape. It is not a copy of your organization's bot. Yours is built on your knowledge, your tone, and your limits. What you borrow from the example is the behavior: a clear answer when the information exists, and an honest handover when it does not.",
            ]),
            _sec("Why Al-Narjis?", [
                "Because we are a Saudi team that understands how customers in the Kingdom speak. We care about the quality of Arabic in every answer, and we design the bot to be a reliable assistant rather than a source of confusion. We read the sentence as a customer in Riyadh would read it, not as a tool emits it with no review.",
                "If a repeated question sits on top of a tiring internal procedure, such as logging a request and routing it, that is automation work and not the bot alone. We connect the two services when the connection is clearer than building two fronts that do not speak to each other.",
            ]),
        ],
        "faq_ar": [
            {"q": "هل يفهم البوت اللهجة السعودية؟", "a": "نصمم البوت ونختبره ليفهم الفصحى والتعابير الشائعة في اللهجة السعودية. الاختبار يشمل أسئلة واقعية لا قائمة مصطلحات فقط."},
            {"q": "هل يمكن ربط البوت بموقعي؟", "a": "نعم، يمكن إضافته إلى موقعك، ونناقش معك القنوات الأخرى المناسبة. لا نفترض قناة لم نتفق عليها."},
            {"q": "ماذا يحدث إذا لم يعرف البوت الإجابة؟", "a": "يوضح ذلك للعميل ويحيل الاستفسار إلى فريقك بدل تقديم معلومة غير مؤكدة."},
            {"q": "هل يمكنني تعديل معلومات البوت لاحقًا؟", "a": "نعم، نصمم مصادر المعرفة بحيث يسهل تحديثها عند تغير خدماتك أو سياساتك. التحديث جزء من التصميم لأن النص سيتغير."},
            {"q": "كيف أبدأ؟", "a": "جرّب بوت النرجس في الموقع واطلب منه التواصل معنا، أو راسلنا عبر البريد الإلكتروني."},
        ],
        "faq_en": [
            {"q": "Does the bot understand the Saudi dialect?", "a": "We design and test the bot so it understands formal Arabic and expressions that are common in the Saudi dialect. The test uses realistic questions, not only a term list."},
            {"q": "Can the bot be connected to my website?", "a": "Yes. It can be added to your site, and we discuss any other channel that fits. We do not assume a channel we have not agreed."},
            {"q": "What happens if the bot does not know the answer?", "a": "It tells the customer, and it hands the enquiry to your team instead of offering an unconfirmed fact."},
            {"q": "Can I change the bot's information later?", "a": "Yes. We design the knowledge sources so they are easy to update when your services or policies change. Updating is part of the design, because the text will change."},
            {"q": "How do I start?", "a": "Try the Al-Narjis bot on the site and ask it to put you in touch with us, or email us."},
        ],
    },
]


# The remaining four services are appended below so each page stays editable
# on its own. They follow the same shape.
from src.services import public_services_rest as _rest  # noqa: E402

SERVICES.extend(_rest.REST)

BY_SLUG = {item["slug"]: item for item in SERVICES}


ARTICLE_LINKS: dict[str, list[dict]] = {
    "ai-agents-for-saudi-businesses": [
        {
            "slug": "automation",
            "bridge_ar": "إن كانت المهمة التي وصفتها إجراءً داخليًا يتكرر، فصفحة أتمتة الأعمال تشرح كيف نحولها إلى سير واضح يبقى القرار فيه عند فريقك.",
            "bridge_en": "If the task you described is an internal procedure that repeats, the business automation page explains how we turn it into a clear workflow where the decision stays with your team.",
        },
    ],
    "ai-customer-service-saudi": [
        {
            "slug": "chatbots",
            "bridge_ar": "صفحة بوتات المحادثة تشرح كيف نبني بوتًا يجيب بالعربية من نص معتمد، ويحيل ما لا يعرفه إلى فريقك بدل التخمين.",
            "bridge_en": "The chatbots page explains how we build a bot that answers in Arabic from approved text, and hands over what it does not know instead of guessing.",
        },
    ],
    "ai-automation-for-saudi-stores": [
        {
            "slug": "automation",
            "bridge_ar": "ما يصلح تشغيله في المتجر من استقبال الطلبات ومتابعتها موضح في صفحة أتمتة الأعمال، بحدّ أن التسعير والاسترجاع يبقيان عندكم.",
            "bridge_en": "What can actually run in a store, from receiving requests to following them up, is set out on the business automation page, with pricing and returns staying with you.",
        },
        {
            "slug": "chatbots",
            "bridge_ar": "الرد على السؤال المتكرر عن الطلب له صفحة مستقلة: بوتات المحادثة، وفيها متى يتوقف البوت ويحوّل الحالة لموظف.",
            "bridge_en": "The repeated question about an order has its own page: chatbots, including when the bot stops and hands the case to a person.",
        },
    ],
    "ai-for-clinics-and-healthcare": [
        {
            "slug": "chatbots",
            "bridge_ar": "الرد على سؤال الموعد، بلا لمس السجل الطبي، قريب من طريقة بناء بوت المحادثة: نص معتمد، وإحالة حين يخرج السؤال عن النطاق.",
            "bridge_en": "Answering an appointment question, without touching the medical record, is close to how we build a chatbot: approved text, and a handover when the question leaves that scope.",
        },
    ],
    "content-calendar-with-ai": [
        {
            "slug": "content-writing",
            "bridge_ar": "التقويم ينظم النشر، والنص نفسه له خدمة مستقلة في صفحة كتابة المحتوى: لغة سليمة، ومراجعة قبل التسليم.",
            "bridge_en": "A calendar organizes publishing. The text itself has its own service on the content writing page: sound language, and a review before delivery.",
        },
    ],
    "ai-seo-for-arabic-businesses": [
        {
            "slug": "content-writing",
            "bridge_ar": "صفحة لكل نية تحتاج نصًا يُكتب للقارئ أولًا. هذا عمل صفحة كتابة المحتوى، لا حشو كلمات في مقال واحد.",
            "bridge_en": "A page for each intent needs text written for the reader first. That is the work of the content writing page, not keyword stuffing in a single article.",
        },
        {
            "slug": "translation",
            "bridge_ar": "إذا كانت الصفحة نفسها ستُقرأ بالإنجليزية، فالتوطين موضح في صفحة الترجمة، مع مراجعة بشرية لا نقلًا حرفيًا.",
            "bridge_en": "If the same page will also be read in English, localization is set out on the translation page, with a human review rather than a literal transfer.",
        },
    ],
    "how-to-choose-ai-agents": [
        {
            "slug": "automation",
            "bridge_ar": "سؤال «ما المهمة التي تعيدها كل أسبوع؟» هو نفسه سؤال أولوية الأتمتة في صفحة أتمتة الأعمال.",
            "bridge_en": "The question «which task do you repeat every week?» is the same priority question on the business automation page.",
        },
    ],
    "ai-agents-vs-agency": [
        {
            "slug": "graphic-design",
            "bridge_ar": "الهوية البصرية والحملة غير المتكررة مكانهما التصميم البشري. صفحة التصميم الجرافيكي توضح نطاق هذا العمل وحدود التسليم.",
            "bridge_en": "A visual identity and a one-off campaign belong with a human designer. The graphic design page sets out the scope of that work and the limits of delivery.",
        },
        {
            "slug": "content-writing",
            "bridge_ar": "المحتوى المتكرر الذي يخدم صفحة الخدمة، لا الحملة العابرة، موضح في صفحة كتابة المحتوى.",
            "bridge_en": "The repeating content that serves a service page, rather than a one-off campaign, is set out on the content writing page.",
        },
    ],
    "ai-agents-for-saudi-hr-and-recruitment": [
        {
            "slug": "content-writing",
            "bridge_ar": "وصف الوظيفة ونص المراسلة يبدأ كنص يُراجع. صفحة كتابة المحتوى تشرح كيف نكتب النص ونعرضه عليكم قبل استخدامه.",
            "bridge_en": "A job description and a message start as text that is reviewed. The content writing page explains how we write the text and show it to you before it is used.",
        },
        {
            "slug": "automation",
            "bridge_ar": "متابعة الوثائق الناقصة وتذكير المواعيد إجراء متكرر. حدوده، ومنها بقاء قرار التوظيف عند الإنسان، موضحة في صفحة أتمتة الأعمال.",
            "bridge_en": "Chasing missing documents and reminding people of dates is a repeated procedure. Its limits, including that the hiring decision stays with a person, are set out on the business automation page.",
        },
    ],
    "ai-agents-for-saudi-restaurants-and-hospitality": [
        {
            "slug": "chatbots",
            "bridge_ar": "سؤال الموعد والموقع والمكوّن المتكرر يناسبه بوت يجيب من نص معتمد. صفحة بوتات المحادثة توضح متى تُحال الشكوى الحساسة إلى موظف.",
            "bridge_en": "A repeated question about hours, location, or ingredients suits a bot that answers from approved text. The chatbots page explains when a sensitive complaint is handed to a person.",
        },
        {
            "slug": "content-writing",
            "bridge_ar": "وصف الطبق والمنشور المتسق مع النبرة عمل كتابة، لا رد آلي. تفاصيله في صفحة كتابة المحتوى.",
            "bridge_en": "A dish description and a post that stays in your tone are writing work, not an automatic reply. The detail is on the content writing page.",
        },
    ],
}


def get_service(slug: str) -> dict | None:
    return BY_SLUG.get(slug)


def related_services(service: dict) -> list[dict]:
    return [BY_SLUG[slug] for slug in service.get("related", []) if slug in BY_SLUG]


def links_for_article(slug: str) -> list[dict]:
    items = []
    for link in ARTICLE_LINKS.get(slug, []):
        service = BY_SLUG.get(link["slug"])
        if service is None:
            continue
        items.append({**link, "name_ar": service["name_ar"], "name_en": service["name_en"]})
    return items


def service_jsonld(service: dict, lang: str) -> dict:
    arabic = lang == "ar"
    name = service["name_ar"] if arabic else service["name_en"]
    description = service["desc_ar"] if arabic else service["desc_en"]
    faqs = service["faq_ar"] if arabic else service["faq_en"]
    provider_name = "النرجس للذكاء الاصطناعي" if arabic else "Al-Narjis AI"
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Service",
                "name": name,
                "serviceType": name,
                "description": description,
                "url": f"https://karmaai.online/{lang}/services/{service['slug']}",
                "inLanguage": lang,
                "provider": {
                    "@type": "ProfessionalService",
                    "@id": "https://karmaai.online/#business",
                    "name": provider_name,
                },
                "areaServed": AREA_SERVED,
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


def visible_words(service: dict, lang: str) -> int:
    parts = [service[f"h1_{lang}"], service[f"desc_{lang}"]]
    for block in service[f"sections_{lang}"]:
        parts.append(block.get("h", ""))
        parts.extend(block.get("p", []))
        parts.extend(block.get("ul", []))
    for item in service[f"faq_{lang}"]:
        parts.append(item["q"])
        parts.append(item["a"])
    return len(" ".join(parts).split())
