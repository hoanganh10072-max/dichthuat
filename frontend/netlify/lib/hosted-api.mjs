import {randomBytes} from 'node:crypto';
import {handleTrial} from './trial-core.mjs';
import {encryptedRepository,HostedError,CONTACT_ADMIN,sha,publicUser,username,password,passwordHash,verifyPassword,sessionUser,keepAdmin} from './hosted-store.mjs';

const COOKIE='__Host-kun_session',SESSION_MS=7*86400000;
function json(value,status=200,headers={}){return new Response(status===204?null:JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...headers}});}
const cookie=token=>`${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${token?SESSION_MS/1000:0}`;
function getToken(req){const match=(req.headers.get('cookie')||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(COOKIE+'='));return match?.slice(COOKIE.length+1)||'';}
function requireAdmin(user){if(user.role!=='admin')throw new HostedError('Chỉ quản trị viên có quyền thực hiện.',403);}
function targetUser(state,id){const user=state.users.find(u=>u.id===id);if(!user)throw new HostedError('Không tìm thấy tài khoản.',404);return user;}
function availableUsername(state,name,id){if(state.users.some(u=>u.id!==id&&u.username.toLowerCase()===name.toLowerCase()))throw new HostedError('Tên đăng nhập đã được sử dụng.',422);}
function cleanProvider(provider){return {configured:!!provider.key,key_source:provider.key?'saved':'none',model:provider.model};}
async function bodyOf(req,max=4.3*1024*1024){
  if(!req.headers.get('content-type')?.startsWith('application/json'))throw new HostedError('Định dạng yêu cầu không hợp lệ.',415);
  const raw=await req.text();if(raw.length>max)throw new HostedError('Yêu cầu quá dung lượng hỗ trợ.',413);
  let value;try{value=JSON.parse(raw);}catch{throw new HostedError('Dữ liệu yêu cầu không hợp lệ.',400);}
  if(!value||typeof value!=='object'||Array.isArray(value))throw new HostedError('Dữ liệu yêu cầu không hợp lệ.',400);return value;
}
function newSession(state,user,token){state.sessions=state.sessions.filter(s=>s.expires>Date.now());state.sessions.push({hash:sha(token),user_id:user.id,auth_version:user.auth_version,expires:Date.now()+SESSION_MS});if(state.sessions.length>5000)state.sessions=state.sessions.slice(-5000);}

