import {useEffect,useState} from 'react';
import {KeyRound,Plus,RefreshCw,Search,ShieldCheck,Trash2,Users} from 'lucide-react';
import {accountApi,jsonRequest,type Account} from './account-api';

import './admin-users.css';

type ManagedAccount=Account&{active_sessions?:number;history_count?:number};
type Props={account:Account;initialUserId?:string|null;onRefresh:()=>Promise<void>;onBusyChange:(busy:boolean)=>void};
const pageSize=20;
export function AdminUsers({account,initialUserId,onRefresh,onBusyChange}:Props){
  const [users,setUsers]=useState<ManagedAccount[]>([]),[selected,setSelected]=useState<ManagedAccount|null>(null);
  const [query,setQuery]=useState(''),[role,setRole]=useState('all'),[status,setStatus]=useState('all'),[page,setPage]=useState(0);
  const [creating,setCreating]=useState(false),[section,setSection]=useState<'profile'>('profile');
  const [deleteTarget,setDeleteTarget]=useState<ManagedAccount|null>(null);
  const [name,setName]=useState(''),[editRole,setEditRole]=useState<'user'|'admin'>('user'),[active,setActive]=useState(true),[password,setPassword]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const locked=busy;
  useEffect(()=>{onBusyChange(locked);},[locked,onBusyChange]);
  useEffect(()=>()=>onBusyChange(false),[onBusyChange]);
  function select(user:ManagedAccount|null){
    setDeleteTarget(null);
    setSelected(user);setCreating(!user);setSection('profile');setName(user?.username||'');setEditRole(user?.role||'user');setActive(!!(user?.active??true));setPassword('');
  }
  async function load(){const list:ManagedAccount[]=await accountApi('admin/users');setUsers(list);return list;}
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'Không quản lý được tài khoản.');}finally{setBusy(false);}}
  useEffect(()=>{
    let current=true;setBusy(true);setError('');
    void accountApi('admin/users').then((list:ManagedAccount[])=>{if(!current)return;setUsers(list);if(initialUserId){const user=list.find(item=>item.id===initialUserId);if(user)select(user);else setError('Không tìm thấy tài khoản đã chọn.');}})
      .catch(e=>{if(current)setError(e instanceof Error?e.message:'Không tải được danh sách tài khoản.');})
      .finally(()=>{if(current)setBusy(false);});
    return()=>{current=false;};
  },[initialUserId]);
  useEffect(()=>{setPage(0);},[query,role,status]);
  const filtered=users.filter(user=>user.username.toLowerCase().includes(query.trim().toLowerCase())&&(role==='all'||user.role===role)&&(status==='all'||!!user.active===(status==='active')));
  const pages=Math.max(1,Math.ceil(filtered.length/pageSize)),currentPage=Math.min(page,pages-1);
  const shown=filtered.slice(currentPage*pageSize,(currentPage+1)*pageSize);
  const activeCount=users.filter(user=>user.active).length;
  async function save(){
    const previous=selected;
    const saved:Account=previous?await accountApi(`admin/users/${previous.id}`,jsonRequest('PATCH',{username:name,role:editRole,active,...(password?{password}:{})})):await accountApi('admin/users',jsonRequest('POST',{username:name,role:editRole,password}));
    if(previous?.id===account.id&&(password||editRole!==account.role)){setPassword('');await onRefresh();return;}
    setPassword('');const list=await load();select(list.find(user=>user.id===saved.id)||saved);
    setNotice(previous?'Đã lưu tài khoản. Đổi mật khẩu, vai trò hoặc khóa tài khoản sẽ đăng xuất các phiên cũ.':'Đã tạo tài khoản. User dùng cấu hình API chung của ứng dụng.');
    await onRefresh();
  }
  async function revoke(){
    if(!selected)return;
    const result=await accountApi(`admin/users/${selected.id}/sessions/revoke`,{method:'POST'});
    if(result.current_account_signed_out){await onRefresh();return;}
    const list=await load();setSelected(list.find(user=>user.id===selected.id)||null);
    setNotice(`Đã đăng xuất ${result.revoked_sessions} phiên đang hoạt động. Tài khoản có thể đăng nhập lại.`);
  }
  async function removeUser(target:ManagedAccount){
    await accountApi(`admin/users/${target.id}`,{method:'DELETE'});
    setUsers(list=>list.filter(user=>user.id!==target.id));
    setSelected(null);
    setDeleteTarget(null);
    setPassword('');
    setNotice(`Đã xóa tài khoản ${target.username}.`);
  }
  return <div className="admin-users">
    <div className="admin-users-heading"><div><h3>Quản lý toàn bộ tài khoản</h3><p>Tạo tài khoản, phân quyền và quản lý truy cập trong ứng dụng.</p></div><button className="secondary" disabled={locked} onClick={()=>void action(async()=>{const list=await load();if(selected)setSelected(list.find(user=>user.id===selected.id)||null);})}><RefreshCw size={15}/>Làm mới</button></div>
    <div className="admin-user-stats">{[['Tổng tài khoản',users.length],['Đang hoạt động',activeCount],['Đã khóa',users.length-activeCount],['Quản trị viên',users.filter(user=>user.role==='admin').length]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    {error&&<div className="account-error" role="alert">{error}</div>}{notice&&<div className="account-notice" role="status">{notice}</div>}
    <div className="admin-user-filters"><label><span><Search size={14}/>Tìm tài khoản</span><input type="search" placeholder="Nhập tên đăng nhập…" value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Vai trò tài khoản<select value={role} onChange={e=>setRole(e.target.value)}><option value="all">Tất cả vai trò</option><option value="admin">Admin</option><option value="user">User</option></select></label><label>Trạng thái tài khoản<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">Tất cả trạng thái</option><option value="active">Hoạt động</option><option value="locked">Đã khóa</option></select></label></div>
    <div className="admin-users-layout"><div className="admin-user-directory"><div className="admin-directory-title"><span>{filtered.length} / {users.length} tài khoản</span><button className="secondary" disabled={locked} onClick={()=>select(null)}><Plus size={15}/>Tạo tài khoản</button></div><div className="admin-user-rows">{shown.map(user=><button key={user.id} aria-pressed={selected?.id===user.id} className={selected?.id===user.id?'selected':''} disabled={locked} onClick={()=>select(user)}><div className="admin-user-row-name"><span className="admin-user-avatar">{user.role==='admin'?<ShieldCheck size={19}/>:<Users size={19}/>}</span><div><strong>{user.username}</strong><small>{user.role==='admin'?'Quản trị viên':'Người dùng'}{user.id===account.id?' · Bạn':''}</small></div><span className={`admin-user-state ${user.active?'active':''}`}>{user.active?'Hoạt động':'Đã khóa'}</span></div><div className="admin-user-row-meta"><span>{user.active_sessions??0} phiên đăng nhập</span><span>{user.history_count??0} mục lịch sử</span></div></button>)}{!shown.length&&<p className="admin-directory-empty">Không có tài khoản phù hợp với bộ lọc.</p>}</div><div className="admin-user-pagination"><button className="secondary" disabled={locked||currentPage===0} onClick={()=>setPage(currentPage-1)}>Trước</button><span>Trang {currentPage+1} / {pages}</span><button className="secondary" disabled={locked||currentPage>=pages-1} onClick={()=>setPage(currentPage+1)}>Sau</button></div></div>
    <div className="admin-user-editor">{selected||creating?<><div className="admin-editor-title"><h3>{selected?selected.username:'Tạo tài khoản mới'}</h3>{selected&&<p>Tạo ngày {new Date(selected.created_at*1000).toLocaleDateString('vi-VN')}</p>}</div>{selected&&<div className="managed-user-tabs"><button className={section==='profile'?'selected':''} disabled={locked} onClick={()=>setSection('profile')}>Thông tin tài khoản</button></div>}
    {section==='profile'&&<><form onSubmit={e=>{e.preventDefault();void action(save);}}><label>Tên đăng nhập<input value={name} required minLength={3} maxLength={64} disabled={locked} onChange={e=>setName(e.target.value)}/></label><label>Vai trò<select value={editRole} disabled={locked} onChange={e=>setEditRole(e.target.value as 'user'|'admin')}><option value="user">User · dùng dịch</option><option value="admin">Admin · quản lý tài khoản</option></select></label>{selected&&<label className="account-check"><input type="checkbox" checked={active} disabled={locked||selected.id===account.id} onChange={e=>setActive(e.target.checked)}/>Cho phép đăng nhập</label>}<label>{selected?'Đặt lại mật khẩu · bỏ trống để giữ nguyên':'Mật khẩu · ít nhất 12 ký tự'}<input type="password" autoComplete="new-password" value={password} required={!selected} minLength={12} maxLength={256} disabled={locked} onChange={e=>setPassword(e.target.value)}/></label><small>Không đọc lại mật khẩu hiện tại. Đặt mật khẩu mới sẽ đăng xuất các phiên cũ của tài khoản.</small><button className="primary" disabled={locked}>{selected?'Lưu thay đổi':'Tạo tài khoản'}</button></form>{selected&&<div className="admin-session-control"><h4><KeyRound size={16}/>Phiên đăng nhập</h4><p>{selected.active_sessions??0} phiên đang hoạt động. Đăng xuất các phiên sẽ giữ nguyên tài khoản, lịch sử và kết nối dịch đã lưu.</p><button className="secondary" disabled={locked||!selected.active_sessions} onClick={()=>void action(revoke)}>Đăng xuất mọi thiết bị</button></div>}</>}
    {selected?.role==='user'&&section==='profile'&&<div className="admin-delete-user">
      {deleteTarget?.id===selected.id&&deleteTarget.username===selected.username?
        <div role="group" aria-labelledby="admin-delete-title">
          <h4 id="admin-delete-title">Xóa tài khoản {deleteTarget.username}?</h4>
          <p>Lịch sử dịch, phiên đăng nhập và kết nối đã lưu trong ứng dụng của tài khoản này sẽ bị xóa vĩnh viễn.</p>
          <div className="admin-delete-actions">
            <button type="button" className="secondary" disabled={locked} onClick={()=>setDeleteTarget(null)}>Hủy</button>
            <button type="button" className="admin-delete-button confirm" disabled={locked} onClick={()=>void action(()=>removeUser(deleteTarget))}>Xác nhận xóa</button>
          </div>
        </div>:
        <button type="button" className="admin-delete-button" disabled={locked} onClick={()=>setDeleteTarget(selected)}><Trash2 size={15}/>Xóa tài khoản</button>}
    </div>}
    </>:<div className="admin-user-empty"><Users size={30}/><h3>Chọn tài khoản để quản lý</h3><p>Chọn một tài khoản trong danh sách hoặc tạo tài khoản mới.</p></div>}</div></div>
  </div>;
}
