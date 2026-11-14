"""Auth/ownership and API protocol tests. Mock transport is not a quality eval."""
import io
import hashlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app import accounts
from app.account_context import current_account
from app.main import app, engine
from app.documents import SESSIONS, session
from app.engine import TranslationTooLong
from app.openai_engine import ProviderError


@pytest.fixture
def users(tmp_path, monkeypatch):
    store = accounts.Store(tmp_path / 'accounts.sqlite')
    store.init()
    monkeypatch.setattr(accounts, 'store', store)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    admin = store.create_user('test-admin', 'only-for-contract-tests-12345', 'admin')
    user = store.create_user('test-user', 'only-for-contract-tests-67890', 'user')
    client = TestClient(app, headers={'X-Kun-Request': '1'})
    yield store, client, admin, user
    SESSIONS.clear()


def login(client, who='admin'):
    password = 'only-for-contract-tests-12345' if who == 'admin' else 'only-for-contract-tests-67890'
    response = client.post('/api/auth/login', json={'username': 'test-' + who, 'password': password})
    assert response.status_code == 200, response.text
    return response


def test_login_cookie_csrf_and_admin_boundary(users):
    store, client, admin, user = users
    assert client.get('/api/languages').status_code == 401
    assert client.get('/api/health').json()['model'] == 'unconfigured'
    response = login(client, 'user')
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'password' not in response.text and 'token' not in response.text
    assert client.get('/api/languages').status_code == 200
    assert client.get('/api/admin/users').status_code == 403
    assert client.put('/api/admin/provider', json={'model': 'gpt-4.1-mini'}).status_code == 403
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.invalid'}).status_code == 403
    assert client.post('/api/auth/logout', headers={'X-Kun-Request': '0'}).status_code == 403
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/history').status_code == 401


def test_only_admin_can_delete_user_and_deletion_removes_account_data(users):
    store, client, admin, user = users
    user_id = user['id']
    path = f'/api/admin/users/{user_id}'
    login(client, 'user')
    user_cookie = client.cookies.get(accounts.COOKIE)
    assert client.post('/api/history', json={
        'input': 'hello', 'output': 'xin chào', 'source': 'en', 'target': 'vi',
    }).status_code == 200
    assert client.delete(path).status_code == 403
    store.record_usage(user_id, 'fixture', 1, 1)
    store.record_usage(admin['id'], 'fixture', 1, 1)
    with store.connect() as db:
        db.execute('''INSERT INTO chatgpt_connections(user_id,issuer,subject,client_id,credentials)
            VALUES (?,?,?,?,?)''', (user_id, 'issuer', 'subject', 'client', 'fixture'))
        db.execute('''INSERT INTO chatgpt_attempts(state_hash,user_id,actor_id,session_hash,payload,expires)
            VALUES (?,?,?,?,?,?)''', ('state', user_id, admin['id'], 'session', 'fixture', int(time.time()) + 60))

    login(client)
    assert client.delete(path, headers={'Origin': 'https://evil.invalid'}).status_code == 403
    assert client.delete(f"/api/admin/users/{admin['id']}").status_code == 422
    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 404
    assert [row['id'] for row in client.get('/api/admin/users').json()] == [admin['id']]
    assert store.account_for(user_cookie) is None
    assert client.post('/api/auth/login', json={
        'username': user['username'], 'password': 'only-for-contract-tests-67890',
    }).status_code == 401

    store.record_usage(user_id, 'fixture', 1, 1)  # A request completed after deletion.
    with store.connect() as db:
        for table in ('history', 'sessions', 'chatgpt_connections', 'chatgpt_attempts', 'usage'):
            assert db.execute(f'SELECT 1 FROM {table} WHERE user_id=?', (user_id,)).fetchone() is None
        assert db.execute('SELECT user_id FROM usage').fetchone()[0] == admin['id']


