import base64
import copy
import io
import json
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from app.main import engine
from app.account_context import current_account
from app.document_layout import refine_dense_layout
from app.openai_engine import ProviderError
from app.word_export import build_word
from test_chatgpt import siwc,connected,stream_fixture


def dense_page():
    return {'number':1,'width':600,'height':840,'blocks':[{'id':str(i),'text':f'Source {i}',
        'translation':f'Field {i}','x':20+(i%2)*240,'y':30+(i//2)*20,'width':180,'height':12} for i in range(24)],
        'tables':[{'x':10,'y':10,'width':500,'height':400,'cells':[{'x':10,'y':10,'width':500,'height':400}]}]}


def plan():
    return {'groups':[{'id':'1-0-0','rows':[{'cells':[{'region_ids':[str(i),str(i+1)],'weight':1}]} for i in range(0,24,2)]}]}


@pytest.mark.parametrize('bad',[None,'missing','duplicate','unknown','weight','too-many-cells'])
def test_dense_layout_is_complete_atomic_and_text_unchanged(siwc,monkeypatch,bad):
    connected(siwc);page=dense_page();before=copy.deepcopy(page['blocks']);result=plan();bodies=[]
    cell=result['groups'][0]['rows'][0]['cells'][0]
    if bad=='missing':cell['region_ids'].pop()
    elif bad=='duplicate':cell['region_ids'].append('2')
    elif bad=='unknown':cell['region_ids'][0]='not-supplied'
    elif bad=='weight':cell['weight']=float('nan')
    elif bad=='too-many-cells':result['groups'][0]['rows'][0]['cells']*=5
    stream_fixture(monkeypatch,events=[{'type':'response.completed','response':{'status':'completed','output':[
        {'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}]}}],inspect_body=bodies.append)
    context=current_account.set(siwc[3])
    try:
        if bad:
            with pytest.raises(ProviderError):refine_dense_layout(engine,[page],b'%PDF-fixture',{'model':'fixture-model','tokens':{'access_token':'fixture-access'}})
            assert 'flow_rows' not in page['tables'][0]['cells'][0]
        else:
            assert refine_dense_layout(engine,[page],b'%PDF-fixture',{'model':'fixture-model','tokens':{'access_token':'fixture-access'}})
            assert page['tables'][0]['cells'][0]['flow_rows']==result['groups'][0]['rows']
    finally:current_account.reset(context)
    assert page['blocks']==before
    content=bodies[0]['input'][0]['content']
    assert base64.b64decode(content[1]['file_data'].split(',',1)[1])==b'%PDF-fixture'


def test_separate_table_boundaries_and_dense_cells_never_drop_text():
    page=dense_page();page['regions']=page.pop('blocks')
    page['tables'][0]['cells'][0]['flow_rows']=plan()['groups'][0]['rows']
    # IDs just beyond the model grouping must survive geometric reassignment.
    page['regions'].append({'id':'extra','text':'extra','translation':'EXTRA VALUE','x':30,'y':300,'width':200,'height':10})
    data=build_word([page]);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(io.BytesIO(data)) as z:root=ET.fromstring(z.read('word/document.xml'))
    text=''.join(n.text or '' for n in root.iter(ns+'t'))
    assert all(b['translation'] in text for b in page['regions'])
    body=root.find(ns+'body');tags=[n.tag for n in body]
    assert not any(a==b==ns+'tbl' for a,b in zip(tags,tags[1:]))
