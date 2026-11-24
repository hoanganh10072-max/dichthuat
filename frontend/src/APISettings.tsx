import {useEffect,useState} from 'react';
import {KeyRound,LoaderCircle} from 'lucide-react';
import {accountApi,jsonRequest} from './account-api';
import './chatgpt.css';

type Settings={model:string;configured:boolean;key_source:'saved'|'environment'|'none'};
export function APISettings(){
  const [settings,setSettings]=useState<Settings|null>(null),[model,setModel]=useState('gpt-4.1-mini'),[key,setKey]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  function changed(){window.dispatchEvent(new Event('kun-chatgpt-changed'));}
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(e instanceof Error?e.message:'Không thực hiện được yêu cầu API.');}finally{setBusy(false);}}
  async function load(){const data:Settings=await accountApi('admin/provider');setSettings(data);setModel(data.model);}
  useEffect(()=>{void action(load);},[]);
  async function save(){
    const data:Settings=await accountApi('admin/provider',jsonRequest('PUT',{model,...(key.trim()?{api_key:key.trim()}: {})}));
    setKey('');setSettings(data);changed();setNotice('Đã lưu cấu hình. Bấm Kiểm tra kết nối để xác nhận khóa và mô hình.');
  }
  return <section className="api-settings"><h3><KeyRound size={19}/> OpenAI API</h3><p>Admin cấu hình một API dùng chung cho các tài khoản đang hoạt động. User đăng nhập app và dịch, không cần kết nối ChatGPT hay nhập khóa.</p>
    <div className="account-permission"><strong>{settings?.configured?'Đã cấu hình khóa API':'Chưa cấu hình khóa API'}</strong><p>{settings?.key_source==='environment'?'Khóa được cấp qua biến môi trường backend.':settings?.configured?'Khóa được mã hóa trong máy chủ; không hiển thị lại.':'Nhập khóa OpenAI API bên dưới để bắt đầu.'}</p></div>
    {error&&<div className="account-error" role="alert">{error}</div>}{notice&&<div className="account-notice" role="status">{notice}</div>}
    <form onSubmit={e=>{e.preventDefault();void action(save);}}><label>Mô hình API<input value={model} onChange={e=>setModel(e.target.value)} required pattern="[a-zA-Z0-9._:\-]+" maxLength={120} disabled={busy}/></label>
      <small>Chọn model hỗ trợ Responses, ảnh/PDF và Structured Outputs. Tên model API có thể khác tên trong ChatGPT.</small>
      <label>Khóa OpenAI API<input type="password" autoComplete="off" spellCheck={false} value={key} placeholder={settings?.configured?'Để trống để giữ khóa hiện tại':'Nhập khóa API'} onChange={e=>setKey(e.target.value)} maxLength={512} disabled={busy}/></label>
      <button className="primary" disabled={busy||!settings}>Lưu cấu hình API</button></form>
    <div className="chatgpt-actions"><button className="secondary" disabled={busy||!settings?.configured||!!key.trim()||model!==settings?.model} onClick={()=>void action(async()=>{const result=await accountApi('admin/provider/test',{method:'POST'});setNotice(result.message);changed();})}>Kiểm tra kết nối</button>
      {settings?.key_source==='saved'&&<button className="secondary" disabled={busy} onClick={()=>void action(async()=>{const data=await accountApi('admin/provider',jsonRequest('PUT',{model:settings.model,clear_key:true}));setSettings(data);setKey('');changed();setNotice(data.configured?'Đã xóa khóa lưu; backend đang dùng khóa từ biến môi trường.':'Đã xóa khóa API lưu trên máy chủ.');})}>Xóa khóa đã lưu</button>}</div>
    <p>API tính phí riêng theo tài khoản OpenAI API; gói ChatGPT không thay thế số dư API. Kiểm tra kết nối gửi một câu thử và có thể phát sinh phí nhỏ. Cần lưu cấu hình trước khi kiểm tra.</p>
    <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">Tạo hoặc quản lý khóa API</a>
    {busy&&<p role="status"><LoaderCircle className="spin" size={16}/> Đang xử lý…</p>}
  </section>;
}
