"""Extra paragraphs so each public agent page clears 300 words without a shared ending."""

from __future__ import annotations


def _add(pages: dict, slug: str, ar: str, en: str) -> None:
    page = pages[slug]
    page["paragraphs_ar"] = tuple(page["paragraphs_ar"]) + (ar,)
    page["paragraphs_en"] = tuple(page["paragraphs_en"]) + (en,)


def extend(pages: dict) -> None:
    _add(
        pages,
        "marketing_agent",
        "عند مراجعة الخطة بعد أسبوعين ننظر إلى ما كُتب أنه سيُختبر، لا إلى انطباع عام. إن لم تُجمع الملاحظة المتفق عليها، نوقف التوسع إلى قناة ثالثة حتى تُجمع. الخطة الأصلية تبقى مرجعًا: ما تغيّر يُكتب تحته بتاريخ، حتى لا تختفي النسخة التي وافق عليها صاحب النشاط. هذا المراجعة جزء من الاستراتيجية لا ملحقًا بعد انتهاء الشهر.",
        "Two weeks later the review looks at what the plan said would be tested, not at a general impression. If the agreed note was not collected, expansion to a third channel waits until it is collected. The original plan stays the reference. A change is written under it with a date, so the version the owner accepted does not disappear. That review is part of the strategy, not an appendix after the month ends.",
    )
    _add(
        pages,
        "text_improver",
        "بعد التسليم يستطيع صاحب النص أن يقبل بعض الجمل ويرفض بعضها. المقبول يُثبَّت، والمرفوض يعود إلى الأصل مع بقاء سبب الاقتراح مكتوبًا حتى لا يُعاد الاقتراح نفسه في طلب لاحق من غير أن يراه. لا ندمج النسختين بصمت. الدمج الصامت يجعل المراجعة مستحيلة. إن كان النص سيُنشر، نذكّر أن محسّن النصوص لا يتحقق من السعر ولا من السياسة.",
        "After delivery the owner can accept some sentences and reject others. What is accepted is kept. What is rejected returns to the original, and the reason for the suggestion stays written so the same suggestion is not repeated on a later request without being seen. We do not merge the two versions silently. A silent merge makes review impossible. If the text will be published, we remind the owner that the text improver does not check the price or the policy.",
    )
    _add(
        pages,
        "product_describer",
        "إذا كان للمتجر عشرات المنتجات، نبدأ بعينة يتفق عليها صاحب المتجر: ثلاثة أصناف مختلفة لا ثلاثة ألوان للمنتج نفسه. العينة تكشف إن كان الوصف يكرر جملة واحدة. بعد اعتماد العينة تُكتب البقية على القاعدة نفسها، ويُراجع صاحب المتجر أي صنف ناقص بياناته قبل النشر. لا نعد بأن الوصف سيظهر في أول نتائج البحث. الظهور مسألة صفحة البحث لا خانة الوصف وحدها.",
        "If the shop has dozens of products, we start with a sample the owner agrees: three different items, not three colours of the same item. The sample shows whether the description repeats one sentence. After the sample is accepted, the rest follow the same rule, and the owner reviews any item whose facts are incomplete before it is published. We do not promise the description will appear at the top of search. Visibility is a matter for the search page, not for the description field alone.",
    )
    _add(
        pages,
        "store_manager",
        "بعد أسبوع من تنفيذ ملاحظة واحدة، نسأل ماذا تغيّر في الأسئلة التي تصل المتجر، لا كم زاد البيع. إن بقي السؤال نفسه، فالملاحظة لم تُغلق أو لم تُفهم، فنعود إلى صياغة أوضح. لا نفتح قائمة جديدة قبل أن تُغلق الأولى. التراكم يوهم بالحركة. المتجر الصغير يستفيد من إغلاق خطوة ظاهرة أكثر من جمع عشرين اقتراحًا على الورق.",
        "A week after one note is carried out, we ask what changed in the questions reaching the shop, not how much sales rose. If the same question remains, the note was not closed or not understood, and we return to a clearer wording. We do not open a new list before the first one is closed. A pile of notes looks like movement. A small shop gains more from closing one visible step than from collecting twenty suggestions on paper.",
    )
    _add(
        pages,
        "customer_manager",
        "إذا تتابعت ثلاث حالات متشابهة في الملخصات الملصقة، نذكر التشابه كملاحظة على هذه الحالات فقط، ونقترح سؤالًا واحدًا يُضاف إلى الرد القادم حتى لا يتكرر الغموض. لا نبني برنامج ولاء ولا نقاطًا. النقاط من غير سياسة مكتوبة تصبح خصمًا مخفيًا. إن أراد صاحب النشاط برنامجًا، يُكتب حدّه أولًا عند حارس السياسات ثم يُصاغ.",
        "If three similar cases appear in the pasted summaries, we mention the similarity as a note on those cases only, and we suggest one question to add to the next reply so the ambiguity does not repeat. We do not build a loyalty programme or points. Points without a written policy become a hidden discount. If the owner wants a programme, its limit is written first with the policy guardian, then the wording is drafted.",
    )
    _add(
        pages,
        "customer_service",
        "نحتفظ في المسودة بعنوان داخلي يصف نوع الطلب: استفسار، أو تأخير، أو طلب لا تغطيه السياسة. العنوان لا يُرسل إلى العميل. هو لصاحب النشاط حتى يفرز الردود لاحقًا. إذا تكرر نوع واحد، يرى النمط من العناوين لا من انطباع. الرد نفسه يبقى قصيرًا. طول الاعتذار لا يعوّض معلومة ناقصة، بل يؤخر الجواب الذي ينتظره العميل.",
        "The draft keeps an internal label for the kind of request: a question, a delay, or a request the policy does not cover. The label is not sent to the customer. It is for the owner, so later replies can be sorted. If one kind repeats, the pattern is visible from the labels rather than from an impression. The reply itself stays short. A long apology does not replace a missing fact. It delays the answer the customer is waiting for.",
    )
    _add(
        pages,
        "email_writer",
        "إذا كانت الرسالة ستُحفظ كنموذج، نكتب في أعلاها متى تُستخدم ومتى لا تُستخدم. النموذج الذي يصلح لمتابعة ملف لا يصلح لشكوى. نترك بين الأقواس ما يجب أن يُستبدل في كل مرة: الاسم، والتاريخ، واسم الملف. القوس الفارغ الذي يُنسى في الإرسال أسوأ من رسالة كُتبت من الصفر. لذلك نطلب من صاحب النشاط أن يقرأ النموذج بصوت عالٍ مرة قبل اعتماده.",
        "If the message will be kept as a pattern, we write at the top when it is used and when it is not. A pattern that fits a file follow-up does not fit a complaint. We leave in brackets what must be replaced each time: the name, the date, and the file name. An empty bracket that is forgotten in the sent mail is worse than a message written from scratch. So we ask the owner to read the pattern aloud once before accepting it.",
    )
    _add(
        pages,
        "content_writer",
        "قبل اعتماد النص نراجعه بسؤال واحد: هل يستطيع شخص لم ير النشاط أن يفهم ماذا يُقدَّم وماذا لا يُقدَّم. إن عجز، فالنص ما زال داخليًا رغم أنه موجه للخارج. نعيد الفقرة الغامضة لا النص كله. وبعد الاعتماد لا نعيد فتح النص بسبب رغبة في تجميله. التجميل بعد الاعتماد يغيّر المعنى الذي وافق عليه صاحب النشاط من غير أن ينتبه.",
        "Before the text is accepted we review it with one question: can a person who has not seen the business understand what is offered and what is not. If they cannot, the text is still internal even though it faces outward. We redo the unclear paragraph, not the whole text. After acceptance we do not reopen the text because someone wants to decorate it. Decoration after acceptance changes the meaning the owner agreed, without them noticing.",
    )
    _add(
        pages,
        "article_writer",
        "نضع في أول المسودة سطرًا داخليًا بالسؤال الذي يجيب عنه المقال والأسئلة التي رُفضت. هذا السطر لا يُنشر. هو للمراجع حتى لا تُضاف في اللحظة الأخيرة فقرة عن موضوع استُبعد. إن أُضيفت فقرة لاحقة، تُراجع على هذا السطر. المقال الذي يتضخم بعد الاعتماد يعود إلى كاتب المقالات لا إلى النشر مباشرة. الطول الزائد يخفي الجواب الذي قُصد من البداية.",
        "At the top of the draft we place an internal line stating the question the article answers and the questions that were refused. That line is not published. It is for the reviewer, so a paragraph on a rejected topic is not added at the last minute. If a later paragraph is added, it is checked against that line. An article that swells after acceptance returns to the article writer rather than going straight to publication. Extra length hides the answer that was intended from the start.",
    )
    _add(
        pages,
        "content_manager",
        "في نهاية الفترة نكتب ماذا نُشر فعلًا مقابل ما خُطط، من غير تفسير بطولي للفجوة. الفجوة إما مادة لم تصل، أو مراجعة تأخرت، أو عرض أُلغي. السبب الواحد يكفي. الفترة التالية تبدأ من الطاقة الحقيقية التي ظهرت، لا من العدد الذي تمنيناه. إن كانت المراجعة لا تتجاوز قطعة في الأسبوع، فالتقويم التالي يُبنى على قطعة لا على أربع.",
        "At the end of the period we write what was actually published against what was planned, with no heroic reading of the gap. The gap is material that did not arrive, a review that was late, or an offer that was cancelled. One reason is enough. The next period starts from the real capacity that showed up, not from the count we wished for. If review never passed one piece a week, the next calendar is built on one piece, not on four.",
    )
    _add(
        pages,
        "market_analyst",
        "نختم الملاحظة بقائمة قصيرة: قرار يمكن اتخاذه هذا الأسبوع من غير رقم ناقص، وقرار يجب أن ينتظر. الخلط بينهما هو أكثر ما يضر صاحب النشاط. القرار الممكن مثاله تعديل جملة في العرض. القرار المؤجل مثاله فتح مدينة من غير تكلفة. لا نضع الاثنين في توصية واحدة حتى يبدو التقرير حاسمًا. الحسم الكاذب أغلى من الانتظار المكتوب.",
        "We close the note with a short list: a decision that can be taken this week without a missing figure, and a decision that must wait. Mixing the two is what hurts the owner most. A possible decision is, for example, editing one sentence in the offer. A postponed decision is opening a city with no cost figure. We do not put both in one recommendation so the note looks decisive. A false decision costs more than a written wait.",
    )
    _add(
        pages,
        "competitor_analyst",
        "بعد الجدول نكتب ماذا لن نفعله: لن نتابع المنافس يوميًا، ولن ننقل عباراته إلى صفحتكم، ولن نحدّث المقارنة وحدنا. التحديث يكون حين يلصق صاحب النشاط صفحة جديدة. مقارنة قديمة تُؤرخ حتى لا تُستخدم بعد تغيّر السعر الظاهر. إن بقيت المقارنة من غير تاريخ، تصبح انطباعًا قديمًا يرتدي شكل تقرير.",
        "After the table we write what we will not do: we will not watch the competitor daily, we will not copy their sentences onto your page, and we will not refresh the comparison on our own. An update happens when the owner pastes a new page. An old comparison is dated so it is not used after the visible price changes. A comparison with no date becomes an old impression wearing the shape of a report.",
    )
    _add(
        pages,
        "business_ideas",
        "بعد اختيار فكرة واحدة نكتب ماذا يُجرَّب في سبعة أيام وبأي مبلغ من المبلغ الذي سُمّي، وما الذي يعني أن التجربة تتوقف. التوقف ليس فشل الشخص. هو حماية للمبلغ. إن نجحت الخطوة الأولى بمعنى أن شخصًا دفع أو حجز بحسب ما عُرّف، تُكتب الخطوة الثانية منفصلة. لا نقفز إلى توظيف أو إلى محل قبل أن تُغلق الخطوة الأولى كتابةً.",
        "After one idea is chosen we write what is tried in seven days, with how much of the named amount, and what it means for the trial to stop. Stopping is not a personal failure. It protects the amount. If the first step succeeds in the sense that someone paid or booked as defined, the second step is written separately. We do not jump to hiring or to a shop before the first step is closed in writing.",
    )
    _add(
        pages,
        "project_manager",
        "كل يوم جمعة، أو في اليوم الذي يختاره صاحب النشاط، تُراجع الخطة بسطرين: ما اكتمل، وما انتقل. النقل يغيّر الموعد ويُبقي الناتج كما هو إلا إذا تغيّر النطاق بموافقة. لا نضيف خطوة في المراجعة الأسبوعية بحجة أنها صغيرة. الخطوة الصغيرة التي تدخل من غير ناتج هي التي تجعل الخطة لا تنتهي. المراجعة تُغلق القائمة، لا تفتحها.",
        "Each Friday, or on the day the owner chooses, the plan is reviewed in two lines: what finished, and what moved. A move changes the date and keeps the output the same unless the scope changed with approval. We do not add a step in the weekly review because it looks small. A small step that enters with no output is what makes a plan endless. The review closes the list. It does not open it.",
    )
    _add(
        pages,
        "time_manager",
        "في نهاية الأسبوع نعدّ المهام التي كُتبت ولم تُلمس، لا الساعات التي شعر بها الشخص. المهمة التي لم تُلمس إما تقديرها خاطئ أو ليست مهمة هذا الأسبوع. نخرجها من الأسبوع التالي صراحة. الإبقاء عليها بدافع الذنب يملأ الخطة ويمنع العمل العميق. النوم والموعد الخارجي الثابت لا يُقصان ليظهر إنجاز على الورق.",
        "At the end of the week we count the tasks that were written and never touched, not the hours the person felt. A task that was not touched was either badly estimated or does not belong to this week. We take it out of the next week in writing. Keeping it out of guilt fills the plan and blocks deep work. Sleep and a fixed outside appointment are not cut so that a paper achievement can appear.",
    )
    _add(
        pages,
        "data_analyst",
        "نسلّم مع الرقم جملة بما لا يثبته الرقم. عدد الطلبات المكتملة لا يثبت رضا، ولا يثبت ربحًا، ولا يثبت أن مدينة أخرى ستشبه هذه المدينة. هذه الجملة تمنع أن يُقتبس الرقم في إعلان. إن أراد صاحب النشاط نشر الرقم، يراجعه خبير البحث أو كاتب المحتوى على أنه وصف لفترة محددة، لا على أنه وعد. الفترة تُذكر بجانبه دائمًا.",
        "With the figure we deliver a sentence on what the figure does not prove. A count of completed orders does not prove satisfaction, does not prove profit, and does not prove that another city will look like this one. That sentence stops the figure from being quoted in an ad. If the owner wants to publish it, the SEO expert or the content writer treats it as a description of a named period, not as a promise. The period is always written beside it.",
    )
    _add(
        pages,
        "cv_writer",
        "قبل إرسال السيرة نطلب من صاحبها أن يطابق كل سطر مع ما يستطيع شرحه في مقابلة من غير ورقة. السطر الذي لا يستطيع شرحه يُحذف أو يُبسَّط. لا نترك عبارة لأن شكلها أقوى. الجهة التي سيُرسل إليها الاسم تُراجع إملائيًا كما كتبها هو. وإن كانت السيرة بالعربية والإنجليزية معًا، فالأرقام والتواريخ تتطابق بين النسختين ولا تُترجم الخبرة إلى دور لم يعمله.",
        "Before the CV is sent we ask the person to match every line with something they can explain in an interview without notes. A line they cannot explain is removed or simplified. We do not keep a phrase because it sounds stronger. The name of the organisation it will be sent to is checked against the spelling they gave. If the CV exists in Arabic and English, the figures and dates match across both, and a job is not translated into a role they did not do.",
    )
    _add(
        pages,
        "software_engineer",
        "بعد الإصلاح نكتب ماذا سيراه صاحب النشاط إن نجح الاختبار وماذا سيراه إن فشل. الرؤية هنا رسالة أو سلوك، لا مصطلح داخلي. إن فشل الاختبار لا نكمل إلى ميزة جديدة في الجلسة نفسها. العطل المفتوح أولًا. وإن احتاج الإصلاح إيقاف الصفحة لدقائق، يُذكر ذلك قبل التنفيذ حتى يختار صاحب النشاط الوقت، لا حتى يُفاجأ والعملاء على الصفحة.",
        "After a repair we write what the owner will see if the test passes and what they will see if it fails. What they see is a message or a behaviour, not an internal term. If the test fails we do not continue to a new feature in the same session. The open fault comes first. If the repair needs the page to be down for minutes, that is said before the work, so the owner chooses the time instead of being surprised while customers are on the page.",
    )
    _add(
        pages,
        "orchestrator",
        "إذا عاد وكيل بمخرج يناقض وكيلًا آخر، نوقف التسليم ونعرض التعارض بجملتين لصاحب النشاط: ماذا قال الأول، وماذا قال الثاني، وأي قيد يحسم. لا نختار الجملة الأقوى. الحسم إما سياسة مكتوبة أو رقم من صاحب النشاط. من غير ذلك يبقى التعارض مفتوحًا ولا يُدمج في نص واحد يُرسل للعميل.",
        "If one agent returns a deliverable that contradicts another, we stop delivery and show the clash to the owner in two sentences: what the first said, what the second said, and which constraint decides. We do not pick the stronger sentence. The decision is either a written policy or a figure from the owner. Without that, the clash stays open and is not merged into one text sent to a customer.",
    )
    _add(
        pages,
        "policy_guardian",
        "نحتفظ بسجل قصير للبنود التي أُوقفت هذا الشهر، من غير أسماء عملاء. السجل يساعد صاحب النشاط أن يرى إن كانت السياسة نفسها ناقصة. إن تكرر الإيقاف للسبب نفسه ثلاث مرات، نوصي بجملة تُضاف إلى السياسة بدل إيقاف كل طلب على حدة. كتابة الجملة قراره. الحارس لا يعدّل السياسة من تلقاء نفسه.",
        "We keep a short log of the items stopped this month, with no customer names. The log helps the owner see whether the policy itself is incomplete. If the same reason stops a request three times, we suggest one sentence to add to the policy instead of stopping every request one by one. Writing that sentence is the owner's decision. The guardian does not edit the policy on its own.",
    )
    _add(
        pages,
        "quality_gate",
        "الملاحظة تُصاغ بحيث يستطيع الوكيل أن يصلحها من غير اجتماع. إن احتاجت اجتماعًا، فهي ليست ملاحظة جودة بل قرارًا ناقصًا، فنعيدها إلى الرئيس التنفيذي الافتراضي ليسمي من يحسم. لا نراكم ملاحظات أسلوب مع ملاحظات نقص حقيقة في قائمة واحدة من غير تمييز. الحقيقة أولًا. الأسلوب بعده. القائمة المختلطة تُصلح الزينة وتترك الرقم الخطأ.",
        "A note is written so the agent can repair it without a meeting. If it needs a meeting, it is not a quality note but a missing decision, and we send it back to the virtual chief executive to name who decides. We do not pile style notes and missing-fact notes into one list without a mark. The fact comes first. Style comes after. A mixed list fixes the decoration and leaves the wrong figure.",
    )
    _add(
        pages,
        "prototype_engineer",
        "نسلّم مع الرسم سؤالين مفتوحين على الأكثر، لا عشرة. السؤال المفتوح الذي لا يمنع المهمة الأولى يُؤجل إلى نسخة لاحقة ويُكتب مؤجلًا. السؤال الذي يمنع المهمة يوقف الرسم حتى يُجاب. بهذا لا يصبح النموذج وثيقة قلق. صاحب الفكرة يعرف ماذا يبني أولًا وماذا ينتظر. مهندس البرمجيات لا يبدأ من سؤال مؤجل.",
        "With the sketch we deliver two open questions at most, not ten. An open question that does not block the first task is postponed to a later version and written as postponed. A question that blocks the task stops the sketch until it is answered. The prototype does not become a document of worry. The owner knows what to build first and what waits. The software engineer does not start from a postponed question.",
    )
    _add(
        pages,
        "product_designer",
        "نذكر حالة الخطأ وحالة النجاح لا الشاشة السعيدة فقط. الخطأ يقول ماذا حدث وماذا يفعل المستخدم من غير لوم. النجاح يقول ماذا بعد الفعل الأساسي. إن غابت الحالتان، فالصفحة جميلة وغير مكتملة. نراجع أيضًا أن النص العربي لا ينكسر في الزر الضيق. إن انكسر، نختصر العبارة مع صاحب النص لا نضغط الحروف.",
        "We describe the error state and the success state, not only the happy screen. The error says what happened and what the user does, without blame. Success says what comes after the main action. If both states are missing, the page is attractive and unfinished. We also check that Arabic text does not break inside a narrow button. If it breaks, we shorten the phrase with the writer. We do not crush the letters.",
    )
    _add(
        pages,
        "qa_engineer",
        "نرتب الحالات بحيث تُجرَّب الحافة قبل أن يُقضى الوقت في تجميل المسار السعيد. إن فشلت الحافة، لا معنى لتلميع الرسائل. نسلّم قائمة يمكن طباعتها: رقم الحالة، الخطوة، النتيجة. بعد التنفيذ يكتب صاحب النشاط بجانب كل حالة: تمت، أو لم تتم، أو تُركت. الخانة الفارغة لا تُعد نجاحًا. الصمت ليس اجتيازًا.",
        "We order the cases so the edge is tried before time is spent polishing the happy path. If the edge fails, there is no point polishing the messages. We deliver a list that can be printed: case number, step, result. After the run, the owner writes beside each case: done, not done, or left. An empty box is not a pass. Silence is not a pass.",
    )
    _add(
        pages,
        "integrations_engineer",
        "نكتب من يلاحظ الفشل خلال ساعة العمل ومن يلاحظه خارجها، حتى لا يبقى الحدث الفاشل حتى الصباح من غير أن يُسمّى أحد. إن لم يوجد شخص، نوقف الوصف ونطلب اسمًا. الربط الذي لا مالك له يفشل بصمت. ونكتب ماذا يُحفظ من الحدث: معرف فقط، لا نص رسالة العميل إن لم يكن لازمًا للإجراء.",
        "We write who notices a failure during working hours and who notices it outside them, so a failed event does not sit until morning with nobody named. If there is no person, we stop the description and ask for a name. A connection with no owner fails silently. We also write what is kept from the event: an identifier only, not the text of a customer message, unless that text is required for the action.",
    )
    _add(
        pages,
        "sales_closer",
        "إن لم يرد العميل، لا نكتب رسالة ثالثة أشد لهجة. الرسالة الثانية، إن طُلبت، تكتفي بتذكير بالمعلومة الناقصة وتترك الباب من غير عتاب. العتاب يحوّل التردد إلى رفض. وإن أغلق العميل الحديث، تتوقف المسودات. الإصرار بعد الإغلاق ليس إقناعًا. هو إزعاج، ولا يُصاغ هنا.",
        "If the customer does not reply, we do not write a third and harsher message. A second message, if requested, only reminds them of the missing fact and leaves the door open without reproach. Reproach turns hesitation into a refusal. If the customer closes the conversation, the drafts stop. Persistence after a close is not persuasion. It is a nuisance, and it is not drafted here.",
    )
    _add(
        pages,
        "search_discovery",
        "بعد تعديل العنوان نطلب من صاحب النشاط أن يفتح الصفحة كما يراها الزائر ويتأكد أن الوعد في العنوان ما زال في أول الشاشة. إن اختفى الوعد تحت صورة أو قائمة، فالعنوان الجديد كاذب رغم أنه أقصر. لا نعدّل العنوان ثم ننسى المتن. وإن وُجدت نسخة إنجليزية، نراجع أن عنوانها لا يعد بمدينة أو بخدمة لا توجد في تلك النسخة.",
        "After the title is changed we ask the owner to open the page as a visitor and check that the promise in the title is still on the first screen. If the promise has disappeared under an image or a list, the new title is false even though it is shorter. We do not change the title and forget the body. If an English version exists, we check that its title does not promise a city or a service that is not in that version.",
    )
    _add(
        pages,
        "security_compliance",
        "نحدد موعدًا واحدًا لإعادة النظر في الملاحظات الثلاث، لا جدول امتثال ثقيلًا. في الموعد نسأل: هل فُصلت الصلاحية، وهل زالت كلمة المرور من المحادثة، وهل عُرف من يُبلَّغ. الإجابة نعم أو لا. التفسير الطويل لا يغني عن لا. إن بقيت لا، تبقى الملاحظة مفتوحة ولا نكتب أن الوضع تحسّن.",
        "We set one date to look again at the three notes, not a heavy compliance calendar. On that date we ask: was permission separated, was the password removed from the chat, and is the person to notify known. The answer is yes or no. A long explanation does not replace a no. If a no remains, the note stays open and we do not write that the situation improved.",
    )
    _add(
        pages,
        "legal_privacy",
        "نضع في أسفل المسودة أسئلة المحامي كما هي، لا نجيب عنها نيابة عنه. السؤال الذي لا يعرف صاحب النشاط جوابه يبقى سؤالًا. من أمثلته: أين يُحفظ النسخ الاحتياطي، ومن موظف يرى رقم الجوال، وماذا يحدث عند طلب الحذف. الإجابة المختلقة في السياسة تُلزم النشاط بشيء لا يفعله. الفراغ أصدق إلى أن يأتي الجواب.",
        "At the bottom of the draft we place the lawyer's questions as questions. We do not answer them on the lawyer's behalf. A question the owner cannot answer stays a question. Examples are: where the backup is kept, which staff member sees the mobile number, and what happens when deletion is requested. An invented answer in a policy binds the business to something it does not do. A gap is more truthful until the answer arrives.",
    )
    _add(
        pages,
        "finance_pricing",
        "إن تغيّر رقم واحد بعد التسليم، لا نصحح النتيجة في الرأس. نعيد الخطوة التي دخلها الرقم ونترك الباقي كما هو حتى يظهر أثر التغيير وحده. هكذا يرى صاحب النشاط إن كان الهامش حسّاسًا لهذا البند. لا نعيد كتابة الخلاصة لتبقى متفائلة. الخلاصة تتبع الحساب. وإن كان الرقم الجديد تقديرًا لا فاتورة، نعلّمه تقديرًا في الخطوة نفسها.",
        "If one figure changes after delivery, we do not correct the result in our heads. We rerun the step that figure enters and leave the rest as it was, so the effect of the change is visible on its own. The owner can then see whether the margin is sensitive to that item. We do not rewrite the conclusion so it stays cheerful. The conclusion follows the arithmetic. If the new figure is an estimate rather than an invoice, we mark it as an estimate in that same step.",
    )
    _add(
        pages,
        "localization",
        "نراجع النسخة الجديدة على ثلاثة أسطر يختارها صاحب النص لأنها الأهم عنده: السعر، والشرط، والفعل المطلوب من القارئ. إن تغيّر أحدها من غير قصد أثناء التعريب، نرجعه ونذكر ذلك. باقي النص يمكن أن يختلف في ترتيب الجملة. هذه الأسطر الثلاثة لا تختلف في المضمون. بهذا لا يصبح التعريب فرصة تضيع فيها مدة أو مبلغ.",
        "We check the new version against three lines the owner chooses because they matter most: the price, the condition, and the action asked of the reader. If one of them changed by accident during localization, we restore it and say so. The rest of the text may differ in sentence order. Those three lines do not differ in substance. Localization does not become a chance to lose a duration or an amount.",
    )
    _add(
        pages,
        "lead_acquisition",
        "في نهاية الأسبوع نعدّ المسودات التي أُرسلت فعلًا والتي بقيت في الدرج، من غير نسبة تحويل مختلقة. المسودة التي بقيت قد تكون لأن العرض تغيّر أو لأن صاحب النشاط لم يطمئن للجملة. نسأل أيهما. لا نزيد عدد الرسائل لتعويض الصمت. وإن تغيّر السعر المعتمد، تُسحب المسودات القديمة ولا تُرسل وفيها السعر السابق.",
        "At the end of the week we count the drafts that were actually sent and the drafts that stayed in the drawer, with no invented conversion rate. A draft that stayed may be there because the offer changed or because the owner did not trust the sentence. We ask which. We do not raise the number of messages to make up for silence. If the approved price changes, old drafts are withdrawn and are not sent with the previous price.",
    )
    _add(
        pages,
        "financial_forecast",
        "نسلّم مع السيناريوهات سطرًا بما يُبطلها: إن تغيّر التسرب فوق ما كُتب، أو تأخر تحصيل لم يُذكر في التكلفة، فالشهر المحسوب لا يُقتبس. هذا السطر يُلصق بجانب أي استخدام لاحق للشهر حتى لا يدخل في إعلان أو في حديث مع شريك كأنه موعد مؤكد. التقدير أداة قرار لصاحب النشاط، لا تاريخًا يُعلن.",
        "With the scenarios we deliver a line on what cancels them: if churn moves above what was written, or a collection delay was never in the cost, the calculated month is not quoted. That line stays beside any later use of the month, so it does not enter an ad or a conversation with a partner as if it were a confirmed date. The estimate is a decision tool for the owner, not a date to announce.",
    )
    _add(
        pages,
        "arabic_ocr",
        "بعد الاستخراج نسأل صاحب النشاط أن يطابق ثلاثة حقول بعينه على الورقة: المورّد، والتاريخ، والإجمالي. إن خالف أحدها الورقة، فالحقل يُصحح بيده لا بتخمين ثانٍ من الصورة. باقي الحقول الضعيفة تبقى معلّمة حتى تُراجع. لا نعتمد الملف لأن معظمه بدا صحيحًا. الحقل المالي الواحد يكفي ليخطئ القيد. لذلك المطابقة شرط قبل أن يذهب الجدول إلى المحاسب.",
        "After extraction we ask the owner to match three fields against the paper with their own eyes: the vendor, the date, and the total. If one of them disagrees with the paper, the owner corrects it. We do not take a second guess from the image. The other low-confidence fields stay marked until they are reviewed. We do not accept the file because most of it looked right. One financial field is enough to make the entry wrong. Matching is a condition before the table goes to an accountant.",
    )
    _add(
        pages,
        "style_memory",
        "كل ربع سنة، أو حين تتغير العلامة، نعرض الملف في صفحة واحدة ليعلم صاحب النشاط ماذا سيُحقن في الوكلاء. الحذف يتم على هذه الصفحة لا داخل مسودة قديمة. إن تراكمت قواعد متناقضة، نوقف الحقن ونطلب أي القاعدتين تبقى. الحقن بقاعدتين متعارضتين يجعل كل وكيل يختار واحدة بصمت. الاختيار الصامت هو ما يفسد اتساق العلامة.",
        "Every quarter, or when the brand changes, we show the profile on one page so the owner can see what will be injected into the agents. Deletion happens on that page, not inside an old draft. If contradictory rules have piled up, we stop the injection and ask which rule remains. Injecting two contradictory rules lets each agent pick one in silence. That silent choice is what breaks the brand's consistency.",
    )
    _add(
        pages,
        "evaluation_loop",
        "الدرجات تُحفظ مع المخرج لا في لوحة عامة تقارن العملاء. لا متوسط بين عميلين، ولا ترتيب. الدرجة تخص هذا النص وهذه الجولة. عند تسليم النص نذكر الجولة التي توقفنا عندها والبند الذي بقي مفتوحًا في السطر الأول، حتى لا يُقرأ النص كأنه اكتمل. السطر الأول داخلي يمكن لصاحب النشاط حذفه قبل الإرسال، بعد أن يراه.",
        "Scores are kept with the deliverable, not on a public board that compares customers. There is no average between two customers, and no ranking. The score belongs to this text and this round. When the text is delivered we state, on the first line, the round we stopped at and the item that stayed open, so the text is not read as finished. That first line is internal. The owner can delete it before sending, after they have seen it.",
    )
    # A second pass for pages that were still short. Each note is specific to the role.
    _add(pages, "email_writer",
         "نختم المسودة بسطر داخلي: هل في الرسالة طلب واحد فقط. إن وجدنا طلبين، نفصل الرسالة. المستقبل الذي يُسأل عن موعد وعن ملف وعن رأي في الجملة نفسها يؤجل الرد. الفصل هنا ليس إطالة، بل رسالة ثانية بعنوانها حين يُطلب ذلك.",
         "We close the draft with an internal line: does the message ask for one thing only. If we find two requests, we split it. A reader asked for a date, a file, and an opinion in the same sentence postpones the reply. Splitting is not making the mail longer. It is a second message with its own subject, when that is requested.")
    _add(pages, "content_manager",
         "لا ننقل خانة من أسبوع مزدحم إلى أسبوع خالٍ من غير أن نسأل هل المادة ما زالت صحيحة. الخانة المنقولة تحمل تاريخها القديم في ملاحظة حتى لا تُنشر كأنها كُتبت للأسبوع الجديد. النقل من غير هذه الملاحظة هو كيف يعود عرض منتهٍ.",
         "We do not move a slot from a crowded week to an empty week without asking whether the material is still true. A moved slot keeps its old date in a note, so it is not published as if it had been written for the new week. A move without that note is how an expired offer returns.")
    _add(pages, "competitor_analyst",
         "إن لم يستطع صاحب النشاط لصق الصفحة، لا نصف المنافس من الذاكرة. نؤجل الصف حتى تصل الصفحة أو يُكتب أن المقارنة أُلغيت. الوصف من الذاكرة يخلط ما رآه الشهر الماضي بما يظنه اليوم.",
         "If the owner cannot paste the page, we do not describe the competitor from memory. We postpone the row until the page arrives, or we write that the comparison was cancelled. A description from memory mixes what they saw last month with what they think today.")
    _add(pages, "project_manager",
         "الناتج الذي لا يمكن لأحد أن يفتحه أو يقرأه لا يُحتسب مكتملًا حتى لو قال المنفذ إنه انتهى. نطلب رابطًا أو ملفًا أو جملة ظاهرة. من غير ذلك تبقى الخطوة مفتوحة. هذا يمنع أن تُقفل الخطة على كلام.",
         "An output nobody can open or read does not count as finished even if the person doing it says it is done. We ask for a link, a file, or a visible sentence. Without that, the step stays open. This stops a plan from being closed on talk.")
    _add(pages, "time_manager",
         "المهمة الثابتة التي تتكرر كل أسبوع تُكتب مرة وتُراجع مدتها بعد أسبوعين، لا كل صباح. إن كانت المدة الحقيقية ضعف التقدير، نصلح التقدير. لا نطلب من الشخص أن يسرع ليطابق رقمًا كتبناه في أول يوم.",
         "A task that repeats every week is written once, and its duration is reviewed after two weeks, not every morning. If the real duration is double the estimate, we fix the estimate. We do not ask the person to hurry so they match a number written on the first day.")
    _add(pages, "data_analyst",
         "إذا كان السؤال يحتاج عمودًا غير موجود، نتوقف ونسمّي العمود. لا نستنتجه من عمود قريب. الاستنتاج من عمود قريب هو كيف يتحول عدد الطلبات إلى ربح من غير تكلفة. نرفض هذا الطريق كتابةً في الملاحظة نفسها.",
         "If the question needs a column that is not there, we stop and name the column. We do not infer it from a nearby column. Inferring from a nearby column is how an order count becomes profit without a cost. We refuse that path in writing.")
    _add(pages, "cv_writer",
         "الخبرة التطوعية تُذكر فقط إذا أراد صاحب السيرة ذلك، وتُوسم تطوعًا حتى لا تُقرأ كوظيفة. لا نضخمها إلى إدارة. الوصف يبقى على ما فعله فعلًا في ذلك العمل.",
         "Volunteer work is included only if the person wants it, and it is labelled as volunteer work so it is not read as a job. We do not inflate it into management. The description stays on what they actually did there.")
    _add(pages, "software_engineer",
         "نذكر ما لن يتغير في هذا الطلب: صفحة، أو تقرير، أو حساب. إن لمس الإصلاح شيئًا من هذه القائمة، نتوقف قبل المتابعة. الحد المكتوب يحمي صاحب النشاط من إصلاح يتسع حتى يصبح مشروعًا آخر.",
         "We state what will not change in this request: a page, a report, or a calculation. If the repair touches something on that list, we stop before continuing. The written limit protects the owner from a fix that grows until it is another project.")
    _add(pages, "orchestrator",
         "في نهاية الترتيب نكتب من لا نحتاج إليه هذا الأسبوع ولماذا. الاستبعاد المكتوب يمنع أن يُستدعى وكيل لاحقًا بحجة أنه موجود في المنصة. الوجود في المنصة ليس مهمة.",
         "At the end of the order we write who is not needed this week and why. A written exclusion stops an agent from being called later just because they exist on the platform. Existing on the platform is not a task.")
    _add(pages, "policy_guardian",
         "البنود التي مرت من غير إيقاف تُذكر في سطر حتى لا يُظن أن الحارس لم يقرأها. المرور قرار مثل الإيقاف. الصمت عن البنود السليمة يجعل صاحب النشاط يشك في الفحص كله.",
         "Items that passed without a stop are named in one line, so nobody thinks the guardian did not read them. A pass is a decision, like a stop. Silence about the sound items makes the owner doubt the whole check.")
    _add(pages, "quality_gate",
         "لا نستخدم كلمة ممتاز ولا كلمة جاهز من غير فعل. نستخدم يمر أو يعود أو يتوقف. الكلمة المطلقة تخفي الملاحظة التي ما زالت مفتوحة. صاحب النشاط يحتاج الفعل لا المدح.",
         "We do not use the word excellent. We use pass, return, or stop. An absolute word hides the note that is still open. The owner needs the action, not the praise.")
    _add(pages, "prototype_engineer",
         "نكتب اسم المهمة الأولى في عنوان الرسم ونكرره تحت كل شاشة تخدمها. الشاشة التي لا تكرر المهمة تُحذف من النسخة الأولى. هذا الاختبار البسيط يمنع أن يكبر الرسم لأن شاشة بدت جميلة على الورق.",
         "We write the name of the first task in the title of the sketch and repeat it under every screen that serves it. A screen that does not repeat the task is removed from this version. That simple test stops the sketch from growing because a screen looked attractive.")
    _add(pages, "product_designer",
         "نراجع الترتيب على شاشة ضيقة قبل الشاشة العريضة. إن سقط الفعل الأساسي تحت الطي، نرفعه. زائر الجوال هو من يكمل الحجز غالبًا. تصميم يُرى كاملًا على شاشة كبيرة فقط لا يُعتمد.",
         "We review the order on a narrow screen before a wide one. If the main action falls below the fold, we move it up. The person on a phone is often the one who finishes a booking. A design that is only whole on a large screen is not accepted.")
    _add(pages, "qa_engineer",
         "الحالة التي تعتمد على بيانات تجريبية تذكر من أين جاءت البيانات. بيانات من غير مصدر لا تُعاد لأنها قد تكون حقيقية نُسيت. إن لم يعرف صاحب النشاط مصدرها، تُستبعد الحالة حتى تُستبدل ببيانات يعرف أصلها.",
         "A case that depends on trial data says where the data came from. Data with no source is not reused, because it may be real data that was forgotten. If the owner does not know the source, the case is set aside until it is replaced.")
    _add(pages, "integrations_engineer",
         "نصف ماذا يرى صاحب النشاط في سجل بسيط: نجح، أو تكرر فمنع، أو فشل ونُبّه فلان. من غير هذه الحالات الثلاث يبقى الربط قصة. السجل جملة لا لوحة. هو يكفي ليعرف إن كان الحدث الحي يطابق الوصف.",
         "We describe what the owner sees in a simple log: it succeeded, it repeated and was blocked, or it failed and a named person was told. Without those three states the connection is a story. The log is a sentence, not a dashboard. It is enough to know whether a live event matches the description.")
    _add(pages, "sales_closer",
         "نكتب في المسودة السعر كما اعتمده صاحب النشاط في سطر مستقل حتى لا يختبئ داخل جملة طويلة. إن اختلف هذا السطر عن صفحة المنتج، نتوقف ولا نرسل. الرسالتان لا تحملان سعرين. التصحيح يتم قبل الإرسال لا بعده.",
         "In the draft we write the price the owner approved on its own line, so it does not hide inside a long sentence. If that line disagrees with the product page, we stop. The two messages must not carry two prices. The correction happens before sending, not after.")
    _add(pages, "search_discovery",
         "لا نقترح صفحة جديدة إن كانت الصفحة الحالية تستطيع أن تجيب بعد تعديل عنوانها ومتنها. الصفحة الزائدة تشتت الزائر وتترك عنوانين يعدان بالشيء نفسه. الصفحة الجديدة تُقترح فقط حين يكون السؤال مختلفًا فعلًا.",
         "We do not suggest a new page if the current page can answer after its title and body are edited. An extra page scatters the visitor and leaves two titles promising the same thing. A new page is suggested only when the question is actually different.")
    _add(pages, "security_compliance",
         "الملاحظة التي تخص جهازًا مفقودًا تسمي الجهاز كما وصفه صاحبه، لا كل الأجهزة. التعميم يضيع الإجراء. وإن كان الجهاز ما زال معه، نكتب ذلك حتى لا تُغلق الجلسات كلها من غير داع.",
         "A note about a lost device names the device as the owner described it, not every device. A generalisation loses the action. If the device is still with them, we write that, so not every session is closed without need.")
    _add(pages, "legal_privacy",
         "نفرّق في المسودة بين ما تفعله المنشأة اليوم وما تنوي فعله لاحقًا. النية لا تُكتب كأنها ممارسة قائمة. حين تبدأ الممارسة، تُحدَّث المسودة. السياسة التي تسبق الواقع تُلزم النشاط أمام عميله بشيء لم يبدأ.",
         "In the draft we separate what the business does today from what it intends to do later. An intention is not written as a current practice. When the practice starts, the draft is updated. A policy that runs ahead of reality binds the business, in front of its customer, to something that has not started.")
    _add(pages, "finance_pricing",
         "إن وُجد خصم معتمد، نحسب السعر بعد الخصم في سطر ثانٍ ولا نحذف السعر الأصلي. السطران معًا يمنعان أن يُعرض الهامش على سعر لا يدفعه العميل. الخصم غير المعتمد لا يدخل الحساب حتى لو ذُكر كفكرة.",
         "If an approved discount exists, we calculate the price after the discount on a second line and we do not delete the original price. The two lines together stop the margin from being shown on a price the customer does not pay. An unapproved discount does not enter the calculation even if it was mentioned as an idea.")
    _add(pages, "localization",
         "المصطلح الذي اختاره صاحب النص يُثبت في سطر أعلى المسودة. أي مرادف يظهر لاحقًا يُعاد إلى هذا المصطلح. الصفحة التي تقول الحجز ثم الموعد ثم الحجز مرة أخرى تُتعب القارئ. الثبات هنا جزء من التعريب لا تفصيلًا شكليًا.",
         "The term the owner chose is fixed on a line above the draft. Any synonym that appears later is brought back to that term. A page that says booking, then appointment, then booking again tires the reader. Consistency here is part of localization, not a cosmetic detail.")
    _add(pages, "lead_acquisition",
         "الفرصة التي تسأل عن شيء لا يبيعه النشاط تُؤشر بأنها خارج العرض ولا تُكتب لها رسالة إقناع. الرسالة في هذه الحالة توضح الحد بلطف وتقترح الجهة إن كانت معروفة، من غير إحالة مبهمة. الإقناع في غير العرض يضيّع وقت الطرفين.",
         "An enquiry that asks for something the business does not sell is marked as outside the offer, and no persuasion message is written for it. The message in that case states the limit plainly and names a place to go only if one is known, with no vague referral. Persuasion outside the offer wastes both sides' time.")
    _add(pages, "financial_forecast",
         "السيناريو المتفائل لا يُعرض وحده في أي ملخص. إن طُلب سطر واحد، نكتب الأساسي وبجانبه أن المحافظ والمتفائل موجودان في التفصيل. عرض المتفائل وحده هو كيف يتحول الفرض إلى وعد. نرفض هذا العرض حتى لو كان الرقم أجمل.",
         "The optimistic scenario is never shown alone in a summary. If one line is requested, we write the base and note that the conservative and optimistic cases are in the detail. Showing only the optimistic case is how an assumption becomes a promise. We refuse that presentation even if the figure looks better.")
    _add(pages, "arabic_ocr",
         "نذكر عدد الصفحات التي قُرئت وعدد الصفحات التي تُركت لأن الصورة داكنة أو مقطوعة. الصفحة المتروكة لا تُخمن. صاحب النشاط يعيد تصويرها أو يقبل أن الحقول فيها غير مستخرجة. الإجمال من الصفحات المقروءة فقط يُكتب صراحة في صدر الجدول حتى لا يُظن أنه إجمالي الفاتورة كلها، ولا يُجمع عند التسليم مع أي صفحة لم تُقرأ في هذا الملف.",
         "We state how many pages were read and how many were left because the image was dark or cut off. A left page is not guessed. The owner photographs it again or accepts that its fields were not extracted. A total taken only from the pages that were read is labelled as such, so it is not mistaken for the total of the whole invoice.")
    _add(pages, "style_memory",
         "التوقيع يُراجع منفصلًا عن النبرة. قد تكون النبرة خفيفة والتوقيع رسميًا باسم النشاط. خلطهما يجعل الرد القصير ينتهي بفقرة قانونية أو يجعل الصفحة الرسمية تنتهي بدعابة. السطران في الملف يمنعان هذا الخلط عند كل وكيل.",
         "The signature is reviewed apart from the tone. The tone may be light while the signature stays formal in the business name. Mixing them makes a short reply end in a legal paragraph, or a formal page end in a joke. The two lines in the profile stop that mix for every agent.")
    _add(pages, "evaluation_loop",
         "لا نرفع درجة الاكتمال لأن النص طويل. الطول قد يخفي خانة لم تُستبدل. نبحث عن القوس الفارغ وعن عبارة تُستكمل لاحقًا قبل أن نمنح الدرجة. إن وُجدت، تبقى الدرجة منخفضة مهما بدا النص مرتبًا.",
         "We do not raise the completeness score because the text is long. Length can hide a slot that was never replaced. We look for an empty bracket and for a phrase that says it will be completed later before we give the score. If one is found, the score stays low however tidy the text looks.")
