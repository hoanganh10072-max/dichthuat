import hashlib
import io

from PIL import Image
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.documents import SESSIONS,inspect_pdf,session,export_pdf,translate_block


def sample():
    stream=io.BytesIO(); c=canvas.Canvas(stream,pagesize=(595,842))
    c.setFont('Helvetica',16); c.drawString(60,760,'Software license agreement')
    c.setFont('Helvetica',12); c.drawString(60,710,'This document describes our software license.')
    c.drawImage(ImageReader(Image.new('RGB',(100,100),(15,130,80))),60,450,120,120)
    c.save();return stream.getvalue()


def test_pdfminer_empty_page_tree_is_recovered_without_changing_original(monkeypatch):
    import pdfplumber
    from contextlib import contextmanager
    open_original=pdfplumber.open
    inputs=[]
    @contextmanager
    def fail_first_tree(stream):
        inputs.append(stream.getvalue())
        with open_original(stream) as pdf:
            if len(inputs)==1:pdf._pages=[]
            yield pdf
    monkeypatch.setattr(pdfplumber,'open',fail_first_tree)
    source=sample();result=inspect_pdf(source,'tree.pdf','en',True)
    assert len(result['pages'])==1
    assert any('Software license agreement' in b['text'] for b in result['pages'][0]['blocks'])
    assert len(inputs)==2 and inputs[0]==source and inputs[1]!=source
    assert session(result['id'])['data']==source
    SESSIONS.clear()


def test_actual_page_limit_precedes_text_extraction(monkeypatch):
    import pdfplumber
    import pytest
    stream=io.BytesIO();pdf=canvas.Canvas(stream)
    for _ in range(11):pdf.showPage()
    pdf.save()
    def forbidden(*args,**kwargs):raise AssertionError('Oversized PDF must not reach text extraction')
    monkeypatch.setattr(pdfplumber,'open',forbidden)
    with pytest.raises(ValueError,match='PDF có 11 trang'):
        inspect_pdf(stream.getvalue(),'eleven.pdf','en',False,'word')


def test_unrecoverable_tree_does_not_report_a_page_limit(monkeypatch):
    import pdfplumber
    import pytest
    from contextlib import contextmanager
    open_original=pdfplumber.open
    @contextmanager
    def broken_tree(stream):
        with open_original(stream) as pdf:
            pdf._pages=[];yield pdf
    monkeypatch.setattr(pdfplumber,'open',broken_tree)
    with pytest.raises(ValueError,match='Cấu trúc PDF không đọc được đầy đủ'):
        inspect_pdf(sample(),'broken.pdf','en',True)


def test_pdf_layout_keeps_page_and_embedded_graphics():
    SESSIONS.clear()
    source=sample(); result=inspect_pdf(source,'sample.pdf','en',True)
    assert len(result['pages'])==1
    assert len(result['pages'][0]['protected'])==1
    assert any('license' in b['text'].lower() and not b['keep'] for b in result['pages'][0]['blocks'])
    item=session(result['id'])
    edits={b['id']:{'translation':'Thỏa thuận cấp phép phần mềm','keep':False} for b in item['pages'][0]['blocks']}
    output=export_pdf(item,edits,'vi')
    original=PdfReader(io.BytesIO(source)); translated=PdfReader(io.BytesIO(output))
    assert translated.pages[0].mediabox==original.pages[0].mediabox
    assert 'Thỏa thuận cấp phép phần mềm' in translated.pages[0].extract_text()
    assert [hashlib.sha256(i.image.tobytes()).hexdigest() for i in original.pages[0].images]==[hashlib.sha256(i.image.tobytes()).hexdigest() for i in translated.pages[0].images]
    SESSIONS.clear()


