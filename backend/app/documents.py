"""Reviewable PDF translation. Source pages/graphics stay in the original PDF."""
import base64
import asyncio
import io
import re
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .account_context import current_account
from .openai_engine import ProviderError

PDF_LOCK = threading.Lock()
SESSIONS_LOCK = threading.Lock()
SESSIONS = {}
TTL = 20 * 60
DEFAULT_GLOSSARY = {
    '西贡-河内商业股份银行': 'Ngân hàng TMCP Sài Gòn - Hà Nội (SHB)',
    '计算机软件著作权登记证书': 'Giấy chứng nhận đăng ký quyền tác giả phần mềm máy tính',
    '中华人民共和国国家版权局': 'Cục Bản quyền Quốc gia nước Cộng hòa Nhân dân Trung Hoa',
    '核心银行': 'ngân hàng lõi', '著作权': 'quyền tác giả', '软件许可': 'giấy phép phần mềm',
    '授权确认函': 'thư xác nhận ủy quyền', '原始取得': 'có được ban đầu', '全部权利': 'toàn bộ quyền',
}


async def prune_sessions():
    while True:
        await asyncio.sleep(60)
        with SESSIONS_LOCK:
            now=time.monotonic()
            for key in list(SESSIONS):
                if SESSIONS[key]['expires']<now:
                    del SESSIONS[key]


def session(token):
    with SESSIONS_LOCK:
        now = time.monotonic()
        for key in list(SESSIONS):
            if SESSIONS[key]['expires'] < now:
                del SESSIONS[key]
        item = SESSIONS.get(token)
        if item is None:
            raise HTTPException(410, 'Phiên tài liệu đã hết hạn. Hãy tải lại PDF.')
        account = current_account.get()
        if account is not None and item.get('owner_id') != account['id']:
            raise HTTPException(404, 'Không tìm thấy tài liệu của tài khoản này.')
        item['expires'] = now + TTL
        return item


def download_link(item):
    if item.get('output_pdf') and item.get('output_revision'):
        return f'/api/documents/{item["id"]}/download?revision={item["output_revision"]}'
    return None


def public(item):
    result={k:item[k] for k in ('id','filename','source','warnings','glossary')}
    result['pages']=[{**p,'blocks':[{k:v for k,v in b.items() if k!='background'} for b in p['blocks']]} for p in item['pages']]
    result['automatic']=item.get('automatic',False)
    result['languages']=item.get('languages',[item['source']])
    result['untranslated_count']=item.get('untranslated_count',0)
    result['ocr_unread_count']=item.get('ocr_unread_count',0)
    result['retained_names']=item.get('retained_names',0)
    result['overflow_count']=item.get('overflow_count',0)
    result['output_policy']=item.get('output_policy')
    result['download_url']=download_link(item)
    return result


def intersects(a, b):
    return a['x'] < b['x']+b['width'] and a['x']+a['width'] > b['x'] and a['y'] < b['y']+b['height'] and a['y']+a['height'] > b['y']


