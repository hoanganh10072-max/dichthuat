import { useEffect, useRef, useState } from 'react';
import { Download, FileText, Image as ImageIcon, Languages } from 'lucide-react';
import { planImageTranslation, fontFamily } from './imageTypography';
import { backgroundColor, foregroundColor } from './imageBackground';
import { combineImageParagraphs } from './imageParagraphs';
import {imageOutputDecision,type OutputDecision} from './outputPolicy';

export type Region = { text: string; x: number; y: number; width: number; height: number; translation?: string };
export type Layout = { width: number; height: number; regions: Region[] };

export default function TranslatedImage({ src, layout, text, target, onDownloadWord, wordBusy=false }: { src: string; layout: Layout; text: string; target: string; onDownloadWord?:()=>void;wordBusy?:boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [view, setView] = useState<'image' | 'text'|'a4'>('image');
  const [decision,setDecision]=useState<OutputDecision|null>(null);
  const manualView=useRef(false);
  useEffect(()=>{manualView.current=false;setDecision(null);},[src,layout]);
  function chooseView(next:'image'|'text'|'a4'){manualView.current=true;setView(next);}
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [fontScale, setFontScale] = useState(1);
  const [zoom, setZoom] = useState(false);
  const [continuationCount, setContinuationCount] = useState(0);
  const [exporting,setExporting]=useState(false);
  useEffect(() => {
    let cancelled = false;
    setReady(false); setError(''); setContinuationCount(0);
    const image = new window.Image();
    image.onload = async () => {
      await document.fonts.ready;
      if (cancelled || !canvas.current) return;
      const c = canvas.current;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      if (!ctx) { setError('Trình duyệt không dựng được ảnh dịch.');setDecision({mode:'a4',reason:'Dùng Word A4 để xem đầy đủ bản dịch.',min_font_pt:null});setView('a4');return; }
      try {
        const renderRegions=combineImageParagraphs(layout.regions,layout.width,layout.height);
        const page = planImageTranslation(ctx,renderRegions,layout.width,layout.height,fontScale);
        const selected=imageOutputDecision(page.plans,layout.width,layout.height);
        setDecision(selected);
        if(!manualView.current)setView(selected.mode==='a4'?'a4':'image');
        const { plans, continuations, padding, size, labelWidth, lineHeight } = page;
        // Bound the complete raster, including the continuation area. Reserve
        // room for the caption added by download() below browser canvas limits.
        const resolution = Math.min(2, Math.sqrt(24_000_000/(layout.width*page.height)),15_000/Math.max(layout.width,page.height));
        c.width = Math.max(1,Math.round(layout.width*resolution));
        c.height = Math.max(1,Math.round(page.height*resolution));
        ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);
        ctx.drawImage(image, 0, 0, c.width, Math.round(layout.height*resolution));
        ctx.scale(resolution,resolution);
        // Read all background samples before painting any translated region.
        const colors = renderRegions.map(r => backgroundColor((x,y)=>ctx.getImageData(
          Math.max(0,Math.min(c.width-1,Math.round(x*resolution))),
          Math.max(0,Math.min(Math.max(0,Math.round(layout.height*resolution)-1),Math.round(y*resolution))),1,1).data,r));
        plans.forEach((p, index) => {
          if (!p.clearSource || !p.lines.length) return;
          const bounds=p.sourceBounds;
          ctx.save(); ctx.beginPath(); ctx.rect(bounds.x,bounds.y,bounds.width,bounds.height); ctx.clip();
          ctx.fillStyle = `rgb(${colors[index].join(',')})`;
          ctx.fillRect(bounds.x,bounds.y,bounds.width,bounds.height);
          ctx.restore();
        });
        plans.forEach((p,index) => {
          if (p.overflow) {
            if (!p.clearSource) return;
            ctx.save(); ctx.beginPath(); ctx.rect(p.x,p.y,p.width,p.height); ctx.clip();
            ctx.font = `700 ${Math.max(6,Math.min(14,p.height*.7))}px ${fontFamily}`;
            ctx.fillStyle = foregroundColor(colors[index]); ctx.textBaseline = 'top'; ctx.textAlign = 'left';
            ctx.fillText(`[${index+1}]`,p.x,p.y,Math.max(1,p.width));
            ctx.restore();
            return;
          }
          ctx.save(); ctx.beginPath(); ctx.rect(p.x,p.y,p.width,p.height); ctx.clip();
          ctx.font = `500 ${p.size}px ${fontFamily}`;
          ctx.fillStyle = foregroundColor(colors[index]); ctx.textBaseline = 'alphabetic';
          ctx.direction=target==='ar'?'rtl':'ltr';
          ctx.textAlign = p.centered ? 'center' : target==='ar'?'right':'left';
          p.lines.forEach((line,i) => ctx.fillText(line,p.centered ? p.x+p.width/2 : target==='ar'?p.x+p.width:p.x,p.y+p.ascent+i*p.lineHeight));
          ctx.restore();
        });
        if (continuations.length) {
          ctx.fillStyle = '#fff7e8';ctx.fillRect(0,layout.height,layout.width,page.height-layout.height);
          ctx.fillStyle = '#ddbd7c';ctx.fillRect(0,layout.height,layout.width,2);
          ctx.textAlign = 'left';ctx.textBaseline = 'top';ctx.fillStyle = '#78531f';
          ctx.font = `700 ${size}px ${fontFamily}`;
          ctx.fillText('BẢN DỊCH CÁC VÙNG CHỮ DÀI',padding,layout.height+padding,Math.max(1,layout.width-padding*2));
          for (const entry of continuations) {
            ctx.font = `700 ${size}px ${fontFamily}`;ctx.fillStyle = '#a47b31';
            ctx.fillText(`[${entry.number}]`,padding,entry.y);
            ctx.font = `600 ${size}px ${fontFamily}`;ctx.fillStyle = '#97794f';
            entry.sourceLines.forEach((line,i)=>ctx.fillText(line,padding+labelWidth,entry.y+i*lineHeight));
            ctx.font = `600 ${size}px ${fontFamily}`;ctx.fillStyle = '#493321';
            entry.lines.forEach((line,i)=>ctx.fillText(line,padding+labelWidth,entry.y+entry.sourceHeight+i*lineHeight));
          }
        }
        setContinuationCount(continuations.length);
        setReady(true);
      } catch (e) { setError(e instanceof Error ? e.message : 'Không dựng được ảnh dịch.');setDecision({mode:'a4',reason:'Không dựng được form gốc trên trình duyệt; dùng bản Word A4.',min_font_pt:null});setView('a4'); }
    };
    image.onerror = () => { if (!cancelled){setError('Không đọc được ảnh gốc để ghép bản dịch.');setDecision({mode:'a4',reason:'Dùng Word A4 để xem đầy đủ bản dịch.',min_font_pt:null});setView('a4');} };
    image.src = src;
    return () => { cancelled = true; };
  }, [src, layout, fontScale,target]);
  function download() {
    if (!canvas.current || !ready || exporting) return;
    setExporting(true);
    // Export includes a visible machine-translation caption outside the source.
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = canvas.current.width;
    const captionHeight = Math.max(28, Math.round(exportCanvas.width * .035));
    exportCanvas.height = canvas.current.height + captionHeight;
    const ctx = exportCanvas.getContext('2d');
    if(!ctx){setExporting(false);setError('Trình duyệt không tạo được file PNG.');return;}
    ctx.drawImage(canvas.current,0,0); ctx.fillStyle='#faf2df'; ctx.fillRect(0,canvas.current.height,exportCanvas.width,captionHeight);
    ctx.fillStyle='#63451f'; ctx.font=`${Math.max(10,Math.round(captionHeight*.42))}px Arial`; ctx.fillText('KUN GLOBAL · Bản dịch máy tham khảo',8,canvas.current.height+captionHeight*.65,exportCanvas.width-16);
    try {
      exportCanvas.toBlob(blob => { setExporting(false);if (!blob) {setError('Không xuất được ảnh PNG. Hãy thử tải lại.');return;} const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`kun-global-${target}.png`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); },'image/png');
    }catch{setExporting(false);setError('Không xuất được ảnh PNG. Hãy thử tải lại.');}
  }
  return <div className="translated-image-panel">
    <div className="source-views"><button aria-pressed={view==='image'} onClick={()=>chooseView('image')}><ImageIcon size={14}/>Ảnh dịch</button><button aria-pressed={view==='a4'} onClick={()=>chooseView('a4')}><FileText size={14}/>Word A4</button><button aria-pressed={view==='text'} onClick={()=>chooseView('text')}><Languages size={14}/>Văn bản</button><button aria-label="Tải ảnh dịch PNG" disabled={!ready||exporting} onClick={download}><Download size={14}/></button></div>
    {decision&&<div className="output-choice" role="status"><strong>Tự chọn: {decision.mode==='original'?'Giữ form gốc':'Word A4 dễ đọc'}</strong><span>{decision.reason}</span></div>}
    {view==='image' && <div className="image-type-controls"><span>Cỡ chữ</span><button aria-label="Giảm cỡ chữ ảnh dịch" disabled={fontScale<=.85} onClick={()=>setFontScale(v=>Math.max(.85,v-.15))}>A−</button><span>{Math.round(fontScale*100)}%</span><button aria-label="Tăng cỡ chữ ảnh dịch" disabled={fontScale>=1.9} onClick={()=>setFontScale(v=>Math.min(1.9,v+.15))}>A+</button><button aria-pressed={zoom} onClick={()=>setZoom(v=>!v)}>{zoom ? 'Vừa khung' : 'Phóng to'}</button></div>}
    <div className={`translated-canvas ${zoom ? 'zoomed' : ''} ${continuationCount ? 'has-appendix' : ''}`} hidden={view!=='image'}><canvas hidden={!ready} ref={canvas} role="img" aria-label="Ảnh dịch máy theo bố cục gốc"/>{!ready && !error && <span>Đang ghép ảnh dịch…</span>}</div>
    {view==='a4'&&<div className="a4-output-panel"><div className="a4-output-heading"><strong>Word A4 · Nền trắng</strong>{onDownloadWord&&<button className="primary" disabled={wordBusy} onClick={onDownloadWord}><Download size={14}/>{wordBusy?'Đang tạo Word…':'Tải Word A4'}</button>}</div><small>Nội dung bản dịch · Tải Word để xem và chỉnh sửa khung bảng.</small><div className="a4-output-text" lang={target} dir={target==='ar'?'rtl':undefined}>{text.split('\n').filter(Boolean).map((line,i)=><p key={i}>{line}</p>)}</div></div>}
    {view==='text' && <div className="result" lang={target} dir={target==='ar'?'rtl':undefined}>{text}</div>}
    {error && <p className="image-render-error" role="alert">{error}</p>}
    {view==='image'&&!!continuationCount && <small className="image-continuation-note" role="status">{continuationCount} vùng chữ dài được ghi đầy đủ phía dưới ảnh, theo số đánh dấu. Cuộn ảnh để xem tiếp.</small>}
    {view==='image'&&<small className="image-disclaimer">Ảnh dịch máy · Nền vùng chữ được phủ lại; kiểm tra nội dung với ảnh gốc.</small>}
  </div>;
}
