import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, ArrowLeftRight, Check, Copy, Download, FileText, History, Image, Languages, LoaderCircle, LockKeyhole, LogOut, Plus, ShieldCheck, Sparkles, Trash2, Upload, X, WifiOff, UserRound } from 'lucide-react';
import './style.css';
import ImagePreview from './ImagePreview';
import './image-preview.css';
import TranslatedImage, { type Layout } from './TranslatedImage';
import PreservedDocumentWorkspace from './PreservedDocumentWorkspace';
import './kun-global.css';
import './translation-workspace.css';
import {AccountGate,AccountPanel} from './Accounts';
import {accountApi,accountFile,saveWord,jsonRequest,type Account} from './account-api';
import './translator.css';
import {PUBLIC_PREVIEW,PREVIEW_NOTICE,PREVIEW_LANGUAGES} from './public-preview';

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(console.error); });
}

type Lang = { code: string; name: string };
type Entry = { id: string; input: string; output: string; source: string; target: string; date: string };
type Health = { model: string; message: string };
type Detection = { code: string; uncertain: boolean; method: string };
type InstallEvent = Event & { prompt: () => Promise<void> };
const defaults: Lang[] = [{ code: 'vi', name: 'Tiếng Việt' }, { code: 'lo', name: 'ພາສາລາວ · Tiếng Lào' }];

async function api(path: string, init?: RequestInit) {
  return accountApi(path,init);
}

