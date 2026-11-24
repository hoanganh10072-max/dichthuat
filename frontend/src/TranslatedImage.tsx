import {useEffect,useRef,useState} from 'react';
import {Download,FileText,Image as ImageIcon,Languages} from 'lucide-react';
import {loadImage,paintTranslation,type FormRegion} from './form-graphics';
export type Region={text:string;x:number;y:number;width:number;height:number;translation?:string};
export type Layout={width:number;height:number;regions:Region[]};
export default function TranslatedImage({src,layout,text,target,onDownloadWord,wordBusy=false}:{src:string;layout:Layout;text:string;target:string;onDownloadWord?:()=>void;wordBusy?:boolean}){
  const [view,setView]=useState<'image'|'text'>('image'),[ready,setReady]=useState(false),[error,setError]=useState(''),[zoom,setZoom]=useState(false);
  const canvas=useRef<HTMLCanvasElement>(null),blob=useRef<Blob|null>(null);
  useEffect(()=>{let cancelled=false;setReady(false);setError('');blob.current=null;setView('image');
    void (async()=>{try{
      const image=await loadImage(src);if(cancelled)return;
      const source=document.createElement('canvas');source.width=image.naturalWidth;source.height=image.naturalHeight;
      if(source.width*source.height>30_000_000)throw new Error('Ảnh vượt kích thước dựng an toàn của trình duyệt.');source.getContext('2d')!.drawImage(image,0,0);
      const regions:FormRegion[]=layout.regions.map((r,i)=>({id:String(i),source:r.text,text:r.translation??r.text,x:r.x/layout.width*1000,y:r.y/layout.height*1000,width:r.width/layout.width*1000,height:r.height/layout.height*1000,font_size:r.height/layout.height*1000*.72,bold:false,align:'left',color:'#202020'}));
      const output=await paintTranslation(source,{source_language:'',regions},target);if(cancelled||!canvas.current)return;
      canvas.current.width=output.canvas.width;canvas.current.height=output.canvas.height;canvas.current.getContext('2d')!.drawImage(output.canvas,0,0);blob.current=output.blob;setReady(true);
    }catch(e){if(!cancelled)setError(e instanceof Error?e.message:'Không dựng được ảnh dịch.');}})();return()=>{cancelled=true;};
  },[src,layout,target]);
  function download(){if(!ready||!blob.current)return;const url=URL.createObjectURL(blob.current),a=document.createElement('a');a.href=url;a.download=`kun-global-${target}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <div className="translated-image-panel"><div className="source-views"><button aria-pressed={view==='image'} onClick={()=>setView('image')}><ImageIcon size={14}/>Ảnh dịch giữ ảnh gốc</button><button aria-pressed={view==='text'} onClick={()=>setView('text')}><Languages size={14}/>Nội dung chữ</button><button aria-label="Tải ảnh dịch PNG" disabled={!ready} onClick={download}><Download size={14}/></button>{onDownloadWord&&<button disabled={wordBusy} onClick={onDownloadWord}><FileText size={14}/>Tải thêm Word</button>}</div><div className="image-type-controls"><span>Giữ nguyên kích thước ảnh và vị trí chữ</span><button aria-pressed={zoom} onClick={()=>setZoom(!zoom)}>{zoom?'Vừa khung':'Phóng to'}</button></div><div className={`translated-canvas ${zoom?'zoomed':''}`} hidden={view!=='image'}><canvas ref={canvas} hidden={!ready} role="img" aria-label="Ảnh dịch giữ hình ảnh gốc"/>{!ready&&!error&&<span>Đang ghép ảnh dịch…</span>}</div>{view==='text'&&<div className="result" lang={target} dir={target==='ar'?'rtl':undefined}>{text}</div>}{error&&<p className="image-render-error" role="alert">{error}</p>}<small className="image-disclaimer">Chỉ thay phần chữ; nền trong vùng chữ được phục dựng gần đúng. Không thêm trang hoặc phụ lục vào ảnh.</small></div>;
}