export function createHostedApi({store,env,fetcher=fetch,ip='unknown'}){
  return async function hostedApi(req){
    try{
      const url=new URL(req.url);let path=url.pathname.replace(/^\/\.netlify\/functions\/api\/?/,'').replace(/^\/api\//,'');path=path.replace(/^\/+|\/+$/g,'');
      if(req.method!=='GET'&&req.method!=='HEAD'){
        if(req.headers.get('origin')!==url.origin||req.headers.get('x-kun-request')!=='1')throw new HostedError('Yêu cầu không hợp lệ. Hãy tải lại trang.',403);
      }
      const repository=encryptedRepository(store,env),token=getToken(req);let {state}=await repository.read();let user=sessionUser(state,token);
      if(path==='auth/session'&&req.method==='GET')return json({user:publicUser(user),setup_required:false});
      if(path==='auth/login'&&req.method==='POST'){
        const body=await bodyOf(req,4096);const name=typeof body.username==='string'?body.username:'';
        if(name.length>64||typeof body.password!=='string'||body.password.length>256)throw new HostedError('Tên đăng nhập hoặc mật khẩu không đúng.',401);
        const limitKeys=[sha('ip:'+ip),sha('user:'+ip+':'+name.toLowerCase())],cutoff=Date.now()-15*60000;
        if(limitKeys.some(key=>(state.failures[key]||[]).filter(t=>t>cutoff).length>=10))throw new HostedError('Đăng nhập quá nhiều lần. Vui lòng thử lại sau 15 phút.',429);
        const found=state.users.find(u=>u.username.toLowerCase()===name.toLowerCase());
        const valid=await verifyPassword(body.password,found?.password_hash||env.KUN_BOOTSTRAP_PASSWORD_HASH);
        if(!found||!found.active||!valid){
          await repository.mutate(db=>{for(const key of limitKeys)db.failures[key]=[...(db.failures[key]||[]).filter(t=>t>cutoff),Date.now()];for(const key of Object.keys(db.failures))if(!db.failures[key].some(t=>t>cutoff))delete db.failures[key];});
          throw new HostedError('Tên đăng nhập hoặc mật khẩu không đúng.',401);
        }
        const session=randomBytes(32).toString('base64url');
        const logged=await repository.mutate(db=>{const current=targetUser(db,found.id);if(!current.active||current.password_hash!==found.password_hash)throw new HostedError('Tên đăng nhập hoặc mật khẩu không đúng.',401);newSession(db,current,session);for(const key of limitKeys)delete db.failures[key];return publicUser(current);});
        return json({user:logged},200,{'Set-Cookie':cookie(session)});
      }
      if(path==='auth/logout'&&req.method==='POST'){
        if(user)await repository.mutate(db=>{db.sessions=db.sessions.filter(s=>s.hash!==sha(token));});return json({ok:true},200,{'Set-Cookie':cookie('')});
      }
      if(path==='health'&&req.method==='GET'){
        if(!user)return json({model:'unconfigured',message:'Vui lòng đăng nhập để sử dụng.'});
        return json({model:state.provider.key&&state.provider.verified?'ready':'unconfigured',message:state.provider.key&&state.provider.verified?'Sẵn sàng dịch.':CONTACT_ADMIN});
      }
      if(!user)throw new HostedError('Vui lòng đăng nhập để tiếp tục.',401);
      if(path.startsWith('admin/'))requireAdmin(user);
      const mutate=action=>repository.mutate(db=>{const current=sessionUser(db,token);if(!current)throw new HostedError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',401);if(path.startsWith('admin/'))requireAdmin(current);return action(db);});
      if(path==='auth/profile'&&req.method==='PATCH'){
        const body=await bodyOf(req,4096),name=username(body.username);
        const updated=await mutate(db=>{availableUsername(db,name,user.id);const current=targetUser(db,user.id);current.username=name;return publicUser(current);});return json({user:updated});
      }
      if(path==='auth/password'&&req.method==='POST'){
        const body=await bodyOf(req,4096);if(!await verifyPassword(body.current_password,user.password_hash))throw new HostedError('Mật khẩu hiện tại không đúng.',422);
        const hash=await passwordHash(password(body.new_password)),session=randomBytes(32).toString('base64url');
        await mutate(db=>{const current=targetUser(db,user.id);if(current.password_hash!==user.password_hash)throw new HostedError('Thông tin tài khoản vừa thay đổi. Vui lòng đăng nhập lại.',401);current.password_hash=hash;current.auth_version++;db.sessions=db.sessions.filter(s=>s.user_id!==user.id);newSession(db,current,session);});return json({ok:true},200,{'Set-Cookie':cookie(session)});
      }
      if(path==='admin/users'&&req.method==='GET')return json(state.users.map(u=>({...publicUser(u),active_sessions:state.sessions.filter(s=>s.user_id===u.id&&s.expires>Date.now()).length,history_count:state.history.filter(h=>h.user_id===u.id).length})));
      if(path==='admin/users'&&req.method==='POST'){
        const body=await bodyOf(req,4096),name=username(body.username),role=body.role||'user';if(!['admin','user'].includes(role))throw new HostedError('Quyền tài khoản không hợp lệ.',422);
        const hash=await passwordHash(password(body.password));const entry={id:randomBytes(16).toString('hex'),username:name,role,active:true,password_hash:hash,auth_version:0,created_at:Date.now()};
        return json(await mutate(db=>{if(db.users.length>=1000)throw new HostedError('Đã đạt giới hạn tài khoản của hệ thống.',422);availableUsername(db,name);db.users.push(entry);return publicUser(entry);}),201);
      }
      const managed=path.match(/^admin\/users\/([a-f0-9]+)(\/sessions\/revoke)?$/);
      if(managed){
        const id=managed[1];targetUser(state,id);
        if(managed[2]&&req.method!=='POST')throw new HostedError('Phương thức không được hỗ trợ.',405);
        if(managed[2]&&req.method==='POST'){
          const count=await mutate(db=>{targetUser(db,id);const count=db.sessions.filter(s=>s.user_id===id).length;db.sessions=db.sessions.filter(s=>s.user_id!==id);return count;});return json({revoked_sessions:count,current_account_signed_out:id===user.id},200,id===user.id?{'Set-Cookie':cookie('')}:{});
        }
        if(req.method==='DELETE'){
          if(id===user.id)throw new HostedError('Không thể xóa tài khoản đang đăng nhập.',422);
          await mutate(db=>{targetUser(db,id);db.users=db.users.filter(u=>u.id!==id);keepAdmin(db);db.sessions=db.sessions.filter(s=>s.user_id!==id);db.history=db.history.filter(h=>h.user_id!==id);db.usage=db.usage.filter(u=>u.user_id!==id);});return json(null,204);
        }
        if(req.method==='PATCH'){
          const body=await bodyOf(req,4096);const name=body.username===undefined?undefined:username(body.username),hash=body.password===undefined?undefined:await passwordHash(password(body.password));
          if(body.role!==undefined&&!['admin','user'].includes(body.role)||body.active!==undefined&&typeof body.active!=='boolean')throw new HostedError('Thông tin tài khoản không hợp lệ.',422);
          const updated=await mutate(db=>{const current=targetUser(db,id);if(name){availableUsername(db,name,id);current.username=name;}const changed=hash||body.role!==undefined&&current.role!==body.role||body.active!==undefined&&current.active!==body.active;
            if(body.role!==undefined)current.role=body.role;if(body.active!==undefined)current.active=body.active;if(hash)current.password_hash=hash;keepAdmin(db);if(changed){current.auth_version++;db.sessions=db.sessions.filter(s=>s.user_id!==id);}return publicUser(current);});return json(updated);
        }
      }
      if(path==='admin/provider'&&req.method==='GET')return json(cleanProvider(state.provider));
      if(path==='admin/provider'&&req.method==='PUT'){
        const body=await bodyOf(req,4096);if(typeof body.model!=='string'||! /^[a-zA-Z0-9._:-]{1,120}$/.test(body.model))throw new HostedError('Tên mô hình không hợp lệ.',422);
        if(typeof body.api_key==='string')body.api_key=body.api_key.trim();
        if(body.api_key!==undefined&&(typeof body.api_key!=='string'||!/^sk-[\x21-\x7e]{17,509}$/.test(body.api_key))||body.clear_key&&body.api_key)throw new HostedError('Khóa API không hợp lệ.',422);
        return json(await mutate(db=>{if(db.provider.model!==body.model||body.clear_key||body.api_key)db.provider.verified=false;db.provider.model=body.model;if(body.clear_key)db.provider.key='';else if(body.api_key)db.provider.key=body.api_key;return cleanProvider(db.provider);}));
      }
      if(path==='admin/usage'&&req.method==='GET'){
        const groups=new Map();for(const item of state.usage.filter(i=>i.created_at>Date.now()-30*86400000)){const group=item.user_id+'|'+item.model;const value=groups.get(group)||{username:state.users.find(u=>u.id===item.user_id)?.username||'',model:item.model,requests:0,input_tokens:0,output_tokens:0};value.requests++;value.input_tokens+=item.input_tokens;value.output_tokens+=item.output_tokens;groups.set(group,value);}return json([...groups.values()]);
      }
      if(path==='history'){
        if(req.method==='GET')return json(state.history.filter(h=>h.user_id===user.id).map(({user_id,...item})=>item));
        if(req.method==='DELETE'){await mutate(db=>{db.history=db.history.filter(h=>h.user_id!==user.id);});return json({ok:true});}
        if(req.method==='POST'){
          const body=await bodyOf(req,100000);if(typeof body.input!=='string'||body.input.length>12000||typeof body.output!=='string'||body.output.length>60000)throw new HostedError('Lịch sử quá dài.',422);
          const entry={id:randomBytes(12).toString('hex'),user_id:user.id,input:body.input,output:body.output,source:body.source,target:body.target,date:new Date().toISOString()};await mutate(db=>{db.history.push(entry);const own=db.history.filter(h=>h.user_id===user.id).slice(-30);db.history=db.history.filter(h=>h.user_id!==user.id).concat(own).slice(-150);});const {user_id,...clean}=entry;return json(clean);
        }
      }
      if(path==='trial'&&req.method==='POST'||path==='admin/provider/test'&&req.method==='POST'){
        const test=path==='admin/provider/test';if(test)requireAdmin(user);
        if(!state.provider.key)throw new HostedError(user.role==='admin'?'Cấu hình khóa trong Quản trị → OpenAI API trước khi dịch.':CONTACT_ADMIN,503);
        if(!test&&!state.provider.verified)throw new HostedError(user.role==='admin'?'Bấm Kiểm tra kết nối trong Quản trị → OpenAI API trước khi dịch.':CONTACT_ADMIN,503);
        const input=test?{mode:'test',source:'en',target:'vi',text:'Hello.'}:await bodyOf(req);
        if(!test&&(input.mode==='test'||input.model!==undefined||input.api_key!==undefined||req.headers.has('authorization')))throw new HostedError('Yêu cầu không hợp lệ.',403);
        const proxy=new Request(url.origin+'/api/trial',{method:'POST',headers:{Origin:url.origin,'X-Kun-Request':'1','Content-Type':'application/json',Authorization:'Bearer '+state.provider.key},body:JSON.stringify({...input,model:state.provider.model})});
        const response=await handleTrial(proxy,fetcher,{onUsage:async usage=>{
          const counts=[usage?.input_tokens,usage?.output_tokens];if(!counts.every(n=>Number.isSafeInteger(n)&&n>=0))return;
          await repository.mutate(db=>{if(db.users.some(u=>u.id===user.id))db.usage.push({user_id:user.id,model:state.provider.model,input_tokens:counts[0],output_tokens:counts[1],created_at:Date.now()});});
        }});
        const data=await response.json();if(!response.ok)return json({detail:user.role==='admin'?data.detail:[401,403,429].includes(response.status)?CONTACT_ADMIN:response.status===504?'Chưa nhận đủ bản dịch trong thời gian chờ. Hãy thử ít trang hơn.':'Dịch vụ dịch đang tạm gián đoạn. Vui lòng thử lại hoặc liên hệ admin để được trợ giúp.'},response.status===401?503:response.status);
        const latest=(await repository.read()).state;if(!sessionUser(latest,token))throw new HostedError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',401);
        if(test){await mutate(db=>{if(db.provider.key!==state.provider.key||db.provider.model!==state.provider.model)throw new HostedError('Cấu hình vừa thay đổi. Vui lòng kiểm tra lại.',409);db.provider.verified=true;});return json({ok:true,model:state.provider.model,message:'Đã nhận phản hồi dịch hợp lệ từ OpenAI API.'});}
        if(user.role!=='admin')delete data.model;return json(data);
      }
      throw new HostedError('Không tìm thấy chức năng này.',404);
    }catch(error){return json({detail:error instanceof HostedError?error.message:'Dịch vụ đang tạm gián đoạn. Vui lòng thử lại hoặc liên hệ admin để được trợ giúp.'},error instanceof HostedError?error.status:503);}
  };
}
