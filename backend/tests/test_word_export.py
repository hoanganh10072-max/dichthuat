import base64
import io
import json
import time
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest
from PIL import Image, ImageDraw
from docx import Document
from docx.shared import Mm
from fastapi.testclient import TestClient
from app import accounts
from app.main import app, engine
from app.documents import SESSIONS
from app.word_export import detect_tables, build_word, clean_label, MIME


@pytest.fixture
def user_client(monkeypatch):
    account=accounts.store.create_user('word-fixture-user','word-test-password-123')
    client=TestClient(app,headers={'X-Kun-Request':'1'})
    assert client.post('/api/auth/login',json={'username':account['username'],'password':'word-test-password-123'}).status_code==200
    def no_inference(*args,**kwargs):raise AssertionError('Word export must reuse existing translations without inference')
    monkeypatch.setattr(engine,'_response',no_inference)
    yield client,account
    SESSIONS.clear()


def fixture_image():
    image=Image.new('RGB',(320,420),'#fff18b');draw=ImageDraw.Draw(image)
    draw.rectangle((25,30,290,250),outline='black',width=2)
    draw.line((25,90,290,90),fill='black',width=2)
    draw.line((25,160,290,160),fill='black',width=2)
    draw.line((110,90,110,250),fill='black',width=2)
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def layout():
    return {'width':320,'height':420,'regions':[
        {'text':'Source title','translation':'BẢN DỊCH KIỂM THỬ','x':40,'y':45,'width':220,'height':22},
        {'text':'Name','translation':'Họ tên','x':35,'y':110,'width':65,'height':20},
        {'text':'NAME 001','translation':'NGUYEN AN 001','x':125,'y':110,'width':145,'height':20},
        {'text':'Footer','translation':'Nội dung cuối trang không bị bỏ sót.','x':30,'y':280,'width':260,'height':45},
    ]}


def text_of(data):
    with ZipFile(io.BytesIO(data)) as z:
        root=ET.fromstring(z.read('word/document.xml'))
    return '\n'.join(node.text or '' for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))


def test_white_editable_a4_with_native_merged_table(user_client):
    response=user_client[0].post('/api/export-word-image',data={'layout':json.dumps(layout())},files={'file':('form.png',fixture_image(),'image/png')})
    assert response.status_code==200,response.text
    assert response.headers['content-type']==MIME and response.headers['cache-control']=='no-store'
    document=Document(io.BytesIO(response.content))
    assert abs(document.sections[0].page_width-Mm(210))<1000
    assert abs(document.sections[0].page_height-Mm(297))<1000
    assert document.tables
    for r in layout()['regions']:assert r['translation'] in text_of(response.content)
    with ZipFile(io.BytesIO(response.content)) as z:
        assert not any(name.startswith('word/media/') for name in z.namelist()),'Do not embed the yellow source image'
        xml=z.read('word/document.xml').decode()
        assert 'gridSpan' in xml and 'FFFFFF' in xml
        assert 'w:color="000000"' in xml and 'w:background' not in xml


def test_detect_ruled_cells_and_preserve_all_unicode():
    page=layout();page['tables']=detect_tables(fixture_image(),320,420)
    assert len(page['tables'])==1 and len(page['tables'][0]['cells'])>=4
    page['regions'][0]['translation']='Tiếng Việt ພາສາລາວ 한국어 中文'
    assert page['regions'][0]['translation'] in text_of(build_word([page]))


@pytest.mark.parametrize('change',[{'width':500},{'regions':[]},{'width':float('nan')},
    {'regions':[{'text':'Source','translation':'','x':0,'y':0,'width':1,'height':1}]},
    {'regions':[{'text':'Source','translation':'Text','x':319,'y':0,'width':10,'height':1}]}])
def test_word_image_validation(user_client,change):
    response=user_client[0].post('/api/export-word-image',data={'layout':json.dumps({**layout(),**change})},files={'file':('form.png',fixture_image())})
    assert response.status_code==422 and not response.content.startswith(b'PK')


def test_word_requires_login_and_handles_corrupt_image(user_client):
    assert TestClient(app,headers={'X-Kun-Request':'1'}).post('/api/export-word',json={'text':'fixture'}).status_code==401
    response=user_client[0].post('/api/export-word-image',data={'layout':json.dumps(layout())},files={'file':('bad.png',b'not a PNG')})
    assert response.status_code==422


def test_plain_text_export_has_no_external_relationships(user_client):
    text='Dòng đầu\nTiếng Việt và 한국어\nhttps://example.invalid/path'
    response=user_client[0].post('/api/export-word',json={'text':text})
    assert response.status_code==200 and all(line in text_of(response.content) for line in text.splitlines())
    with ZipFile(io.BytesIO(response.content)) as z:
        for name in z.namelist():
            if name.endswith('.rels'):assert 'TargetMode="External"' not in z.read(name).decode()
    assert user_client[0].post('/api/export-word',json={'text':'   '}).status_code==422


def test_document_word_is_owned_complete_and_uses_latest_edits(user_client):
    client,account=user_client
    block={**layout()['regions'][0],'id':'page-0','keep':False}
    page={'width':320,'height':420,'preview':'data:image/png;base64,'+base64.b64encode(fixture_image()).decode(),'blocks':[block]}
    SESSIONS['word-session']={'owner_id':account['id'],'expires':time.monotonic()+100,'pages':[page],'target':'vi','output_pdf':b'%PDF-fixture'}
    body={'session_id':'word-session','target':'vi'}
    result=client.post('/api/documents/export-word',json=body)
    assert result.status_code==200 and block['translation'] in text_of(result.content)
    edited=client.post('/api/documents/export-word',json={**body,'edits':[{'id':'page-0','translation':'Bản đã chỉnh sửa mới nhất'}]})
    assert edited.status_code==200 and 'Bản đã chỉnh sửa mới nhất' in text_of(edited.content)
    assert client.post('/api/documents/export-word',json={**body,'target':'en'}).status_code==409
    accounts.store.create_user('word-other-user','word-other-password-123')
    client.post('/api/auth/login',json={'username':'word-other-user','password':'word-other-password-123'})
    assert client.post('/api/documents/export-word',json=body).status_code==404


def test_label_cleanup_only_collapses_repeated_phrase():
    assert clean_label('Quốc gia: Quốc gia / Quốc gia')=='Quốc gia:'
    assert clean_label('Đã được ký bởi: Đã được ký bởi Đã được ký bởi')=='Đã được ký bởi:'
    assert clean_label('NGUYEN ANH 001')=='NGUYEN ANH 001'
    assert clean_label('Nội dung chứng nhận không thay đổi.')=='Nội dung chứng nhận không thay đổi.'


def test_unchanged_repeated_person_name_is_not_collapsed():
    page=layout();page['tables']=detect_tables(fixture_image(),320,420)
    page['regions'][1].update(text='John John',translation='John John')
    assert 'John John' in text_of(build_word([page]))
