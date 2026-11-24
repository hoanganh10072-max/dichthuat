import {randomBytes,createHash,createCipheriv,createDecipheriv,scrypt as nodeScrypt,timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
const scrypt=promisify(nodeScrypt);
export class HostedError extends Error {constructor(message,status=400){super(message);this.status=status;}}
export const CONTACT_ADMIN='Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.';
export const sha=value=>createHash('sha256').update(value).digest('hex');
export function publicUser(user){return user?{id:user.id,username:user.username,role:user.role,active:user.active,created_at:Math.floor(user.created_at/1000)}:null;}
export function username(value){if(typeof value!=='string'||!/^[a-zA-Z0-9_.@-]{3,64}$/.test(value))throw new HostedError('Tên đăng nhập gồm 3–64 ký tự: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.',422);return value;}
export function password(value){if(typeof value!=='string'||value.length<12||value.length>256)throw new HostedError('Mật khẩu cần từ 12 đến 256 ký tự.',422);return value;}
export async function passwordHash(value){const salt=randomBytes(16);const key=await scrypt(value,salt,64,{N:16384,r:8,p:1});return `scrypt$${salt.toString('base64')}$${key.toString('base64')}`;}
export async function verifyPassword(value,stored){
  if(typeof value!=='string'||value.length>256||typeof stored!=='string')return false;
  const [type,salt,hash]=stored.split('$');if(type!=='scrypt'||!salt||!hash)return false;
  const expected=Buffer.from(hash,'base64');if(expected.length!==64)return false;
  const actual=await scrypt(value,Buffer.from(salt,'base64'),64,{N:16384,r:8,p:1});return timingSafeEqual(actual,expected);
}
export function encryptedRepository(store,env){
  const master=Buffer.from(env.KUN_MASTER_KEY||'','base64');
  if(master.length!==32)throw new HostedError('Hệ thống chưa sẵn sàng. Vui lòng liên hệ admin.',503);
  const seal=value=>{const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',master,iv);const data=Buffer.concat([cipher.update(JSON.stringify(value),'utf8'),cipher.final()]);return 'v1.'+Buffer.concat([iv,cipher.getAuthTag(),data]).toString('base64');};
  const open=value=>{try{if(!value.startsWith('v1.'))throw new Error();const bytes=Buffer.from(value.slice(3),'base64'),decipher=createDecipheriv('aes-256-gcm',master,bytes.subarray(0,12));decipher.setAuthTag(bytes.subarray(12,28));return JSON.parse(Buffer.concat([decipher.update(bytes.subarray(28)),decipher.final()]).toString('utf8'));}catch{throw new HostedError('Không đọc được dữ liệu hệ thống. Vui lòng liên hệ admin.',503);}};
  const initial=()=>{
    if(!env.KUN_BOOTSTRAP_PASSWORD_HASH?.startsWith('scrypt$'))throw new HostedError('Hệ thống chưa sẵn sàng. Vui lòng liên hệ admin.',503);
    return {version:1,users:[{id:randomBytes(16).toString('hex'),username:username(env.KUN_BOOTSTRAP_USERNAME||'admin'),role:'admin',active:true,password_hash:env.KUN_BOOTSTRAP_PASSWORD_HASH,created_at:Date.now(),auth_version:0}],sessions:[],provider:{model:'gpt-4.1-mini',key:'',verified:false},failures:{},usage:[],history:[]};
  };
  async function read(){
    const item=await store.getWithMetadata('control',{type:'text',consistency:'strong'});
    if(item)return {state:open(item.data),etag:item.etag};
    const state=initial(),write=await store.set('control',seal(state),{onlyIfNew:true});
    if(write.modified)return {state,etag:write.etag};
    const existing=await store.getWithMetadata('control',{type:'text',consistency:'strong'});if(!existing)throw new HostedError('Hệ thống đang khởi tạo. Vui lòng thử lại.',503);return {state:open(existing.data),etag:existing.etag};
  }
  async function mutate(action){
    for(let attempt=0;attempt<7;attempt++){
      const {state,etag}=await read();const result=await action(state);
      const now=Date.now();state.sessions=state.sessions.filter(s=>s.expires>now);state.usage=state.usage.filter(u=>u.created_at>now-31*86400000);
      const write=await store.set('control',seal(state),{onlyIfMatch:etag});if(write.modified)return result;
    }
    throw new HostedError('Có thay đổi đồng thời. Vui lòng thử lại thao tác.',409);
  }
  return {read,mutate};
}
export function sessionUser(state,token){
  if(typeof token!=='string'||token.length>128)return null;const hash=sha(token),session=state.sessions.find(s=>s.hash===hash&&s.expires>Date.now());
  if(!session)return null;return state.users.find(u=>u.id===session.user_id&&u.active&&u.auth_version===session.auth_version)||null;
}
export function keepAdmin(state){if(!state.users.some(u=>u.active&&u.role==='admin'))throw new HostedError('Phải giữ ít nhất một tài khoản quản trị đang hoạt động.',422);}
