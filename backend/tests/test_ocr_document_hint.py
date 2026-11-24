"""Protocol checks for per-page language recovery; no translation fixtures."""
from PIL import Image
import pytesseract
from app.auto_ocr import detect_page_language


SPANISH='Este documento certifica el nacimiento y contiene los datos del registro civil. La presente copia corresponde al documento original expedido por la autoridad competente. '
ENGLISH='This document certifies the registration and contains the details recorded by the competent public authority. The original document remains unchanged. '


def test_difficult_page_confirms_spanish_document_hint_before_unrelated_alphabets(monkeypatch):
    monkeypatch.setattr(pytesseract,'image_to_string',lambda *args,**kwargs:'unreadable')
    def hinted(*args,**kwargs):
        assert kwargs['lang']=='spa'
        words=SPANISH.split()
        return {'text':words,'conf':[52]*len(words)}
    monkeypatch.setattr(pytesseract,'image_to_data',hinted)
    def forbidden(*args):raise AssertionError('Verified Spanish page must not be reclassified as Thai')
    monkeypatch.setattr('app.auto_ocr.detect_image_language',forbidden)
    result=detect_page_language(Image.new('RGB',(200,300),'white'),['spa','eng','tha'],{'es':'spa','en':'eng','th':'tha'},'es')
    assert result['code']=='es' and result['method']=='page-document-confirmed'


def test_clear_english_page_overrides_spanish_document_hint(monkeypatch):
    monkeypatch.setattr(pytesseract,'image_to_string',lambda *args,**kwargs:ENGLISH)
    def forbidden(*args,**kwargs):raise AssertionError('Clear page evidence must precede the document hint')
    monkeypatch.setattr(pytesseract,'image_to_data',forbidden)
    result=detect_page_language(Image.new('RGB',(200,300),'white'),['spa','eng'],{'es':'spa','en':'eng'},'es')
    assert result['code']=='en' and result['method']=='page-latin-confirmed'


def test_clear_second_pdf_page_is_not_overwhelmed_by_noisy_first_page(monkeypatch):
    from types import SimpleNamespace
    import app.auto_ocr as ocr
    class Bitmap:
        def __init__(self,number):self.number=number
        def to_pil(self):
            image=Image.new('RGB',(200,300),'white');image.info['page']=self.number;return image
        def close(self):pass
    class Page:
        width=600
        def extract_text(self):return ''
        def render(self,**kwargs):return Bitmap(0 if self is pages[0] else 1)
    pages=[Page(),Page()]
    spanish=SPANISH*3;noise='NOISY '*100
    monkeypatch.setattr(pytesseract,'image_to_data',lambda image,**kwargs:{'text':(noise if image.info['page']==0 else spanish).split(),'conf':[85 if image.info['page']==0 else 52]*len((noise if image.info['page']==0 else spanish).split())})
    monkeypatch.setattr(pytesseract,'image_to_string',lambda *args,**kwargs:spanish)
    real_detect=ocr.detect_language
    def detect(text):
        if 'NOISY' in text:raise ValueError('Unsupported OCR noise')
        return real_detect(text)
    monkeypatch.setattr(ocr,'detect_language',detect)
    monkeypatch.setattr(ocr,'detect_image_language',lambda *args:{'code':'th','uncertain':False})
    result=ocr.detect_pdf_language(SimpleNamespace(pages=pages),pages,['spa','eng','tha'],{'es':'spa','en':'eng','th':'tha'})
    assert result['code']=='es' and result['method']=='pdf-page-confirmed'
