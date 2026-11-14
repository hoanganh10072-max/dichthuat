"""Best-effort OCR language selection among traineddata installed locally."""
import math
import re
from collections import Counter

from .detection import detect_language, SCRIPTS


def detect_image_language(image, installed, mapping):
    import pytesseract
    preview = image.copy()
    preview.thumbnail((1600, 1600))
    candidates = []
    for code, traineddata in mapping.items():
        if traineddata not in installed:
            continue
        try:
            data = pytesseract.image_to_data(preview, lang=traineddata, config='--psm 11',
                output_type=pytesseract.Output.DICT, timeout=8)
        except RuntimeError:
            continue
        words = [(word.strip(), max(0, float(conf))) for word, conf in zip(data['text'], data['conf']) if word.strip() and float(conf) >= 0]
        text = ' '.join(word for word, _ in words)
        letters = ''.join(c for c in text if c.isalpha())
        if len(letters) < 3:
            continue
        confidence = sum(conf * len(word) for word, conf in words) / sum(len(word) for word, _ in words)
        pattern = r'[\u3400-\u9fff]' if code == 'zh' else SCRIPTS.get(code)
        script_match = len(re.findall(pattern, letters)) / len(letters) if pattern else 0
        try:
            detected = detect_language(text)
        except ValueError:
            continue
        score = confidence + script_match * 8 + (12 if detected['code'] == code else 0) + min(5, math.log1p(len(letters)))
        candidates.append((score, detected, code,confidence,len(letters)))
    if not candidates:
        raise ValueError('Chưa phát hiện được ngôn ngữ trong ảnh. Chọn nguồn thủ công hoặc tải ảnh rõ hơn.')
    votes=Counter(c[1]['code'] for c in candidates if c[3]>=60 and c[4]>=30)
    candidates=[(s+min(24,max(0,votes[d['code']]-1)*8),d,c,conf,length) for s,d,c,conf,length in candidates]
    candidates.sort(key=lambda item: item[0], reverse=True)
    score, detected, *_ = candidates[0]
    if score < 35:
        raise ValueError('Ảnh chưa đủ rõ để tự phát hiện ngôn ngữ. Hãy chọn nguồn thủ công và kiểm tra chữ OCR.')
    if mapping[detected['code']] not in installed:
        raise ValueError('Đã nhận diện ngôn ngữ nhưng chưa cài dữ liệu OCR tương ứng trên máy chủ. Hãy chọn nguồn thủ công hoặc cài thêm traineddata.')
    return {**detected, 'method': 'ocr-candidates', 'uncertain': detected['uncertain'] or (len(candidates)>1 and score-candidates[1][0]<8)}


def detect_pdf_language(pdf,renderer,installed,mapping):
    """Use multi-page Latin evidence before voting on decorative cover pages."""
    import pytesseract
    native='\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
    if len(''.join(c for c in native if c.isalpha()))>=100:
        detected=detect_language(native)
        if mapping[detected['code']] in installed:
            return {**detected,'method':'pdf-text'}
    texts=[];best=None;best_count=-1
    for i in range(min(3,len(pdf.pages))):
        page=pdf.pages[i]
        bitmap=renderer[i].render(scale=min(1.8,1400/float(page.width)))
        image=bitmap.to_pil().convert('RGB');bitmap.close()
        d=pytesseract.image_to_data(image,lang='eng',config='--psm 11',output_type=pytesseract.Output.DICT,timeout=20)
        words=[w for w,c in zip(d['text'],d['conf']) if float(c)>=75 and len(re.findall(r'[A-Za-zÀ-ž]',w))>=2]
        text=' '.join(words);texts.append(text)
        count=len(re.findall(r'[A-Za-zÀ-ž]',text))
        if count>best_count:best=image;best_count=count
    evidence='\n'.join(texts)
    latin={'en','vi','es','fr','de','id','ms','it','pt','nl'}
    if len(re.findall(r'[A-Za-zÀ-ž]',evidence))>=180:
        try:
            detected=detect_language(evidence)
            if detected['code'] in latin and not detected['uncertain'] and mapping[detected['code']] in installed:
                # Confirm the inferred Latin language with its own OCR data.
                trained=mapping[detected['code']]
                confirm=pytesseract.image_to_string(best,lang=trained,config='--psm 11',timeout=20)
                check=detect_language(confirm)
                if check['code']==detected['code'] and len(re.findall(r'[A-Za-zÀ-ž]',confirm))>=60:
                    return {**detected,'method':'pdf-multiple-pages'}
        except ValueError:
            pass
    return detect_image_language(best,installed,mapping)


def detect_page_language(image,installed,mapping,hint,*,native=''):
    import pytesseract
    if sum(char.isalpha() for char in native)>=100:
        try:
            detected=detect_language(native)
            if not detected['uncertain'] and mapping.get(detected['code']) in installed:
                return {**detected,'method':'page-pdf-text'}
        except ValueError:
            pass
    preview=image.copy();preview.thumbnail((1600,1800))
    # First use readable Latin content, then confirm with the inferred OCR
    # language. This handles alternating original/translated certificate pages.
    text=pytesseract.image_to_string(preview,lang='eng',config='--psm 11',timeout=20)
    if len(re.findall(r'[A-Za-zÀ-ž]',text))>=60:
        try:
            detected=detect_language(text)
            if detected['code'] in {'es','en','vi','fr','de','id','ms','it','pt','nl'} and not detected['uncertain'] and mapping[detected['code']] in installed:
                trained=mapping[detected['code']]
                confirm=text if trained=='eng' else pytesseract.image_to_string(preview,lang=trained,config='--psm 11',timeout=20)
                if detect_language(confirm)['code']==detected['code']:
                    return {**detected,'method':'page-latin-confirmed'}
        except ValueError:
            pass
    result=detect_image_language(preview,installed,mapping)
    return result
