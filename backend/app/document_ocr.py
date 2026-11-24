"""Local OCR of page text and embedded images; no external services."""
import base64
import io
from pathlib import Path
from math import isfinite

import cv2
import numpy as np
from PIL import Image, ImageDraw


def protected_marks(image, scale):
    """Conservative detection of red seals and dense square machine codes.

    This does not identify every signature/seal. It deliberately leaves the
    lettering inside detected seals alone; ordinary image text is still OCR'd.
    """
    rgb=np.asarray(image.convert('RGB'))
    rects=[]
    red=((rgb[:,:,0].astype(int)>rgb[:,:,1].astype(int)+35)
         & (rgb[:,:,0].astype(int)>rgb[:,:,2].astype(int)+25)
         & (rgb[:,:,0]>110)).astype('uint8')*255
    joined=cv2.dilate(red,np.ones((max(3,round(scale*2)),)*2,np.uint8))
    count,_,stats,_=cv2.connectedComponentsWithStats(joined)
    for x,y,w,h,area in stats[1:]:
        if min(w,h)>scale*15 and .4<w/h<2.5 and area>scale*scale*20:
            rects.append((x-2,y-2,x+w+2,y+h+2,'seal'))
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    cascade=Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'
    if cascade.is_file():
        small_scale=min(1,1000/max(image.size))
        small=cv2.resize(gray,None,fx=small_scale,fy=small_scale)
        faces=cv2.CascadeClassifier(str(cascade)).detectMultiScale(small,scaleFactor=1.1,minNeighbors=6,minSize=(25,25))
        for fx,fy,fw,fh in faces:
            fx,fy,fw,fh=fx/small_scale,fy/small_scale,fw/small_scale,fh/small_scale
            rects.append((fx-fw*.35,fy-fh*.4,fx+fw*1.35,fy+fh*2.6,'photo'))
    blue=((rgb[:,:,2].astype(int)>rgb[:,:,0].astype(int)+35)
          & (rgb[:,:,2].astype(int)>rgb[:,:,1].astype(int)+12)
          & (rgb[:,:,0]<170)&(rgb[:,:,2]>100)).astype('uint8')*255
    # Blue translator/notary stamps must be protected too. A circular ring is
    # required so ordinary blue diploma lettering is still translated.
    ring_scale=min(1,1800/max(image.size))
    ring=cv2.resize(blue,None,fx=ring_scale,fy=ring_scale)
    circles=cv2.HoughCircles(cv2.GaussianBlur(ring,(5,5),0),cv2.HOUGH_GRADIENT,1.2,
        minDist=max(10,scale*ring_scale*15),param1=100,param2=22,
        minRadius=max(8,round(scale*ring_scale*12)),maxRadius=max(9,round(scale*ring_scale*55)))
    if circles is not None:
        joined_blue=cv2.dilate(blue,np.ones((max(3,round(scale*3)),)*2,np.uint8))
        _,_,blue_stats,_=cv2.connectedComponentsWithStats(joined_blue)
        for cx,cy,radius in circles[0]/ring_scale:
            if cy<image.height*.25:
                continue
            theta=np.linspace(0,2*np.pi,128,endpoint=False)
            def coverage(r):
                hits=np.zeros(128,dtype=bool)
                for delta in (-2,0,2):
                    xs=np.clip(np.rint(cx+(r+delta)*np.cos(theta)).astype(int),0,image.width-1)
                    ys=np.clip(np.rint(cy+(r+delta)*np.sin(theta)).astype(int),0,image.height-1)
                    hits|=blue[ys,xs]>0
                return hits.mean()
            if coverage(radius)<.55 or coverage(radius*.72)<.4:
                continue
            candidates=[(x,y,w,h) for x,y,w,h,area in blue_stats[1:]
                        if x<cx<x+w and y<cy<y+h and w<scale*150 and h<scale*250]
            if candidates:
                x,y,w,h=max(candidates,key=lambda r:r[2]*r[3])
                # Printed lines immediately below the circular seal belong to
                # the same blue stamp. Keep them with the graphic, rather than
                # translating them into a vertical stack over its signature.
                left,right,top,bottom=x,x+w,y,y+h
                for bx,by,bw,bh,area in sorted(blue_stats[1:],key=lambda s:s[1]):
                    if by>=top and by<=bottom+scale*12 and by+bh>bottom and bx<cx+radius*1.5 and bx+bw>cx-radius*1.5 and bw<scale*150 and by+bh-top<scale*250:
                        left=min(left,bx);right=max(right,bx+bw);bottom=max(bottom,by+bh)
                x,y,w,h=left,top,right-left,bottom-top
                rects.append((x-3,y-3,x+w+3,y+h+3,'seal'))
            else:
                rects.append((cx-radius-3,cy-radius-3,cx+radius+3,cy+radius+3,'seal'))
    detector=cv2.QRCodeDetector()
    ok,points=detector.detectMulti(gray)
    if ok:
        for p in points:
            rects.append((p[:,0].min()-4,p[:,1].min()-4,p[:,0].max()+4,p[:,1].max()+4,'code'))
    ok,points=cv2.barcode_BarcodeDetector().detect(gray)
    if ok:
        for p in points.reshape(-1,4,2):
            rects.append((p[:,0].min()-4,p[:,1].min()-4,p[:,0].max()+4,p[:,1].max()+4,'code'))
    # Also protect dense matrix/stacked codes that are not QR codes.
    dark=(gray<90).astype('uint8')*255
    connected=cv2.dilate(dark,np.ones((3,3),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(connected)
    for x,y,w,h,_ in stats[1:]:
        if min(w,h)>scale*15 and .35<w/h<3 and w*h<image.width*image.height*.08:
            tile=dark[y:y+h,x:x+w]>0
            # A large Chinese character is dense and square too. Machine codes
            # have many alternating runs in both axes; density alone is unsafe.
            horizontal=np.median(np.count_nonzero(np.diff(tile,axis=1),axis=1))
            vertical=np.median(np.count_nonzero(np.diff(tile,axis=0),axis=0))
            if tile.mean()>.26 and horizontal>14 and vertical>5:
                rects.append((x-3,y-3,x+w+3,y+h+3,'code'))
    result=[]
    for left,top,right,bottom,kind in rects:
        if kind=='code':
            # Include quiet zones and edge bars, which may be disconnected
            # from the dense centre of stacked codes.
            left-=scale*7;right+=scale*7;top-=scale*2;bottom+=scale*2
        left=max(0,float(left));top=max(0,float(top))
        right=min(image.width,float(right));bottom=min(image.height,float(bottom))
        if any(left>=r['x']*scale and top>=r['y']*scale and right<=(r['x']+r['width'])*scale and bottom<=(r['y']+r['height'])*scale for r in result):
            continue
        result.append({'x':left/scale,'y':top/scale,'width':(right-left)/scale,'height':(bottom-top)/scale,'kind':kind})
    return result


def native_page_words(page):
    """Use readable PDF text with its coordinates, falling back for broken fonts."""
    raw=page.dedupe_chars().extract_words()
    text=' '.join(word['text'] for word in raw)
    if sum(char.isalpha() for char in text)<3 or any(
        char=='\ufffd' or '\ue000'<=char<='\uf8ff' or (not char.isprintable() and not char.isspace())
        for char in text
    ):
        return None
    words=[]
    for word in raw:
        x,y,right,bottom=(float(word[key]) for key in ('x0','top','x1','bottom'))
        if not word.get('upright',True) or not all(isfinite(value) for value in (x,y,right,bottom)):
            return None
        if x<0 or y<0 or right>page.width+1 or bottom>page.height+1 or right<=x or bottom<=y:
            return None
        words.append({'text':word['text'],'x':x,'y':y,'width':right-x,'height':bottom-y,'conf':100})
    return words


def ocr_words(image,scale,trained,zones,protected):
    import pytesseract
    words=[]
    for zone_index,zone in enumerate(zones):
        exclusions=protected+(zone.get('exclude') or [])
        if zone.get('native_words') is not None:
            words.extend({**word,'zone':zone_index} for word in zone['native_words'] if not any(
                word['x']<rect['x']+rect['width'] and word['x']+word['width']>rect['x']
                and word['y']<rect['y']+rect['height'] and word['y']+word['height']>rect['y']
                for rect in exclusions))
            continue
        crop=image.crop((round(zone['x']*scale),round(zone['y']*scale),round((zone['x']+zone['width'])*scale),round((zone['y']+zone['height'])*scale)))
        if zone['image']:
            # Suppress pale blue patterns and colored borders before OCR.
            rgb=np.asarray(crop)
            darkest=rgb.min(axis=2); lightest=rgb.max(axis=2)
            if zone.get('read_color') or trained in ('spa','fra','deu','eng','vie'):
                # Diplomas often use dark blue type. Do not discard it as an
                # ornamental border just because the ink is saturated.
                ink=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)<155
            else:
                ink=(darkest<145)&((lightest.astype(int)-darkest.astype(int))<70)
            crop=Image.fromarray(np.where(ink,0,255).astype('uint8')).convert('RGB')
        drawing=ImageDraw.Draw(crop)
        for rect in exclusions:
            drawing.rectangle(((rect['x']-zone['x'])*scale,(rect['y']-zone['y'])*scale,
                               (rect['x']+rect['width']-zone['x'])*scale,(rect['y']+rect['height']-zone['y'])*scale),fill='white')
        d=pytesseract.image_to_data(crop,lang=trained,config='--psm 11' if zone['image'] else '--psm 6',output_type=pytesseract.Output.DICT,timeout=60)
        for i,word in enumerate(d['text']):
            if not word.strip() or float(d['conf'][i])<0:
                continue
            x,y,w,h=[float(d[k][i])/scale for k in ('left','top','width','height')]
            x+=zone['x'];y+=zone['y']
            # Sparse OCR can mistake ornate borders for tiny Han characters.
            # Keep low-confidence words inside real lines for review, rather
            # than dropping a legal label just because two glyphs are unclear.
            if zone['image'] and not zone.get('read_color') and (min(w,h)<1.8 or h<4):
                continue
            if any(x<r['x']+r['width'] and x+w>r['x'] and y<r['y']+r['height'] and y+h>r['y'] for r in exclusions):
                continue
            words.append({'text':word.strip(),'x':x,'y':y,'width':w,'height':h,
                          'conf':float(d['conf'][i]),'zone':zone_index})
    return words


def repaired_background(image,scale,block,words):
    """Remove only OCR word rectangles locally, retaining surrounding artwork."""
    pad=1
    x=max(0,block['x']-pad);y=max(0,block['y']-pad)
    right=min(image.width/scale,block['x']+block['width']+pad)
    bottom=min(image.height/scale,block['y']+block['height']+pad)
    crop=image.crop((round(x*scale),round(y*scale),round(right*scale),round(bottom*scale))).convert('RGB')
    pixels=np.asarray(crop)
    # OCR word boxes can leave a stroke between word boxes. Remove all dark
    # ink in this tight text band, rather than leaving isolated source glyphs.
    mask_pixels=(cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY)<185).astype('uint8')*255
    mask_pixels=cv2.dilate(mask_pixels,np.ones((3,3),np.uint8))
    fixed=cv2.inpaint(pixels,mask_pixels,5,cv2.INPAINT_TELEA)
    # Large character masks can pull dark remnants back in from a tight OCR
    # boundary. Replace residual ink inside the erased area with nearby paper
    # color rather than exporting ghost characters behind the translation.
    paper=pixels[(mask_pixels==0)&(pixels.min(axis=2)>160)]
    if len(paper):
        color=np.median(paper,axis=0).astype('uint8')
        residue=(mask_pixels>0)&(cv2.cvtColor(fixed,cv2.COLOR_RGB2GRAY)<185)
        fixed[residue]=color
    output=io.BytesIO();Image.fromarray(fixed).save(output,format='PNG')
    return {'x':x,'y':y,'width':right-x,'height':bottom-y,'png':base64.b64encode(output.getvalue()).decode()}