def test_lockout_and_password_revocation(users):
    store, client, admin, user = users
    for _ in range(5):
        assert client.post('/api/auth/login', json={'username': 'test-user', 'password': 'incorrect'}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'test-user', 'password': 'incorrect'}).status_code == 429
    login(client)
    old_cookie = client.cookies.get(accounts.COOKIE)
    assert client.post('/api/auth/password', json={'current_password': 'only-for-contract-tests-12345', 'new_password': 'new-contract-test-password-456'}).status_code == 200
    assert store.account_for(old_cookie) is None
    assert client.get('/api/admin/users').status_code == 200
    assert client.patch('/api/admin/users/' + admin['id'], json={'role': 'user'}).status_code == 422
    assert client.patch('/api/admin/users/' + user['id'], json={'active': False}).status_code == 200


def test_no_connection_is_not_ready_and_shared_key_configuration_is_retired(users):
    store, client, *_ = users
    login(client)
    assert client.post('/api/translate', json={'text':'Hello there','source':'en','target':'vi'}).status_code == 409
    assert client.put('/api/admin/provider', json={'model':'unused','api_key':'not-used'}).status_code == 410
    assert client.get('/api/admin/usage').json() == []


def test_history_and_pdf_are_owned_by_user(users):
    store, client, admin, user = users
    login(client)
    assert client.post('/api/history', json={'input': 'hello', 'output': 'test response', 'source': 'en', 'target': 'vi'}).status_code == 200
    entry = client.get('/api/history').json()[0]
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    stream = io.BytesIO(); writer.write(stream)
    SESSIONS['owned-test'] = {'id': 'owned-test', 'owner_id': admin['id'], 'expires': time.monotonic() + 60,
        'pages': [], 'output_pdf': stream.getvalue(), 'target': 'vi','output_revision':'fixture-revision','filename':'Tài liệu.pdf'}
    assert client.post('/api/documents/export', json={'session_id': 'owned-test', 'target': 'vi', 'automatic': True}).content == stream.getvalue()
    link='/api/documents/owned-test/download?revision=fixture-revision'
    native=client.get(link)
    assert native.status_code==200 and native.content==stream.getvalue()
    assert "filename*=UTF-8''T%C3%A0i%20li%E1%BB%87u-dich.pdf" in native.headers['content-disposition']
    assert client.get(link.replace('fixture-revision','stale-revision')).status_code==409
    client.post('/api/auth/logout'); login(client, 'user')
    assert client.get(link).status_code==404
    assert client.get('/api/history').json() == []
    assert client.delete('/api/history/' + entry['id']).status_code == 200
    assert len(store.history(admin['id'])) == 1
    assert client.post('/api/documents/export', json={'session_id': 'owned-test', 'target': 'vi', 'automatic': True}).status_code == 404
    with store.connect() as db:
        db.execute('UPDATE sessions SET expires=0')
    assert client.get('/api/history').status_code == 401


def test_admin_directory_lists_all_roles_and_locked_accounts_without_secrets(users):
    from types import SimpleNamespace
    store,client,admin,user=users
    second=store.create_user('other-admin','directory-test-password-123','admin')
    locked=store.create_user('locked-user','directory-test-password-456')
    store.update_user(locked['id'],{'active':False},admin['id'])
    store.new_session(user['id']);store.new_session(user['id'])
    expired=store.new_session(user['id'])
    with store.connect() as db:
        db.execute('UPDATE sessions SET expires=0 WHERE token_hash=?',(hashlib.sha256(expired.encode()).hexdigest(),))
    store.add_history(user['id'],SimpleNamespace(input='private fixture source',output='private fixture output',source='en',target='vi'))
    login(client)
    response=client.get('/api/admin/users');assert response.status_code==200
    listed={row['id']:row for row in response.json()}
    assert set(listed)=={admin['id'],user['id'],second['id'],locked['id']}
    assert not listed[locked['id']]['active'] and listed[second['id']]['role']=='admin'
    assert listed[user['id']]['active_sessions']==2 and listed[user['id']]['history_count']==1
    assert all(secret not in response.text for secret in ('password','token','private fixture','credentials'))


