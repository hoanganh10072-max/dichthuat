"""Official SIWC protocol fixtures; no real login, subscription use or quality claim."""
import base64
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit, urlencode

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import accounts
from app.account_context import current_account
from app.chatgpt import chatgpt, ISSUER, RESOURCE, SCOPES
from app.engine import TranslationTooLong
from app.main import app, engine
from app.openai_engine import ProviderError


@pytest.fixture
def siwc(monkeypatch):
    # Historical OAuth contract fixtures explicitly inject the retired adapter.
    # Production defaults to the shared API engine and never falls back to it.
    from app.chatgpt_engine import ChatGPTEngine
    monkeypatch.setenv('CHATGPT_LOCAL_ENABLED','true')
    monkeypatch.setattr(type(engine),'state',ChatGPTEngine.state)
    monkeypatch.setattr(engine,'credentials',lambda user_id:chatgpt.credentials(user_id))
    monkeypatch.setattr(engine,'_response',ChatGPTEngine._response.__get__(engine,type(engine)))
    store = accounts.store
    admin = store.create_user('fixture-admin', 'fixture-password-admin-123', 'admin')
    user = store.create_user('fixture-user', 'fixture-password-user-456')
    client = TestClient(app, base_url='http://localhost:8080', headers={'X-Kun-Request':'1'})
    assert client.post('/api/auth/login', json={'username':'fixture-user','password':'fixture-password-user-456'}).status_code == 200
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())); jwk['kid']='fixture-key'
    state = {'calls':[], 'scopes':SCOPES, 'subject':'fixture-subject', 'claim_changes':{}}
    monkeypatch.setenv('APP_ORIGIN', 'http://localhost:8080')
    monkeypatch.setattr(chatgpt, '_metadata', None); monkeypatch.setattr(chatgpt, '_jwks', None)
    monkeypatch.setattr(chatgpt, 'listener_ready', True)
    def upstream(request):
        state['calls'].append(request)
        if request.url.path == '/.well-known/openid-configuration':
            return httpx.Response(200, json={'issuer':ISSUER,'authorization_endpoint':ISSUER+'/api/accounts/authorize',
                'token_endpoint':ISSUER+'/api/accounts/oauth/token','jwks_uri':ISSUER+'/.well-known/jwks.json',
                'revocation_endpoint':ISSUER+'/revoke'})
        if request.url.path == '/.well-known/jwks.json':
            return httpx.Response(200, json={'keys':[jwk]})
        if request.url.path == '/api/accounts/oauth/token':
            fields = {k:v[0] for k,v in parse_qs(request.content.decode()).items()}
            assert fields['resource'] == RESOURCE and 'client_secret' not in fields
            if fields['grant_type'] == 'refresh_token':
                assert fields['client_id']=='oaiapp_fixture' and fields['refresh_token']=='fixture-refresh'
                return httpx.Response(200, json={'access_token':'fixture-renewed','refresh_token':'fixture-rotated','expires_in':3600})
            assert fields['client_id']=='oaiapp_fixture'
            assert fields['redirect_uri']=='http://127.0.0.1:17653/auth/callback'
            challenge=base64.urlsafe_b64encode(hashlib.sha256(fields['code_verifier'].encode()).digest()).decode().rstrip('=')
            assert challenge==state['authorization']['code_challenge']
            claims={'iss':ISSUER,'aud':'oaiapp_fixture','sub':state['subject'],'iat':int(time.time()),
                'exp':int(time.time())+3600,'nonce':state['authorization']['nonce'],'email':'fixture@example.invalid'}
            claims.update(state['claim_changes'])
            signed=jwt.encode(claims,key,algorithm='RS256',headers={'kid':'fixture-key'})
            return httpx.Response(200, json={'access_token':'fixture-access','refresh_token':'fixture-refresh',
                'id_token':signed,'scope':state['scopes'],'expires_in':3600})
        if request.url.path == '/v1/models':
            assert request.headers['authorization'] in ('Bearer fixture-access','Bearer fixture-renewed')
            return httpx.Response(200,json={'models':[
                {'slug':'hidden-fixture','display_name':'Hidden','visibility':'hide'},
                {'slug':'fixture-model','display_name':'Fixture model','visibility':'list'},
                {'slug':'fixture-second','display_name':'Second fixture','visibility':'list'}]})
        if request.url.path == '/revoke':
            assert b'fixture-refresh' in request.content
            return httpx.Response(200)
        raise AssertionError(str(request.url))
    monkeypatch.setattr(chatgpt,'client_factory',lambda **kwargs:httpx.Client(transport=httpx.MockTransport(upstream),**kwargs))
    return store,client,admin,user,state


def begin(siwc):
    store,client,admin,user,state=siwc
    response=client.post('/api/chatgpt/connect');assert response.status_code==200,response.text
    url=urlsplit(response.json()['authorization_url'])
    assert url.scheme=='https' and url.netloc=='auth.openai.com'
    params={k:v[0] for k,v in parse_qs(url.query).items()};state['authorization']=params
    return params


def connected(siwc):
    params=begin(siwc)
    assert chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})=='connected'
    assert siwc[1].get('/api/chatgpt/models').status_code==200


