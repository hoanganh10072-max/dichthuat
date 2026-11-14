import io
import json
from zipfile import ZipFile
import pytest
from docx import Document
from PIL import Image

from app.engine import LANGUAGES
from app.extract import OCR_LANGS
from app.detection import detect_language
from app.output_policy import document_output_policy,PDF_FORM_LANGUAGES
from app.word_export import build_word


def test_all_twenty_languages_have_ocr_data_installed():
    import pytesseract
    assert len(LANGUAGES)==20
    assert set(LANGUAGES)==set(OCR_LANGS)
    assert set(OCR_LANGS.values())<=set(pytesseract.get_languages(config=''))


@pytest.mark.parametrize('code,text',[
 ('it','Questo documento contiene informazioni importanti relative alla domanda e ai documenti originali da presentare.'),
 ('pt','Este documento contém informações importantes sobre o pedido e os documentos originais que devem ser apresentados.'),
 ('nl','Dit document bevat belangrijke informatie over de aanvraag en de originele documenten die moeten worden ingediend.'),
 ('ar','هذه الوثيقة تحتوي على معلومات مهمة عن الطلب والمستندات الأصلية المطلوبة.')])
def test_new_languages_are_detected_locally(code,text):
    assert detect_language(text)['code']==code


def test_pdf_format_policy_prefers_form_only_when_readable():
    item={'target':'vi','pages':[{'blocks':[{'translation':'Text','font_size':14,'layout':{'font_size':11}}]}]}
    assert document_output_policy(item)['mode']=='original'
    item['pages'][0]['blocks'][0]['layout']['font_size']=7
    assert document_output_policy(item)['mode']=='a4'
    item['pages'][0]['blocks'][0]['layout']['font_size']=11
    item['overflow_count']=1
    assert document_output_policy(item)['mode']=='a4'
    item['overflow_count']=0;item['target']='ar'
    assert document_output_policy(item)['mode']=='a4'
    assert {'it','pt','nl'}<=PDF_FORM_LANGUAGES


def test_arabic_word_has_native_bidi_text_and_no_source_background():
    text='هذه ترجمة واضحة للنص في المستند'
    data=build_word([{'width':600,'height':800,'regions':[{'x':40,'y':30,'width':500,'height':40,'translation':text}]}])
    with ZipFile(io.BytesIO(data)) as z:
        xml=z.read('word/document.xml').decode()
        assert text in xml and 'w:bidi' in xml and 'w:rtl' in xml and 'w:szCs' in xml
        assert not any(name.startswith('word/media/') for name in z.namelist())
