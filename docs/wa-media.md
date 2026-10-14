# WhatsApp voice notes and images (tenant reply agent)

Flow: `POST /webhooks/whatsapp` → message on a customer's linked number with `type` `audio`/`image` →
`tenant_reply.safe_handle_media` → `media_understanding.understand`:

1. `GET https://graph.facebook.com/v20.0/{media-id}` with the **customer's own** token (`ClientProject.wa_access_token_enc`) → URL, mime, size.
2. Download (cap `MEDIA_MAX_BYTES`, default 16 MB). Bytes are never stored.
3. Voice → speech-to-text, `language=ar` (OpenAI `whisper-1`, Groq `whisper-large-v3`, or Gemini). Image → vision description + verbatim OCR of visible text.
4. The text goes through the normal RAG reply (`handle_inbound`) scoped to that project, in the project's mode (review by default; auto only if the customer enabled it).

Graceful handoff (chat moves to the customer's human queue, polite Arabic message, never a guess) when:
no provider key (`media_no_provider`), no customer token (`media_no_project_token`), over the plan's
conversation limit (`media_over_limit`, no paid call), provider error, too large, unsupported type, empty transcript.

Usage: every processed item is a `UsageEvent` per tenant (`media_voice`, quantity = seconds reported by the
provider or 1; `media_image`, quantity 1), deduplicated by WhatsApp message id. `usage.media_usage()` gives the
window totals. It does **not** consume the plan's voice-agent minutes; billing it is an owner decision.

Privacy: audio/images go to the chosen provider (OpenAI / Groq / Google). They cannot be PII-masked like text.
Update `/subprocessors` and the DPA before enabling a provider that is not listed there.
