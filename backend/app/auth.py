import os

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from . import accounts
from .account_context import current_account


def cookie(response, token):
    response.set_cookie(accounts.COOKIE, token, httponly=True, samesite='lax',
        secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
        max_age=accounts.SESSION_SECONDS, path='/api')


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.url.path.startswith('/api/'):
            return await call_next(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            allowed = os.getenv('APP_ORIGIN', 'http://localhost:8080').rstrip('/')
            if request.headers.get('x-kun-request') != '1' or (origin and origin != allowed):
                return JSONResponse({'detail': 'Yêu cầu không hợp lệ. Tải lại trang và thử lại.'}, status_code=403)
        user = await run_in_threadpool(accounts.store.account_for, request.cookies.get(accounts.COOKIE))
        public = request.url.path in ('/api/health', '/api/auth/session', '/api/auth/login')
        if not public and not user:
            return JSONResponse({'detail': 'Vui lòng đăng nhập để tiếp tục.'}, status_code=401)
        if request.url.path.startswith('/api/admin/') and (not user or user['role'] != 'admin'):
            return JSONResponse({'detail': 'Chỉ quản trị viên có quyền thực hiện.'}, status_code=403)
        if ('/chatgpt/' in request.url.path or request.url.path.endswith('/chatgpt')) and os.getenv('CHATGPT_LOCAL_ENABLED','false').lower()!='true':
            return JSONResponse({'detail':'Ứng dụng đã chuyển sang API. Admin cấu hình trong Quản trị → OpenAI API.'},status_code=410)
        request.state.account = user
        token = current_account.set(user)
        try:
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            current_account.reset(token)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(max_length=256)


class NewUser(Login):
    role: str = 'user'


class UserChanges(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    role: str | None = None
    active: bool | None = None
    password: SecretStr | None = Field(default=None, min_length=12, max_length=256)


class PasswordChange(BaseModel):
    current_password: SecretStr = Field(max_length=256)
    new_password: SecretStr = Field(min_length=12, max_length=256)


class ProviderSettings(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    api_key: SecretStr | None = Field(default=None, max_length=512)
    clear_key: bool = False


class Profile(BaseModel):
    username: str = Field(min_length=3, max_length=64)


class HistoryEntry(BaseModel):
    input: str = Field(min_length=1, max_length=12000)
    output: str = Field(min_length=1, max_length=60000)
    source: str = Field(min_length=2, max_length=12)
    target: str = Field(min_length=2, max_length=12)


def auth_router(engine):
    router = APIRouter()

    @router.get('/api/auth/session')
    def session(request: Request):
        return {'user': request.state.account, 'setup_required': not bool(accounts.store.users())}

    @router.post('/api/auth/login')
    def login(body: Login, request: Request, response: Response):
        try:
            user, token = accounts.store.login(body.username, body.password.get_secret_value(), request.client.host)
        except BlockingIOError as exc:
            raise HTTPException(429, str(exc))
        except ValueError as exc:
            raise HTTPException(401, str(exc))
        cookie(response, token)
        return {'user': user}

    @router.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        accounts.store.logout(request.cookies.get(accounts.COOKIE, ''))
        response.delete_cookie(accounts.COOKIE, path='/api')
        return {'ok': True}

    @router.post('/api/auth/password')
    def change_password(body: PasswordChange, request: Request, response: Response):
        try:
            token = accounts.store.change_password(request.state.account['id'],
                body.current_password.get_secret_value(), body.new_password.get_secret_value())
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        cookie(response, token)
        return {'ok': True}

    @router.patch('/api/auth/profile')
    def profile(body: Profile, request: Request):
        try:
            return {'user': accounts.store.update_user(request.state.account['id'], {'username': body.username}, request.state.account['id'])}
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.get('/api/history')
    def history(request: Request):
        return accounts.store.history(request.state.account['id'])

    @router.post('/api/history')
    def add_history(body: HistoryEntry, request: Request):
        return accounts.store.add_history(request.state.account['id'], body)

    @router.delete('/api/history')
    def clear_history(request: Request):
        accounts.store.clear_history(request.state.account['id'])
        return {'ok': True}

    @router.delete('/api/history/{entry_id}')
    def delete_history(entry_id: str, request: Request):
        accounts.store.clear_history(request.state.account['id'], entry_id)
        return {'ok': True}

    @router.get('/api/admin/users')
    def users():
        return accounts.store.managed_users()

    @router.post('/api/admin/users/{user_id}/sessions/revoke')
    def revoke_user_sessions(user_id: str, request: Request, response: Response):
        try:
            count = accounts.store.revoke_sessions(user_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        signed_out = user_id == request.state.account['id']
        if signed_out:
            response.delete_cookie(accounts.COOKIE, path='/api')
        return {'revoked_sessions': count, 'current_account_signed_out': signed_out}

    @router.post('/api/admin/users')
    def create_user(body: NewUser):
        try:
            return accounts.store.create_user(body.username, body.password.get_secret_value(), body.role)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.delete('/api/admin/users/{user_id}', status_code=204)
    def delete_user(user_id: str):
        try:
            accounts.store.delete_user(user_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return Response(status_code=204)

    @router.patch('/api/admin/users/{user_id}')
    def update_user(user_id: str, body: UserChanges, request: Request):
        changes = body.model_dump(exclude_none=True)
        if body.password is not None:
            changes['password'] = body.password.get_secret_value()
        try:
            return accounts.store.update_user(user_id, changes, request.state.account['id'])
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.get('/api/admin/provider')
    def provider():
        config=accounts.store.provider()
        with accounts.store.connect() as db:
            saved=bool(db.execute("SELECT 1 FROM settings WHERE key='openai_key'").fetchone())
        return {'model':config['model'],'configured':bool(config['key']),
                'key_source':'saved' if saved else 'environment' if config['key'] else 'none'}

    @router.put('/api/admin/provider')
    def configure_provider(body:ProviderSettings):
        try:
            accounts.store.configure_provider(body.model,
                body.api_key.get_secret_value() if body.api_key is not None else None,body.clear_key)
            return provider()
        except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @router.post('/api/admin/provider/test')
    def test_provider():
        from .openai_engine import ProviderError
        from .engine import TranslationTooLong
        try:
            translated=engine.translate_segments(['Hello.'],'en','vi')
            return {'ok':True,'model':accounts.store.provider()['model'],'message':'Đã nhận phản hồi dịch hợp lệ từ OpenAI API.'}
        except ProviderError as exc:raise HTTPException(exc.status_code,str(exc)) from None
        except BlockingIOError as exc:raise HTTPException(429,str(exc)) from None
        except TranslationTooLong:raise HTTPException(422,'API chưa trả đầy đủ câu thử. Kiểm tra model và thử lại.') from None

    @router.get('/api/admin/usage')
    def usage():
        return accounts.store.usage()

    return router
