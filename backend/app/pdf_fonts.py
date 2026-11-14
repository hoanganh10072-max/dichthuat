"""Embed Unicode fallback fonts without discarding translated characters."""
from functools import lru_cache
from pathlib import Path
import unicodedata
import re
from xml.sax.saxutils import escape

BASE_FONT = 'SaengDoc'
FONT_ROOT = Path('/usr/share/fonts/truetype')
FALLBACKS = (
    ('DocSans', 'dejavu/DejaVuSans.ttf'),
    ('DocCJK', 'wqy/wqy-zenhei.ttc'),
    ('DocKorean', 'nanum/NanumGothic.ttf'),
    ('DocLao', 'noto/NotoSansLao-Regular.ttf'),
    ('DocThai', 'noto/NotoSansThai-Regular.ttf'),
    ('DocKhmer', 'noto/NotoSansKhmer-Regular.ttf'),
    ('DocMyanmar', 'noto/NotoSansMyanmar-Regular.ttf'),
    ('DocHindi', 'noto/NotoSansDevanagari-Regular.ttf'),
    ('DocSymbols', 'ancient-scripts/Symbola_hint.ttf'),
    ('DocHanA', 'hanazono/HanaMinA.ttf'),
    ('DocHanB', 'hanazono/HanaMinB.ttf'),
)


@lru_cache(maxsize=None)
def register_font(name, relative_path):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    path = FONT_ROOT / relative_path
    if not path.is_file():
        path = next(FONT_ROOT.rglob(Path(relative_path).name), None)
    if path is None:
        return False
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return True


def register_document_fonts():
    register_font(BASE_FONT, 'dejavu/DejaVuSerif.ttf')
    register_font(BASE_FONT+'Bold', 'dejavu/DejaVuSerif-Bold.ttf')


@lru_cache(maxsize=16384)
def character_font(character, bold):
    from reportlab.pdfbase import pdfmetrics
    base = BASE_FONT+'Bold' if bold else BASE_FONT
    if character.isspace() or pdfmetrics.getFont(base).face.charToGlyph.get(ord(character)):
        return base
    if unicodedata.category(character) in ('Co', 'Cn', 'Cc'):
        return None
    for name, path in FALLBACKS:
        if register_font(name, path) and pdfmetrics.getFont(name).face.charToGlyph.get(ord(character)):
            return name
    return None


def paragraph_markup(text, bold=False):
    register_document_fonts()
    base = BASE_FONT+'Bold' if bold else BASE_FONT
    parts, run = [], []
    current_font = base

    def flush():
        if run:
            content = escape(''.join(run))
            parts.append(content if current_font == base else f'<font name="{current_font}">{content}</font>')
            run.clear()

    for character in unicodedata.normalize('NFC', text).replace('\r\n', '\n').replace('\r', '\n'):
        if character == '\n':
            flush()
            parts.append('<br/>')
            continue
        # Format controls and variation selectors have no independent visible glyph.
        if unicodedata.category(character) == 'Cf' or '\ufe00' <= character <= '\ufe0f' or '\U000e0100' <= character <= '\U000e01ef':
            continue
        selected = character_font(character, bold)
        content = character
        if selected is None:
            selected, content = base, f'[U+{ord(character):04X}]'
        if selected != current_font:
            flush()
            current_font = selected
        run.append(content)
    flush()
    return ''.join(parts)


def repair_unicode_maps(reader):
    """ReportLab 4.4 writes non-BMP characters as scalar hex instead of UTF-16."""
    from pypdf.generic import DecodedStreamObject, NameObject

    def utf16_mapping(match):
        character = chr(int(match[2], 16))
        return match[1] + b'<' + character.encode('utf-16-be').hex().upper().encode('ascii') + b'>'

    for page in reader.pages:
        for reference in page.get('/Resources', {}).get('/Font', {}).values():
            font = reference.get_object()
            if '/ToUnicode' not in font:
                continue
            original = font['/ToUnicode'].get_data()
            repaired = re.sub(rb'(<[0-9A-Fa-f]+>\s*)<([0-9A-Fa-f]{5,6})>', utf16_mapping, original)
            if repaired != original:
                stream = DecodedStreamObject()
                stream.set_data(repaired)
                font[NameObject('/ToUnicode')] = stream