def test_pkce_signed_identity_issued_client_and_private_catalog(siwc):
    store,client,admin,user,state=siwc
    params=begin(siwc)
    assert params['client_id']=='dynamic_agent_client' and params['agent_name_hint']=='KUN GLOBAL'
    assert params['scope']==SCOPES and params['resource']==RESOURCE and params['code_challenge_method']=='S256'
    assert params['ext_agent_host_id'].startswith('urn:uuid:')
    assert chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})=='connected'
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'replay','client_id':'oaiapp_fixture'})
    catalog=client.get('/api/chatgpt/models').json()
    assert [m['slug'] for m in catalog]==['fixture-model','fixture-second']
    status=client.get('/api/chatgpt/status')
    assert status.json()['ready'] and status.json()['model']=='fixture-model'
    assert all(secret not in status.text for secret in ('fixture-access','fixture-refresh','id_token'))
    assert b'fixture-access' not in store.path.read_bytes() and b'fixture-refresh' not in store.path.read_bytes()
    assert client.put('/api/chatgpt/model',json={'model':'invented'}).status_code==422
    assert client.put('/api/chatgpt/model',json={'model':'fixture-second'}).json()['model']=='fixture-second'
    again=begin(siwc)
    assert again['client_id']=='oaiapp_fixture' and 'agent_name_hint' not in again
    assert again['ext_agent_host_id']==params['ext_agent_host_id']
    assert again['state']!=params['state'] and again['nonce']!=params['nonce']
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'}).status_code==200
    assert not client.get('/api/chatgpt/status').json()['connected']
    assert client.get('/api/chatgpt/models').status_code==409


@pytest.mark.parametrize('changes',[{'nonce':'wrong'},{'iss':'https://evil.invalid'},{'aud':'wrong-client'},{'exp':1}])
def test_invalid_signed_identity_never_links(siwc,changes):
    params=begin(siwc);siwc[4]['claim_changes']=changes
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert not siwc[1].get('/api/chatgpt/status').json()['connected']


def test_invalid_state_client_and_revoked_app_session_stop_exchange(siwc):
    params=begin(siwc);state=siwc[4]
    with pytest.raises(ProviderError):chatgpt.callback({'state':'x'*50,'code':'fixture-code','client_id':'oaiapp_fixture'})
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code'})
    assert not any(r.url.path.endswith('/oauth/token') for r in state['calls'])
    params=begin(siwc);siwc[1].post('/api/auth/logout')
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})


@pytest.mark.parametrize('scopes',['openid profile email','openid profile email chatgpt.tokens.use.direct'])
def test_callback_query_cannot_grant_plan_usage(siwc,scopes):
    params=begin(siwc);siwc[4]['scopes']=scopes
    chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture','scope':SCOPES})
    status=siwc[1].get('/api/chatgpt/status').json()
    assert status['connected'] and not status['sharing'] and not status['ready']
    assert siwc[1].post('/api/translate',json={'text':'Hello','source':'en','target':'vi'}).status_code==409


def test_refresh_rotation_is_serial_and_disconnect_clears_private_tokens(siwc):
    connected(siwc);store,client,admin,user,state=siwc
    record=chatgpt.connection(user['id']);chatgpt._save_tokens(user['id'],{**record['tokens'],'expires_at':0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:chatgpt.credentials(user['id']),range(2)))
    assert all(r['tokens']['access_token']=='fixture-renewed' for r in results)
    refreshes=[r for r in state['calls'] if b'grant_type=refresh_token' in r.content]
    assert len(refreshes)==1 and chatgpt.connection(user['id'])['tokens']['refresh_token']=='fixture-rotated'
    # Revocation fixture expects the current token and confirms remote success.
    chatgpt._save_tokens(user['id'],{**results[0]['tokens'],'refresh_token':'fixture-refresh'})
    assert client.post('/api/chatgpt/disconnect').json()['revoked']
    assert not client.get('/api/chatgpt/status').json()['connected']
    assert 'access_token' not in chatgpt.connection(user['id'])['tokens']
    assert chatgpt.connection(user['id'])['client_id']=='oaiapp_fixture'


def stream_fixture(monkeypatch,translations=None,events=None,status=200,inspect_body=None,content_type='text/event-stream'):
    def respond(request):
        assert str(request.url)==RESOURCE+'/responses' and request.headers['authorization']=='Bearer fixture-access'
        body=json.loads(request.content)
        assert body['store'] is False and body['stream'] is True and isinstance(body['input'],list)
        forbidden={'max_output_tokens','temperature','top_p','metadata','user','previous_response_id','conversation'}
        assert not forbidden.intersection(body)
        assert body['model']=='fixture-model'
        if inspect_body:
            inspect_body(body)
        messages=events if events is not None else [{'type':'response.completed','response':{'status':'completed',
            'usage':{'input_tokens':20,'output_tokens':10},'output':[{'type':'message','content':[
                {'type':'output_text','text':json.dumps({'translations':translations})}]}]}}]
        content=''.join('data: '+json.dumps(event)+'\n\n' for event in messages)
        headers={'content-type':content_type} if content_type else {}
        return httpx.Response(status,headers=headers,content=content)
    monkeypatch.setattr(engine,'client_factory',lambda **kwargs:httpx.Client(transport=httpx.MockTransport(respond),**kwargs))


