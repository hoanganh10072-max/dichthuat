import {useEffect,useState} from 'react';
import {ExternalLink,LoaderCircle,ShieldCheck} from 'lucide-react';
import {accountApi,jsonRequest,type Account} from './account-api';
import './chatgpt.css';

type Connection={local_enabled:boolean;callback_ready:boolean;connected:boolean;sharing:boolean;needs_reconnect:boolean;ready:boolean;email:string;model:string;message:string;attempt?:{status:string;message:string}};
type Model={slug:string;display_name:string};
export function ChatGPTConnection({managedUser,onBusyChange}:{managedUser?:Account;onBusyChange?:(busy:boolean)=>void}={}){
  const prefix=managedUser?`admin/users/${encodeURIComponent(managedUser.id)}/chatgpt`:'chatgpt';
  const statusPath=managedUser?prefix:`${prefix}/status`;
  const [status,setStatus]=useState<Connection|null>(null),[models,setModels]=useState<Model[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  function changed(){window.dispatchEvent(new Event('kun-chatgpt-changed'));}
  async function load(){const data:Connection=await accountApi(statusPath);setStatus(data);setModels([]);if(data.connected&&data.sharing&&!data.needs_reconnect){setModels(await accountApi(`${prefix}/models`));setStatus(await accountApi(statusPath));}changed();}
  async function action(fn:()=>Promise<void>){setBusy(true);onBusyChange?.(true);setError('');setNotice('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'Không kết nối được ChatGPT.');}finally{setBusy(false);onBusyChange?.(false);}}
  useEffect(()=>{void action(load);},[]);
  async function connect(){const data=await accountApi(`${prefix}/connect`,{method:'POST'});const url=new URL(data.authorization_url);if(url.origin!=='https://auth.openai.com')throw new Error('Địa chỉ đăng nhập không hợp lệ.');window.location.assign(url.href);}
  return <div className="chatgpt-connection"><div className="chatgpt-intro"><span className="chatgpt-shield"><ShieldCheck size={26}/></span><div><h3>{managedUser?`ChatGPT cho ${managedUser.username}`:'ChatGPT của tôi'}</h3><p>{managedUser?'Admin kết nối hộ. User chỉ cần đăng nhập app và dịch.':'Dùng gói ChatGPT riêng để dịch. Không cần khóa API.'}</p></div></div>
    <div className="chatgpt-status"><span className={status?.ready?'connection-dot ready':'connection-dot'}/><div><strong>{status?.ready?'Sẵn sàng dịch':status?.connected?'Cần hoàn tất kết nối':'Chưa kết nối ChatGPT'}</strong><small>{status?.email||'Mỗi người dùng kết nối tài khoản của mình.'}</small></div></div>
    <p>{managedUser?`Đăng nhập tài khoản ChatGPT riêng của ${managedUser.username} trên trang OpenAI, khi đã được người đó đồng ý. Kết nối chỉ lưu cho user này; user sẽ không cần tự làm bước kết nối.`:'Đăng nhập trên trang chính thức của OpenAI và cấp quyền sử dụng gói ChatGPT cho KUN GLOBAL.'} Văn bản cần dịch được gửi đến OpenAI; OCR và ghép PDF chạy trên máy bạn.</p>
    {managedUser&&!managedUser.active&&<div className="account-error">User đang bị khóa. Mở khóa trước khi kết nối ChatGPT.</div>}
    {status&&!status.local_enabled&&<div className="account-error">Bản này chỉ hỗ trợ app chạy trên máy riêng. Hãy mở bằng localhost trên máy đã cài app.</div>}
    {status?.local_enabled&&!status.callback_ready&&<div className="account-error">Chưa mở được cổng nhận đăng nhập. Khởi động lại app hoặc đổi CHATGPT_CALLBACK_PORT theo README.</div>}
    {status?.connected&&!status.sharing&&<div className="account-error">Bạn mới đăng nhập nhận diện tài khoản. Cần kết nối lại và cấp quyền dùng gói ChatGPT để dịch.</div>}
    {status?.needs_reconnect&&<div className="account-error">Kết nối đã hết hạn. Hãy đăng nhập ChatGPT lại.</div>}
    {status?.attempt?.status==='failed'&&<div className="account-error">{status.attempt.message}</div>}
    {error&&<div className="account-error" role="alert">{error}</div>}{notice&&<div className="account-notice" role="status">{notice}</div>}
    <button type="button" onClick={()=>void action(connect)} data-oai-siwc-button className="chatgpt-signin" disabled={busy||!status?.local_enabled||!status.callback_ready||(!!managedUser&&!managedUser.active)}>{busy?<LoaderCircle size={18} className="spin"/>:null}Continue with ChatGPT<ExternalLink size={16}/></button>
    {status?.local_enabled&&!status.connected&&<p className="chatgpt-local-note">Lần đầu kết nối, nếu OpenAI hiện ô tên tác nhân, hãy giữ tên gợi ý KUN GLOBAL và xác nhận cấp quyền.</p>}
    {models.length>0&&<label className="chatgpt-model">{managedUser?'Mô hình dùng cho user này':'Mô hình của tài khoản bạn'}<select value={status?.model||''} disabled={busy} onChange={e=>void action(async()=>{setStatus(await accountApi(`${prefix}/model`,jsonRequest('PUT',{model:e.target.value})));changed();})}>{models.map(model=><option key={model.slug} value={model.slug}>{model.display_name}</option>)}</select></label>}
    <div className="chatgpt-actions"><button className="secondary" disabled={busy} onClick={()=>void action(load)}>Làm mới trạng thái</button><a href="https://chatgpt.com/#settings/Usage" target="_blank" rel="noreferrer">Xem hạn mức ChatGPT <ExternalLink size={14}/></a></div>
    {status?.connected&&<button className="account-logout" disabled={busy} onClick={()=>void action(async()=>{const result=await accountApi(`${prefix}/disconnect`,{method:'POST'});await load();setNotice(result.message||'Đã ngắt kết nối.');})}>Ngắt kết nối ChatGPT{managedUser?` của ${managedUser.username}`:''}</button>}
    <small className="chatgpt-local-note">Dành cho bản cài trên máy riêng. Hạn mức và mô hình phụ thuộc gói ChatGPT của bạn. Đăng xuất app và ngắt kết nối ChatGPT là hai thao tác riêng.</small>
  </div>;
}
