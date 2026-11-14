import io
import re
import zipfile
from pathlib import Path

MAX_TEXT = 12000
OCR_LANGS = {'vi': 'vie', 'lo': 'lao', 'en': 'eng', 'th': 'tha', 'zh': 'chi_sim', 'ja': 'jpn', 'ko': 'kor', 'km': 'khm', 'fr': 'fra', 'de': 'deu', 'es': 'spa', 'ru': 'rus', 'id': 'ind', 'ms': 'msa', 'my': 'mya', 'hi': 'hin','it':'ita','pt':'por','nl':'nld','ar':'ara'}


def validate_ocr_script(text, language):
    # A script mismatch is not a quality score, but it prevents translating
    # clearly invalid OCR (e.g. Latin noise from an image selected as Chinese).
    scripts = {'zh': (r'[\u3400-\u9fff]', 'Trung'), 'ko': (r'[\uac00-\ud7af\u1100-\u11ff]', 'Hàn')}
    if language in scripts and text.strip():
        pattern, name = scripts[language]
        if not re.search(pattern, text):
            raise ValueError(f'OCR không nhận ra chữ {name} trong ảnh. Kiểm tra ngôn ngữ nguồn, dùng ảnh gốc rõ hơn hoặc cắt sát vùng chữ rồi tải lại; chưa thể dịch đáng tin cậy từ kết quả này.')


def extract(data: bytes, filename: str, language: str):
    suffix = Path(filename).suffix.lower()
    warnings = []
    layout = None
    detection = None
    if suffix == '.txt':
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('TXT cần dùng mã hóa UTF-8.')
    elif suffix == '.pdf':
        from pypdf import PdfReader
        pdf = PdfReader(io.BytesIO(data))
        if pdf.is_encrypted:
            raise ValueError('PDF có mật khẩu chưa được hỗ trợ.')
        if len(pdf.pages) > 30:
            raise ValueError('PDF tối đa 30 trang.')
        text = '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
        warnings.append('Chỉ trích xuất lớp văn bản PDF; PDF scan cần xuất thành ảnh rồi OCR. Không giữ bố cục gốc.')
    elif suffix == '.docx':
        from docx import Document
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError('DOCX giải nén quá lớn.')
        doc = Document(io.BytesIO(data))
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        parts = []
        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)
            elif isinstance(block, Table):
                parts.extend('\t'.join(c.text for c in row.cells) for row in block.rows)
        text = '\n'.join(parts)
        warnings.append('Trích xuất đoạn văn và bảng; không giữ định dạng, ảnh, header/footer.')
    elif suffix in {'.png', '.jpg', '.jpeg', '.webp'}:
        import pytesseract
        from PIL import Image, ImageOps
        import math
        from .image_layout import line_regions
        # Enforce this OCR path's own limit without mutating Pillow globally;
        # the vision path can safely downscale larger phone photographs.
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError('Ảnh tối đa 16 megapixel.')
            # Sparse-text mode handles short Korean signs/captions more reliably
            # than automatic page segmentation; OCR does not preserve layout.
            image = ImageOps.exif_transpose(image).convert('RGB')
            # Read small, yellow-tinted forms at a useful resolution. Keep the
            # untouched colour image and map OCR coordinates back to it.
            factor = min(2, max(1, 1400 / image.width), math.sqrt(16_000_000 / (image.width * image.height)))
            ocr_image = ImageOps.autocontrast(image.convert('L'))
            if factor > 1:
                ocr_image = ocr_image.resize((round(image.width * factor), round(image.height * factor)), Image.Resampling.LANCZOS)
            installed = pytesseract.get_languages(config='')
            if language == 'auto':
                from .auto_ocr import detect_page_language
                # Confirm readable Latin text using its own OCR model before
                # comparing unrelated scripts, which can hallucinate Thai.
                detection = detect_page_language(ocr_image, installed, OCR_LANGS, 'auto')
                language = detection['code']
            lang = OCR_LANGS[language]
            if lang not in installed:
                raise ValueError(f'Chưa cài dữ liệu OCR {lang} trên máy chủ.')
            if language in {'es', 'fr', 'de', 'vi'} and 'eng' in installed:
                lang += '+eng'
            config = '--psm 11'
            regions = line_regions(pytesseract.image_to_data(ocr_image, lang=lang, config=config, output_type=pytesseract.Output.DICT, timeout=45))
            text = '\n'.join(region['text'] for region in regions)
            if not text.strip():
                # Retry a tightly cropped text block with the same language.
                regions = line_regions(pytesseract.image_to_data(ocr_image, lang=lang, config='--psm 6', output_type=pytesseract.Output.DICT, timeout=45))
                text = '\n'.join(region['text'] for region in regions)
            sx, sy = ocr_image.width / image.width, ocr_image.height / image.height
            for region in regions:
                left, top = math.floor(region['x'] / sx), math.floor(region['y'] / sy)
                right = min(image.width, math.ceil((region['x'] + region['width']) / sx))
                bottom = min(image.height, math.ceil((region['y'] + region['height']) / sy))
                region.update(x=left, y=top, width=max(1, right-left), height=max(1, bottom-top))
            layout = {'width': image.width, 'height': image.height, 'regions': regions}
        validate_ocr_script(text, language)
        warnings.append('Kiểm tra chữ nhỏ, tên riêng và số hiệu sau khi nhận diện ảnh.')
    else:
        raise ValueError('Chỉ hỗ trợ PNG, JPG, WEBP, PDF, DOCX và TXT.')
    text = text.strip()
    if not text:
        raise ValueError('Không tìm thấy văn bản. Với PDF scan, hãy tải ảnh của trang cần OCR.')
    if len(text) > MAX_TEXT:
        raise ValueError('Văn bản vượt 12.000 ký tự; hãy chia tài liệu nhỏ hơn. Không có nội dung nào bị cắt âm thầm.')
    if language == 'auto':
        from .detection import detect_language
        detection = detect_language(text)
    if detection:
        warnings.append('Ngôn ngữ được tự phát hiện; hãy chọn thủ công nếu nhận diện chưa đúng.')
    return {'text': text, 'warnings': warnings, 'filename': Path(filename).name, 'layout': layout, 'detection': detection}
