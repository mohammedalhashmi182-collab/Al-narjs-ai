# Runbooks

Production: https://karmaai.online (Render, auto-deploys `main`). Owner alerts go
to the Telegram War Room (`TELEGRAM_OWNER_CHAT_ID`). Never paste secrets into
chat, tickets or commits while following these steps.

## Monitoring at a glance

| Signal | Where |
|---|---|
| Liveness (Render health check) | `GET /health` → `{"status":"healthy"}` (cheap, no dependencies) |
| Deep check | `GET /health/deep` or `/health?deep=1` → db latency + reachability of configured providers (Telegram, Meta, PayPal, Gemini). 503 only when the DB is down. Booleans only, no secrets. |
| Owner view | `GET /api/owner/ops/health` (owner cookie) |
| Uptime self-check | schedule `ops-uptime-self-check`, every 5 min: deep check + `PUBLIC_BASE_URL/health`; alerts owner on failure (throttled 30 min per issue) |
| Errors | `OpsAlertMiddleware`: any 5xx / unhandled exception → owner alert; `/webhooks/*` failures get a named alert |
| Channel health | `GET /webhooks/telegram/health`, `GET /webhooks/whatsapp/health` |

Note: a self-check running inside the app cannot report the app being fully
down. Add an external monitor (e.g. UptimeRobot/Better Stack free tier) on
`https://karmaai.online/health` as well.

## Failed deploy

Symptoms: Render shows the deploy as failed, or the site returns 5xx / the uptime alert fires right after a merge.

1. Render dashboard → service → **Events / Logs**. Identify: build failure (dependency, Dockerfile) vs. start failure (import error, missing env var, DB migration).
2. If production is down: **Rollback** in Render to the last green deploy (Events → previous deploy → "Rollback"). This is safe and immediate.
3. Reproduce locally on the failing commit: `python -m pytest` and `uvicorn src.main:app`.
4. Fix on a branch, open a PR, merge only when tests pass. Never push directly to `main`.
5. Confirm: `/health` 200, `/health/deep` healthy, `/webhooks/telegram/health` OK, send yourself a Telegram test message.

## Expired / invalid Meta (WhatsApp) token

Symptoms: WhatsApp sends fail with Meta error code `190` (OAuthException) or HTTP 401; `send_failed` lead events; template sends fall back to `awaiting_manual`.

1. Check `GET /webhooks/whatsapp/health` (booleans only) and recent `outbound_messages` with `error_code` 190.
2. Meta Business Settings → System users → generate a **permanent system-user token** with `whatsapp_business_messaging` and `whatsapp_business_management` for the WABA. (Temporary tokens expire in 24h.)
3. Render → Environment → update `WHATSAPP_TOKEN` (never paste it anywhere else). Render redeploys.
4. Verify by checking `/webhooks/whatsapp/health` and sending a test message to your own number.
5. Resend the queued fallbacks: messages with status `awaiting_manual` (re-trigger the send from the owner queue).

## Payment webhook failure (PayPal)

Symptoms: owner alert "فشل webhook الدفع"; a customer paid but the order is not activated.

Card checkout (Moyasar) was removed. Historical payment rows may still say `gateway=moyasar`; do not call that provider, and do not delete the rows.

1. PayPal: 401 = signature verification failed (`PAYPAL_WEBHOOK_ID` wrong); 502 = PayPal API unreachable. Check Render logs for `/webhooks/paypal`.
2. Fix the env var in Render if needed (never share values). PayPal is offered to customers only when `CUSTOMER_PAYPAL_ENABLED` is on and `PAYPAL_MODE=live`.
3. Bank transfer stays a manual invoice. The owner confirms receipt with the existing confirm-received flow. Customers can start it when `content/transfer.json` has a valid Saudi IBAN, account name, and bank name. Card checkout stays closed.
4. For a specific paid order that did not activate: confirm the payment in the PayPal dashboard (or the bank statement for a transfer), then activate it through the existing owner payment flow. Do not hand-edit payment rows.
5. In the PayPal dashboard, resend the failed webhook once the secret is fixed. Confirm the customer project shows `active`.
