# Status monitoring

The site already publishes its own status:

- Arabic page: https://karmaai.online/ar/status
- English page: https://karmaai.online/en/status
- JSON: https://karmaai.online/api/status

The JSON is cached for 30 seconds. It reports `operational`, `degraded`, or
`outage` for the site, `/health`, the customer portal, and the agent registry.
It does not include keys, hostnames, or error text.

`GET /health` stays the cheap process check Render uses. Monitor that as well
as `/api/status`.

## Free UptimeRobot monitor

The free plan (no card) allows 50 monitors at a 5-minute interval, plus one
basic status page on `stats.uptimerobot.com`. A custom domain on that UptimeRobot
page is a paid feature (Solo and above). Use the free monitor for alerts, and
use the steps in the next section for `status.karmaai.online`.

1. Create an account at https://uptimerobot.com (Free).
2. Add Monitor → HTTP(s).
3. Friendly name: `Al-Narjis status`.
4. URL: `https://karmaai.online/api/status`
5. Monitoring interval: 5 minutes (the free-plan minimum).
6. Keyword on this monitor, optional: `outage`, and alert when the keyword
   **exists**. Do not alert on a missing `operational`. A degraded feed still
   contains `operational` for the components that are up.
7. Add a second HTTP(s) monitor for `https://karmaai.online/health` and expect
   HTTP 200. Render already probes this path. This UptimeRobot check is the
   one from outside the host. No keyword on `/health`.
8. Alert contacts: the owner's email. Do not put an API token in the repository.
9. Status Pages → Create Status Page. Name it Al-Narjis. Attach the two monitors.
   The free page URL looks like `https://stats.uptimerobot.com/<your-page>`.
   Leave the custom-domain field empty on the free plan.

## status.karmaai.online

This hostname should show the same status page the app already renders. It does
not depend on a paid UptimeRobot domain.

1. In the Render dashboard, open the web service and add the custom domain
   `status.karmaai.online`. Render shows the CNAME target (the service hostname
   on `onrender.com`). Do not guess that hostname.
2. At the DNS host for `karmaai.online`, add:

   | Type | Name | Value |
   | --- | --- | --- |
   | CNAME | status | the Render target from step 1 |

3. Wait until the certificate is issued. Then:

   - `https://status.karmaai.online/` redirects to the Arabic status page
   - `https://status.karmaai.online/en` redirects to the English status page
   - `https://status.karmaai.online/api/status` is the same JSON feed

If the domain's CAA records limit certificate issuers, allow Let's Encrypt
(`0 issue "letsencrypt.org"`). If there is no CAA record, leave DNS as it is.

UptimeRobot's own custom domain (CNAME to `stats.uptimerobot.com`) needs their
Solo plan or higher. Skip that while the goal is a free monitor. The branded
page is the one on this app.
