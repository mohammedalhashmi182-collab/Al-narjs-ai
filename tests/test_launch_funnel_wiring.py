"""Launch funnel wiring: a paid payment must actually activate the client's
portal project, and an unpaid one must not. Covers the payment -> subscription
-> team chain that previously existed only as decorative UI."""

from uuid import uuid4

import pytest

from src.db.session import engine
from src.models import ClientAgent, ClientProject, Payment
from src.services import payments as pm


@pytest.fixture(scope="module", autouse=True)
async def _db():
    import src.models  # noqa: F401  register models on Base.metadata
    from src.db.session import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def _pending_project(package: str = "social", phone: str = "0500000000", created=None) -> ClientProject:
    from datetime import datetime, timezone
    from src.db.session import async_session_factory
    async with async_session_factory() as session:
        project = ClientProject(
            client_name="Test Client", phone=phone, email="c@example.com", package=package, status="pending",
            created_at=created or datetime.now(timezone.utc),
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def _paid_payment(package: str = "social", project_id=None, phone="0500000000") -> Payment:
    from src.db.session import async_session_factory
    async with async_session_factory() as session:
        payment = Payment(
            amount=150000,
            currency="SAR",
            package=package,
            customer_name="Test Client",
            customer_phone=phone,
            customer_email="c@example.com",
            project_id=project_id,
            status="paid",
            gateway="moyasar",
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment


async def test_payment_carries_project_link():
    from src.db.session import async_session_factory
    pid = uuid4()
    async with async_session_factory() as session:
        payment = await pm.create_payment(
            session,
            "social",
            customer_name="A",
            customer_phone="0500000000",
            customer_email="a@example.com",
            project_id=pid,
        )
        assert payment.project_id == pid
        assert payment.status == "pending"


async def test_paid_payment_activates_pending_project():
    from src.db.session import async_session_factory
    project = await _pending_project()
    payment = await _paid_payment(project_id=project.id)

    async with async_session_factory() as session:
        result = await pm.activate_subscription(session, await _fetch(payment))
        assert result["activated"] is True

    async with async_session_factory() as session:
        p = await session.get(ClientProject, project.id)
        assert p.status == "active"
        assert p.subscription_note


async def test_activation_is_idempotent():
    from src.db.session import async_session_factory
    project = await _pending_project()
    payment = await _paid_payment(project_id=project.id)
    async with async_session_factory() as session:
        first = await pm.activate_subscription(session, await _fetch(payment))
        second = await pm.activate_subscription(session, await _fetch(payment))
    assert first["activated"] is True
    assert second["activated"] is True
    assert second.get("already_active") is True


async def test_unpaid_payment_does_not_activate():
    from src.db.session import async_session_factory
    project = await _pending_project()
    async with async_session_factory() as session:
        payment = Payment(
            amount=150000, currency="SAR", package="social",
            customer_phone=project.phone, project_id=project.id,
            status="pending", gateway="invoice",
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        result = await pm.activate_subscription(session, payment)
    assert result["activated"] is False
    async with async_session_factory() as session:
        p = await session.get(ClientProject, project.id)
        assert p.status == "pending"


async def test_phone_package_fallback_activates_latest_pending():
    from datetime import datetime, timedelta, timezone
    from src.db.session import async_session_factory
    now = datetime.now(timezone.utc)
    first = await _pending_project(phone="0599999999", created=now - timedelta(minutes=5))
    second = await _pending_project(phone="0599999999", created=now)
    payment = await _paid_payment(project_id=None, phone="0599999999")
    async with async_session_factory() as session:
        result = await pm.activate_subscription(session, await _fetch(payment))
    # Latest created (second) must win, not `first`.
    async with async_session_factory() as session:
        p = await session.get(ClientProject, second.id)
        assert p.status == "active"
        p_first = await session.get(ClientProject, first.id)
        assert p_first.status == "pending"


async def _fetch(payment: Payment):
    from src.db.session import async_session_factory
    async with async_session_factory() as session:
        return await session.get(Payment, payment.id)