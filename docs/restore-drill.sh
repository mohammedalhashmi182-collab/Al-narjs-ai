#!/usr/bin/env bash
# Al-Narjis local backup/restore drill. NEVER touches production:
# it runs a throwaway PostgreSQL on 127.0.0.1:${PORT}, under env -i, so no
# production DATABASE_URL or other secret from the caller's environment is visible.
# Usage: restore-drill.sh [repo_worktree] [python_with_app_deps]
set -euo pipefail
REPO=${1:-/workspace/wt-audit-d}
PY=${2:-/workspace/alnarjs/.venv/bin/python}
PGBIN=${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)}
PORT=${PORT:-55432}
WORK=$(mktemp -d /tmp/narjis-drill.XXXXXX)
DATA=$WORK/data; DUMP=$WORK/drill_src.dump; LOG=$WORK/pg.log
SRC=drill_src; DST=drill_restored; USER_=drill
URL_SRC="postgresql+asyncpg://$USER_@127.0.0.1:$PORT/$SRC"
CLEAN_ENV=(env -i PATH=/usr/bin:/bin HOME="$WORK" LANG=C.UTF-8)
psqlq() { "${CLEAN_ENV[@]}" "$PGBIN/psql" -X -q -At -h 127.0.0.1 -p "$PORT" -U "$USER_" "$@"; }
cleanup() { "$PGBIN/pg_ctl" -D "$DATA" -m fast stop >/dev/null 2>&1 || true; }
trap cleanup EXIT
echo "== 1. local cluster ($("$PGBIN/postgres" --version)) in $WORK"
"${CLEAN_ENV[@]}" "$PGBIN/initdb" -D "$DATA" -U "$USER_" --auth=trust -E UTF8 >/dev/null
"${CLEAN_ENV[@]}" "$PGBIN/pg_ctl" -D "$DATA" -l "$LOG" -o "-p $PORT -k $WORK -c listen_addresses=127.0.0.1" -w start >/dev/null
"${CLEAN_ENV[@]}" "$PGBIN/createdb" -h 127.0.0.1 -p "$PORT" -U "$USER_" "$SRC"
echo "== 2. apply the app schema exactly as production startup does (src.db.session.init_db + ensure_pgvector)"
cd "$REPO"
"${CLEAN_ENV[@]}" DATABASE_URL="$URL_SRC" ENVIRONMENT=test SECRET_KEY=drill-not-a-secret-0000000000000000 OWNER_PASSWORD=drill-only PYTHONPATH="$REPO" "$PY" - <<'PY'
import asyncio
from src.db.session import init_db, ensure_pgvector
async def main():
    await init_db(); print("init_db ok; pgvector:", await ensure_pgvector())
asyncio.run(main())
PY
echo "tables: $(psqlq -d $SRC -c "select count(*) from information_schema.tables where table_schema='public'")"
echo "== 3. synthetic rows (3 per table, FK order, fake values only)"
"${CLEAN_ENV[@]}" DATABASE_URL="$URL_SRC" ENVIRONMENT=test SECRET_KEY=drill-not-a-secret-0000000000000000 OWNER_PASSWORD=drill-only PYTHONPATH="$REPO" "$PY" - <<'PY'
import asyncio, uuid, datetime as dt, os, sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
import src.models  # noqa
from src.db.session import Base
N = 3
def val(col, i, refs):
    if col.foreign_keys:
        fk = next(iter(col.foreign_keys)); pool = refs.get((fk.column.table.name, fk.column.name)) or []
        return pool[i % len(pool)] if pool else None
    t = col.type; py = None
    try: py = t.python_type
    except Exception: pass
    name = type(t).__name__.lower()
    if "uuid" in name or py is uuid.UUID: return uuid.uuid4()
    if getattr(t, "enums", None): return t.enums[0]
    if py is bool: return bool(i % 2)
    if py is int: return 1000 + i
    if py in (float,) or "numeric" in name: return 10 + i
    if py is dt.datetime: return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(hours=i)
    if py is dt.date: return dt.date(2026, 1, 1 + i)
    if py in (dict,) or "json" in name: return {"synthetic": i}
    if py is list or "array" in name: return []
    if py is str:
        s = f"syn-{col.table.name}-{col.name}-{i}"
        if "email" in col.name: s = f"drill{i}@example.invalid"
        if "phone" in col.name: s = f"9665000000{i}"
        n = getattr(t, "length", None)
        return s[-n:] if n else s
    return None
