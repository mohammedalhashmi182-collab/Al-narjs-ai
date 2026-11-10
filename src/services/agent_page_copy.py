"""Unique public copy for each specialist agent.

Arabic is the source. English carries the same facts in natural English.
Nothing here is a client name, a review, or a measured result.
"""

from __future__ import annotations


def register(put, faq) -> None:
    put(
        "social_media",
        (
            "مدير حسابات التواصل في النرجس يبني خطة نشر يمكن لصاحب النشاط أن يراجعها قبل أن تخرج أي جملة. العمل يبدأ من المنصة التي يركّز عليها النشاط اليوم، لا من قائمة منصات نطلب فتحها دفعة واحدة. نسأل عن الجمهور، وعن نوع المحتوى الموجود أصلًا، وعن الهدف القريب: تعريف بالخدمة، أو حجز، أو بيع منتج محدد. من هذه الإجابات تخرج خطة لأسبوعين أو لشهر، فيها محور كل منشور، والصيغة المقترحة، وما الذي ينقص قبل الكتابة: صورة، سعر، أو جملة لا يريد صاحب النشاط ظهورها.",
            "الخطة ليست تقويمًا فارغًا بعدد منشورات فقط. كل بند يشرح لماذا هذا المحور في هذا اليوم، وما الذي يجب أن يفهمه القارئ بعد المشاهدة. إذا كان النشاط يبيع في الرياض ويستقبل طلبات من خارجها، نفصل بين المنشور الذي يشرح التغطية والمنشور الذي يشرح طريقة الطلب، حتى لا يختلط الوعد. إذا كان التفاعل السابق ضعيفًا ولا رقم معروفًا له، نكتب ذلك كما هو ولا نخترع نسبة.",
            "صاحب النشاط يبقى صاحب الحساب. الوكيل لا يدخل إلى المنصة، ولا يجدول النشر بنفسه، ولا يرد على التعليقات إلا إذا طُلبت مسودة رد ووافق عليها صاحب النشاط. ما يُسلَّم هو نص وخطة. النشر، والرد، وإيقاف حملة، تبقى قرارات بشرية. وإن تغيّر العرض في منتصف الشهر، تُراجع البنود المتأثرة ولا نُبقي جملة تصف عرضًا انتهى.",
            "هذا الدور يجلس بجانب كاتب الإعلانات ومولّد الأفكار، لا بدلًا عنهما. الأفكار تعطيه محاورًا، وهو يرتبها على رزنامة. الإعلان المدفوع، إن وُجد، يُكتب في صفحة كاتب الإعلانات ثم يُشار إليه في الخطة حتى لا يعد المنشور العضوي بما يعده الإعلان. الحد الواضح يحمي صاحب النشاط من نصين يعدان بشيئين مختلفين في الأسبوع نفسه.",
        ),
        (
            "The social account manager at Al-Narjis builds a posting plan the owner can read before any line goes out. Work starts from the platform the business already uses, not from a list of new accounts to open. We ask who the audience is, what content already exists, and what the near goal is: explaining the service, taking a booking, or selling one product. From those answers comes a two-week or one-month plan. Each item names the theme, a suggested shape, and what is still missing: a photo, a price, or a sentence the owner does not want published.",
            "The plan is not an empty calendar that only counts posts. Each item says why that theme belongs on that day, and what the reader should understand afterwards. If the business sells in Riyadh and also takes orders from outside it, the plan separates a post about coverage from a post about how to order, so the promise does not blur. If past engagement is unknown, the page says unknown. It does not invent a rate.",
            "The owner keeps the account. This agent does not log in, does not schedule posts, and does not answer comments unless a reply draft was requested and approved. What comes back is copy and a plan. Publishing, replying, and stopping a campaign stay human decisions. If the offer changes mid-month, the affected items are revised. A sentence that describes an expired offer does not stay in the plan.",
            "This role sits beside the ad writer and the ideas generator. Ideas supply themes. This agent places them on a calendar. A paid ad, if there is one, is written on the ad-writer page and then pointed to from the plan, so the organic post and the ad do not promise two different things in the same week.",
        ),
        "لنفترض نشاطًا يبيع حلويات حسب الطلب وينشر على منصة واحدة ثلاث مرات في الأسبوع من غير محور ثابت. يكتب صاحبه: الجمهور عائلات تطلب لمناسبات نهاية الأسبوع، والهدف حجز، ولا يعرف نسبة التفاعل. الخطة المقترحة تفصل منشورًا يشرح مدة الطلب، ومنشورًا يشرح ما الذي يجب تأكيده قبل الدفع، ومنشورًا يعرض شكل التغليف من غير ادّعاء نفاد الكمية. كل بند يترك خانة للصورة الحقيقية. لا يُذكر عدد متابعين، ولا تُخترع مدينة توصيل لم يذكرها صاحب النشاط.",
        "Suppose a made-to-order sweet shop posts three times a week on one platform with no fixed theme. The owner writes: the audience is families ordering for the weekend, the goal is bookings, and the engagement rate is unknown. The suggested plan separates one post on how long an order takes, one post on what must be confirmed before payment, and one post on packaging that does not claim a sell-out. Each item leaves a slot for a real photo. No follower count is invented, and no delivery city is added that the owner did not name.",
        faq(
            ("هل ينشر الوكيل على الحساب مباشرة؟", "لا. يسلّم الخطة والنص. صاحب النشاط هو من ينشر، أو من يفوّض شخصًا في فريقه بعد المراجعة."),
            ("ماذا لو لم أعرف عدد المتابعين أو التفاعل؟", "اكتب أن الرقم غير معروف. الخطة تُبنى على الجمهور والهدف والعرض، ولا تحتاج نسبة مختلقة."),
            ("هل الخطة تشمل الإعلان المدفوع؟", "الخطة العضوية تُكتب هنا. نص الإعلان المدفوع يُطلب من كاتب الإعلانات حتى لا يختلط الوعدان."),
        ),
        faq(
            ("Does the agent post to the account?", "No. It returns the plan and the copy. The owner publishes, or asks someone on the team to publish after review."),
            ("What if I do not know followers or engagement?", "Write that the figure is unknown. The plan is built from the audience, the goal, and the offer. It does not need a made-up rate."),
            ("Does the plan include paid ads?", "The organic plan is written here. Paid ad copy is requested from the ad writer so the two promises stay separate."),
        ),
    )
    put(
        "ad_writer",
        (
            "كاتب الإعلانات يكتب نصًا لعرض واحد على منصة واحدة، لا حملة كاملة من غير حدود. قبل الكتابة نحدد المنتج أو الخدمة، والجمهور الذي يرى الإعلان، والفعل المطلوب بعد القراءة: طلب، أو اتصال، أو زيارة صفحة. نحدد أيضًا ما الذي لا يجوز قوله: خصم غير معتمد، أو مدة توصيل غير مؤكدة، أو عبارة طبية أو مالية تحتاج جهة مختصة. النص الذي يتجاوز هذا الحد يُعاد، ولا يُلمَّع بادّعاء أقوى.",
            "المسوّدة تأتي في أكثر من صيغة قصيرة حتى يستطيع صاحب النشاط أن يختار، لا حتى نُغرقه بعشرين عنوانًا متشابهًا. كل صيغة تذكر العرض كما كُتب، والفعل، وما الذي يجب أن يظهر بجانب النص إن كان صورة أو سعرًا. إذا كان السعر غير جاهز نترك مكانه فارغًا ونقول ذلك، بدل كتابة رقم تقريبي. الإعلان الذي يعدّ بسعر غير مؤكد يضر أكثر مما ينفع.",
            "هذا الوكيل لا يطلق الحملة، ولا يضبط الميزانية، ولا يختار الجمهور داخل أداة الإعلانات. تلك خطوات في حساب صاحب النشاط أو من يدير الإعلان له. ما يُسلَّم هو نص قابل للمراجعة، مع ملاحظة إن كانت العبارة قد تخالف سياسة المنصة المعروفة بشكل عام، من غير ادّعاء أن المراجعة تغني عن قراءة سياسة المنصة نفسها.",
            "عندما تكون الخطة العضوية عند مدير الحسابات، يُشار إلى الإعلان منها حتى يتفق الوعد. وإن كان العرض موسميًا، يُكتب تاريخ انتهاء العرض في المسوّدة نفسها. بعد هذا التاريخ لا يُعاد استخدام النص كما هو. التحديث جزء من التسليم، لا ملحقًا يُنسى.",
        ),
        (
            "The ad writer writes copy for one offer on one platform, not an unbounded campaign. Before writing, we name the product or service, the audience who will see the ad, and the action after reading: an order, a call, or a page visit. We also name what must not be said: an unapproved discount, a delivery time that is not confirmed, or a medical or financial claim that needs a specialist. Copy that crosses that line is sent back. It is not polished into a stronger claim.",
            "The draft comes in more than one short form so the owner can choose, not so the page can pile up twenty similar headlines. Each form repeats the offer as it was written, the action, and what must sit beside the words if a photo or a price is required. If the price is not ready, the slot stays empty and the draft says so, instead of inventing a round number. An ad that promises an unconfirmed price does more harm than good.",
            "This agent does not launch the campaign, set the budget, or pick the audience inside an ads tool. Those steps stay in the owner's account, or with the person who runs ads for them. What comes back is copy ready for review, plus a note when a phrase may conflict with a platform's general policy. That note does not replace reading the platform's own policy.",
            "When the organic plan lives with the account manager, the ad is pointed to from that plan so the promise matches. If the offer is seasonal, the end date is written into the draft. After that date the same text is not reused as it stands. Updating it is part of the delivery.",
        ),
        "لنفترض عيادة أسنان تريد إعلانًا واحدًا عن تنظيف الأسنان، لا عن علاج. تكتب: الجمهور بالغون في جدة، والفعل حجز موعد، ولا خصم، ومدة الموعد أربعون دقيقة إن حضر المريض في وقته. المسوّدة تذكر التنظيف والحجز والمدة، وتمتنع عن عبارة تشفي أو تقارن بعيادة أخرى. خانة السعر تبقى فارغة لأن العيادة لم تذكر رقمًا. النص لا يقول إن المواعيد متاحة اليوم.",
        "Suppose a dental clinic wants one ad about cleaning, not about treatment. It writes: the audience is adults in Jeddah, the action is booking, there is no discount, and the visit is forty minutes if the patient arrives on time. The draft names cleaning, booking, and the duration. It refuses a cure claim and a comparison with another clinic. The price slot stays empty because no figure was given. The text does not say same-day appointments are open.",
        faq(
            ("هل يضبط الوكيل ميزانية الإعلان؟", "لا. الميزانية والجمهور داخل أداة الإعلان يبقى عند صاحب الحساب. هنا يُكتب النص فقط."),
            ("ماذا لو لم أحدد السعر؟", "تُترك خانة السعر فارغة. لا نضع رقمًا تقريبيًا ولا عبارة تبدأ من دون أن تذكرها."),
            ("هل النص يضمن قبول المنصة؟", "لا. نتجنب العبارات المحظورة المعروفة بشكل عام، وصاحب النشاط يراجع سياسة المنصة قبل الإطلاق."),
        ),
        faq(
            ("Does the agent set the ad budget?", "No. Budget and audience inside the ads tool stay with the account owner. This page only writes the copy."),
            ("What if I have not set a price?", "The price slot stays empty. We do not insert a round number or a from-price you did not state."),
            ("Does the copy guarantee the platform will accept it?", "No. We avoid claims that are generally disallowed, and the owner still checks the platform policy before launch."),
        ),
    )
    put(
        "content_ideas",
        (
            "مولّد الأفكار لا يملأ جدولًا بعناوين عامة عن الجودة والثقة. يطلب المجال، والجمهور، وما الذي مُنع سابقًا لأن صاحب النشاط لا يريد تكراره. من ذلك يخرج بنك قصير، كل فكرة فيه بجملة تشرح الزاوية، لا بكلمة واحدة. الفكرة الجيدة يمكن أن تُرفض لأنها لا تناسب هذا الأسبوع، وهذا أفضل من نشر محور لا يملك النشاط مادة له.",
            "كل فكرة تُوسم بما تحتاجه قبل أن تُكتب: صورة من الشغل الحقيقي، سؤال من العملاء تكرر هذا الشهر، أو رقم يملكه صاحب النشاط ويريد إظهاره. إذا لم تتوفر المادة، تُؤجل الفكرة ولا تُستبدل بادّعاء. البنك يفرز أيضًا بين فكرة تصلح لمنشور عضوي وفكرة تصلح لبريد أو لوصف منتج، حتى لا تُستخدم الزاوية نفسها في ثلاثة أماكن بنص واحد.",
            "الأفكار اقتراحات. صاحب النشاط يحذف ما لا يشبهه، ويُبقي ما يستطيع الدفاع عنه لو سأله عميل. الوكيل لا يعد بأن الفكرة سترفع التفاعل، ولا يرتب البنك بحسب ترند لم يُفحص. إذا ذُكر ترند، يُذكر بوصفه ملاحظة يحتاج صاحب النشاط أن يتأكد أنها ما زالت مناسبة لجمهوره، لا بوصفها أمرًا بالنشر.",
            "بعد اختيار ثلاث أفكار كحد معقول لأسبوع، تنتقل إلى مدير الحسابات لترتيبها، أو إلى كاتب المحتوى لصياغتها. هذه الصفحة لا تكتب المنشور النهائي ولا خطة الشهر. فصل الخطوات يمنع أن تتحول قائمة أفكار إلى نص منشور من غير مراجعة.",
        ),
        (
            "The ideas generator does not fill a calendar with generic lines about quality and trust. It asks for the field, the audience, and what was banned before because the owner does not want it repeated. What comes back is a short bank. Each idea is a sentence that explains the angle, not a single word. A good idea can still be rejected because this week has no material for it. That is better than publishing a theme the business cannot support.",
            "Each idea is tagged with what it needs before it is written: a photo of the real work, a customer question that came up this month, or a figure the owner actually has and wants to show. If the material is missing, the idea waits. It is not replaced with a claim. The bank also separates an idea fit for an organic post from one fit for an email or a product description, so the same angle is not pasted into three places.",
            "Ideas are proposals. The owner deletes what does not sound like the business, and keeps what they could defend if a customer asked. The agent does not promise that an idea will raise engagement, and it does not rank the bank by a trend it has not checked. If a trend is mentioned, it is a note the owner should confirm still fits their audience, not an order to publish.",
            "After three ideas, a sensible week, they move to the account manager to be scheduled or to the content writer to be drafted. This page does not write the finished post or the month plan. Separating the steps stops a list of ideas from becoming a published text with no review.",
        ),
        "لنفترض مخبزًا في الخبر يريد أفكارًا لأسبوع من غير أن يعدّ بنفاد الكمية. يكتب: الجمهور موظفون يطلبون فطورًا، والممنوع صور مخزون قديم، والمادة المتوفرة هي وقت الجاهزية وسعر الصندوق العائلي. البنك يقترح فكرة عن الفرق بين الطلب اليومي والطلب للمناسبة، وفكرة عن ما يفسد لو تُرك الصندوق في السيارة، وفكرة سؤال للعميل عن وقت الاستلام. لا فكرة عن خصم، لأن الخصم لم يُذكر.",
        "Suppose a bakery in Khobar wants a week of ideas and will not claim a sell-out. It writes: the audience is people ordering breakfast, old stock photos are banned, and the available facts are the ready time and the family-box price. The bank suggests one idea on the difference between a daily order and an occasion order, one idea on what spoils if the box stays in a car, and one question about pickup time. There is no discount idea, because no discount was stated.",
        faq(
            ("كم فكرة أحصل عليها؟", "بنك قصير يمكن مراجعته، لا قائمة طويلة متشابهة. اختر ما تملك مادته هذا الأسبوع."),
            ("هل الأفكار منشورات جاهزة؟", "لا. هي زوايا. الصياغة النهائية عند كاتب المحتوى، والترتيب عند مدير الحسابات."),
            ("هل تتبعون الترند؟", "لا نأمر بالنشر لأن موضوعًا رائجًا. إن ذُكر، يبقى ملاحظة يتحقق منها صاحب النشاط."),
        ),
        faq(
            ("How many ideas do I get?", "A short bank you can review, not a long list of lookalikes. Choose what you have material for this week."),
            ("Are the ideas finished posts?", "No. They are angles. The content writer drafts them, and the account manager schedules them."),
            ("Do you follow trends?", "We do not order a post because a topic is popular. If a trend is mentioned, it stays a note for the owner to check."),
        ),
    )
    put(
        "marketing_agent",
        (
            "استراتيجي التسويق يرتب القرار قبل القنوات. يسأل عن العرض، والميزانية التي يستطيع النشاط صرفها فعلًا، والمدة، وما الذي يُعد نجاحًا يمكن قياسه من غير رقم مختلق. الخطة تسمي قناة أو قناتين للبداية، وتشرح ماذا يُختبر أولًا، وما الذي يُؤجل لأن مادته غير جاهزة. خطة تقول انشر في كل مكان ليست خطة.",
            "كل قناة في الخطة لها جملة عن الجمهور هناك، وجملة عن العرض المناسب لها، وجملة عن ما لا يُقاس بعد. إذا كان النشاط لا يملك أداة قياس، نكتب أن القياس سيكون بعدد الطلبات التي يذكر أصحابها مصدرهم، أو بسؤال واحد عند الحجز، لا بلوحة وهمية. الوضوح هنا أهم من شكل التقرير.",
            "الخطة لا تعتمد ميزانية لم يوافق عليها صاحب النشاط، ولا تعد بعائد. تضع سقف الصرف الذي كُتب، وتترك خانة لمن يوقف الصرف إذا تجاوز الحد. الإعلان، والمحتوى، وصفحات المنتج تُحال إلى الوكلاء المختصين بعد أن تُقفل هذه الحدود، حتى لا يكتب كل وكيل وعدًا مختلفًا.",
            "إذا كان النشاط في أكثر من مدينة، تُفصل الخطة بين مدينة جاهزة للبيع ومدينة ما زال التوصيل فيها غير مؤكد. لا ننسخ الخطة نفسها ونغيّر اسم المدينة. وما كان تجربة لشهر لا يتحول إلى التزام سنوي داخل النص.",
        ),
        (
            "The marketing strategist orders the decision before the channels. It asks for the offer, the budget the business can actually spend, the period, and what would count as success without an invented number. The plan names one or two channels to start, what to test first, and what waits because the material is not ready. A plan that says post everywhere is not a plan.",
            "Each channel gets one line on the audience there, one line on the offer that fits, and one line on what is not measured yet. If the business has no measurement tool, the plan says measurement will be orders whose owners name the source, or one question at booking, not a fake dashboard. Clarity matters more than the look of a report.",
            "The plan does not approve a budget the owner did not approve, and it does not promise a return. It writes the spend cap that was given, and leaves a line for who stops the spend if it passes the cap. Ads, content, and product pages go to the specialist agents only after those limits are closed, so each agent does not write a different promise.",
            "If the business works in more than one city, the plan separates a city that is ready to sell from a city where delivery is still unconfirmed. The same plan is not copied with the city name swapped. A one-month test does not become a yearly commitment inside the text.",
        ),
        "لنفترض متجر عطور يريد خطة لشهر بميزانية حددها صاحبه للإعلانات فقط، والبيع يتم عبر الطلب المباشر. الخطة تقترح قناة واحدة للتعريف وقناة واحدة للإعلان عن تشكيلة موجودة، وتؤجل قناة الفيديو لأن لا صور كافية. مقياس الشهر هو عدد الطلبات التي يذكر أصحابها الإعلان، لا نسبة عائد. سقف الصرف هو الرقم الذي كُتب، ومن يوقفه هو صاحب المتجر.",
        "Suppose a perfume shop wants a one-month plan. The owner has named an ads-only budget, and sales happen by direct order. The plan suggests one channel for explanation and one channel for an ad about a range that already exists. Video waits because there are not enough photos. The month is measured by orders whose customers mention the ad, not by a return rate. The spend cap is the figure the owner wrote, and the owner is the person who stops it.",
        faq(
            ("هل الخطة تعد بعائد؟", "لا. هي ترتيب للقنوات والاختبار والسقف. العائد لا يُخمَّن."),
            ("كم قناة نبدأ؟", "قناة أو قناتان جاهزتان. الباقي يُؤجل حتى تتوفر المادة أو القياس."),
            ("هل تشمل الخطة كتابة الإعلان؟", "لا. بعد تثبيت الحدود يُحال النص إلى كاتب الإعلانات والمحتوى إلى كاتب المحتوى."),
        ),
        faq(
            ("Does the plan promise a return?", "No. It orders channels, the test, and the cap. Return is not guessed."),
            ("How many channels do we start with?", "One or two that are ready. The rest wait until the material or the measurement exists."),
            ("Does the plan include the ad copy?", "No. After the limits are fixed, copy goes to the ad writer and content goes to the content writer."),
        ),
    )
