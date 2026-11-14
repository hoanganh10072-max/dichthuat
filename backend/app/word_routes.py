import base64

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from starlette.concurrency import run_in_threadpool

from .word_export import build_word, detect_tables, MIME


class WordRegion(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    text:str=Field(default='',max_length=12000)
    translation:str=Field(min_length=1,max_length=12000)
    x:float=Field(ge=0,le=64000)
    y:float=Field(ge=0,le=64000)
    width:float=Field(gt=0,le=64000)
    height:float=Field(gt=0,le=64000)


class WordLayout(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    width:float=Field(gt=0,le=64000)
    height:float=Field(gt=0,le=64000)
    regions:list[WordRegion]=Field(min_length=1,max_length=1000)


class WordText(BaseModel):
    text:str=Field(min_length=1,max_length=150000)


def word_response(data):
    return Response(data,media_type=MIME,headers={'Content-Disposition':'attachment; filename="kun-global-translated.docx"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


def _image_export(data,filename,layout):
    from .image_translation import prepare_image
    (width,height),normalized,_,_=prepare_image(data,filename)
    if abs(width-layout.width)>1 or abs(height-layout.height)>1:
        raise ValueError('Bố cục không khớp ảnh gốc. Hãy dịch lại ảnh trước khi xuất Word.')
    if sum(len(r.translation) for r in layout.regions)>150000:
        raise ValueError('Bản Word vượt giới hạn nội dung.')
    for r in layout.regions:
        if not r.translation.strip() or r.x+r.width>width+1 or r.y+r.height>height+1:
            raise ValueError('Tọa độ hoặc nội dung bản dịch không hợp lệ.')
    page=layout.model_dump();page['tables']=detect_tables(normalized,width,height)
    return build_word([page])


def create_word_router(gate):
    router=APIRouter(prefix='/api')

    @router.post('/export-word')
    def export_text(request:WordText):
        if not request.text.strip():raise HTTPException(422,'Chưa có bản dịch để xuất Word.')
        regions=[{'text':'','translation':line,'x':0,'y':index*20,'width':600,'height':18}
            for index,line in enumerate(request.text.splitlines()) if line.strip()]
        return word_response(build_word([{'width':600,'height':800,'regions':regions}]))

    @router.post('/export-word-image')
    async def export_image(file:UploadFile=File(...),layout:str=Form(...)):
        try:data=await file.read(10*1024*1024+1)
        finally:await file.close()
        if len(data)>10*1024*1024:raise HTTPException(413,'Ảnh tối đa 10 MB.')
        try:
            parsed=WordLayout.model_validate_json(layout)
            async with gate:
                result=await run_in_threadpool(_image_export,data,file.filename or '',parsed)
            return word_response(result)
        except ValidationError:
            raise HTTPException(422,'Bố cục bản dịch Word không hợp lệ.') from None
        except (ValueError,OSError) as exc:
            raise HTTPException(422,str(exc)) from None

    return router


def document_word(item,edits):
    pages=[]
    for source in item['pages']:
        regions=[]
        for block in source['blocks']:
            edit=edits.get(block['id'])
            keep=edit.keep if edit is not None else block['keep']
            translation=(edit.translation if edit is not None else block['translation'])
            if keep:translation=edit.source_text if edit is not None and edit.source_text else block['text']
            if not translation.strip():raise ValueError('Tài liệu còn vùng chưa dịch. Hãy dịch lại trước khi xuất Word.')
            regions.append({**{k:block[k] for k in ('x','y','width','height','text')},'translation':translation})
        if not regions:continue
        preview=source.get('preview','')
        tables=detect_tables(base64.b64decode(preview.split(',',1)[1]),source['width'],source['height']) if preview.startswith('data:image/') else []
        pages.append({'width':source['width'],'height':source['height'],'regions':regions,'tables':tables})
    if not pages:raise ValueError('Tài liệu chưa có nội dung để xuất Word.')
    return build_word(pages)
