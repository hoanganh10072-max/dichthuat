"""Real PDF/OCR/DOCX coverage. The engine below is a protocol fixture only."""
import base64
import io
import time
from zipfile import ZipFile

import pytest
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app import accounts
from app.auth import AuthenticationMiddleware, auth_router
from app.documents import SESSIONS, create_document_router, inspect_pdf, session
from app.engine import LANGUAGES
from app.word_export import MIME


def sample_pdf():
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23)
    scan=Image.new('RGB',(600,840),'#fff5a1');draw=ImageDraw.Draw(scan)
    draw.text((55,32),'SCANNED CERTIFICATE',font=font,fill='black')
    draw.rectangle((45,100,555,310),outline='black',width=3)
    draw.line((45,205,555,205),fill='black',width=3)
    draw.line((270,100,270,310),fill='black',width=3)
    for xy,text in [((65,130),'Country'),((290,130),'Canada'),((65,235),'Year'),((290,235),'2026'),((45,750),'SCAN FOOTER COMPLETE')]:draw.text(xy,text,font=font,fill='black')
    image=io.BytesIO();scan.save(image,format='PNG')
    data=io.BytesIO();c=canvas.Canvas(data,pagesize=(600,840))
    c.setFont('Helvetica',15);c.drawString(50,790,'NATIVE DOCUMENT TITLE')
    c.rect(50,610,480,100);c.line(50,660,530,660);c.line(125,610,125,710)
    c.setFont('Helvetica',11)
    for x,y,text in [(60,680,'Country'),(135,680,'Canada'),(60,630,'Year'),(135,630,'2026')]:c.drawString(x,y,text)
    c.drawImage(ImageReader(io.BytesIO(image.getvalue())),50,80,300,420)
    c.drawString(50,35,'NATIVE FOOTER COMPLETE');c.showPage()
    c.drawImage(ImageReader(io.BytesIO(image.getvalue())),0,0,600,840);c.save()
    return data.getvalue()


class ProtocolEngine:
    state='ready'
    provider='chatgpt'
    def __init__(self):self.calls=[]
    def translate_segments(self,texts,source,target,*args,**kwargs):
        self.calls.extend(texts)
        return [f'{target}: {text}' for text in texts]


@pytest.fixture
def client():
    engine=ProtocolEngine();app=FastAPI();app.add_middleware(AuthenticationMiddleware)
    app.include_router(auth_router(engine));app.include_router(create_document_router(engine))
    user=accounts.store.create_user('pdf-word-user','pdf-word-password-123')
    client=TestClient(app,headers={'X-Kun-Request':'1'})
    assert client.post('/api/auth/login',json={'username':user['username'],'password':'pdf-word-password-123'}).status_code==200
    yield client,engine,user
    SESSIONS.clear()


def test_word_reads_native_and_embedded_and_scanned_pages_without_pdf_overlay(client,monkeypatch):
    import app.documents as documents
    def forbidden(*args,**kwargs):raise AssertionError('Word must not render a background or PDF overlay')
    monkeypatch.setattr(documents,'export_pdf',forbidden)
    monkeypatch.setattr('app.document_ocr.repaired_background',forbidden)
    http,engine,user=client
    analyzed=http.post('/api/documents/analyze',data={'source':'en','output_format':'word','preserve_images':'true'},files={'file':('mixed.pdf',sample_pdf(),'application/pdf')})
    assert analyzed.status_code==200,analyzed.text
    doc=analyzed.json();assert len(doc['pages'])==2
    contents=' '.join(b['text'] for p in doc['pages'] for b in p['blocks'])
    for text in ('NATIVE DOCUMENT TITLE','NATIVE FOOTER COMPLETE','SCANNED CERTIFICATE','SCAN FOOTER COMPLETE'):
        assert text in contents
    assert any(b['inside_image'] for b in doc['pages'][0]['blocks'])
    assert all(p['tables'] for p in doc['pages'])
    assert any(b['text']=='Country' for b in doc['pages'][0]['blocks']), 'Do not merge the Country label with the next column'
    assert any(b['text']=='Canada' for b in doc['pages'][0]['blocks'])
    assert not any('background' in b for p in session(doc['id'])['pages'] for b in p['blocks'])
    request={'session_id':doc['id'],'target':'vi','output_format':'word','automatic':True}
    complete=http.post('/api/documents/complete',json=request)
    assert complete.status_code==200,complete.text
    assert complete.json()['pages']==[] and complete.json()['document']['output_policy']['format']=='docx'
    assert 'NATIVE DOCUMENT TITLE' in engine.calls, 'Translate uppercase prose too'
    assert 'output_pdf' not in session(doc['id'])
    output=http.post('/api/documents/export-word',json=request)
    assert output.status_code==200 and output.headers['content-type']==MIME
    document=Document(io.BytesIO(output.content))
    assert len(document.tables)>=3
    with ZipFile(io.BytesIO(output.content)) as z:
        xml=z.read('word/document.xml').decode()
        for text in ('NATIVE FOOTER COMPLETE','SCAN FOOTER COMPLETE'):assert text in xml
        assert not any(name.startswith('word/media/') for name in z.namelist())
        assert 'w:sz w:val="22"' in xml and 'w:hRule="atLeast"' in xml


@pytest.mark.parametrize('target',list(LANGUAGES))
def test_word_completion_works_for_all_twenty_targets_and_reuses_translations(client,target,monkeypatch):
    http,engine,user=client
    block={'id':'0-0','text':'Content to translate','translation':'','keep':False,'confidence':100,'x':30,'y':30,'width':200,'height':20,'issues':[]}
    SESSIONS['word-language']={'id':'word-language','owner_id':user['id'],'expires':time.monotonic()+100,'filename':'fixture.pdf','source':'en','pages':[{'number':1,'width':600,'height':840,'preview':'','tables':[],'blocks':[block]}],'warnings':[],'glossary':{}}
    def forbidden(*args,**kwargs):raise AssertionError('Word must never depend on the PDF font or overlay')
    monkeypatch.setattr('app.documents.export_pdf',forbidden)
    request={'session_id':'word-language','target':target,'output_format':'word'}
    result=http.post('/api/documents/complete',json=request)
    assert result.status_code==200,result.text
    previous=list(engine.calls)
    assert http.post('/api/documents/export-word',json=request).status_code==200
    assert http.post('/api/documents/export-word',json=request).status_code==200
    assert engine.calls==previous
    assert http.post('/api/documents/export-word',json={**request,'target':'zz'}).status_code==409


def test_invalid_output_format_rejected_and_anonymous_word_export_denied(client):
    http,_,_=client
    assert http.post('/api/documents/complete',json={'session_id':'missing','output_format':'html'}).status_code==422
    assert TestClient(http.app,headers={'X-Kun-Request':'1'}).post('/api/documents/export-word',json={'session_id':'missing'}).status_code==401


def test_word_does_not_drop_recognized_small_image_footnotes(monkeypatch):
    from app.document_ocr import ocr_words
    import pytesseract
    monkeypatch.setattr(pytesseract,'image_to_data',lambda *args,**kwargs:{'text':['Footnote'],'conf':[88],'left':[10],'top':[15],'width':[20],'height':[3]})
    image=Image.new('RGB',(100,100),'white')
    zone={'x':0,'y':0,'width':100,'height':100,'image':True,'read_color':True}
    assert ocr_words(image,1,'eng',[zone],[])[0]['text']=='Footnote'