def test_completed_stream_preserves_lines_and_attributes_usage(siwc,monkeypatch):
    bodies=[]
    connected(siwc);stream_fixture(monkeypatch,['fixture one','fixture two'],inspect_body=bodies.append)
    result=siwc[1].post('/api/translate',json={'text':'first\n\nsecond','source':'en','target':'vi'})
    assert result.status_code==200,result.text
    assert result.json()['text']=='fixture one\n\nfixture two'
    assert siwc[0].usage()[0]['username']=='fixture-user' and siwc[0].usage()[0]['input_tokens']==20
    content=json.loads(bodies[0]['input'][0]['content'][0]['text'])
    assert 'name: faithful-translation' in content['translation_workflow']
    assert 'name: translation-review' in content['translation_workflow']
    assert content['source_language']=='en' and content['target_language']=='vi'


@pytest.mark.parametrize('events',[
    [],[{'type':'response.output_text.delta','delta':'partial'}],
    [{'type':'response.failed','response':{'error':{'code':'subscription_sharing_usage_limit_exceeded'}}}],
    [{'type':'response.completed','response':{'status':'completed','output':[]}}],
    [{'type':'response.completed','response':{'status':'incomplete'}}],
])
@pytest.mark.parametrize('content_type',[None,'text/event-stream'])
def test_partial_failed_or_missing_output_never_succeeds(siwc,monkeypatch,events,content_type):
    connected(siwc);stream_fixture(monkeypatch,events=events,content_type=content_type)
    response=siwc[1].post('/api/translate',json={'text':'first','source':'en','target':'vi'})
    assert response.status_code>=400 and 'text' not in response.json()


@pytest.mark.parametrize('content_type',[None,'Text/Event-Stream; charset=utf-8'])
def test_completed_stream_with_missing_or_case_insensitive_content_type(siwc,monkeypatch,content_type):
    connected(siwc)
    stream_fixture(monkeypatch,['fixture translation'],content_type=content_type)
    response=siwc[1].post('/api/translate',json={'text':'Source fixture','source':'en','target':'vi','document':True})
    assert response.status_code==200,response.text
    assert response.json()['text']=='fixture translation'


def test_completed_items_restore_empty_terminal_output(siwc,monkeypatch):
    connected(siwc)
    # Arrival order is not output order, and the terminal event omits output.
    message={'type':'message','status':'completed','content':[{'type':'output_text','text':json.dumps({'translations':['Bản dịch thật từ sự kiện hoàn tất']})}]}
    stream_fixture(monkeypatch,events=[
        {'type':'response.output_item.done','output_index':1,'item':message},
        {'type':'response.output_item.done','output_index':0,'item':{'type':'reasoning'}},
        {'type':'response.completed','response':{'status':'completed','output':[],'usage':{'input_tokens':20,'output_tokens':10}}}])
    result=siwc[1].post('/api/translate',json={'text':'Source fixture','source':'en','target':'vi'})
    assert result.status_code==200,result.text
    assert result.json()['text']=='Bản dịch thật từ sự kiện hoàn tất'
    assert siwc[0].usage()[0]['input_tokens']==20


@pytest.mark.parametrize('terminal',[None,'response.incomplete','response.failed','response.completed'])
def test_finished_items_require_complete_response_and_message(siwc,monkeypatch,terminal):
    connected(siwc)
    message={'type':'message','status':'in_progress' if terminal=='response.completed' else 'completed',
        'content':[{'type':'output_text','text':json.dumps({'translations':['Must not publish']})}]}
    messages=[{'type':'response.output_item.done','output_index':0,'item':message}]
    if terminal:messages.append({'type':terminal,'response':{'status':'completed','output':[]}})
    stream_fixture(monkeypatch,events=messages)
    result=siwc[1].post('/api/translate',json={'text':'Source fixture','source':'en','target':'vi'})
    assert result.status_code>=400 and 'text' not in result.json()


def test_explicit_non_stream_response_is_rejected(siwc,monkeypatch):
    connected(siwc)
    stream_fixture(monkeypatch,['fixture translation'],content_type='application/json')
    response=siwc[1].post('/api/translate',json={'text':'Source fixture','source':'en','target':'vi'})
    assert response.status_code==502 and 'text' not in response.json()


@pytest.mark.parametrize('path',['/api/translate','/api/translate-image'])
def test_uploaded_content_uses_translator_pro_workflow(siwc,monkeypatch,path):
    connected(siwc)
    bodies=[]
    stream_fixture(monkeypatch,['fixture translation'],inspect_body=bodies.append)
    payload={'text':'Source fixture','source':'en','target':'vi','document':True}
    if path.endswith('image'):
        payload['regions']=[{'text':'Source fixture','x':0,'y':0,'width':100,'height':20}]
    result=siwc[1].post(path,json=payload)
    assert result.status_code==200,result.text
    assert result.json()['text']=='fixture translation'
    content=json.loads(bodies[0]['input'][0]['content'][0]['text'])
    assert 'name: faithful-translation' in content['translation_workflow']
    assert 'name: translation-review' in content['translation_workflow']
    assert 'compare each draft translation with its source' in bodies[0]['instructions']
    assert content['segments']==['Source fixture']


def vision_fixture_image():
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(800,1000),'#fff4b0').save(stream,format='PNG')
    return stream.getvalue()


