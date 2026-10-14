# PDPL cross-border transfer risk assessment (TRA)

Controller / processor: The Arabian Convoy Establishment — Al-Narjis AI (CR 31332495263), Riyadh.
Scope: personal data processed by karmaai.online and sent outside the Kingdom of Saudi Arabia.
Framework: the Personal Data Protection Law (PDPL, Royal Decree M/19, amended M/148), its Implementing
Regulation, and SDAIA's *Regulation on Personal Data Transfer outside the Kingdom*. This includes the
risk-assessment duty that applies when a transfer relies on appropriate safeguards (e.g. Standard
Contractual Clauses) or on an exemption, and to continuous or large-scale transfers.
Status: v1, 14 Oct 2026. Engineering draft. **Owner and a qualified Saudi privacy adviser must review it before relying on it.** Review it every 12 months and whenever a subprocessor changes.

## 1. Data categories

| Category | Examples | Sensitive under PDPL? | Source |
|---|---|---|---|
| Customer (subscriber) account | name, phone, email, business, package | No | checkout / portal |
| End-customer messages | WhatsApp, Telegram and Messenger text sent to a subscriber's agent | Usually no; can incidentally contain health (clinics), financial or ID data | channel webhooks |
| Contact identifiers | phone numbers, display names | No | channel webhooks |
| Knowledge-base content | FAQ, prices, policies uploaded by the subscriber | Normally business data | portal |
| Billing | invoices, payment status (no card numbers stored by us) | No (financial) | Moyasar / PayPal |
| Operational logs | request paths, error types (no message bodies or secrets by policy) | No | app |

We do not deliberately collect sensitive data (health, religion, criminal, genetic, credit). Clinic tenants must be told in onboarding not to collect diagnoses over chat.

## 2. Transfers and risk per recipient

Risk scale: L / M / H. It weighs data volume, sensitivity, the recipient country's protection level, and the provider's contractual controls.

| Recipient | Purpose | Country / region | Data sent | Safeguards in place | Residual risk |
|---|---|---|---|---|---|
| **Google — Gemini API** (default LLM) | generate replies / diagnoses | USA and global Google infra | prompt text (CEO advisor, agents) | **PII masking before send** (phones, emails, national/iqama IDs, IBANs → placeholders; `src/core/pii_mask.py`, `PII_MASKING=on`). TLS. Paid-tier API terms: prompts are not used to train models. Minimal prompts. | **L–M** |
| **Moonshot AI — Kimi** (fallback LLM) | fallback replies | China / Singapore (provider infra) | same as above, only when Gemini fails | PII masking, TLS, fallback-only use | **M**. China is not on any adequacy list. Recommend disabling the fallback for tenant/end-customer content, or replacing it with an EU/US provider |
| OpenAI / Groq / Anthropic / OpenRouter (optional, off unless key set) | optional LLMs | USA | prompt text | PII masking, TLS, API no-training terms | L–M (only if enabled) |
| **Render** | hosting app + PostgreSQL | USA (default region **Oregon** unless the owner chose Frankfurt/Singapore. `render.yaml` sets no region, so confirm in the dashboard) | **all** stored data | TLS in transit, provider encryption at rest, access limited to owner, secrets only in env vars | **M**. Full dataset abroad. Option: move to the Frankfurt (EU) region, or a KSA region host if one becomes required |
| **Meta** (WhatsApp Cloud API, Messenger) | message delivery | USA / global | message text, phone numbers | Required by the channel the subscriber chose. Meta's WhatsApp Business terms and data processing terms. TLS. | M (inherent to the channel; disclosed) |
| **Telegram** | channel + owner alerts | UAE / global | message text, chat ids; alerts carry no secrets | TLS. Owner alerts are minimised (ids, statuses) | L–M |
| **Brevo** (email, when enabled) | transactional email | EU (France) | email address, invoice/notice content | GDPR-grade DPA, TLS | L |
| **PayPal** (optional payment method) | card / PayPal payment | USA / Luxembourg | payer name, email, amount | PCI-DSS. We never see card data. Only sent when the buyer chooses PayPal | L |
| Moyasar | card payments | KSA (Saudi company) | payer data, amount | domestic, PCI-DSS | not a cross-border transfer |

## 3. Safeguards (technical and organisational)

1. **Minimisation:** only the text needed for the reply is sent to an LLM. Tenant Reply Agent answers come from the tenant's KB locally (no LLM call today).
2. **PII redaction before LLM (implemented):** `ModelProvider.complete`, `complete_with_fallback` and `stream` mask emails, Saudi national/iqama IDs, Saudi IBANs and phone numbers (Saudi and international, Arabic-Indic digits included) for every external provider. Values are restored locally in the answer. The switch is env `PII_MASKING` (default **on**); a call can opt out with `metadata["pii_mask"]=False` (none do today). Local Ollama is not masked because the data stays on the server. Limits: names, addresses and free-text health details are **not** detected.
3. **Encryption:** TLS for every provider call and webhook. Database encryption at rest by Render. Secrets only in env vars, never logged.
4. **Retention** (published on `/subprocessors` and `/dpa`): conversations, files and KB for the subscription term plus 30 days; invoices as ZATCA requires; logs up to 90 days; opt-out numbers kept only on the do-not-contact list.
5. **Access control:** owner console cookie auth; portal session auth per project; tenant isolation tests.
6. **Contracts:** each subprocessor's API / business terms and DPA (Google Cloud DPA, Meta business terms, Brevo DPA, PayPal). **Action:** sign SDAIA Standard Contractual Clauses where a provider offers custom terms; otherwise record reliance on their published DPA.
7. **Transparency:** `/privacy` §3a, `/dpa` §4 and `/subprocessors` carry the cross-border clause.

## 4. Legal basis

- **Processing:** performance of the contract with the subscriber (PDPL Art. 6(2)) and legitimate interest in operating and securing the service. End-customer data is processed on the subscriber's documented instructions (the subscriber is the controller for its own customers; we are processor). Consent where the subscriber collects it.
- **Transfer:** necessary for performing the agreement with the data subject or controller, with appropriate safeguards (contractual terms, masking, encryption). This assessment documents why the transfer does not prejudice national security or vital interests, and why minimisation is applied.

## 5. Conclusion and actions

The transfers are acceptable with the safeguards above, **except** the items below. Owner decisions:

1. Confirm the Render region; consider Frankfurt.
2. Decide on Moonshot (China) as fallback: restrict it to non-personal content, or replace it.
3. Sign or record SCCs/DPAs per provider.
4. Add an onboarding notice for clinics (no diagnoses over chat).
5. Get a legal review of this document and the `/dpa` text.
