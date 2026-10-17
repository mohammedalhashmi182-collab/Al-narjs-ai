"""The remaining public service pages. Same editorial rules as public_services."""

from __future__ import annotations


def _sec(heading: str, paragraphs: list[str], bullets: list[str] | None = None) -> dict:
    block: dict = {"h": heading, "p": paragraphs}
    if bullets:
        block["ul"] = bullets
    return block


REST: list[dict] = [
    {
        "slug": "graphic-design",
        "name_ar": "التصميم الجرافيكي",
        "name_en": "Graphic design",
        "title_ar": "تصميم جرافيك وهوية بصرية للمنشآت في السعودية | النرجس",
        "title_en": "Graphic design and visual identity for Saudi organizations | Al-Narjis",
        "desc_ar": "تصاميم جرافيك وهويات بصرية تعبر عن منشأتك: شعارات، مواد تسويقية، ومحتوى بصري لوسائل التواصل بطابع يناسب السوق السعودي.",
        "desc_en": "Graphic design and visual identities that express your organization: logos, marketing materials, and social visuals with a character that fits the Saudi market.",
        "h1_ar": "التصميم الجرافيكي والهوية البصرية",
        "h1_en": "Graphic design and visual identity",
        "card_ar": "شعارات ومواد تسويقية ومحتوى بصري، مع عناية بالخط العربي واتجاه الكتابة.",
        "card_en": "Logos, marketing materials, and social visuals, with care for Arabic type and reading direction.",
        "related": ["ui-ux-design", "content-writing"],
        "sections_ar": [
            _sec("", [
                "الانطباع الأول عن منشأتك غالبًا ما يكون بصريًا: شعار على لوحة، أو منشور في وسائل التواصل، أو عرض تقديمي في اجتماع. والتصميم الجيد لا يقتصر على الجمال، بل يوصل رسالتك بوضوح ويجعل منشأتك مميزة وسهلة التذكر. في النرجس نقدم خدمات التصميم الجرافيكي للمنشآت في المملكة والخليج، بطابع يحترم الذوق المحلي ويواكب الاتجاهات الحديثة.",
                "نبدأ من رسالتكم لا من قالب جاهز. القالب قد يسرّع شكلاً، لكنه يمحو الفرق بين منشأة وأخرى. نسأل ماذا تقدمون، ولمن، وما الذي يجب أن يفهمه الرائي في الثواني الأولى قبل أن يقرأ فقرة.",
            ]),
            _sec("خدمات التصميم التي نقدمها", [
                "يمكن أن يكون العمل هوية متكاملة أو عنصرًا واحدًا. النطاق يُكتب قبل البدء حتى لا يختلط دليل الهوية بمنشور واحد.",
            ], [
                "الهوية البصرية: الشعار، والألوان، والخطوط، ودليل استخدام الهوية.",
                "تصاميم وسائل التواصل الاجتماعي: قوالب ومنشورات متناسقة مع هويتك.",
                "المواد التسويقية: المطويات، والملصقات، والإعلانات الرقمية والمطبوعة.",
                "العروض التقديمية: عروض واضحة ومنظمة تدعم رسالتك أمام عملائك وشركائك.",
                "الرسوم التوضيحية والإنفوجرافيك: لتبسيط المعلومات المعقدة.",
            ]),
            _sec("كيف نعمل؟", [
                "الاستماع والفهم: نتعرف على منشأتك وجمهورها وقيمها وما يميزها. نطلب أمثلة لما يعجبكم وما لا يناسبكم، لأن الرفض أوضح أحيانًا من الوصف المجرد.",
                "البحث والإلهام: ندرس السوق والمنافسين ونقترح اتجاهات بصرية. الاتجاه اقتراح يُناقش، لا قرارًا نهائيًا نصل به في الاجتماع الأول.",
                "المسودات الأولية: نقدم تصورات مبدئية لمناقشتها معك. المسودة أداة حديث، ويجوز رفضها. نفضل أن يظهر الاختلاف مبكرًا على أن يُكتشف بعد بناء نظام كامل.",
                "التطوير والمراجعة: نطور التصميم المختار وفق ملاحظاتك. جولات المراجعة جزء من العمل، ونحدد عددها في الاتفاق حتى يبقى المسار مفهومًا للطرفين.",
                "التسليم: نسلم الملفات النهائية بالصيغ المناسبة للطباعة والاستخدام الرقمي. ما يُسلَّم من ملفات مصدرية وصيغ نتفق عليه قبل بدء العمل، لا في آخر يوم.",
            ]),
            _sec("التصميم العربي بإتقان", [
                "نولي عناية خاصة للخط العربي وتنسيق النصوص من اليمين إلى اليسار، وهو جانب يُهمل أحيانًا في التصاميم المنقولة عن قوالب أجنبية. ونحرص على أن تبدو تصاميمك متقنة باللغتين العربية والإنجليزية عند الحاجة.",
                "العناية هنا عملية: طول الكلمة العربية، وموضع التشكيل إن استُخدم، واتجاه الأيقونة التي توحي بحركة، والهامش الذي يقلب حين تُنسخ الصفحة إلى الإنجليزية. التصميم الذي «يُقلب» في اللحظة الأخيرة تظهر فيه أخطاء المحاذاة. لذلك نضع الاتجاه العربي في المسودة الأولى إذا كان الجمهور عربيًا.",
            ]),
            _sec("الاستفادة من أدوات الذكاء الاصطناعي بمسؤولية", [
                "نستعين بأدوات الذكاء الاصطناعي لتسريع استكشاف الأفكار، لكن القرار الإبداعي والتنفيذ النهائي يبقيان بيد المصمم، مع مراعاة حقوق الملكية الفكرية واستخدام مصادر مرخصة.",
                "الأداة قد تقترح تكوينًا أو لوحة ألوان. لا نعتمد مخرجًا لم نراجع أصله، ولا نسلم صورة لا نعرف ترخيصها. إن كان العنصر يحتاج رسمًا أصليًا، يُرسم. السرعة في الاستكشاف لا تبرر غموض الملكية في الملف النهائي.",
            ]),
            _sec("لماذا النرجس؟", [
                "لأننا نجمع التصميم مع المحتوى والتقنية تحت سقف واحد، فيمكن أن تتكامل هويتك البصرية مع موقعك ومحتواك وبوت المحادثة الخاص بك بانسجام. الجملة التي يكتبها كاتب المحتوى والشكل الذي يحملها يخرجان من نقاش واحد، لا من تسليم ملف بين جهتين لا تريان بعضهما.",
                "وإذا كان الاحتياج شاشة يتفاعل معها المستخدم، لا مادة تُطبع أو تُنشر، فمكانه تصميم الواجهات. نفصل بين الاثنين في الاتفاق حتى لا يُسمى كل عمل بصري هوية، ولا كل شاشة منشورًا.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "The first impression of your organization is often visual: a logo on a sign, a post on social media, or a presentation in a meeting. Good design is not only beauty. It carries your message clearly and makes the organization distinct and easy to remember. At Al-Narjis we offer graphic design for organizations in the Kingdom and the Gulf, with a character that respects local taste and keeps up with current practice.",
                "We start from your message, not from a ready-made template. A template can speed up a shape, but it erases the difference between one organization and another. We ask what you offer, to whom, and what the viewer must understand in the first seconds before reading a paragraph.",
            ]),
            _sec("The design services we offer", [
                "The work can be a full identity or a single piece. The scope is written before we start, so an identity guide is not confused with one post.",
            ], [
                "Visual identity: the logo, colours, type, and a guide for using the identity.",
                "Social media design: templates and posts consistent with your identity.",
                "Marketing materials: leaflets, posters, and digital and print ads.",
                "Presentations: clear, ordered decks that support your message with customers and partners.",
                "Illustrations and infographics: to make complex information easier to follow.",
            ]),
            _sec("How we work", [
                "Listening and understanding: we learn your organization, its audience, its values, and what sets it apart. We ask for examples of what you like and what does not fit, because a refusal is sometimes clearer than an abstract description.",
                "Research and direction: we look at the market and the alternatives, and we propose visual directions. A direction is a proposal to discuss, not a final decision we arrive with at the first meeting.",
                "Early drafts: we present initial concepts to discuss with you. A draft is a tool for the conversation, and it may be refused. We prefer the disagreement to appear early rather than after a whole system has been built.",
                "Development and review: we develop the chosen design according to your notes. Review rounds are part of the work, and we set how many of them in the agreement so the path stays understandable to both sides.",
                "Delivery: we deliver the final files in the formats suited to print and digital use. Which source files and formats are delivered is agreed before the work starts, not on the last day.",
            ]),
            _sec("Arabic design done with care", [
                "We give particular care to Arabic type and to arranging text from right to left. That is a side sometimes neglected in designs copied from foreign templates. When you need both languages, we take care that the design holds in Arabic and in English.",
                "The care is practical: the length of an Arabic word, the place of diacritics if they are used, the direction of an icon that suggests movement, and the margin that flips when the page is also set in English. A design that is «flipped» at the last moment shows alignment errors. If the audience is Arabic, we put that direction in the first draft.",
            ]),
            _sec("Using AI tools responsibly", [
                "We use AI tools to speed up the exploration of ideas, but the creative decision and the final execution stay with the designer, with regard to intellectual property and the use of licensed sources.",
                "A tool may suggest a composition or a palette. We do not adopt an output whose origin we have not reviewed, and we do not deliver an image whose licence we do not know. If an element needs an original drawing, it is drawn. Speed in exploration does not excuse unclear ownership in the final file.",
            ]),
            _sec("Why Al-Narjis?", [
                "Because we bring design, content, and technology under one roof, your visual identity can sit with your site, your content, and your chatbot without a clash. The sentence a writer prepares and the form that carries it come out of one discussion, not a file passed between two parties who never see each other.",
                "If the need is a screen a person interacts with, rather than a piece that is printed or posted, that belongs to interface design. We separate the two in the agreement so that not every visual job is called an identity, and not every screen is called a post.",
            ]),
        ],
        "faq_ar": [
            {"q": "هل تصممون هوية كاملة أم عناصر منفردة؟", "a": "نقدم الخيارين: هوية بصرية متكاملة، أو تصاميم منفردة حسب حاجتك. النطاق يُكتب قبل البدء."},
            {"q": "هل أحصل على الملفات المصدرية؟", "a": "نتفق معك على الملفات المسلّمة وصيغها قبل بدء العمل. لا نترك هذا السؤال ليوم التسليم."},
            {"q": "هل يمكن تعديل التصميم بعد عرضه؟", "a": "نعم، تتضمن مراحل العمل جولات مراجعة لتطوير التصميم وفق ملاحظاتك، وعددها يتضح في الاتفاق."},
            {"q": "هل تصممون باللغتين العربية والإنجليزية؟", "a": "نعم، مع عناية خاصة بجودة الخط العربي واتجاه الصفحة، لا بقلب قالب أجنبي في آخر خطوة."},
            {"q": "كيف أبدأ؟", "a": "تحدث مع بوت النرجس في الموقع أو راسلنا عبر البريد الإلكتروني بفكرة مشروعك."},
        ],
        "faq_en": [
            {"q": "Do you design a full identity or single pieces?", "a": "Both. A full visual identity, or single designs according to your need. The scope is written before we start."},
            {"q": "Do I receive the source files?", "a": "We agree the delivered files and their formats before the work starts. We do not leave that question for delivery day."},
            {"q": "Can the design be changed after it is shown?", "a": "Yes. The stages include review rounds to develop the design from your notes, and the number of rounds is set in the agreement."},
            {"q": "Do you design in both Arabic and English?", "a": "Yes, with particular care for Arabic type and page direction, not by flipping a foreign template as a last step."},
            {"q": "How do I start?", "a": "Talk to the Al-Narjis bot on the site, or email us with the idea of the project."},
        ],
    },
    {
        "slug": "ui-ux-design",
        "name_ar": "تصميم الواجهات وتجربة المستخدم",
        "name_en": "UI and UX design",
        "title_ar": "تصميم واجهات وتجربة مستخدم UI/UX بالعربية | النرجس",
        "title_en": "Arabic UI/UX design for websites and apps | Al-Narjis",
        "desc_ar": "نصمم واجهات مواقع وتطبيقات سهلة الاستخدام تدعم العربية من اليمين لليسار، مبنية على فهم المستخدم وأهداف منشأتك.",
        "desc_en": "We design website and app interfaces that are easy to use, support Arabic from right to left, and are built on an understanding of the user and your organization's goals.",
        "h1_ar": "تصميم واجهات المستخدم وتجربة المستخدم",
        "h1_en": "User interface and user experience design",
        "card_ar": "واجهات مواقع وتطبيقات تبدأ من العربية ومن اليمين إلى اليسار، لا من قلب قالب إنجليزي.",
        "card_en": "Website and app interfaces that start from Arabic and from right to left, not from flipping an English template.",
        "related": ["graphic-design", "chatbots"],
        "sections_ar": [
            _sec("", [
                "قد يملك الموقع أو التطبيق خدمات ممتازة، لكن إذا ضل المستخدم طريقه أو لم يفهم الخطوة التالية، فقد يغادر. تصميم تجربة المستخدم يهتم بأن يكون المنتج سهلًا ومفهومًا، وتصميم الواجهات يهتم بأن يكون جذابًا ومتسقًا. في النرجس نجمع الجانبين لنصمم مواقع وتطبيقات ولوحات تحكم تخدم مستخدميك وأهداف منشأتك معًا.",
                "لا نفصل الجمال عن المهمة. الشاشة الجميلة التي لا يعرف الزائر أين يضغط فيها لا تخدم الهدف. والشاشة الواضحة التي تبدو مهملة تُضعف الثقة. العمل يجمع الاثنين منذ المخطط الأول، لا في طبقة تلوين تُضاف بعد أن يتجمد الهيكل.",
            ]),
            _sec("ماذا نقدم؟", [
                "هذه مخرجات التصميم. أيها يدخل في مشروعكم يُحدد في نطاق العمل، حتى لا يُفترض بحث مستخدم كامل لمهمة هي تحسين شاشة واحدة.",
            ], [
                "بحث المستخدم: فهم احتياجات جمهورك وسلوكه وتوقعاته.",
                "هيكلة المعلومات: تنظيم المحتوى والقوائم ليصل المستخدم لما يريد بسهولة.",
                "المخططات الأولية: رسم هيكل الصفحات قبل التصميم المرئي.",
                "النماذج التفاعلية: نماذج قابلة للتجربة قبل التطوير.",
                "تصميم الواجهات: تصميم مرئي متكامل مع نظام مكونات قابل لإعادة الاستخدام.",
                "مراجعة قابلية الاستخدام: تقييم المنتجات القائمة واقتراح التحسينات.",
            ]),
            _sec("تصميم يبدأ من العربية", [
                "كثير من المنتجات تُصمم بالإنجليزية ثم تُقلب للعربية، فتظهر مشكلات في المحاذاة والأيقونات واتجاه الحركة والخطوط. نحن نصمم مع مراعاة الاتجاه من اليمين إلى اليسار منذ البداية، ونختار خطوطًا عربية واضحة على الشاشات المختلفة، لتكون التجربة طبيعية للمستخدم العربي.",
                "القلب المتأخر يكسر أكثر من الهامش. سهم «التالي» يشير إلى الجهة الخطأ، والأيقونة التي تعني تقدمًا تُفهم تراجعًا، والخط العربي الذي لم يُختبر على شاشة صغيرة يصبح سطرًا مزدحمًا. نختبر الاتجاه العربي على عرض الجوال وعرض المكتب قبل أن نثبت المكونات.",
                "إذا كان المنتج ثنائي اللغة، لا نجعل الإنجليزية الأصل والعربية نسخة. لكل لغة طول مختلف وترتيب مختلف. المكوّن الذي يتسع للجملة الإنجليزية قد يقص الجملة العربية، فنصمم للغة الأطول حيث يلزم.",
            ]),
            _sec("إمكانية الوصول", [
                "نراعي مبادئ إمكانية الوصول، مثل تباين الألوان الكافي، وأحجام النصوص المقروءة، ووضوح عناصر التفاعل، ليتمكن أكبر عدد من المستخدمين من استخدام منتجك بسهولة.",
                "هذا ليس ملحقًا في نهاية الملف. الزر الذي لا يُميز إلا باللون، والنص الرمادي الباهت على خلفية فاتحة، والحقل الذي لا يُعرف أنه قابل للنقر، كلها تُراجع مع التصميم لا بعده. نوضح في التسليم ما روعي، حتى يستطيع المطوّر الحفاظ عليه حين يبني.",
            ]),
            _sec("مراحل العمل", [
                "الاكتشاف: نفهم أهداف المنتج والمستخدمين والقيود التقنية. القيد التقني الذي يُعرف متأخرًا يعيد التصميم. لذلك نسأله في البداية: ما الذي يستطيع الفريق بناؤه، وما الذي هو ثابت لا يُمس.",
                "الهيكلة: نبني خريطة الموقع ورحلات المستخدم الأساسية. الرحلة هنا مسار مهمة واحدة، مثل إتمام طلب أو إيجاد سياسة، لا خريطة لكل صفحة ممكنة.",
                "المخططات والنماذج: نختبر الأفكار مبكرًا قبل الاستثمار في التطوير. النموذج يجيب: هل فهم المستخدم الخطوة؟ إن لم يفهمها على مخطط بلا ألوان، فالألوان لن تنقذه.",
                "التصميم المرئي: نطبق الهوية البصرية ونبني نظام التصميم. إن لم تكن لديكم هوية بعد، يمكن أن يسبق ذلك عمل التصميم الجرافيكي، ثم نعود إلى الشاشات.",
                "التسليم للمطورين: نسلم ملفات منظمة ومواصفات واضحة لتسهيل التنفيذ. المواصفة تذكر الحالة العادية وحالة الخطأ والحالة الفارغة، لأن الشاشة السعيدة وحدها لا تكفي للبناء.",
            ]),
            _sec("لماذا النرجس؟", [
                "لأننا نفهم المستخدم السعودي وتوقعاته، ونربط التصميم بالتقنية؛ فيمكننا دمج بوت محادثة أو أتمتة داخل التجربة بصورة متسقة. زر المساعدة لا يُلصق في الزاوية بعد انتهاء التصميم. مكانه يُدرس مع رحلة المستخدم: متى يحتاج شخصًا، ومتى تكفيه صفحة.",
                "ونوضح نطاق التنفيذ. نسلم ملفات جاهزة للمطورين، ويمكن مناقشة البناء البرمجي حسب المشروع. لا نخلط وعد التصميم بوعد الإطلاق إذا لم يكن الإطلاق داخل الاتفاق.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "A website or an app may offer excellent services, but if the user loses the way or does not understand the next step, they may leave. User experience design cares that the product is easy and understandable. Interface design cares that it is attractive and consistent. At Al-Narjis we combine the two so the sites, apps, and dashboards we design serve your users and your organization's goals together.",
                "We do not separate beauty from the task. A beautiful screen where the visitor does not know where to press does not serve the goal. A clear screen that looks neglected weakens trust. The work combines both from the first sketch, not as a coat of colour added after the structure has frozen.",
            ]),
            _sec("What we deliver", [
                "These are design outputs. Which of them enter your project is set in the scope, so a full user study is not assumed for a task that is the improvement of one screen.",
            ], [
                "User research: understanding your audience's needs, behavior, and expectations.",
                "Information structure: organizing content and menus so the user reaches what they want.",
                "Wireframes: drawing the structure of pages before visual design.",
                "Prototypes: models that can be tried before development.",
                "Interface design: a visual design with a component system that can be reused.",
                "Usability review: assessing an existing product and proposing improvements.",
            ]),
            _sec("Design that starts from Arabic", [
                "Many products are designed in English and then flipped into Arabic, and problems appear in alignment, icons, the direction of movement, and type. We design with right-to-left in mind from the start, and we choose Arabic type that stays clear on different screens, so the experience feels natural for an Arabic user.",
                "A late flip breaks more than the margin. A «next» arrow points the wrong way, an icon that means progress is read as going back, and Arabic type that was not tried on a small screen becomes a crowded line. We test the Arabic direction on a phone width and a desktop width before we lock the components.",
                "If the product is bilingual, we do not make English the original and Arabic a copy. Each language has a different length and a different order. A component that fits the English sentence may cut the Arabic one, so we design for the longer language where that is needed.",
            ]),
            _sec("Accessibility", [
                "We respect accessibility principles, such as sufficient colour contrast, readable text sizes, and clear interactive elements, so more people can use your product with ease.",
                "This is not an appendix at the end of the file. A button distinguished only by colour, pale grey text on a light background, and a field that does not look tappable are reviewed with the design, not after it. In the handover we state what was considered, so the developer can keep it when they build.",
            ]),
            _sec("Stages of the work", [
                "Discovery: we understand the product goals, the users, and the technical constraints. A constraint discovered late sends the design back. We ask it at the start: what the team can build, and what is fixed and must not be touched.",
                "Structure: we build the site map and the basic user journeys. A journey here is the path of one task, such as completing a request or finding a policy, not a map of every possible page.",
                "Sketches and prototypes: we test ideas early, before the investment in development. The prototype answers: did the user understand the step? If they did not understand it on a sketch without colour, colour will not save it.",
                "Visual design: we apply the visual identity and build the design system. If you do not have an identity yet, graphic design can come first, and we return to the screens after it.",
                "Handover to developers: we deliver organized files and clear specifications to make implementation easier. The specification names the normal state, the error state, and the empty state, because the happy screen alone is not enough to build from.",
            ]),
            _sec("Why Al-Narjis?", [
                "Because we understand the Saudi user and their expectations, and we connect design to technology. A chatbot or an automation step can sit inside the experience in a consistent way. A help button is not stuck in the corner after the design is finished. Its place is studied with the journey: when a person is needed, and when a page is enough.",
                "We also make the scope of implementation clear. We deliver files ready for developers, and building the software can be discussed according to the project. We do not mix a design promise with a launch promise if the launch is not inside the agreement.",
            ]),
        ],
        "faq_ar": [
            {"q": "ما الفرق بين واجهة المستخدم وتجربة المستخدم؟", "a": "تجربة المستخدم تهتم بسهولة الاستخدام ومنطق الرحلة، وواجهة المستخدم تهتم بالمظهر المرئي والتفاعل. نعمل على الاثنين معًا ونوضح في النطاق وزن كل منهما."},
            {"q": "هل تصممون لتطبيقات الجوال والمواقع؟", "a": "نعم، نصمم للمواقع وتطبيقات الجوال ولوحات التحكم. الاتجاه العربي يُختبر على أكثر من عرض شاشة."},
            {"q": "هل تقومون بتطوير التصميم برمجيًا؟", "a": "نوضح معك نطاق العمل. نسلم ملفات جاهزة للمطورين، ويمكن مناقشة التنفيذ حسب المشروع. التصميم لا يعني تلقائيًا أن الإطلاق داخل الاتفاق."},
            {"q": "هل يمكنكم تحسين منتج قائم؟", "a": "نعم، نراجع قابلية الاستخدام ونقترح تحسينات عملية، بدءًا من الرحلة التي يتعطل فيها المستخدم لا من إعادة رسم كل الشاشات."},
            {"q": "كيف أبدأ؟", "a": "تحدث مع بوت النرجس في الموقع أو راسلنا عبر البريد الإلكتروني."},
        ],
        "faq_en": [
            {"q": "What is the difference between UI and UX?", "a": "User experience cares about ease of use and the logic of the journey. The user interface cares about visual appearance and interaction. We work on both, and the scope states the weight of each."},
            {"q": "Do you design for mobile apps and websites?", "a": "Yes. We design for websites, mobile apps, and dashboards. The Arabic direction is tested on more than one screen width."},
            {"q": "Do you develop the design in code?", "a": "We make the scope clear with you. We deliver files ready for developers, and implementation can be discussed per project. Design does not automatically mean that launch is inside the agreement."},
            {"q": "Can you improve an existing product?", "a": "Yes. We review usability and propose practical improvements, starting from the journey where the user gets stuck, not from redrawing every screen."},
            {"q": "How do I start?", "a": "Talk to the Al-Narjis bot on the site, or email us."},
        ],
    },
    {
        "slug": "content-writing",
        "name_ar": "كتابة المحتوى",
        "name_en": "Content writing",
        "title_ar": "كتابة محتوى عربي احترافي للمنشآت في السعودية | النرجس",
        "title_en": "Professional Arabic content writing for Saudi organizations | Al-Narjis",
        "desc_ar": "محتوى عربي واضح ومتوافق مع محركات البحث لمواقع المنشآت ومدوناتها ووسائل تواصلها، بلغة سليمة تناسب الجمهور السعودي.",
        "desc_en": "Clear, search-aware Arabic content for organization websites, blogs, and social channels, in sound language suited to a Saudi audience.",
        "h1_ar": "كتابة المحتوى العربي الاحترافي",
        "h1_en": "Professional Arabic content writing",
        "card_ar": "محتوى عربي سليم لموقعك ومدونتك ووسائل تواصلك، يُكتب للقارئ وتُراجع مسودته معك.",
        "card_en": "Sound Arabic content for your site, blog, and social channels, written for the reader and reviewed with you.",
        "related": ["translation", "graphic-design"],
        "sections_ar": [
            _sec("", [
                "الكلمة هي ما يقنع العميل بعد أن يجذبه التصميم. والمحتوى الجيد يشرح خدماتك بوضوح، ويجيب عن أسئلة جمهورك، ويساعد منشأتك على الظهور في نتائج البحث. في النرجس نكتب محتوى عربيًا سليمًا وسلسًا، يناسب الجمهور في المملكة والخليج، ويحقق التوازن بين متطلبات القارئ ومتطلبات محركات البحث.",
                "لا نكتب نصًا يمكن أن يوقّعه أي نشاط. نبدأ من خدمتكم الفعلية ومن السؤال الذي يطرحه من يبحث، ثم نصوغ الجواب بلغة يفهمها دون أن تبدو مترجمة أو مكدسة بالمصطلحات.",
            ]),
            _sec("أنواع المحتوى الذي نكتبه", [
                "النوع يحدد البناء. صفحة خدمة ليست مقالًا، ومنشور ليس نشرة بريدية. نتفق على النوع قبل الكتابة.",
            ], [
                "محتوى المواقع: الصفحة الرئيسية، وصفحات الخدمات، وصفحة من نحن.",
                "مقالات المدونة: مقالات معرفية تجيب عن أسئلة جمهورك وتدعم ظهورك في البحث.",
                "محتوى وسائل التواصل: منشورات متسقة مع هوية منشأتك ونبرتها.",
                "النشرات البريدية: رسائل واضحة ومفيدة لعملائك.",
                "أوصاف المنتجات والخدمات: نصوص دقيقة تشرح القيمة دون مبالغة.",
            ]),
            _sec("محتوى متوافق مع محركات البحث", [
                "نبدأ بفهم ما يبحث عنه جمهورك فعلًا، ثم نبني المحتوى حول هذه الاحتياجات بصياغة طبيعية، مع العناية بالعناوين والوصف والروابط الداخلية. لا نحشو الكلمات المفتاحية، لأن المحتوى المكتوب للقارئ أولًا هو الأقدر على الاستمرار.",
                "الصفحة الواحدة تخدم نية واحدة. إذا خلط النص شرحًا ومقارنة وطلب شراء في كتلة لا عنوان لها، ضاع القارئ ومحرك البحث معًا. نقسم: عنوان يصف الموضوع، وفقرة تجيب، ورابط يقود إلى الصفحة التالية التي يحتاجها الزائر. الرابط الداخلي جزء من الكتابة لا مهمة تُضاف بعد النشر كيفما اتفق.",
                "الوصف الذي يظهر في نتائج البحث نكتبه مع النص، لأنه الوعد الذي يقرأه الشخص قبل أن يفتح الصفحة. نجعله صادقًا ومحددًا. إن كانت الصفحة تشرح خدمة، يقول الوصف ذلك. لا نعد بنتيجة لا تحتويها الصفحة.",
            ]),
            _sec("الدقة والمصداقية", [
                "نلتزم بعدم نشر ادعاءات غير قابلة للتحقق، ونراجع المعلومات مع منشأتك قبل النشر، بما يتوافق مع أنظمة حماية المستهلك في المملكة. فالثقة التي يبنيها المحتوى الصادق أبقى من أي عبارة تسويقية مبالغ فيها.",
                "إذا لم تتوفر لدينا معلومة، نسأل ولا نملأ الفراغ. الرقم، واسم العميل، ونتيجة «قبل وبعد» لا تُكتب إلا إذا قدمتموها أنتم ووافقتم على نشرها. في غياب ذلك يبقى النص على وصف الخدمة وطريقة العمل. هذا أضيق، وهو أسلم.",
            ]),
            _sec("كيف نعمل؟", [
                "فهم المنشأة والجمهور: نتعرف على خدماتك وجمهورك ونبرة التواصل المناسبة. نطلب نماذج مما كتبتموه سابقًا إن وُجدت، لأن النبرة تُرى في المثال أوضح مما تُرى في صفة مثل «رسمي» أو «قريب».",
                "التخطيط: نقترح موضوعات وهيكلًا للمحتوى. الخطة تقول ماذا تُجيب كل صفحة، لا كم كلمة نعدّها. الطول تابع للسؤال لا هدفًا مستقلًا.",
                "الكتابة: نكتب بلغة عربية سليمة ميسّرة. الفصحى الميسرة هي الأصل في صفحات الموقع. وفي وسائل التواصل يمكن أن تقترب النبرة من الجمهور المحلي إذا طلبتم ذلك صراحة.",
                "المراجعة والتدقيق: ندقق اللغة والمعلومات ونعرض المسودة عليك. ملاحظتكم جزء من التسليم. لا نعدّ النص نهائيًا قبل أن ترونه.",
                "التسليم: نسلم المحتوى جاهزًا للنشر مع العناوين والأوصاف المقترحة. إن كان النشر على موقعكم، نرتب النص بحيث يستطيع من يضعه في الصفحة أن ينقله دون أن يعيد بناء الهيكل.",
            ]),
            _sec("الكتابة بمساعدة الذكاء الاصطناعي", [
                "قد نستعين بأدوات الذكاء الاصطناعي في البحث والتنظيم، لكن كل نص يمر بكاتب ومدقق بشري يضمن جودة اللغة ودقة المعلومة وملاءمتها لجمهورك.",
                "الأداة تسرّع جمع الأسئلة المتشابهة أو اقتراح هيكل. لا نسلم مخرجها كما هو. الجملة التي تصل إليكم قرأها شخص يتقن العربية وراجعها على معلوماتكم. إن تعارضت أداة مع معلومة من منشأتكم، فالمعلومة هي التي تبقى.",
            ]),
            _sec("لماذا النرجس؟", [
                "لأننا نجمع الكتابة مع التصميم والتقنية، فيصل محتواك إلى جمهورك في قالب متكامل، ونهتم بأن يعكس كل نص هوية منشأتك. العنوان والوصف والصورة المرافقة يمكن أن تُناقش مع التصميم في العمل نفسه، بدل أن يُكتب النص ثم يُبحث له عن شكل لا يتسع له.",
                "وإن كان النص سيُنشر بالإنجليزية أيضًا، فالأسلم أن تُكتب العربية أولًا ثم تُوطَّن، لا أن تُكتب الإنجليزية وتُقلب. ذلك عمل صفحة الترجمة، ونحيله إليها حين يكون مطلوبًا.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "Words are what convince a customer after design has attracted them. Good content explains your services clearly, answers your audience's questions, and helps your organization appear in search results. At Al-Narjis we write Arabic that is sound and easy to follow, suited to audiences in the Kingdom and the Gulf, and balanced between what the reader needs and what search engines need.",
                "We do not write text that any business could sign. We start from your actual service and from the question a person is searching with, then we phrase the answer in language they understand, without it sounding translated or piled with terminology.",
            ]),
            _sec("The kinds of content we write", [
                "The kind decides the structure. A service page is not an article, and a post is not an email newsletter. We agree the kind before writing.",
            ], [
                "Website content: the home page, service pages, and the about page.",
                "Blog articles: pieces that answer your audience's questions and support your presence in search.",
                "Social content: posts consistent with your organization's identity and tone.",
                "Email newsletters: clear, useful messages for your customers.",
                "Product and service descriptions: accurate text that explains the value without exaggeration.",
            ]),
            _sec("Content that respects search", [
                "We start by understanding what your audience actually searches for, then we build the content around those needs in natural phrasing, with care for headings, the description, and internal links. We do not stuff keywords. Content written for the reader first is the content that can last.",
                "One page serves one intent. If the text mixes an explanation, a comparison, and a request to buy in a block with no heading, the reader and the search engine are both lost. We divide: a heading that names the subject, a paragraph that answers, and a link that leads to the next page the visitor needs. The internal link is part of the writing, not a task added anyhow after publishing.",
                "The description that appears in search results is written with the text, because it is the promise a person reads before opening the page. We make it honest and specific. If the page explains a service, the description says so. We do not promise a result the page does not contain.",
            ]),
            _sec("Accuracy and credibility", [
                "We do not publish claims that cannot be checked, and we review the information with your organization before publishing, in line with consumer-protection rules in the Kingdom. The trust that honest content builds outlasts any inflated marketing sentence.",
                "If we do not have a fact, we ask. We do not fill the gap. A number, a client name, and a before-and-after result are written only if you supply them and agree to publish them. Without that, the text stays on the service and the way of working. That is narrower, and it is safer.",
            ]),
            _sec("How we work", [
                "Understanding the organization and the audience: we learn your services, your audience, and the right tone, using samples of what you have written before when they exist.",
                "Planning: we propose subjects and a structure. The plan says what each page answers. Length follows the question.",
                "Writing: we write in sound, accessible formal Arabic for website pages. On social channels the tone can move closer to the local audience if you ask for that explicitly.",
                "Review: we check the language and the facts and show you the draft. The text is not final before you have seen it.",
                "Delivery: we deliver content ready to publish, with proposed headings and descriptions, arranged so it can be placed on your site without rebuilding the structure.",
            ]),
            _sec("Writing with the help of AI", [
                "We may use AI tools in research and organization, but every text passes through a human writer and a human proofreader who are responsible for the quality of the language, the accuracy of the fact, and the fit for your audience.",
                "A tool speeds up gathering similar questions or proposing a structure. We do not deliver its output as it is. The sentence that reaches you has been read by a person who knows Arabic and checked against your information. If a tool conflicts with a fact from your organization, the fact is what stays.",
            ]),
            _sec("Why Al-Narjis?", [
                "Because we combine writing with design and technology, your content reaches the audience in one piece, and we care that every text reflects your identity. The heading, the description, and the image that accompanies them can be discussed with design in the same engagement, instead of writing the text and then searching for a shape that does not fit it.",
                "If the text will also be published in English, it is safer to write the Arabic first and then localize it, not to write the English and flip it. That is the work of the translation page, and we hand it there when it is needed.",
            ]),
        ],
        "faq_ar": [
            {"q": "هل تكتبون بالفصحى أم باللهجة؟", "a": "نكتب بالعربية الفصحى الميسّرة غالبًا، ويمكن اعتماد نبرة أقرب للجمهور المحلي في وسائل التواصل حسب رغبتك. الاختيار يُحسم قبل الكتابة لا في المسودة الأخيرة."},
            {"q": "هل المحتوى متوافق مع محركات البحث؟", "a": "نعم، نراعي أسس تحسين محركات البحث مع الحفاظ على سلاسة النص للقارئ. لا نحشو الكلمات، ونكتب وصفًا صادقًا للصفحة."},
            {"q": "هل يمكنني مراجعة المحتوى قبل النشر؟", "a": "بالتأكيد. نعرض المسودات عليك ونعدلها وفق ملاحظاتك. النص لا يُعد نهائيًا قبل مراجعتك."},
            {"q": "هل تكتبون بالإنجليزية أيضًا؟", "a": "نعم، ويمكن الجمع بين الكتابة والترجمة حسب احتياجك. العربية تُكتب أولًا حين تكون هي الأصل."},
            {"q": "كيف أبدأ؟", "a": "تحدث مع بوت النرجس في الموقع أو راسلنا عبر البريد الإلكتروني."},
        ],
        "faq_en": [
            {"q": "Do you write in formal Arabic or in dialect?", "a": "We usually write in accessible formal Arabic. A tone closer to the local audience can be used on social channels if you want that. The choice is settled before writing, not in the last draft."},
            {"q": "Is the content written with search in mind?", "a": "Yes. We respect the basics of search while keeping the text easy for the reader. We do not stuff keywords, and we write an honest description of the page."},
            {"q": "Can I review the content before it is published?", "a": "Yes. We show you the drafts and revise them from your notes. The text is not treated as final before your review."},
            {"q": "Do you also write in English?", "a": "Yes, and writing can be combined with translation according to your need. Arabic is written first when it is the source."},
            {"q": "How do I start?", "a": "Talk to the Al-Narjis bot on the site, or email us."},
        ],
    },
    {
        "slug": "translation",
        "name_ar": "الترجمة الاحترافية",
        "name_en": "Professional translation",
        "title_ar": "ترجمة احترافية عربي إنجليزي للمنشآت في السعودية | النرجس",
        "title_en": "Professional Arabic–English translation for Saudi organizations | Al-Narjis",
        "desc_ar": "ترجمة دقيقة بين العربية والإنجليزية لمحتوى المواقع والمستندات والتسويق، تجمع أدوات الذكاء الاصطناعي ومراجعة بشرية متخصصة.",
        "desc_en": "Accurate Arabic–English translation for websites, documents, and marketing, combining AI tools with a specialist human review.",
        "h1_ar": "الترجمة الاحترافية بين العربية والإنجليزية",
        "h1_en": "Professional translation between Arabic and English",
        "card_ar": "ترجمة وتوطين بين العربية والإنجليزية، مع مسرد لمصطلحاتكم ومراجعة بشرية لكل نص.",
        "card_en": "Translation and localization between Arabic and English, with a glossary of your terms and a human review of every text.",
        "related": ["content-writing", "ui-ux-design"],
        "sections_ar": [
            _sec("", [
                "تتعامل المنشآت في المملكة مع جمهور متنوع وشركاء من داخل المملكة وخارجها، مما يجعل الترجمة الدقيقة ضرورة لا رفاهية. والترجمة الجيدة لا تنقل الكلمات فحسب، بل تنقل المعنى والنبرة بما يناسب ثقافة القارئ. في النرجس نقدم ترجمة احترافية بين العربية والإنجليزية تجمع سرعة أدوات الذكاء الاصطناعي ودقة المراجعة البشرية.",
                "الجمهور الذي يقرأ الإنجليزية قد يكون شريكًا دوليًا أو زائرًا لا تناسبه الجملة المنقولة حرفيًا من العربية. والجمهور الذي يقرأ العربية لا تناسبه جملة كُتبت بالإنجليزية ثم قُلبت بلا نظر إلى طولها ورتبتها. نحدد من يقرأ قبل أن نبدأ.",
            ]),
            _sec("ما الذي نترجمه؟", [
                "النطاق تجاري وتسويقي وتقني. نذكر في آخر هذه الصفحة ما لا نترجمه، حتى لا يُطلب منا ختم لا نقدمه.",
            ], [
                "محتوى المواقع والتطبيقات: الصفحات والواجهات والرسائل داخل المنتج.",
                "المواد التسويقية: الإعلانات والعروض التقديمية والمطويات.",
                "المستندات التجارية: الملفات التعريفية والتقارير والمراسلات.",
                "المحتوى التقني: أدلة الاستخدام والوثائق التقنية.",
            ]),
            _sec("التوطين لا مجرد الترجمة", [
                "نهتم بتوطين المحتوى، أي تكييفه ليناسب القارئ المحلي في اللغة والأمثلة والصياغة، فلا يبدو النص مترجمًا حرفيًا. وعند الترجمة إلى الإنجليزية نحرص على أن يناسب النص القارئ الدولي مع الحفاظ على هوية منشأتك.",
                "التكييف لا يعني تغيير عرضكم. إذا كان المثال في الأصل مرتبطًا بالسوق السعودي، قد نبقيه ونشرحه بدل استبداله بمثال أجنبي يضيع السياق. وإذا كانت العبارة اصطلاحًا داخليًا لديكم، تبقى كما اتفقتم في المسرد، حتى لو وُجد مقابل أشهر لا تستخدمونه.",
                "في الواجهات نراعي طول النص واتجاهه. الترجمة التي تزيد عدد الكلمات قد تكسر زرًا أو قائمة. نُعلمكم حين يحتاج النص العربي أو الإنجليزي مساحة مختلفة، حتى يُعالج في التصميم لا بعد أن يقصّه الإطار.",
            ]),
            _sec("كيف نعمل؟", [
                "فهم السياق: نتعرف على الجمهور المستهدف والغرض من النص. الغرض يغير القرار: نص يُلقى في اجتماع ليس نصًا يُقرأ على شاشة جوال.",
                "إعداد المسرد: نوحد المصطلحات الخاصة بمنشأتك وقطاعك. المصطلح الذي يُترجم بثلاث طرق في الملف نفسه يشتت القارئ. المسرد يُرسل إليكم لتأكيد الخيارات قبل أن يمتد إلى بقية المواد.",
                "الترجمة: نترجم بالاستعانة بالأدوات المناسبة. الأداة مسودة عمل، لا نسخة نهائية.",
                "المراجعة البشرية: يراجع مترجم متخصص النص لغويًا ودلاليًا. المراجعة تبحث عن المعنى الضائع والجملة التي صحت نحويًا وفسدت دلالة، وهذا ما لا تمسكه الأداة وحدها.",
                "التسليم: نسلم النص بالتنسيق المطلوب، مع مراعاة اتجاه الكتابة العربية. إن كان الأصل جدولًا أو واجهة، نسلّم الترجمة بشكل يمكن وضعه في المكان نفسه دون إعادة تنضيد عشوائية.",
            ]),
            _sec("السرية وحماية البيانات", [
                "نتعامل مع مستنداتك بسرية، ونراعي نظام حماية البيانات الشخصية في المملكة عند التعامل مع أي بيانات شخصية ضمن النصوص.",
                "إن احتوى الملف على بيانات لا تلزم للترجمة، نطلب حذفها أو إخفاءها قبل العمل. لا نحتاج نسخة من كل مرفق «للفهم» إذا كانت فقرة السياق كافية. وما يُرسل إلى أداة نوضحه لكم قبل استخدام الأداة على النص.",
            ]),
            _sec("ملاحظة مهمة", [
                "خدماتنا موجهة لترجمة المحتوى التجاري والتسويقي والتقني. أما الترجمة القانونية المعتمدة التي تتطلب ختم مكتب ترجمة مرخص، فننصح بالرجوع فيها إلى الجهات المعتمدة المختصة.",
                "هذا الحد واضح حتى لا يُستخدم نصّنا حيث يُشترط ختم. العقد، والوكالة، والمستند الرسمي الذي يطلبه إجراء حكومي، مكانها مكتب مرخص. نستطيع أن نترجم المادة التعريفية التي تحيط بالإجراء، ولا نقدّم أنفسنا بديلاً عن الختم. ",
            ]),
            _sec("لماذا النرجس؟", [
                "لأننا نجمع الترجمة مع كتابة المحتوى والتصميم، فيمكن أن يخرج محتواك ثنائي اللغة متسقًا في المعنى والشكل. المترجم يرى القيد البصري، والمصمم يرى طول الجملة، والكاتب يرى ما إذا كان الأصل العربي نفسه يحتاج تحريرًا قبل أن يُترجم.",
                "إن كان الأصل ضعيفًا، نقول ذلك. ترجمة جملة مرتبكة تنتج جملة مرتبكة بلغة أخرى. في هذه الحالة نبدأ بتحرير عربي عبر كتابة المحتوى، ثم نترجم. الترتيب أوضح من إصلاح المعنى في اللغة الثانية.",
            ]),
        ],
        "sections_en": [
            _sec("", [
                "Organizations in the Kingdom deal with a varied audience and with partners inside and outside the country, so accurate translation is a necessity, not a luxury. Good translation does not only move words. It moves the meaning and the tone in a way that fits the reader's culture. At Al-Narjis we offer professional translation between Arabic and English that combines the speed of AI tools with the accuracy of a human review.",
                "The person reading English may be an international partner or a visitor who is not served by a sentence moved literally from Arabic. The person reading Arabic is not served by a sentence written in English and flipped with no attention to its length and order. We decide who is reading before we start.",
            ]),
            _sec("What we translate", [
                "The scope is commercial, marketing, and technical. At the end of this page we say what we do not translate, so that a stamp we do not offer is not requested from us.",
            ], [
                "Website and app content: pages, interfaces, and the messages inside the product.",
                "Marketing materials: ads, presentations, and leaflets.",
                "Business documents: profile documents, reports, and correspondence.",
                "Technical content: user guides and technical documentation.",
            ]),
            _sec("Localization, not only translation", [
                "We care about localizing the content: adapting it so it fits the local reader in language, examples, and phrasing, and does not sound literal. When we translate into English we take care that the text fits an international reader while keeping your organization's identity.",
                "Adaptation does not mean changing your offer. If an example in the source is tied to the Saudi market, we may keep it and explain it instead of replacing it with a foreign example that loses the context. If a phrase is an internal term of yours, it stays as agreed in the glossary, even if a more famous equivalent exists that you do not use.",
                "In interfaces we watch the length of the text and its direction. A translation that adds words can break a button or a menu. We tell you when the Arabic or the English needs a different space, so it is handled in the design and not clipped by the frame afterwards.",
            ]),
            _sec("How we work", [
                "Understanding the context: we learn the audience and the purpose of the text. Purpose changes the decision. A text spoken in a meeting is not a text read on a phone screen.",
                "Preparing the glossary: we unify the terms that belong to your organization and your sector. A term translated three ways in the same file confuses the reader. The glossary is sent to you so the choices are confirmed before they spread to the rest of the material.",
                "Translation: we translate with the help of suitable tools. The tool is a working draft, not a final version.",
                "Human review: a specialist translator reviews the text for language and meaning. The review looks for lost meaning and for the sentence that is grammatically fine and semantically wrong. That is what a tool alone does not catch.",
                "Delivery: we deliver the text in the format you need, with regard to Arabic writing direction. If the source is a table or an interface, we deliver the translation in a form that can be placed in the same spot without random retyping.",
            ]),
            _sec("Confidentiality and data protection", [
                "We treat your documents as confidential, and we respect the Personal Data Protection Law in the Kingdom when any personal data appears inside the texts.",
                "If a file contains data the translation does not need, we ask for it to be removed or hidden before the work. We do not need a copy of every attachment «for context» if a paragraph of context is enough. What would be sent to a tool is explained to you before that tool is used on the text.",
            ]),
            _sec("An important limit", [
                "Our service is for commercial, marketing, and technical content. Certified legal translation that requires the stamp of a licensed translation office should go to the competent licensed parties.",
                "The limit is plain so our text is not used where a stamp is required. A contract, a power of attorney, and an official document a government procedure asks for belong with a licensed office. We can translate the explanatory material around a procedure. We do not offer ourselves as a substitute for the stamp.",
            ]),
            _sec("Why Al-Narjis?", [
                "Because we combine translation with content writing and design, your bilingual content can come out consistent in meaning and in form. The translator sees the visual constraint, the designer sees the length of the sentence, and the writer sees whether the Arabic source itself needs editing before it is translated.",
                "If the source is weak, we say so. Translating a tangled sentence produces a tangled sentence in the other language. In that case we start with an Arabic edit through content writing, then we translate. The order is clearer than repairing the meaning in the second language.",
            ]),
        ],
        "faq_ar": [
            {"q": "ما اللغات التي تترجمون منها وإليها؟", "a": "نركز على الترجمة بين العربية والإنجليزية، في الاتجاهين. لا نعرض لغات أخرى ضمن هذه الخدمة."},
            {"q": "هل تعتمدون على الترجمة الآلية فقط؟", "a": "لا. نستعين بالأدوات لتسريع العمل، ويراجع كل نص مترجم بشري متخصص قبل التسليم."},
            {"q": "هل تقدمون ترجمة معتمدة للمستندات الرسمية؟", "a": "لا نقدم الترجمة القانونية المعتمدة التي تحتاج ختم مكتب مرخص. ننصح بالرجوع إلى المكاتب المختصة لهذا الغرض."},
            {"q": "هل يمكن توحيد مصطلحات منشأتي؟", "a": "نعم، نعد مسردًا للمصطلحات ونلتزم به في جميع الأعمال، بعد أن تؤكدوا خياراتكم."},
            {"q": "كيف أبدأ؟", "a": "تحدث مع بوت النرجس في الموقع أو راسلنا عبر البريد الإلكتروني."},
        ],
        "faq_en": [
            {"q": "Which languages do you translate?", "a": "We focus on translation between Arabic and English, in both directions. Other languages are not part of this service."},
            {"q": "Do you rely only on machine translation?", "a": "No. We use tools to speed the work, and a specialist human reviews every translated text before delivery."},
            {"q": "Do you provide certified translation for official documents?", "a": "We do not provide certified legal translation that needs the stamp of a licensed office. We recommend the competent offices for that purpose."},
            {"q": "Can my organization's terminology be kept consistent?", "a": "Yes. We prepare a glossary and follow it across the work, after you confirm the choices."},
            {"q": "How do I start?", "a": "Talk to the Al-Narjis bot on the site, or email us."},
        ],
    },
]