def vision_fixture_events(regions=None):
    # Protocol fixtures verify wiring/validation, never translation quality.
    payload={'has_text':True,'source':'es','notes':[],'regions':regions if regions is not None else [
        {'text':'Source protocol fixture','translation':'Translated protocol fixture','x':100,'y':200,'width':500,'height':50}]}
    return [{'type':'response.completed','response':{'status':'completed','usage':{'input_tokens':20,'output_tokens':10},
        'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(payload)}]}]}}]


def test_image_vision_sends_original_image_and_translator_pro(siwc,monkeypatch):
    import base64
    from PIL import Image
    connected(siwc);bodies=[]
    stream_fixture(monkeypatch,events=vision_fixture_events(),inspect_body=bodies.append)
    response=siwc[1].post('/api/translate-image-vision',data={'source':'auto','target':'vi'},
        files={'file':('source.png',vision_fixture_image(),'image/png')})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['method']=='vision-translator-pro' and result['source']=='es'
    assert result['source_text']=='Source protocol fixture'
    assert result['text']=='Translated protocol fixture'
    assert result['regions'][0]['x']==80 and result['regions'][0]['y']==200
    assert result['regions'][0]['width']==400 and result['regions'][0]['height']==50
    content=bodies[0]['input'][0]['content']
    assert content[1]['type']=='input_image' and content[1]['detail']=='high'
    encoded=content[1]['image_url'].split(',',1)[1]
    image=Image.open(io.BytesIO(base64.b64decode(encoded)))
    assert image.size==(800,1000) and image.getpixel((0,0))==(255,244,176)
    workflow=json.loads(content[0]['text'])['translation_workflow']
    for name in ('translation-router','faithful-translation','translation-review'):
        assert 'name: '+name in workflow
    assert 'Read the original image directly' in bodies[0]['instructions']
    assert 'source.png' not in json.dumps(bodies[0])


@pytest.mark.parametrize('regions',[
    [],[{'text':'source','translation':'fixture','x':900,'y':0,'width':200,'height':50}],
    [{'text':'source','translation':'','x':0,'y':0,'width':100,'height':50}],
    [{'text':'source','translation':'fixture','x':0,'y':0,'width':0,'height':50}],
])
def test_invalid_vision_output_is_not_published(siwc,monkeypatch,regions):
    connected(siwc);stream_fixture(monkeypatch,events=vision_fixture_events(regions))
    response=siwc[1].post('/api/translate-image-vision',data={'source':'auto','target':'vi'},
        files={'file':('source.png',vision_fixture_image(),'image/png')})
    assert response.status_code==502 and 'layout' not in response.json()


def test_vision_requires_access_and_valid_image(siwc,monkeypatch):
    response=siwc[1].post('/api/translate-image-vision',files={'file':('source.png',vision_fixture_image(),'image/png')})
    assert response.status_code==409 and 'admin' in response.json()['detail']
    connected(siwc)
    def no_response(*args,**kwargs):raise AssertionError('Invalid image must not call the model')
    monkeypatch.setattr(engine,'_response',no_response)
    response=siwc[1].post('/api/translate-image-vision',files={'file':('source.png',b'not an image','image/png')})
    assert response.status_code==422


def test_all_twenty_targets_reach_text_and_image_provider_requests(siwc,monkeypatch):
    from app.engine import LANGUAGES
    connected(siwc)
    assert len(LANGUAGES)==20
    for target in LANGUAGES:
        bodies=[]
        stream_fixture(monkeypatch,['Protocol fixture '+target],inspect_body=bodies.append)
        result=siwc[1].post('/api/translate',json={'text':'Source protocol fixture','source':'vi' if target=='en' else 'en','target':target})
        assert result.status_code==200,(target,result.text)
        assert json.loads(bodies[0]['input'][0]['content'][0]['text'])['target_language']==target
        bodies=[];stream_fixture(monkeypatch,events=vision_fixture_events(),inspect_body=bodies.append)
        result=siwc[1].post('/api/translate-image-vision',data={'source':'auto','target':target},files={'file':('fixture.png',vision_fixture_image(),'image/png')})
        assert result.status_code==200,(target,result.text)
        schema=bodies[0]['text']['format']['schema']
        assert set(schema['properties']['source']['enum'])==set(LANGUAGES)|{'unknown'}
        assert json.loads(bodies[0]['input'][0]['content'][0]['text'])['target_language']==LANGUAGES[target]


def test_pdf_complex_script_uses_real_word_and_retranslation_does_not_reuse_old_word(siwc,monkeypatch):
    from reportlab.pdfgen import canvas
    from app.documents import SESSIONS
    from zipfile import ZipFile
    connected(siwc);client=siwc[1]
    stream=io.BytesIO();c=canvas.Canvas(stream);c.drawString(60,730,'This document requires an accurate translation.');c.save()
    analyzed=client.post('/api/documents/analyze',data={'source':'en'},files={'file':('fixture.pdf',stream.getvalue(),'application/pdf')})
    assert analyzed.status_code==200,analyzed.text
    token=analyzed.json()['id']
    try:
        for target,output in [('ar','هذه وثيقة اختبار للبنية فقط'),('vi','Protocol fixture for updated target')]:
            stream_fixture(monkeypatch,[output])
            completed=client.post('/api/documents/complete',json={'session_id':token,'target':target})
            assert completed.status_code==200,completed.text
            if target=='ar':
                assert completed.json()['ready'] and completed.json()['pages']==[]
                assert completed.json()['document']['output_policy']['mode']=='a4'
                assert completed.json()['document']['download_url'] is None
            word=client.post('/api/documents/export-word',json={'session_id':token,'target':target})
            assert word.status_code==200,word.text
            with ZipFile(io.BytesIO(word.content)) as z:xml=z.read('word/document.xml').decode()
            assert output in xml
            if target=='vi':assert 'هذه وثيقة' not in xml
    finally:SESSIONS.clear()


@pytest.mark.parametrize('payload', [None, [], {'has_text':True,'source':'es','notes':[],'regions':['bad']},
    {'has_text':True,'source':'es','notes':[],'regions':[None]},
    {'has_text':False,'source':'es','notes':[],'regions':[]},
    {'has_text':True,'source':'es','notes':'not a list','regions':[]},
    {'has_text':True,'source':'es','notes':[],'regions':[{'text':'test','translation':'test','x':True,'y':0,'width':10,'height':10}]}])
def test_malformed_vision_payload_is_controlled_without_partial_result(siwc,monkeypatch,payload):
    connected(siwc)
    completed={'usage':{},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(payload)}]}]}
    monkeypatch.setattr(engine,'_response',lambda *args:completed)
    result=siwc[1].post('/api/translate-image-vision',files={'file':('source.png',vision_fixture_image(),'image/png')})
    assert result.status_code==502 and 'regions' not in result.json()
    assert engine.lock.acquire(False);engine.lock.release()


