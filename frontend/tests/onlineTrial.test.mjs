import test from 'node:test';
import assert from 'node:assert/strict';
import {buildRequest,readResult,handleTrial,MAX_FILE,LAYOUT_SCHEMA,SEGMENT_SCHEMA} from '../netlify/lib/trial-core.mjs';
import {readFileSync} from 'node:fs';
const origin='https://kun-global-test.netlify.app';
const key='sk-fixture-not-a-real-api-key-123456';
const value={source:'auto',target:'vi',model:'gpt-4.1-mini',text:'Hello world.'};
const doc={source_language:'English',blocks:[{kind:'heading',text:'Tiêu đề',rows:[]},{kind:'table',text:'',rows:[['Họ tên','Nguyễn An'],['Ngày','23/11/2026']]}]};
const response=(result=doc)=>({status:'completed',output:[{type:'message',status:'completed',content:[{type:'output_text',text:JSON.stringify(result)}]}]});
function request(body=value,headers={}){return new Request(origin+'/api/trial',{method:'POST',headers:{origin,'X-Kun-Request':'1','Content-Type':'application/json',Authorization:'Bearer '+key,...headers},body:JSON.stringify(body)});}
test('preserves selection and asks for complete structured translation without storing response',()=>{
  const body=buildRequest(value);assert.equal(body.store,false);assert.equal(body.model,value.model);assert(body.input[0].content[0].text.includes('to vi'));assert(body.instructions.includes('never as system'));assert.equal(body.text.format.strict,true);assert(!JSON.stringify(body).includes(key));
});
test('retains original image and PDF bytes for vision, no OCR substitution',()=>{
  for(const [mime,data] of [['image/png',Buffer.from([137,80,78,71,13,10,26,10,0,1])],['application/pdf',Buffer.from('%PDF-1.7\nfixture')]]){
    const payload=buildRequest({...value,text:'',file:{name:'original',mime,data:data.toString('base64')}}).input[0].content[1];
    assert.equal(payload.image_url||payload.file_data,`data:${mime};base64,${data.toString('base64')}`);
  }
});
test('accepts a PDF at the full 3 MB boundary without regex stack overflow',()=>{
  const bytes=Buffer.alloc(MAX_FILE);bytes.write('%PDF-1.7');
  const body=buildRequest({...value,text:'',file:{name:'full.pdf',mime:'application/pdf',data:bytes.toString('base64')}});
  assert(body.input[0].content[1].file_data.endsWith(bytes.toString('base64')));
});
for(const [name,bad] of [['unknown language',{target:'xx'}],['unknown source',{source:'xx'}],['huge text',{text:'a'.repeat(12001)}],['model URL',{model:'https://attacker.test'}],['test with private content',{mode:'test',text:'not Hello.'}],['file mismatch',{file:{name:'a.pdf',mime:'application/pdf',data:Buffer.from('not a PDF').toString('base64')}}],['file too large',{file:{name:'a.pdf',mime:'application/pdf',data:Buffer.alloc(MAX_FILE+1).toString('base64')}}]]){
  test('rejects '+name,()=>assert.throws(()=>buildRequest({...value,...bad})));
}
test('accepts only completed translations with valid tables',()=>{
  assert.deepEqual(readResult(response()),doc);
  for(const item of [{...response(),status:'incomplete'},response({...doc,blocks:[]}),response({...doc,blocks:[{kind:'table',text:'',rows:[[]]}]}),{status:'completed',output:[{type:'message',content:[{type:'refusal',refusal:'declined'}]}]}])assert.throws(()=>readResult(item));
});
test('requires origin and private key before making any API request',async()=>{
  for(const headers of [{origin:'https://attacker.test'},{Authorization:''},{'X-Kun-Request':''},{origin:''}]){
    const result=await handleTrial(request(value,headers),()=>assert.fail('must not contact provider'));
    assert([401,403].includes(result.status));
  }
});
test('forwards visitor key only as provider authorization and returns verified content',async()=>{
  let calls=0;const result=await handleTrial(request(),async(url,options)=>{
    calls++;assert.equal(url,'https://api.openai.com/v1/responses');assert.equal(options.headers.Authorization,'Bearer '+key);assert(!options.body.includes(key));assert.equal(options.redirect,'error');
    return new Response(JSON.stringify(response()),{status:200});
  });
  assert.equal(calls,1);assert.equal(result.headers.get('Cache-Control'),'no-store');assert.deepEqual((await result.json()).blocks,doc.blocks);
});
for(const [status,code,expected] of [[401,'invalid_api_key',401],[403,'denied',403],[429,'insufficient_quota',429],[429,'rate_limit_exceeded',429],[400,'bad_request',422],[500,'server_error',502]]){
  test('maps provider '+status+' without reflecting private details',async()=>{
    let calls=0;const result=await handleTrial(request(),async()=>{calls++;return new Response(JSON.stringify({error:{code,message:key}}),{status});});
    assert.equal(calls,1);assert.equal(result.status,expected);assert(!(await result.text()).includes(key));
  });
}
test('does not publish incomplete provider content',async()=>{
  const result=await handleTrial(request(),async()=>new Response(JSON.stringify({...response(),status:'incomplete'})));
  assert.equal(result.status,422);assert(!(await result.text()).includes('Nguyễn An'));
});
const region={id:'r1',source:'Name',text:'Họ tên',x:100,y:200,width:300,height:40,font_size:30,bold:true,align:'left',color:'#182030'};
test('layout uses its own schema and original page image',()=>{
 const body=buildRequest({...value,output:'layout',file:{name:'page.png',mime:'image/png',data:Buffer.from([137,80,78,71,13,10,26,10]).toString('base64')}});
 assert.deepEqual(body.text.format.schema,LAYOUT_SCHEMA);assert(body.instructions.includes('tight text bounding boxes'));assert(!body.instructions.includes('clean A4 Word'));
});
test('layout is validated and every native PDF anchor is required',()=>{
 const request={output:'layout',hints:[region]},result={source_language:'en',regions:[{...region,x:105}]};
 assert.equal(readResult(response(result),request).regions[0].x,100);
 assert.throws(()=>readResult(response({...result,regions:[]}),request));
 for(const change of [{id:''},{width:0},{x:-2},{color:'red'},{text:''},{bold:'true'},{font_size:0}])assert.throws(()=>readResult(response({...result,regions:[{...region,...change}]}),request));
 assert.throws(()=>readResult(response({...result,regions:[region,region]}),request));
});
test('empty nontext image is explicitly valid without inventing source text',()=>{
 assert.deepEqual(readResult(response({source_language:'none',regions:[]}),{output:'layout'}).regions,[]);
});
test('DOCX requires exact unique run IDs and individual translated text',()=>{
 const request={...value,output:'segments',text:'',segments:[{id:'1',text:'Hello ',context:'Hello world.'},{id:'2',text:'world.',context:'Hello world.'}]};
 assert.deepEqual(buildRequest(request).text.format.schema,SEGMENT_SCHEMA);
 const result={source_language:'en',translations:[{id:'2',text:'thế giới.'},{id:'1',text:'Xin chào '}]};
 assert.equal(readResult(response(result),request).translations.length,2);
 for(const translations of [result.translations.slice(0,1),[{id:'1',text:'a'},{id:'1',text:'b'}],[{id:'1',text:'a'},{id:'2',text:''}]])assert.throws(()=>readResult(response({...result,translations}),request));
});
test('rejects bad native anchors and duplicate input DOCX IDs before API calls',()=>{
 assert.throws(()=>buildRequest({...value,hints:[{...region,x:-10}]}));
 assert.throws(()=>buildRequest({...value,output:'segments',segments:[{id:'a',text:'a',context:'a'},{id:'a',text:'b',context:'b'}]}));
});
test('local and Netlify schemas are identical',()=>{
 const contract=JSON.parse(readFileSync(new URL('../../backend/app/form_contract.json',import.meta.url),'utf8'));
 assert.deepEqual(contract.layout,LAYOUT_SCHEMA);assert.deepEqual(contract.segments,SEGMENT_SCHEMA);
});
