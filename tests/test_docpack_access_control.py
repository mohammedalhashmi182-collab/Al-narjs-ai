"""Project outputs are not public bearer links; demo outputs remain explicit samples."""
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token as owner_token
from src.core.portal_auth import COOKIE_NAME, make_session_token as portal_token
from src.db.session import Base
from src.models import ClientProject
from src.services.docgen.store import PACKS


@pytest.fixture
async def setup_app(monkeypatch):
    from src.main import app
    from src.utils.rate_limit import docpack_api_limiter, docpack_demo_limiter, docpack_demo_global_limiter

    engine = create_async_engine('sqlite+aiosqlite://', poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        a = ClientProject(client_name='Test A', phone='00001', package='bidaya', status='active')
        b = ClientProject(client_name='Test B', phone='00002', package='bidaya', status='active')
        session.add_all([a, b]); await session.commit()
    monkeypatch.setattr(app.state, 'session_factory', maker, raising=False)
    monkeypatch.setattr(app.state, 'model_provider', None, raising=False)
    # This fixture isolates token authorization from the independent QA
    # provider; missing reviewer behavior is covered by release-gate tests.
    from src.services.docgen.release_gate import ReleaseApproval, pack_digest
    async def reviewed(pack, provider):
        return ReleaseApproval(pack_digest(pack), "test-independent-reviewer")
    monkeypatch.setattr("src.interfaces.docpack_routes.independent_review", reviewed)
    for limiter in (docpack_api_limiter, docpack_demo_limiter, docpack_demo_global_limiter):
        limiter.reset()
    PACKS.reset()
    yield app, maker, a, b
    PACKS.reset()
    await engine.dispose()


def client(app, cookies=None):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', cookies=cookies or {})


@pytest.mark.asyncio
async def test_project_download_rejects_anonymous_other_tenant_revoked_and_inactive(setup_app):
    app, maker, a, b = setup_app
    old_cookie = {COOKIE_NAME: portal_token(a)}
    async with client(app, old_cookie) as c:
        result = await c.post('/api/docpack', data={'brief':'100 ثم 150', 'agent_key':'data_analyst', 'formats':'xlsx'})
        assert result.status_code == 200, result.text
        url = result.json()['files'][0]['url']
        assert (await c.get(url)).status_code == 200
    async with client(app) as c:
        assert (await c.get(url)).status_code == 404
    async with client(app, {COOKIE_NAME: portal_token(b)}) as c:
        assert (await c.get(url)).status_code == 404
    async with client(app, {'narjis_owner': owner_token()}) as c:
        assert (await c.get(url)).status_code == 200
    async with maker() as s:
        project = await s.get(ClientProject, a.id)
        project.portal_token_version += 1
        await s.commit()
    async with client(app, old_cookie) as c:
        assert (await c.get(url)).status_code == 404
    async with maker() as s:
        project = await s.get(ClientProject, a.id)
        new_cookie = {COOKIE_NAME: portal_token(project)}
        project.status = 'expired'
        await s.commit()
    async with client(app, new_cookie) as c:
        assert (await c.get(url)).status_code == 404


@pytest.mark.asyncio
async def test_owner_file_private_and_demo_deliberately_public(setup_app):
    app, _, a, _ = setup_app
    async with client(app, {'narjis_owner': owner_token()}) as c:
        result = await c.post('/api/docpack', data={'brief':'100 ثم 150', 'agent_key':'data_analyst', 'formats':'xlsx'})
        assert result.status_code == 200, result.text
        private_url = result.json()['files'][0]['url']
        assert (await c.get(private_url)).status_code == 200
    async with client(app, {COOKIE_NAME: portal_token(a)}) as c:
        assert (await c.get(private_url)).status_code == 404
    async with client(app) as c:
        assert (await c.get(private_url)).status_code == 404
        demo = await c.post('/api/docpack/demo', data={'sample':'1'})
        assert demo.status_code == 200, demo.text
        assert (await c.get(demo.json()['files'][0]['url'])).status_code == 200


def test_pack_store_requires_explicit_valid_scope():
    with pytest.raises(ValueError):
        PACKS.put([], scope='project')
    with pytest.raises(ValueError):
        PACKS.put([], scope='demo', project_id='other-project')
    with pytest.raises(ValueError):
        PACKS.put([], scope='unknown')

@pytest.mark.asyncio
async def test_legacy_agent_path_fails_closed_to_owner_only(setup_app, monkeypatch):
    from types import SimpleNamespace
    from src.main import _maybe_docpack
    from src.services.agent_tools import docpack_tool
    from src.services.docgen.schema import BuiltFile

    app, _, a, b = setup_app
    file = BuiltFile(format='xlsx', filename='result.xlsx', content=b'fixture',
                     media_type='application/octet-stream', label_ar='ملف', label_en='File')
    pack = SimpleNamespace(files=[file], meta=SimpleNamespace(agent_key='data_analyst'),
                           narrative=SimpleNamespace(source='test'), analysis=SimpleNamespace(facts=[]))
    async def fake_build(**kwargs):
        return pack
    monkeypatch.setattr(docpack_tool, 'build', fake_build)
    request = SimpleNamespace(app=app, client=SimpleNamespace(host='127.0.0.1'), headers={})
    result = await _maybe_docpack('data_analyst', {'docpack': True, 'goal': 'test'}, a, request)
    url = result['files'][0]['url']
    async with client(app, {COOKIE_NAME: portal_token(a)}) as c:
        assert (await c.get(url)).status_code == 404
    async with client(app, {COOKIE_NAME: portal_token(b)}) as c:
        assert (await c.get(url)).status_code == 404
    async with client(app, {'narjis_owner': owner_token()}) as c:
        assert (await c.get(url)).status_code == 200