import type {FormLayout,FormRegion} from './form-graphics';
import {apiImage,canvasBlob,originalCanvas,paintTranslation} from './form-graphics';

export type FormCall=(body:Record<string,unknown>,signal?:AbortSignal)=>Promise<any>;
export type FormPage={url:string;width:number;height:number};
export type FormOutput={blob:Blob;extension:'png'|'pdf'|'docx'|'txt';pages:FormPage[];text:string;pageCount:number;regionCount:number};
type Progress=(message:string)=>void;
function check(signal?:AbortSignal){if(signal?.aborted)throw new Error('Đã dừng xử lý tài liệu. Chưa xuất bản dịch dở dang.');}
function pagePreview(canvas:HTMLCanvasElement):FormPage{return {url:canvas.toDataURL('image/png'),width:canvas.width,height:canvas.height};}
async function translatePage(canvas:HTMLCanvasElement,call:FormCall,target:string,signal?:AbortSignal,hints:FormRegion[]=[]){
  check(signal);const result:FormLayout=await call({output:'layout',file:apiImage(canvas),hints},signal);
  if(!Array.isArray(result.regions))throw new Error('Máy chủ chưa trả vị trí chữ dịch. Chưa tạo ảnh thay thế.');
  check(signal);const painted=await paintTranslation(canvas,result,target);return {painted,result};
}
export async function translateImageFile(file:Blob,call:FormCall,target:string,progress:Progress,signal?:AbortSignal):Promise<FormOutput>{
  progress('Đang đọc toàn bộ chữ và vị trí trong ảnh…');const original=await originalCanvas(file);const {painted,result}=await translatePage(original,call,target,signal);
  return {blob:painted.blob,extension:'png',pages:[pagePreview(painted.canvas)],text:result.regions.map(r=>r.text).join('\n'),pageCount:1,regionCount:result.regions.length};
}
export async function translatePdfFile(file:Blob,call:FormCall,target:string,progress:Progress,signal?:AbortSignal):Promise<FormOutput>{
  const pdfjs=await import('pdfjs-dist');const {default:worker}=await import('pdfjs-dist/build/pdf.worker.min.mjs?url');pdfjs.GlobalWorkerOptions.workerSrc=worker;
  const loading=pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer()),cMapUrl:'/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/pdfjs/standard_fonts/',wasmUrl:'/pdfjs/wasm/'});
  const original=await loading.promise;const {PDFDocument}=await import('pdf-lib');const translated=await PDFDocument.create();const pages:FormPage[]=[],texts:string[]=[];let regionCount=0;
  try{
    if(original.numPages>30)throw new Error('Bản giữ form hỗ trợ tối đa 30 trang một lượt. Chưa xử lý hay bỏ qua trang nào.');
    for(let number=1;number<=original.numPages;number++){
      check(signal);progress(`Đang dịch và giữ bố cục trang ${number}/${original.numPages}…`);
      const page=await original.getPage(number),size=page.getViewport({scale:1}),viewport=page.getViewport({scale:Math.min(2.5,1800/Math.max(size.width,size.height))});
      const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);await page.render({canvas,canvasContext:canvas.getContext('2d')!,viewport}).promise;
      const text=await page.getTextContent(),hints:FormRegion[]=[];
      for(const item of text.items){
        if(!('str'in item)||!item.str.trim())continue;
        const t=pdfjs.Util.transform(viewport.transform,item.transform);if(Math.abs(Math.atan2(t[1],t[0]))>.05)continue;
        const font=Math.hypot(t[2],t[3]),x=Math.max(0,t[4]),y=Math.max(0,t[5]-font*.88),width=Math.min(item.width*viewport.scale,canvas.width-x),height=Math.min(font*1.12,canvas.height-y);
        if(width<.5||height<.5||x>=canvas.width||y>=canvas.height)continue;
        hints.push({id:`p${number}-${hints.length}`,source:item.str,text:item.str,x:x/canvas.width*1000,y:y/canvas.height*1000,width:width/canvas.width*1000,height:height/canvas.height*1000,font_size:font/canvas.height*1000,bold:false,align:'left',color:'#202020'});
      }
      if(hints.length>400)throw new Error(`Trang ${number} có quá nhiều vùng chữ cho một lượt giữ form. Chưa có file hoàn chỉnh để tải.`);
      const {painted,result}=await translatePage(canvas,call,target,signal,hints);const image=await translated.embedPng(new Uint8Array(await painted.blob.arrayBuffer()));
      translated.addPage([size.width,size.height]).drawImage(image,{x:0,y:0,width:size.width,height:size.height});
      pages.push(pagePreview(painted.canvas));texts.push(result.regions.map(r=>r.text).join('\n'));regionCount+=result.regions.length;page.cleanup();
    }
    check(signal);return {blob:new Blob([new Uint8Array(await translated.save())],{type:'application/pdf'}),extension:'pdf',pages,text:texts.join('\n\n'),pageCount:pages.length,regionCount};
  }finally{await loading.destroy();}
}