def test_no_legible_text_is_explained_without_fabricated_translation(siwc,monkeypatch):
    connected(siwc)
    completed={'usage':{},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(
        {'has_text':False,'source':'unknown','regions':[],'notes':[]})}]}]}
    monkeypatch.setattr(engine,'_response',lambda *args:completed)
    result=siwc[1].post('/api/translate-image-vision',files={'file':('blank.png',vision_fixture_image(),'image/png')})
    assert result.status_code==422 and 'Không tìm thấy chữ đọc được' in result.json()['detail']
    assert 'layout' not in result.json()


def test_image_limits_and_busy_request_do_not_start_model(siwc,monkeypatch):
    connected(siwc)
    def unexpected(*args):raise AssertionError('Invalid/busy requests must not start inference')
    monkeypatch.setattr(engine,'_response',unexpected)
    client=siwc[1]
    assert client.post('/api/translate-image-vision',files={'file':('large.png',b'x'*(10*1024*1024+1),'image/png')}).status_code==413
    assert client.post('/api/translate-image-vision',data={'target':'unsupported'},files={'file':('x.png',vision_fixture_image())}).status_code==422
    engine.lock.acquire()
    try:
        result=client.post('/api/translate-image-vision',files={'file':('x.png',vision_fixture_image())})
        assert result.status_code==429 and result.headers['Retry-After']=='3'
    finally:engine.lock.release()


@pytest.mark.parametrize('status,expected',[(401,409),(403,409),(429,429),(500,502)])
def test_provider_error_statuses(siwc,monkeypatch,status,expected):
    connected(siwc);stream_fixture(monkeypatch,status=status)
    response=siwc[1].post('/api/translate',json={'text':'first','source':'en','target':'vi'})
    assert response.status_code==expected,response.text


def test_pdf_retranslation_exports_latest_completed_result(siwc,monkeypatch):
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader
    from app.documents import SESSIONS
    connected(siwc);client=siwc[1]
    source=io.BytesIO();page=canvas.Canvas(source)
    page.drawString(70,720,'Documento de prueba.');page.save()
    response=client.post('/api/documents/analyze',data={'source':'es'},files={'file':('fixture.pdf',source.getvalue(),'application/pdf')})
    assert response.status_code==200,response.text
    document=response.json()
    previous_link=None
    for target in ('vi','fr'):
        bodies=[]
        fixture='Protocol fixture '+target;stream_fixture(monkeypatch,[fixture],inspect_body=bodies.append)
        result=client.post('/api/documents/complete',json={'session_id':document['id'],'target':target})
        assert result.status_code==200,result.text
        assert result.json()['ready']
        assert len(bodies)==1
        payload=json.loads(bodies[0]['input'][0]['content'][0]['text'])
        assert 'name: faithful-translation' in payload['translation_workflow']
        assert 'name: translation-router' in payload['translation_workflow']
        assert 'Preserve meaning, names, numbers, formatting, and register' in payload['translation_workflow']
        assert payload['segments']==[block['text'] for page in document['pages'] for block in page['blocks'] if not block['keep']]
        assert 'Translator Pro' in bodies[0]['instructions']
        output=client.post('/api/documents/export',json={'session_id':document['id'],'target':target,'automatic':True})
        assert output.status_code==200 and output.content.startswith(b'%PDF-')
        assert fixture in PdfReader(io.BytesIO(output.content)).pages[0].extract_text()
        link=result.json()['document']['download_url']
        download=client.get(link)
        assert download.status_code==200 and download.content==output.content
        assert download.headers['content-type']=='application/pdf'
        assert download.headers['content-disposition'].startswith('attachment;')
        assert client.get(link+'&inline=true').headers['content-disposition'].startswith('inline;')
        if previous_link:
            assert client.get(previous_link).status_code==409
        previous_link=link
    assert client.post('/api/documents/export',json={'session_id':document['id'],'target':'vi','automatic':True}).status_code==422
    block=document['pages'][0]['blocks'][0]
    preview=client.post('/api/documents/preview',json={'session_id':document['id'],'target':'fr','automatic':True,
        'edits':[{'id':block['id'],'translation':'Edited PDF fixture','keep':False}]})
    assert preview.status_code==200,preview.text
    assert client.get(previous_link).status_code==409
    edited=client.get(preview.json()['download_url'])
    assert 'Edited PDF fixture' in PdfReader(io.BytesIO(edited.content)).pages[0].extract_text()
    SESSIONS.clear()


