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


def detect_tables(data, width, height):
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
        if len(cells)>=2:
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


def _paragraph(paragraph,text,size=9.5,bold=False):
    paragraph.paragraph_format.space_before=Pt(0)
    paragraph.paragraph_format.space_after=Pt(2)
    paragraph.paragraph_format.line_spacing=1.06
    paragraph.paragraph_format.widow_control=True
    run=paragraph.add_run(_clean(text))
    run.font.name='Arial';run.font.size=Pt(size);run.font.bold=bold;run.font.color.rgb=RGBColor(0,0,0)
    letters=sum(c.isalpha() for c in text)
    if letters and sum('\u0600'<=c<='\u06ff' for c in text)>letters*.25:
        _element(paragraph._p.get_or_add_pPr(),'bidi',val=1)
        _element(run._r.get_or_add_rPr(),'rtl',val=1)
        _element(run._r.get_or_add_rPr(),'szCs',val=round(size*2))
        run._r.get_or_add_rPr().rFonts.set(qn('w:cs'),'Arial')
        paragraph.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    return paragraph


def _table(doc,widths,indent=0,bordered=True,rows=1):
    table=doc.add_table(rows=rows,cols=len(widths));table.autofit=False;table.alignment=WD_TABLE_ALIGNMENT.LEFT
    props=table._tbl.tblPr
    _element(props,'tblInd',w=int(Mm(max(0,indent)).twips),type='dxa')
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


def _ruled_table(doc,frame,regions,scale,page_width):
    cells=frame['cells'];tolerance=page_width*.007
    xs=_snap([v for cell in cells for v in (cell['x'],cell['x']+cell['width'])],tolerance)
    ys=_snap([v for cell in cells for v in (cell['y'],cell['y']+cell['height'])],tolerance)
    if len(xs)<2 or len(ys)<2 or len(xs)*len(ys)>1600:return False
    table=_table(doc,[(b-a)*scale for a,b in zip(xs,xs[1:])],xs[0]*scale,True,len(ys)-1)
    for row,a,b in zip(table.rows,ys,ys[1:]):
        row.height=Mm(max(2,(b-a)*scale));row.height_rule=WD_ROW_HEIGHT_RULE.AT_LEAST
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
        for index,region in enumerate(sorted(items,key=lambda r:(r['y'],r['x']))):
            p=target.paragraphs[0] if index==0 else target.add_paragraph()
            text=region['translation']
            if cell['width']<frame['width']*.33 and len(text)<130 and text.strip()!=region.get('text','').strip():text=clean_label(text)
            _paragraph(p,text)
            if cell['width']>frame['width']*.6 and len(region['translation'])<75:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    return True


def _outside(doc,regions,scale,page_width):
    if not regions:return
    groups=[]
    for region in sorted(regions,key=lambda r:(r['y'],r['x'])):
        if groups and region['y']<=groups[-1]['bottom']+2:
            groups[-1]['items'].append(region);groups[-1]['bottom']=max(groups[-1]['bottom'],region['y']+region['height'])
        else:groups.append({'items':[region],'bottom':region['y']+region['height']})
    for group in groups:
        items=group['items'];starts=_snap([r['x'] for r in items],page_width*.065)
        if len(starts)>1 and max(starts)-min(starts)>page_width*.1:
            # Borderless layout columns keep a side stamp beside footer prose.
            right=min(page_width,max(r['x']+r['width'] for r in items))
            starts=[*starts,right]
            widths=[max(8,(b-a)*scale) for a,b in zip(starts,starts[1:])]
            table=_table(doc,widths,starts[0]*scale,False)
            buckets=[[] for _ in widths]
            for region in items:buckets[min(range(len(widths)),key=lambda i:abs(starts[i]-region['x']))].append(region)
            for cell,bucket in zip(table.rows[0].cells,buckets):
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.TOP
                for j,region in enumerate(bucket):_paragraph(cell.paragraphs[0] if j==0 else cell.add_paragraph(),region['translation'],9)
        else:
            for region in items:
                p=doc.add_paragraph();_paragraph(p,region['translation'],9)
                available=max(55,region['width']*scale)
                left=min(region['x']*scale,180-available)
                p.paragraph_format.left_indent=Mm(max(0,left))
                p.paragraph_format.right_indent=Mm(max(0,180-left-available))
                if region['y']<page_width*.12 and len(region['translation'])<60:
                    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.left_indent=Mm(0);p.paragraph_format.right_indent=Mm(0)


def build_word(pages):
    doc=Document();section=doc.sections[0]
    section.page_width=Mm(210);section.page_height=Mm(297)
    section.top_margin=section.bottom_margin=Mm(14)
    section.left_margin=section.right_margin=Mm(15)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(9.5);normal.font.color.rgb=RGBColor(0,0,0)
    normal.paragraph_format.space_after=Pt(2)
    doc.core_properties.author='KUN GLOBAL';doc.core_properties.title='Bản dịch';doc.core_properties.comments=''
    for number,page in enumerate(pages):
        if number:doc.add_page_break()
        width=page['width'];scale=180/width
        regions=[r for r in page['regions'] if r.get('translation','').strip()]
        remaining=list(regions)
        for frame in sorted(page.get('tables',[]),key=lambda f:(f['y'],f['x'])):
            before=[r for r in remaining if r['y']+r['height']/2<frame['y']]
            _outside(doc,before,scale,width);remaining=[r for r in remaining if r not in before]
            inside=[r for r in remaining if frame['x']<=r['x']+r['width']/2<=frame['x']+frame['width']+(width*.035 if r['height']>r['width']*2 else 0)
                and frame['y']<=r['y']+r['height']/2<=frame['y']+frame['height']]
            if _ruled_table(doc,frame,inside,scale,width):remaining=[r for r in remaining if r not in inside]
        _outside(doc,remaining,scale,width)
    stream=io.BytesIO();doc.save(stream)
    return stream.getvalue()
