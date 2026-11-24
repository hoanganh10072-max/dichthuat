"""Editable A4 translation: white paper, native Word cells and plain text.

No source raster, seal, signature, or paper texture is embedded in the DOCX.
Rows grow with translated text; source coordinates guide columns and order.
"""
import io
import re

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

MIME='application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def detect_tables(data, width, height, *, single_frames=False):
    """Recover closed ruled cells locally; coordinates use the layout units."""
    import cv2
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        image=image.convert('RGB')
        image.thumbnail((1800,2200))
        gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY)
    h,w=gray.shape
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,13)
    horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(24,w//18),1)))
    vertical=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(20,h//35))))
    mask=cv2.morphologyEx(cv2.bitwise_or(horizontal,vertical),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:return []
    result=[]
    for i,contour in enumerate(contours):
        if hierarchy[0][i][3]!=-1:continue
        x,y,bw,bh=cv2.boundingRect(contour)
        if bw<w*.25 or bh<h*.055:continue
        cells=[]
        for j,child in enumerate(contours):
            if hierarchy[0][j][3]!=i:continue
            cx,cy,cw,ch=cv2.boundingRect(child)
            if cw<14 or ch<8 or cv2.contourArea(child)<cw*ch*.65:continue
            cells.append({'x':cx*width/w,'y':cy*height/h,'width':cw*width/w,'height':ch*height/h})
        if len(cells)>=(1 if single_frames else 2):
            result.append({'x':x*width/w,'y':y*height/h,'width':bw*width/w,'height':bh*height/h,'cells':cells})
    return sorted(result,key=lambda t:(t['y'],t['x']))[:30]


def _element(parent,name,**attributes):
    element=OxmlElement('w:'+name)
    for key,value in attributes.items():element.set(qn('w:'+key),str(value))
    parent.append(element)
    return element


def _clean(text):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',' ',text or '')


def clean_label(text):
    # A trilingual form repeats the same label three times after translation.
    # Only used for short, narrow field labels, never prose, names or values.
    matches=list(re.finditer(r'\w+',text,flags=re.UNICODE))
    words=[m.group().casefold() for m in matches]
    for prefix in range(min(3,len(words))):
        tail=words[prefix:]
        for copies in (3,2):
            if not tail or len(tail)%copies:continue
            length=len(tail)//copies
            if length and all(tail[i*length:(i+1)*length]==tail[:length] for i in range(copies)):
                end=matches[prefix+length-1].end()
                return text[:end]+(':' if ':' in text[:end+1] else '')
    return text


def _paragraph(paragraph,text,size=11,bold=False,text_format=None):
    formatting=text_format or {}
    role=formatting.get('role','paragraph')
    size=max(10,min(24,formatting.get('font_size_pt',size)))
    if role=='title':paragraph.style='Title'
    elif role=='heading':paragraph.style='Heading 2'
    paragraph.paragraph_format.space_before=Pt(0)
    paragraph.paragraph_format.space_after=Pt(6 if role=='title' else 4 if role=='heading' else 2)
    paragraph.paragraph_format.line_spacing=1.15
    paragraph.paragraph_format.widow_control=True
    paragraph.paragraph_format.keep_with_next=role in ('title','heading')
    if formatting.get('border'):
        borders=_element(paragraph._p.get_or_add_pPr(),'pBdr')
        for edge in ('top','left','bottom','right'):_element(borders,edge,val='single',sz=4,color='000000',space=2)
    run=paragraph.add_run(_clean(text))
    run.font.name='Arial';run.font.size=Pt(size);run.font.bold=formatting.get('bold',bold);run.font.color.rgb=RGBColor(0,0,0)
    run.font.italic=formatting.get('italic',False);run.font.underline=formatting.get('underline',False)
    properties=run._r.get_or_add_rPr()
    properties.rFonts.set(qn('w:cs'),'Arial');properties.rFonts.set(qn('w:eastAsia'),'Arial')
    _element(properties,'szCs',val=round(size*2))
    _element(properties,'bCs',val=int(bool(formatting.get('bold',bold))))
    _element(properties,'iCs',val=int(bool(formatting.get('italic',False))))
    letters=sum(c.isalpha() for c in text)
    if letters and sum('\u0600'<=c<='\u06ff' for c in text)>letters*.25:
        _element(paragraph._p.get_or_add_pPr(),'bidi',val=1)
        _element(run._r.get_or_add_rPr(),'rtl',val=1)
        run._r.get_or_add_rPr().rFonts.set(qn('w:cs'),'Arial')
        paragraph.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    alignment=formatting.get('alignment')
    if alignment in ('left','center','right','justify'):
        paragraph.alignment={'left':WD_ALIGN_PARAGRAPH.LEFT,'center':WD_ALIGN_PARAGRAPH.CENTER,'right':WD_ALIGN_PARAGRAPH.RIGHT,'justify':WD_ALIGN_PARAGRAPH.JUSTIFY}[alignment]
    return paragraph


def _table(doc,widths,indent=0,bordered=True,rows=1):
    table=doc.add_table(rows=rows,cols=len(widths));table.autofit=False
    # Adjacent DOCX tables are coalesced by Word/LibreOffice on import. A tiny
    # paragraph boundary prevents a later narrow box resizing preceding tables.
    separator=doc.add_paragraph();separator.paragraph_format.space_before=Pt(0)
    separator.paragraph_format.space_after=Pt(0);separator.paragraph_format.line_spacing=Pt(1)
    separator.add_run().font.size=Pt(1)
    table.alignment=WD_TABLE_ALIGNMENT.RIGHT if indent>80 and sum(widths)<100 else WD_TABLE_ALIGNMENT.CENTER if indent>10 else WD_TABLE_ALIGNMENT.LEFT
    props=table._tbl.tblPr
    preferred=props.find(qn('w:tblW'))
    preferred.set(qn('w:type'),'dxa');preferred.set(qn('w:w'),str(int(Mm(sum(widths)).twips)))
    # Use supported table alignment instead of large indents which some Word
    # renderers subtract from the first cell's usable width.
    _element(props,'tblInd',w=0,type='dxa')
    borders=_element(props,'tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        _element(borders,edge,val='single' if bordered else 'nil',sz=4,color='000000')
    for col,width in zip(table.columns,widths):col.width=Mm(width)
    for row in table.rows:
        for cell,width in zip(row.cells,widths):
            cell.width=Mm(width);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            margins=_element(cell._tc.get_or_add_tcPr(),'tcMar')
            for edge,value in [('top',22),('bottom',22),('left',45),('right',45)]:_element(margins,edge,w=value,type='dxa')
            _element(cell._tc.get_or_add_tcPr(),'shd',fill='FFFFFF',val='clear')
    return table


def _snap(values,tolerance):
    groups=[]
    for value in sorted(values):
        if groups and value-groups[-1][-1]<=tolerance:groups[-1].append(value)
        else:groups.append([value])
    return [sum(group)/len(group) for group in groups]


def _rows(regions):
    groups=[]
    for region in sorted(regions,key=lambda r:(r['y'],r['x'])):
        last=groups[-1] if groups else None
        overlap=0 if last is None else min(last['bottom'],region['y']+region['height'])-max(last['top'],region['y'])
        if last and overlap>min(region['height'],last['bottom']-last['top'])*.3:
            last['items'].append(region);last['bottom']=max(last['bottom'],region['y']+region['height'])
        else:groups.append({'items':[region],'top':region['y'],'bottom':region['y']+region['height']})
    return groups


def _columns(items):
    groups=[]
    for region in sorted(items,key=lambda r:r['x']):
        left,right=region['x'],region['x']+region['width']
        matches=[g for g in groups if min(g['right'],right)-max(g['left'],left)>.25*min(g['right']-g['left'],region['width'])]
        if matches:
            first=matches[0];first['items'].append(region)
            for other in matches[1:]:first['items'].extend(other['items']);groups.remove(other)
            first['left']=min(r['x'] for r in first['items']);first['right']=max(r['x']+r['width'] for r in first['items'])
        else:groups.append({'left':left,'right':right,'items':[region]})
    groups.sort(key=lambda g:g['left'])
    # A row of field labels must not become a dozen word-wide Word columns.
    while len(groups)>4:
        index=min(range(len(groups)-1),key=lambda i:groups[i+1]['left']-groups[i]['right'])
        a,b=groups[index:index+2];a['items'].extend(b['items']);a['right']=max(a['right'],b['right']);groups.pop(index+1)
    return groups


def _widths(raw,budget,minimum=20):
    minimum=min(minimum,budget/len(raw));extra=max(0,budget-minimum*len(raw))
    weights=[max(0,v-minimum) for v in raw];total=sum(weights)
    return [minimum+extra*(w/total if total else 1/len(raw)) for w in weights]


def _compact_end(cell):
    paragraph=cell.paragraphs[-1]
    if not paragraph.text:
        paragraph.paragraph_format.space_before=Pt(0);paragraph.paragraph_format.space_after=Pt(0)
        paragraph.paragraph_format.line_spacing=Pt(1)


def _dense_cell(target,items,width,flow_rows=None):
    # Open forms often have one enclosing cell with many inline fields.
    # Rebuild their baselines rather than stacking every OCR label vertically.
    target.paragraphs[0].paragraph_format.line_spacing=Pt(1)
    target.paragraphs[0].paragraph_format.space_after=Pt(0)
    by_id={r.get('id'):r for r in items}
    if flow_rows:
        rows=[[{'items':[by_id[i] for i in c['region_ids'] if i in by_id],'weight':c['weight']} for c in row['cells']] for row in flow_rows]
        included={r.get('id') for row in rows for cell in row for r in cell['items']}
        remaining=[r for r in items if r.get('id') not in included]
        rows.extend([[{**c,'weight':c['right']-c['left']} for c in _columns(row['items'])] for row in _rows(remaining)])
    else:rows=[[{**c,'weight':c['right']-c['left']} for c in _columns(row['items'])] for row in _rows(items)]
    for columns in rows:
        nested=target.add_table(rows=1,cols=len(columns));nested.autofit=False
        weights=[g['weight'] for g in columns];total=sum(weights)
        widths=_widths([v/total*max(25,width-2) for v in weights],max(25,width-2),minimum=22)
        preferred=nested._tbl.tblPr.find(qn('w:tblW'))
        preferred.set(qn('w:type'),'dxa');preferred.set(qn('w:w'),str(int(Mm(sum(widths)).twips)))
        for col,w in zip(nested.columns,widths):col.width=Mm(w)
        for cell,w,group in zip(nested.rows[0].cells,widths,columns):
            cell.width=Mm(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.TOP
            ordered=group['items'] if flow_rows else sorted(group['items'],key=lambda r:(r['y'],r['x']))
            for i,region in enumerate(ordered):
                p=cell.paragraphs[0] if flow_rows or i==0 else cell.add_paragraph()
                _paragraph(p,(' ' if flow_rows and i else '')+region['translation'],text_format=region.get('format'))
                p.style='Normal'
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.keep_with_next=False;p.paragraph_format.line_spacing=1.05
        if sum(len(r['translation']) for g in columns for r in g['items'])<1000:_element(nested.rows[0]._tr.get_or_add_trPr(),'cantSplit')
        _compact_end(target)


def _ruled_table(doc,frame,regions,scale,page_width):
    cells=frame['cells'];tolerance=page_width*.007
    xs=_snap([v for cell in cells for v in (cell['x'],cell['x']+cell['width'])],tolerance)
    ys=_snap([v for cell in cells for v in (cell['y'],cell['y']+cell['height'])],tolerance)
    if len(xs)<2 or len(ys)<2 or len(xs)*len(ys)>1600:return False
    dense=(len(regions)>35 or len(cells)>=6) and frame['width']*scale<140
    table_scale=180/frame['width'] if dense else scale
    raw=[(b-a)*table_scale for a,b in zip(xs,xs[1:])]
    widths=_widths(raw,min(180,sum(raw)),minimum=12)
    table=_table(doc,widths,0 if dense else xs[0]*scale,True,len(ys)-1)
    for index,(row,a,b) in enumerate(zip(table.rows,ys,ys[1:])):
        row.height=Mm(max(2,(b-a)*scale));row.height_rule=WD_ROW_HEIGHT_RULE.AT_LEAST
        if index<frame.get('header_rows',0):_element(row._tr.get_or_add_trPr(),'tblHeader',val=1)
    occupied=set();targets=[]
    for cell in sorted(cells,key=lambda c:-c['width']*c['height']):
        c0=min(range(len(xs)),key=lambda i:abs(xs[i]-cell['x']))
        c1=min(range(len(xs)),key=lambda i:abs(xs[i]-cell['x']-cell['width']))
        r0=min(range(len(ys)),key=lambda i:abs(ys[i]-cell['y']))
        r1=min(range(len(ys)),key=lambda i:abs(ys[i]-cell['y']-cell['height']))
        indices={(r,c) for r in range(r0,r1) for c in range(c0,c1)}
        if not indices or indices&occupied:continue
        target=table.cell(r0,c0).merge(table.cell(r1-1,c1-1)) if r1-r0>1 or c1-c0>1 else table.cell(r0,c0)
        occupied.update(indices);targets.append((cell,target,[]))
    if not targets:return False
    for region in regions:
        cx=region['x']+region['width']/2;cy=region['y']+region['height']/2
        found=next((entry for entry in targets if entry[0]['x']-3<=cx<=entry[0]['x']+entry[0]['width']+3 and entry[0]['y']-3<=cy<=entry[0]['y']+entry[0]['height']+3),None)
        if found is None:
            found=min(targets,key=lambda entry:((entry[0]['x']+entry[0]['width']/2-cx)/max(1,frame['width']))**2+((entry[0]['y']+entry[0]['height']/2-cy)/max(1,frame['height']))**2)
        found[2].append(region)
    for cell,target,items in targets:
        if len(items)>12:
            _dense_cell(target,items,sum(widths[min(range(len(xs)),key=lambda i:abs(xs[i]-cell['x'])):min(range(len(xs)),key=lambda i:abs(xs[i]-cell['x']-cell['width']))]),cell.get('flow_rows'))
            continue
        for index,region in enumerate(sorted(items,key=lambda r:(r['y'],r['x']))):
            p=target.paragraphs[0] if index==0 else target.add_paragraph()
            text=region['translation']
            if not region.get('format') and cell['width']<frame['width']*.33 and len(text)<130 and text.strip()!=region.get('text','').strip():text=clean_label(text)
            _paragraph(p,text,text_format=region.get('format'))
            p.style='Normal'
            if region.get('format'):p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.05
            if not region.get('format') and cell['width']>frame['width']*.6 and len(region['translation'])<75:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    return True


def _outside(doc,regions,scale,page_width,previous_bottom=None):
    if not regions:return previous_bottom
    groups=_rows(regions)
    for group in groups:
        items=group['items'];columns=_columns(items);starts=[g['left'] for g in columns]
        gap=0 if previous_bottom is None else min(7,max(0,(min(r['y'] for r in items)-previous_bottom)*scale))
        previous_bottom=group['bottom']
        long_prose=any(len(r['translation'])>250 and r.get('format',{}).get('role') in ('paragraph','footer') for r in items)
        if len(columns)>1 and not long_prose:
            if gap:
                spacer=doc.add_paragraph();spacer.paragraph_format.space_after=Mm(gap)
                spacer.paragraph_format.space_before=Pt(0);spacer.paragraph_format.line_spacing=Pt(1)
            # Borderless layout columns keep a side stamp beside footer prose.
            centered=all(r.get('format',{}).get('alignment')=='center' for r in items)
            anchors=[(g['left']+g['right'])/2 for g in columns]
            if centered:
                edges=[max(0,anchors[0]-(anchors[1]-anchors[0])/2),
                    *[(a+b)/2 for a,b in zip(anchors,anchors[1:])],
                    min(page_width,anchors[-1]+(anchors[-1]-anchors[-2])/2)]
            else:
                edges=[*starts,min(page_width,max(r['x']+r['width'] for r in items))]
            indent=edges[0]*scale
            if 180-indent<len(columns)*22:indent=0
            budget=min(180-indent,max((edges[-1]-edges[0])*scale,len(columns)*22))
            desired=sum(max(22,min(80,max(len(r['translation']) for r in g['items'])*1.2)) for g in columns)
            budget=min(180-indent,max(budget,desired))
            widths=_widths([(b-a)*scale for a,b in zip(edges,edges[1:])],budget,minimum=22)
            table=_table(doc,widths,indent,False)
            if sum(len(r['translation']) for r in items)<600:_element(table.rows[0]._tr.get_or_add_trPr(),'cantSplit')
            buckets=[g['items'] for g in columns]
            for cell,bucket in zip(table.rows[0].cells,buckets):
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.TOP
                for j,region in enumerate(bucket):_paragraph(cell.paragraphs[0] if j==0 else cell.add_paragraph(),region['translation'],text_format=region.get('format'))
        else:
            for index,region in enumerate(items):
                p=doc.add_paragraph();_paragraph(p,region['translation'],text_format=region.get('format'))
                if index==0:p.paragraph_format.space_before=Mm(gap)
                available=max(55,region['width']*scale)
                left=min(region['x']*scale,180-available)
                if len(region['translation'])>250 and region.get('format',{}).get('role') in ('paragraph','footer'):
                    available=180;left=0
                p.paragraph_format.left_indent=Mm(max(0,left))
                p.paragraph_format.right_indent=Mm(max(0,180-left-available))
                centered_on_page=region.get('format',{}).get('alignment')=='center' and abs(region['x']+region['width']/2-page_width/2)<page_width*.05
                if centered_on_page or (not region.get('format') and region['y']<page_width*.12 and len(region['translation'])<60):
                    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.left_indent=Mm(0);p.paragraph_format.right_indent=Mm(0)
    return previous_bottom


def build_word(pages):
    doc=Document();section=doc.sections[0]
    section.page_width=Mm(210);section.page_height=Mm(297)
    section.top_margin=section.bottom_margin=Mm(14)
    section.left_margin=section.right_margin=Mm(15)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(11);normal.font.color.rgb=RGBColor(0,0,0)
    # The python-docx template may carry a blue rule/theme in Title. Source
    # formatting must not acquire decoration from the installation template.
    for name in ('Normal','Title','Heading 1','Heading 2'):
        style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor(0,0,0)
        props=style.element.find(qn('w:pPr'))
        if props is not None:
            for border in list(props.findall(qn('w:pBdr'))):props.remove(border)
    normal.paragraph_format.space_after=Pt(2)
    doc.core_properties.author='KUN GLOBAL';doc.core_properties.title='Bản dịch';doc.core_properties.comments=''
    for number,page in enumerate(pages):
        if number:doc.add_page_break()
        width=page['width'];scale=180/width
        regions=[{**r,'format':dict(r.get('format') or {})} for r in page['regions'] if r.get('translation','').strip()]
        for r in regions:
            if r['height']>r['width']*2:r['format'].update(role='footer',alignment='right',font_size_pt=10,bold=False)
        for r in regions:
            if r['height']>r['width']*2:
                r['format'].update(role='footer',alignment='right')
        frames=[]
        for frame in page.get('tables',[]):
            if len(frame['cells'])==1:
                for r in regions:
                    if frame['x']<=r['x']+r['width']/2<=frame['x']+frame['width'] and frame['y']<=r['y']+r['height']/2<=frame['y']+frame['height']:r['format']['border']=True
            else:frames.append(frame)
        remaining=list(regions);cursor=None
        for frame in sorted(frames,key=lambda f:(f['y'],f['x'])):
            before=[r for r in remaining if r['y']+r['height']/2<frame['y']]
            cursor=_outside(doc,before,scale,width,cursor);remaining=[r for r in remaining if r not in before]
            inside=[r for r in remaining if r['height']<=r['width']*2 and frame['x']<=r['x']+r['width']/2<=frame['x']+frame['width']
                and frame['y']<=r['y']+r['height']/2<=frame['y']+frame['height']]
            if _ruled_table(doc,frame,inside,scale,width):
                remaining=[r for r in remaining if r not in inside];cursor=frame['y']+frame['height']
        _outside(doc,remaining,scale,width,cursor)
    stream=io.BytesIO();doc.save(stream)
    return stream.getvalue()
