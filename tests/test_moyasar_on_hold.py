"""The shipped release remains Pending even when live credentials are present."""
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from src.config.settings import get_settings
from src.models import Payment
from src.services import payments as pm


@pytest.fixture
def live_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'moyasar_api_secret', 'sk_' + 'live_FAKE-FOR-TESTS')
    monkeypatch.setattr(settings, 'moyasar_publishable_key', 'pk_' + 'live_FAKE-FOR-TESTS')


def test_release_is_pending_even_with_live_credentials(live_keys):
    assert pm.MOYASAR_ON_HOLD is True
    caps = pm.readiness(card_state='ok')
    assert caps['moyasar_status'] == 'pending'
    assert caps['moyasar_on_hold'] is True
    assert caps['card_credentials'] == 'pending'
    assert not caps['card']
    assert all(not caps['methods'][method] for method in pm.CARD_METHODS)
    assert pm.get_publishable_key() is None


async def test_hold_never_contacts_gateway_or_creates_invoice(live_keys, monkeypatch):
    get = AsyncMock(side_effect=AssertionError('Gateway must not be contacted'))
    post = AsyncMock(side_effect=AssertionError('Gateway must not be contacted'))
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    assert await pm.probe_moyasar_credentials() == 'pending'
    assert (await pm.capabilities_async())['moyasar_status'] == 'pending'
    payment = Payment(id=uuid4(), amount=49900, currency='SAR', status='pending')
    session = AsyncMock()
    with pytest.raises(pm.PaymentError, match='On Hold'):
        await pm.initiate_moyasar(session, payment, pm.source_mada())
    assert await pm.handle_moyasar_webhook(session, {'type': 'payment_paid'}) == {
        'ok': True, 'ignored': 'moyasar_on_hold',
    }
    session.commit.assert_not_awaited()
    get.assert_not_awaited()
    post.assert_not_awaited()
    assert payment.status == 'pending'


def test_paid_event_cannot_activate_held_payment(live_keys):
    payment = Payment(id=uuid4(), amount=49900, total_halalas=49900, status='pending')
    pm.apply_gateway_status(payment, {'status': 'paid', 'amount': 49900, 'currency': 'SAR'})
    assert payment.status == pm.REVIEW_STATUS


async def test_public_payment_api_rejects_cards_before_creating_order(live_keys):
    from src.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        caps = await client.get('/api/payments/capabilities')
        assert caps.status_code == 200
        assert caps.json()['moyasar_status'] == 'pending'
        response = await client.post('/api/payments', json={
            'package': 'bidaya', 'method': 'mada',
            'customer_name': 'Test', 'customer_phone': '0555555555',
            'refund_consent': True,
        })
        assert response.status_code == 503, response.text
