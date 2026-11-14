"""Find printed lines independently of OCR, then retry weak Latin/Gothic lines.

Coverage is a heuristic, not a correctness score. No page-specific transcriptions
or translations are stored here.
"""
import re
from functools import lru_cache
import subprocess
import cv2
import numpy as np
from PIL import Image,ImageOps

LATIN_OCR={'eng','spa','fra','deu','vie','ita','por','nld'}


@lru_cache(maxsize=1)
def fraktur_language():
    import pytesseract
    try:
        output=subprocess.run([pytesseract.pytesseract.tesseract_cmd,'--list-langs'],capture_output=True,text=True,timeout=5,check=True).stdout
        available={line.strip() for line in output.splitlines()}
        return next((name for name in ('Fraktur','script/Fraktur','frk') if name in available),None)
    except (OSError,subprocess.SubprocessError):
        return None


def line_regions(image,scale,zone,protected):
    gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY)
    ink=(gray<155).astype('uint8')*255
    mask=np.zeros_like(ink)
    x0,y0=round(zone['x']*scale),round(zone['y']*scale)
    x1,y1=round((zone['x']+zone['width'])*scale),round((zone['y']+zone['height'])*scale)
    mask[y0:y1,x0:x1]=ink[y0:y1,x0:x1]
    for r in protected+zone.get('exclude',[]):
        cv2.rectangle(mask,(round(r['x']*scale),round(r['y']*scale)),
                      (round((r['x']+r['width'])*scale),round((r['y']+r['height'])*scale)),0,-1)
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    photos=[(x,y,w,h) for x,y,w,h,a in stats[1:] if h>scale*80 and w>scale*35 and a/(w*h)>.22 and y>image.height*.2]
    chars=[];caps=[]
    for x,y,w,h,area in stats[1:]:
        if any(px<=x+w/2<=px+pw and py<=y+h/2<=py+ph for px,py,pw,ph in photos):continue
        if h>scale*55 and h<scale*150 and w<scale*90 and y<image.height*.25:
            caps.append((x,y,w,h));continue
        if scale*2.2<=h<=scale*60 and w>=scale*.4 and w<=scale*180 and area>=scale*scale*.15:
            chars.append({'x':x/scale,'y':y/scale,'width':w/scale,'height':h/scale,'area':area/scale**2})
    rows=[]
    for char in sorted(chars,key=lambda c:c['y']):
        row=next((r for r in rows if min(r['bottom'],char['y']+char['height'])-max(r['top'],char['y'])>min(r['bottom']-r['top'],char['height'])*.5),None)
        if row is None:row={'top':char['y'],'bottom':char['y']+char['height'],'chars':[]};rows.append(row)
        row['chars'].append(char);row['top']=min(row['top'],char['y']);row['bottom']=max(row['bottom'],char['y']+char['height'])
    regions=[]
    for row in rows:
        runs=[];run=[]
        median=float(np.median([c['height'] for c in row['chars']]))
        for char in sorted(row['chars'],key=lambda c:c['x']):
            if run and char['x']-run[-1]['x']-run[-1]['width']>max(18,median*2.5):runs.append(run);run=[]
            run.append(char)
        if run:runs.append(run)
        for run in runs:
            left=min(c['x'] for c in run);right=max(c['x']+c['width'] for c in run)
            top=min(c['y'] for c in run);bottom=max(c['y']+c['height'] for c in run)
            width=right-left;height=bottom-top;density=sum(c['area'] for c in run)/max(1,width*height)
            if width<height*1.6 or density<.08 or (len(run)<3 and width<height*3.5):continue
            for cx,cy,cw,ch in caps:
                cx,cy,cw,ch=cx/scale,cy/scale,cw/scale,ch/scale
                if cx<left and cx+cw>=left-35 and cy<bottom and cy+ch>top:
                    left=min(left,cx);top=min(top,cy);bottom=max(bottom,cy+ch)
            regions.append({'x':left,'y':top,'width':right-left,'height':bottom-top})
    unique=[]
    for region in sorted(regions,key=lambda r:r['width']*r['height'],reverse=True):
        if not any(overlap(region,r)>.6*min(region['width']*region['height'],r['width']*r['height']) for r in unique):unique.append(region)
    return sorted(unique,key=lambda r:(r['y'],r['x'])),mask


def overlap(a,b):
    return max(0,min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x']))*max(0,min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y']))


def confidence(words):
    size=sum(max(1,len(re.sub(r'\W','',w['text']))) for w in words)
    return sum(w['conf']*max(1,len(re.sub(r'\W','',w['text']))) for w in words)/max(1,size)


def recover_regions(image,scale,trained,zones,protected,words):
    if trained not in LATIN_OCR:return words,[]
    import pytesseract
    result=list(words);regions=[];attempts=0
    fraktur=fraktur_language()
    for zone_index,zone in enumerate(zones):
        detected,ink=line_regions(image,scale,zone,protected)
        for region in detected:
            region['zone']=zone_index
            old=[w for w in result if w['zone']==zone_index and overlap(w,region)>w['width']*w['height']*.5]
            old_score=confidence(old)
            covered=sum(overlap(w,region) for w in old if w['conf']>=40)/max(1,region['width']*region['height'])
            native_covered=zone.get('native_words') is not None and covered>=.6 and old_score>=95
            retry=not native_covered and (covered<.75 or old_score<70 or region['height']>13 or len(old)<=3)
            selected=old;method='page-ocr'
            if retry and attempts<28:
                attempts+=1
                pad=2
                left=max(0,region['x']-pad);top=max(0,region['y']-pad)
                right=min(image.width/scale,region['x']+region['width']+pad)
                bottom=min(image.height/scale,region['y']+region['height']+pad)
                crop=image.crop((round(left*scale),round(top*scale),round(right*scale),round(bottom*scale)))
                # A white margin helps line mode without rescaling source boxes.
                margin=16
                prepared=ImageOps.expand(ImageOps.autocontrast(ImageOps.grayscale(crop)),border=margin,fill=255)
                languages=[trained]+([fraktur] if fraktur and (region['height']>11 or old_score<60) else [])
                best_score=old_score
                for lang in languages:
                    try:
                        d=pytesseract.image_to_data(prepared,lang=lang,config='--psm 7',output_type=pytesseract.Output.DICT,timeout=12)
                    except RuntimeError:
                        continue
                    candidate=[]
                    for i,text in enumerate(d['text']):
                        if not text.strip() or float(d['conf'][i])<0:continue
                        x,y,w,h=[float(d[k][i]) for k in ('left','top','width','height')]
                        candidate.append({'text':text.strip(),'x':left+(x-margin)/scale,'y':top+(y-margin)/scale,'width':w/scale,'height':h/scale,'conf':float(d['conf'][i]),'zone':zone_index})
                    score=confidence(candidate)
                    old_letters=sum(len(re.findall(r'[^\W\d_]',w['text'])) for w in old)
                    new_letters=sum(len(re.findall(r'[^\W\d_]',w['text'])) for w in candidate)
                    enough_text=not old or new_letters>=old_letters*.8
                    if candidate and enough_text and (score>best_score+3 or not selected and score>=40):
                        selected=candidate;best_score=score;method='regional-fraktur' if lang==fraktur else 'regional-ocr'
                if selected and confidence(selected)>=40:
                    result=[w for w in result if w not in old]
                    for w in selected:w['region']=dict(region);w['ocr_method']=method
                    result.extend(selected)
            score=confidence(selected)
            region['confidence']=round(score,1)
            region['method']=method
            region['status']='uncertain' if score<55 or not selected else 'recognized'
            regions.append(region)
    return result,regions
