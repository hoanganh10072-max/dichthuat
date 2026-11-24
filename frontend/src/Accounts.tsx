import {useEffect,useState,type ReactNode} from 'react';
import {ArrowLeft,ArrowRight,Eye,EyeOff,FileText,Image,Languages,LoaderCircle,LockKeyhole,LogOut,Phone,Settings,ShieldCheck,UserRound,Users,X} from 'lucide-react';
import {accountApi,jsonRequest,type Account} from './account-api';
import './accounts.css';
import './login.css';
import {APISettings} from './APISettings';
import {AdminUsers} from './AdminUsers';
import {LandingPage} from './LandingPage';
import {PUBLIC_PREVIEW,PREVIEW_NOTICE} from './public-preview';
import OnlineTrial from './OnlineTrial';
const HOSTED_APP=import.meta.env.VITE_HOSTED_APP==='true';

export function AccountGate({children}:{children:(account:Account,logout:()=>Promise<void>,refresh:()=>Promise<void>)=>ReactNode}) {
  const [account,setAccount]=useState<Account|null>(null),[loading,setLoading]=useState(!PUBLIC_PREVIEW);
  const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[setup,setSetup]=useState(false);
  const [busy,setBusy]=useState(false);
  const [showPassword,setShowPassword]=useState(false);
  const [path,setPath]=useState(window.location.pathname);
  function navigate(destination:string,replace=false){
    if(replace)window.history.replaceState(null,'',destination);
    else window.history.pushState(null,'',destination);
    setPath(window.location.pathname);window.scrollTo(0,0);
  }
  async function refresh(){
    if(PUBLIC_PREVIEW)return;
    const data=await accountApi('auth/session');setAccount(data.user);setSetup(data.setup_required);
    if(window.location.pathname==='/'&&new URLSearchParams(window.location.search).has('chatgpt')){
      navigate((data.user?'/app':'/login')+window.location.search,true);
    }
  }
  useEffect(()=>{const update=()=>setPath(window.location.pathname);window.addEventListener('popstate',update);return()=>window.removeEventListener('popstate',update);},[]);
  useEffect(()=>{
    if(loading||PUBLIC_PREVIEW)return;
    if(path==='/app'&&!account)navigate('/login'+window.location.search,true);
    else if(path==='/login'&&account)navigate('/app'+window.location.search,true);
  },[path,account,loading]);
  useEffect(()=>{void refresh().catch(()=>setError('Chưa kết nối được máy chủ.')).finally(()=>setLoading(false));
    const expired=()=>{setAccount(null);setPassword('');setError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');navigate('/login',true);};
    window.addEventListener('kun-auth-expired',expired);return()=>window.removeEventListener('kun-auth-expired',expired);
  },[]);
  async function login(e:React.FormEvent){e.preventDefault();if(PUBLIC_PREVIEW){navigate('/app');return;}setBusy(true);setError('');try{const data=await accountApi('auth/login',jsonRequest('POST',{username,password}));setPassword('');setAccount(data.user);navigate('/app'+window.location.search,true);}catch(e){setError(e instanceof Error?e.message:'Không đăng nhập được.');}finally{setBusy(false);}}
  async function logout(){await accountApi('auth/logout',{method:'POST'});setAccount(null);setPassword('');setError('');navigate('/',true);}
  if(loading)return <div className="account-loading"><LoaderCircle className="spin"/> Đang kết nối KUN GLOBAL…</div>;
  if(path==='/')return <LandingPage signedIn={!!account} onStart={()=>navigate(account?'/app':'/login')}/>;
  if(HOSTED_APP&&account)return <OnlineTrial account={account} onHome={()=>navigate('/')} onLogout={logout} onRefresh={refresh}/>;
  // Anonymous, read-only UI preview. This is not a logged-in backend session.
  if(PUBLIC_PREVIEW&&path==='/app')return children({id:'public-ui-preview',username:'Xem giao diện',role:'user',active:false,created_at:0},async()=>navigate('/'),refresh);
  if(account)return children(account,logout,refresh);
  return <main className="login-page">
    <div className="login-topbar">
      <a className="login-wordmark" href="/" aria-label="KUN GLOBAL trang chủ" onClick={event=>{if(!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();navigate('/');}}}><img src="/kun-global-logo-v2.png" alt="" width="1033" height="1042"/><span><strong>KUN GLOBAL</strong><small>KẾT NỐI GIÁ TRỊ · VƯƠN TẦM QUỐC TẾ</small></span></a>
      <a className="login-home-link" href="/" onClick={event=>{if(!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();navigate('/');}}}><ArrowLeft size={15}/><span>Về trang chủ</span></a>
    </div>
    <div className="login-layout">
      <section className="login-story" aria-labelledby="login-story-title">
        <div className="login-story-copy"><span className="login-eyebrow"><span/> KHÔNG GIAN DỊCH THUẬT</span><h2 id="login-story-title">Kết nối ngôn ngữ.<br/><em>Mở rộng thế giới.</em></h2><p>Từ một câu chào đến những hồ sơ quan trọng.<br/>Mỗi bản dịch, một bước kết nối gần hơn.</p><div className="login-formats" aria-label="Các loại nội dung có thể dịch"><span><Languages size={15}/>Văn bản</span><span><Image size={15}/>Hình ảnh</span><span><FileText size={15}/>Tài liệu</span></div></div>
        <div className="login-story-caption"><span/>Hồ sơ của bạn.<br/><strong>Là trách nhiệm của chúng tôi.</strong></div>
      </section>
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-card-inner"><span className="login-symbol"><ShieldCheck size={23} strokeWidth={1.6}/></span><span className="login-card-eyebrow">TÀI KHOẢN KUN GLOBAL</span><h1 id="login-title">Chào mừng trở lại.</h1><p className="login-description">Đăng nhập để bắt đầu dịch văn bản,<br className="login-desktop-break"/> hình ảnh và tài liệu của bạn.</p>
          {PUBLIC_PREVIEW&&<p className="public-preview-notice" role="status">{PREVIEW_NOTICE} Bấm Đăng nhập để xem giao diện bên trong; không cần nhập mật khẩu.</p>}<form onSubmit={login} aria-busy={busy}>
            <div className="login-field"><label htmlFor="login-username">Tên đăng nhập</label><div className="login-input-wrap"><UserRound size={18} aria-hidden="true"/><input id="login-username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} placeholder={PUBLIC_PREVIEW?"Không cần nhập khi xem thử":"Nhập tên đăng nhập"} required={!PUBLIC_PREVIEW} maxLength={64} disabled={busy||PUBLIC_PREVIEW} aria-describedby={error?'login-error':undefined} onChange={e=>setUsername(e.target.value)}/></div></div>
            <div className="login-field"><label htmlFor="login-password">Mật khẩu</label><div className="login-input-wrap"><LockKeyhole size={18} aria-hidden="true"/><input id="login-password" name="password" type={showPassword?'text':'password'} autoComplete="current-password" value={password} placeholder={PUBLIC_PREVIEW?"Không cần nhập khi xem thử":"Nhập mật khẩu"} required={!PUBLIC_PREVIEW} maxLength={256} disabled={busy||PUBLIC_PREVIEW} aria-describedby={error?'login-error':undefined} onChange={e=>setPassword(e.target.value)}/><button type="button" className="login-password-toggle" aria-label={showPassword?'Ẩn mật khẩu':'Hiện mật khẩu'} aria-controls="login-password" aria-pressed={showPassword} disabled={busy} onClick={()=>setShowPassword(value=>!value)}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div>
            {error&&<div id="login-error" className="account-error" role="alert">{error}</div>}
            {setup&&<div className="account-error" role="status">Chưa có tài khoản. Vui lòng liên hệ quản trị viên để được cấp quyền sử dụng.</div>}
            <button className="login-submit" type="submit" disabled={busy||setup}>{busy?<><LoaderCircle size={18} className="spin"/>Đang đăng nhập…</>:<>Đăng nhập<ArrowRight size={18}/></>}</button>
          </form>
          <div className="login-access-note"><ShieldCheck size={16}/><span>{PUBLIC_PREVIEW?"Bản xem thử giao diện; chưa xác thực tài khoản.":"Sử dụng tài khoản do quản trị viên cấp."}</span></div>
          <div className="login-help"><span>Bạn cần hỗ trợ đăng nhập?</span><a href="tel:+84986839092"><Phone size={14}/>Liên hệ KUN GLOBAL<ArrowRight size={14}/></a></div>
        </div>
      </section>
    </div>
    <div className="login-footer"><span>© 2026 KUN GLOBAL</span><span>Một ngôn ngữ mới. Một thế giới gần hơn.</span></div>
  </main>;
}

type Usage={username:string;model:string;requests:number;input_tokens:number;output_tokens:number};
export function AccountPanel({account,onClose,onLogout,onRefresh,initialUserId,initialSection,canTranslate=false}:{account:Account;canTranslate?:boolean;initialUserId?:string|null;initialSection?:'users'|'provider';onClose:()=>void;onLogout:()=>Promise<void>;onRefresh:()=>Promise<void>}) {
  const [tab,setTab]=useState<'profile'|'users'|'provider'|'usage'>(account.role==='admin'?(initialSection||'users'):'profile');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [username,setUsername]=useState(account.username),[currentPassword,setCurrentPassword]=useState(''),[newPassword,setNewPassword]=useState('');
  const [managedBusy,setManagedBusy]=useState(false);
  const [usage,setUsage]=useState<Usage[]>([]);
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'Không thực hiện được.');}finally{setBusy(false);}}
  useEffect(()=>{setError('');setNotice('');if(tab==='usage')void action(async()=>setUsage(await accountApi('admin/usage')));},[tab,initialUserId]);
  return <div className="account-overlay" onClick={onClose}><section className="account-panel" role="dialog" aria-modal="true" aria-label="Tài khoản và quản trị" onClick={e=>e.stopPropagation()}><div className="account-title"><div><span>KUN GLOBAL</span><h2>{account.role==='admin'?'Tài khoản & quản trị':'Tài khoản của bạn'}</h2></div><button aria-label="Đóng quản trị" onClick={onClose}><X/></button></div><div className="account-tabs"><button className={tab==='profile'?'selected':''} onClick={()=>setTab('profile')} disabled={busy||managedBusy}>Tài khoản</button>{account.role==='admin'&&<button className={tab==='provider'?'selected':''} onClick={()=>setTab('provider')} disabled={busy||managedBusy}><Settings size={15}/>OpenAI API</button>}{account.role==='admin'&&<><button className={tab==='users'?'selected':''} onClick={()=>setTab('users')} disabled={busy||managedBusy}><Users size={15}/>Người dùng</button><button className={tab==='usage'?'selected':''} onClick={()=>setTab('usage')} disabled={busy||managedBusy}>Sử dụng</button></>}</div><div className="account-body">{error&&<div className="account-error" role="alert">{error}</div>}{notice&&<div className="account-notice" role="status">{notice}</div>}
    {tab==='profile'&&<>{account.role==='user'&&<div className="account-permission"><strong>{canTranslate?'Đã được cấp quyền sử dụng':'Chưa được cấp quyền sử dụng'}</strong><p>{canTranslate?'Bạn có thể dịch văn bản, hình ảnh và tài liệu.':'Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.'}</p></div>}<p>Đang đăng nhập: <strong>{account.username}</strong> · {account.role==='admin'?'Quản trị viên':'Người dùng'}</p><form onSubmit={e=>{e.preventDefault();void action(async()=>{await accountApi('auth/profile',jsonRequest('PATCH',{username}));await onRefresh();setNotice('Đã đổi tên đăng nhập.');});}}><label>Tên đăng nhập<input value={username} minLength={3} maxLength={64} required onChange={e=>setUsername(e.target.value)}/></label><button className="secondary" disabled={busy||managedBusy}>Lưu tên đăng nhập</button></form><h3>Đổi mật khẩu</h3><form onSubmit={e=>{e.preventDefault();void action(async()=>{await accountApi('auth/password',jsonRequest('POST',{current_password:currentPassword,new_password:newPassword}));setCurrentPassword('');setNewPassword('');setNotice('Đã đổi mật khẩu và đăng xuất các phiên khác.');});}}><label>Mật khẩu hiện tại<input type="password" autoComplete="current-password" value={currentPassword} required onChange={e=>setCurrentPassword(e.target.value)}/></label><label>Mật khẩu mới · ít nhất 12 ký tự<input type="password" autoComplete="new-password" value={newPassword} minLength={12} maxLength={256} required onChange={e=>setNewPassword(e.target.value)}/></label><button className="primary" disabled={busy||managedBusy}>Đổi mật khẩu</button></form><button className="account-logout" disabled={busy||managedBusy} onClick={()=>void action(onLogout)}><LogOut size={16}/>Đăng xuất</button></>}
    {tab==='users'&&account.role==='admin'&&<AdminUsers account={account} initialUserId={initialUserId} onRefresh={onRefresh} onBusyChange={setManagedBusy}/>}
    {tab==='provider'&&account.role==='admin'&&<APISettings/>}
    {tab==='usage'&&<><h3>Sử dụng API trong 30 ngày</h3><p>Số lượt và token được ghi nhận theo tài khoản app. Xem chi phí thực tế trong OpenAI API Dashboard.</p><div className="account-usage">{usage.length?<table><thead><tr><th>Tài khoản</th><th>Mô hình</th><th>Lượt gọi</th><th>Token vào / ra</th></tr></thead><tbody>{usage.map((row,i)=><tr key={i}><td>{row.username||'Hệ thống'}</td><td>{row.model}</td><td>{row.requests}</td><td>{row.input_tokens} / {row.output_tokens}</td></tr>)}</tbody></table>:<p>Chưa có lượt dịch được ghi nhận.</p>}</div></>}
    {busy&&<p className="account-busy"><LoaderCircle className="spin" size={16}/>Đang xử lý…</p>}</div></section></div>;
}
