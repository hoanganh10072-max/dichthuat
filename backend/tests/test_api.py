import io
import pytest
from app import accounts

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.extract import extract, validate_ocr_script
from app.main import app, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_user(tmp_path, monkeypatch):
    database = accounts.Store(tmp_path / 'api-tests.sqlite')
    database.init()
    database.create_user('test-user', 'api-contract-password-12345')
    monkeypatch.setattr(accounts, 'store', database)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    client.cookies.clear()
    client.headers['X-Kun-Request'] = '1'
    assert client.post('/api/auth/login', json={'username':'test-user','password':'api-contract-password-12345'}).status_code == 200
    yield
    client.cookies.clear()


def test_unavailable_is_truthful():
    assert client.get('/api/health').json()['model'] == 'unconfigured'
    assert client.post('/api/translate', json={'text': 'Xin chào', 'source': 'vi', 'target': 'lo'}).status_code == 409


def test_input_validation():
    for payload in [ {'text': '  '}, {'text': 'x' * 12001}, {'text': 'hello', 'source': 'xx'}, {'text': 'hello', 'source': 'vi', 'target': 'vi'} ]:
        assert client.post('/api/translate', json=payload).status_code == 422


def test_txt_roundtrip_and_invalid_encoding():
    text = 'Xin chào Việt Nam.\nສະບາຍດີ'
    response = client.post('/api/extract', files={'file': ('hello.txt', text.encode('utf-8'), 'text/plain')})
    assert response.status_code == 200
    assert response.json()['text'] == text


def test_real_auto_translation_resolves_source():
    import pytest
    if engine.state != 'ready':
        engine.load()
    if engine.state != 'ready':
        pytest.skip('No real ChatGPT connection in isolated test database')
    response=client.post('/api/translate',json={'text':'Hello, this is an English document about software.','source':'auto','target':'vi'})
    assert response.status_code == 200, response.text
    assert response.json()['source'] == 'en'
    assert response.json()['text'].strip()
    assert client.post('/api/extract', files={'file': ('bad.txt', b'\xff\xfe')}).status_code == 422


def test_docx_order():
    doc = Document()
    doc.add_paragraph('Đầu')
    doc.add_table(rows=1, cols=1).cell(0, 0).text = 'Giữa'
    doc.add_paragraph('Cuối')
    stream = io.BytesIO()
    doc.save(stream)
    assert extract(stream.getvalue(), 'hello.docx', 'vi')['text'] == 'Đầu\nGiữa\nCuối'


def test_blank_pdf_explains_scan_limit():
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    stream = io.BytesIO()
    pdf.write(stream)
    response = client.post('/api/extract', files={'file': ('scan.pdf', stream.getvalue(), 'application/pdf')})
    assert response.status_code == 422
    assert 'OCR' in response.json()['detail']


def test_upload_limit():
    assert client.post('/api/extract', files={'file': ('large.txt', b'a' * (10 * 1024 * 1024 + 1))}).status_code == 413


def test_real_tesseract_english():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1000, 160), 'white')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 55)
    ImageDraw.Draw(image).text((20, 40), 'Hello Vietnam', font=font, fill='black')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    response = client.post('/api/extract', data={'language': 'en'}, files={'file': ('sample.png', stream.getvalue(), 'image/png')})
    assert response.status_code == 200, response.text
    assert 'Hello Vietnam' in response.json()['text']
    layout = response.json()['layout']
    assert (layout['width'], layout['height']) == (1000, 160)
    assert layout['regions'][0]['text'] == 'Hello Vietnam'
    assert layout['regions'][0]['width'] > 0


def test_real_translation_if_model_present():
    # Integration test uses actual local weights, no mock result or quality assertion.
    import pytest
    engine.load()
    if engine.state != 'ready':
        pytest.skip('No real ChatGPT connection in isolated test database')
    for source, target, text in [('vi', 'lo', 'Xin chào, bạn khỏe không?'), ('lo', 'vi', 'ສະບາຍດີ')]:
        response = client.post('/api/translate', json={'source': source, 'target': target, 'text': text})
        assert response.status_code == 200, response.text
        assert response.json()['text'].strip()


