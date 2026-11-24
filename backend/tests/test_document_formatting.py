import io
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.document_file_translation import _text_format
from app.word_export import build_word
from app.word_routes import document_word


def style(role='paragraph',alignment='left',size=11,**changes):
    return dict(role=role,alignment=alignment,font_size_pt=size,**{'bold':False,'italic':False,'underline':False,**changes})


@pytest.mark.parametrize('bad',[None,{},style(size=True),style(size=500),style(size=float('nan')),
    {**style(),'alignment':'bogus'},{**style(),'bold':'true'},{**style(),'role':'script'}])
def test_invalid_source_format_rejected(bad):
    with pytest.raises(ValueError):_text_format({'format':bad})


def test_original_styles_survive_export_and_edits():
    title=style('title','center',18,bold=True)
    blocks=[dict(id='title',text='TITLE',translation='TIÊU ĐỀ TÀI LIỆU',keep=False,x=50,y=30,width=500,height=30,format=title),
        dict(id='heading',text='Section',translation='Nội dung hồ sơ',keep=False,x=50,y=90,width=400,height=20,format=style('heading','left',13,bold=True)),
        dict(id='value',text='Value',translation='Thông tin chi tiết',keep=False,x=50,y=140,width=400,height=40,format=style('value','right',11,italic=True,underline=True))]
    item={'pages':[dict(width=600,height=840,blocks=blocks,tables=[])]}
    doc=Document(io.BytesIO(document_word(item,{})))
    first=doc.paragraphs[0]
    assert first.text=='TIÊU ĐỀ TÀI LIỆU' and first.style.name=='Title'
    assert first.runs[0].bold and first.runs[0].font.size.pt==18
    assert first.alignment==WD_ALIGN_PARAGRAPH.CENTER and first.paragraph_format.keep_with_next
    assert 'pBdr' not in doc.styles['Title'].element.xml
    assert doc.paragraphs[1].style.name=='Heading 2'
    assert doc.paragraphs[1].paragraph_format.space_before.pt>0
    last=doc.paragraphs[2]
    assert last.alignment==WD_ALIGN_PARAGRAPH.RIGHT and last.runs[0].italic and last.runs[0].underline
    assert all(str(p.runs[0].font.color.rgb)=='000000' for p in doc.paragraphs)
    with ZipFile(io.BytesIO(document_word(item,{}))) as z:assert not any(n.startswith('word/media/') for n in z.namelist())


def test_table_headers_merge_columns_and_readable_expanding_text():
    page={'width':600,'height':840,'tables':[{'x':40,'y':100,'width':520,'height':160,'header_rows':1,'cells':[
        {'x':40,'y':100,'width':520,'height':40},
        {'x':40,'y':140,'width':160,'height':120},{'x':200,'y':140,'width':360,'height':120}]}],
        'regions':[dict(text='',translation='THÔNG TIN HỒ SƠ',x=60,y=110,width=480,height=20,format=style('heading','center',13,bold=True)),
            dict(text='',translation='Nhãn thông tin',x=50,y=150,width=140,height=40,format=style('label','left',9,bold=True)),
            dict(text='',translation='Bản dịch dài cần xuống dòng và giữ đủ toàn bộ nội dung. '*50,x=210,y=150,width=330,height=90,format=style('value','justify',11))]}
    data=build_word([page]);doc=Document(io.BytesIO(data));table=doc.tables[0]
    assert table.cell(0,0)._tc is table.cell(0,1)._tc
    assert table.cell(1,0).paragraphs[0].runs[0].font.size.pt==10
    assert table.cell(1,1).paragraphs[0].alignment==WD_ALIGN_PARAGRAPH.JUSTIFY
    assert len(table.cell(1,1).text)>2500
    with ZipFile(io.BytesIO(data)) as z:
        xml=z.read('word/document.xml').decode()
        assert 'tblHeader' in xml and 'hRule="atLeast"' in xml and 'hRule="exact"' not in xml


def test_centered_signature_columns_use_column_space_not_glyph_width():
    from docx.shared import Mm
    page={'width':600,'height':840,'regions':[
        dict(text='',translation='NGƯỜI ĐỀ NGHỊ',x=100,y=400,width=70,height=20,format=style('signature','center')),
        dict(text='',translation='NGƯỜI XÁC NHẬN',x=420,y=400,width=70,height=20,format=style('signature','center'))]}
    table=Document(io.BytesIO(build_word([page]))).tables[0]
    assert len(table.columns)==2 and all(c.width>Mm(70) for c in table.columns)
    assert table.cell(0,0).text=='NGƯỜI ĐỀ NGHỊ' and table.cell(0,1).text=='NGƯỜI XÁC NHẬN'
