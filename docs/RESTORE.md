# RESTORE.md — Al-Narjis database & deploy recovery
Prod DB = Neon Postgres (DATABASE_URL in Render env group **"paypal"**, linked to service Al-narjs-ai-1 / srv-dagt70rl550s73ecl7o0). There is no Render Postgres.
Golden rule: **never restore in place.** Always restore into a NEW Neon branch, validate, then repoint. Every step that changes prod needs the owner's explicit OK.

## A. Restore to a new branch (point-in-time)
Ref: https://neon.com/branching/recovery-workflows.md , https://neon.com/docs/postgres/backup-restore/history-window.md
1. Freeze writes if possible (announce; optionally pause cron/agent jobs). Note incident time T (UTC).
2. Neon console → project → Branches → **Create branch** from `main` **at a timestamp** just before T (must be inside the history window — check plan first). Name `restore-YYYYMMDD-HHMM`. Do NOT use "Restore" on the root branch (that's in-place; it keeps `{branch}_old_{ts}` but still replaces prod).
3. Get the new branch's **pooled** connection string; convert to `postgresql+asyncpg://…` form matching the current value's format (sslmode/params identical).
4. Validate the branch read-only from a trusted machine: row counts for key tables (users, projects, subscriptions/payments, invoices, store_connections, conversations) vs. expectations; spot-check the deleted rows exist.
5. Optional (partial recovery): instead of repointing, copy only the missing rows from the branch into prod (`pg_dump --data-only -t <table> --where`-style or INSERT … SELECT via dblink) — preferred when only a few rows were lost and later writes must be kept.
6. Full cutover (owner approval): Render → env group "paypal" → set DATABASE_URL to the new branch → service redeploys; `init_db` self-heals schema on boot.
7. Verify: /healthz (or homepage) 200, portal login, owner console, one payment-status page, logs free of DB errors.
8. Keep the old branch untouched ≥7 days for forensics. Record actual RTO/RPO.

## B. Restore from a logical dump (if one exists in future)
`createdb` on a NEW Neon branch/project → `pg_restore --no-owner --exit-on-error -d <new> dump.pgc` → compare counts/checksums (as restore-drill.sh does) → repoint as A.6.

## C. Checklist — accidental deletion
- [ ] Stop the bleeding: identify actor (owner console / agent / migration / script); disable it.
- [ ] Record T (UTC + Riyadh), affected tables, approximate row count.
- [ ] Check T is inside the Neon history window (plan!). If not → data unrecoverable from Neon; check exports/emails/payment provider (Moyasar/PayPal) for reconstruction.
- [ ] Create restore branch at T-1min (A.2). Never in place.
- [ ] Validate (A.4). Choose partial copy (A.5) vs cutover (A.6, owner OK).
- [ ] Verify app (A.7); notify affected customers if needed; post-mortem.

## D. Checklist — bad deploy (described only; not triggered in this audit)
- [ ] Confirm the regression is code (errors started at deploy time in Render events/logs).
- [ ] Render dashboard → service → Events/Deploys → previous good deploy → **Rollback** (https://render.com/docs/rollbacks). Note: autoDeploy=yes, so the next push to main redeploys — revert the commit on main via PR too.
- [ ] If the bad deploy ran destructive schema/data changes (init_db ALTERs only add; check any data scripts), treat as accidental deletion → section C.
- [ ] Verify (A.7). Note: no healthCheckPath is set on the service, so Render won't auto-block a broken-but-listening deploy — consider adding one.
