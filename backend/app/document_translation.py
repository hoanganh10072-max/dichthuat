"""Automatic document rules around the real, local translation engine.

Terminology is generic; there are no stored translations of the user's pages.
Pinyin is a name spelling convention, not a substitute for translating prose.
"""
import re
from difflib import SequenceMatcher
from itertools import groupby

COMPANY_RE=r'[\u3400-\u9fff]{2,50}?(?:股份有限公司|有限责任公司|有限公司)'
LEGAL_SUFFIXES={'股份有限公司':'Công ty CP','有限责任公司':'Công ty TNHH','有限公司':'Công ty TNHH'}
DESCRIPTORS={'集团':'Tập đoàn','科技':'Công nghệ','技术':'Kỹ thuật','信息':'Thông tin','软件':'Phần mềm'}
CITIES=('北京','上海','广州','深圳','大连','天津','杭州','南京','成都','重庆')
DOCUMENT_TERMS={
    '著作权人':'Chủ sở hữu quyền tác giả','软件名称':'Tên phần mềm',
    '权利取得方式':'Cách xác lập quyền','权利范围':'Phạm vi quyền',
    '证书号':'Số chứng nhận','登记号':'Số đăng ký','简称':'Viết tắt',
    '计算机软件保护条例':'Quy định bảo vệ phần mềm máy tính',
    '计算机软件著作权登记办法':'Biện pháp đăng ký quyền tác giả phần mềm máy tính',
    '中国版权保护中心':'Trung tâm Bảo vệ bản quyền Trung Quốc',
    '银行核心业务系统':'Hệ thống nghiệp vụ ngân hàng lõi',
}


def pinyin_name(text):
    from pypinyin import lazy_pinyin
    return ' '.join(word.title() for word in lazy_pinyin(text,v_to_u=True))


def company_parts(text):
    suffix=next((s for s in LEGAL_SUFFIXES if text.endswith(s)),None)
    if not suffix:
        return None
    stem=text[:-len(suffix)]
    descriptions=[]
    while True:
        term=next((t for t in DESCRIPTORS if stem.endswith(t)),None)
        if not term:
            break
        descriptions.append(DESCRIPTORS[term]);stem=stem[:-len(term)]
    return suffix,stem,descriptions


def translate_company(text):
    suffix,stem,descriptions=company_parts(text)
    return ' '.join([LEGAL_SUFFIXES[suffix],*descriptions,pinyin_name(stem)])


def document_terms(item,user_terms,target):
    from .document_academic import is_academic,TERMS
    has_chinese=any(p.get('source',item['source'])=='zh' for p in item['pages'])
    terms={**item['glossary'],**(DOCUMENT_TERMS if has_chinese and target=='vi' else {}),**user_terms}
    if target=='vi' and is_academic(item):
        terms={**TERMS,**terms}
    if has_chinese and target=='vi':
        for page in item['pages']:
            for block in page['blocks']:
                for match in re.finditer(COMPANY_RE,block['text']):
                    name=match.group()
                    terms.setdefault(name,translate_company(name))
                    _,stem,_=company_parts(name)
                    city=next((c for c in CITIES if stem.startswith(c)),None)
                    if city:
                        stem=stem[len(city):]
                    if 2<=len(stem)<=12:
                        terms.setdefault(stem,pinyin_name(stem))
    return terms


def normalize_field(text):
    """Correct one OCR error only in a known field label, never in its value."""
    for label in ('权利取得方式','著作权人','软件名称','权利范围'):
        prefix=text[:len(label)]
        if prefix!=label and len(prefix)==len(label) and SequenceMatcher(None,prefix,label).ratio()>=.8:
            return label+text[len(label):],True
    return text,False


def identifier_field(text):
    """Registration identifiers are data, not prose for the model to invent."""
    match=re.fullmatch(r'(证书号|登记号)\s*[:：]?\s*([^\d]*?)\s*(\d[\dA-Za-z/-]*)\s*号?',text.strip())
    if not match:
        return None
    label,prefix,number=match.groups()
    prefix=prefix.strip(' :：第')
    result=DOCUMENT_TERMS[label]+': '+number
    if prefix:
        result+=' (ký hiệu: '+pinyin_name(prefix)+')'
    return result


def bounded_translation(text,source,target,engine,terms,translate,depth=0):
    from .engine import TranslationTooLong
    try:
        return translate(text,source,target,engine,terms)
    except TranslationTooLong:
        if depth>=4 or len(text)<12:
            raise ValueError('Mô hình sinh lặp dù đã tự chia đoạn; chưa tạo được bản dịch đầy đủ cho tài liệu này.')
        # Split near the middle, at a sentence/word boundary where possible.
        middle=len(text)//2
        breaks=[m.end() for m in re.finditer(r'[\s。；，;,.!?]',text) if len(text)*.2<m.end()<len(text)*.8]
        cut=min(breaks,key=lambda x:abs(x-middle)) if breaks else middle
        return bounded_translation(text[:cut],source,target,engine,terms,translate,depth+1).strip()+' '+bounded_translation(text[cut:],source,target,engine,terms,translate,depth+1).strip()


