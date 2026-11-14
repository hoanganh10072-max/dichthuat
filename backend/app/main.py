import asyncio
import logging
import time
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .engine import Engine, LANGUAGES
from .extract import extract
from .detection import detect_language
from . import accounts
from .auth import AuthenticationMiddleware, auth_router
from .openai_engine import ProviderError
from .chatgpt import chatgpt, chatgpt_router, admin_chatgpt_router, start_callback_listener
from .account_context import current_account
from .service_messages import CONTACT_ADMIN, is_admin, access_message

engine = Engine()
extract_gate = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(app):
    accounts.store.init()
    callback = start_callback_listener()
    task = asyncio.create_task(run_in_threadpool(engine.load))
    cleanup = asyncio.create_task(prune_sessions())
    yield
    cleanup.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup
    await task
    if callback:
        await run_in_threadpool(callback.shutdown)
        callback.server_close()
        chatgpt.listener_ready = False


app = FastAPI(title='KUN GLOBAL Translation', version='2.0.0', lifespan=lifespan)
app.add_middleware(AuthenticationMiddleware)
app.include_router(auth_router(engine))
app.include_router(chatgpt_router())
app.include_router(admin_chatgpt_router())
from .documents import create_document_router, prune_sessions
app.include_router(create_document_router(engine))
from .word_routes import create_word_router
app.include_router(create_word_router(extract_gate))


class Translation(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    source: str = 'vi'
    target: str = 'lo'
    document: bool = False

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Nội dung không được để trống.')
        return value

    @field_validator('source', 'target')
    @classmethod
    def language(cls, value, info):
        if value not in LANGUAGES and not (info.field_name == 'source' and value == 'auto'):
            raise ValueError('Ngôn ngữ chưa được hỗ trợ.')
        return value


class ImageRegion(BaseModel):
    text: str = Field(min_length=1, max_length=2000, pattern=r'^[^\r\n]+$')
    x: int = Field(ge=0, le=16000000)
    y: int = Field(ge=0, le=16000000)
    width: int = Field(gt=0, le=16000000)
    height: int = Field(gt=0, le=16000000)


class ImageTranslation(Translation):
    regions: list[ImageRegion] = Field(min_length=1, max_length=300)


@app.post('/api/translate-image')
def translate_image(request: ImageTranslation):
    joined = '\n'.join(region.text for region in request.regions)
    if len(joined) > 12000:
        raise HTTPException(422, 'Văn bản ảnh vượt 12.000 ký tự.')
    # Reuse the exact same engine, limits and lock as plain-text translation.
    validated = Translation(text=joined, source=request.source, target=request.target, document=request.document)
    result = translate(validated)
    lines = result['text'].split('\n')
    if len(lines) != len(request.regions):
        raise HTTPException(422, 'Không ghép được bản dịch vào vùng chữ. Hãy dùng bản dịch văn bản.')
    return {**result, 'regions': [{**region.model_dump(), 'translation': line} for region, line in zip(request.regions, lines)]}


@app.get('/api/health')
def health():
    configured = engine.state == 'ready'
    if not is_admin():
        return {'status': 'ok', 'model': engine.state, 'engine': 'Dịch thuật đa ngôn ngữ',
                'message': 'Sẵn sàng dịch.' if configured else CONTACT_ADMIN}
    return {'status': 'ok', 'model': engine.state, 'engine': 'ChatGPT cá nhân',
            'message': 'Đã kết nối gói ChatGPT và chọn mô hình của tài khoản bạn.' if configured
                       else 'Mở ChatGPT của tôi để kết nối tài khoản và cấp quyền dùng gói ChatGPT.'}


@app.post('/api/translate-image-vision')
async def translate_image_vision(file: UploadFile = File(...), source: str = Form('auto'), target: str = Form('vi')):
    if source not in LANGUAGES and source!='auto' or target not in LANGUAGES:
        raise HTTPException(422,'Ngôn ngữ chưa được hỗ trợ.')
    try:
        data=await file.read(10*1024*1024+1)
    finally:
        await file.close()
    if len(data)>10*1024*1024:
        raise HTTPException(413,'File tối đa 10 MB.')
    if engine.state!='ready':
        raise HTTPException(409,access_message())
    from .image_translation import translate_image as translate_visual
    try:
        return await run_in_threadpool(translate_visual,engine,data,file.filename or '',source,target)
    except BlockingIOError as exc:
        raise HTTPException(429,str(exc),headers={'Retry-After':'3'})
    except ProviderError as exc:
        raise HTTPException(exc.status_code,str(exc))
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except OSError as exc:
        raise HTTPException(422,'Không đọc được ảnh PNG, JPG hoặc WEBP hợp lệ.') from exc


@app.get('/api/languages')
def languages():
    return [{'code': code, 'name': name} for code, name in LANGUAGES.items()]


@app.post('/api/detect')
def detect(request: Translation):
    try:
        return detect_language(request.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post('/api/translate')
def translate(request: Translation):
    if request.source == request.target:
        raise HTTPException(422, 'Hãy chọn hai ngôn ngữ khác nhau.')
    if engine.state != 'ready':
        raise HTTPException(409, access_message())
    detection = None
    source = request.source
    if source == 'auto':
        try:
            detection = detect_language(request.text)
            source = detection['code']
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    if source == request.target:
        if request.source == 'auto':
            return {'text': request.text, 'source': source, 'target': request.target, 'chunks': 0,
                    'elapsed_ms': 0, 'detection': detection, 'unchanged': True}
        raise HTTPException(422, 'Hãy chọn hai ngôn ngữ khác nhau.')
    started = time.monotonic()
    try:
        text, chunks = engine.translate(request.text, source, request.target, document=request.document)
    except BlockingIOError as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After': '3'})
    except ProviderError as exc:
        raise HTTPException(exc.status_code, str(exc))
    except Exception:
        logging.exception('Inference failed')
        raise HTTPException(500, 'Dịch không thành công. Hãy thử đoạn ngắn hơn hoặc kiểm tra log máy chủ.')
    return {'text': text, 'source': source, 'target': request.target, 'detection': detection,
            'chunks': chunks, 'elapsed_ms': round((time.monotonic() - started) * 1000)}


@app.post('/api/extract')
async def extract_file(file: UploadFile = File(...), language: str = Form('vi')):
    if language not in LANGUAGES and language != 'auto':
        raise HTTPException(422, 'Ngôn ngữ chưa được hỗ trợ.')
    try:
        data = await file.read(10 * 1024 * 1024 + 1)
    finally:
        await file.close()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, 'File tối đa 10 MB.')
    if extract_gate.locked():
        raise HTTPException(429, 'Máy chủ đang đọc file khác. Vui lòng thử lại.')
    async with extract_gate:
        try:
            return await run_in_threadpool(extract, data, file.filename or '', language)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            logging.exception('Extraction failed')
            raise HTTPException(422, 'Không đọc được file. Kiểm tra file hoặc dữ liệu ngôn ngữ Tesseract.')
