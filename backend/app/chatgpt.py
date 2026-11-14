"""Official SIWC public-client flow for a user-controlled local installation.

Credentials never pass to the web UI. The loopback callback is bound to the
existing app login, and each connection belongs to exactly one local user.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import accounts
from .openai_engine import ProviderError

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
LOOPBACK = {'localhost', '127.0.0.1'}


class ChatGPTConnections:
    def __init__(self):
        self.client_factory = httpx.Client
        self._metadata = None
        self._jwks = None
        self._metadata_until = self._jwks_until = 0
        self._guard = threading.RLock()
        self._locks = {}
        self.listener_ready = False

    def lock(self, user_id):
        with self._guard:
            return self._locks.setdefault(user_id, threading.RLock())

    def local_enabled(self):
        origin = urlsplit(os.getenv('APP_ORIGIN', 'http://localhost:8080'))
        return os.getenv('CHATGPT_LOCAL_ENABLED', 'true').lower() == 'true' and origin.hostname in LOOPBACK

    def callback_uri(self):
        return f'http://127.0.0.1:{int(os.getenv("CHATGPT_CALLBACK_PORT", "17653"))}/auth/callback'

    def _request(self, method, url, **kwargs):
        try:
            with self.client_factory(timeout=httpx.Timeout(30, connect=10), follow_redirects=False) as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError:
            raise ProviderError('Không kết nối được OpenAI. Kiểm tra mạng rồi thử lại.', 502)

    def metadata(self):
        with self._guard:
            if self._metadata is not None and self._metadata_until > time.time():
                return self._metadata
            response = self._request('GET', ISSUER + '/.well-known/openid-configuration')
            if response.status_code != 200:
                raise ProviderError('Chưa tải được cấu hình đăng nhập OpenAI.', 502)
            try:
                data = response.json()
                if data['issuer'] != ISSUER:
                    raise ValueError()
                for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                    value = urlsplit(data[key])
                    if value.scheme != 'https' or value.netloc != 'auth.openai.com' or value.username or value.password:
                        raise ValueError()
                if data.get('revocation_endpoint'):
                    value = urlsplit(data['revocation_endpoint'])
                    if value.scheme != 'https' or value.netloc != 'auth.openai.com':
                        raise ValueError()
            except (KeyError, ValueError, TypeError):
                raise ProviderError('Cấu hình đăng nhập OpenAI không hợp lệ.', 502)
            self._metadata, self._metadata_until = data, time.time() + 300
            return data

    def validate_identity(self, token, client_id, nonce=None, expected=None):
        try:
            if not isinstance(token, str) or len(token) > 65536:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get('alg') not in ('RS256', 'ES256') or not isinstance(header.get('kid'), str):
                raise ValueError()
            with self._guard:
                key = None
                for force in (False, True):
                    if force or self._jwks is None or self._jwks_until < time.time():
                        response = self._request('GET', self.metadata()['jwks_uri'])
                        if response.status_code != 200:
                            raise ValueError()
                        self._jwks, self._jwks_until = response.json()['keys'], time.time() + 300
                    key = next((item for item in self._jwks if item.get('kid') == header['kid']), None)
                    if key:
                        break
            if not key:
                raise ValueError()
            identity = jwt.decode(token, jwt.PyJWK.from_dict(key).key, algorithms=['RS256', 'ES256'],
                audience=client_id, issuer=self.metadata()['issuer'], leeway=5,
                options={'require': ['sub', 'exp', 'iat'] + (['nonce'] if nonce is not None else [])})
            if not isinstance(identity['sub'], str) or not identity['sub']:
                raise ValueError()
            if nonce is not None and (not isinstance(identity.get('nonce'), str) or not hmac.compare_digest(identity['nonce'], nonce)):
                raise ValueError()
            if expected is not None and (identity['iss'], identity['sub']) != expected:
                raise ValueError()
            return identity
        except ProviderError:
            raise
        except (jwt.PyJWTError, KeyError, ValueError, TypeError, StopIteration):
            raise ProviderError('Không xác minh được danh tính OpenAI. Hãy bắt đầu kết nối lại.', 400)

    def connection(self, user_id):
        with accounts.store.connect() as db:
            row = db.execute('SELECT * FROM chatgpt_connections WHERE user_id=?', (user_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result['tokens'] = json.loads(accounts.store.cipher().decrypt(row['credentials'].encode()))
        except Exception:
            raise ProviderError('Không đọc được kết nối ChatGPT đã lưu. Cần khôi phục master.key hoặc kết nối lại.', 503)
        return result

    def _save_tokens(self, user_id, tokens):
        encrypted = accounts.store.cipher().encrypt(json.dumps(tokens).encode()).decode()
        with accounts.store.connect() as db:
            db.execute('UPDATE chatgpt_connections SET credentials=? WHERE user_id=?', (encrypted, user_id))

    def status(self, user_id):
        connection = self.connection(user_id)
        tokens = connection['tokens'] if connection else {}
        connected = bool(tokens.get('access_token') or tokens.get('id_token'))
        sharing = connected and {PLAN_SCOPE, 'resource.invoke'}.issubset(tokens.get('scopes', []))
        renewable = tokens.get('expires_at', 0) > time.time() or bool(tokens.get('refresh_token'))
        return {'local_enabled': self.local_enabled(), 'callback_ready': self.listener_ready,
                'connected': connected, 'sharing': sharing, 'needs_reconnect': connected and not renewable,
                'ready': bool(self.local_enabled() and sharing and renewable and connection['model']),
                'email': tokens.get('email', ''), 'model': connection['model'] if connection else '',
                'message': 'Chỉ dùng trên máy riêng của user; chưa hỗ trợ máy chủ/VPS dùng chung.' if not self.local_enabled()
                           else 'Hãy kết nối ChatGPT của chính bạn và cấp quyền sử dụng gói để dịch.'}

    def attempt_authorized(self, db, user_id, actor_id, session_hash):
        # The initiating admin and the credential owner are separate identities.
        # Recheck both live accounts at start, callback and final token commit.
        return db.execute('''SELECT target.username FROM sessions s
            JOIN users actor ON actor.id=s.user_id JOIN users target ON target.id=?
            WHERE s.token_hash=? AND actor.id=? AND s.expires>?
            AND actor.active=1 AND target.active=1
            AND (actor.id=target.id OR actor.role='admin')''',
            (user_id, session_hash, actor_id, int(time.time()))).fetchone()

    def start(self, user_id, app_cookie, hostname, *, actor_id=None, expected_email=''):
        if not self.local_enabled() or hostname not in LOOPBACK:
            raise ProviderError('Luồng này chỉ dành cho app chạy local trên máy của bạn.', 409)
        if not self.listener_ready:
            raise ProviderError('Cổng nhận đăng nhập ChatGPT chưa sẵn sàng. Kiểm tra cổng callback và khởi động lại app.', 503)
        actor_id = actor_id or user_id
        session_hash = hashlib.sha256(app_cookie.encode()).hexdigest()
        expected_email = expected_email.strip().casefold()
        with accounts.store.connect() as db:
            if not self.attempt_authorized(db, user_id, actor_id, session_hash):
                raise ProviderError('Không có quyền kết nối cho user này hoặc tài khoản đã bị khóa.', 403)
        metadata = self.metadata()
        state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        connection = self.connection(user_id)
        client_id = connection['client_id'] if connection else 'dynamic_agent_client'
        pending = {'nonce': nonce, 'verifier': verifier, 'redirect_uri': self.callback_uri(),
                   'client_id': client_id, 'issuer': metadata['issuer'],
                   'expected_email': expected_email,
                   'expected_subject': connection['subject'] if connection else None}
        with accounts.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self.attempt_authorized(db, user_id, actor_id, session_hash):
                raise ProviderError('Quyền kết nối đã thay đổi. Đăng nhập và thử lại.', 403)
            db.execute('DELETE FROM chatgpt_attempts WHERE expires<?', (int(time.time()),))
            db.execute('DELETE FROM chatgpt_attempts WHERE user_id=?', (user_id,))
            host = db.execute("SELECT value FROM settings WHERE key='chatgpt_host_id'").fetchone()
            host_id = host['value'] if host else 'urn:uuid:' + str(uuid.uuid4())
            if not host:
                db.execute('INSERT INTO settings VALUES(?,?)', ('chatgpt_host_id', host_id))
            encrypted = accounts.store.cipher().encrypt(json.dumps(pending).encode()).decode()
            db.execute('INSERT INTO chatgpt_attempts(state_hash,user_id,actor_id,session_hash,payload,expires) VALUES(?,?,?,?,?,?)',
                (hashlib.sha256(state.encode()).hexdigest(), user_id, actor_id, session_hash, encrypted, int(time.time()) + 600))
        params = {'client_id': client_id, 'ext_agent_host_id': host_id, 'response_type': 'code',
                  'redirect_uri': pending['redirect_uri'], 'scope': SCOPES, 'resource': RESOURCE,
                  'state': state, 'nonce': nonce, 'code_challenge_method': 'S256', 'code_challenge': challenge}
        if not connection:
            params['agent_name_hint'] = 'KUN GLOBAL'
        return {'authorization_url': metadata['authorization_endpoint'] + '?' + urlencode(params)}

    def callback(self, params):
        state = params.get('state', '')
        if not isinstance(state, str) or not 20 <= len(state) <= 256:
            raise ProviderError('Phiên đăng nhập không hợp lệ hoặc đã hết hạn.', 400)
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        with accounts.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM chatgpt_attempts WHERE state_hash=? AND status=? AND expires>?',
                (state_hash, 'pending', int(time.time()))).fetchone()
            if not row or not self.attempt_authorized(db, row['user_id'], row['actor_id'], row['session_hash']):
                raise ProviderError('Phiên app đã hết hạn hoặc callback đã dùng. Đăng nhập và kết nối lại.', 400)
            db.execute("UPDATE chatgpt_attempts SET status='exchanging' WHERE state_hash=?", (state_hash,))
        pending = json.loads(accounts.store.cipher().decrypt(row['payload'].encode()))
        try:
            if params.get('error'):
                raise ProviderError('Bạn đã hủy hoặc chưa cấp quyền kết nối ChatGPT.', 400)
            client_id = params.get('client_id') or pending['client_id']
            if client_id == 'dynamic_agent_client' or not isinstance(client_id, str) or len(client_id) > 256:
                raise ProviderError('OpenAI chưa cấp client ID cho kết nối này. Hãy thử lại từ đầu.', 400)
            if pending['client_id'] != 'dynamic_agent_client' and client_id != pending['client_id']:
                raise ProviderError('Client ID trả về không khớp kết nối đã chọn.', 400)
            code = params.get('code')
            if not isinstance(code, str) or not code or len(code) > 4096:
                raise ProviderError('Không nhận được mã đăng nhập hợp lệ.', 400)
            response = self._request('POST', self.metadata()['token_endpoint'], data={
                'grant_type': 'authorization_code', 'client_id': client_id, 'code': code,
                'code_verifier': pending['verifier'], 'redirect_uri': pending['redirect_uri'], 'resource': RESOURCE})
            if response.status_code != 200:
                raise ProviderError('OpenAI không chấp nhận mã đăng nhập. Hãy bắt đầu kết nối lại.', 400)
            data = response.json()
            expected = (pending['issuer'], pending['expected_subject']) if pending.get('expected_subject') else None
            identity = self.validate_identity(data.get('id_token'), client_id, pending['nonce'], expected)
            if pending.get('expected_email') and str(identity.get('email', '')).strip().casefold() != pending['expected_email']:
                raise ProviderError('Email ChatGPT không khớp user đã chọn. Chọn đúng tài khoản ChatGPT của user rồi kết nối lại.', 409)
            scopes = data.get('scope', '').split()
            if PLAN_SCOPE in scopes and not data.get('access_token'):
                raise ProviderError('OpenAI chưa cấp access token để sử dụng gói ChatGPT.', 400)
            tokens = {'access_token': data.get('access_token', ''), 'refresh_token': data.get('refresh_token', ''),
                'id_token': data['id_token'], 'scopes': scopes, 'expires_at': time.time() + int(data.get('expires_in', 0)),
                'email': identity.get('email', ''), 'issuer': identity['iss'], 'subject': identity['sub']}
            encrypted = accounts.store.cipher().encrypt(json.dumps(tokens).encode()).decode()
            with self.lock(row['user_id']), accounts.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                still_pending = db.execute('''SELECT 1 FROM chatgpt_attempts
                    WHERE state_hash=? AND status='exchanging' AND expires>?''',
                    (state_hash, int(time.time()))).fetchone()
                if not still_pending or not self.attempt_authorized(db, row['user_id'], row['actor_id'], row['session_hash']):
                    raise ProviderError('Phiên app đã hết hạn trong lúc đăng nhập. Kết nối lại từ app.', 400)
                try:
                    db.execute('''INSERT INTO chatgpt_connections(user_id,issuer,subject,client_id,credentials,model)
                        VALUES(?,?,?,?,?,'') ON CONFLICT(user_id) DO UPDATE SET issuer=excluded.issuer,
                        subject=excluded.subject,client_id=excluded.client_id,credentials=excluded.credentials,model='' ''',
                        (row['user_id'], identity['iss'], identity['sub'], client_id, encrypted))
                except sqlite3.IntegrityError:
                    raise ProviderError('Tài khoản ChatGPT này đã gắn với user khác. Hãy kết nối tài khoản riêng.', 409)
                db.execute("UPDATE chatgpt_attempts SET status='completed',payload='' WHERE state_hash=?", (state_hash,))
            return 'connected'
        except ProviderError as exc:
            with accounts.store.connect() as db:
                db.execute("UPDATE chatgpt_attempts SET status='failed',message=?,payload='' WHERE state_hash=?", (str(exc), state_hash))
            raise
        except (ValueError, KeyError, TypeError):
            with accounts.store.connect() as db:
                db.execute("UPDATE chatgpt_attempts SET status='failed',message=?,payload='' WHERE state_hash=?",
                           ('Phản hồi đăng nhập không hợp lệ.', state_hash))
            raise ProviderError('Phản hồi đăng nhập OpenAI không hợp lệ. Kết nối lại từ app.', 400)

    def credentials(self, user_id):
        if not self.local_enabled():
            raise ProviderError('ChatGPT cá nhân chỉ được dùng trên máy riêng của user trong bản này.', 409)
        with self.lock(user_id):
            connection = self.connection(user_id)
            if not connection or not {PLAN_SCOPE, 'resource.invoke'}.issubset(connection['tokens'].get('scopes', [])):
                raise ProviderError('Hãy kết nối ChatGPT của bạn và cấp quyền sử dụng gói trước khi dịch.', 409)
            tokens = connection['tokens']
            if tokens.get('access_token') and tokens.get('expires_at', 0) > time.time() + 60:
                return connection
            if not tokens.get('refresh_token'):
                raise ProviderError('Kết nối ChatGPT đã hết hạn. Hãy kết nối lại.', 409)
            response = self._request('POST', self.metadata()['token_endpoint'], data={'grant_type': 'refresh_token',
                'client_id': connection['client_id'], 'refresh_token': tokens['refresh_token'], 'resource': RESOURCE})
            if response.status_code in (400, 401, 403):
                self._save_tokens(user_id, {**tokens, 'access_token': '', 'refresh_token': '', 'expires_at': 0})
                raise ProviderError('Quyền ChatGPT đã hết hạn hoặc bị thu hồi. Hãy kết nối lại.', 409)
            if response.status_code != 200:
                raise ProviderError('Chưa gia hạn được kết nối ChatGPT. Vui lòng thử lại sau.', 502)
            try:
                result = response.json()
                if not result.get('access_token'):
                    raise ValueError()
                if result.get('id_token'):
                    self.validate_identity(result['id_token'], connection['client_id'], expected=(connection['issuer'], connection['subject']))
                scopes = result['scope'].split() if 'scope' in result else tokens['scopes']
                tokens = {**tokens, 'access_token': result['access_token'], 'refresh_token': result.get('refresh_token', tokens['refresh_token']),
                    'id_token': result.get('id_token', tokens['id_token']), 'scopes': scopes,
                    'expires_at': time.time() + int(result.get('expires_in', 0))}
                self._save_tokens(user_id, tokens)
                if not {PLAN_SCOPE, 'resource.invoke'}.issubset(scopes):
                    raise ProviderError('Kết nối không còn quyền dùng gói ChatGPT. Cấp quyền lại để dịch.', 409)
                return {**connection, 'tokens': tokens}
            except (ValueError, TypeError, KeyError):
                raise ProviderError('Phản hồi gia hạn ChatGPT không hợp lệ.', 502)

    def models(self, user_id):
        connection = self.credentials(user_id)
        response = self._request('GET', RESOURCE + '/models', headers={'Authorization': 'Bearer ' + connection['tokens']['access_token']})
        if response.status_code in (401, 403):
            raise ProviderError('Chưa có quyền đọc mô hình của gói ChatGPT. Kiểm tra gói hoặc kết nối lại.', 409)
        if response.status_code != 200:
            raise ProviderError('Chưa tải được mô hình ChatGPT của tài khoản này.', 502)
        try:
            models = [{'slug': item['slug'], 'display_name': item['display_name']} for item in response.json()['models']
                if item.get('visibility') == 'list' and isinstance(item.get('slug'), str) and isinstance(item.get('display_name'), str)]
        except (ValueError, KeyError, TypeError):
            raise ProviderError('Danh sách mô hình ChatGPT không hợp lệ.', 502)
        if not models:
            raise ProviderError('Gói ChatGPT này chưa có mô hình khả dụng cho ứng dụng.', 403)
        if connection['model'] not in [item['slug'] for item in models]:
            with accounts.store.connect() as db:
                db.execute('UPDATE chatgpt_connections SET model=? WHERE user_id=?', (models[0]['slug'], user_id))
        return models

    def choose_model(self, user_id, model):
        if model not in [item['slug'] for item in self.models(user_id)]:
            raise ProviderError('Mô hình không thuộc danh sách khả dụng của tài khoản này.', 422)
        with accounts.store.connect() as db:
            db.execute('UPDATE chatgpt_connections SET model=? WHERE user_id=?', (model, user_id))

    def disconnect(self, user_id):
        with self.lock(user_id):
            connection = self.connection(user_id)
            if not connection:
                with accounts.store.connect() as db:
                    db.execute('DELETE FROM chatgpt_attempts WHERE user_id=?', (user_id,))
                return {'revoked': True}
            tokens = connection['tokens']
            revoked = not bool(tokens.get('refresh_token'))
            try:
                if tokens.get('refresh_token'):
                    endpoint = self.metadata().get('revocation_endpoint')
                    if endpoint:
                        response = self._request('POST', endpoint, data={'token': tokens['refresh_token'],
                            'token_type_hint': 'refresh_token', 'client_id': connection['client_id']})
                        revoked = response.status_code == 200
            except ProviderError:
                revoked = False
            self._save_tokens(user_id, {key: tokens[key] for key in ('email', 'issuer', 'subject') if key in tokens})
            with accounts.store.connect() as db:
                db.execute("UPDATE chatgpt_connections SET model='' WHERE user_id=?", (user_id,))
                db.execute('DELETE FROM chatgpt_attempts WHERE user_id=?', (user_id,))
            return {'revoked': revoked, 'message': 'Đã ngắt kết nối ChatGPT.' if revoked else
                'Đã xóa token trên máy; chưa xác nhận thu hồi ở OpenAI. Hãy ngắt app trong ChatGPT Settings → Usage.'}


chatgpt = ChatGPTConnections()


def start_callback_listener():
    if not chatgpt.local_enabled():
        return None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth authorization codes and state must not enter access logs.

        def do_GET(self):
            expected_host = urlsplit(chatgpt.callback_uri()).netloc
            if self.headers.get('Host') != expected_host or len(self.path) > 16384 or urlsplit(self.path).path != '/auth/callback':
                self.send_error(400, 'Invalid local callback')
                return
            values = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            try:
                if any(len(items) != 1 for items in values.values()):
                    raise ProviderError('Callback chứa tham số trùng lặp.', 400)
                chatgpt.callback({key: items[0] for key, items in values.items()})
                outcome = 'connected'
            except Exception:
                outcome = 'failed'
            # Restore the selected user from the server-side attempt, never a
            # user-supplied target in the OAuth callback query string.
            return_params = {'chatgpt': outcome}
            state = values.get('state', [''])[0]
            with accounts.store.connect() as db:
                row = db.execute('SELECT user_id,actor_id FROM chatgpt_attempts WHERE state_hash=?',
                    (hashlib.sha256(state.encode()).hexdigest(),)).fetchone()
            if row and row['actor_id'] != row['user_id']:
                return_params['chatgpt_user'] = row['user_id']
            self.send_response(303)
            self.send_header('Location', os.getenv('APP_ORIGIN', 'http://localhost:8080').rstrip('/') + '/?' + urlencode(return_params))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', '0')
            self.end_headers()

    try:
        server = ThreadingHTTPServer((os.getenv('CHATGPT_CALLBACK_BIND', '127.0.0.1'), int(os.getenv('CHATGPT_CALLBACK_PORT', '17653'))), Handler)
        server.daemon_threads = True
    except OSError:
        chatgpt.listener_ready = False
        return None
    threading.Thread(target=server.serve_forever, daemon=True, name='chatgpt-loopback').start()
    chatgpt.listener_ready = True
    return server


class ModelSelection(BaseModel):
    model: str = Field(min_length=1, max_length=200)


def chatgpt_router():
    router = APIRouter(prefix='/api/chatgpt')

    def attempt(call):
        try:
            return call()
        except ProviderError as exc:
            raise HTTPException(exc.status_code, str(exc))

    @router.get('/status')
    def status(request: Request):
        result = chatgpt.status(request.state.account['id'])
        with accounts.store.connect() as db:
            row = db.execute('SELECT status,message FROM chatgpt_attempts WHERE user_id=? AND expires>?',
                (request.state.account['id'], int(time.time()))).fetchone()
        result['attempt'] = dict(row) if row else None
        return result

    @router.post('/connect')
    def connect(request: Request):
        return attempt(lambda: chatgpt.start(request.state.account['id'], request.cookies.get(accounts.COOKIE, ''), request.url.hostname))

    @router.get('/models')
    def models(request: Request):
        return attempt(lambda: chatgpt.models(request.state.account['id']))

    @router.put('/model')
    def model(body: ModelSelection, request: Request):
        attempt(lambda: chatgpt.choose_model(request.state.account['id'], body.model))
        return chatgpt.status(request.state.account['id'])

    @router.post('/disconnect')
    def disconnect(request: Request):
        return attempt(lambda: chatgpt.disconnect(request.state.account['id']))

    return router


class AssistedConnection(BaseModel):
    expected_email: str | None = Field(default=None, min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def admin_chatgpt_router():
    router = APIRouter(prefix='/api/admin/users/{user_id}/chatgpt')

    def target(user_id, request):
        if request.state.account['role'] != 'admin':
            raise HTTPException(403, 'Chỉ admin có quyền hỗ trợ kết nối.')
        with accounts.store.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Không tìm thấy user.')
        return accounts.public_user(row)

    def attempt(call):
        try:
            return call()
        except ProviderError as exc:
            raise HTTPException(exc.status_code, str(exc))

    @router.get('')
    def status(user_id: str, request: Request):
        user = target(user_id, request)
        result = attempt(lambda: chatgpt.status(user_id))
        with accounts.store.connect() as db:
            row = db.execute('SELECT status,message FROM chatgpt_attempts WHERE user_id=? AND actor_id=? AND expires>?',
                (user_id, request.state.account['id'], int(time.time()))).fetchone()
        return {**result, 'user': user, 'attempt': dict(row) if row else None}

    @router.post('/connect')
    def connect(user_id: str, request: Request, body: AssistedConnection | None = None):
        target(user_id, request)
        return attempt(lambda: chatgpt.start(user_id, request.cookies.get(accounts.COOKIE, ''), request.url.hostname,
            actor_id=request.state.account['id'], expected_email=(body.expected_email or '') if body else ''))

    @router.get('/models')
    def models(user_id: str, request: Request):
        target(user_id, request)
        return attempt(lambda: chatgpt.models(user_id))

    @router.put('/model')
    def model(user_id: str, body: ModelSelection, request: Request):
        target(user_id, request)
        attempt(lambda: chatgpt.choose_model(user_id, body.model))
        return status(user_id, request)

    @router.post('/disconnect')
    def disconnect(user_id: str, request: Request):
        target(user_id, request)
        return attempt(lambda: chatgpt.disconnect(user_id))

    return router
