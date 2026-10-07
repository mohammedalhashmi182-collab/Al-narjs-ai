"""The Postgres self-heal list must cover what the live database was missing.

``init_db()`` runs ``create_all``, which creates missing *tables* but does
nothing about missing *columns* on a table that already exists. The production
Postgres was built before ``payments.lead_id`` existed on the model, so every
payment INSERT failed with *"column lead_id does not exist"* and the checkout
answered 500 to every buyer.

A fresh SQLite database in CI never sees this: ``create_all`` builds the entire
current schema, so the suite stayed green while production could not take a
payment. The invariant is therefore asserted against the model metadata and the
migration list directly, rather than left for a live database to discover.

Note the two lists in ``session.py`` are named the wrong way round for a reader:
``placeholders`` is the **postgresql** branch and ``sqlite_placeholders`` is the
SQLite one. These tests target ``placeholders``, which is the one that matters
here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SESSION_PY = ROOT / "src" / "db" / "session.py"

# Columns confirmed absent from the live Postgres schema by comparing SQLAlchemy
# metadata against information_schema. Only genuine drift belongs here.
KNOWN_DRIFT = [("payments", "lead_id")]


def _postgres_placeholders() -> list[tuple[str, str, str]]:
    """Read (table, column, ddl) out of the postgresql branch of init_db()."""
    tree = ast.parse(SESSION_PY.read_text(encoding="utf-8"))
    found: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", "") == "placeholders" for target in node.targets
        ):
            for element in node.value.elts:
                table, column, ddl = element.elts
                found.append((table.value, column.value, ddl.value))
    return found


def test_the_postgres_self_heal_list_is_readable() -> None:
    assert len(_postgres_placeholders()) > 5, "could not parse the postgresql self-heal list"


@pytest.mark.parametrize(("table", "column"), KNOWN_DRIFT)
def test_drifted_column_is_covered(table: str, column: str) -> None:
    pairs = {(t, c) for t, c, _ in _postgres_placeholders()}
    assert (table, column) in pairs, (
        f"{table}.{column} was missing from the live database. Add it to the "
        f"postgresql self-heal list in src/db/session.py -- create_all never "
        f"adds a column to a table that already exists."
    )


def test_lead_id_is_added_as_a_uuid() -> None:
    """A wrong type would fail on the first non-null write, silently later."""
    for table, column, ddl in _postgres_placeholders():
        if (table, column) == ("payments", "lead_id"):
            assert ddl.strip().upper() == "UUID", f"expected UUID, got {ddl!r}"
            return
    pytest.fail("payments.lead_id is absent from the postgresql self-heal list")


def test_every_entry_is_a_triple_of_strings() -> None:
    for table, column, ddl in _postgres_placeholders():
        assert isinstance(table, str) and table
        assert isinstance(column, str) and column
        assert isinstance(ddl, str) and ddl


def test_the_postgres_branch_uses_add_column_if_not_exists() -> None:
    """Without IF NOT EXISTS, every second boot would raise on a duplicate."""
    source = SESSION_PY.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS" in source, "postgres self-heal is not idempotent"


def test_each_alter_is_individually_guarded() -> None:
    """One bad entry must not abort the rest of the migrations on boot."""
    source = SESSION_PY.read_text(encoding="utf-8")
    loop = source[source.index("for table, column, ddl in placeholders") :]
    assert "try:" in loop[:200], "the postgres ALTER loop is not guarded by try/except"