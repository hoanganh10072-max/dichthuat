import {useEffect,useRef,useState} from 'react';
import {Download,FileText,Image as ImageIcon,LoaderCircle,Upload,X} from 'lucide-react';
import {translateDocxFile,translateImageFile,translatePdfFile,type FormCall,type FormOutput} from './form-files';
import './form-workspace.css';
type Props={mode:'image'|'document';source:string;target:string;canTranslate:boolean;call:FormCall;onBusy?:(busy:boolean)=>void;maxBytes?:number};
export default function FormTranslationWorkspace({mode,source,target,canTranslate,call,onBusy,maxBytes=3*1024*1024}:Props){
  const [file,setFile]=useState<File|null>(null),[result,setResult]=useState<FormOutput|null>(null),[progress,setProgress]=useState(''),[error,setError]=useState(''),[showText,setShowText]=useState(false);
  const [sourceUrl,setSourceUrl]=useState(''),[resultUrl,setResultUrl]=useState('');const active=useRef(false),abort=useRef<AbortController|null>(null),input=useRef<HTMLInputElement>(null);
  useEffect(()=>{setResult(null);setError('');setShowText(false);},[source,target]);
  useEffect(()=>()=>abort.current?.abort(),[]);
  useEffect(()=>{if(!file){setSourceUrl('');return;}const url=URL.createObjectURL(file);setSourceUrl(url);return()=>URL.revokeObjectURL(url);},[file]);
  useEffect(()=>{if(!result){setResultUrl('');return;}const url=URL.createObjectURL(result.blob);setResultUrl(url);return()=>URL.revokeObjectURL(url);},[result]);
  function choose(file?:File){
    if(active.current||!file)return;setResult(null);setError('');setFile(null);setShowText(false);
    if(file.size>maxBytes){setError(`File tối đa ${Math.round(maxBytes/1024/1024)} MB.`);return;}
    const ext=file.name.split('.').pop()?.toLowerCase();if(!file.size||!(mode==='image'?['png','jpg','jpeg','webp']:['pdf','docx','txt']).includes(ext||'')){setError('File trống hoặc định dạng không được hỗ trợ.');return;}setFile(file);
  }
  async function translate(){
    if(active.current||!file)return;if(!canTranslate){setError('Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.');return;}
    active.current=true;onBusy?.(true);setResult(null);setError('');setProgress('Đang chuẩn bị tài liệu gốc…');const controller=new AbortController();abort.current=controller;
    try{
      const ext=file.name.split('.').pop()?.toLowerCase();let output:FormOutput;
      if(mode==='image')output=await translateImageFile(file,call,target,setProgress,controller.signal);
      else if(ext==='pdf')output=await translatePdfFile(file,call,target,setProgress,controller.signal);
      else if(ext==='docx')output=await translateDocxFile(file,call,target,setProgress,controller.signal);
      else{
        const text=await file.text();if(text.length>12000)throw new Error('File TXT tối đa 12.000 ký tự mỗi lượt.');
        setProgress('Đang dịch nội dung văn bản…');const response=await call({output:'text',text},controller.signal);
        if(!Array.isArray(response.blocks)||!response.blocks.length)throw new Error('Chưa nhận đủ nội dung bản dịch.');
        const content=response.blocks.map((b:any)=>b.kind==='table'?b.rows.map((r:string[])=>r.join('\t')).join('\n'):b.text).join('\n\n');
        output={blob:new Blob(['\uFEFF'+content],{type:'text/plain;charset=utf-8'}),extension:'txt',pages:[],text:content,pageCount:1,regionCount:response.blocks.length};
      }
      if(controller.signal.aborted)throw new Error('Đã hủy xử lý. Không tạo bản dịch dở dang.');setResult(output);
    }catch(e){setError(controller.signal.aborted?'Đã hủy xử lý. Không xuất bản dịch dở dang.':e instanceof Error?e.message:'Chưa tạo được bản dịch hoàn chỉnh.');}
    finally{active.current=false;onBusy?.(false);setProgress('');abort.current=null;}
  }
  function download(){if(!result||!resultUrl)return;const link=document.createElement('a');link.href=resultUrl;link.download=`${file!.name.replace(/\.[^.]+$/,'')}-${target}.${result.extension}`;link.click();}
  const ext=file?.name.split('.').pop()?.toLowerCase(),busy=!!progress;
  return <div className="form-workspace">
    <div className="form-file"><input ref={input} type="file" id={`form-file-${mode}`} disabled={busy} accept={mode==='image'?'.png,.jpg,.jpeg,.webp':'.pdf,.docx,.txt'} onChange={e=>choose(e.target.files?.[0])}/><label htmlFor={`form-file-${mode}`}><Upload size={22}/><span><strong>{file?.name||(mode==='image'?'Chọn ảnh gốc để dịch':'Chọn tài liệu gốc để dịch')}</strong><small>{mode==='image'?'Giữ hình ảnh và vị trí chữ · tải PNG':'PDF giữ từng trang · DOCX giữ định dạng gốc · TXT ra văn bản'} · {Math.round(maxBytes/1024/1024)} MB</small></span></label>{file&&<button aria-label="Bỏ file gốc" disabled={busy} onClick={()=>{setFile(null);setResult(null);setError('');if(input.current)input.current.value='';}}><X size={17}/></button>}</div>
    {error&&<div className="trial-error" role="alert">{error}</div>}{busy&&<div className="trial-progress" role="status"><LoaderCircle size={18} className="spin"/>{progress}<button onClick={()=>abort.current?.abort()}>Hủy</button></div>}
    <div className="form-columns"><section><h2>{mode==='image'?'Ảnh gốc':'Tài liệu gốc'}</h2>{sourceUrl&&mode==='image'?<img src={sourceUrl} alt="Ảnh gốc"/>:sourceUrl&&ext==='pdf'?<iframe title="PDF gốc" src={sourceUrl}/>:<div className="form-empty"><FileText size={32}/><strong>{file?.name||'Chưa chọn file'}</strong><p>{file?'Bấm Dịch ngay để dịch toàn bộ, giữ định dạng tài liệu.':'Chọn file gốc ở phía trên. Bản dịch sẽ hiện bên phải.'}</p></div>}</section>
    <section className="form-result" aria-label="Bản dịch giữ form"><h2>{mode==='image'?'Ảnh đã dịch':'Tài liệu đã dịch'}{result&&<span>{result.extension.toUpperCase()} · {result.extension==='pdf'?`${result.pageCount} trang`:'Giữ định dạng gốc'}</span>}</h2>{result?<>
      <div className="form-view-tabs"><button aria-pressed={!showText} onClick={()=>setShowText(false)}>{mode==='image'?<ImageIcon size={14}/>:<FileText size={14}/>}Bản dịch giữ form</button><button aria-pressed={showText} onClick={()=>setShowText(true)}>Nội dung chữ</button></div>
      {showText?<div className="form-text">{result.text}</div>:result.extension==='png'?<img src={result.pages[0].url} alt="Ảnh dịch giữ hình ảnh gốc"/>:result.extension==='pdf'?<iframe title="PDF dịch giữ form" src={resultUrl}/>:result.extension==='txt'?<div className="form-text">{result.text}</div>:<div className="form-empty"><FileText size={36}/><strong>Đã tạo Word từ file gốc</strong><p>Khung bảng, ảnh và thiết lập trang được giữ trong DOCX. Tải và mở bằng Word để kiểm tra bố cục thực tế.</p><button className="trial-gold" onClick={download}><Download size={17}/>Tải DOCX đã dịch</button></div>}
    </>:<div className="form-empty"><ImageIcon size={32}/><strong>{mode==='image'?'Ảnh dịch sẽ giữ hình ảnh gốc':'Bản dịch sẽ giữ form tài liệu'}</strong><p>Chỉ thay phần chữ cần dịch. Chưa có kết quả thì chưa có file để tải.</p></div>}</section></div>
    <div className="form-actions"><p>{mode==='image'?'Ảnh giữ nguyên kích thước và đồ họa ngoài vùng chữ.':ext==='docx'?'DOCX giữ bảng, lề, kiểu chữ và ảnh trong file gốc; chữ dịch dài có thể làm giãn dòng.':'PDF giữ kích thước, số trang và nền; dịch cả chữ trong ảnh scan.'}<br/>Nền trong vùng thay chữ được phục dựng gần đúng; cần kiểm tra phần scan mờ.</p><div>{result&&<button className="form-download" onClick={download}><Download size={17}/>Tải {result.extension.toUpperCase()} đã dịch</button>}<button className="trial-gold" disabled={busy||!file||!canTranslate} onClick={()=>void translate()}><FileText size={17}/>Dịch ngay</button></div></div>
  </div>;
}
