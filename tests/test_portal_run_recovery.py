"""Provider outages must not strand a paid client's agent in running state."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientAgent, ClientProject


@pytest.mark.parametrize('previous_result', [None, 'Previous deliverable'])
@pytest.mark.parametrize('empty_response', [False, True])
async def test_failed_run_preserves_output_and_can_retry(monkeypatch, previous_result, empty_response):
    from src.main import app
    engine = create_async_engine('sqlite+aiosqlite://', poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(app.state, 'session_factory', maker, raising=False)
    definition = SimpleNamespace(prompt_templates={'default': SimpleNamespace(template_text='test')}, default_parameters={})
    monkeypatch.setattr(app.state, 'agent_registry', SimpleNamespace(get_agent=AsyncMock(return_value=definition)), raising=False)
    monkeypatch.setattr(app.state, 'prompt_engine', SimpleNamespace(render=lambda *args: SimpleNamespace(user_prompt='test', system_prompt='')), raising=False)
    completion = AsyncMock(return_value=SimpleNamespace(content='   ')) if empty_response else AsyncMock(side_effect=RuntimeError('private provider detail'))
    monkeypatch.setattr(app.state, 'model_provider', SimpleNamespace(complete_with_fallback=completion), raising=False)
    try:
        async with maker() as session:
            project = ClientProject(client_name='Test', phone='0500000000', package='social', status='active')
            session.add(project)
            await session.flush()
            agent = ClientAgent(project_id=project.id, slug='social_media', status='interviewing', result=previous_result)
            session.add(agent)
            await session.commit()
            agent_id, project_id = agent.id, project.id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            url = f'/api/portal/projects/{project_id}/agents/social_media/run'
            result = await client.post(url, json={'answers': {'business': 'Test'}})
            assert result.status_code == 503
            assert 'private provider detail' not in result.text
            async with maker() as session:
                saved = await session.get(ClientAgent, agent_id)
                assert saved.status == ('done' if previous_result else 'interviewing')
                assert saved.result == previous_result
            completion.side_effect = None
            completion.return_value = SimpleNamespace(content='New deliverable')
            retry = await client.post(url, json={'answers': {'business': 'Test'}})
            assert retry.status_code == 200
            assert retry.json()['result'] == 'New deliverable'
            async with maker() as session:
                saved = await session.get(ClientAgent, agent_id)
                assert saved.status == 'done'
                assert saved.result == 'New deliverable'
    finally:
        await engine.dispose()


async def test_consult_failure_is_identified_for_recovery_links(monkeypatch):
    from starlette.requests import Request
    from src.main import app, consult_chat, ConsultRequest, ConsultMessage
    monkeypatch.setattr(app.state, 'model_provider', SimpleNamespace(
        complete_with_fallback=AsyncMock(side_effect=RuntimeError('provider unavailable'))
    ), raising=False)
    request = Request({'type': 'http', 'headers': [], 'method': 'POST', 'path': '/api/consult'})
    response = await consult_chat(ConsultRequest(messages=[ConsultMessage(role='user', content='اختبار')]), request)
    assert response['unavailable'] is True
    assert 'تعذر الاتصال' in response['reply']
