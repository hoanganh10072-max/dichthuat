// Real auth/storage logic with an isolated in-memory Blobs adapter; no paid API.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHostedApi} from '../netlify/lib/hosted-api.mjs';
import {passwordHash} from '../netlify/lib/hosted-store.mjs';
class MemoryStore{
  data=null;etag=0;
  async getWithMetadata(){return this.data===null?null:{data:this.data,etag:String(this.etag)};}
  async set(key,data,options){if(options.onlyIfNew&&this.data!==null||options.onlyIfMatch!==undefined&&options.onlyIfMatch!==String(this.etag))return {modified:false};this.data=data;this.etag++;return {modified:true,etag:String(this.etag)};}
}
const origin='https://fixture.netlify.app',adminPassword='fixture-admin-password-123456',userPassword='fixture-user-password-123456',KEY='sk-fixture-shared-secret-not-real-123456';
async function fixture(){
 const store=new MemoryStore(),env={KUN_MASTER_KEY:Buffer.alloc(32,7).toString('base64'),KUN_BOOTSTRAP_USERNAME:'admin',KUN_BOOTSTRAP_PASSWORD_HASH:await passwordHash(adminPassword)};const calls=[];let upstreamStatus=200;
 const api=createHostedApi({store,env,ip:'fixture-address',fetcher:async(url,options)=>{calls.push({url,headers:options.headers,body:JSON.parse(options.body)});if(upstreamStatus!==200)return new Response(JSON.stringify({error:{message:KEY,code:upstreamStatus===429?'insufficient_quota':'invalid_api_key'}}),{status:upstreamStatus});return new Response(JSON.stringify({status:'completed',usage:{input_tokens:10,output_tokens:8},output:[{type:'message',status:'completed',content:[{type:'output_text',text:JSON.stringify({source_language:'en',blocks:[{kind:'paragraph',text:'Xin chào.',rows:[]}]})}]}]}));}});
 async function request(path,{method='GET',body,cookie='',headers={}}={}){return api(new Request(origin+'/api/'+path,{method,headers:{Origin:origin,'X-Kun-Request':'1',...(body!==undefined?{'Content-Type':'application/json'}:{}),...(cookie?{Cookie:cookie}:{}),...headers},...(body!==undefined?{body:JSON.stringify(body)}:{})}));}
 const login=async(name='admin',pass=adminPassword)=>{const r=await request('auth/login',{method:'POST',body:{username:name,password:pass}});assert.equal(r.status,200,await r.clone().text());return r.headers.get('set-cookie').split(';')[0];};
 const admin=await login();return {store,api,request,login,admin,calls,setStatus:value=>{upstreamStatus=value;}};
}
test('anonymous visitors cannot use translation or admin configuration',async()=>{
 const f=await fixture();assert.equal((await f.request('auth/session')).status,200);assert.equal((await(await f.request('auth/session')).json()).user,null);
 for(const path of ['trial','admin/provider','admin/users'])assert.equal((await f.request(path,{method:path==='trial'?'POST':'GET',body:path==='trial'?{text:'Hi',target:'vi'}:undefined})).status,401);
 assert.equal((await f.request('auth/login',{method:'POST',body:{username:'admin',password:adminPassword},headers:{Origin:'https://foreign.test'}})).status,403);assert.equal(f.calls.length,0);
});
test('API key, model, permissions and connection test are admin-only',async()=>{
 const f=await fixture();const created=await f.request('admin/users',{method:'POST',cookie:f.admin,body:{username:'customer',password:userPassword,role:'user'}});assert.equal(created.status,201);const user=await f.login('customer',userPassword);
 for(const [path,method,body] of [['admin/provider','GET'],['admin/provider','PUT',{model:'gpt-4.1-mini',api_key:KEY}],['admin/provider/test','POST'],['admin/usage','GET'],['admin/users','GET']])assert.equal((await f.request(path,{method,cookie:user,body})).status,403);
 const unavailable=await f.request('trial',{method:'POST',cookie:user,body:{text:'Hello',target:'vi'}});assert.equal(unavailable.status,503);assert.match((await unavailable.json()).detail,/liên hệ admin/);assert.equal(f.calls.length,0);
 const configured=await f.request('admin/provider',{method:'PUT',cookie:f.admin,body:{model:'gpt-4.1-mini',api_key:KEY}});assert.equal(configured.status,200);assert(!(await configured.text()).includes(KEY));assert(!f.store.data.includes(KEY));assert(!f.store.data.includes(adminPassword));assert(!f.store.data.includes('customer'));
 assert.equal((await(await f.request('health',{cookie:user})).json()).model,'unconfigured');
 assert.equal((await f.request('admin/provider/test',{method:'POST',cookie:f.admin})).status,200);assert.equal((await(await f.request('health',{cookie:user})).json()).model,'ready');
 const translated=await f.request('trial',{method:'POST',cookie:user,body:{text:'Hello',source:'en',target:'vi'}});assert.equal(translated.status,200);const output=await translated.json();assert.equal(output.blocks[0].text,'Xin chào.');assert(!('model' in output));assert.equal(f.calls.at(-1).headers.Authorization,'Bearer '+KEY);assert.equal(f.calls.at(-1).body.model,'gpt-4.1-mini');
 for(const body of [{text:'Hi',target:'vi',model:'gpt-other'},{text:'Hi',target:'vi',mode:'test'},{text:'Hi',target:'vi',api_key:'sk-attacker-secret-placeholder'}])assert.equal((await f.request('trial',{method:'POST',cookie:user,body})).status,403);
 assert.equal((await f.request('trial',{method:'POST',cookie:user,body:{text:'Hi',target:'vi'},headers:{Authorization:'Bearer '+KEY}})).status,403);
});
test('user errors never disclose API provider, keys, model or quota',async()=>{
 const f=await fixture();await f.request('admin/users',{method:'POST',cookie:f.admin,body:{username:'customer',password:userPassword}});const user=await f.login('customer',userPassword);
 await f.request('admin/provider',{method:'PUT',cookie:f.admin,body:{model:'gpt-4.1-mini',api_key:KEY}});await f.request('admin/provider/test',{method:'POST',cookie:f.admin});
 for(const status of [401,403,429,500]){f.setStatus(status);const r=await f.request('trial',{method:'POST',cookie:user,body:{text:'Hello',target:'vi'}});const message=await r.text();assert(!/OpenAI|API|gpt-|quota|hạn mức|giới hạn|sk-/i.test(message),message);assert(r.status>=400);}
});
test('locking, password reset, logout, revocation and deletion invalidate sessions',async()=>{
 const f=await fixture();const created=await(await f.request('admin/users',{method:'POST',cookie:f.admin,body:{username:'customer',password:userPassword}})).json();let user=await f.login('customer',userPassword);
 await f.request('admin/users/'+created.id,{method:'PATCH',cookie:f.admin,body:{active:false}});assert.equal((await(await f.request('auth/session',{cookie:user})).json()).user,null);
 await f.request('admin/users/'+created.id,{method:'PATCH',cookie:f.admin,body:{active:true}});user=await f.login('customer',userPassword);
 await f.request('admin/users/'+created.id+'/sessions/revoke',{method:'POST',cookie:f.admin});assert.equal((await(await f.request('auth/session',{cookie:user})).json()).user,null);
 user=await f.login('customer',userPassword);await f.request('admin/users/'+created.id,{method:'PATCH',cookie:f.admin,body:{password:'new-fixture-password-123456'}});assert.equal((await(await f.request('auth/session',{cookie:user})).json()).user,null);
 user=await f.login('customer','new-fixture-password-123456');const logout=await f.request('auth/logout',{method:'POST',cookie:user});assert.equal(logout.status,200);assert.match(logout.headers.get('set-cookie'),/Max-Age=0/);assert.equal((await(await f.request('auth/session',{cookie:user})).json()).user,null);
 assert.equal((await f.request('admin/users/'+created.id,{method:'DELETE',cookie:f.admin})).status,204);
 assert.equal((await f.request('admin/users/'+created.id+'/sessions/revoke',{method:'POST',cookie:f.admin})).status,404);
});
test('last admin is protected and accidental wrong-method revocation cannot delete users',async()=>{
 const f=await fixture();const users=await(await f.request('admin/users',{cookie:f.admin})).json();const own=users[0];
 for(const body of [{active:false},{role:'user'}])assert.equal((await f.request('admin/users/'+own.id,{method:'PATCH',cookie:f.admin,body})).status,422);
 assert.equal((await f.request('admin/users/'+own.id,{method:'DELETE',cookie:f.admin})).status,422);
 const second=await(await f.request('admin/users',{method:'POST',cookie:f.admin,body:{username:'second',password:userPassword}})).json();assert.equal((await f.request('admin/users/'+second.id+'/sessions/revoke',{method:'DELETE',cookie:f.admin})).status,405);assert.equal((await(await f.request('admin/users',{cookie:f.admin})).json()).length,2);
});
test('conditional writes preserve concurrent account changes and persist between deployments',async()=>{
 const f=await fixture();const results=await Promise.all(['one','two','three'].map(name=>f.request('admin/users',{method:'POST',cookie:f.admin,body:{username:name,password:userPassword}})));assert(results.every(r=>r.status===201));const list=await(await f.request('admin/users',{cookie:f.admin})).json();assert.equal(list.length,4);
});
test('brute force login is limited and secrets never appear in error responses',async()=>{
 const f=await fixture();let response;for(let i=0;i<11;i++)response=await f.request('auth/login',{method:'POST',body:{username:'missing',password:'wrong-password'}});assert.equal(response.status,429);assert(!(await response.text()).includes(adminPassword));
});