def inspect_pdf(data, filename, source, preserve_images=False):
    import pdfplumber
    import pypdfium2 as pdfium
    import pytesseract
    from .extract import OCR_LANGS, validate_ocr_script
    from .engine import LANGUAGES
    from .document_ocr import protected_marks, ocr_words, repaired_background, native_page_words
    from pypdf import PdfReader
    if source not in LANGUAGES and source != 'auto':
        raise ValueError('Ngôn ngữ nguồn không hợp lệ.')
    check=PdfReader(io.BytesIO(data))
    if check.is_encrypted:
        raise ValueError('PDF có mật khẩu chưa được hỗ trợ trong chế độ giữ form.')
    if check.get_fields() or any(a.get_object().get('/Subtype')=='/Widget' for p in check.pages for a in p.get('/Annots',[])):
        raise ValueError('PDF có trường điền/chữ ký tương tác chưa được hỗ trợ. Chế độ này dành cho trang PDF tĩnh; không làm mất trường form hoặc chữ ký của file gốc.')
    pages = []
    auto_source=source=='auto'
    installed=pytesseract.get_languages(config='')
    with PDF_LOCK, pdfplumber.open(io.BytesIO(data)) as pdf, closing(pdfium.PdfDocument(data)) as renderer:
        if not 1 <= len(pdf.pages) <= 10:
            raise ValueError('Chế độ giữ form hỗ trợ PDF tối đa 10 trang mỗi lượt.')
        if source=='auto':
            from .auto_ocr import detect_pdf_language
            source=detect_pdf_language(pdf,renderer,installed,OCR_LANGS)['code']
        for number, page in enumerate(pdf.pages):
            width, height = float(page.width), float(page.height)
            scale = min(2.8, (8_000_000/(width*height))**.5)
            rendered = renderer[number].render(scale=scale)
            image = rendered.to_pil().convert('RGB')
            embedded=[]
            for graphic in page.images:
                if graphic['width']*graphic['height'] < width*height*.75 and graphic['width']>15 and graphic['height']>10:
                    rect={'x':max(0,float(graphic['x0'])),'y':max(0,float(graphic['top'])),
                          'width':float(graphic['width']),'height':float(graphic['height'])}
                    rect['width']=min(rect['width'],width-rect['x']);rect['height']=min(rect['height'],height-rect['y'])
                    if not any(intersects(rect,r) for r in embedded):
                        embedded.append(rect)
            protected=embedded if preserve_images else protected_marks(image,scale)
            full_scan=any(g['width']*g['height']>=width*height*.75 for g in page.images)
            page_source=source
            if auto_source:
                from .auto_ocr import detect_page_language
                native='' if full_scan else page.extract_text() or ''
                page_source=detect_page_language(image,installed,OCR_LANGS,source,native=native)['code']
            trained = OCR_LANGS[page_source]
            if trained not in installed:
                raise ValueError(f'Chưa cài OCR {trained}.')
            # OCR image crops separately so certificate rows cannot merge with
            # page paragraphs, and image text stays inside its own frame.
            zones=[{'x':0,'y':0,'width':width,'height':height,'image':full_scan,'exclude':embedded}]
            from .document_regions import recover_regions,overlap,LATIN_OCR,line_regions
            if not full_scan:
                native_words=native_page_words(page)
                if native_words and trained not in LATIN_OCR:
                    # Mixed text/vector pages still need OCR for outlined labels.
                    regions,_=line_regions(image,scale,zones[0],protected)
                    if any(sum(overlap(word,region) for word in native_words)<region['width']*region['height']*.6 for region in regions):
                        native_words=None
                zones[0]['native_words']=native_words
            if not preserve_images:
                zones.extend({**r,'image':True} for r in embedded)
            words=ocr_words(image,scale,trained,zones,protected)
            words,detected_regions=recover_regions(image,scale,trained,zones,protected,words)
            # Group by geometric baseline, not Tesseract's paragraph IDs: the
            # sample's outlined Chinese text produced overlapping paragraphs.
            rows=[]
            for word in sorted(words,key=lambda w:(w['zone'],w['y'])):
                row=next((r for r in rows if r['zone']==word['zone'] and ((word.get('region') and any(w.get('region')==word['region'] for w in r['words'])) or min(r['bottom'],word['y']+word['height'])-max(r['top'],word['y'])>min(r['bottom']-r['top'],word['height'])*.45)),None)
                if row is None:
                    row={'top':word['y'],'bottom':word['y']+word['height'],'words':[],'zone':word['zone']}; rows.append(row)
                row['words'].append(word)
                row['top']=min(row['top'],word['y']);row['bottom']=max(row['bottom'],word['y']+word['height'])
            runs=[]
            for row in rows:
                run=[]
                for word in sorted(row['words'],key=lambda w:w['x']):
                    gap_blocked=run and any(r['x']>=run[-1]['x']+run[-1]['width'] and r['x']+r['width']<=word['x'] and r['y']<word['y']+word['height'] and r['y']+r['height']>word['y'] for r in protected)
                    separate_region=run and word.get('region') and run[-1].get('region') and word['region']['x']>=run[-1]['region']['x']+run[-1]['region']['width']
                    if run and (gap_blocked or separate_region or word['x']-run[-1]['x']-run[-1]['width']>max(35,word['height']*5)):
                        runs.append(run);run=[]
                    run.append(word)
                if run:runs.append(run)
            grouped=OrderedDict()
            for run in runs:
                x=min(w['x'] for w in run); y=min(w['y'] for w in run)
                right=max(w['x']+w['width'] for w in run); bottom=max(w['y']+w['height'] for w in run)
                for word in run:
                    if word.get('region'):
                        r=word['region'];x=min(x,r['x']);y=min(y,r['y'])
                        right=max(right,r['x']+r['width']);bottom=max(bottom,r['y']+r['height'])
                median=sorted(w['height'] for w in run)[len(run)//2]
                previous=next(reversed(grouped.values()),None) if grouped else None
                height_tolerance=.6 if page_source in ('es','en','fr','de','vi') else .3
                can_merge=previous and previous['zone']==run[0]['zone'] and y>=previous['bottom']-1 and y-previous['bottom']<median*2 and (abs(x-previous['x'])<35 or abs(right-previous['right'])<15) and abs(median-sorted(previous['heights'])[len(previous['heights'])//2])<median*height_tolerance
                if zones[run[0]['zone']]['image']:
                    can_merge=bool(can_merge and page_source in ('es','en','fr','de','vi') and y-previous['bottom']<median*.7 and previous.get('last_width',0)>zones[run[0]['zone']]['width']*.35)
                if can_merge and x-previous['x']>12 and previous.get('last_width',right-x)<(previous['right']-previous['x'])*.75:
                    can_merge=False
                key=len(grouped) if not can_merge else next(reversed(grouped))
                block=grouped.setdefault(key,{'words':[],'x':x,'y':y,'right':right,'bottom':bottom,'heights':[],'conf':[],'first_x':x,'zone':run[0]['zone'],'boxes':[]})
                block['boxes'].extend(run)
                block['last_width']=right-x
                block['words'].extend((0,w['text']) for w in run)
                block['x'],block['y'] = min(block['x'],x),min(block['y'],y)
                block['right'],block['bottom'] = max(block['right'],right),max(block['bottom'],bottom)
                block['heights'].extend(w['height'] for w in run);block['conf'].extend(w['conf'] for w in run)
            blocks=[]
            for index,b in enumerate(grouped.values()):
                if zones[b['zone']]['image'] and sum(b['conf'])/len(b['conf'])<40:
                    continue
                text=' '.join(word for _,word in b['words'])
                if page_source in ('zh','ja'):
                    text=re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])','',text)
                    text=re.sub(r'\s*-\s*','-',text)
                # Identifiers and company names default to the unchanged source.
                keep=bool(not any(c.isalpha() for c in text) or re.fullmatch(r'[A-Z]{2,12}',text)
                    or (re.fullmatch(r'[A-Za-z0-9_.:/%+-]+',text) and re.search(r'\d',text)))
                blocks.append({'id':f'{number}-{index}','text':text,'translation':text if keep else '',
                    'keep':keep,'x':b['x'],'y':b['y'],'width':b['right']-b['x'],'height':b['bottom']-b['y'],
                    'indent':max(0,b['first_x']-b['x']),
                    'font_size':max(7,min(26,sorted(b['heights'])[len(b['heights'])//2]*1.18)),
                    'confidence':round(sum(b['conf'])/len(b['conf']),1),'issues':[],'inside_image':zones[b['zone']]['image']})
                if blocks[-1]['inside_image']:
                    blocks[-1]['bounds']={k:zones[b['zone']][k] for k in ('x','y','width','height')}
                    if b['zone']:
                        # Keep translated fields inside the image's border.
                        inset=min(22,zones[b['zone']]['width']*.065)
                        blocks[-1]['bounds']['x']+=inset
                        blocks[-1]['bounds']['width']-=2*inset
                    blocks[-1]['background']=repaired_background(image,scale,blocks[-1],b['boxes'])
            if blocks:
                validate_ocr_script(' '.join(b['text'] for b in blocks),page_source)
                if full_scan:
                    edges=sorted(b['x']+b['width'] for b in blocks)
                    content_right=edges[min(len(edges)-1,int(len(edges)*.95))]
                    for b in blocks:b['content_right']=max(content_right,b['x']+b['width'])
            unread=[]
            for r in detected_regions:
                if r['status']=='uncertain' or not any(overlap(b,r)>r['width']*r['height']*.45 for b in blocks):
                    unread.append({k:r[k] for k in ('x','y','width','height','confidence')})
            preview=io.BytesIO(); image.thumbnail((1200,1700)); image.save(preview,format='JPEG',quality=85)
            pages.append({'number':number+1,'source':page_source,'unread_regions':unread,'coverage_evaluated':trained in LATIN_OCR,'width':width,'height':height,'preview':'data:image/jpeg;base64,'+base64.b64encode(preview.getvalue()).decode(),
                'protected':protected,'graphics':embedded,'blocks':blocks,'rules':[{'x0':float(l['x0']),'x1':float(l['x1']),'top':float(l['top']),'bottom':float(l['bottom']),'width':float(l.get('linewidth') or .5)} for l in page.edges if (abs(l['x1']-l['x0'])>25 and abs(l['bottom']-l['top'])<2) or (abs(l['bottom']-l['top'])>25 and abs(l['x1']-l['x0'])<2)]})
            rendered.close()
    if not any(p['blocks'] for p in pages):
        raise ValueError('Không đọc được chữ trong tài liệu. Thử bỏ chế độ giữ ảnh gốc hoặc dùng file rõ hơn.')
    if sum(len(b['text']) for p in pages for b in p['blocks']) > 24000:
        raise ValueError('Nội dung vượt 24.000 ký tự. Hãy chia PDF nhỏ hơn.')
    if sum(len(p['blocks']) for p in pages)>400:
        raise ValueError('PDF vượt 400 vùng chữ. Hãy chia tài liệu nhỏ hơn.')
    source=pages[0]['source']
    account = current_account.get()
    item={'id':uuid.uuid4().hex,'owner_id':account['id'] if account else None,'data':data,'filename':Path(filename).name,'source':source,'languages':list(dict.fromkeys(p['source'] for p in pages)),'pages':pages,
        'ocr_unread_count':sum(len(p['unread_regions']) for p in pages),
        'expires':time.monotonic()+TTL,'glossary':DEFAULT_GLOSSARY.copy() if source=='zh' else {},
        'warnings':['Bản dịch máy cần rà soát; mã và số được giữ gốc mặc định.',
                    'Mặc định dịch cả chữ trong ảnh. OCR có thể bỏ sót chữ quá nhỏ/mờ; hoa văn OCR kém được giữ nguyên. Dấu đỏ và mã máy được nhận diện để tránh ghi đè, nhưng có thể bỏ sót; kiểm tra bản xem trước.',
                    'Phiên chỉ giữ trong RAM, hết hạn sau 20 phút không thao tác. Không chỉnh file gốc.']}
    if item['ocr_unread_count']:
        item['warnings'].append(f'Còn {item["ocr_unread_count"]} vùng nghi là chữ chưa đọc rõ; PDF có thể còn chữ gốc ở các vùng này. Đây chưa phải bản dịch đầy đủ.')
    with SESSIONS_LOCK:
        now=time.monotonic()
        for key in list(SESSIONS):
            if SESSIONS[key]['expires']<now:
                del SESSIONS[key]
        if sum(s.get('owner_id')==item['owner_id'] for s in SESSIONS.values())>=3 or sum(len(s['data']) for s in SESSIONS.values())+len(data)>100*1024*1024:
            raise ValueError('Máy chủ đang giữ đủ phiên PDF. Đợi phiên cũ hết hạn rồi thử lại.')
        SESSIONS[item['id']]=item
    return public(item)


def translate_block(text,source,target,engine,glossary):
    if source==target:
        return text
    page_number=re.fullmatch(r'第\s*(\d+)\s*页',text)
    if page_number and target=='vi':
        return 'Trang '+page_number[1]
    rules=glossary if target=='vi' else {}
    pattern='('+'|'.join(re.escape(k) for k in sorted(rules,key=len,reverse=True))+r'|第\s*\d+\s*章|[A-Za-z][A-Za-z0-9_.-]*(?:\s+[A-Za-z][A-Za-z0-9_.-]*)*|\d[\dA-Za-z.,%/-]*)'
    # Preserve Latin identifiers only in CJK sources, not full English sentences.
    if source not in ('zh','ja','ko'):
        pattern='('+'|'.join(re.escape(k) for k in sorted(rules,key=len,reverse=True))+')' if rules else None
    if not pattern:
        return engine.translate(text,source,target,document=True)[0]
    output=[]
    folded_rules={k.casefold():v for k,v in rules.items()}
    for part in re.split(pattern,text,flags=re.IGNORECASE):
        if not part:
            continue
        if part.casefold() in folded_rules:
            output.append(folded_rules[part.casefold()])
        elif target=='vi' and re.fullmatch(r'第\s*\d+\s*章',part):
            output.append('Chương '+re.search(r'\d+',part)[0])
        elif not any(c.isalpha() for c in part) or (source in ('zh','ja','ko') and re.fullmatch(r'[A-Za-z0-9_. ,%/-]+',part)):
            output.append(part)
        else:
            output.append(engine.translate(part,source,target,document=True)[0])
    return ' '.join(output).strip()


def append_translation_pages(writer, entries, font):
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from .pdf_fonts import paragraph_markup, repair_unicode_maps

    stream = io.BytesIO()
    title = ParagraphStyle('AppendixTitle', fontName=font+'Bold', fontSize=16, leading=21, spaceAfter=14, keepWithNext=True)
    label = ParagraphStyle('AppendixLabel', fontName=font+'Bold', fontSize=10, leading=14, spaceBefore=9, keepWithNext=True)
    body = ParagraphStyle('AppendixBody', fontName=font, fontSize=11, leading=15, spaceAfter=8)
    story = [Paragraph('Phụ lục bản dịch', title)]
    for number, page, region, text in entries:
        story.append(Paragraph(f'[{number}] Trang gốc {page} · Vùng {region}', label))
        story.append(Paragraph(paragraph_markup(text), body))
    SimpleDocTemplate(stream, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=44, bottomMargin=44).build(story)
    appendix=PdfReader(io.BytesIO(stream.getvalue()))
    repair_unicode_maps(appendix)
    writer.append_pages_from_reader(appendix)


def export_pdf(item,edits,target,automatic=False):
    from pypdf import PdfReader,PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from .pdf_fonts import register_document_fonts, paragraph_markup, repair_unicode_maps
    from .output_policy import PDF_FORM_LANGUAGES
    if target not in PDF_FORM_LANGUAGES:
        raise ValueError('Xuất PDF giữ form hiện hỗ trợ Việt, Anh và các ngôn ngữ Latin/Nga. Ngôn ngữ khác cần bổ sung phông và kiểm tra dàn chữ.')
    font='SaengDoc'
    with PDF_LOCK:
        register_document_fonts()
        reader=PdfReader(io.BytesIO(item['data'])); writer=PdfWriter()
        overflow=[]
        for index,page_data in enumerate(item['pages']):
            page=reader.pages[index]
            # Transfer rotation to content so top-left OCR coordinates match.
            if page.rotation:
                page.transfer_rotation_to_content()
            stream=io.BytesIO(); c=canvas.Canvas(stream,pagesize=(page_data['width'],page_data['height']))
            all_blocks=page_data['blocks']
            image_previous={}
            # Erase all source image text before drawing any translations.
            # Neighbouring source boxes may overlap by a few pixels.
            for block in all_blocks:
                if (not edits.get(block['id'],{}).get('keep',block['keep']) or automatic and block.get('inside_image')) and block.get('background'):
                    patch=block['background']
                    c.drawImage(ImageReader(io.BytesIO(base64.b64decode(patch['png']))),patch['x'],page_data['height']-patch['y']-patch['height'],patch['width'],patch['height'])
            for region, block in enumerate(all_blocks, 1):
                edit=edits.get(block['id'],{})
                if edit.get('keep',block['keep']) and not (automatic and block.get('inside_image')):
                    continue
                text=edit.get('translation',block['translation']).strip()
                text=text.translate(str.maketrans({'。':'.','，':',','；':';','：':':','（':'(', '）':')','《':'"','》':'"','【':'[','】':']','、':','}))
                if not text:
                    raise ValueError('Có vùng chưa có bản dịch. Dịch/sửa vùng đó hoặc bật Giữ gốc.')
                markup=paragraph_markup(text,bold=block['font_size']>18)
                x,y,w,h=block['x'],block['y'],block['width'],block['height']
                bounds=block.get('bounds',{'x':35,'y':0,'width':page_data['width']-70,'height':page_data['height']-25})
                zone=tuple(bounds[k] for k in ('x','y','width','height'))
                source_y=y
                if automatic and block.get('inside_image'):
                    prior=image_previous.setdefault(zone,[])
                    y=max([y]+[r['bottom'] for r in prior if r['x']<x+w and r['right']>x])
                graphics=page_data['protected']+([] if block.get('inside_image') else page_data.get('graphics',[]))
                same_row=[b for b in all_blocks if b['id']!=block['id'] and b['y']<y+h and b['y']+b['height']>y]
                right=min([bounds['x']+bounds['width'],block.get('content_right',bounds['x']+bounds['width'])]+[b['x']-2 for b in same_row if b['x']>=x+w-3 and b['x']>x+w*.7]+[r['x']-3 for r in graphics if r['y']<y+h and r['y']+r['height']>y and r['x']>=x+w])
                if automatic and block.get('inside_image'):
                    # Nearby text in a neighbouring column also limits width,
                    # even when its baseline differs (e.g. a portrait caption).
                    neighbours=[b['x']-2 for b in all_blocks if b['id']!=block['id'] and b['x']>=x+w-3 and b['x']>x+w*.7 and b['width']>40 and abs(b['y']-source_y)<max(45,h*3)]
                    right=min([right]+neighbours)
                width=max(7,right-x) if automatic else max(w,right-x)
                obstacles=[b for b in all_blocks if b['id']!=block['id']]+graphics
                threshold=y+max(3,h*.3) if block.get('inside_image') else y+h
                gap=1 if block.get('inside_image') else 3
                bottom=min([bounds['y']+bounds['height'],y+max(h*2,h+25)]+[b['y']-gap for b in obstacles if b['y']>=threshold and b['x']<x+width and b['x']+b['width']>x])
                available=bottom-y if block.get('inside_image') else max(h,bottom-y)
                centered=abs(x+w/2-bounds['x']-bounds['width']/2)<15 and w>bounds['width']*.4 and not same_row and h<=block['font_size']*2.1
                right_aligned=x>bounds['x']+bounds['width']*(.6 if automatic and block.get('inside_image') else .4) and not centered
                if centered:
                    width=w; x=block['x']
                elif right_aligned:
                    left=max([bounds['x']]+[b['x']+b['width']+3 for b in same_row+graphics if b['x']+b['width']<=x and b['y']<y+h and b['y']+b['height']>y])
                    width=min(max(w,w*2),block['x']+w-left);x=block['x']+w-width
                if block['font_size']>18:
                    available=min(available,h)
                crossing_rules=[r['top']-y-1 for r in page_data.get('rules',[]) if abs(r['bottom']-r['top'])<2 and y+3<r['top']<y+h and r['x0']<x+width and r['x1']>x]
                if crossing_rules:
                    available=min(available,min(crossing_rules))
                allowances=[available]
                if automatic and block.get('inside_image'):
                    future=[b for b in all_blocks if b.get('bounds')==block.get('bounds') and b['y']>source_y+3 and b['x']<x+width and b['x']+b['width']>x]
                    limit=min([bounds['y']+bounds['height']]+[r['y']-2 for r in graphics if r['y']>=y and r['x']<x+width and r['x']+r['width']>x])
                    # Borrow blank space and move following rows down within the
                    # same image. Reserve a readable line for every later row.
                    expanded=limit-y-len(future)*8.05
                    allowances=[max(8.05,available),expanded] if expanded>available else [available]
                max_size=min(16 if automatic and block.get('inside_image') and block['font_size']>18 else 12 if automatic and block.get('inside_image') else 24,block['font_size'])
                fitted=False
                for allowed in allowances:
                    for half_points in range(int(max_size*2),13,-1):
                        size=half_points/2
                        alignment=1 if centered else 2 if right_aligned else 0
                        style=ParagraphStyle('cell',fontName=font+'Bold' if block['font_size']>18 else font,fontSize=size,leading=size*(1.15 if right_aligned or block.get('inside_image') else 1.2),alignment=alignment,firstLineIndent=min(35,block.get('indent',0)) if alignment==0 else 0,spaceAfter=0)
                        para=Paragraph(markup,style)
                        _,needed=para.wrap(width,allowed)
                        if needed<=allowed:
                            fitted=True
                            break
                    if fitted:
                        break
                if not fitted:
                    if not automatic:
                        raise ValueError(f'Không đủ khoảng trống để dàn bản dịch ở vùng {block["id"]} với cỡ chữ đọc được.')
                    number=len(overflow)+1
                    overflow.append((number,index+1,region,text))
                    block.pop('layout',None)
                    # Keep the page layout and use only the source box for a reference.
                    if not block.get('background'):
                        c.setFillColorRGB(1,1,1)
                        c.rect(block['x']-.5,page_data['height']-source_y-h-.5,w+1,h+1,stroke=0,fill=1)
                    marker=f'[{number}]'
                    if h>=8 and pdfmetrics.stringWidth(marker,font,7)<=w:
                        c.setFont(font,7);c.setFillColorRGB(0,0,0)
                        c.drawString(block['x'],page_data['height']-source_y-7,marker)
                    continue
                if automatic and centered and block['font_size']>18 and h>needed*1.5:
                    y+=(h-needed)/2
                if automatic and block.get('inside_image'):
                    image_previous[zone].append({'x':x,'right':x+width,'bottom':y+needed+1})
                block['layout']={'x':x,'y':y,'width':width,'height':needed,'font_size':size}
                if not block.get('background'):
                    c.setFillColorRGB(1,1,1)
                    c.rect(block['x']-.5,page_data['height']-y-h-.5,w+1,h+1,stroke=0,fill=1)
                    c.rect(x-.5,page_data['height']-y-needed-.5,width+1,needed+1,stroke=0,fill=1)
                c.setFillColorRGB(0,0,0)
                para.drawOn(c,x,page_data['height']-y-needed)
            # White text masks must not remove the original form's rules.
            c.setStrokeColorRGB(0,0,0)
            for rule in page_data.get('rules',[]):
                c.setLineWidth(rule['width'])
                c.line(rule['x0'],page_data['height']-rule['top'],rule['x1'],page_data['height']-rule['bottom'])
            if not any(b['y']+b['height']>page_data['height']-18 for b in all_blocks+page_data['protected']):
                c.setFont(font,6); c.setFillColorRGB(.35,.4,.35)
                c.drawString(10,7,'KUN GLOBAL - Bản dịch máy chưa đầy đủ: còn vùng OCR chưa rõ.' if item.get('ocr_unread_count') else 'KUN GLOBAL - Bản dịch máy tham khảo; đối chiếu bản gốc.')
            c.save()
            overlay=PdfReader(io.BytesIO(stream.getvalue()))
            repair_unicode_maps(overlay)
            page.merge_page(overlay.pages[0]); writer.add_page(page)
        if overflow:
            append_translation_pages(writer,overflow,font)
        output=io.BytesIO(); writer.write(output)
        item['overflow_count']=len(overflow)
        return output.getvalue()


class Edit(BaseModel):
    id:str
    source_text:str|None=Field(default=None,max_length=3000)
    translation:str=Field(default='',max_length=4000)
    keep:bool=False


class DocumentRequest(BaseModel):
    session_id:str=Field(max_length=64)
    target:str='vi'
    edits:list[Edit]=Field(default_factory=list,max_length=400)
    glossary:dict[str,str]=Field(default_factory=dict,max_length=60)
    automatic:bool=False


def create_document_router(engine):
    router=APIRouter(prefix='/api/documents')
    gate=threading.Lock()

    @router.post('/complete')
    def complete(request:DocumentRequest):
        from .document_translation import automatic_translation
        from .engine import LANGUAGES
        import copy
        if request.target not in LANGUAGES:
            raise HTTPException(422,'Ngôn ngữ đích không hợp lệ.')
        if any(not k.strip() or len(k)>200 or len(v)>500 for k,v in request.glossary.items()):
            raise HTTPException(422,'Thuật ngữ không hợp lệ.')
        if not gate.acquire(False):
            raise HTTPException(429,'Máy chủ đang xử lý PDF khác.')
        try:
            # Commit only a complete output, so failed retries do not replace an
            # earlier successful translation with a half-translated document.
            original=session(request.session_id)
            from .service_messages import access_message
            if engine.state != 'ready':
                raise HTTPException(409, access_message())
            item=copy.deepcopy({k:v for k,v in original.items() if k not in ('output_pdf','output_word','output_policy','translation_complete','output_revision')})
            edits={e.id:e for e in request.edits}
            ids={b['id'] for p in item['pages'] for b in p['blocks']}
            if any(key not in ids for key in edits) or sum(len(e.source_text or '') for e in request.edits)>24000:
                raise ValueError('Nội dung chỉnh sửa không hợp lệ.')
            for page in item['pages']:
                for block in page['blocks']:
                    if block['id'] in edits:
                        edit=edits[block['id']]
                        block['keep']=edit.keep
                        if edit.source_text is not None:
                            if not edit.source_text.strip():
                                raise ValueError('Nội dung OCR không được để trống.')
                            block['text']=edit.source_text.strip()
            automatic_translation(item,request.target,engine,request.glossary,translate_block)
            from .output_policy import PDF_FORM_LANGUAGES, document_output_policy
            item['target']=request.target
            item['translation_complete']=True
            if request.target not in PDF_FORM_LANGUAGES:
                from .word_routes import document_word
                item['output_word']=document_word(item,{})
                item.pop('output_revision',None)
                item['output_policy']=document_output_policy(item)
                with SESSIONS_LOCK:SESSIONS[item['id']]=item
                return {'document':public(item),'pages':[],'ready':True}
            output=export_pdf(item,{},request.target,automatic=True)
            previews=pdf_previews(output,len(item['pages']))
            item['output_pdf']=output
            item['output_revision']=uuid.uuid4().hex
            item['output_policy']=document_output_policy(item)
            with SESSIONS_LOCK:
                SESSIONS[item['id']]=item
            return {'document':public(item),'pages':previews,'ready':True}
        except HTTPException:
            raise
        except BlockingIOError as exc:
            raise HTTPException(429,str(exc))
        except ProviderError as exc:
            raise HTTPException(exc.status_code,str(exc))
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        except Exception:
            import logging
            logging.exception('Automatic PDF translation failed')
            raise HTTPException(503,'Chưa hoàn tất dịch tài liệu. Kiểm tra mô hình và thử lại; không có bản PDF hoàn chỉnh để tải.')
        finally:
            gate.release()

    @router.post('/analyze')
    def analyze(file:UploadFile=File(...),source:str=Form('auto'),preserve_images:bool=Form(False)):
        if not (file.filename or '').lower().endswith('.pdf'):
            raise HTTPException(422,'Chế độ giữ form hiện hỗ trợ PDF. DOCX/TXT dùng trích xuất văn bản.')
        data=file.file.read(30*1024*1024+1); file.file.close()
        if len(data)>30*1024*1024:
            raise HTTPException(413,'PDF giữ form tối đa 30 MB.')
        if not gate.acquire(False):
            raise HTTPException(429,'Máy chủ đang xử lý PDF khác. Vui lòng thử lại.')
        try:
            return inspect_pdf(data,file.filename,source,preserve_images)
        except HTTPException:
            raise
        except Exception as exc:
            logging_error = not isinstance(exc,ValueError)
            if logging_error:
                import logging
                logging.exception('PDF analysis failed')
            raise HTTPException(422,str(exc) if not logging_error else 'Không phân tích được PDF. Kiểm tra mật khẩu, định dạng và log máy chủ.')
        finally:
            gate.release()

    @router.post('/translate')
    def translate_document(request:DocumentRequest):
        from .engine import LANGUAGES
        item=session(request.session_id)
        if request.target not in LANGUAGES:
            raise HTTPException(422,'Ngôn ngữ đích không hợp lệ.')
        from .service_messages import access_message
        if engine.state != 'ready':
            raise HTTPException(409, access_message())
        if any(not k.strip() or len(k)>200 or len(v)>500 for k,v in request.glossary.items()):
            raise HTTPException(422,'Thuật ngữ không hợp lệ (nguồn ≤200, đích ≤500 ký tự).')
        if not gate.acquire(False):
            raise HTTPException(429,'Máy chủ đang xử lý PDF khác.')
        try:
            if sum(len(e.source_text or '') for e in request.edits)>24000:
                raise ValueError('Nội dung nguồn đã sửa vượt 24.000 ký tự.')
            edits={e.id:e for e in request.edits}
            for page in item['pages']:
                for block in page['blocks']:
                    if block['id'] in edits:
                        block['keep']=edits[block['id']].keep
                        if edits[block['id']].source_text is not None:
                            block['text']=edits[block['id']].source_text.strip()
                        if not block['text']:
                            raise ValueError('Nội dung nguồn không được để trống. Có thể chọn Giữ gốc thay thế.')
                    if block['keep']:
                        block['translation']=block['text']; continue
                    block['translation']=translate_block(block['text'],page.get('source',item['source']),request.target,engine,request.glossary)
                    words=block['translation'].lower().split()
                    block['issues']=[]
                    if len(words)>12 and len(set(words))/len(words)<.35:
                        block['issues'].append('Có dấu hiệu lặp từ; cần sửa trước khi xuất.')
                    if not block['translation'].strip():
                        block['issues'].append('Mô hình chưa trả bản dịch. Hãy kiểm tra chữ OCR và nhập bản dịch cho vùng này.')
                    elif request.target in ('vi','en','fr','de','es','id','ms','ru') and re.search(r'[\u3400-\u9fff\uac00-\ud7af\u3040-\u30ff]',block['translation']):
                        block['issues'].append('Bản dịch còn chữ nguồn hoặc tên riêng chưa chuyển ngữ. Hãy sửa/đặt thuật ngữ trước khi xuất PDF.')
                    if block['confidence']<65:
                        block['issues'].append('OCR có độ tin cậy thấp; đối chiếu ảnh gốc.')
            item['target']=request.target
            with SESSIONS_LOCK:
                item.pop('output_pdf',None)
                item.pop('output_revision',None)
            return public(item)
        except BlockingIOError as exc:
            raise HTTPException(429,str(exc))
        except Exception as exc:
            raise HTTPException(503,str(exc))
        finally:
            gate.release()

    @router.post('/export')
    def export(request:DocumentRequest):
        item=session(request.session_id)
        ids={b['id'] for p in item['pages'] for b in p['blocks']}
        if any(e.id not in ids for e in request.edits):
            raise HTTPException(422,'Mã vùng chữ không hợp lệ.')
        if item.get('target') and item['target']!=request.target:
            raise HTTPException(422,'Bạn đã đổi ngôn ngữ đích; hãy dịch lại tài liệu trước khi xuất.')
        if not gate.acquire(False):
            raise HTTPException(429,'Máy chủ đang xử lý PDF khác.')
        try:
            result=item['output_pdf'] if request.automatic and not request.edits and item.get('output_pdf') else export_pdf(item,{e.id:e.model_dump() for e in request.edits},request.target,request.automatic)
            with SESSIONS_LOCK:
                if result is not item.get('output_pdf') or not item.get('output_revision'):
                    item.update(output_pdf=result,output_revision=uuid.uuid4().hex,target=request.target)
                    item.pop('output_word',None)
                from .output_policy import document_output_policy
                item['output_policy']=document_output_policy(item)
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        finally:
            gate.release()
        return Response(result,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="saeng-translated.pdf"','Cache-Control':'no-store'})

    @router.post('/export-word')
    def export_word(request:DocumentRequest):
        from .word_routes import document_word, word_response
        import copy
        original=session(request.session_id)
        if original.get('target')!=request.target or not (original.get('output_pdf') or original.get('translation_complete')):
            raise HTTPException(409,'Hãy hoàn tất dịch sang ngôn ngữ đã chọn trước khi xuất Word.')
        ids={b['id'] for p in original['pages'] for b in p['blocks']}
        if any(e.id not in ids for e in request.edits):raise HTTPException(422,'Mã vùng chữ không hợp lệ.')
        if not gate.acquire(False):raise HTTPException(429,'Máy chủ đang xử lý tài liệu khác.')
        try:
            return word_response(original['output_word'] if not request.edits and original.get('output_word') else document_word(copy.deepcopy(original),{e.id:e for e in request.edits}))
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        finally:gate.release()

    @router.post('/preview')
    def preview(request:DocumentRequest):
        response=export(request)
        item=session(request.session_id)
        return {'pages':pdf_previews(response.body,len(item['pages'])),'overflow_count':item.get('overflow_count',0),
                'download_url':download_link(item),'output_policy':item.get('output_policy')}

    @router.get('/{session_id}/download')
    def download(session_id:str, revision:str=Query(min_length=1,max_length=64), inline:bool=False):
        item=session(session_id)
        with SESSIONS_LOCK:
            if not item.get('output_pdf') or revision!=item.get('output_revision'):
                raise HTTPException(409,'Liên kết tải đã thay đổi. Mở bản dịch mới nhất và tải lại.')
            output=item['output_pdf']
            suffix='-dich-ban-nhap.pdf' if item.get('ocr_unread_count') or item.get('untranslated_count') else '-dich.pdf'
            filename=(Path(item['filename']).stem or 'kun-global')+suffix
        disposition='inline' if inline else 'attachment'
        return Response(output,media_type='application/pdf',headers={
            'Content-Disposition':f'{disposition}; filename="kun-global-translated.pdf"; filename*=UTF-8\'\'{quote(filename,safe="")}',
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        })

    return router


def pdf_previews(data, page_limit):
    import pypdfium2 as pdfium
    previews=[]
    with PDF_LOCK, closing(pdfium.PdfDocument(data)) as pdf:
        for index in range(min(len(pdf),page_limit)):
            with closing(pdf[index]) as page, closing(page.render(scale=1.7)) as bitmap:
                image=bitmap.to_pil().convert('RGB'); stream=io.BytesIO(); image.save(stream,format='JPEG',quality=88)
                previews.append('data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode())
    return previews