def test_native_text_pdf_avoids_full_page_ocr_and_keeps_coordinates(monkeypatch):
    import pytesseract
    from app.document_ocr import native_page_words
    calls=[]
    original=pytesseract.image_to_data
    def track(image,*args,**kwargs):
        calls.append(image.width)
        return original(image,*args,**kwargs)
    monkeypatch.setattr(pytesseract,'image_to_data',track)
    result=inspect_pdf(sample(),'native.pdf','en',True)
    blocks=result['pages'][0]['blocks']
    assert any('Software license agreement' in block['text'] for block in blocks)
    assert all(width<1400 for width in calls)
    assert min(block['x'] for block in blocks)>=59
    class BrokenFontPage:
        def dedupe_chars(self):return self
        def extract_words(self):return [{'text':'Unreadable \ufffd'}]
    assert native_page_words(BrokenFontPage()) is None
    SESSIONS.clear()


def test_pdf_glossary_does_not_call_model_for_exact_terms():
    class MustNotRun:
        def translate(self,*args):
            raise AssertionError('Glossary term should not use the model')
    assert translate_block('原始取得','zh','vi',MustNotRun(),{'原始取得':'có được ban đầu'})=='có được ban đầu'
    assert translate_block('第172页','zh','vi',MustNotRun(),{})=='Trang 172'


def test_unicode_fallback_fonts_export_names_and_symbols_without_manual_edits():
    from pypdf import PdfWriter
    from app.pdf_fonts import paragraph_markup

    original=io.BytesIO()
    writer=PdfWriter()
    writer.add_blank_page(width=595,height=842)
    writer.write(original)
    text='Bản dịch đầy đủ · 张伟 · 김민수 · 𠮷田 · ✅ · 😀'
    block={'id':'0-12','x':40,'y':60,'width':500,'height':60,'font_size':12,'translation':text,'keep':False}
    item={'data':original.getvalue(),'pages':[{'width':595,'height':842,'protected':[],'blocks':[block]}]}
    result=PdfReader(io.BytesIO(export_pdf(item,{},'vi',automatic=True)))
    extracted=''.join(result.pages[0].extract_text().split())
    assert ''.join(text.split()) in extracted
    block.update(y=825,width=45,height=9,inside_image=True)
    result=PdfReader(io.BytesIO(export_pdf(item,{},'vi',automatic=True)))
    assert item['overflow_count']==1
    appendix=''.join(''.join(page.extract_text().split()) for page in result.pages[1:])
    assert ''.join(text.split()) in appendix
    assert '[U+10FFFF]' in paragraph_markup('\U0010ffff')


def test_dense_automatic_pdf_keeps_full_translation_in_readable_appendix():
    from pypdf import PdfWriter

    original = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(original)
    start, end = 'Nội dung đầu vùng', 'Nội dung cuối vùng'
    text = start + ' ' + 'một câu trong bản dịch. ' * 350 + end
    block = {'id':'1-12','x':40,'y':825,'width':45,'height':9,'font_size':7.3,
             'translation':text,'keep':False,'inside_image':True}
    item = {'data':original.getvalue(),'pages':[{'width':595,'height':842,'protected':[],'blocks':[block]}]}
    result = PdfReader(io.BytesIO(export_pdf(item,{},'vi',automatic=True)))
    assert item['overflow_count'] == 1
    assert result.pages[0].mediabox == PdfReader(original).pages[0].mediabox
    assert '[1]' in result.pages[0].extract_text()
    appendix = '\n'.join(page.extract_text() for page in result.pages[1:])
    assert len(result.pages) > 2
    assert 'Trang gốc 1 · Vùng 1' in appendix
    assert start in appendix and end in appendix
    assert ' '.join(appendix.split()).count('một câu trong bản dịch.') == 350


def test_document_batches_same_language_pages_and_splits_truncated_batches():
    from app.document_translation import automatic_translation
    from app.engine import TranslationTooLong

    class Translator:
        provider = 'chatgpt'

        def __init__(self):
            self.calls = []

        def translate_segments(self, texts, source, target, glossary, *, document=False):
            assert document
            self.calls.append((source, texts))
            if source == 'fr' and len(texts) > 1:
                raise TranslationTooLong('fixture limit')
            return [f'Dịch {text}' for text in texts]

    pages = [{'source': source, 'blocks':[{'text':str(index),'keep':False,'confidence':90}]}
             for index, source in enumerate(('en','en','en','fr','fr','vi'))]
    engine = Translator()
    automatic_translation({'pages':pages,'source':'en'},'vi',engine,{},None)
    assert engine.calls == [('en',['0','1','2']),('fr',['3','4']),('fr',['3']),('fr',['4'])]
    assert [page['blocks'][0]['translation'] for page in pages] == ['Dịch '+str(i) for i in range(5)] + ['5']


