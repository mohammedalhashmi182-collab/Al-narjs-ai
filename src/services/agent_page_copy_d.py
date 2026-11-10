"""Public agent pages, fourth group."""

from __future__ import annotations


def register(put, faq) -> None:
    put(
        "software_engineer",
        (
            "مهندس البرمجيات يحوّل طلبًا مفهومًا إلى خطوات بناء أو إصلاح يقدر صاحب النشاط أن يراجع نطاقها قبل التنفيذ. المدخل: ماذا يفعل النظام اليوم، وما العطل أو الإضافة، وما الذي لا يجب أن يتغير. من غير هذا الحد يتحول العمل إلى إعادة بناء صامتة.",
            "الشرح بلغة يفهمها صاحب الطلب: أي جزء يُلمس، وما الاختبار الذي يثبت أن العطل زال، وما الأثر الجانبي المتوقع. لا وعد بأن الكود مثالي. إن نقصت معلومة عن البيئة، نتوقف ونسأل بدل افتراض خادم أو لغة.",
            "الأسرار لا تُلصق في الطلب. مفتاح واجهة أو كلمة مرور تُستبعد ويُطلب من صاحب النشاط تدويرها إن وصلت بالخطأ. السجل الذي نسلمه يذكر ماذا تغيّر من غير أن ينسخ بيانات عملاء.",
            "هذا ليس استضافة ولا عقد تشغيل دائم من الصفحة نفسها. التسليم شرح وخطوات. التشغيل على بيئة صاحب النشاط وبموافقته. إن كان الربط مع نظام خارجي هو أصل الطلب، يُحال الوصف إلى مهندس التكاملات حتى لا يختلط إصلاح داخلي بربط خارجي.",
        ),
        (
            "The software engineer turns a request that can be understood into build or repair steps whose scope the owner can review before the work starts. The input is what the system does today, what is broken or added, and what must not change. Without that limit the work becomes a silent rebuild.",
            "The explanation uses words the requester can follow: which part is touched, which test shows the fault is gone, and which side effect is expected. There is no promise that the code is perfect. If the environment is missing, we stop and ask instead of assuming a server or a language.",
            "Secrets do not belong in the request. An API key or a password is removed, and the owner is asked to rotate it if it arrived by mistake. The note we deliver says what changed and does not copy customer data.",
            "This page is not hosting and not a standing operations contract. Delivery is an explanation and steps. Running them happens in the owner's environment, with their approval. If the real request is a connection to an outside system, the description goes to the integrations engineer so an internal fix is not mixed with an external link.",
        ),
        "لنفترض متجرًا يقول إن صفحة تأكيد الطلب تظهر مبلغًا مختلفًا عن السلة عندما يُضاف منتج واحد. هو يصف السلوك ولا يلصق مفتاح دفع. الخطة تقترح أين يُراجع حساب المجموع، واختبارًا بسلة من منتج واحد ومنتجين، وتوقفًا إذا كان الفرق من ضريبة لم تُشرح. لا إعادة تصميم للمتجر كله.",
        "Suppose a shop says the order confirmation shows a different amount from the basket when one product is added. The owner describes the behaviour and does not paste a payment key. The plan suggests where the total is calculated, a test with a one-item basket and a two-item basket, and a stop if the gap is a tax that was never explained. The whole shop is not redesigned.",
        faq(
            ("هل تلصقون مفاتيح الدفع؟", "لا. إن وصلت بالخطأ نطلب استبعادها وتدويرها."),
            ("هل تشغّلون الموقع عنا؟", "لا. نشرح الخطوات. التشغيل في بيئة صاحب النشاط وبموافقته."),
            ("ماذا لو كان الطلب ربطًا خارجيًا؟", "يُحال الوصف إلى مهندس التكاملات حتى لا يختلط الإصلاح بالربط."),
        ),
        faq(
            ("Should I paste payment keys?", "No. If one arrives by mistake we ask for it to be removed and rotated."),
            ("Do you run the site for us?", "No. We explain the steps. Running them happens in your environment, with your approval."),
            ("What if the request is an external connection?", "The description goes to the integrations engineer so a fix is not mixed with a connection."),
        ),
    )
    put(
        "orchestrator",
        (
            "الرئيس التنفيذي الافتراضي يقرأ وصف المشكلة ويرتب من يبدأ العمل، لا يكتب كل المخرجات بنفسه. هو يسأل عن الهدف، والقيد، وما الذي يُعد جوابًا كافيًا هذا الأسبوع. ثم يسمي الوكلاء الذين يلمسون الموضوع، ولماذا، وبأي ترتيب حتى لا يسبق النصُ القرارَ.",
            "الاقتراح يلتزم بأصغر مجموعة تكفي. إضافة وكيل من غير مهمة ظاهرة تُرفض داخل التوصية نفسها. الباقة والسعر لا يُخترعان هنا. إن ذُكرت باقة، فهي من الكتالوج المعروض في صفحة الباقات، وبالاسم والسعر المنشورين هناك.",
            "هو لا يعد بنتيجة تجارية. يقول ما الذي سيعود به كل وكيل: خطة، أو مسودة، أو ملاحظة أرقام. صاحب النشاط يعتمد الترتيب أو يغيّره. الرفض جزء من العمل، لا فشل في الأداة.",
            "التنفيذ بعد الاعتماد عند الوكلاء المختصين، والمراجعة عند بوابة الجودة حين يكون المخرج للعميل. الرئيس يرتب ويوقف التوسع. لا يجمع وعود الوكلاء في جملة واحدة أقوى من كل واحد منهم.",
        ),
        (
            "The virtual chief executive reads the problem and orders who starts, and does not write every deliverable. It asks for the goal, the constraint, and what would count as a sufficient answer this week. It then names the agents who touch the subject, why, and in which order, so copy does not run ahead of the decision.",
            "The proposal stays with the smallest set that is enough. Adding an agent with no visible task is rejected inside the recommendation itself. Plan and price are not invented here. If a plan is named, it comes from the catalog on the pricing page, with the published name and price.",
            "It does not promise a commercial result. It says what each agent will bring back: a plan, a draft, or a note on figures. The owner accepts the order or changes it. A refusal is part of the work, not a failure of the tool.",
            "After acceptance, the specialist agents do the work, and the quality gate reviews a deliverable that will reach a customer. The chief executive orders the work and stops the spread. It does not merge the agents' promises into one sentence stronger than any of them.",
        ),
        "لنفترض صاحب مقهى يقول إن العملاء يسألون عن الحجز وإن الوصف في الخرائط قديم. الترتيب: موظف الخدمة يجهّز رد الحجز بعد أن تُكتب قاعدة الحجز، وكاتب المحتوى يحدّث وصفًا قصيرًا من الحقائق التي يلصقها صاحب المقهى، ولا يُستدعى محلل سوق لأن السؤال تشغيلي. لا جملة عن ارتفاع المبيعات.",
        "Suppose a café owner says customers ask about booking and the map description is out of date. The order is: the service agent drafts a booking reply after a booking rule is written, and the content writer updates a short description from facts the owner pastes. A market analyst is not called, because the question is operational. There is no sentence about higher sales.",
        faq(
            ("هل يكتب كل النصوص بنفسه؟", "لا. يرتب من يكتب، ثم يعتمد صاحب النشاط الترتيب."),
            ("هل يختار باقة بسعر من عنده؟", "لا. أي باقة تُذكر من الكتالوج المنشور، بالاسم والسعر المعروضين."),
            ("هل يعد بنتيجة؟", "لا. يحدد ماذا سيعود به كل وكيل. النتيجة التجارية لا تُخمَّن."),
        ),
        faq(
            ("Does it write every text itself?", "No. It orders who writes, then the owner accepts that order."),
            ("Does it pick a plan at a price of its own?", "No. Any plan it names comes from the published catalog, with the published name and price."),
            ("Does it promise a result?", "No. It states what each agent will bring back. A commercial result is not guessed."),
        ),
    )
    put(
        "policy_guardian",
        (
            "حارس السياسات يفحص طلبًا قبل أن يُنفذ، ويفرّق بين ممنوع، وبين ما يحتاج موافقة صاحب النشاط، وبين ما يمكن أن يمضي. القاعدة تُكتب من سياسات النشاط التي يلصقها، لا من ذوق الوكيل. إن لم توجد سياسة، نقول ذلك ولا نخترع بندًا.",
            "الممنوع مثاله: وعد استرداد بنتيجة محددة، أو خصم يتجاوز الحد المكتوب، أو استخدام بيانات عميل في مثال عام. ما يحتاج موافقة مثاله: تغيير مدة التوصيل، أو ذكر اسم شريك. ما يمضي مثاله: إعادة ترتيب جملة لا تغيّر الالتزام.",
            "الفحص قصير ومعلل. كل بند فيه الجملة التي أوقفها والسبب والقاعدة التي استند إليها إن وُجدت. من غير قاعدة مكتوبة يُعلَّم البند بأنه قرار صاحب النشاط لا مخالفة مكتشفة.",
            "الحارس لا يستبدل بوابة الجودة. البوابة تراجع اكتمال المخرج وأسلوبه. الحارس يراجع هل الطلب نفسه مسموح قبل أن يُصرف وقت الكتابة. الاثنان لا يكرران الملاحظة ذاتها بصيغتين.",
        ),
        (
            "The policy guardian checks a request before it is carried out, and separates what is forbidden, what needs the owner's approval, and what may proceed. The rule is taken from policies the business pastes, not from the agent's taste. If no policy exists, we say so and do not invent a clause.",
            "Forbidden means, for example, a refund promise with a fixed outcome, a discount past the written cap, or using a customer's data in a public example. Needs approval means, for example, changing a delivery time or naming a partner. May proceed means, for example, reordering a sentence that does not change the commitment.",
            "The check is short and reasoned. Each item names the sentence that stopped, the reason, and the rule it rested on when one exists. With no written rule, the item is marked as the owner's decision, not as a discovered violation.",
            "The guardian does not replace the quality gate. The gate reviews whether a deliverable is complete and in voice. The guardian reviews whether the request itself is allowed before writing time is spent. The two do not repeat the same note in two styles.",
        ),
        "لنفترض طلبًا لكتابة رد يعد العميل باسترداد كامل خلال يوم لأن الطلب تأخر. سياسة النشاط الملصقة تقول إن الاسترداد يُراجع بالبريد ولا تُوعد نتيجته. الحارس يوقف جملة الاسترداد الكامل، ويسمح باعتذار عن التأخير من غير مبلغ، ويطلب موافقة قبل أي رقم تعويض. السبب مذكور بجانب الجملة.",
        "Suppose a request to draft a reply promising a full refund within a day because an order was late. The pasted policy says refunds are reviewed by email and no outcome is promised. The guardian stops the full-refund sentence, allows an apology for the delay with no amount, and asks for approval before any compensation figure. The reason sits beside the sentence.",
        faq(
            ("من أين تأتي القاعدة؟", "من السياسة التي يلصقها صاحب النشاط. لا قاعدة من ذوق الوكيل."),
            ("ماذا لو لم توجد سياسة؟", "نقول إنها غير موجودة. لا نخترع بندًا، ونعلّم القرار بأنه لصاحب النشاط."),
            ("ما الفرق عن بوابة الجودة؟", "الحارس قبل التنفيذ: هل الطلب مسموح. البوابة بعد المسودة: هل المخرج مكتمل."),
        ),
        faq(
            ("Where does the rule come from?", "From the policy the owner pastes. Not from the agent's taste."),
            ("What if there is no policy?", "We say it is missing. We do not invent a clause, and we mark the decision as the owner's."),
            ("How is this different from the quality gate?", "The guardian is before the work: is the request allowed. The gate is after the draft: is the deliverable complete."),
        ),
    )
    put(
        "quality_gate",
        (
            "بوابة الجودة تقرأ مخرجًا قبل أن يراه عميل، وتسأل هل اكتمل، وهل طابق الطلب، وهل بقيت فيه خانة فارغة أو رقم لا مصدر له. هي لا تعيد كتابة النص لتلميعه. تعيد ما ينقص مع سبب واحد لكل ملاحظة.",
            "الفحص يغطي اللغة العربية من حيث الفهم لا من حيث الزخرفة، واتجاه العرض إن كان النص سيُنشر، ومطابقة الأسماء لملف الأسلوب إن وُجد. جملة تعد بنتيجة لم تُطلب تُعلم حتى لو كانت سليمة نحويًا.",
            "القرار واحد من ثلاثة: يمر، أو يعود للوكيل بسبب محدد، أو يتوقف لأن الحقيقة ناقصة ولا يجوز تخمينها. لا درجة مجاملة. إذا مر النص، يبقى صاحب النشاط هو من يرسله.",
            "البوابة لا تستبدل مختصًا. النص القانوني الذي يحتاج محاميًا يُحال، والرقم المالي الحساس يُحال. هي تمنع أن يخرج مخرج نصف مكتمل، لا أن توقع على صحته التخصصية وحدها.",
        ),
        (
            "The quality gate reads a deliverable before a customer sees it, and asks whether it is complete, whether it matches the request, and whether an empty slot or an unsourced figure remains. It does not rewrite the text to polish it. It sends back what is missing, with one reason for each note.",
            "The check covers Arabic for understanding rather than decoration, reading direction if the text will be published, and whether names match the style profile when one exists. A sentence that promises a result nobody requested is marked even if the grammar is fine.",
            "The decision is one of three: it passes, it returns to the agent for a stated reason, or it stops because a fact is missing and must not be guessed. There is no courtesy score. If the text passes, the owner is still the person who sends it.",
            "The gate does not replace a specialist. Legal text that needs a lawyer is referred, and a sensitive financial figure is referred. The gate stops a half-finished deliverable from going out. It does not, by itself, sign that the specialist content is true.",
        ),
        "لنفترض وصف منتج مرّ من كاتب الوصف وفيه جملة الأكثر طلبًا هذا الموسم من غير مصدر، وخانة الوزن فارغة. البوابة تعيد الجملتين: احذفوا الأكثر طلبًا أو ضعوا مصدر صاحب المتجر، واملأوا الوزن أو اكتبوا أنه غير مؤكد. لا تعيد صياغة بقية الوصف.",
        "Suppose a product description from the description writer contains a sentence that it is the most requested this season, with no source, and an empty weight field. The gate sends back two notes: remove the most-requested line or supply the owner's source, and fill the weight or write that it is unconfirmed. The rest of the description is not rewritten.",
        faq(
            ("هل تعيدون كتابة النص؟", "لا. نعيد ما ينقص مع سبب. الصياغة تبقى لصاحبها."),
            ("هل المرور يعني أن العميل استلمه؟", "لا. المرور يعني أن المخرج اكتمل للمراجعة. الإرسال قرار صاحب النشاط."),
            ("هل تغنون عن محامٍ أو محاسب؟", "لا. نحيل ما يحتاج مختصًا. نمنع خروج نصف المخرج فقط."),
        ),
        faq(
            ("Do you rewrite the text?", "No. We send back what is missing, with a reason. The wording stays with its author."),
            ("Does a pass mean the customer received it?", "No. A pass means the deliverable is complete enough to review. Sending it is the owner's decision."),
            ("Do you replace a lawyer or an accountant?", "No. We refer what needs a specialist. We only stop a half-finished deliverable from going out."),
        ),
    )
    put(
        "prototype_engineer",
        (
            "مهندس النماذج الأولية يحوّل فكرة منتج رقمي إلى تسلسل شاشات ونطاق بناء يمكن قراءته قبل أي تنفيذ. المدخل: من يستخدم المنتج، وما المهمة الأولى التي يجب أن تنجح، وما الذي خارج النسخة الأولى. شاشة لا تخدم المهمة الأولى لا تدخل الرسم.",
            "لكل شاشة: ما يراه المستخدم، وما الذي يكتبه، وما الذي يحدث إن نقص حقل، وأين يتوقف وينتظر إنسانًا. لا نرسم لوحة إدارة كاملة إذا كانت المهمة حجزًا واحدًا. النطاق الصغير يحمي من مشروع لا ينتهي.",
            "النموذج وصف وخطوات، لا تطبيق منشور. لا نعد بأن الشكل النهائي سيطابق الرسم في كل بكسل. نعد بأن المهمة الأولى موصوفة بما يكفي ليراجعها صاحب الفكرة ومصمم المنتجات من غير أن يختلفا على الهدف.",
            "الجدوى التقنية الظاهرة تُذكر بحد: ماذا نعرف عن الربط، وماذا نحتاج من مهندس التكاملات لاحقًا. لا نختار مزودًا باسمه إن لم يختره صاحب الفكرة. الاختيار التجاري ليس جزءًا من الرسم.",
        ),
        (
            "The prototype engineer turns a digital product idea into a screen sequence and a build scope that can be read before any implementation. The input is who uses it, which first task must succeed, and what sits outside the first version. A screen that does not serve that first task does not enter the sketch.",
            "For each screen: what the user sees, what they type, what happens if a field is missing, and where the flow stops for a person. We do not draw a full admin console if the task is one booking. A small scope protects the owner from a project that never ends.",
            "The prototype is a description and steps, not a published app. We do not promise the final look will match every pixel. We do promise the first task is described well enough that the owner and the product designer can review it without disagreeing about the goal.",
            "Visible technical limits are stated: what we know about connections, and what the integrations engineer must answer later. We do not name a vendor the owner did not choose. A commercial choice is not part of the sketch.",
        ),
        "لنفترض فكرة حجز طاولة لمقهى من غير قائمة طعام. المهمة الأولى: اختيار وقت وإرسال الاسم. الرسم شاشتان: الأوقات المتاحة، وتأكيد الاسم مع تنبيه إن تُرك فارغًا. قائمة الطعام ولوحة المخزون خارج النسخة. لا اسم نظام حجز تجاري.",
        "Suppose an idea for booking a café table, with no menu. The first task is choosing a time and sending a name. The sketch is two screens: available times, and a name confirmation that warns if the name is empty. The menu and a stock console are outside this version. No commercial booking product is named.",
        faq(
            ("هل تسلّمون تطبيقًا؟", "لا. تسلسل شاشات ونطاق. التنفيذ لاحق وبموافقة."),
            ("ماذا يخرج من النسخة الأولى؟", "كل ما لا يخدم المهمة الأولى. يُكتب خارج النطاق صراحة."),
            ("هل تختارون الأداة؟", "لا، ما لم يخترها صاحب الفكرة. الرسم يصف المهمة لا المزود."),
        ),
        faq(
            ("Do you deliver an app?", "No. A screen sequence and a scope. Building comes later, with approval."),
            ("What stays out of the first version?", "Anything that does not serve the first task. It is written as out of scope."),
            ("Do you choose the tool?", "No, unless the owner already chose it. The sketch describes the task, not a vendor."),
        ),
    )
    put(
        "product_designer",
        (
            "مصمم المنتجات يرتب الواجهة والهوية بالقدر الذي يخدم مهمة واضحة، لا لوحة مزاج عامة. المدخل: ما الشاشة أو الصفحة، وما الفعل الأساسي عليها، وهل توجد ألوان وخطوط معتمدة. إن لم توجد، نقترح اتجاهًا واحدًا يمكن رفضه، لا خمسة اتجاهات تُشتت القرار.",
            "الاقتراح يذكر التباين حتى يُقرأ النص على الخلفية، وترتيب العناصر بحسب الفعل لا بحسب الزخرفة، وما الذي يتكرر في كل صفحة حتى لا تُعاد الهوية في كل شاشة بشكل مختلف. الألوان المعتمدة في النرجس للمواد العامة سوداء وبيضاء والبرتقالي المعروف، لكن مادة العميل تتبع ملف أسلوبه إن وُجد.",
            "لا نعد بأن التصميم سيرفع التحويل. نسلم وصفًا يمكن لمهندس النماذج أو لصاحب النشاط أن يطابقه: ماذا في الأعلى، وماذا في الزر، وماذا في حالة الفراغ. الزر الذي لا فعل له يُحذف.",
            "الشعار والأصول إن وُجدت تُستخدم كما هي. لا نعيد رسم شعار العميل من الذاكرة، ولا نضع شعار جهة لم تُذكر. إن غاب الشعار، نترك مكانه ونطلب الملف.",
        ),
        (
            "The product designer orders the interface and the identity only as far as a clear task needs, not as a mood board. The input is which screen or page, what the main action is, and whether colours and type are already approved. If they are not, we propose one direction that can be rejected, not five directions that scatter the decision.",
            "The proposal states contrast so text can be read on the background, the order of elements by action rather than decoration, and what repeats on every page so the identity is not reinvented on each screen. Al-Narjis materials use black, white, and the known orange. A client's material follows their style profile when one exists.",
            "We do not promise the design will raise conversion. We deliver a description the prototype engineer or the owner can match: what sits at the top, what the button says, and what the empty state shows. A button with no action is removed.",
            "A logo and assets, when they exist, are used as they are. We do not redraw a client's logo from memory, and we do not place an organisation's logo that was not named. If the logo is missing, we leave the space and ask for the file.",
        ),
        "لنفترض صفحة حجز لعيادة من غير هوية مكتوبة. الفعل الأساسي تأكيد الموعد. الاقتراح يضع اختيار اليوم ثم الوقت ثم زر التأكيد، وحالة فراغ تقول لا مواعيد ظاهرة بدل صورة عامة. لون الفعل واحد يمكن استبداله حين يصل ملف الهوية. لا شعار مخترع.",
        "Suppose a booking page for a clinic with no written identity. The main action is confirming an appointment. The proposal places day, then time, then a confirm button, and an empty state that says no times are visible instead of a generic picture. One action colour can be replaced when the identity file arrives. No invented logo.",
        faq(
            ("هل تعدون برفع التحويل؟", "لا. نصف ترتيب الصفحة والفعل. الأثر لا يُخمَّن."),
            ("ماذا لو لم يوجد شعار؟", "نترك المكان ونطلب الملف. لا نرسم شعارًا من الذاكرة."),
            ("كم اتجاهًا تقترحون؟", "اتجاه واحد يمكن رفضه. لا حزمة اتجاهات تُشتت القرار."),
        ),
        faq(
            ("Do you promise higher conversion?", "No. We describe the page order and the action. Effect is not guessed."),
            ("What if there is no logo?", "We leave the space and ask for the file. We do not draw a logo from memory."),
            ("How many directions do you propose?", "One direction that can be rejected. Not a pack of directions that scatters the decision."),
        ),
    )
    put(
        "qa_engineer",
        (
            "مهندس ضمان الجودة يكتب حالات اختبار لمسار معروف قبل أن يُقال إن العمل جاهز. المدخل: ماذا يجب أن يفعل النظام، وما المثال الطبيعي، وما الحافة التي تهم صاحب النشاط: حقل فارغ، أو رقم حد، أو انقطاع. حالة من غير نتيجة متوقعة ليست حالة.",
            "لكل حالة: الخطوة، والمدخل، والنتيجة التي تُعد نجاحًا، والنتيجة التي تُعد فشلًا. لا نكتب نجح النظام بشكل عام. إذا لم تُعرف النتيجة الصحيحة، نوقف الحالة ونطلبها. التخمين هنا يخفي العطل.",
            "القرار في النهاية: يمكن التجربة على المسار الموصوف، أو لا يمكن لأن حالة أساسية فشلت أو لأن وصف السلوك ناقص. هذا ليس إطلاقًا للمتجر ولا شهادة أمن. الإطلاق قرار صاحب النشاط بعد أن يقرأ الحالات.",
            "الاختبار على ما لُصق من سلوك أو خطوات، لا على بيئة إنتاج يدخلها الوكيل وحده. بيانات العملاء الحقيقية لا تُستخدم كأمثلة. نطلب بيانات تجريبية.",
        ),
        (
            "The QA engineer writes test cases for a known path before anyone says the work is ready. The input is what the system should do, the ordinary example, and the edge that matters to the owner: an empty field, a limit, or an interruption. A case with no expected result is not a case.",
            "Each case has the step, the input, the result that counts as success, and the result that counts as failure. We do not write that the system generally passed. If the correct result is unknown, we stop the case and ask for it. Guessing here hides the fault.",
            "The closing decision is: the described path can be tried, or it cannot, because a basic case failed or the behaviour was not described. This is not a shop launch and not a security certificate. Launch is the owner's decision after they read the cases.",
            "Testing uses behaviour or steps that were pasted, not a production environment the agent enters alone. Real customer data is not used as examples. We ask for trial data.",
        ),
        "لنفترض نموذج حجز يرفض الاسم الفارغ ويقبل موعدًا داخل ساعات العمل فقط. الحالات: اسم فارغ يُتوقع رفضه، وموعدًا داخل الساعات يُتوقع قبوله، وموعدًا بعد الإغلاق يُتوقع رفضه. لا حالة عن سرعة الصفحة لأن السرعة لم تُذكر كشرط. القرار يتوقف إن لم يعرف صاحب النموذج نص رسالة الرفض.",
        "Suppose a booking form rejects an empty name and accepts a time only inside working hours. The cases are: an empty name should be rejected, a time inside hours should be accepted, and a time after closing should be rejected. There is no case about page speed, because speed was not a stated condition. The decision stops if the owner does not know the text of the rejection message.",
        faq(
            ("هل هذا إطلاق للمتجر؟", "لا. حالات لمسار موصوف. الإطلاق بعد أن يقرأها صاحب النشاط."),
            ("هل تستخدمون بيانات عملاء؟", "لا. نطلب بيانات تجريبية. البيانات الحقيقية لا تُستخدم كأمثلة."),
            ("ماذا لو لم تُعرف النتيجة الصحيحة؟", "نتوقف ونطلبها. لا نخمّن النجاح."),
        ),
        faq(
            ("Is this a shop launch?", "No. Cases for a described path. Launch comes after the owner reads them."),
            ("Do you use customer data?", "No. We ask for trial data. Real customer data is not used as examples."),
            ("What if the correct result is unknown?", "We stop and ask for it. We do not guess a pass."),
        ),
    )
    put(
        "integrations_engineer",
        (
            "مهندس التكاملات يصف كيف يلتقي نظامان عند حدث واضح، بأقل صلاحية تكفي. المدخل: اسم النظام كما يكتبه صاحب النشاط، والحدث الذي يبدأ الربط، وما الذي يُنقل، وما الذي لا يُنقل. ربط من غير حدث يبقى شعارًا لا تصميمًا.",
            "الوصف يذكر ماذا يحدث إذا تكرر الحدث، حتى لا يُنشأ طلب مرتين، وماذا يحدث إذا فشل الإرسال: إعادة مرة مفهومة أو إيقاف وتنبيه. لا نخترع نقطة ربط لم يذكر صاحب النشاط أنها متاحة عنده.",
            "ربط سلة أو زد المباشر غير مشمول كتشغيل حي في هذه الصفحة. يمكن وصف ما سيُطلب حين يتاح الربط، من غير ادّعاء أن الطلبات تُقرأ الآن. أي جملة تقول تم الربط تُحذف.",
            "المفاتيح لا تُلصق. الصلاحية تُسمى بالحد الأدنى: قراءة أو إنشاء، لا صلاحية مدير إن كانت القراءة تكفي. صاحب النشاط هو من ينشئ المفتاح في حسابه بعد أن يوافق على الوصف.",
        ),
        (
            "The integrations engineer describes how two systems meet at a clear event, with the smallest permission that is enough. The input is the system name as the owner writes it, the event that starts the connection, what is transferred, and what is not transferred. A connection with no event is a slogan, not a design.",
            "The description says what happens if the event repeats, so an order is not created twice, and what happens if sending fails: one understandable retry, or a stop and a notice. We do not invent an endpoint the owner has not said they have.",
            "A live Salla or Zid connection is not included on this page. We can describe what will be asked when a connection is available, without claiming orders are read now. Any sentence that says the connection is already done is removed.",
            "Keys are not pasted. Permission is named at the minimum: read or create, not an administrator permission if read is enough. The owner creates the key in their own account after they accept the description.",
        ),
        "لنفترض مكتبًا يريد أن يصله بريد داخلي عندما يُعلَّم طلب بأنه جاهز في جدول يلصقونه، لا من متجر حي. الحدث تغيير الحالة إلى جاهز. الوصف يقول إن تكرار الحالة نفسها لا يرسل بريدًا ثانيًا، وإن فشل الإرسال يُنبّه الشخص المسمى ولا يعيد المحاولة بلا حد. لا مفتاح في النص، ولا ادّعاء ربط بسلة.",
        "Suppose an office wants an internal email when an order in a pasted sheet is marked ready, not from a live shop. The event is the status changing to ready. The description says a repeated status does not send a second email, and a failed send notifies the named person and does not retry without a limit. No key is in the text, and there is no claim of a Salla connection.",
        faq(
            ("هل تربطون سلة أو زد الآن؟", "لا. الربط المباشر غير مشمول. نصف ما سيُطلب حين يتاح، من غير ادّعاء أنه يعمل."),
            ("هل ألصق المفتاح؟", "لا. المفتاح يُنشأ في حسابكم بعد الموافقة على الوصف."),
            ("ماذا عن تكرار الحدث؟", "يُكتب صراحة حتى لا يُنشأ الإجراء مرتين."),
        ),
        faq(
            ("Do you connect Salla or Zid now?", "No. A direct connection is not included. We describe what will be asked when it is available, without claiming it works."),
            ("Should I paste a key?", "No. The key is created in your account after the description is accepted."),
            ("What about a repeated event?", "It is written explicitly so the action is not created twice."),
        ),
    )
    put(
        "sales_closer",
        (
            "مسؤول الإقناع يكتب ردًا على اعتراض أو على سلة لم تكتمل، انطلاقًا من قيمة العرض المكتوب لا من ضغط. المدخل: ماذا قال العميل، وما المنتج وسعره كما اعتمده صاحب النشاط، وما حد الخصم الذي لا يُتجاوز من غير موافقة. خارج هذا الحد لا تُكتب جملة خصم.",
            "الرد يعيد الاعتراض كما قيل، ثم يوضح ما يشمله السعر، ثم يسأل سؤالًا واحدًا إن كان النقص معلومة لا خصمًا. لا نفترض أن كل تردد يطلب تخفيضًا. أحيانًا التردد موعد توصيل غير واضح.",
            "لا وعد بتوفر غير مؤكد، ولا تهديد بأن العرض ينتهي الليلة إن لم يُكتب ذلك عند صاحب النشاط. الإحياء هنا مسودة رسالة لا إرسال. صاحب النشاط يرسلها من قناته.",
            "إن كان الاعتراض خارج السياسة، يُحال إلى حارس السياسات قبل الصياغة النهائية. رقم التعويض لا يُخترع. إن لم يوجد حد، نطلب الحد ولا نضع رقمًا وسطًا.",
        ),
        (
            "The sales closer drafts a reply to an objection or to a basket that was not finished, from the value of the written offer, not from pressure. The input is what the customer said, the product and price as the owner approved them, and the discount cap that cannot be crossed without approval. Outside that cap, no discount sentence is written.",
            "The reply restates the objection as it was said, then explains what the price includes, then asks one question if the gap is a missing fact rather than a discount. We do not assume every hesitation is a request for a lower price. Sometimes the hesitation is an unclear delivery time.",
            "There is no promise of stock that is not confirmed, and no threat that the offer ends tonight unless the owner wrote that. Revival here is a draft message, not a send. The owner sends it from their own channel.",
            "If the objection sits outside policy, it goes to the policy guardian before the final wording. A compensation figure is not invented. If there is no cap, we ask for the cap and do not insert a middle number.",
        ),
        "لنفترض عميلًا قال إن السعر مرتفع مقارنة بتغليف بسيط، وسعر المنتج مكتوب، وحد الخصم صفر من غير موافقة. الرد يوضح ماذا يشمل السعر من غير تخفيض، ويسأل إن كان الاعتراض على التغليف أو على المحتوى. لا جملة تنتهي الليلة، ولا خصم مخفي.",
        "Suppose a customer said the price is high for simple packaging. The product price is written, and the discount cap is zero without approval. The reply explains what the price includes, with no reduction, and asks whether the objection is the packaging or the contents. There is no ends-tonight line and no hidden discount.",
        faq(
            ("هل تعطون خصمًا؟", "فقط داخل الحد الذي كتبه صاحب النشاط. من غيره لا تُكتب جملة خصم."),
            ("هل تُرسل الرسالة؟", "لا. مسودة يرسلها صاحب النشاط من قناته."),
            ("هل كل اعتراض يطلب تخفيضًا؟", "لا. قد يكون النقص موعدًا أو شرحًا. نسأل سؤالًا واحدًا قبل أي عرض."),
        ),
        faq(
            ("Do you give a discount?", "Only inside the cap the owner wrote. Otherwise no discount sentence is written."),
            ("Is the message sent?", "No. It is a draft the owner sends from their own channel."),
            ("Is every objection a request for a lower price?", "No. The gap may be a date or an explanation. We ask one question before any offer."),
        ),
    )
    put(
        "search_discovery",
        (
            "خبير البحث يرتب ظهور صفحة موجودة بما يطابق ما فيها، لا بما نريد أن تبدو عليه. المدخل: عنوان الصفحة الحالي، وما الذي تقدمه فعلًا، والعبارة التي يبحث بها العميل كما يقولها صاحب النشاط، والسوق واللغة. من غير الصفحة نفسها نعمل على نص يلصقه، ونقول إننا لم نر الموقع حيًا.",
            "الاقتراح يمس العنوان والوصف الظاهر والربط الداخلي بين الصفحات إن وُصفت. العبارة تُستخدم إن كانت صادقة. حشو العبارة في كل فقرة يُرفض. لا نعد بترتيب في نتائج البحث، ولا بتاريخ لظهور الصفحة.",
            "الصفحات الضعيفة تُشار إليها: عنوان يعد بأكثر من المتن، أو صفحة لا تجيب عن السؤال. العلاج محتوى أوضح عند كاتب المقالات أو كاتب الخدمة، لا خدعة تقنية. إن كان الموقع بطيئًا ولم تُقاس السرعة، لا نكتب رقمًا للسرعة.",
            "اللغة العربية لها تركيبها. لا نترجم عبارة إنجليزية حرفيًا ثم نكررها. الصفحة العربية تُراجع كصفحة عربية، والإنجليزية كإنجليزية، والرابط بينهما يُذكر حتى لا تتعارض النسختان.",
        ),
        (
            "The SEO expert orders the visibility of a page that already exists so it matches what is on the page, not what we wish the page looked like. The input is the current title, what the page actually offers, the phrase a customer uses as the owner states it, and the market and language. Without the page itself we work from pasted text, and we say we have not seen the live site.",
            "The suggestion touches the title, the visible description, and internal links between pages when those pages were described. A phrase is used when it is true. Stuffing the phrase into every paragraph is refused. We do not promise a rank in search results, or a date when the page will appear.",
            "Weak pages are pointed out: a title that promises more than the body, or a page that does not answer the question. The remedy is clearer content with the article writer or the service writer, not a technical trick. If the site is slow and speed was not measured, we do not write a speed figure.",
            "Arabic has its own structure. We do not translate an English phrase literally and then repeat it. An Arabic page is reviewed as Arabic, an English page as English, and the link between them is stated so the two versions do not conflict.",
        ),
        "لنفترض صفحة خدمة توصيل داخل الخبر عنوانها الأفضل في المملكة. المتن يتحدث عن الخبر فقط. الاقتراح يغيّر العنوان إلى توصيل داخل الخبر، ويمنع تكرار العبارة في كل فقرة، ويطلب من كاتب المحتوى شرح مدة التجهيز إن كانت معروفة. لا ترتيب متوقع، ولا رقم سرعة.",
        "Suppose a delivery-service page for Khobar is titled the best in the Kingdom. The body talks only about Khobar. The suggestion changes the title to delivery inside Khobar, stops the phrase from repeating in every paragraph, and asks the content writer to explain preparation time if it is known. No expected rank, and no speed figure.",
        faq(
            ("هل تضمنون ترتيبًا في البحث؟", "لا. نطابق العنوان والوصف لما في الصفحة. الترتيب لا يُوعد."),
            ("هل تحشون الصفحة بالعبارة؟", "لا. العبارة تُستخدم إن كانت صادقة. التكرار يُرفض."),
            ("ماذا لو لم نشارك الصفحة؟", "نعمل على النص الملصق ونقول إن الموقع الحي لم يُراجع."),
        ),
        faq(
            ("Do you guarantee a search rank?", "No. We match the title and description to the page. Rank is not promised."),
            ("Do you stuff the page with the phrase?", "No. The phrase is used when it is true. Repetition is refused."),
            ("What if we do not share the page?", "We work from the pasted text and say the live site was not reviewed."),
        ),
    )
    put(
        "security_compliance",
        (
            "خبير الأمن والامتثال يرتب ملاحظات حماية مما يصفه صاحب النشاط عن نظامه، لا من فحص صامت يتسلل إلى الحساب. المدخل: ما النظام، ومن يدخل إليه، وأين تُحفظ الأسرار، وما الحادث الذي يخشاه صاحب النشاط إن قال ذلك. من غير هذا الوصف لا ندّعي أننا فحصنا الخوادم.",
            "الملاحظة عملية: لا تشاركوا كلمة المرور في المحادثة، فصلتوا صلاحية من يقرأ عن من يعدّل، واكتبوا من يُبلَّغ إذا ضاع جهاز. لا قائمة عامة من مئة بند. ثلاث ملاحظات مرتبطة بوصفه تكفي لتبدأ.",
            "لا تقرير اختراق، ولا ادّعاء أن النظام آمن بعد الملاحظات. الملاحظة تقلل خطأً ظاهرًا. الاختبار الهجومي ليس هذه الصفحة ولا يُعرض كخدمة مستترة. إن احتاج النشاط فحصًا متخصصًا، نقول ذلك حدًا لا تخويفًا.",
            "بيانات العملاء في الأمثلة تُزال. إن لصق صاحب النشاط رقم هوية أو بطاقة، نطلب حذفه ولا نكرره في الملاحظة. الامتثال هنا ترتيب احترازي، لا فتوى بأن النشاط مطابق لنظام بعينه من غير مراجعة مختص.",
        ),
        (
            "The security and compliance expert orders protection notes from what the owner describes about their system, not from a silent probe into the account. The input is which system, who enters it, where secrets are kept, and which incident the owner fears if they say so. Without that description we do not claim we inspected the servers.",
            "A note is practical: do not share a password in the chat, separate who can read from who can change, and write who is told if a device is lost. Not a generic list of a hundred items. Three notes tied to the description are enough to start.",
            "There is no breach report, and no claim that the system is safe after the notes. A note reduces a visible mistake. An offensive test is not this page and is not offered as a hidden service. If the business needs a specialist test, we say so as a limit, not as a scare.",
            "Customer data in examples is removed. If the owner pastes an identity number or a card number, we ask for it to be deleted and we do not repeat it in the note. Compliance here is precautionary order, not a ruling that the business matches a named law without a specialist review.",
        ),
        "لنفترض عيادة تقول إن موظفين اثنين يدخلان البريد نفسه بكلمة واحدة، وإن المواعيد في جدول مشترك. الملاحظات: افصلوا الحسابين، ولا تضعوا كلمة المرور في رسالة، وسمّوا من يُبلَّغ إذا فُقد الجهاز. لا ادّعاء أن البريد أصبح آمنًا، ولا طلب رقم هوية مريض في المثال.",
        "Suppose a clinic says two staff enter the same mailbox with one password, and appointments sit in a shared sheet. The notes are: separate the accounts, do not put the password in a message, and name who is told if a device is lost. There is no claim the mailbox is now safe, and no request for a patient's identity number in the example.",
        faq(
            ("هل تفحصون الخوادم خلسة؟", "لا. نعمل على الوصف الذي يكتبه صاحب النشاط. لا فحص صامت."),
            ("هل تقولون إن النظام أصبح آمنًا؟", "لا. الملاحظة تقلل خطأً ظاهرًا. لا شهادة أمان."),
            ("ماذا عن أرقام الهوية في المثال؟", "تُحذف ولا تُكرر. نطلب من صاحب النشاط مسحها."),
        ),
        faq(
            ("Do you probe the servers quietly?", "No. We work from the description the owner writes. There is no silent test."),
            ("Do you say the system is now safe?", "No. A note reduces a visible mistake. There is no safety certificate."),
            ("What about identity numbers in an example?", "They are deleted and not repeated. We ask the owner to remove them."),
        ),
    )
    put(
        "legal_privacy",
        (
            "مستشار القانون والخصوصية يجهّز مسودة أو قائمة فحص تجعل مراجعة المحامي أقصر، ولا يحل محل المحامي. المدخل: ما الوثيقة، وما الذي تفعله المنشأة ببيانات العملاء فعلًا، وأي بلد يعرفه صاحب النشاط أنه معني. ما لا يعرفه يُكتب غير معروف.",
            "المسودة تستخدم عبارات النشاط لا عبارات منشأة أخرى. إذا كانت الممارسة لم تُوصف، لا نكتب أننا نشارك البيانات مع شركاء. الجملة الكاذبة في السياسة أسوأ من الفراغ. الفراغ يُعلَّم ليسده المحامي أو صاحب النشاط.",
            "نظام حماية البيانات الشخصية يُذكر كإطار يجب أن يراجعه مختص على واقع المنشأة، لا كختم مطابقة. هذه الصفحة لا تقول إنكم ملتزمون. تقول ماذا يجب أن تشرحوه للمحامي: ماذا تجمعون، ولماذا، وكم تبقونه، ومن يطلع عليه.",
            "العقد النهائي لا يُوقَّع هنا. نسلّم نقاطًا وأسئلة. الاسترداد والالتزامات التجارية تتبع النصوص المنشورة في الشروط وسياسة الاسترداد، ولا نعد بنتيجة استرداد داخل المسودة.",
        ),
        (
            "The legal and privacy advisor prepares a draft or a checklist that makes a lawyer's review shorter, and does not replace the lawyer. The input is which document, what the business actually does with customer data, and which country the owner knows is relevant. What they do not know is written as unknown.",
            "The draft uses this business's practices, not another organisation's sentences. If a practice was not described, we do not write that data is shared with partners. A false sentence in a policy is worse than a gap. The gap is marked so the lawyer or the owner can fill it.",
            "The personal-data law is named as a frame a specialist must review against the real business, not as a compliance stamp. This page does not say you are compliant. It says what you should explain to the lawyer: what you collect, why, how long you keep it, and who can see it.",
            "The final contract is not signed here. We deliver points and questions. Refunds and commercial commitments follow the published terms and refund policy, and the draft does not promise a refund outcome.",
        ),
        "لنفترض متجرًا يريد قائمة فحص لسياسة خصوصية. هو يجمع الاسم والجوال لإتمام الطلب، ويحذف الطلب بعد مدة لم يحددها، ولا يشارك البيانات مع إعلان. القائمة تذكر الجمع للإتمام، وتعلّم مدة الحذف كفراغ، وتكتب أن المشاركة الإعلانية غير مذكورة فلا تُدعى. الجملة الأخيرة تطلب مراجعة محامٍ قبل النشر.",
        "Suppose a shop wants a checklist for a privacy policy. It collects a name and a mobile number to complete an order, deletes the order after a period it has not defined, and does not share data with advertising. The checklist states collection for completion, marks the deletion period as a gap, and says advertising sharing was not described so it is not claimed. The last line asks for a lawyer's review before publication.",
        faq(
            ("هل تغنون عن المحامي؟", "لا. نجهّز المسودة والأسئلة. الاعتماد والنشر بعد مراجعة مختص."),
            ("هل تقولون إن النشاط ملتزم؟", "لا. لا ختم مطابقة. نصف ما يجب شرحه فقط."),
            ("ماذا لو لم تُوصف الممارسة؟", "نترك فراغًا. لا ننسخ جملة من منشأة أخرى."),
        ),
        faq(
            ("Do you replace a lawyer?", "No. We prepare the draft and the questions. Acceptance and publication follow a specialist review."),
            ("Do you say the business is compliant?", "No. There is no compliance stamp. We only describe what should be explained."),
            ("What if a practice was not described?", "We leave a gap. We do not copy a sentence from another organisation."),
        ),
    )
    put(
        "finance_pricing",
        (
            "محلل المالية والتسعير يحسب من أرقام يلصقها صاحب النشاط: تكلفة، وسعر، وعدد، ووحدة. من غير هذه الأرقام لا هامش. لا نقدر التكلفة من نشاط مشابه، ولا نستخدم سعر باقة النرجس إلا إذا كان السؤال عن تلك الباقة كما هي منشورة في الكتالوج.",
            "الحساب يُعرض خطوة بخطوة حتى يستطيع محاسب صاحب النشاط أن يعيد الرقم. الوحدة تُذكر. خلط الشهر بالقطعة يُرفض. الضريبة تُدخل فقط إذا كتب صاحب النشاط أنها تُحصّل، وبالنظر إلى إعداد الضريبة في المنصة لا إلى رقم نختاره نحن.",
            "النتيجة تقول أي سعر يغطي التكلفة الظاهرة في الأرقام، وأي سعر لا يغطيها. لا نقول إن السعر سيرفع المبيعات. التغطية الحسابية غير الطلب في السوق. الطلب عند محلل السوق إن لزم.",
            "التوقع لعدة أشهر، إن طُلب بسيناريوهات، يُحال إلى محلل التوقع المالي حتى لا نخلط هامش وحدة بتوقع نمو. هنا اقتصاد الوحدة والسعر. هناك الأفق.",
        ),
        (
            "The finance and pricing analyst calculates from figures the owner pastes: a cost, a price, a count, and a unit. Without those figures there is no margin. We do not estimate cost from a similar business, and we do not use an Al-Narjis plan price unless the question is about that plan as it is published in the catalog.",
            "The calculation is shown step by step so the owner's accountant can repeat the figure. The unit is stated. Mixing a month with a piece is refused. Tax is included only if the owner wrote that it is collected, and it follows the tax setting on the platform rather than a rate we choose.",
            "The result says which price covers the cost visible in the figures, and which price does not. We do not say the price will raise sales. Arithmetic coverage is not market demand. Demand belongs with the market analyst when it is needed.",
            "A multi-month forecast, when scenarios are requested, goes to the financial forecast analyst so a unit margin is not mixed with a growth forecast. Here the subject is unit economics and price. There the subject is the horizon.",
        ),
        "لنفترض منتجًا تكلفته الظاهرة أربعون ريالًا للقطعة من غير شحن، وسعر البيع ستين، والضريبة غير مفعّلة في وصف صاحب المتجر. الحساب يطرح التكلفة من السعر ويذكر أن الشحن غير داخل، وأن الضريبة لم تُدخل لأنها غير مذكورة كمحصّلة. لا جملة عن أن السعر مناسب للسوق.",
        "Suppose a product whose visible cost is forty riyals a piece excluding shipping, the selling price is sixty, and tax is not described as collected. The calculation subtracts cost from price and states that shipping is outside it, and that tax was not included because it was not described as collected. There is no sentence that the price suits the market.",
        faq(
            ("هل تقدّرون التكلفة؟", "لا. من غير رقم ملصق لا هامش. لا تقدير من نشاط شبيه."),
            ("هل الضريبة دائمًا داخل الحساب؟", "فقط إذا كتب صاحب النشاط أنها تُحصّل. وإلا تُستبعد ويُذكر ذلك."),
            ("هل تقولون إن السعر سيرفع البيع؟", "لا. نقول إن كان السعر يغطي التكلفة الظاهرة. الطلب ليس هذا الحساب."),
        ),
        faq(
            ("Do you estimate the cost?", "No. Without a pasted figure there is no margin. No estimate from a similar business."),
            ("Is tax always inside the calculation?", "Only if the owner wrote that it is collected. Otherwise it is excluded and that is stated."),
            ("Do you say the price will raise sales?", "No. We say whether the price covers the visible cost. Demand is not this calculation."),
        ),
    )
    put(
        "localization",
        (
            "خبير التعريب يعيد كتابة نص حتى يُقرأ لجمهور محدد، لا يستبدل كلمة بكلمة. المدخل: النص، والسوق، ونوعه: واجهة، أو منتج، أو بريد، أو تسويق. ما كان دعابة في لغة قد يكون إساءة في أخرى. نسأل عن الممنوع قبل أن نختار المثل.",
            "العملة والوحدة والمثال تُستبدل بما يناسب السوق إن كان صاحب النص يسمح. لا نغيّر رقم سعر من غير إشارة. الاسم التجاري يبقى كما سجله صاحبه. المصطلح المتخصص يُثبت مرة ثم يُستخدم بثبات حتى لا تتعدد الترجمات في الصفحة نفسها.",
            "النص القانوني لا يُعرَّب كأنه نص تسويق. إن كان المصدر عقدًا، نعلّم أن المراجعة لمحامٍ في السوق الهدف لازمة، ونحافظ على التحفظ لا على الخفة. التعريب هنا وضوح، لا تخفيف التزام.",
            "المخرج نسختان يمكن مقارنتهما: الأصل، وما تغيّر ولماذا. لا ندّعي أن النص أصبح معتمدًا في جهة رسمية. الاعتماد عند صاحب النص ومن يراجعه.",
        ),
        (
            "The localization expert rewrites a text so it reads for a named audience. It does not swap word for word. The input is the text, the market, and the type: interface, product, email, or marketing. A joke in one language can be an insult in another. We ask what is forbidden before choosing an example.",
            "Currency, unit, and example are changed for the market when the owner allows it. A price figure is not changed without a mark. The brand name stays as the owner registered it. A specialist term is fixed once and then used steadily, so the same page does not carry several translations.",
            "Legal text is not localised as if it were marketing. If the source is a contract, we mark that a lawyer in the target market still has to review it, and we keep the caution rather than the lightness. Localization here is clarity, not a lighter obligation.",
            "The output is two versions that can be compared: the source, and what changed and why. We do not claim the text is now accepted by an official body. Acceptance sits with the owner and whoever reviews it for them.",
        ),
        "لنفترض واجهة تطبيق كُتبت لجمهور عام وتُراد لعميل في الرياض. زر الاشتراك المكتوب بلغة أجنبية يصبح اشترك، والمثال بالدولار يُعلَّم ليبدله صاحب التطبيق بالريال إن كان السعر بالريال، ولا نغيّر الرقم وحدنا. دعابة عن البطء تُحذف لأن صاحب النص منع السخرية. اسم المنتج يبقى كما كُتب.",
        "Suppose an interface written for a general audience is wanted for a customer in Riyadh. A subscribe button becomes the Arabic word for subscribe. A dollar example is marked so the owner can switch it to riyals if the price is in riyals. We do not change the figure alone. A joke about slowness is removed because the owner banned mockery. The product name stays as written.",
        faq(
            ("هل تغيّرون السعر؟", "لا من غير إشارة. الرقم يبقى، والعملة تُعلَّم ليؤكدها صاحب النص."),
            ("هل التعريب ترجمة حرفية؟", "لا. نعيد الصياغة للجمهور، ونثبت المصطلح حتى لا يتعدد."),
            ("هل تعتمد جهة رسمية النص؟", "لا. الاعتماد عند صاحب النص ومن يراجعه. العقد يحتاج محاميًا."),
        ),
        faq(
            ("Do you change the price?", "Not without a mark. The figure stays, and the currency is flagged for the owner to confirm."),
            ("Is localization a literal translation?", "No. We rewrite for the audience, and we keep one term so it does not multiply."),
            ("Does an official body accept the text?", "No. Acceptance sits with the owner and their reviewer. A contract still needs a lawyer."),
        ),
    )
    put(
        "lead_acquisition",
        (
            "وكيل اكتساب العملاء المحتملين يرتب فرصًا وردت فعلًا، ويصيغ رسالة أولى لكل فرصة تستحق المتابعة. المدخل: من أين جاءت الفرصة، وما العرض والسعر المعتمد، وما الذي يجعل الفرصة جاهزة أو غير جاهزة بحسب قاعدة صاحب النشاط. من غير قاعدة نسأل ولا نخترع درجة حرارة للفرصة.",
            "الترتيب على ما كُتب: هل سأل عن السعر، هل طلب موعدًا، هل اكتفى بتحية. التحية وحدها لا تُقدَّم على سؤال واضح. لا ندّعي أننا نعرف نية الشراء من اسم الشخص.",
            "الرسالة الأولى قصيرة، بلهجة مهنية، وتذكر العرض كما هو من غير مبالغة ومن غير وعد لم يُعتمد. لا اسم عميل حقيقي في الأمثلة العامة. إن لصق صاحب النشاط بيانات، تُستخدم لمسودته هو فقط ولا تُعرض كقصة نجاح.",
            "الإرسال ليس من هذه الصفحة. المسودة تعود لصاحب النشاط ليرسلها من بريده أو من قناته. لا شراء قوائم، ولا تخمين أرقام جوالات. الفرصة التي لا مصدر لها لا تُكتب.",
        ),
        (
            "The lead acquisition agent orders enquiries that actually arrived, and drafts a first message for each one that deserves a follow-up. The input is where the enquiry came from, the approved offer and price, and what makes an enquiry ready or not ready under the owner's own rule. Without a rule we ask. We do not invent a temperature for the lead.",
            "The order follows what was written: did they ask the price, did they request a time, or did they only send a greeting. A greeting alone is not placed above a clear question. We do not claim to know buying intent from a person's name.",
            "The first message is short, in a professional tone, and states the offer as it is, without exaggeration and without a promise that was not approved. A real customer's name is not used in a public example. If the owner pastes details, they are used only for their own draft and are not shown as a success story.",
            "Sending is not done from this page. The draft returns to the owner to send from their mail or their channel. There is no buying of lists and no guessing of mobile numbers. An enquiry with no source is not written.",
        ),
        "لنفترض ورشة سألت ثلاثة أشخاص هذا الأسبوع: واحد طلب سعر صيانة، وواحد أرسل تحية، وواحد سأل عن موعد معاينة. الترتيب يقدّم سؤال السعر ثم الموعد ثم التحية. رسالة السعر تذكر أن الرقم يُرسل بعد تأكيد الموديل، لأن الموديل غير معروف. لا خصم ترحيبي لم يُعتمد.",
        "Suppose a workshop heard from three people this week: one asked the price of a repair, one sent a greeting, and one asked for an inspection time. The order places the price question, then the time, then the greeting. The price message says the figure will be sent after the model is confirmed, because the model is unknown. There is no welcome discount that was not approved.",
        faq(
            ("هل تشترون قوائم عملاء؟", "لا. نرتب فرصًا وردت. لا تخمين لأرقام."),
            ("هل تُرسل الرسالة؟", "لا. المسودة لصاحب النشاط يرسلها من قناته."),
            ("كيف تُرتب الفرص؟", "بحسب ما كُتب: سؤال واضح قبل تحية. لا درجة من اسم الشخص."),
        ),
        faq(
            ("Do you buy contact lists?", "No. We order enquiries that arrived. Numbers are not guessed."),
            ("Is the message sent?", "No. The draft is for the owner to send from their own channel."),
            ("How are enquiries ordered?", "By what was written: a clear question before a greeting. Not a score from a person's name."),
        ),
    )
    put(
        "financial_forecast",
        (
            "محلل التوقع المالي يبني ثلاثة تقديرات من أرقام يلصقها صاحب النشاط: محافظ، وأساسي، ومتفائل. المدخل: أسعار الباقات أو المنتجات، وعدد العملاء الآن، ونسبة النمو التي يفترضها هو، ونسبة التسرب التي يفترضها، والتكاليف الثابتة والمتغيرة، وهل تُحسب الضريبة، وعدد الأشهر. الفرض يُكتب بجانب الرقم حتى لا يُقرأ كحقيقة.",
            "شهر التعادل يُذكر إن وقع داخل الأفق. إن لم يقع، نقول إنه خارج الأفق ولا نمد الأشهر حتى يظهر. التمديد الصامت يخفي الخسارة. التكاليف التي لم تُذكر تبقى خارج الحساب ويُعلن ذلك.",
            "الملف، حين يُطلب، يُراد بمعادلات يمكن لمحاسب أن يتتبعها، لا بأرقام ملصقة نتيجتها فقط. إن تعذر الملف في المحادثة، تُسرد المعادلة بالعربية حتى تُعاد. لا نعد بأن التقدير سيتحقق.",
            "هذا ليس تقييمًا للمنشأة ولا سعرًا للبيع. هو حساب على فرض صاحب النشاط. تغيير الفرض يغيّر الشهر. محلل المالية يحسب هامش الوحدة إن كان السؤال عن قطعة لا عن أفق.",
        ),
        (
            "The financial forecast analyst builds three estimates from figures the owner pastes: conservative, base, and optimistic. The input is plan or product prices, how many customers there are now, the growth rate the owner assumes, the churn rate the owner assumes, fixed and variable costs, whether tax is included, and how many months. The assumption is written beside the figure so it is not read as a fact.",
            "The break-even month is stated if it falls inside the horizon. If it does not, we say it is outside the horizon and we do not extend the months until it appears. A silent extension hides a loss. Costs that were not stated stay outside the calculation, and that is announced.",
            "The file, when requested, is meant to use formulas an accountant can follow, not pasted totals only. If a file is not possible in the conversation, the formula is written out so it can be repeated. We do not promise the estimate will come true.",
            "This is not a valuation of the business and not a sale price. It is a calculation on the owner's assumptions. Changing an assumption changes the month. The finance analyst calculates a unit margin when the question is about one item, not about a horizon.",
        ),
        "لنفترض نشاطًا يلصق: عشرون عميلًا الآن، ونمو يفترضه اثنان بالمئة شهريًا في الأساسي وواحد في المحافظ وثلاثة في المتفائل، وتسرب واحد بالمئة، وتكلفة ثابتة يعرفها، وأفق ستة أشهر، والضريبة غير محسوبة لأنه لم يفعّلها. التقدير يظهر التعادل إن وقع داخل الستة، وإلا يقول إنه خارجها. لا نضيف شهرًا سابعًا ليظهر التعادل.",
        "Suppose a business pastes: twenty customers now, growth the owner assumes at two percent a month in the base, one in the conservative, and three in the optimistic, churn at one percent, a fixed cost they know, a six-month horizon, and tax excluded because they have not switched it on. The estimate shows break-even if it falls inside the six months, and otherwise says it is outside them. A seventh month is not added to force break-even into view.",
        faq(
            ("هل التقدير سيتحقق؟", "لا. هو حساب على الفرض الذي لصقه صاحب النشاط. تغيير الفرض يغيّر النتيجة."),
            ("ماذا لو لم يظهر التعادل؟", "نقول إنه خارج الأفق. لا نطيل الأشهر حتى يظهر."),
            ("هل هذا تقييم للبيع؟", "لا. ليس سعر منشأة. هامش القطعة عند محلل المالية إن كان السؤال عن وحدة."),
        ),
        faq(
            ("Will the estimate come true?", "No. It is a calculation on the assumptions the owner pasted. Change an assumption and the result changes."),
            ("What if break-even does not appear?", "We say it is outside the horizon. We do not lengthen the months until it shows up."),
            ("Is this a valuation for a sale?", "No. It is not a price for the business. A unit margin belongs with the finance analyst when the question is about one item."),
        ),
    )
    put(
        "arabic_ocr",
        (
            "قارئ المستندات العربية يستخرج نصًا وحقولًا من ملف أو صورة يلصقها صاحب النشاط: فاتورة، أو إيصال، أو عقد. الحقول المعتادة المورّد والتاريخ والمبلغ والضريبة إن ظهرت. الحقل الذي لم يُقرأ بوضوح يُعلَّم بأنه ضعيف الثقة ولا يُستبدل برقم قريب.",
            "أرقام البطاقات والهوية لا تُعاد في الناتج ولا تُطلب للتخزين. إن ظهرت في الملف، تُحذف من المخرج ويُذكر أن الحقل أُزيل. لا نبني جدول عملاء من هذه الأرقام.",
            "الاستخراج ليس مراجعة محاسبية. مجموع الأسطر قد لا يطابق الإجمالي بسبب قص في الصورة. حين يحدث ذلك نذكر التعارض ولا نرجّح رقمًا. الترجيح لمحاسب صاحب النشاط.",
            "العقد المستخرج نص للمراجعة لا رأيًا قانونيًا. البنود التي لم تظهر في الصورة تُذكر كناقصة. لا نكمل بندًا من عقد شبيه.",
        ),
        (
            "The Arabic document reader extracts text and fields from a file or image the owner supplies: an invoice, a receipt, or a contract. Usual fields are the vendor, the date, the amount, and tax when it is visible. A field that was not read clearly is marked low confidence and is not replaced with a nearby figure.",
            "Card numbers and identity numbers are not returned in the output and are not kept. If they appear in the file, they are removed from the result and the note says the field was stripped. We do not build a customer table from those numbers.",
            "Extraction is not an accounting review. Line totals may not match the grand total because the image was cropped. When that happens we state the conflict and do not prefer a figure. Preference belongs to the owner's accountant.",
            "An extracted contract is text for review, not a legal opinion. Clauses that were not visible are listed as missing. We do not complete a clause from a similar contract.",
        ),
        "لنفترض صورة فاتورة يظهر فيها اسم المورّد والتاريخ والإجمالي، وسطر الكمية مقطوع، ورقم بطاقة في الهامش. المخرج يثبت المورّد والتاريخ والإجمالي، ويعلّم الكمية كضعيفة الثقة، ويحذف رقم البطاقة من غير أن يعيده. التعارض بين السطر والإجمالي يُذكر ولا يُحسم.",
        "Suppose an invoice image shows the vendor, the date, and the total. The quantity line is cut off, and a card number sits in the margin. The output keeps the vendor, the date, and the total, marks the quantity as low confidence, and removes the card number without repeating it. A conflict between the line and the total is stated and not settled.",
        faq(
            ("هل تحفظون أرقام البطاقات؟", "لا. تُحذف من المخرج ولا تُطلب للتخزين."),
            ("ماذا لو اختلف المجموع؟", "نذكر التعارض. لا نرجّح رقمًا. الحسم للمحاسب."),
            ("هل العقد المستخرج استشارة؟", "لا. نص ظاهر فقط. البند الناقص يبقى ناقصًا."),
        ),
        faq(
            ("Do you store card numbers?", "No. They are removed from the output and are not kept."),
            ("What if the totals disagree?", "We state the conflict. We do not prefer a figure. An accountant settles it."),
            ("Is an extracted contract advice?", "No. Only the visible text. A missing clause stays missing."),
        ),
    )
    put(
        "style_memory",
        (
            "ذاكرة الأسلوب تحفظ طريقة كتابة العلامة حتى لا يعيد كل وكيل السؤال نفسه. المدخل: إملاء الاسم بالعربية والإنجليزية، والفصحى أو اللهجة، والنبرة، والكلمات الممنوعة، والألوان والخطوط إن كانت هوية، والتوقيع الثابت. ما لم يُكتب لا يُخترع كجزء من الهوية.",
            "الملف يُحقن كتعليمات للوكلاء الذين يعملون لهذا العميل، لا كشعار يُنشر وحده. التعديل الذي يعتمده صاحب النشاط يُضاف كقاعدة: هذه الصيغة لا تلك. التعديل غير المعتمد لا يعلّم الملف حتى لا تتغير الهوية من مسودة رُفضت.",
            "اللهجة تُحترم داخل حد الوضوح. كلمة ممنوعة تُستبدل أو تُحذف أينما ظهرت في مسودة لاحقة، مع ذكر السبب. الألوان في مواد النرجس العامة تبقى الأسود والأبيض والبرتقالي، بينما مادة العميل تتبع ملفه هو.",
            "الملف ليس أرشيف محادثات العملاء. لا نحفظ شكوى عميل كأسلوب. الأسلوب طريقة كلام العلامة، لا سجل علاقات. الحذف من الملف متاح حين يطلبه صاحب النشاط.",
        ),
        (
            "Style memory keeps how the brand writes so every agent does not ask the same question again. The input is the brand spelling in Arabic and English, formal Arabic or dialect, tone, banned words, colours and type when they are identity, and the standing signature. What was not written is not invented as part of the identity.",
            "The profile is injected as instructions for agents working for that client, not as a badge published on its own. An edit the owner approves is added as a rule: this form, not that one. An edit that was not approved does not teach the profile, so identity does not change from a rejected draft.",
            "Dialect is respected inside the limit of clarity. A banned word is replaced or removed wherever it appears in a later draft, and the reason is stated. Al-Narjis public materials stay black, white, and orange. A client's material follows their own profile.",
            "The profile is not an archive of customer conversations. We do not store a customer complaint as style. Style is how the brand speaks, not a relationship log. Removal from the profile is available when the owner asks.",
        ),
        "لنفترض علامة تكتب اسمها بشكل واحد بالعربية، وتمنع كلمة رخيص، وتريد فصحى في الصفحات ولهجة خفيفة في الرد القصير، وتوقيعًا ثابتًا باسم النشاط لا باسم شخص. الملف يثبت الإملاء والمنع ويفصل بين الصفحة والرد. مسودة رُفضت فيها كلمة رخيص لا تُعتمد كاستثناء. لا يُحفظ نص عميل.",
        "Suppose a brand spells its Arabic name one way, bans the word cheap, wants formal Arabic on pages and a light dialect in a short reply, and uses a standing signature in the business name rather than a person's name. The profile fixes the spelling and the ban, and separates the page from the reply. A rejected draft that used the banned word is not kept as an exception. No customer text is stored.",
        faq(
            ("هل يحفظ الملف شكاوى العملاء؟", "لا. الأسلوب طريقة العلامة. سجل العلاقة ليس هنا."),
            ("متى تتغير القاعدة؟", "حين يعتمد صاحب النشاط تعديلًا. المسودة المرفوضة لا تعلّم الملف."),
            ("ماذا عن كلمة ممنوعة؟", "تُحذف أو تُستبدل في المسودة التالية، ويُذكر السبب."),
        ),
        faq(
            ("Does the profile store customer complaints?", "No. Style is how the brand speaks. The relationship log is not here."),
            ("When does a rule change?", "When the owner approves an edit. A rejected draft does not teach the profile."),
            ("What about a banned word?", "It is removed or replaced in the next draft, and the reason is stated."),
        ),
    )
    put(
        "evaluation_loop",
        (
            "حلقة التقييم تقرأ مخرجًا قبل تسليمه وتعيد صياغته في جولات محدودة، مع درجة مكتوبة لا مجاملة. المحاور: هل الرقم له مصدر، وهل العربية مفهومة، وهل الاتجاه مناسب إن كان النشر عربيًا، وهل طابق الهوية، وهل اكتمل، وهل بقيت خانة فارغة أو عبارة لم تُستبدل.",
            "كل جولة تذكر ماذا تغيّر. بعد ثلاث جولات نتوقف ونسلّم الدرجات مع ما بقي مفتوحًا. الاستمرار بعد ذلك يخفي العيب بدل إصلاحه. التوقف قرار جودة لا عجزًا عن الكلام.",
            "الدرجة لا تُترجم إلى وعد بأن العميل سيقبل المخرج. هي أداة داخلية لصاحب النشاط وللبوابة. إن تعارضت الدرجة مع سياسة، السياسة تُقدَّم وتُعلَّم عبر حارس السياسات.",
            "الحلقة لا تخترع مصدرًا لترفع درجة الدقة. الرقم بلا مصدر يبقى بلا مصدر وتُخفَّض الدرجة. هذا أفضل من تلميع يخدع المراجعة.",
        ),
        (
            "The evaluation loop reads a deliverable before it is returned and revises it for a limited number of rounds, with a written score rather than a courtesy. The axes are: whether a figure has a source, whether the Arabic is understandable, whether direction fits if the piece will be published in Arabic, whether it matches the identity, whether it is complete, and whether an empty slot or an unreplaced phrase remains.",
            "Each round states what changed. After three rounds we stop and deliver the scores with what is still open. Continuing after that hides the defect instead of repairing it. Stopping is a quality decision, not an inability to write more.",
            "The score is not translated into a promise that the customer will accept the deliverable. It is an internal tool for the owner and for the gate. If a score conflicts with policy, policy wins and is marked through the policy guardian.",
            "The loop does not invent a source to raise the accuracy score. A figure with no source stays unsourced and the score stays lower. That is better than polish that fools the review.",
        ),
        "لنفترض نشرة أسبوعية فيها جملة وفرنا ساعات كثيرة بلا رقم، وفقرة عربية اتجاهها اختلط، وتوقيع لا يطابق الملف. الجولة الأولى تحذف جملة الساعات أو تطلب رقمًا من صاحب النشاط، وتصحح الاتجاه، وتستبدل التوقيع بالتوقيع المعتمد. إن بقي الرقم بلا مصدر بعد ثلاث جولات، تُسلَّم النشرة مع درجة دقة منخفضة وعبارة أن المصدر لم يصل.",
        "Suppose a weekly note contains a sentence that many hours were saved, with no figure, an Arabic paragraph whose direction is mixed, and a signature that does not match the profile. The first round removes the hours sentence or asks the owner for a figure, corrects the direction, and replaces the signature with the approved one. If the figure still has no source after three rounds, the note is delivered with a low accuracy score and a line that the source never arrived.",
        faq(
            ("كم جولة تصحيح؟", "حتى ثلاث، ثم تتوقف الحلقة وتسلّم الدرجات مع ما بقي مفتوحًا."),
            ("هل الدرجة تعني قبول العميل؟", "لا. أداة داخلية. القبول قرار صاحب النشاط والعميل."),
            ("هل ترفعون الدرجة بمصدر مخترع؟", "لا. الرقم بلا مصدر يبقى بلا مصدر وتُخفَّض الدرجة."),
        ),
        faq(
            ("How many revision rounds?", "Up to three, then the loop stops and delivers the scores with what is still open."),
            ("Does the score mean the customer accepts it?", "No. It is an internal tool. Acceptance is the owner's and the customer's decision."),
            ("Do you raise the score with an invented source?", "No. A figure with no source stays unsourced and the score stays lower."),
        ),
    )