def translate_document_batch(engine, blocks, source, target, glossary):
    from .engine import TranslationTooLong
    try:
        translations = engine.translate_segments([block['text'] for block in blocks], source, target, glossary, document=True)
    except TranslationTooLong:
        if len(blocks) == 1:
            raise ValueError(f'Mô hình chưa dịch hết vùng {blocks[0]["id"]}. Chưa tạo PDF cho lượt này.') from None
        middle = len(blocks) // 2
        translate_document_batch(engine, blocks[:middle], source, target, glossary)
        translate_document_batch(engine, blocks[middle:], source, target, glossary)
        return
    if len(translations) != len(blocks) or any(not result.strip() for result in translations):
        raise ValueError('Mô hình chưa trả đủ nội dung dịch cho tài liệu.')
    for block, result in zip(blocks, translations):
        block['translation'] = result
        block['translation_state'] = 'translated'
        block['issues'] = ['OCR chưa chắc chắn; cần đối chiếu chữ gốc.'] if block['confidence'] < 65 else []


def automatic_translation(item,target,engine,user_terms,translate):
    if getattr(engine, 'provider', None) in ('openai', 'chatgpt'):
        # Combine consecutive pages of the same language into bounded requests.
        for source, pages in groupby(item['pages'], key=lambda page: page.get('source', item['source'])):
            batch, chars = [], 0
            for page in pages:
                for block in page['blocks']:
                    if block['keep'] or source == target:
                        block['translation'] = block['text']
                        continue
                    length = len(block['text'])
                    if batch and (len(batch) >= 80 or chars + length > 6000):
                        translate_document_batch(engine, batch, source, target, user_terms)
                        batch, chars = [], 0
                    batch.append(block)
                    chars += length
            if batch:
                translate_document_batch(engine, batch, source, target, user_terms)
        item.update(target=target, automatic=True, untranslated_count=0, retained_names=0)
        return
    from .document_academic import is_academic,normalize,named_field
    terms=document_terms(item,user_terms,target)
    academic=is_academic(item)
    used_names=False
    for page in item['pages']:
        source=page.get('source',item['source'])
        for block in page['blocks']:
            block['issues']=[]
            if block['keep']:
                block['translation']=block['text'];continue
            text=block['text']
            block['translation_state']='translated'
            if academic and source in ('es','en'):
                normalized=normalize(text,source)
                if normalized!=text:
                    block['issues'].append('Đã chuẩn hóa nhãn học thuật OCR; không tự sửa tên người/mã số.')
                text=normalized
                field=named_field(text) if target=='vi' else None
                if field and not any(text.casefold()==key.casefold() for key in terms):
                    block['translation'],block['translation_state']=field
                    if block['translation_state']=='proper_name':
                        block['issues'].append('Giữ tên riêng theo OCR; chính tả chưa được xác minh.')
                    continue
            if source=='zh':
                text,corrected=normalize_field(text)
                if corrected:
                    block['issues'].append('Đã tự chuẩn hóa nhãn trường OCR; giá trị và mã giữ nguyên.')
                used_names=used_names or bool(re.search(COMPANY_RE,text))
            field=identifier_field(text) if source=='zh' and target=='vi' else None
            result=field if field else bounded_translation(text,source,target,engine,terms,translate).strip()
            if field and '(ký hiệu:' in field:
                block['issues'].append('Giữ số/mã từ OCR; ký hiệu chữ Hán được phiên âm, chưa xác minh với hồ sơ gốc.')
            words=result.lower().split()
            repeated=len(words)>12 and len(set(words))/len(words)<.35
            if not result or repeated:
                # A deterministic retry with smaller sentence context, not a
                # fabricated fallback or a hidden second translation service.
                pieces=[p for p in re.split(r'(?<=[。；;!?！？])|(?<=[，,])',text) if p.strip()]
                retry=' '.join(bounded_translation(p,source,target,engine,terms,translate).strip() for p in pieces)
                if retry and (not repeated or len(set(retry.lower().split()))/max(1,len(retry.split()))>=.35):
                    result=retry
                    block['issues'].append('Đã tự dịch lại theo câu ngắn.')
            if not result:
                if re.fullmatch(r'[A-Za-zÀ-ž\s.\-]{1,4}',text.strip()):
                    result=text
                    block['issues'].append('Mảnh chữ quá ngắn để dịch theo ngữ cảnh; giữ chữ gốc.')
                else:
                    raise ValueError(f'Trang {page.get("number","?")}, vùng {block["id"]}: mô hình không trả bản dịch; chưa tạo PDF hoàn chỉnh.')
            block['translation']=re.sub(r'\s+([,.;:!?])',r'\1',result)
            if block['confidence']<65:
                block['issues'].append('Chữ nguồn nhỏ/mờ; độ chính xác OCR còn hạn chế.')
    if used_names and target=='vi':
        item['warnings'].append('Tên riêng Trung Quốc dùng phiên âm Pinyin tự động; đây không phải tên pháp nhân tiếng Việt đã được xác minh.')
    unchanged=sum(any('giữ chữ gốc' in issue for issue in b['issues']) for p in item['pages'] for b in p['blocks'])
    item['untranslated_count']=unchanged
    item['retained_names']=sum(b.get('translation_state')=='proper_name' for p in item['pages'] for b in p['blocks'])
    if unchanged:
        item['warnings'].append(f'Có {unchanged} mảnh chữ rất ngắn mô hình không dịch được; giữ chữ gốc, không coi các mảnh này là đã dịch.')
    item['target']=target
    item['automatic']=True
