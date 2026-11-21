"""Public subscribe links into the existing portal checkout step.

There is no separate ``/checkout`` route. Card payment is the ``#step-checkout``
section on ``/portal``: it shows the chosen plan, then ``POST /api/payments``
sends the buyer to the live gateway. ``checkout=1`` opens that step for the
plan in ``pkg``. While payments are closed the same link stays the interest
form, without a checkout flag, so the label «سجّل اهتمامك» is not a dead pay button.
"""

from __future__ import annotations

from src.services import catalog


def subscribe_path(
    plan_key: str | None,
    *,
    billing: str = "monthly",
    addons: int = 0,
    agents: list[str] | None = None,
) -> str:
    """Path for one public plan. Prices stay in the catalog; this only builds the URL."""
    from src.services import payments

    key = plan_key if plan_key in catalog.PACKAGES else catalog.purchasable_plan_key(plan_key)
    parts = [f"pkg={key}"]
    slugs = [slug for slug in (agents or []) if slug]
    if slugs:
        parts.append("agents=" + ",".join(slugs))
    extra = max(0, int(addons or 0))
    if extra:
        parts.append(f"addons={extra}")
    if billing == "annual":
        parts.append("billing=annual")
    if payments.payments_open():
        parts.append("checkout=1")
    return "/portal?" + "&".join(parts)
