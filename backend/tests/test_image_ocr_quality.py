"""Real Tesseract regression: a Latin form must not become Thai OCR."""
import io

from PIL import Image, ImageDraw, ImageFont

from app.extract import extract


def test_small_yellow_spanish_form_confirms_latin_and_retains_coordinates(monkeypatch):
    from app import auto_ocr
    image=Image.new('RGB',(1000,640),'#fff47a')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    lines=[
        'APOSTILLE',
        'El presente documento público ha sido firmado por',
        'la directora general del registro civil del estado.',
        'Esta certificación confirma la firma del documento.',
        'El documento se presenta ante las autoridades competentes.',
        'Lugar de expedición: Hermosillo, Sonora, México.',
        'Nombre de la persona autorizada para firmar el documento.',
        'Fecha de expedición: 10 de noviembre de 2026.',
    ]
    for i,line in enumerate(lines):
        draw.text((40,35+i*58),line,fill='#28220e',font=font)
        draw.line((30,75+i*58,960,75+i*58),fill='#78662c',width=1)
    def wrong_script_fallback(*args,**kwargs):
        raise AssertionError('Confirmed Latin text must bypass unrelated-script candidates')
    monkeypatch.setattr(auto_ocr,'detect_image_language',wrong_script_fallback)
    stream=io.BytesIO();image.save(stream,format='PNG')
    result=extract(stream.getvalue(),'spanish-form.png','auto')
    assert result['detection']['code']=='es',result['detection']
    assert result['detection']['method']=='page-latin-confirmed'
    assert 'documento' in result['text'].lower()
    assert 'Hermosillo' in result['text']
    assert not any('\u0e00'<=c<='\u0e7f' for c in result['text'])
    layout=result['layout']
    assert (layout['width'],layout['height'])==(1000,640)
    assert len(layout['regions'])>=8
    for region in layout['regions']:
        assert 0<=region['x']<1000 and 0<=region['y']<640
        assert region['x']+region['width']<=1000
        assert region['y']+region['height']<=640
        assert region['height']<80,'A table line must not become a giant OCR text box'