def test_remote_origin_is_disabled(siwc,monkeypatch):
    monkeypatch.setenv('APP_ORIGIN','https://shared.example.invalid')
    assert not chatgpt.local_enabled()
    assert siwc[1].post('/api/chatgpt/connect').status_code==409


def test_same_chatgpt_identity_cannot_be_shared_between_app_users(siwc):
    connected(siwc);client=siwc[1]
    client.post('/api/auth/logout')
    client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'})
    params=begin(siwc)
    with pytest.raises(ProviderError,match='user khác'):
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert not client.get('/api/chatgpt/status').json()['connected']
    assert chatgpt.status(siwc[3]['id'])['ready']


def test_expired_pending_state_stops_before_token_exchange(siwc):
    params=begin(siwc)
    with siwc[0].connect() as db:db.execute('UPDATE chatgpt_attempts SET expires=0')
    with pytest.raises(ProviderError):
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert not any(r.url.path.endswith('/oauth/token') for r in siwc[4]['calls'])


def test_missing_segment_and_incomplete_terminal_event_are_not_translations(siwc,monkeypatch):
    connected(siwc);stream_fixture(monkeypatch,['only one'])
    result=siwc[1].post('/api/translate',json={'text':'first\nsecond','source':'en','target':'vi'})
    assert result.status_code>=400 and 'text' not in result.json()
    stream_fixture(monkeypatch,events=[{'type':'response.incomplete'}])
    token=current_account.set(siwc[3])
    try:
        with pytest.raises(TranslationTooLong):engine.translate('first','en','vi')
    finally:current_account.reset(token)


def test_revoked_refresh_requires_reconnect_and_failed_revocation_is_honest(siwc,monkeypatch):
    connected(siwc);user=siwc[3]
    tokens=chatgpt.connection(user['id'])['tokens']
    chatgpt._save_tokens(user['id'],{**tokens,'expires_at':0})
    def rejected(method,url,**kwargs):return httpx.Response(400)
    monkeypatch.setattr(chatgpt,'_request',rejected)
    with pytest.raises(ProviderError):chatgpt.credentials(user['id'])
    assert chatgpt.status(user['id'])['needs_reconnect']
    assert chatgpt.connection(user['id'])['tokens']['refresh_token']==''
    chatgpt._save_tokens(user['id'],tokens)
    result=chatgpt.disconnect(user['id'])
    assert not result['revoked'] and 'chưa xác nhận' in result['message']
    assert not chatgpt.status(user['id'])['connected']


def admin_begin(siwc, user_id=None, email='fixture@example.invalid'):
    client=siwc[1]
    assert client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'}).status_code==200
    user_id=user_id or siwc[3]['id']
    body={'json':{'expected_email':email}} if email is not None else {}
    response=client.post(f'/api/admin/users/{user_id}/chatgpt/connect',**body)
    assert response.status_code==200,response.text
    params={k:v[0] for k,v in parse_qs(urlsplit(response.json()['authorization_url']).query).items()}
    siwc[4]['authorization']=params
    return params


def test_admin_assists_user_without_changing_admin_connection(siwc,monkeypatch):
    store,client,admin,user,state=siwc
    params=admin_begin(siwc,email=None)
    assert params['agent_name_hint']=='KUN GLOBAL'
    with store.connect() as db:
        row=db.execute('SELECT * FROM chatgpt_attempts').fetchone()
        assert row['user_id']==user['id'] and row['actor_id']==admin['id']
    # A callback query cannot replace the server-side credential owner.
    chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture','user_id':admin['id']})
    prefix=f'/api/admin/users/{user["id"]}/chatgpt'
    assert client.get(prefix+'/models').status_code==200
    status=client.get(prefix)
    assert status.json()['ready'] and status.json()['user']['id']==user['id']
    assert all(value not in status.text for value in ('fixture-access','fixture-refresh','id_token'))
    assert not client.get('/api/chatgpt/status').json()['connected']
    assert client.put(prefix+'/model',json={'model':'fixture-second'}).json()['model']=='fixture-second'
    assert client.put(prefix+'/model',json={'model':'fixture-model'}).status_code==200
    # User can translate immediately without starting or completing OAuth.
    assert client.post('/api/auth/login',json={'username':'fixture-user','password':'fixture-password-user-456'}).status_code==200
    assert client.get('/api/health').json()['model']=='ready'
    stream_fixture(monkeypatch,['assisted fixture'])
    response=client.post('/api/translate',json={'text':'hello','source':'en','target':'vi'})
    assert response.status_code==200 and response.json()['text']=='assisted fixture'
    assert store.usage()[0]['username']=='fixture-user'


def test_admin_wrong_chatgpt_email_does_not_replace_valid_connection(siwc):
    connected(siwc);original=chatgpt.connection(siwc[3]['id'])
    params=admin_begin(siwc,email='another-owner@example.invalid')
    with pytest.raises(ProviderError,match='Email ChatGPT không khớp'):
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(siwc[3]['id'])==original
    result=siwc[1].get(f'/api/admin/users/{siwc[3]["id"]}/chatgpt').json()
    assert result['ready'] and result['attempt']['status']=='failed'