def test_admin_can_create_rename_reset_promote_lock_and_unlock(users):
    store,client,admin,user=users;login(client)
    created=client.post('/api/admin/users',json={'username':'created-user','password':'initial-fixture-password-123','role':'user'})
    assert created.status_code==200,created.text
    target=created.json();old_token=store.new_session(target['id'])
    updated=client.patch('/api/admin/users/'+target['id'],json={'username':'renamed-user','password':'reset-fixture-password-456','role':'admin'})
    assert updated.status_code==200 and updated.json()['role']=='admin'
    assert store.account_for(old_token) is None
    assert client.post('/api/auth/login',json={'username':'created-user','password':'initial-fixture-password-123'}).status_code==401
    assert client.post('/api/auth/login',json={'username':'renamed-user','password':'reset-fixture-password-456'}).status_code==200
    assert client.get('/api/admin/users').status_code==200
    login(client)
    assert client.patch('/api/admin/users/'+target['id'],json={'active':False}).status_code==200
    assert client.post('/api/auth/login',json={'username':'renamed-user','password':'reset-fixture-password-456'}).status_code==401
    assert client.patch('/api/admin/users/'+target['id'],json={'active':True,'role':'user'}).status_code==200
    assert client.post('/api/auth/login',json={'username':'renamed-user','password':'reset-fixture-password-456'}).status_code==200
    assert client.get('/api/admin/users').status_code==403


def test_admin_revoke_sessions_is_scoped_and_preserves_user_data(users):
    from types import SimpleNamespace
    store,client,admin,user=users;login(client)
    admin_cookie=client.cookies.get(accounts.COOKIE)
    first=store.new_session(user['id']);second=store.new_session(user['id'])
    store.add_history(user['id'],SimpleNamespace(input='source fixture',output='output fixture',source='en',target='vi'))
    encrypted=store.cipher().encrypt(b'{"fixture":true}').decode()
    with store.connect() as db:
        db.execute('INSERT INTO chatgpt_connections VALUES(?,?,?,?,?,?)',(user['id'],'fixture-issuer','fixture-subject','fixture-client',encrypted,'fixture-model'))
    result=client.post('/api/admin/users/'+user['id']+'/sessions/revoke')
    assert result.status_code==200 and result.json()=={'revoked_sessions':2,'current_account_signed_out':False}
    assert store.account_for(first) is None and store.account_for(second) is None
    assert store.account_for(admin_cookie)['id']==admin['id']
    assert len(store.history(user['id']))==1
    with store.connect() as db:
        assert db.execute('SELECT credentials FROM chatgpt_connections WHERE user_id=?',(user['id'],)).fetchone()[0]==encrypted
    listed={row['id']:row for row in client.get('/api/admin/users').json()}
    assert listed[user['id']]['active_sessions']==0


def test_admin_can_revoke_own_sessions_without_disabling_admin(users):
    store,client,admin,user=users;login(client)
    token=client.cookies.get(accounts.COOKIE)
    response=client.post('/api/admin/users/'+admin['id']+'/sessions/revoke')
    assert response.status_code==200 and response.json()['current_account_signed_out']
    assert 'Max-Age=0' in response.headers['set-cookie']
    assert store.account_for(token) is None and client.get('/api/admin/users').status_code==401
    assert next(row for row in store.users() if row['id']==admin['id'])['active']
    login(client)
    assert client.get('/api/admin/users').status_code==200


def test_directory_and_session_controls_enforce_admin_boundary(users):
    store,client,admin,user=users
    assert client.post('/api/admin/users/'+user['id']+'/sessions/revoke').status_code==401
    login(client,'user')
    for target in (admin['id'],user['id']):
        assert client.post('/api/admin/users/'+target+'/sessions/revoke').status_code==403
    assert client.patch('/api/admin/users/'+admin['id'],json={'active':False}).status_code==403
    login(client)
    assert client.post('/api/admin/users/missing/sessions/revoke').status_code==404
    assert client.post('/api/admin/users/'+user['id']+'/sessions/revoke',headers={'X-Kun-Request':'0'}).status_code==403
    assert client.patch('/api/admin/users/'+admin['id'],json={'active':False}).status_code==422
    assert client.patch('/api/admin/users/'+admin['id'],json={'role':'user'}).status_code==422