def test_latin_glossary_does_not_leave_surrounding_ascii_untranslated():
    class Track:
        def __init__(self):self.calls=[]
        def translate(self,text,*args,**kwargs):self.calls.append(text);return 'ĐÃ DỊCH',1
    model=Track()
    output=translate_block('This software license is required.','en','vi',model,{'software license':'giấy phép phần mềm'})
    assert len(model.calls)==2 and 'This' in model.calls[0] and 'required' in model.calls[1]
    assert 'giấy phép phần mềm' in output and 'required' not in output


def test_academic_labels_and_person_names_have_different_handling():
    from app.document_academic import normalize,named_field
    assert normalize('Gtorga a','es').casefold()=='otorga a'
    assert named_field('La Universidad de Valencia')==('Đại học Valencia','institution')
    assert named_field('María Elena García Pérez')==('María Elena García Pérez','proper_name')
    assert named_field('Clinical Chemist Biologist') is None


def test_regional_ocr_recovers_an_omitted_printed_line_and_tracks_failures(monkeypatch):
    import pytesseract
    from PIL import ImageDraw,ImageFont
    from app.document_regions import recover_regions
    picture=Image.new('RGB',(1000,420),'white');draw=ImageDraw.Draw(picture)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',40)
    draw.text((45,65),'Missing printed sentence',font=font,fill=(0,30,230))
    zone={'x':0,'y':0,'width':1000,'height':420,'image':True,'exclude':[]}
    words,regions=recover_regions(picture,1,'eng',[zone],[],[])
    assert 'Missing' in ' '.join(w['text'] for w in words)
    assert regions and any(r['status']=='recognized' for r in regions)
    monkeypatch.setattr(pytesseract,'image_to_data',lambda *a,**k:{'text':[],'conf':[]})
    words,regions=recover_regions(picture,1,'eng',[zone],[],[])
    assert not words and regions and all(r['status']=='uncertain' for r in regions)


def test_erased_blue_text_does_not_remain_behind_translation():
    import base64,cv2
    import numpy as np
    from PIL import ImageDraw,ImageFont
    from app.document_ocr import repaired_background
    picture=Image.new('RGB',(650,180),'white');draw=ImageDraw.Draw(picture)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',42)
    box=draw.textbbox((25,45),'Blue printed title',font=font);draw.text((25,45),'Blue printed title',font=font,fill=(0,30,230))
    block={'x':box[0],'y':box[1],'width':box[2]-box[0],'height':box[3]-box[1]}
    patch=repaired_background(picture,1,block,[])
    result=np.asarray(Image.open(io.BytesIO(base64.b64decode(patch['png']))).convert('RGB'))
    assert (cv2.cvtColor(result,cv2.COLOR_RGB2GRAY)<150).mean()<.01


def test_automatic_company_names_and_field_labels_do_not_invent_verified_names():
    import re
    from app.document_translation import document_terms,normalize_field,identifier_field
    item={'source':'zh','glossary':{},'pages':[{'blocks':[{'text':'杭州新源软件有限公司'}]}]}
    terms=document_terms(item,{},'vi')
    assert terms['杭州新源软件有限公司'].startswith('Công ty TNHH Phần mềm ')
    assert not re.search(r'[\u3400-\u9fff]',terms['杭州新源软件有限公司'])
    text,changed=normalize_field('权利到得方式: AB2026-123')
    assert changed and text=='权利取得方式: AB2026-123'
    assert normalize_field('登记号: AB2026-123')[0]=='登记号: AB2026-123'
    assert identifier_field('登记号: 2026SR123456')=='Số đăng ký: 2026SR123456'
    assert '17862965' in identifier_field('证书号软闭登字第17862965号')