async def main():
    eng = create_async_engine(os.environ["DATABASE_URL"])
    refs, done, skipped = {}, 0, []
    for table in Base.metadata.sorted_tables:
        ok = 0
        for i in range(N):
            row = {}
            for c in table.columns:
                if c.name == "embedding_vec": continue
                v = val(c, i, refs)
                if v is None and (c.nullable or c.server_default is not None or c.autoincrement is True and c.primary_key):
                    continue
                row[c.name] = v
            try:
                async with eng.begin() as conn:
                    res = await conn.execute(table.insert().values(**row).returning(*table.primary_key.columns, *[c for c in table.columns if c.unique or any(c is fk.column for t2 in Base.metadata.tables.values() for col in t2.columns for fk in col.foreign_keys)]))
                    r = res.mappings().first()
                    for k, v in r.items(): refs.setdefault((table.name, k), []).append(v)
                ok += 1
            except Exception as e:
                skipped.append(f"{table.name}: {type(e).__name__}"); break
        done += ok
    print(f"synthetic rows inserted: {done}; tables skipped: {len(set(skipped))}")
    for s in sorted(set(skipped)): print("  skip", s)
    await eng.dispose()
asyncio.run(main())
PY
CHK="select string_agg(t || ':' || n || ':' || h, E'\n' order by t) from (select table_name t, (xpath('/row/c/text()', query_to_xml(format('select count(*) c from %I', table_name), false, true, '')))[1]::text n, (xpath('/row/h/text()', query_to_xml(format('select coalesce(md5(string_agg(x::text, ''|'' order by x::text)), ''empty'') h from %I x', table_name), false, true, '')))[1]::text h from information_schema.tables where table_schema='public' and table_type='BASE TABLE') s"
psqlq -d "$SRC" -c "$CHK" > "$WORK/src.chk"
echo "rows in source: $(awk -F: '{s+=$2} END{print s}' "$WORK/src.chk") across $(wc -l < "$WORK/src.chk") tables"
echo "== 4. pg_dump (custom format)"
"${CLEAN_ENV[@]}" "$PGBIN/pg_dump" -h 127.0.0.1 -p "$PORT" -U "$USER_" -Fc --no-owner --no-privileges -f "$DUMP" "$SRC"
ls -l "$DUMP" | awk '{print "dump bytes:", $5}'
echo "== 5. second database + pg_restore"
"${CLEAN_ENV[@]}" "$PGBIN/createdb" -h 127.0.0.1 -p "$PORT" -U "$USER_" "$DST"
"${CLEAN_ENV[@]}" "$PGBIN/pg_restore" -h 127.0.0.1 -p "$PORT" -U "$USER_" --no-owner --no-privileges --exit-on-error -d "$DST" "$DUMP"
psqlq -d "$DST" -c "$CHK" > "$WORK/dst.chk"
echo "== 6. verify per-table row counts + md5 checksums"
if diff -u "$WORK/src.chk" "$WORK/dst.chk"; then
  echo "RESULT: PASS ($(wc -l < "$WORK/dst.chk") tables identical; sha256 of checksum list $(sha256sum < "$WORK/dst.chk" | cut -c1-16))"
else
  echo "RESULT: FAIL"; exit 1
fi
echo "artifacts: $WORK (src.chk, dst.chk, drill_src.dump)"