@pytest.mark.parametrize('action',['logout','demote','disable_target','delete_target'])
def test_assisted_callback_rechecks_actor_and_target(siwc,action):
    params=admin_begin(siwc);store,client,admin,user,state=siwc
    if action=='logout':client.post('/api/auth/logout')
    else:
        with store.connect() as db:
            if action=='demote':db.execute("UPDATE users SET role='user' WHERE id=?",(admin['id'],))
            elif action=='disable_target':db.execute('UPDATE users SET active=0 WHERE id=?',(user['id'],))
            else:db.execute('DELETE FROM users WHERE id=?',(user['id'],))
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert not any(r.url.path.endswith('/oauth/token') for r in state['calls'])
    assert chatgpt.connection(user['id']) is None


def test_assisted_callback_rechecks_permission_after_network_exchange(siwc,monkeypatch):
    params=admin_begin(siwc)
    original=chatgpt.validate_identity
    def validate(*args,**kwargs):
        identity=original(*args,**kwargs)
        with siwc[0].connect() as db:db.execute('UPDATE users SET active=0 WHERE id=?',(siwc[3]['id'],))
        return identity
    monkeypatch.setattr(chatgpt,'validate_identity',validate)
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(siwc[3]['id']) is None


def test_assisted_endpoints_require_admin_and_validate_target(siwc):
    client=siwc[1];prefix=f'/api/admin/users/{siwc[3]["id"]}/chatgpt'
    for method,path,body in [('GET',prefix,None),('GET',prefix+'/models',None),('PUT',prefix+'/model',{'model':'fixture-model'}),
        ('POST',prefix+'/connect',{'expected_email':'fixture@example.invalid'}),('POST',prefix+'/disconnect',None)]:
        assert client.request(method,path,json=body).status_code==403
    client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'})
    assert client.get('/api/admin/users/nonexistent/chatgpt').status_code==404
    assert client.post(prefix+'/connect',json={'expected_email':'invalid-email'}).status_code==422
    with siwc[0].connect() as db:db.execute('UPDATE users SET active=0 WHERE id=?',(siwc[3]['id'],))
    assert client.post(prefix+'/connect').status_code==403
    assert not siwc[4]['calls']


def test_cancelled_assisted_attempt_and_same_chatgpt_account_are_rejected(siwc):
    # Link one existing ChatGPT identity to the admin, then refuse it for user.
    client=siwc[1]
    client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'})
    connected(siwc)
    params=admin_begin(siwc)
    with pytest.raises(ProviderError,match='user khác'):
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(siwc[3]['id']) is None
    params=admin_begin(siwc)
    assert client.post(f'/api/admin/users/{siwc[3]["id"]}/chatgpt/disconnect').status_code==200
    before=len([r for r in siwc[4]['calls'] if r.url.path.endswith('/oauth/token')])
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert len([r for r in siwc[4]['calls'] if r.url.path.endswith('/oauth/token')])==before


def test_simultaneous_assisted_flows_keep_their_original_user(siwc):
    store,client,admin,user,state=siwc
    second=store.create_user('fixture-second-user','fixture-password-user-789')
    first_params=admin_begin(siwc)
    second_params=admin_begin(siwc,second['id'],email='second@example.invalid')
    for params,subject,email in [(first_params,'first-subject','fixture@example.invalid'),(second_params,'second-subject','second@example.invalid')]:
        state.update(authorization=params,subject=subject,claim_changes={'email':email})
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(user['id'])['subject']=='first-subject'
    assert chatgpt.connection(second['id'])['subject']=='second-subject'
    assert chatgpt.connection(admin['id']) is None


def test_old_attempt_schema_migrates_without_losing_accounts(siwc):
    store,client,admin,user,state=siwc
    with store.connect() as db:
        db.execute('ALTER TABLE chatgpt_attempts DROP COLUMN actor_id')
        db.execute('INSERT INTO chatgpt_attempts(state_hash,user_id,session_hash,payload,expires) VALUES(?,?,?,?,?)',
            ('legacy-state',user['id'],'old-session','encrypted-placeholder',0))
    store.init();store.init()
    with store.connect() as db:
        row=db.execute('SELECT * FROM chatgpt_attempts WHERE state_hash=?',('legacy-state',)).fetchone()
    assert row['actor_id']==user['id'] and row['payload']=='encrypted-placeholder'
    assert len(store.users())==2


@pytest.mark.parametrize('action',['disconnect','restart'])
def test_cancel_or_restart_during_exchange_cannot_commit_old_tokens(siwc,monkeypatch,action):
    params=admin_begin(siwc)
    original=chatgpt.validate_identity
    def validate(*args,**kwargs):
        identity=original(*args,**kwargs)
        if action=='disconnect':chatgpt.disconnect(siwc[3]['id'])
        else:
            chatgpt.start(siwc[3]['id'],siwc[1].cookies.get(accounts.COOKIE),'localhost',
                actor_id=siwc[2]['id'],expected_email='fixture@example.invalid')
        return identity
    monkeypatch.setattr(chatgpt,'validate_identity',validate)
    with pytest.raises(ProviderError):chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(siwc[3]['id']) is None