function verifyZip(bytes:Uint8Array){
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let end=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--)if(view.getUint32(i,true)===0x06054b50){end=i;break;}
  if(end<0)throw new Error('File DOCX không đúng cấu trúc ZIP.');
  const count=view.getUint16(end+10,true);let offset=view.getUint32(end+16,true),total=0;
  if(count>2000)throw new Error('DOCX có quá nhiều thành phần để xử lý an toàn.');
  for(let i=0;i<count;i++){
    if(offset+46>bytes.length||view.getUint32(offset,true)!==0x02014b50)throw new Error('DOCX bị lỗi cấu trúc.');
    total+=view.getUint32(offset+24,true);if(total>80*1024*1024)throw new Error('DOCX vượt dung lượng giải nén an toàn.');
    offset+=46+view.getUint16(offset+28,true)+view.getUint16(offset+30,true)+view.getUint16(offset+32,true);
  }
}
const WORD='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
export async function translateDocxFile(file:Blob,call:FormCall,target:string,progress:Progress,signal?:AbortSignal):Promise<FormOutput>{
  const bytes=new Uint8Array(await file.arrayBuffer());verifyZip(bytes);const {default:JSZip}=await import('jszip');const zip=await JSZip.loadAsync(bytes);if(!zip.file('word/document.xml'))throw new Error('File không phải tài liệu Word DOCX hợp lệ.');
  for(const name of Object.keys(zip.files).filter(n=>/^word\/.*\.rels$/.test(n))){
    const relationships=new DOMParser().parseFromString(await zip.file(name)!.async('string'),'application/xml');
    if(Array.from(relationships.getElementsByTagName('Relationship')).some(r=>r.getAttribute('TargetMode')==='External'&&r.getAttribute('Type')?.endsWith('/image')))throw new Error('Word có ảnh liên kết ngoài file. Hãy nhúng ảnh vào Word hoặc chuyển sang PDF để dịch đầy đủ.');
  }
  const parts:{name:string;document:XMLDocument}[]=[],segments:{id:string;text:string;context:string;node:Element}[]=[];
  for(const name of Object.keys(zip.files).filter(n=>/^word\/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$/.test(n))){
    const raw=await zip.file(name)!.async('string'),document=new DOMParser().parseFromString(raw,'application/xml');
    if(document.getElementsByTagName('parsererror').length)throw new Error('Không đọc được cấu trúc Word.');
    if(document.getElementsByTagNameNS(WORD,'altChunk').length)throw new Error('DOCX chứa tài liệu nhúng đặc biệt; hãy chuyển sang PDF để dịch đầy đủ.');
    const nodes=Array.from(document.getElementsByTagNameNS(WORD,'t')).concat(Array.from(document.getElementsByTagNameNS('http://schemas.openxmlformats.org/drawingml/2006/main','t')));
    for(const node of nodes){
      const text=node.textContent||'';if(!text.trim())continue;
      let paragraph:Element|null=node.parentElement;while(paragraph&&!(paragraph.namespaceURI===WORD&&paragraph.localName==='p'))paragraph=paragraph.parentElement;
      const context=paragraph?Array.from(paragraph.getElementsByTagNameNS(WORD,'t')).map(t=>t.textContent||'').join(''):text;
      segments.push({id:`r${segments.length}`,text,context:context.slice(0,1800),node});
    }
    parts.push({name,document});
  }
  const allText:string[]=[];let position=0;
  while(position<segments.length){
    check(signal);const batch:typeof segments=[];let length=0;
    while(position<segments.length&&batch.length<70){const item=segments[position],cost=JSON.stringify({id:item.id,text:item.text,context:item.context}).length;if(batch.length&&length+cost>18000)break;if(cost>22000)throw new Error('Một đoạn Word quá dài để dịch nguyên định dạng. Hãy chia đoạn đó hoặc dùng PDF.');batch.push(item);length+=cost;position++;}
    progress(`Đang dịch chữ trong Word ${position}/${segments.length}, giữ nguyên bảng và định dạng…`);
    const result=await call({output:'segments',segments:batch.map(({id,text,context})=>({id,text,context}))},signal);
    const translations=new Map<string,string>((result.translations||[]).map((t:{id:string;text:string})=>[t.id,t.text]));
    if(translations.size!==batch.length)throw new Error('Chưa dịch đủ các đoạn Word. Chưa xuất file hoàn chỉnh.');
    for(const item of batch){const translation=translations.get(item.id);if(typeof translation!=='string'||!translation.trim())throw new Error('Word còn thiếu đoạn dịch.');item.node.textContent=(item.text.match(/^\s*/)?.[0]||'')+translation.trim()+(item.text.match(/\s*$/)?.[0]||'');item.node.setAttributeNS('http://www.w3.org/XML/1998/namespace','xml:space','preserve');allText.push(translation);}
  }
  for(const part of parts)zip.file(part.name,new XMLSerializer().serializeToString(part.document));
  const pages:FormPage[]=[];
  const media=Object.keys(zip.files).filter(n=>/^word\/media\/[^/]+$/.test(n)&&!zip.files[n].dir);
  for(let i=0;i<media.length;i++){
    check(signal);progress(`Đang dịch chữ trong ảnh nhúng Word ${i+1}/${media.length}…`);
    const name=media[i],ext=name.split('.').pop()?.toLowerCase();
    if(!['png','jpg','jpeg','webp','gif','bmp'].includes(ext||''))throw new Error(`Ảnh nhúng ${ext||''} chưa được trình duyệt hỗ trợ. Hãy dùng PDF để dịch cả ảnh, không bỏ sót.`);
    const data=await zip.file(name)!.async('uint8array'),mime=ext==='jpg'?'image/jpeg':`image/${ext}`;
    const original=await originalCanvas(new Blob([new Uint8Array(data)],{type:mime}));const {painted,result}=await translatePage(original,call,target,signal);
    if(result.regions.length){
      const encoded=ext==='jpg'||ext==='jpeg'?await canvasBlob(painted.canvas,'image/jpeg'):ext==='png'?painted.blob:null;
      if(!encoded)throw new Error('Ảnh nhúng có định dạng chưa thể ghi lại an toàn. Hãy chuyển tài liệu sang PDF.');
      zip.file(name,new Uint8Array(await encoded.arrayBuffer()));allText.push(result.regions.map(r=>r.text).join('\n'));
    }
    pages.push(pagePreview(painted.canvas));
  }
  check(signal);return {blob:await zip.generateAsync({type:'blob',compression:'DEFLATE',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),extension:'docx',pages,text:allText.join('\n'),pageCount:parts.length,regionCount:segments.length};
}
