import {useEffect,useRef,useState} from 'react';
import {Download,ExternalLink,FileText,LoaderCircle,Upload,WandSparkles} from 'lucide-react';
import './documents.css';
import './document-auto.css';
import {accountApi,accountFile} from './account-api';
import {PUBLIC_PREVIEW,PREVIEW_NOTICE} from './public-preview';
import DocumentWordPreview from './DocumentWordPreview';

type Block={id:string;text:string;translation:string;keep:boolean;confidence:number|null;issues:string[];inside_image?:boolean;x:number;y:number;width:number;height:number;format?:{role?:'title'|'heading'|'paragraph'|'label'|'value'|'footer'|'signature';alignment?:'left'|'center'|'right'|'justify';font_size_pt?:number;bold?:boolean;italic?:boolean;underline?:boolean}};
export type WordPage={number:number;source?:string;width:number;height:number;preview:string;blocks:Block[];tables?:{x:number;y:number;width:number;height:number;header_rows?:number;cells:{x:number;y:number;width:number;height:number;flow_rows?:{cells:{region_ids:string[];weight:number}[]}[]}[]}[]};
type Doc={id:string;filename:string;source:string;languages?:string[];ocr_unread_count?:number;pages:WordPage[];warnings:string[];glossary:Record<string,string>;automatic:boolean;translation_method?:string};
type Props={languages:{code:string;name:string}[];onBusy:(busy:boolean)=>void;onTextFile:(file:File,source:string,target:string)=>void;accountId:string;canTranslate:boolean};
const PROMPT_LANGUAGES:Record<string,string>={vi:'Việt',lo:'Lào',en:'Anh',th:'Thái',zh:'Trung',km:'Khmer',ja:'Nhật',ko:'Hàn',fr:'Pháp',de:'Đức',es:'Tây Ban Nha',ru:'Nga',id:'Indonesia',ms:'Mã Lai',my:'Myanmar',hi:'Hindi',it:'Ý',pt:'Bồ Đào Nha',nl:'Hà Lan',ar:'Ả Rập'};
function defaultPrompt(target:string){return `Áp dụng hướng dẫn Translator Pro. Dịch chuẩn toàn bộ văn bản trong tài liệu này sang tiếng ${PROMPT_LANGUAGES[target]||target} cho tôi, gồm cả chữ trong ảnh và trang scan. Giữ chính xác tên riêng, ngày tháng, số liệu và mã. Dựng lại định dạng gần bản gốc nhất: phân cấp tiêu đề, đoạn văn, căn lề, chữ đậm/nghiêng/gạch chân, cột, khung bảng và ô gộp. Giữ nhãn và giá trị đúng ô, đúng thứ tự; không dồn bảng thành đoạn văn. Xuất Word A4 nền trắng, chữ rõ ràng; không cần giữ nền màu hay hoa văn. Cho phép đoạn và ô giãn hoặc sang trang để không cắt chữ. Không tóm tắt hoặc bỏ sót nội dung. Đánh dấu phần không đọc rõ, không tự đoán.`;}
export default function DocumentWorkspace({languages,onBusy,onTextFile,canTranslate}:Props){
  const [source,setSource]=useState('auto'),[target,setTarget]=useState('vi');
  const [file,setFile]=useState<File|null>(null),[doc,setDoc]=useState<Doc|null>(null);
  const [localPreview,setLocalPreview]=useState<string|null>(null),[word,setWord]=useState<{url:string;filename:string}|null>(null);
  const [page,setPage]=useState(0),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const [edited,setEdited]=useState(false);
  const [completedTarget,setCompletedTarget]=useState<string|null>(null);
  const active=useRef(false);
  const hasTranslation=!!doc&&completedTarget===target;
  useEffect(()=>{if(!file){setLocalPreview(null);return;}const url=URL.createObjectURL(new Blob([file],{type:'application/pdf'}));setLocalPreview(url);return()=>URL.revokeObjectURL(url);},[file]);
  useEffect(()=>()=>{if(word)URL.revokeObjectURL(word.url);},[word]);
  function reset(){setDoc(null);setPage(0);setWord(null);setCompletedTarget(null);setEdited(false);setError('');}
  async function task(label:string,action:()=>Promise<void>){
    if(active.current)return;
    active.current=true;setBusy(label);onBusy(true);setError('');
    try{await action();}catch(e){setError(e instanceof Error?e.message:'Không xử lý được tài liệu. Hãy thử lại.');}
    finally{active.current=false;setBusy('');onBusy(false);}
  }
  function payload(document=doc,includeEdits=edited){
    if(!document)throw new Error('Chọn PDF và bấm Dịch tài liệu.');
    return {session_id:document.id,target,edits:includeEdits?document.pages.flatMap(p=>p.blocks.map(b=>({id:b.id,source_text:b.text,translation:b.translation,keep:b.keep}))):[]};
  }
  async function prepareWord(document:Doc,includeEdits:boolean){
    const blob=await accountFile('documents/export-word',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload(document,includeEdits))});
    const result={url:URL.createObjectURL(blob),filename:(document.filename.replace(/\.pdf$/i,'')||'kun-global')+'-ban-dich.docx'};setWord(result);return result;
  }
  function translateDocument(){
    if(PUBLIC_PREVIEW){setError(PREVIEW_NOTICE);return;}
    if(!canTranslate){setError('Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.');return;}
    void task('Đang chuẩn bị tài liệu gốc…',async()=>{
      if(!file)throw new Error('Chọn một file PDF trước.');
      if(!/\.pdf$/i.test(file.name))throw new Error('Chọn tài liệu PDF.');
      if(file.size>30*1024*1024)throw new Error('PDF tối đa 30 MB.');
      setWord(null);setCompletedTarget(null);
      let prepared=doc;
      if(!prepared){
        const form=new FormData();form.append('file',file);form.append('source',source);
        prepared=await accountApi('documents/prepare',{method:'POST',body:form}) as Doc;setDoc(prepared);setPage(0);
      }
      setBusy('Đang dịch toàn bộ tài liệu…');
      const result=await accountApi('documents/translate-original',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:prepared.id,target,prompt:defaultPrompt(target)})});
      setDoc(result.document);setCompletedTarget(target);setEdited(false);setBusy('Đang chuẩn bị file Word để tải…');await prepareWord(result.document,false);
    });
  }
  function downloadWord(){void task('Đang chuẩn bị Word…',async()=>{
    if(!doc||!hasTranslation)return;const output=word||await prepareWord(doc,edited);
    const link=document.createElement('a');link.href=output.url;link.download=output.filename;link.click();
  });}
  function edit(id:string,change:Partial<Block>){setWord(null);setEdited(true);setDoc(value=>value?{...value,pages:value.pages.map(p=>({...p,blocks:p.blocks.map(b=>b.id===id?{...b,...change}:b)}))}:null);}
  const current=doc?.pages[page];
  const sourceNames=doc?((doc.languages||[doc.source]).map(code=>languages.find(l=>l.code===code)?.name||code).join(' / ')||'Tự phát hiện từ tài liệu'):'';
  return <div className="document-workspace">
    <div className="document-intro"><FileText size={25}/><div><strong>Dịch tài liệu tự động</strong><p>Chọn PDF và ngôn ngữ đích để dịch sang Word · 30 MB / 10 trang.</p></div></div>
    <div className="document-setup">
      <label className="document-file"><Upload size={18}/>{file?.name||'Chọn tài liệu PDF gốc'}<input type="file" accept=".pdf" disabled={!!busy} onChange={e=>{
        const selected=e.currentTarget.files?.[0];e.currentTarget.value='';if(!selected)return;
        if(/\.(docx|txt)$/i.test(selected.name)){onTextFile(selected,source,target);return;}
        setFile(selected);reset();
      }}/></label>
      <label>Nguồn<select aria-label="Ngôn ngữ nguồn tài liệu" disabled={!!busy} value={source} onChange={e=>{setSource(e.target.value);reset();}}><option value="auto">Tự phát hiện</option>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
      <label>Đích<select aria-label="Ngôn ngữ đích tài liệu" disabled={!!busy} value={target} onChange={e=>{setTarget(e.target.value);setWord(null);setCompletedTarget(null);}}>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
      <button className="primary" disabled={!file||!!busy||!canTranslate} onClick={translateDocument}><WandSparkles size={17}/>Dịch tài liệu</button>
    </div>
    <p className="document-help">Dịch cả chữ trong ảnh và scan; dựng lại tiêu đề, căn lề, cột và khung bảng theo bản gốc trong Word A4 nền trắng. Chữ và ô tự giãn để giữ đủ nội dung. Kết quả hiển thị bên phải; tải Word để xem đầy đủ định dạng. Nội dung được xử lý tại máy chủ dịch.</p>
    {busy&&<div className="document-progress" role="status"><LoaderCircle className="spin" size={18}/>{busy}</div>}
    {error&&<div className="error" role="alert">{error}</div>}
    {doc&&<div className="document-toolbar"><span>{doc.pages.length} trang · {sourceNames}</span><select aria-label="Trang tài liệu" value={page} onChange={e=>setPage(Number(e.target.value))}>{doc.pages.map((p,i)=><option key={i} value={i}>Trang {p.number}</option>)}</select><button className="primary" disabled={!!busy||!hasTranslation} onClick={downloadWord}><Download size={16}/>Tải Word</button></div>}
    {word&&hasTranslation&&<p className="document-download-help" role="status">Word đã sẵn sàng. Chọn Tải Word để nhận toàn bộ bản dịch, với khung và bảng có thể chỉnh sửa.</p>}
    {hasTranslation&&!!doc?.warnings.length&&<details className="document-advanced"><summary>Ghi chú bản dịch ({doc.warnings.length})</summary>{doc.warnings.map((note,i)=><p className="document-help" key={i}>{note}</p>)}</details>}
    {!!doc?.ocr_unread_count&&<p className="document-review-warning">Có {doc.ocr_unread_count} vùng chữ chưa đọc rõ. Cần đối chiếu với PDF hoặc tải bản rõ hơn; ứng dụng không tự điền nội dung không đọc được.</p>}
    {(localPreview||current)&&<div className="document-pages">
      <figure><figcaption>PDF gốc {localPreview&&<a href={localPreview} target="_blank" rel="noopener noreferrer">Mở tài liệu gốc <ExternalLink size={13}/></a>}</figcaption><div className={current?'':'document-native-pdf'}>{current?<img src={current.preview} alt={`Trang gốc ${current.number}`}/>:<iframe src={localPreview!} title="Xem trước tài liệu gốc"/>}</div></figure>
      <figure><figcaption>Bản dịch Word · Nền trắng A4</figcaption><div>{hasTranslation&&current?<DocumentWordPreview page={current} language={target}/>:<div className="document-waiting">{busy&&<LoaderCircle size={24} className="spin"/>}<p>{busy?'Đang chờ kết quả dịch tài liệu.':'Chọn ngôn ngữ rồi bấm Dịch tài liệu. Kết quả sẽ hiển thị tại đây.'}</p></div>}</div></figure>
    </div>}
    {doc&&<details className="document-advanced"><summary>Đối chiếu và chỉnh sửa bản dịch</summary>
      <div className="document-blocks"><h3>Đối chiếu nội dung · Trang {page+1}</h3>{current?.blocks.map((block,i)=><article key={block.id}><div className="document-block-heading"><strong>Vùng {i+1}{block.inside_image?' · Trong ảnh':''}</strong><span>{typeof block.confidence==='number'?Math.round(block.confidence):'Đọc từ file gốc'}</span><label><input type="checkbox" checked={block.keep} disabled={!!busy} onChange={e=>edit(block.id,{keep:e.target.checked})}/>Giữ gốc</label></div><div className="document-block-content"><textarea aria-label={`Chữ OCR vùng ${i+1}`} lang={doc.source} readOnly value={block.text}/><textarea aria-label={`Bản dịch vùng ${i+1}`} lang={target} disabled={!!busy||block.keep} value={block.translation} onChange={e=>edit(block.id,{translation:e.target.value})}/></div>{block.issues.map(issue=><p className="document-review-warning" key={issue}>{issue}</p>)}</article>)}</div>
    </details>}
  </div>;
}
