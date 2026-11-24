import {useEffect,useRef,useState} from 'react';
import {ArrowLeftRight,Copy,Download,FileText,Image as ImageIcon,Languages,LoaderCircle,ShieldCheck,UserRound,LogOut} from 'lucide-react';
import {PREVIEW_LANGUAGES} from './public-preview';
import FormTranslationWorkspace from './FormTranslationWorkspace';
import {saveBlob,textContent,textWord,type TextBlock} from './text-export';
import './online-trial.css';
import {accountApi,jsonRequest,type Account} from './account-api';
import {AccountPanel} from './Accounts';
type Result={ok:true;source_language:string;blocks:TextBlock[]};
export default function OnlineTrial({onHome,account,onLogout,onRefresh}:{onHome:()=>void;account:Account;onLogout:()=>Promise<void>;onRefresh:()=>Promise<void>}){
  const isAdmin=account.role==='admin';
  const [enabled,setEnabled]=useState(false),[panel,setPanel]=useState<'users'|'provider'|'profile'|null>(null);
  useEffect(()=>{let current=true;const refresh=()=>{void accountApi('health').then(data=>{if(current)setEnabled(data.model==='ready');}).catch(()=>{if(current)setEnabled(false);});};refresh();window.addEventListener('kun-chatgpt-changed',refresh);window.addEventListener('focus',refresh);return()=>{current=false;window.removeEventListener('kun-chatgpt-changed',refresh);window.removeEventListener('focus',refresh);};},[]);
  const [mode,setMode]=useState<'text'|'image'|'document'>('text'),[source,setSource]=useState('auto'),[target,setTarget]=useState('vi');
  const [input,setInput]=useState(''),[result,setResult]=useState<Result|null>(null),[busy,setBusy]=useState(''),[formBusy,setFormBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const active=useRef(false),controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  const locked=!!busy||formBusy;
  function invalidate(){setResult(null);setError('');setNotice('');}
  async function call(body:Record<string,unknown>,signal?:AbortSignal){
    const cancel=new AbortController(),cancelled=()=>cancel.abort();signal?.addEventListener('abort',cancelled,{once:true});if(signal?.aborted)cancel.abort();const timer=setTimeout(cancelled,65000);
    try{
      const data=await accountApi('trial',{...jsonRequest('POST',{source,target,...body}),signal:cancel.signal});
      if(!data?.ok)throw new Error('Chưa nhận được bản dịch hoàn chỉnh.');return data;
    }catch(e){if(cancel.signal.aborted)throw new Error(signal?.aborted?'Đã hủy xử lý.':'Chưa nhận đủ kết quả trong thời gian chờ. Hãy thử ít trang hơn.');throw e;}
    finally{clearTimeout(timer);signal?.removeEventListener('abort',cancelled);}
  }
  async function request(){
    if(active.current||formBusy)return;if(!input.trim()){setError('Nhập văn bản trước khi dịch.');return;}
    active.current=true;setBusy('Đang dịch toàn bộ văn bản…');setError('');setNotice('');setResult(null);controller.current=new AbortController();
    try{const data=await call({text:input,output:'text'},controller.current.signal);if(!Array.isArray(data.blocks)||!data.blocks.length)throw new Error('Chưa nhận đủ bản dịch văn bản.');setResult(data);setNotice('Đã nhận bản dịch văn bản hoàn chỉnh. Bạn có thể sao chép hoặc tải TXT.');}
    catch(e){setError(e instanceof Error?e.message:'Mất kết nối. Chưa có kết quả mới.');}
    finally{active.current=false;setBusy('');controller.current=null;}
  }
  async function word(){if(!result||active.current)return;active.current=true;setBusy('Đang tạo Word…');setError('');try{saveBlob(await textWord(result.blocks),`kun-global-ban-dich-${target}.docx`);}catch{setError('Không tạo được Word. Bạn vẫn có thể tải TXT hoặc sao chép nội dung.');}finally{active.current=false;setBusy('');}}
  return <div className="trial-page"><header className="trial-header"><a href="/" onClick={e=>{if(!e.ctrlKey&&!e.metaKey){e.preventDefault();if(!locked)onHome();}}}><img src="/kun-global-logo-v2.png" alt="KUN GLOBAL"/><span><strong>KUN GLOBAL</strong><small>DỊCH THUẬT ĐA NGÔN NGỮ</small></span></a><div className="hosted-actions"><button disabled={locked} onClick={()=>setPanel(isAdmin?'users':'profile')}><UserRound size={16}/>{isAdmin?'Quản trị':'Tài khoản'}</button><button onClick={()=>void onLogout().catch(()=>setError('Chưa đăng xuất được. Vui lòng thử lại.'))} disabled={locked}><LogOut size={16}/>Đăng xuất</button></div></header>
  <main className="trial-main"><div className="trial-intro"><div><span className="trial-eyebrow">KHÔNG GIAN DỊCH THUẬT TRỰC TUYẾN</span><h1>Ngôn ngữ mới.<br/><em>Kết nối mới.</em></h1><p>20 ngôn ngữ · Tự nhận diện nguồn.<br/>Văn bản ra văn bản · Ảnh giữ hình ảnh · Tài liệu giữ form.</p></div><div className="trial-intro-note"><ShieldCheck size={26}/><strong>Không gian dịch của bạn</strong><p>Dịch văn bản, hình ảnh và tài liệu trong cùng một giao diện. Tài khoản do quản trị viên cấp và quản lý.</p></div></div>
  {!enabled&&<div className="hosted-permission" role="status"><ShieldCheck size={20}/><p>{isAdmin?'Mở phần quản trị để cấu hình và kiểm tra dịch vụ dịch.':'Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.'}</p>{isAdmin&&<button onClick={()=>setPanel('provider')}>Cấu hình dịch vụ</button>}</div>}
  <section className="trial-workspace" aria-label="Dịch thử trực tuyến"><div className="trial-tabs" role="tablist" aria-label="Loại nội dung">{([{id:'text',label:'Văn bản',icon:Languages},{id:'image',label:'Hình ảnh',icon:ImageIcon},{id:'document',label:'Tài liệu',icon:FileText}] as const).map(tab=><button role="tab" aria-selected={mode===tab.id} className={mode===tab.id?'active':''} disabled={locked} key={tab.id} onClick={()=>{setMode(tab.id);invalidate();}}><tab.icon size={18}/>{tab.label}</button>)}</div>
  <div className="trial-languages"><label>Ngôn ngữ nguồn<select aria-label="Ngôn ngữ nguồn" value={source} disabled={locked} onChange={e=>{setSource(e.target.value);invalidate();}}><option value="auto">Tự phát hiện</option>{PREVIEW_LANGUAGES.map(l=><option value={l.code} key={l.code}>{l.name}</option>)}</select></label><button aria-label="Đảo chiều ngôn ngữ" disabled={locked||source==='auto'} onClick={()=>{setSource(target);setTarget(source);invalidate();}}><ArrowLeftRight size={19}/></button><label>Ngôn ngữ dịch<select aria-label="Ngôn ngữ dịch" value={target} disabled={locked} onChange={e=>{setTarget(e.target.value);invalidate();}}>{PREVIEW_LANGUAGES.map(l=><option value={l.code} key={l.code}>{l.name}</option>)}</select></label></div>
  {mode!=='text'?<FormTranslationWorkspace key={mode} mode={mode} source={source} target={target} canTranslate={enabled} call={call} onBusy={setFormBusy}/>:<>
  {error&&<div className="trial-error" role="alert">{error}</div>}{notice&&<div className="trial-notice" role="status">{notice}</div>}{busy&&<div className="trial-progress" role="status"><LoaderCircle className="spin" size={19}/>{busy}</div>}
  <div className="trial-columns"><section className="trial-source"><h2>Nội dung gốc<span>{input.length.toLocaleString('vi-VN')} / 12.000 ký tự</span></h2><textarea aria-label="Văn bản cần dịch" placeholder="Nhập nội dung bạn muốn dịch…" value={input} maxLength={12000} disabled={locked} onChange={e=>{setInput(e.target.value);invalidate();}}/></section><section className="trial-output" aria-label="Bản dịch"><h2>Bản dịch<span>{result?`Nguồn: ${result.source_language}`:'Văn bản đầy đủ'}</span></h2>{result?<div className="trial-result">{result.blocks.map((b,i)=>b.kind==='table'?<div className="trial-table-scroll" key={i}><table><tbody>{b.rows.map((row,ri)=><tr key={ri}>{row.map((cell,ci)=><td key={ci}>{cell}</td>)}</tr>)}</tbody></table></div>:b.kind==='heading'?<h3 key={i}>{b.text}</h3>:<p key={i}>{b.text}</p>)}</div>:<div className="trial-empty"><Languages size={34}/><strong>Bản dịch bắt đầu từ đây</strong><p>Chọn ngôn ngữ, nhập nội dung và bấm Dịch ngay.</p></div>}</section></div>
  <div className="trial-actions"><p>Văn bản được xử lý tại máy chủ dịch khi bạn bấm dịch.<br/>Chỉ hiện bản dịch khi đã nhận phản hồi hoàn chỉnh.</p><div>{result&&<><button disabled={locked} onClick={()=>void navigator.clipboard.writeText(textContent(result.blocks)).then(()=>setNotice('Đã sao chép bản dịch.')).catch(()=>setError('Không sao chép được. Hãy chọn nội dung và sao chép thủ công.'))}><Copy size={17}/>Sao chép</button><button disabled={locked} onClick={()=>saveBlob(new Blob(['\uFEFF'+textContent(result.blocks)],{type:'text/plain;charset=utf-8'}),`kun-global-ban-dich-${target}.txt`)}><Download size={17}/>Tải TXT</button><button disabled={locked} onClick={()=>void word()}><FileText size={17}/>Tải Word</button></>}<button className="trial-gold" disabled={locked||!enabled||!input.trim()} onClick={()=>void request()}><Languages size={18}/>Dịch ngay</button></div></div>
  </>}
  </section><p className="trial-footer">KUN GLOBAL · Dịch thuật đa ngôn ngữ. Hãy đối chiếu nội dung quan trọng và phần chữ scan mờ với bản gốc.</p></main>{panel&&<AccountPanel account={account} canTranslate={enabled} initialSection={isAdmin&&panel!=='profile'?panel:undefined} onClose={()=>setPanel(null)} onLogout={onLogout} onRefresh={onRefresh}/>}</div>;
}