def test_failed_automatic_job_does_not_commit_a_partial_pdf():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.documents import create_document_router
    class Offline:
        def translate(self,*args,**kwargs):raise RuntimeError('Model unavailable')
    SESSIONS.clear()
    app=FastAPI();app.include_router(create_document_router(Offline()));client=TestClient(app)
    analyzed=client.post('/api/documents/analyze',data={'source':'en'},files={'file':('sample.pdf',sample(),'application/pdf')})
    assert analyzed.status_code==200,analyzed.text
    token=analyzed.json()['id']
    before=[b['translation'] for p in session(token)['pages'] for b in p['blocks']]
    result=client.post('/api/documents/complete',json={'session_id':token,'target':'vi'})
    assert result.status_code==503
    assert 'output_pdf' not in session(token)
    assert before==[b['translation'] for p in session(token)['pages'] for b in p['blocks']]
    SESSIONS.clear()


def test_real_automatic_document_finishes_without_region_edits():
    import pytest
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.documents import create_document_router
    from app.main import engine
    if engine.state!='ready':engine.load()
    if engine.state!='ready':pytest.skip('No real ChatGPT connection in isolated test database')
    SESSIONS.clear()
    app=FastAPI();app.include_router(create_document_router(engine));client=TestClient(app)
    analyzed=client.post('/api/documents/analyze',data={'source':'en'},files={'file':('sample.pdf',sample(),'application/pdf')})
    assert analyzed.status_code==200,analyzed.text
    token=analyzed.json()['id']
    completed=client.post('/api/documents/complete',json={'session_id':token,'target':'vi'})
    assert completed.status_code==200,completed.text
    result=completed.json()
    assert result['ready'] and result['document']['automatic'] and result['pages'][0].startswith('data:image/jpeg;base64,')
    assert all(b['translation'].strip() for p in result['document']['pages'] for b in p['blocks'])
    output=client.post('/api/documents/export',json={'session_id':token,'target':'vi','automatic':True})
    assert output.status_code==200 and output.content.startswith(b'%PDF')
    assert output.content==session(token)['output_pdf']
    assert client.post('/api/documents/export',json={'session_id':token,'target':'en','automatic':True}).status_code==422
    SESSIONS.clear()


def test_decode_limit_is_retried_in_smaller_pieces_without_dropping_content():
    from app.document_translation import bounded_translation
    from app.engine import TranslationTooLong
    calls=[]
    def translate(text,*args):
        calls.append(text)
        if len(text)>24:raise TranslationTooLong('limit')
        return text
    text='Primera parte del documento. Segunda parte del documento.'
    output=bounded_translation(text,'es','vi',None,{},translate)
    assert output.split()==text.split()
    assert len(calls)>1


def test_real_spanish_pdf_detection_uses_multiple_scanned_pages():
    from PIL import ImageDraw,ImageFont
    SESSIONS.clear()
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',30)
    image=Image.new('RGB',(1200,1400),'white');draw=ImageDraw.Draw(image)
    lines=['Universidad de Sonora','Certificado de estudios universitarios',
           'La universidad certifica que la estudiante ha cumplido',
           'con todos los requisitos del programa de estudios.',
           'Este documento contiene las materias y calificaciones',
           'obtenidas durante el periodo de estudios universitarios.',
           'El presente certificado se expide para los fines legales',
           'que correspondan a solicitud de la persona interesada.']
    for i,line in enumerate(lines):draw.text((50,70+i*90),line,font=font,fill=(15,35,95))
    stream=io.BytesIO();c=canvas.Canvas(stream,pagesize=(595,842))
    for _ in range(2):c.drawImage(ImageReader(image),0,0,595,842);c.showPage()
    english=Image.new('RGB',(1200,1400),'white');english_draw=ImageDraw.Draw(english)
    english_lines=['University certificate and academic record',
                   'This document certifies that the student completed',
                   'the required university program and examinations.',
                   'The following subjects were successfully completed.',
                   'The certificate is issued by the university registrar.',
                   'This English translation accompanies the original',
                   'Spanish document and describes the academic program.']
    for i,line in enumerate(english_lines):english_draw.text((50,70+i*90),line,font=font,fill=(15,35,95))
    c.drawImage(ImageReader(english),0,0,595,842);c.showPage()
    c.save()
    result=inspect_pdf(stream.getvalue(),'spanish.pdf','auto')
    assert result['source']=='es'
    assert [p['source'] for p in result['pages']]==['es','es','en']
    assert result['languages']==['es','en']
    assert any('Universidad' in b['text'] for b in result['pages'][0]['blocks'])
    SESSIONS.clear()