function App({account,onLogout,onRefresh}:{account:Account;onLogout:()=>Promise<void>;onRefresh:()=>Promise<void>}) {
  const isAdmin=account.role==='admin';
  const contactAdmin='Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.';
  const preferenceKey = `kun-remember-${account.id}`;
  const [accountOpen,setAccountOpen]=useState(false);
  const [accountUser,setAccountUser]=useState<string|null>(null);
  const [accountSection,setAccountSection]=useState<'users'|'provider'|undefined>(undefined);
  const [tab, setTab] = useState<'text' | 'image' | 'document'>('text');
  const [documentMode,setDocumentMode]=useState<'form'|'text'>('form');
  const [documentBusy,setDocumentBusy]=useState(false);
  const [langs, setLangs] = useState(PUBLIC_PREVIEW?PREVIEW_LANGUAGES:defaults);
  const [source, setSource] = useState('auto');
  const [target, setTarget] = useState('vi');
  const [detected, setDetected] = useState<Detection | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [layout, setLayout] = useState<Layout | null>(null);
  const [ocrSource, setOcrSource] = useState<string | null>(null);
  const [translatedLayout, setTranslatedLayout] = useState<Layout | null>(null);
  const [busy, setBusy] = useState(false);
  const [wordBusy,setWordBusy]=useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [health, setHealth] = useState<Health>(PUBLIC_PREVIEW?{model:'preview',message:PREVIEW_NOTICE}:{ model: 'checking', message: 'Đang kết nối máy chủ' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [fileName, setFileName] = useState('');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const imageFileRef = useRef<File | null>(null);
  // Guard synchronously too: React state updates do not block a second click
  // in the same event loop. Switching tabs never starts another model request.
  const requestActive = useRef(false);
  useEffect(() => () => { if (imagePreview) URL.revokeObjectURL(imagePreview); }, [imagePreview]);
  useEffect(() => { if (!fileName) { setImagePreview(null); imageFileRef.current = null; } }, [fileName]);
  const [history, setHistory] = useState<Entry[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [remember, setRemember] = useState(() => localStorage.getItem(preferenceKey) !== 'false');
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [timing, setTiming] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const locked = busy || extracting || documentBusy || loggingOut || wordBusy;
  useEffect(() => {
    if (!busy) { setElapsed(0); return; }
    const started=Date.now();
    const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);
    return ()=>clearInterval(timer);
  }, [busy]);
  async function signOut() {
    if (locked) return;
    setLoggingOut(true);
    try { await onLogout(); }
    catch { setNotice('Chưa đăng xuất được. Kiểm tra kết nối và thử lại.'); }
    finally { setLoggingOut(false); }
  }
  useEffect(() => {
    if(PUBLIC_PREVIEW)return;
    if(tab==='image' && imagePreview){setDetecting(false);return;}
    if (source !== 'auto' || !input.trim() || extracting) { setDetected(null); setDetecting(false); return; }
    let active = true;
    const controller = new AbortController();
    setDetected(null); setDetecting(true);
    const timer = setTimeout(() => {
      api('detect', { method: 'POST', headers: {'Content-Type':'application/json'}, signal: controller.signal,
        body: JSON.stringify({text:input,source:'auto',target}) })
        .then(result => { if (active) setDetected(result); })
        .catch(() => {})
        .finally(() => { if (active) setDetecting(false); });
    }, 750);
    return () => { active=false; clearTimeout(timer); controller.abort(); };
  }, [source,input,extracting,target,tab,imagePreview]);
  useEffect(() => { if (locked) setHistoryOpen(false); }, [locked, historyOpen]);
  const name = (code: string) => langs.find(l => l.code === code)?.name || code;
  useEffect(() => {
    const check = () => {if(!PUBLIC_PREVIEW)void api('health').then(setHealth).catch(() => setHealth({ model: 'offline', message: 'Chưa kết nối được máy chủ' }));};
    window.addEventListener('kun-chatgpt-changed', check);
    check(); if(!PUBLIC_PREVIEW)void api('languages').then(setLangs).catch(() => {});
    const timer = window.setInterval(check, 15000);
    const installation = (event: Event) => { event.preventDefault(); setInstall(event as InstallEvent); };
    const connection = () => setOnline(navigator.onLine);
    window.addEventListener('beforeinstallprompt', installation);
    window.addEventListener('online', connection); window.addEventListener('offline', connection);
    return () => { window.removeEventListener('kun-chatgpt-changed', check); clearInterval(timer); window.removeEventListener('beforeinstallprompt', installation); window.removeEventListener('online', connection); window.removeEventListener('offline', connection); };
  }, []);
  useEffect(() => { const params=new URLSearchParams(window.location.search);const outcome=params.get('chatgpt'); if(outcome){if(account.role==='admin'){const user=params.get('chatgpt_user');setAccountUser(user);setAccountSection(user?'users':'provider');}setAccountOpen(true);window.history.replaceState(null,'',window.location.pathname);}},[]);
  useEffect(() => { if(PUBLIC_PREVIEW)return; api('history').then(setHistory).catch(()=>setNotice('Chưa tải được lịch sử của tài khoản.')); }, [account.id]);
  useEffect(() => { if (!notice) return; const t = setTimeout(() => setNotice(''), 6500); return () => clearTimeout(t); }, [notice]);
  function invalidate() { setOutput(''); setTiming(null); setError(''); setTranslatedLayout(null); }
  function chooseSource(value: string) {
    const previous = source === 'auto' ? detected?.code : source;
    setSource(value);
    if (value === target) setTarget(previous && previous !== value ? previous : value === 'vi' ? 'lo' : 'vi');
    invalidate();
  }
  function swap() {
    const resolved = source === 'auto' ? detected?.code : source;
    if (!resolved) { setError('Chưa xác định được ngôn ngữ để đảo chiều. Nhập thêm chữ hoặc chọn nguồn thủ công.'); return; }
    setSource(target); setTarget(resolved); setInput(output || input); setImagePreview(null); setFileName(''); invalidate();
    if(tab==='image')setTab('text');
  }
  async function translate() {
    if (locked || requestActive.current || (!input.trim() && !(tab==='image' && imageFileRef.current))) return;
    if(health.model!=='ready'){setError(isAdmin?'Mở mục quản trị để kiểm tra kết nối dịch.':contactAdmin);return;}
    requestActive.current=true;
    setBusy(true); setError(''); setNotice(''); setOutput(''); setTiming(null); setTranslatedLayout(null);
    try {
      if(tab==='image' && imageFileRef.current){await translateVisual(imageFileRef.current,{source,target});return;}
      await translateContent(input, tab === 'image' && imagePreview ? layout : null, !!fileName);
    } catch (e) { setError(e instanceof Error ? e.message : 'Không dịch được nội dung.'); }
    finally { requestActive.current=false;setBusy(false); }
  }
  async function translateVisual(file:File,languages={source,target}) {
    const data=new FormData();data.append('file',file);data.append('source',languages.source);data.append('target',languages.target);
    const result=await api('translate-image-vision',{method:'POST',body:data});
    setInput(result.source_text);setOutput(result.text);setLayout(result.layout);setTranslatedLayout(result.layout);
    setDetected(result.detection);setOcrSource(result.source);setTiming(result.elapsed_ms);
    if(result.warnings?.length)setNotice(result.warnings.join(' '));
    if(remember){try{setHistory(await api('history',jsonRequest('POST',{input:result.source_text,output:result.text,source:result.source,target:languages.target})));}catch{setNotice('Bản dịch đã xong nhưng chưa lưu được lịch sử.');}}
  }
  async function translateContent(text:string, imageLayout:Layout|null, fromFile:boolean, languages={source,target}) {
    const lines = text.split('\n');
    const useLayout = imageLayout && lines.length === imageLayout.regions.length;
    const regions = useLayout ? imageLayout.regions.map((region,i) => ({ ...region, text: lines[i] })) : undefined;
    const resolvedSource = imageLayout && languages.source==='auto' && ocrSource && ocrSource!==languages.target ? ocrSource : languages.source;
    const data = await api(useLayout ? 'translate-image' : 'translate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, source:resolvedSource, target:languages.target, regions, document:fromFile }) });
    setOutput(data.text); setTiming(data.elapsed_ms);
    if (data.detection) setDetected(data.detection);
    if (data.unchanged) setNotice('Nội dung đã là ngôn ngữ đích; giữ nguyên văn bản.');
    if (useLayout && data.regions) setTranslatedLayout({ ...imageLayout, regions: data.regions });
    else if (tab === 'image') setNotice('Số dòng đã thay đổi hoặc chưa có tọa độ OCR; chỉ hiển thị bản dịch văn bản. Chọn lại ảnh để tạo ảnh dịch.');
    if (remember) { try { setHistory(await api('history',jsonRequest('POST',{input:text,output:data.text,source:data.source,target:languages.target}))); } catch { setNotice('Bản dịch đã xong nhưng chưa lưu được lịch sử.'); } }
  }
  async function upload(file?: File, languages={source,target}) {
    if (!file || locked || requestActive.current) return;
    if (file.size > 10 * 1024 * 1024) { setError('File tối đa 10 MB.'); return; }
    const image = /\.(png|jpe?g|webp)$/i.test(file.name);
    if (tab === 'image' && !image) { setError('Hãy chọn ảnh PNG, JPG hoặc WEBP.'); return; }
    requestActive.current=true;setNotice('');
    imageFileRef.current = image ? file : null;
    setImagePreview(image ? URL.createObjectURL(file) : null);
    setFileName(file.name); setInput(''); setLayout(null); setOcrSource(null); setDetected(null); invalidate();
    setExtracting(true); setError('');
    const data = new FormData(); data.append('file', file); data.append('language', languages.source);
    try {
      if(tab==='image' && image){
        if(health.model!=='ready'){setError(isAdmin?'Mở mục quản trị để kiểm tra kết nối dịch.':contactAdmin);return;}
        setBusy(true);await translateVisual(file,languages);return;
      }
      const result = await api('extract', { method: 'POST', body: data });
      const detectedSource = languages.source==='auto' ? result.detection?.code : languages.source;
      setOcrSource(detectedSource || null);
      setInput(result.text); setLayout(result.layout || null); setDetected(result.detection || null); invalidate(); setFileName(result.filename); setNotice(result.warnings.join(' '));
      if(health.model!=='ready'){setError(isAdmin?'Mở mục quản trị để kiểm tra kết nối dịch.':contactAdmin);return;}
      setBusy(true);
      await translateContent(result.text, tab==='image' && image ? result.layout || null : null, true,
        {...languages, source:detectedSource && detectedSource!==languages.target ? detectedSource : languages.source});
    } catch (e) { setError(e instanceof Error ? e.message : 'Không đọc được file.'); }
    finally { requestActive.current=false;setBusy(false); setExtracting(false); if (fileRef.current) fileRef.current.value = ''; }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(output); setNotice('Đã sao chép bản dịch.'); }
    catch { setError('Không truy cập được clipboard. Hãy chọn và sao chép văn bản thủ công.'); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([output], { type: 'text/plain;charset=utf-8' }));
    const a = document.createElement('a'); a.href = url; a.download = `kun-global-${source}-${target}.txt`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function downloadWord(){
    if(!output||locked)return;
    setWordBusy(true);setError('');
    try{
      let blob:Blob;
      if(tab==='image'&&translatedLayout&&imageFileRef.current){
        const form=new FormData();form.append('file',imageFileRef.current);form.append('layout',JSON.stringify(translatedLayout));
        blob=await accountFile('export-word-image',{method:'POST',body:form});
      }else blob=await accountFile('export-word',jsonRequest('POST',{text:output}));
      saveWord(blob,`kun-global-${target}-a4.docx`);setNotice('Đã chuẩn bị Word A4 nền trắng. Chữ và bảng có thể chỉnh sửa trong Word.');
    }catch(e){setError(e instanceof Error?e.message:'Không xuất được Word.');}
    finally{setWordBusy(false);}
  }
  async function removeHistory(id?:string){try{await api(id?`history/${id}`:'history',{method:'DELETE'});setHistory(items=>id?items.filter(e=>e.id!==id):[]);}catch{setNotice('Chưa xóa được lịch sử. Vui lòng thử lại.');}}
  return <div className="translator-page">
    <header className="translator-header"><a className="brand" href="/" aria-label="KUN GLOBAL trang chủ"><span className="brand-logo-frame"><img src="/kun-global-logo-v2.png" alt="KUN GLOBAL" width="1033" height="1042"/></span><span className="translator-wordmark" aria-hidden="true"><strong>KUN GLOBAL</strong><small>KHÔNG GIAN DỊCH THUẬT</small></span></a><nav aria-label="Tài khoản và tiện ích"><button aria-label="Lịch sử" title="Lịch sử dịch" disabled={PUBLIC_PREVIEW} onClick={() => setHistoryOpen(true)}><History size={18}/><span>Lịch sử</span>{history.length > 0 && <b className="count">{history.length}</b>}</button><button className="install" aria-label="Cài ứng dụng" onClick={async () => { if (install) { await install.prompt(); setInstall(null); } else setNotice('Cài ứng dụng từ menu trình duyệt → Cài đặt ứng dụng / Thêm vào màn hình chính. iPhone: Safari → Chia sẻ → Thêm vào MH chính. Cần HTTPS hoặc localhost.'); }}><Download size={17}/><span>Cài ứng dụng</span></button><button className="account-menu-button" aria-label={account.role==='admin'?'Quản trị và tài khoản':'Tài khoản'} disabled={locked||PUBLIC_PREVIEW} onClick={()=>setAccountOpen(true)}><UserRound size={17}/><span>{account.username}</span></button><button className="header-logout" aria-label={PUBLIC_PREVIEW?'Về trang chủ':loggingOut?'Đang đăng xuất…':'Đăng xuất'} disabled={locked} onClick={()=>void signOut()}><LogOut size={17}/><span>{PUBLIC_PREVIEW?'Về trang chủ':loggingOut?'Đang đăng xuất…':'Đăng xuất'}</span></button></nav></header>
    <main className="translator-main">{PUBLIC_PREVIEW&&<div className="public-preview-notice" role="status">{PREVIEW_NOTICE}</div>}
      <section className="intro"><div className="intro-copy"><div className="eyebrow"><span/> KUN GLOBAL · KẾT NỐI GIÁ TRỊ</div><h1>Một không gian.<br/><span>Kết nối mọi ngôn ngữ.</span></h1><p>Dịch văn bản, hình ảnh và tài liệu của bạn.<br className="desktop"/> Bắt đầu từ điều bạn muốn thấu hiểu hôm nay.</p><div className="intro-languages"><Languages size={15}/><span>TIẾNG VIỆT</span><i/><span>ENGLISH</span><i/><span>中文</span><i/><span>한국어</span><span>20 ngôn ngữ</span></div></div></section>
      <div className="workspace-heading"><div><span className="translator-section-label">KHÔNG GIAN LÀM VIỆC</span><h2>Bàn dịch của bạn</h2></div><p>{tab==='text'?'Nhập nội dung, chọn ngôn ngữ và bắt đầu dịch.':tab==='image'?'Đọc chữ trong ảnh, kết nối ý nghĩa.':'Từ tài liệu gốc đến bản dịch của bạn.'}</p></div>
      {health.model==='unconfigured'&&<div className="connect-banner"><div><strong>{isAdmin?'Cấu hình API để bắt đầu dịch':'Chưa được cấp quyền sử dụng'}</strong><span>{isAdmin?'Admin cấu hình OpenAI API dùng chung cho các user.':contactAdmin}</span></div>{isAdmin&&<button onClick={()=>{setAccountUser(null);setAccountSection('provider');setAccountOpen(true);}}>Cấu hình API <ArrowRight size={16}/></button>}</div>}<section className="workspace" aria-label="Trình dịch"><div className="workspace-top"><div className="tabs" role="tablist" aria-label="Loại nội dung">{([{ key: 'text', label: 'Văn bản', hint: 'Nhập và dịch', icon: Languages }, { key: 'image', label: 'Hình ảnh', hint: 'Đọc chữ trong ảnh', icon: Image }, { key: 'document', label: 'Tài liệu', hint: 'PDF, DOCX, TXT', icon: FileText }] as const).map(t => <button key={t.key} role="tab" aria-label={t.label} aria-selected={tab === t.key} disabled={locked} className={tab === t.key ? 'active' : ''} onClick={() => { setTab(t.key); setError(''); }}><span className="tab-icon"><t.icon size={19}/></span><span className="tab-copy"><strong>{t.label}</strong><small>{t.hint}</small></span></button>)}</div><div className={`status ${health.model === 'ready' ? 'ready' : ''}`} title={health.message}><span/>{PUBLIC_PREVIEW?'Xem giao diện':health.model === 'ready' ? (isAdmin?'API đã cấu hình':'Sẵn sàng dịch') : health.model === 'loading' ? 'Đang cấu hình' : health.model === 'checking' ? 'Đang kết nối' : (isAdmin?'Chưa cấu hình API':'Chưa được cấp quyền')}</div></div>
      {isAdmin&&health.model==='ready'&&<div className="plan-usage"><span>Sử dụng OpenAI API</span><a href="https://platform.openai.com/usage" target="_blank" rel="noreferrer">Xem sử dụng API</a></div>}{tab==='document'&&<div className="document-mode"><button disabled={locked} aria-pressed={documentMode==='form'} onClick={()=>setDocumentMode('form')}>Dịch giữ form · PDF / DOCX / TXT</button><button disabled={locked} aria-pressed={documentMode==='text'} onClick={()=>setDocumentMode('text')}>Chỉ lấy nội dung văn bản</button></div>}
      {tab==='document'&&documentMode==='form'&&<PreservedDocumentWorkspace languages={langs} onBusy={setDocumentBusy} canTranslate={health.model==='ready'}/>}
      <div className="legacy-panel" hidden={tab==='document'&&documentMode==='form'}>
      {tab !== 'text' && <div className="upload-zone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}><span className="upload-icon"><Upload size={23}/></span><div><strong>{extracting ? 'Đang trích xuất văn bản…' : tab === 'image' ? 'Tải ảnh để tự dịch' : 'Tải tài liệu để tự dịch'}</strong><p>{tab === 'image' ? 'PNG, JPG, WEBP · Đọc ảnh gốc và dịch toàn bộ nội dung' : 'PDF có văn bản, DOCX, TXT · Tối đa 30 trang PDF'} · 10 MB</p></div><button disabled={locked} className="secondary" onClick={() => fileRef.current?.click()}>{extracting ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>}Chọn {tab === 'image' ? 'ảnh' : 'tài liệu'}</button><input hidden ref={fileRef} type="file" accept={tab === 'image' ? '.png,.jpg,.jpeg,.webp' : '.pdf,.docx,.txt'} onChange={e => upload(e.target.files?.[0])}/></div>}
      <div className="language-bar">
        <label className="language-choice"><span className="mini-label">NGÔN NGỮ NGUỒN</span><select aria-label="Ngôn ngữ nguồn" value={source} disabled={locked} onChange={e => chooseSource(e.target.value)}><option value="auto">Tự phát hiện</option>{langs.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
        <button className="swap" title="Đảo chiều ngôn ngữ" aria-label="Đảo chiều ngôn ngữ" disabled={locked || (source==='auto' && !detected)} onClick={swap}><ArrowLeftRight size={19}/></button>
        <label className="language-choice"><span className="mini-label">NGÔN NGỮ ĐÍCH</span><select aria-label="Ngôn ngữ đích" value={target} disabled={locked} onChange={e => { const value = e.target.value; setTarget(value); if (value === source) setSource(target); invalidate(); }}>{langs.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}</select></label>
      </div>
      {source==='auto' && <div className="detected-language" role="status">{extracting ? 'Đang phát hiện ngôn ngữ và đọc file…' : detecting ? 'Đang nhận diện ngôn ngữ…' : detected ? `Đã phát hiện: ${name(detected.code)}${detected.uncertain ? ' · Có thể chưa chính xác, bạn có thể chọn nguồn thủ công.' : ''}` : input.trim() ? 'Chưa xác định chắc chắn. Nhập thêm chữ hoặc chọn nguồn thủ công.' : 'Tự nhận diện ngôn ngữ khi nhập chữ hoặc tải file. Có thể chọn nguồn thủ công.'}</div>}
      <div className={`editors ${tab === 'image' && imagePreview ? 'image-editors' : ''}`}>
        <div className="editor input-editor">
          <div className="editor-heading"><span><FileText size={15}/>Nội dung gốc</span><small>{source === 'auto' ? (detected ? name(detected.code) : 'Tự phát hiện') : name(source)}</small></div>
          {fileName && <div className="file-tag"><FileText size={13}/><span>{fileName}</span><button aria-label="Bỏ tên file" disabled={locked} onClick={() => {setFileName('');setInput('');setLayout(null);setDetected(null);invalidate();}}><X size={12}/></button></div>}
          {tab === 'image' && imagePreview && <ImagePreview key={imagePreview} url={imagePreview} name={fileName}/>}
          <textarea lang={source==='auto'?detected?.code:source} aria-label="Văn bản cần dịch" placeholder="Nhập hoặc dán nội dung cần dịch…" value={input} maxLength={12000} readOnly={tab==='image'&&!!imagePreview} disabled={locked} onChange={e => { setInput(e.target.value); invalidate(); }} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); translate(); } }}/>
          <div className="editor-bottom"><span>{extracting ? 'Đang đọc chữ trong ảnh…' : tab==='image'&&imagePreview ? `${input.length.toLocaleString('vi-VN')} ký tự đọc từ ảnh gốc` : `${input.length.toLocaleString('vi-VN')} / 12.000 ký tự`}</span><button title="Xóa nội dung" aria-label="Xóa nội dung" disabled={locked || (!input && !imagePreview)} onClick={() => { setInput(''); setFileName(''); setLayout(null);setDetected(null);invalidate(); }}><Trash2 size={17}/></button></div>
        </div>
        <div className="editor output-editor"><div className="editor-heading"><span><Sparkles size={15}/>Bản dịch</span><small>{name(target)}</small></div>{busy ? <div className="empty translating"><LoaderCircle className="spin" size={28}/><p>Đang dịch nội dung…</p><small>Đã xử lý {elapsed} giây · Giữ trang mở để nhận kết quả.</small></div> : output ? (tab === 'image' && imagePreview && translatedLayout ? <TranslatedImage src={imagePreview} layout={translatedLayout} text={output} target={target} onDownloadWord={()=>void downloadWord()} wordBusy={wordBusy}/> : <div className="result" lang={target} dir={target==="ar"?"rtl":undefined}>{output}</div>) : <div className="empty"><span className="empty-icon"><Languages size={30}/></span><p>Sẵn sàng kết nối ngôn ngữ</p><small>Nhập nội dung cần dịch và chọn Dịch ngay.</small></div>}<div className="editor-bottom"><span>{timing !== null ? `Hoàn thành trong ${(timing / 1000).toFixed(1)} giây` : 'Kết quả sẽ hiển thị tại đây'}</span><div><button className="word-export-button" aria-label="Tải bản dịch Word A4" title="Word A4 · Nền trắng, chữ và bảng chỉnh sửa được" onClick={downloadWord} disabled={!output || locked}>{wordBusy?<LoaderCircle className="spin" size={17}/>:<FileText size={17}/>}<span>Word A4</span></button><button aria-label="Tải bản dịch TXT" title="Tải bản dịch TXT" onClick={download} disabled={!output || locked}><Download size={17}/></button><button aria-label="Sao chép bản dịch" title="Sao chép bản dịch" onClick={copy} disabled={!output || locked}><Copy size={17}/></button></div></div></div>
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      {!online && <div className="error"><WifiOff size={17}/>Bạn đang offline. Có thể xem lịch sử; dịch và đọc file cần kết nối máy chủ.</div>}
      <div className="workspace-bottom"><div className="workspace-privacy"><span><LockKeyhole size={18}/></span><div><strong>Dịch thuật đa ngôn ngữ</strong><small>{health.model==='ready'?(isAdmin?(tab==='image'?'Ảnh và nội dung cần dịch được gửi đến OpenAI.':'Văn bản cần dịch được gửi đến OpenAI.'):'Nội dung được xử lý tại máy chủ dịch.'):'Quyền sử dụng do quản trị viên cấp.'}</small></div></div><button className="primary" onClick={translate} disabled={locked || (!input.trim() && !(tab==='image' && imageFileRef.current)) || !online || health.model !== 'ready'}>{busy ? <LoaderCircle className="spin" size={18}/> : null}{busy ? 'Đang dịch' : 'Dịch ngay'}{!busy && <ArrowRight size={18}/>}</button></div></div></section>
      <div className="under-workspace"><span><ShieldCheck size={14}/> Lịch sử riêng theo tài khoản</span><span>Phím tắt <kbd>Ctrl</kbd> + <kbd>Enter</kbd></span></div>
      <div className="desk-bottom">
        <section className="desk-benefits" aria-label="Tiện ích của KUN GLOBAL">
          <div className="desk-benefit"><span className="desk-benefit-icon"><Languages size={23} strokeWidth={1.6}/></span><div><h3>Dịch đa ngôn ngữ</h3><p>Tự phát hiện và chuyển đổi ngôn ngữ.</p></div></div>
          <div className="desk-benefit"><span className="desk-benefit-icon"><ShieldCheck size={23} strokeWidth={1.6}/></span><div><h3>Tài khoản riêng biệt</h3><p>Lịch sử và tài liệu theo từng tài khoản.</p></div></div>
          <div className="desk-benefit"><span className="desk-benefit-icon"><Download size={23} strokeWidth={1.6}/></span><div><h3>Mang theo mọi nơi</h3><p>Cài ứng dụng lên màn hình điện thoại.</p></div></div>
        </section>
        <footer className="desk-footer">
          <div className="desk-footer-top">
            <a className="desk-footer-brand" href="/" aria-label="Về trang chủ KUN GLOBAL"><img src="/kun-global-logo-v2.png" alt="" width="1033" height="1042"/><span><strong>KUN GLOBAL</strong><small>Kết nối giá trị · Vươn tầm quốc tế</small></span></a>
            <div className="desk-footer-note"><span>LƯU Ý VỀ BẢN DỊCH</span><p>Dịch máy có thể sai. Hãy kiểm tra lại<br className="desk-note-break"/> nội dung quan trọng trước khi sử dụng.</p></div>
            <div className="desk-footer-support"><span>ĐỒNG HÀNH CÙNG BẠN</span><a href="tel:+84986839092">Liên hệ hỗ trợ<ArrowRight size={16}/></a></div>
          </div>
          <div className="desk-footer-bottom"><span>© 2026 KUN GLOBAL</span><div><a href="/">Trang chủ</a><span aria-hidden="true"/><a href="mailto:lienhekuni@gmail.com">Gửi email</a></div><span className="desk-footer-sign"><Languages size={14}/>DỊCH THUẬT ĐA NGÔN NGỮ</span></div>
        </footer>
      </div>
    </main>
    {accountOpen&&<AccountPanel account={account} initialUserId={accountUser} initialSection={accountSection} canTranslate={health.model==='ready'} onClose={()=>{setAccountOpen(false);setAccountUser(null);setAccountSection(undefined);}} onLogout={onLogout} onRefresh={onRefresh}/>}
    {notice && <div className="toast" role="status"><Check size={18}/><span>{notice}</span><button aria-label="Đóng thông báo" onClick={() => setNotice('')}><X size={16}/></button></div>}
    {historyOpen && <div className="modal-backdrop" onClick={() => setHistoryOpen(false)}><section className="history-panel" role="dialog" aria-modal="true" aria-label="Lịch sử dịch" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape') setHistoryOpen(false); }}><div className="history-heading"><div><h2>Lịch sử dịch</h2><p>Chỉ tài khoản này xem · tối đa 30 bản dịch.</p></div><button autoFocus aria-label="Đóng lịch sử" onClick={() => setHistoryOpen(false)}><X/></button></div><label className="remember"><input type="checkbox" checked={remember} onChange={e => { setRemember(e.target.checked); localStorage.setItem(preferenceKey, String(e.target.checked)); }}/>Lưu các bản dịch tiếp theo vào tài khoản</label>{history.length ? <><button className="clear-history" onClick={() => { if (confirm('Xóa toàn bộ lịch sử của tài khoản này?')) void removeHistory(); }}><Trash2 size={15}/>Xóa tất cả</button><div className="history-list">{history.map(item => <article key={item.id}><div className="history-meta">{name(item.source)} → {name(item.target)}<button aria-label="Xóa bản dịch này" onClick={() => void removeHistory(item.id)}><Trash2 size={14}/></button></div><button className="history-item" onClick={() => { setInput(item.input); setOutput(item.output); setSource(item.source); setTarget(item.target); setError(''); setFileName(''); setTiming(null); setTab('text'); setHistoryOpen(false); }}><p>{item.input}</p><p>{item.output}</p><small>{new Date(item.date).toLocaleString('vi-VN')}</small></button></article>)}</div></> : <div className="history-empty"><History size={36}/><h3>Chưa có bản dịch nào</h3><p>Các bản dịch thành công sẽ xuất hiện ở đây.</p></div>}</section></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><AccountGate>{(account,logout,refresh)=><App key={account.id} account={account} onLogout={logout} onRefresh={refresh}/>}</AccountGate></React.StrictMode>);
