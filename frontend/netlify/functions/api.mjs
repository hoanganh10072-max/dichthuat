import {getStore} from '@netlify/blobs';
import {createHostedApi} from '../lib/hosted-api.mjs';
export default async (request,context)=>{
  try{
  const store=getStore({name:'kun-global-private',consistency:'strong'});
  return await createHostedApi({store,env:process.env,ip:context.ip||'unknown'})(request);
  }catch{return new Response(JSON.stringify({detail:'Hệ thống chưa sẵn sàng. Vui lòng liên hệ admin để được trợ giúp.'}),{status:503,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});}
};