def test_interactive_pdf_is_rejected_without_flattening():
    import pytest
    stream=io.BytesIO(); c=canvas.Canvas(stream,pagesize=(595,842))
    c.acroForm.textfield(name='keep_me',x=60,y=700,width=200,height=25)
    c.showPage(); c.save()
    original=stream.getvalue()
    with pytest.raises(ValueError,match='trường điền'):
        inspect_pdf(original,'interactive.pdf','en',True)
    assert 'keep_me' in PdfReader(io.BytesIO(original)).get_fields()


def test_default_reads_image_text_and_keeps_detected_seal_and_code_pixels():
    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    from contextlib import closing
    from PIL import ImageDraw, ImageFont, ImageChops
    SESSIONS.clear()
    picture=Image.new('RGB',(900,600),(217,239,247))
    draw=ImageDraw.Draw(picture)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',34)
    draw.text((35,50),'Software license agreement',font=font,fill='black')
    draw.text((35,125),'Banking solution',font=font,fill='black')
    draw.ellipse((620,320,790,490),outline=(210,35,35),width=9)
    draw.ellipse((350,320,520,490),outline=(25,65,170),width=9)
    draw.ellipse((374,344,496,466),outline=(25,65,170),width=5)
    qr=cv2.QRCodeEncoder_create().encode('saeng-local-test')
    qr=Image.fromarray(qr).resize((150,150),Image.Resampling.NEAREST).convert('RGB')
    picture.paste(qr,(80,340))
    stream=io.BytesIO(); c=canvas.Canvas(stream,pagesize=(595,842))
    c.setFont('Helvetica',18);c.drawString(60,760,'Document with embedded image')
    c.drawImage(ImageReader(picture),60,300,450,300)
    c.save()
    source=stream.getvalue();result=inspect_pdf(source,'image.pdf','en')
    blocks=result['pages'][0]['blocks']
    image_blocks=[b for b in blocks if b.get('inside_image')]
    assert any('license' in b['text'].lower() and not b['keep'] for b in image_blocks)
    assert any(r.get('kind')=='seal' for r in result['pages'][0]['protected'])
    assert sum(r.get('kind')=='seal' for r in result['pages'][0]['protected'])>=2
    assert any(r.get('kind')=='code' for r in result['pages'][0]['protected'])
    # Inpainting bytes remain server-side; clients receive only review metadata.
    assert all('background' not in b for b in blocks)
    item=session(result['id'])
    import base64
    for block in item['pages'][0]['blocks']:
        if block.get('background'):
            background=Image.open(io.BytesIO(base64.b64decode(block['background']['png']))).convert('RGB')
            # The erased band must not retain black source characters.
            assert (np.asarray(background).max(axis=2)<150).mean()<.01
    edits={b['id']:{'translation':'Giấy phép phần mềm','keep':False} for b in blocks}
    output=export_pdf(item,edits,'vi')
    assert PdfReader(io.BytesIO(source)).pages[0].mediabox==PdfReader(io.BytesIO(output)).pages[0].mediabox
    with closing(pdfium.PdfDocument(source)) as a,closing(pdfium.PdfDocument(output)) as b:
        original=a[0].render(scale=2).to_pil().convert('RGB')
        translated=b[0].render(scale=2).to_pil().convert('RGB')
        for r in result['pages'][0]['protected']:
            rect=(round(r['x']*2)+2,round(r['y']*2)+2,round((r['x']+r['width'])*2)-2,round((r['y']+r['height'])*2)-2)
            assert ImageChops.difference(original.crop(rect),translated.crop(rect)).getbbox() is None
    SESSIONS.clear()
