import {backgroundColor} from './imageBackground';
import {wrapText,fontFamily} from './imageTypography';

export type FormRegion={id:string;source:string;text:string;x:number;y:number;width:number;height:number;font_size:number;bold:boolean;align:'left'|'center'|'right';color:string};
export type FormLayout={ok?:boolean;source_language:string;regions:FormRegion[]};
export function loadImage(src:string):Promise<HTMLImageElement>{return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Không đọc được ảnh để giữ bố cục gốc.'));image.src=src;});}
export function canvasBlob(canvas:HTMLCanvasElement,type='image/png'):Promise<Blob>{return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Không tạo được file ảnh dịch.')),type));}
export async function originalCanvas(blob:Blob){
  const url=URL.createObjectURL(blob);try{
    const image=await loadImage(url),width=image.naturalWidth,height=image.naturalHeight;
    if(!width||!height||width*height>30_000_000||Math.max(width,height)>16000)throw new Error('Ảnh vượt kích thước dựng an toàn của trình duyệt. Hãy dùng ảnh dưới 30 triệu điểm ảnh.');
    const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;canvas.getContext('2d')!.drawImage(image,0,0);return canvas;
  }finally{URL.revokeObjectURL(url);}
}
export function apiImage(canvas:HTMLCanvasElement){
  const scale=Math.min(1,2000/Math.max(canvas.width,canvas.height));const copy=document.createElement('canvas');copy.width=Math.max(1,Math.round(canvas.width*scale));copy.height=Math.max(1,Math.round(canvas.height*scale));const ctx=copy.getContext('2d')!;ctx.fillStyle='white';ctx.fillRect(0,0,copy.width,copy.height);ctx.drawImage(canvas,0,0,copy.width,copy.height);
  let url=copy.toDataURL('image/png');if(url.length>4*1024*1024)url=copy.toDataURL('image/jpeg',.9);
  if(url.length>4*1024*1024)throw new Error('Trang ảnh quá lớn để gửi dịch. Hãy dùng trang có độ phân giải thấp hơn.');
  return {name:'page.'+(url.startsWith('data:image/png')?'png':'jpg'),mime:url.slice(5,url.indexOf(';')),data:url.slice(url.indexOf(',')+1)};
}
export async function paintTranslation(original:HTMLCanvasElement,layout:FormLayout,target:string){
  await document.fonts.ready;
  const canvas=document.createElement('canvas');canvas.width=original.width;canvas.height=original.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true})!;ctx.drawImage(original,0,0);
  const boxes=layout.regions.map(r=>({x:Math.max(0,r.x/1000*canvas.width),y:Math.max(0,r.y/1000*canvas.height),width:Math.min(r.width/1000*canvas.width,canvas.width-r.x/1000*canvas.width),height:Math.min(r.height/1000*canvas.height,canvas.height-r.y/1000*canvas.height)}));
  // Sample the untouched original, so neighboring translated regions cannot
  // contaminate background estimates. Pixels outside these boxes never change.
  const read=(x:number,y:number)=>ctx.getImageData(Math.max(0,Math.min(canvas.width-1,Math.round(x))),Math.max(0,Math.min(canvas.height-1,Math.round(y))),1,1).data;
  const backgrounds=boxes.map(box=>backgroundColor(read,box));let minFont=Infinity;
  const paint=layout.regions.map(r=>!!r.text.trim()&&r.text.trim()!==r.source.trim());
  // Clear every affected background before drawing any replacement text.
  // If a translated box overlaps an unchanged number/name, redraw that run too
  // so a later fill cannot erase it or another translated line.
  const overlap=(a:typeof boxes[number],b:typeof boxes[number])=>Math.min(a.x+a.width,b.x+b.width)>Math.max(a.x,b.x)&&Math.min(a.y+a.height,b.y+b.height)>Math.max(a.y,b.y);
  for(let pass=0;pass<paint.length;pass++){let changed=false;for(let i=0;i<paint.length;i++)if(!paint[i]&&paint.some((p,j)=>p&&overlap(boxes[i],boxes[j]))){paint[i]=true;changed=true;}if(!changed)break;}
  for(let i=0;i<paint.length;i++)if(paint[i]){const b=boxes[i];ctx.save();ctx.beginPath();ctx.rect(b.x,b.y,b.width,b.height);ctx.clip();ctx.fillStyle=`rgb(${backgrounds[i].join(',')})`;ctx.fillRect(b.x,b.y,b.width,b.height);ctx.restore();}
  for(let i=0;i<layout.regions.length;i++){
    const r=layout.regions[i],b=boxes[i];if(!paint[i]||!r.text.trim())continue;
    const padding=Math.min(.7,b.height*.02),width=Math.max(.2,b.width-padding*2),height=Math.max(.2,b.height-padding*2);
    const setFont=(size:number)=>{ctx.font=`${r.bold?700:400} ${size}px ${fontFamily}`;};
    const linesAt=(size:number)=>{setFont(size);return r.text.split(/\r?\n/).flatMap(line=>line?wrapText(ctx,line,width):['']);};
    let low=.15,high=Math.max(.3,Math.min(r.font_size/1000*canvas.height,b.height*.95));
    for(let n=0;n<18;n++){const size=(low+high)/2,lines=linesAt(size);if(lines.length*size*1.15<=height&&lines.every(line=>ctx.measureText(line).width<=width+.01))low=size;else high=size;}
    const size=low,lines=linesAt(size);minFont=Math.min(minFont,size);
    ctx.save();ctx.beginPath();ctx.rect(b.x,b.y,b.width,b.height);ctx.clip();
    ctx.fillStyle=/^#[0-9a-f]{6}$/i.test(r.color)?r.color:'#202020';setFont(size);ctx.textBaseline='alphabetic';ctx.direction=target==='ar'?'rtl':'ltr';ctx.textAlign=r.align==='center'?'center':target==='ar'?'right':r.align;
    const x=r.align==='center'?b.x+b.width/2:ctx.textAlign==='right'?b.x+b.width-padding:b.x+padding;
    const metrics=ctx.measureText(lines[0]||'Ag');const ascent=metrics.actualBoundingBoxAscent||size*.85;
    lines.forEach((line,index)=>ctx.fillText(line,x,b.y+padding+ascent+index*size*1.15));ctx.restore();
  }
  return {canvas,blob:await canvasBlob(canvas),minFont:Number.isFinite(minFont)?minFont:null};
}
