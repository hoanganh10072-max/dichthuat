import { useEffect, useState } from 'react';
import { Download, ExternalLink, FileText, LoaderCircle, Upload, WandSparkles } from 'lucide-react';
import './documents.css';
import './document-auto.css';
import {accountFile,saveWord} from './account-api';
import type {OutputDecision} from './outputPolicy';

type Block={id:string;text:string;translation:string;keep:boolean;confidence:number;issues:string[];inside_image?:boolean};
type Region={x:number;y:number;width:number;height:number;confidence:number};
type Page={number:number;source?:string;unread_regions?:Region[];coverage_evaluated?:boolean;width:number;height:number;preview:string;blocks:Block[]};
type Doc={id:string;filename:string;source:string;languages?:string[];untranslated_count?:number;ocr_unread_count?:number;retained_names?:number;overflow_count?:number;download_url?:string|null;pages:Page[];warnings:string[];glossary:Record<string,string>;automatic:boolean;output_policy?:OutputDecision|null};
type Props={languages:{code:string;name:string}[];onBusy:(busy:boolean)=>void;onTextFile:(file:File,source:string,target:string)=>void;accountId:string;canTranslate:boolean};
function termsFromText(text:string) {
  const result:Record<string,string>={};
  for(const line of text.split('\n').filter(l=>l.trim())) {
    const at=line.indexOf('=');
    if(at<1||!line.slice(at+1).trim()) throw new Error('Thuật ngữ dùng dạng: chữ nguồn = bản dịch');
    result[line.slice(0,at).trim()]=line.slice(at+1).trim();
  }
  return result;
}
export default function DocumentWorkspace({languages,onBusy,onTextFile,accountId,canTranslate}:Props) {
  const [source,setSource]=useState('auto'),[target,setTarget]=useState('vi');
  const [file,setFile]=useState<File|null>(null),[doc,setDoc]=useState<Doc|null>(null);
  const [localPreview,setLocalPreview]=useState<string|null>(null);
  const [preserve,setPreserve]=useState(false),[glossary,setGlossary]=useState('');
  const [page,setPage]=useState(0),[previews,setPreviews]=useState<string[]>([]);
  const [busy,setBusy]=useState(''),[error,setError]=useState('');
  const [saved,setSaved]=useState(false),[ready,setReady]=useState(false),[edited,setEdited]=useState(false);
  const [pdfDownload,setPdfDownload]=useState<{url:string;openUrl:string;filename:string}|null>(null);
  const [downloadNotice,setDownloadNotice]=useState('');
  const [showUnclear,setShowUnclear]=useState(true);
  const [showOriginal,setShowOriginal]=useState(false);
  const preferA4=doc?.output_policy?.mode==='a4'||!!doc?.overflow_count;
  useEffect(()=>{
    if(!file){setLocalPreview(null);return;}
    const url=URL.createObjectURL(new Blob([file],{type:'application/pdf'}));
    setLocalPreview(url);
    return()=>URL.revokeObjectURL(url);
  },[file]);
  useEffect(()=>()=>{if(pdfDownload?.url.startsWith('blob:'))URL.revokeObjectURL(pdfDownload.url);},[pdfDownload]);
  function clearOutput(){setReady(false);setPdfDownload(null);setDownloadNotice('');setShowOriginal(false);}
  function reset(){setDoc(null);setPreviews([]);clearOutput();setEdited(false);setError('');}
  async function task(label:string,action:()=>Promise<void>) {
    if(busy)return;setBusy(label);onBusy(true);setError('');
    try{await action();}catch(e){setError(e instanceof TypeError?'Kết nối tải tài liệu bị gián đoạn. Kiểm tra máy chủ và bấm tải lại.':e instanceof Error?e.message:'Không xử lý được tài liệu.');}
    finally{setBusy('');onBusy(false);}
  }
  async function request(path:string,body:BodyInit,json=false) {
    const response=await fetch(`/api/documents/${path}`,{method:'POST',body,credentials:'same-origin',headers:json?{'Content-Type':'application/json','X-Kun-Request':'1'}:{'X-Kun-Request':'1'}});
    if(response.status===401)window.dispatchEvent(new Event('kun-auth-expired'));
    if(!response.ok){const data=await response.json().catch(()=>null);if(response.status===410){reset();throw new Error('Phiên tài liệu đã hết hạn. Bấm Dịch tự động để xử lý lại file đã chọn.');}throw new Error(typeof data?.detail==='string'?data.detail:'Không xử lý được PDF. Kiểm tra file và giới hạn máy chủ.');}
    return response;
  }
  function payload(document=doc,text=glossary,includeEdits=edited) {
    if(!document)throw new Error('Chọn tài liệu và bấm Dịch tự động.');
    return JSON.stringify({session_id:document.id,target,automatic:true,glossary:termsFromText(text),
      edits:includeEdits?document.pages.flatMap(p=>p.blocks.map(b=>({id:b.id,source_text:b.text,translation:b.translation,keep:b.keep}))):[]});
  }
  async function prepareDownload(document:Doc,text=glossary,includeEdits=edited) {
    if(document.output_policy?.mode==='a4'&&!document.download_url){setReady(true);setPdfDownload(null);return;}
    let url=document.download_url||'';
    if(includeEdits||!url.startsWith('/api/documents/')){
      setBusy('Đang chuẩn bị PDF của bản dịch mới nhất để tải…');
      const response=await request('export',payload(document,text,includeEdits),true);
      const blob=await response.blob();
      if(!blob.size||(await blob.slice(0,5).text())!=='%PDF-')throw new Error('Máy chủ chưa trả về file PDF hợp lệ. Bấm Chuẩn bị PDF để tải để thử lại.');
      url=URL.createObjectURL(new Blob([blob],{type:'application/pdf'}));
    }
    const incomplete=!!(document.ocr_unread_count||document.untranslated_count);
    const filename=(document.filename.replace(/\.pdf$/i,'')||'kun-global')+(incomplete?'-dich-ban-nhap.pdf':'-dich.pdf');
    setPdfDownload({url,openUrl:url.startsWith('blob:')?url:url+'&inline=true',filename});
    setReady(true);
  }
  function automatic(selectedFile=file,newUpload=false){if(!canTranslate){setError('Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.');return;}void task('Đang đọc toàn bộ tài liệu và chữ trong ảnh…',async()=>{
    if(!selectedFile)throw new Error('Chọn một file PDF trước.');
    if(selectedFile.size>30*1024*1024)throw new Error('PDF tối đa 30 MB.');
    clearOutput();setPreviews([]);
    let analyzed=newUpload?null:doc,terms=newUpload?'':glossary;
    if(!analyzed){
      const form=new FormData();form.append('file',selectedFile);form.append('source',source);form.append('preserve_images',String(preserve));
      analyzed=await(await request('analyze',form)).json() as Doc;
      setDoc(analyzed);setPage(0);
      terms=Object.entries(analyzed.glossary).map(([a,b])=>`${a} = ${b}`).join('\n');
      try{const stored=localStorage.getItem(`kun-document-glossary-${accountId}-${analyzed.source}-${target}`);if(stored!==null)terms=stored;}catch{}
      setGlossary(terms);setSaved(false);
    }
    setBusy('Đang dịch, tự dàn chữ và tạo PDF…');
    const result=await(await request('complete',payload(analyzed,terms,!newUpload&&edited),true)).json();
    setDoc(result.document);setPreviews(result.pages);setEdited(false);
    await prepareDownload(result.document,terms,false);
  });}
  function preview(){void task('Đang cập nhật PDF…',async()=>{
    clearOutput();
    const result=await(await request('preview',payload(),true)).json();setPreviews(result.pages);
    if(doc){const updated={...doc,overflow_count:result.overflow_count,download_url:result.download_url,output_policy:result.output_policy};setDoc(updated);await prepareDownload(updated,glossary,false);}
  });}
  function retryDownload(){void task('Đang chuẩn bị PDF để tải…',async()=>{if(doc)await prepareDownload(doc);});}
  function downloadWord(){void task('Đang tạo Word A4 nền trắng và khung bảng…',async()=>{
    if(!doc)return;
    const blob=await accountFile('documents/export-word',{method:'POST',headers:{'Content-Type':'application/json'},body:payload()});
    saveWord(blob,(doc.filename.replace(/\.pdf$/i,'')||'kun-global')+'-dich-a4.docx');
    setDownloadNotice('Đã chuẩn bị Word A4 nền trắng. Chữ và bảng có thể chỉnh sửa.');
  });}
  function edit(id:string,change:Partial<Block>){setPreviews([]);clearOutput();setEdited(true);setDoc(d=>d?({...d,pages:d.pages.map(p=>({...p,blocks:p.blocks.map(b=>b.id===id?{...b,...change,issues:[]}:b)}))}):null);}
  const current=doc?.pages[page];
  const sourceNames=doc?(doc.languages||[doc.source]).map(code=>languages.find(l=>l.code===code)?.name||code).join(' / '):'';
  const incomplete=!!(doc?.ocr_unread_count||doc?.untranslated_count);
  function pageImage(src:string,alt:string,p:Page){return <div className="document-page-paper"><img src={src} alt={alt}/>{showUnclear&&!!p.unread_regions?.length&&<svg className="document-ocr-overlay" viewBox={`0 0 ${p.width} ${p.height}`} preserveAspectRatio="none" aria-label="Vùng chữ chưa đọc rõ">{p.unread_regions.map((r,i)=><rect key={i} x={r.x} y={r.y} width={r.width} height={r.height}><title>Vùng {i+1}: OCR chưa đọc rõ; có thể còn chữ gốc.</title></rect>)}</svg>}</div>;}
  return <div className="document-workspace">
    <div className="document-intro"><FileText size={25}/><div><strong>Dịch tài liệu tự động, giữ bố cục</strong><p>Chọn file để tự dịch và xem kết quả bên phải. PDF gồm cả chữ trong ảnh · 30 MB / 10 trang.</p></div></div>
    <div className="document-setup">
      <label className="document-file"><Upload size={18}/>{file?.name||'Chọn PDF, DOCX hoặc TXT'}<input type="file" accept=".pdf,.docx,.txt" disabled={!!busy} onChange={e=>{
        const selected=e.currentTarget.files?.[0];e.currentTarget.value='';
        if(!selected)return;
        if(/\.(docx|txt)$/i.test(selected.name)){onTextFile(selected,source,target);return;}
        setFile(selected);reset();automatic(selected,true);
      }}/></label>
      <label>Nguồn<select aria-label="Ngôn ngữ nguồn tài liệu" disabled={!!busy} value={source} onChange={e=>{setSource(e.target.value);reset();}}><option value="auto">Tự phát hiện</option>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
      <label>Đích<select aria-label="Ngôn ngữ đích tài liệu" disabled={!!busy} value={target} onChange={e=>{setTarget(e.target.value);clearOutput();setPreviews([]);}}>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
      <button className="primary" disabled={!file||!!busy||!canTranslate} onClick={()=>automatic()}><WandSparkles size={17}/>Dịch tự động</button>
    </div>
    <label className="preserve-images"><input type="checkbox" checked={!preserve} disabled={!!busy} onChange={e=>{setPreserve(!e.target.checked);reset();}}/>Đọc và dịch cả chữ trong ảnh đính kèm</label>
    <p className="document-help">App đọc chữ tại máy chủ, gửi văn bản tới OpenAI để dịch rồi ghép vào PDF. Giữ vị trí ảnh, khung, dấu và mã nhận diện được; hoa văn dưới chữ phục hồi gần đúng. Không cần chỉnh từng vùng để tải bản dịch.</p>
    {busy&&<div className="document-progress" role="status"><LoaderCircle className="spin" size={18}/>{busy}</div>}
    {error&&<div className="error" role="alert">{error}</div>}
    {!doc&&localPreview&&<div className="document-pages document-local-preview">
      <figure><figcaption>File gốc <a href={localPreview} target="_blank" rel="noopener noreferrer">Mở tài liệu gốc <ExternalLink size={13}/></a></figcaption>
        <div className="document-native-pdf"><iframe src={localPreview} title="Xem trước tài liệu gốc"/></div>
      </figure>
      <figure><figcaption>Bản dịch</figcaption><div className="document-waiting">
        {busy&&<LoaderCircle size={24} className="spin"/>}
        <p>{busy?'Đang xử lý tài liệu. Bản dịch sẽ hiện tại đây khi sẵn sàng.':'Bấm Dịch tự động để xử lý tài liệu đã chọn.'}</p>
      </div></figure>
    </div>}
    {doc&&<>
      <div className="document-toolbar">
        <button className={preferA4?'primary':'secondary'} disabled={!!busy||(!ready&&!edited)} onClick={downloadWord}><FileText size={16}/>Tải Word A4</button>
        <span>{doc.pages.length} trang · {sourceNames}{ready?(preferA4?' · Ưu tiên Word A4':' · Giữ form gốc'):''}</span>
        <select aria-label="Trang tài liệu" value={page} onChange={e=>setPage(Number(e.target.value))}>{doc.pages.map((p,i)=><option key={i} value={i}>Trang {p.number}{p.source?' · '+p.source.toUpperCase():''}</option>)}</select>
        {pdfDownload&&ready&&!busy?<><a className="secondary document-open-pdf" href={pdfDownload.openUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={15}/>Mở PDF</a><a className={preferA4?'secondary document-download-pdf':'primary document-download-pdf'} href={pdfDownload.url} download={pdfDownload.filename} onClick={()=>setDownloadNotice('Đã yêu cầu trình duyệt tải PDF. Nếu chưa thấy file, chọn Mở PDF rồi lưu từ trình xem PDF.')}><Download size={16}/>{incomplete?'Tải PDF bản nháp':'Tải PDF'}</a></>:(previews.length||!preferA4)?<button className="primary" disabled={!!busy||!previews.length} onClick={retryDownload}><Download size={16}/>{previews.length?'Chuẩn bị PDF để tải':'Tải PDF'}</button>:null}
      </div>
      {ready&&<div className="output-choice" role="status"><strong>Tự chọn: {preferA4?'Word A4 dễ đọc':'Giữ form gốc'}</strong><span>{doc.output_policy?.reason||(preferA4?'Bản dịch không vừa khung gốc.':'Bản dịch vừa khung.')}</span>{preferA4&&!!previews.length&&<button className="secondary" onClick={()=>setShowOriginal(value=>!value)}>{showOriginal?'Xem nội dung A4':'Xem PDF giữ form'}</button>}</div>}
      {ready&&<p className="document-download-help" role="status">{downloadNotice||(preferA4?'Chọn Tải Word A4 để nhận bản nền trắng với chữ và bảng chỉnh sửa được.':'Chọn Tải PDF để nhận bản dịch giữ form gốc.')}</p>}
      <div className="document-notice">Bản dịch tự động; có thể sai nghĩa hoặc bỏ sót chữ mờ. Bố cục được ghép tự động, chưa bảo đảm giống tuyệt đối mọi tài liệu.</div>
      {!!previews.length&&!!doc.overflow_count&&<p className="document-help">{doc.overflow_count} vùng chữ được đưa nguyên bản dịch vào phụ lục cuối file để giữ cỡ chữ dễ đọc. Chọn Mở PDF để xem phụ lục.</p>}
      {doc.warnings.filter(w=>w.includes('Pinyin')||w.includes('giữ chữ gốc')||w.includes('chưa đọc rõ')).map(w=><p className="document-review-warning" key={w}>{w}</p>)}
      {!!doc.retained_names&&<p className="document-help">{doc.retained_names} vùng được giữ như tên riêng, ghép lại bằng chữ dễ đọc. Cần đối chiếu chính tả tên với bản gốc.</p>}
      {!!doc.ocr_unread_count&&<label className="document-coverage-control"><input type="checkbox" checked={showUnclear} onChange={e=>setShowUnclear(e.target.checked)}/>Đánh dấu màu cam các vùng chưa đọc rõ ({doc.ocr_unread_count})</label>}
      {current&&<div className="document-pages"><figure><figcaption>Trang gốc</figcaption><div>{pageImage(current.preview,`Trang gốc ${page+1}`,current)}</div></figure><figure><figcaption>{preferA4&&!showOriginal?'Nội dung bản Word A4':incomplete?'PDF bản nháp · còn vùng chưa rõ':'PDF dịch tự động'}</figcaption><div>{preferA4&&!showOriginal?<div className="document-a4-preview" lang={target} dir={target==='ar'?'rtl':undefined}><strong>Word A4 · Nền trắng</strong><p>Tải Word để xem khung bảng và chỉnh sửa.</p>{current.blocks.map(block=><p key={block.id}>{block.keep?block.text:block.translation||'Chưa có bản dịch vùng này.'}</p>)}</div>:previews[page]?pageImage(previews[page],`Trang dịch ${page+1}`,current):<p>{error?'Chưa tạo được bản PDF hoàn chỉnh.':'Bản dịch sẽ tự xuất hiện sau khi xử lý xong.'}</p>}</div></figure></div>}
      <details className="document-advanced"><summary>Tùy chọn: thuật ngữ và chỉnh sửa thêm</summary>
        <div className="document-glossary"><strong>Thuật ngữ dùng lại</strong><p>Mỗi dòng: chữ nguồn = bản dịch. Thuật ngữ Trung→Việt được áp dụng khi bấm Dịch tự động; không cần nhập để chạy.</p><textarea aria-label="Thuật ngữ tài liệu" value={glossary} disabled={!!busy} onChange={e=>{setGlossary(e.target.value);setSaved(false);}}/><button className="secondary" disabled={!!busy} onClick={()=>{try{termsFromText(glossary);localStorage.setItem(`kun-document-glossary-${accountId}-${doc.source}-${target}`,glossary);setSaved(true);}catch(e){setError(e instanceof Error?e.message:'Không lưu được thuật ngữ.');}}}>{saved?'Đã lưu trên thiết bị':'Lưu thuật ngữ cho lần sau'}</button></div>
        <div className="document-blocks"><h3>Chỉnh sửa tùy chọn · Trang {page+1}</h3>{current?.blocks.map((block,i)=><article key={block.id}><div className="document-block-heading"><strong>Vùng {i+1}{block.inside_image?' · Trong ảnh':''}</strong><span>OCR: {Math.round(block.confidence)}</span><label><input type="checkbox" checked={block.keep} disabled={!!busy} onChange={e=>edit(block.id,{keep:e.target.checked})}/>Giữ gốc</label></div><div className="document-block-content"><textarea aria-label={`Chữ OCR vùng ${i+1}`} lang={doc.source} disabled={!!busy} value={block.text} onChange={e=>edit(block.id,{text:e.target.value,translation:''})}/><textarea aria-label={`Bản dịch vùng ${i+1}`} lang={target} disabled={!!busy||block.keep} value={block.translation} onChange={e=>edit(block.id,{translation:e.target.value})}/></div>{block.issues.map(issue=><p className="document-review-warning" key={issue}>{issue}</p>)}</article>)}</div>
        {(doc.download_url||!preferA4)&&<button className="secondary" disabled={!!busy||!edited} onClick={preview}>Cập nhật PDF từ chỉnh sửa</button>}
      </details>
    </>}
  </div>;
}