def test_loopback_callback_returns_to_server_selected_user_only(siwc,monkeypatch):
    from app.chatgpt import start_callback_listener
    params=admin_begin(siwc)
    monkeypatch.setenv('CHATGPT_CALLBACK_BIND','127.0.0.1')
    monkeypatch.setenv('CHATGPT_CALLBACK_PORT','17653')
    listener=start_callback_listener()
    assert listener is not None
    try:
        query=urlencode({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture','chatgpt_user':siwc[2]['id']})
        response=httpx.get(chatgpt.callback_uri()+'?'+query,follow_redirects=False)
        assert response.status_code==303
        returned=parse_qs(urlsplit(response.headers['location']).query)
        assert returned=={'chatgpt':['connected'],'chatgpt_user':[siwc[3]['id']]}
        assert 'code=' not in response.headers['location'] and 'state=' not in response.headers['location']
        assert response.headers['cache-control']=='no-store' and response.headers['referrer-policy']=='no-referrer'
        assert httpx.get(chatgpt.callback_uri()+'?'+query,headers={'Host':'evil.invalid'},follow_redirects=False).status_code==400
        response=httpx.get(chatgpt.callback_uri()+'?state=invalid&chatgpt_user='+siwc[2]['id'],follow_redirects=False)
        assert parse_qs(urlsplit(response.headers['location']).query)=={'chatgpt':['failed']}
    finally:
        listener.shutdown();listener.server_close()


def test_user_without_access_gets_admin_help_for_text_image_and_pdf(siwc):
    from app.service_messages import CONTACT_ADMIN
    from app.documents import SESSIONS
    from reportlab.pdfgen import canvas
    client=siwc[1]
    health=client.get('/api/health').json()
    assert health['model']=='unconfigured' and health['message']==CONTACT_ADMIN
    assert 'ChatGPT' not in json.dumps(health) and 'email' not in health
    payload={'text':'Hello','source':'en','target':'vi'}
    for path,body in [('/api/translate',payload),('/api/translate-image',{**payload,'regions':[
        {'text':'Hello','x':0,'y':0,'width':120,'height':24}]})]:
        response=client.post(path,json=body)
        assert response.status_code==409 and response.json()['detail']==CONTACT_ADMIN
    # Automatic source detection and unchanged text cannot bypass the grant.
    response=client.post('/api/translate',json={'text':'Hello, this is an English document.','source':'auto','target':'en'})
    assert response.status_code==409 and response.json()['detail']==CONTACT_ADMIN
    source=io.BytesIO();page=canvas.Canvas(source);page.drawString(70,720,'Hello document.');page.save()
    analyzed=client.post('/api/documents/analyze',data={'source':'en'},files={'file':('fixture.pdf',source.getvalue(),'application/pdf')})
    assert analyzed.status_code==200,analyzed.text
    for path in ('complete','translate'):
        response=client.post('/api/documents/'+path,json={'session_id':analyzed.json()['id'],'target':'vi'})
        assert response.status_code==409 and response.json()['detail']==CONTACT_ADMIN
    assert 'output_pdf' not in SESSIONS[analyzed.json()['id']]
    assert siwc[4]['calls']==[]
    SESSIONS.clear()


@pytest.mark.parametrize('status,expected',[(401,409),(403,409),(429,429),(500,502)])
def test_user_provider_errors_do_not_expose_connection_setup(siwc,monkeypatch,status,expected):
    connected(siwc);stream_fixture(monkeypatch,status=status)
    response=siwc[1].post('/api/translate',json={'text':'hello','source':'en','target':'vi'})
    assert response.status_code==expected
    message=response.json()['detail']
    assert 'admin' in message and 'ChatGPT' not in message and 'OpenAI' not in message
    assert 'kết nối' not in message and 'fixture-access' not in message


def test_admin_retains_detailed_connection_troubleshooting(siwc,monkeypatch):
    client=siwc[1]
    client.post('/api/auth/login',json={'username':'fixture-admin','password':'fixture-password-admin-123'})
    assert 'OpenAI API' in client.get('/api/health').json()['message']
    connected(siwc);stream_fixture(monkeypatch,status=401)
    response=client.post('/api/translate',json={'text':'hello','source':'en','target':'vi'})
    assert response.status_code==409 and 'ChatGPT' in response.json()['detail']


def test_authorized_auto_same_language_is_explicitly_unchanged(siwc,monkeypatch):
    connected(siwc)
    def no_inference(*args,**kwargs):raise AssertionError('Unchanged content must not call inference')
    monkeypatch.setattr(engine,'_response',no_inference)
    text='Xin chào, đây là một đoạn văn bản bằng tiếng Việt.'
    response=siwc[1].post('/api/translate',json={'text':text,'source':'auto','target':'vi'})
    assert response.status_code==200,response.text
    assert response.json()['unchanged'] and response.json()['source']=='vi'
    assert response.json()['text']==text and response.json()['chunks']==0
    assert siwc[0].usage()==[]


def test_forcing_actor_logout_blocks_pending_assisted_connection(siwc):
    params=admin_begin(siwc)
    response=siwc[1].post(f'/api/admin/users/{siwc[2]["id"]}/sessions/revoke')
    assert response.status_code==200 and response.json()['current_account_signed_out']
    with pytest.raises(ProviderError):
        chatgpt.callback({'state':params['state'],'code':'fixture-code','client_id':'oaiapp_fixture'})
    assert chatgpt.connection(siwc[3]['id']) is None
