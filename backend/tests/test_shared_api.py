"""API migration contracts. No real keys, accounts or paid model calls."""
import base64
import io
import json
from zipfile import ZipFile

import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app import accounts
from app.main import app,engine
from app.chatgpt import chatgpt
from app.documents import SESSIONS
from test_accounts_openai import users,login
from test_original_document import pdf_fixture,output_fixture

KEY='sk-test-shared-api-secret-contract-only'


def respond(monkeypatch,output,status=200):
    bodies=[]
    def transport(request):
        assert str(request.url)=='https://api.openai.com/v1/responses'
        assert request.headers['authorization']=='Bearer '+KEY
        body=json.loads(request.content);bodies.append(body)
        assert body['model']=='fixture-api-model' and body['store'] is False and body['stream'] is True
        data={'type':'response.completed','response':{'status':'completed','usage':{'input_tokens':20,'output_tokens':15},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(output)}]}]}}
        return httpx.Response(status,headers={'content-type':'text/event-stream'},content='data: '+json.dumps(data)+'\n\n')
    monkeypatch.setattr(engine,'client_factory',lambda **kwargs:httpx.Client(transport=httpx.MockTransport(transport),**kwargs))
    def no_oauth(*a,**k):raise AssertionError('API requests must never use OAuth credentials')
    monkeypatch.setattr(chatgpt,'credentials',no_oauth)
    return bodies


def configure(client):
    result=client.put('/api/admin/provider',json={'model':'fixture-api-model','api_key':KEY})
    assert result.status_code==200,result.text
    assert result.json()=={'model':'fixture-api-model','configured':True,'key_source':'saved'}
    assert KEY not in result.text


def test_admin_key_encrypted_shared_for_users_and_never_returned(users,monkeypatch):
    store,client,admin,user=users;login(client)
    assert client.get('/api/admin/provider').json()['configured'] is False
    configure(client)
    with store.connect() as db:
        raw=db.execute("SELECT value FROM settings WHERE key='openai_key'").fetchone()['value']
        assert KEY not in raw and raw!=KEY
    bodies=respond(monkeypatch,{'translations':['Xin chào.']})
    assert client.post('/api/admin/provider/test').json()['ok'] is True
    login(client,'user')
    assert client.get('/api/health').json()['model']=='ready'
    assert client.get('/api/admin/provider').status_code==403
    assert client.put('/api/admin/provider',json={'model':'x'}).status_code==403
    assert client.post('/api/admin/provider/test').status_code==403
    response=client.post('/api/translate',json={'text':'Hello.','source':'en','target':'vi'})
    assert response.status_code==200 and response.json()['text']=='Xin chào.'
    assert len(bodies)==2 and 'name: faithful-translation' in bodies[1]['input'][0]['content'][0]['text']
    assert KEY not in client.get('/api/health').text
    login(client);assert {r['username'] for r in client.get('/api/admin/usage').json()}=={'test-admin','test-user'}
    assert client.put('/api/admin/provider',json={'model':'fixture-api-model','clear_key':True}).json()['configured'] is False
    assert client.get('/api/health').json()['model']=='unconfigured'


@pytest.mark.parametrize('status,expected',[(401,503),(403,503),(429,429),(400,502),(500,502)])
def test_api_errors_are_reported_without_key_or_result(users,monkeypatch,status,expected):
    _,client,*_=users;login(client);configure(client);respond(monkeypatch,{},status)
    r=client.post('/api/admin/provider/test');assert r.status_code==expected
    assert KEY not in r.text and 'ok' not in r.json()
    login(client,'user');r=client.post('/api/translate',json={'text':'Hello','source':'en','target':'vi'})
    assert r.status_code==expected and 'text' not in r.json() and KEY not in r.text
    message=r.json()['detail'].lower()
    assert not any(private in message for private in ('openai','chatgpt','api','hạn mức','gpt-'))
    if status==429:
        assert r.json()['detail']=='Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.'


def test_image_pdf_and_word_keep_original_inputs_with_shared_api(users,monkeypatch):
    _,client,*_=users;login(client);configure(client);login(client,'user')
    output={'has_text':True,'source':'en','regions':[{'text':'Hello','translation':'Xin chào','x':100,'y':100,'width':400,'height':80}],'notes':[]}
    bodies=respond(monkeypatch,output)
    stream=io.BytesIO();Image.new('RGB',(800,1000),'white').save(stream,format='PNG')
    response=client.post('/api/translate-image-vision',data={'source':'auto','target':'vi'},files={'file':('test.png',stream.getvalue(),'image/png')})
    assert response.status_code==200,response.text
    assert bodies[0]['input'][0]['content'][1]['type']=='input_image'
    data=pdf_fixture();prepared=client.post('/api/documents/prepare',data={'source':'auto'},files={'file':('test.pdf',data,'application/pdf')}).json()
    bodies=respond(monkeypatch,output_fixture())
    result=client.post('/api/documents/translate-original',json={'session_id':prepared['id'],'target':'vi','prompt':'Dịch toàn bộ và giữ khung bảng.'})
    assert result.status_code==200,result.text
    pdf=bodies[0]['input'][0]['content'][2]
    assert pdf['type']=='input_file' and base64.b64decode(pdf['file_data'].split(',',1)[1])==data
    word=client.post('/api/documents/export-word',json={'session_id':prepared['id'],'target':'vi'})
    assert word.status_code==200
    with ZipFile(io.BytesIO(word.content)) as z:assert 'Bản dịch kiểm thử trang 2' in z.read('word/document.xml').decode()
    assert len(bodies)==1


def test_validation_env_key_and_disabled_oauth(users,monkeypatch):
    _,client,*_=users;login(client)
    for key in ('bad','sk-test-key-with-newline\ninside-secret-123','é'*25):
        assert client.put('/api/admin/provider',json={'model':'fixture-model','api_key':key}).status_code==422
    assert client.put('/api/admin/provider',json={'model':'fixture-model','api_key':KEY,'clear_key':True}).status_code==422
    monkeypatch.setenv('OPENAI_API_KEY',KEY)
    assert client.get('/api/admin/provider').json()['key_source']=='environment'
    assert KEY not in client.get('/api/admin/provider').text
    monkeypatch.setenv('CHATGPT_LOCAL_ENABLED','false')
    assert client.post('/api/chatgpt/connect').status_code==410
