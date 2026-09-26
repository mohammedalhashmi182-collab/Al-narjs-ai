# -*- coding: utf-8 -*-
"""English bodies and FAQs for the blog articles.

``blog_articles_1.py`` holds the Arabic originals (the primary language). This module
holds the English counterparts, keyed by slug, and is merged onto the articles at
import time. English pages must never fall back to Arabic copy: a wrong-language body
hurts readers and it is a real defect for search engines.

Editorial rules are identical to the Arabic file: no invented statistics, market
sizes, client names, testimonials or results; no outcome promises; every illustration
is labelled as an example; prices are never hard-coded.
"""

EN: dict[str, dict] = {
    "ai-agents-for-saudi-businesses": {
        "body": [
            {
                "h": "Start with the conclusion",
                "p": [
                    "An AI agent is a digital employee that performs one defined job: it writes, answers, analyses, or organises. It does not request leave and it does not send a payroll.",
                    "A business does not need a full department to begin. It needs one measurable task and one agent whose output you can check. This guide explains the difference, when to start, and what it costs.",
                ],
            },
            {
                "h": "What an AI agent actually is",
                "p": [
                    "Not a passing conversation, but a process with a goal: it takes inputs, runs steps, and delivers an output you can use.",
                ],
                "ul": [
                    "A narrow speciality: content, customer care, e-commerce, or analysis.",
                    "Repeatable output you can compare week to week.",
                    "Works in Modern Standard Arabic, understands Saudi usage, and produces an English version on request.",
                    "It invents no numbers and inflates no results; output is reviewed before it goes out.",
                ],
            },
            {
                "h": "Employee versus agent",
                "p": [
                    "An employee needs management and salary. An agent needs one task defined and one expected output. The fair comparison is not person versus program, but a task that repeats weekly against a task that needs human judgement.",
                    "Suits an agent: content calendars, repeated replies, product descriptions, data analysis, request follow-up.",
                    "Does not suit an agent: final pricing, legal files, or any commitment made on your behalf before a human review.",
                ],
            },
            {
                "h": "Where to start: three steps",
                "p": ["Start with one task. Do not start with the phrase \"automate everything\"."],
                "ul": [
                    "Pick the task that repeats every week and eats an employee's time.",
                    "Write the one output you want in week one. Example: four posts, three stories, and a publishing schedule.",
                    "Measure time before and after. If the time did not drop or the output did not improve, do not expand.",
                ],
            },
            {
                "h": "Cost",
                "p": [
                    "A subscription is a monthly payment, not a salary, and it starts from the entry plan on the pricing page. Every subscription opens a team of five agents specialised for your field, billed on an official invoice with 15% VAT, with no long-term contract and cancellation at any time.",
                    "The fair question is not \"how cheap is it\" but: does this task slip every week? That is the real cost being removed.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Do agents replace employees?",
                "a": "They replace repetitive work, not people. Legal responsibility, pricing, and final sign-off stay with a human. That limit is written into every subscription.",
            },
            {
                "q": "Is the output original?",
                "a": "The agent produces drafts built from your data and your instructions, and they are reviewed before publishing. The output is a working tool; the decision is yours.",
            },
            {
                "q": "Which language does it work in?",
                "a": "Arabic first, in Modern Standard Arabic with Saudi usage for commercial contexts, and an English version in the same request when you need one.",
            },
        ],
    },
    "ai-customer-service-saudi": {
        "body": [
            {
                "h": "The problem is not speed",
                "p": [
                    "A Saudi customer will not accept a cold reply, and will not accept a reply that ignores their situation. They accept a reply that understands the case: a late order, a size change, or a payment question.",
                ],
            },
            {
                "h": "What a customer-care agent is good at",
                "p": [
                    "It answers repeated questions, writes in a professional register, and reduces the conversation to two lines before handing it to a human.",
                ],
                "ul": [
                    "Product questions: sizes, materials, instructions, availability.",
                    "Order questions: tracking, delivery date, shipping cost.",
                    "Returns: it collects the details, then transfers the case to a person.",
                    "Conversation summary: two lines that capture the case before transfer.",
                ],
            },
            {
                "h": "The limits",
                "p": [
                    "Financial refund decisions, unapproved discounts, and repeat complaints: these are limits automation does not cross. Every serious platform sets them before the sale, not after.",
                ],
            },
            {
                "h": "Protecting your voice",
                "p": [
                    "Send ten to twenty replies you wrote yourself, and a tone guide for your team is built from them. That is where the visible difference comes from after two weeks.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Will it reply in my language?",
                "a": "Yes, Arabic first, and it picks up your store's local vocabulary. Replies are reviewed and the register is calibrated against examples from your own conversations.",
            },
            {
                "q": "What happens on a payment or return problem?",
                "a": "The agent stops at that point, collects the details, and transfers to a human. It makes no financial decision and promises the customer no amount.",
            },
        ],
    },
    "ai-automation-for-saudi-stores": {
        "body": [
            {
                "h": "Start from the order, not the product",
                "p": [
                    "What costs a Saudi store the most is not publishing, it is the pile-up of orders, slow replies, and the same question repeating. Automation starts with repeated messages.",
                ],
            },
            {
                "h": "What runs today",
                "p": [
                    "Descriptions: turning specifications into sales copy in your audience's language. Replies: availability, size, shipping. Follow-up: after the order and after delivery.",
                ],
                "ul": [
                    "Product descriptions written from specifications, in the register that suits your audience.",
                    "Replies to the order questions you answer every day.",
                    "Post-purchase follow-up that cuts the \"where is my order\" messages.",
                    "A weekly report: what moved, and what did not.",
                ],
            },
            {
                "h": "Honest integration limits",
                "p": [
                    "Before the sale we state what can be connected, what needs extra access from you, and what cannot be connected from our side. Agents produce the output; connecting it to your system is a separate step that needs your permission.",
                ],
            },
            {
                "h": "What stays with you",
                "p": [
                    "Pricing, return policy, and the customer relationship. Automation removes repetition, not responsibility.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does it connect to my store directly?",
                "a": "Connection depends on your store system and your permissions. At the start we tell you what can be connected and what needs an extra step, with no general promises.",
            },
            {
                "q": "Does it change prices?",
                "a": "No. Pricing and refunds are two areas the agent does not touch without your approval on each case.",
            },
        ],
    },
    "ai-for-clinics-and-healthcare": {
        "body": [
            {
                "h": "The pain in a clinic is time",
                "p": [
                    "Not diagnosis, but hours: an unanswered call, a cancelled slot nobody filled, a patient who forgot. Automation here works on the hours, not on the medicine.",
                ],
            },
            {
                "h": "What can run",
                "p": [
                    "Answering appointment and published-price questions, confirming a booking, reminding before the visit, and following up afterwards.",
                ],
                "ul": [
                    "A clear confirmation message after booking.",
                    "A reminder one day before and two hours before, which reduces no-shows.",
                    "A post-visit follow-up with a single question about the experience.",
                ],
            },
            {
                "h": "The line we do not cross",
                "p": [
                    "Medical records, diagnosis, and prescriptions are outside any agent's scope. We do not request patient data and we do not store it. That limit is built into the product, not a marketing position.",
                ],
            },
            {
                "h": "Where to begin",
                "p": [
                    "With one task: appointment reminders. Request it from the pricing page and you can measure the effect within two weeks before adding anything else.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does it contact patients directly?",
                "a": "It works through your approved channel and your number, and it never starts a conversation with a patient without the clinic's knowledge.",
            },
            {
                "q": "Who pays the subscription?",
                "a": "The clinic pays. The reminder reaches the patient from the clinic's number, so the cost is yours, not the patient's.",
            },
        ],
    },
    "content-calendar-with-ai": {
        "body": [
            {
                "h": "A calendar is consistency, not creativity",
                "p": [
                    "Most teams do not publish consistently because production eats the time, not because ideas run out. Creativity is the easy part; consistency is what is missing.",
                ],
            },
            {
                "h": "The week cycle",
                "p": [
                    "A day for research and ideas, a day for the schedule, two days for writing, a day for review and approval, a day for capture, and a day to read the numbers.",
                ],
                "ul": [
                    "Ideas for the week: how-to, behind the scenes, opinion, comparison, and an answer to a real customer question.",
                    "Example weekly decision: stop the underperforming post and repeat the video that worked.",
                    "Publishing log: attach the link to each post so the team can read reach and replies at the end of the week.",
                ],
            },
            {
                "h": "Protecting the voice",
                "p": [
                    "Hand over ten posts you wrote yourself, and a tone reference for your team is built from them: preferred vocabulary, the sentences you never say, and the register you use.",
                ],
            },
            {
                "h": "Photos and video",
                "p": [
                    "Agents produce text, not footage. The right split: the text goes to the agent, and the capture goes to a camera or an image tool.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does the content look automated?",
                "a": "If you have not supplied a tone reference, yes. Supply ten posts, and week two looks different from week one.",
            },
            {
                "q": "How many posts a week?",
                "a": "Whatever you can keep up for twelve weeks. We start at three to four and raise it from there.",
            },
        ],
    },
    "ai-seo-for-arabic-businesses": {
        "body": [
            {
                "h": "Intent before keyword",
                "p": [
                    "Before any keyword: what does the searcher want? Information, a comparison, or a purchase. One page that mixes all three loses all three.",
                ],
            },
            {
                "h": "One page per intent",
                "p": [
                    "\"AI agents\", \"automate my store\", and \"AI for clinics\" are different intents and need different pages.",
                ],
                "ul": [
                    "Information intent: a direct explanation that answers a live question.",
                    "Comparison intent: a clear table with no exaggeration.",
                    "Buying intent: one page, one obvious next step.",
                ],
            },
            {
                "h": "Internal links",
                "p": [
                    "A page without internal links is an isolated page. Make every article point to two others: one that serves it, and one that sells.",
                ],
            },
            {
                "h": "The mistake that costs traffic",
                "p": [
                    "One long post covering ten topics ranks for none of them and serves no single reader intent. Ten topics means ten pages.",
                ],
            },
        ],
        "faq": [
            {
                "q": "When do results appear?",
                "a": "Indexing within days, ranking within four to eight weeks. Anyone promising you first place overnight is selling you something they do not have.",
            },
            {
                "q": "Is a blog enough on its own?",
                "a": "No. The strongest setup: a page per service, an article that serves information intent, and a clear link to buy.",
            },
        ],
    },
    "how-to-choose-ai-agents": {
        "body": [
            {
                "h": "Start from the task",
                "p": [
                    "If you cannot describe the output in one sentence, the task is not ready for an agent yet.",
                ],
            },
            {
                "h": "The seven questions",
                "p": [
                    "Read these before any subscription and write one line per answer. A seller who cannot answer clearly is selling you something they cannot describe.",
                ],
                "ul": [
                    "Which task do you repeat every week?",
                    "What output do you want in week one?",
                    "Who reviews it before it goes out?",
                    "What must the agent never do?",
                    "How do you measure success: less time or more output?",
                    "What happens if you dislike the output?",
                    "Is cancelling simple?",
                ],
            },
            {
                "h": "Warning signs",
                "p": [
                    "A promise of results instead of a description of outputs. Someone promising to double your sales is selling optimism, not a product.",
                ],
                "ul": [
                    "Output with no human review.",
                    "A promise to automate everything from month one.",
                    "Cancellation hidden behind an email address.",
                ],
            },
            {
                "h": "The question that settles it",
                "p": [
                    "Ask: what output will I see at the end of this week? If you do not get a specific answer, you are buying a promise, not a service.",
                ],
            },
        ],
        "faq": [
            {
                "q": "What if it does not work for me?",
                "a": "We tune the instructions with you for two weeks. If the output does not improve, cancel at any time with no process.",
            },
            {
                "q": "Should I start on a big plan?",
                "a": "No. Start with one task, measure it, then expand. Expanding before it is stable is a risk.",
            },
        ],
    },
    "ai-agents-vs-agency": {
        "body": [
            {
                "h": "They are not the same need",
                "p": [
                    "An agency delivers one defined project with an execution team. An agent subscription delivers a process that runs on daily tasks. Do not put them in the same budget line.",
                ],
            },
            {
                "h": "When agents win",
                "p": [
                    "When the task is repetitive and visible: daily content, replies, weekly analysis. Here speed and cost lead from day one.",
                ],
            },
            {
                "h": "When an agency wins",
                "p": [
                    "When the task is not repetitive and needs a full creative build: a launch campaign, a visual identity, or large-scale advertising.",
                ],
            },
            {
                "h": "The practical order",
                "p": [
                    "If most of your time goes to repetition, subscribe. If it goes to big decisions, use an execution partner. Most owners need both, in a clear order: repetition first, then decisions.",
                ],
                "ul": [
                    "Weekly replies, descriptions, and analysis: an agent subscription.",
                    "A product launch, a visual identity, or large ad spend: an execution partner with human review.",
                    "The final decision in either case: a person, always.",
                ],
            },
            {
                "h": "The conclusion",
                "p": [
                    "An agent is not measured by team size but by the time you got back. Start with a task that slips every week and measure the time immediately after.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does an agent replace a designer?",
                "a": "No. It replaces repetitive execution and frees your time for design and decisions.",
            },
            {
                "q": "Where do I actually start?",
                "a": "On the pricing page: pick the plan that matches how repetitive your work is, since every subscription opens a five-agent team for that field.",
            },
        ],
    },
    "ai-agents-for-saudi-hr-and-recruitment": {
        "body": [
            {
                "h": "Where HR time actually goes",
                "p": [
                    "In most companies, HR time goes into repeated administration: reading hundreds of files, writing a similar job description for every vacancy, and chasing documents and test dates.",
                    "These are tasks with defined inputs and checkable outputs. That is exactly what an AI agent is built for.",
                ],
            },
            {
                "h": "What can genuinely be automated",
                "ul": [
                    "Initial screening: it extracts skills and experience, ranks applicants by fit to the role, and leaves the final decision to a human.",
                    "Job description writing: one description and four ad variants in Arabic and English from the same requirements.",
                    "Correspondence follow-up: reminding the candidate about missing documents and updating the hiring team daily.",
                    "Interview summaries: turning interview notes into fixed points that are easy to compare between candidates.",
                ],
            },
            {
                "h": "The line that is not crossed",
                "p": [
                    "The agent does not decide a hire and does not exclude a candidate by name, nationality, or age. Automated screening is used to rank priority only, and the final assessment stays with a person.",
                    "Review any automated screening with an HR consultant, and align it with the Kingdom's personal data protection rules, before you apply it.",
                ],
            },
            {
                "h": "How to start without risk",
                "p": [
                    "Start with writing, not screening: have the agent write a job description and improve your correspondence. A task with no effect on any applicant, measurable in minutes.",
                    "Then move to initial screening on a single role and review the results manually for a full month before expanding.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Is automated screening against the labour law?",
                "a": "Not in itself, provided the final decision remains human and automated systems are reviewed against the personal data protection regulation. Screening must not be used to exclude applicants or to decide a hire.",
            },
            {
                "q": "What is the first task you recommend?",
                "a": "Writing the job description and the correspondence: a clear output, zero risk, and immediate measurement.",
            },
        ],
    },
    "ai-agents-for-saudi-restaurants-and-hospitality": {
        "body": [
            {
                "h": "Lost time in its right shape",
                "p": [
                    "A small restaurant manager works across five tracks: marketing, bookings, repeated questions, orders, and reviews. Four of them are repeated text that can be handed to an agent.",
                ],
            },
            {
                "h": "Deliberate uses",
                "ul": [
                    "A description for every dish on the menu in Arabic, plus an English version ready for social platforms.",
                    "Replies to repeated questions: opening hours, location, parking, and ingredients that can cause an allergy.",
                    "Booking follow-up: confirming the time, reminding before the visit, and releasing the slot automatically on cancellation.",
                    "Draft replies to reviews in a calm register, with no promise and no over-apology.",
                ],
            },
            {
                "h": "What you do not delegate",
                "p": [
                    "Orders with financial transactions, allergy or ingredient complaints, and supplier relationships: all of these stay with a trained employee. The agent prepares the information and writes the draft; sending and deciding stay with you.",
                ],
            },
            {
                "h": "A simple one-week measurement",
                "p": [
                    "Before starting: write down how many minutes messages and replies take you each day.",
                    "After a week: compare. The example: you have a consistent description for every dish on the menu and ready replies for repeated questions, without anything stopping.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does it work with delivery apps?",
                "a": "It prepares content and replies. Direct connection to delivery apps is done through official integrations, because unofficial access breaks the platforms' terms.",
            },
            {
                "q": "Which dialect does it reply in?",
                "a": "It writes public-facing text in simplified Modern Standard Arabic, and answers visitor questions in the register close to the branch's own audience when needed.",
            },
        ],
    },
}