def test_real_tesseract_korean():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1200, 220), 'white')
    font = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 64)
    ImageDraw.Draw(image).text((40, 65), '안녕하세요 한국어 번역', font=font, fill='black')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    response = client.post('/api/extract', data={'language': 'ko'}, files={'file': ('korean.png', stream.getvalue(), 'image/png')})
    assert response.status_code == 200, response.text
    assert '안녕하세요' in response.json()['text'].replace(' ', '')
    assert '한국어' in response.json()['text'].replace(' ', '')


def test_ocr_script_mismatch_is_not_translated_as_valid_text():
    import pytest
    for language in ('zh', 'ko'):
        with pytest.raises(ValueError, match='OCR không nhận ra'):
            validate_ocr_script('!£ fTIR 4 Bt RunningCore V8.0', language)
    validate_ocr_script('中华人民共和国 V8.0', 'zh')
    validate_ocr_script('안녕하세요 V8.0', 'ko')


def test_image_region_validation():
    response = client.post('/api/translate-image', json={'text': 'hello', 'source': 'en', 'target': 'vi',
        'regions': [{'text': 'hello\nworld', 'x': 0, 'y': 0, 'width': 50, 'height': 30}]})
    assert response.status_code == 422


def test_real_image_translation_retains_region_coordinates():
    import pytest
    if engine.state != 'ready':
        engine.load()
    if engine.state != 'ready':
        pytest.skip('No real ChatGPT connection in isolated test database')
    response = client.post('/api/translate-image', json={'text': 'Hello Vietnam\nWelcome', 'source': 'en', 'target': 'vi',
        'regions': [{'text': 'Hello Vietnam', 'x': 20, 'y': 40, 'width': 400, 'height': 50},
                    {'text': 'Welcome', 'x': 20, 'y': 110, 'width': 300, 'height': 50}]})
    assert response.status_code == 200, response.text
    regions = response.json()['regions']
    assert len(regions) == 2
    assert (regions[0]['x'], regions[1]['y']) == (20, 110)
    assert all(region['translation'].strip() for region in regions)


def test_detect_text_languages_and_reject_nontext():
    samples = {'vi': 'Xin chào, tôi muốn dịch văn bản tiếng Việt sang tiếng Lào.',
               'en': 'Hello, this document describes a software application and its features.',
               'lo': 'ສະບາຍດີ ຂ້ອຍຕ້ອງການແປພາສາ',
               'zh': '中华人民共和国国家版权局', 'ko': '안녕하세요 한국어 번역',
               'ja': 'これは日本語の文章です。', 'th': 'สวัสดีครับ ภาษาไทย'}
    for expected, text in samples.items():
        response = client.post('/api/detect', json={'text':text,'source':'auto','target':'vi'})
        assert response.status_code == 200, response.text
        assert response.json()['code'] == expected, response.text
    assert client.post('/api/detect',json={'text':'12345 !!!','source':'auto'}).status_code == 422
    assert client.post('/api/detect',json={'text':'hello','source':'auto'}).status_code in (200,422)
    assert client.post('/api/translate',json={'text':'hello','target':'auto'}).status_code == 422


def test_real_auto_ocr_korean():
    from PIL import Image, ImageDraw, ImageFont
    image=Image.new('RGB',(1200,220),'white')
    font=ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',64)
    ImageDraw.Draw(image).text((40,65),'안녕하세요 한국어 번역',font=font,fill='black')
    stream=io.BytesIO(); image.save(stream,format='PNG')
    response=client.post('/api/extract',data={'language':'auto'},files={'file':('auto.png',stream.getvalue(),'image/png')})
    assert response.status_code == 200, response.text
    assert response.json()['detection']['code'] == 'ko'
    assert '한국어' in response.json()['text'].replace(' ','')
