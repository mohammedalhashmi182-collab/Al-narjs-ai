# Agent tools (env vars)

All tools are read-only toward the outside world and degrade gracefully when unset.

| Tool | Env vars | Where to get it |
|---|---|---|
| Web search (analysts) | one of `TAVILY_API_KEY` (preferred), `BRAVE_SEARCH_API_KEY`, `SERPER_API_KEY`; optional `WEB_SEARCH_PROVIDER=tavily\|brave\|serper` | app.tavily.com · api-dashboard.search.brave.com · serper.dev |
| Salla (store_manager) | `SALLA_ACCESS_TOKEN` (merchant token); OAuth install: `SALLA_CLIENT_ID`, `SALLA_CLIENT_SECRET`, `SALLA_REDIRECT_URI` | Salla Partners portal (salla.partners) → create app, scopes: products.read, orders.read |
| Zid (store_manager) | `ZID_AUTHORIZATION_TOKEN`, `ZID_MANAGER_TOKEN`, `ZID_STORE_ID`; OAuth install: `ZID_CLIENT_ID`, `ZID_CLIENT_SECRET`, `ZID_REDIRECT_URI` | Zid Partner Dashboard (partner.zid.sa) → create app; tokens come from the OAuth token response |
| Uploads | optional `AGENT_UPLOAD_MAX_BYTES` (default 5 MB), `KB_UPLOAD_MAX_BYTES` (default 3 MB) | — |

Owner endpoints: `GET /api/owner/tools/status`, `GET /api/owner/stores/{salla|zid}/snapshot`,
`GET /api/owner/stores/{salla|zid}/connect`, `GET/POST/DELETE /api/owner/knowledge`.
Smart replies use the owner knowledge base but still go through the channel mode (review by default).
