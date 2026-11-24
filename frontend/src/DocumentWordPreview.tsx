import type {CSSProperties,ReactNode} from 'react';
import type {WordPage} from './DocumentWorkspace';

type Block=WordPage['blocks'][number];
const text=(b:Block)=>b.keep?b.text:b.translation||'Chưa có bản dịch vùng này.';
function snap(values:number[],tolerance:number){
  const groups:number[][]=[];
  for(const value of values.sort((a,b)=>a-b)){
    const last=groups.at(-1);if(last&&value-last.at(-1)!<=tolerance)last.push(value);else groups.push([value]);
  }
  return groups.map(group=>group.reduce((a,b)=>a+b,0)/group.length);
}
export default function DocumentWordPreview({page,language}:{page:WordPage;language:string}){
  let remaining=[...page.blocks];const content:ReactNode[]=[];
  const paragraph=(b:Block,inCell=false)=>{
    const f=b.format||{};
    const style:CSSProperties={textAlign:f.alignment,fontSize:`${Math.max(10,Math.min(24,f.font_size_pt||11))/11}em`,fontWeight:f.bold?'bold':'normal',fontStyle:f.italic?'italic':'normal',textDecoration:f.underline?'underline':undefined};
    if(!inCell){style.marginLeft=`${b.x/page.width*100}%`;style.width=`${Math.min(100-b.x/page.width*100,Math.max(30,b.width/page.width*100))}%`;}
    if(!inCell&&text(b).length>250&&(f.role==='paragraph'||f.role==='footer')){style.marginLeft=0;style.width='100%';}
    if(!inCell&&f.alignment==='center'&&Math.abs(b.x+b.width/2-page.width/2)<page.width*.05){style.marginLeft=0;style.width='100%';}
    return <p key={b.id} data-role={f.role} style={style}>{text(b)}</p>;
  };
  const paragraphs=(blocks:Block[],inCell=false)=>{
    const sorted=[...blocks].sort((a,b)=>a.y-b.y||a.x-b.x);
    if(inCell)return sorted.map(b=>paragraph(b,true));
    const groups:{items:Block[];bottom:number}[]=[];
    for(const b of sorted){const last=groups.at(-1);if(last&&b.y<=last.bottom+2){last.items.push(b);last.bottom=Math.max(last.bottom,b.y+b.height);}else groups.push({items:[b],bottom:b.y+b.height});}
    return groups.map(group=>{
      const starts=snap(group.items.map(b=>b.x),page.width*.065);
      if(starts.length<2||starts.at(-1)!-starts[0]<=page.width*.1)return group.items.map(b=>paragraph(b));
      const centered=group.items.every(b=>b.format?.alignment==='center');
      const anchors=centered?snap(group.items.map(b=>b.x+b.width/2),page.width*.065):starts;
      const edges=centered&&anchors.length>1?[Math.max(0,anchors[0]-(anchors[1]-anchors[0])/2),...anchors.slice(1).map((x,i)=>(x+anchors[i])/2),Math.min(page.width,anchors.at(-1)!+(anchors.at(-1)!-anchors.at(-2)!)/2)]:[...starts,Math.min(page.width,Math.max(...group.items.map(b=>b.x+b.width)))];
      const buckets=edges.slice(1).map(()=>[] as Block[]);
      for(const b of group.items){const position=centered?b.x+b.width/2:b.x;let closest=0;anchors.forEach((x,i)=>{if(Math.abs(x-position)<Math.abs(anchors[closest]-position))closest=i;});buckets[closest].push(b);}
      return <div className="document-preview-columns" key={`columns-${group.items[0].id}`} style={{marginLeft:`${edges[0]/page.width*100}%`,width:`${(edges.at(-1)!-edges[0])/page.width*100}%`,gridTemplateColumns:edges.slice(1).map((x,i)=>`${Math.max(1,x-edges[i])}fr`).join(' ')}}>{buckets.map((bucket,i)=><div key={i}>{bucket.map(b=>paragraph(b,true))}</div>)}</div>;
    });
  };
  const cellContent=(cell:NonNullable<WordPage['tables']>[number]['cells'][number],blocks:Block[])=>{
    if(!cell.flow_rows)return paragraphs(blocks,true);
    const byId=new Map(blocks.map(b=>[b.id,b])),seen=new Set<string>();
    const rows=cell.flow_rows.map((row,i)=><div className="document-preview-form-row" key={i} style={{gridTemplateColumns:row.cells.map(c=>`${c.weight}fr`).join(' ')}}>{row.cells.map((c,j)=><p key={j}>{c.region_ids.map(id=>{
      const b=byId.get(id);if(!b)return null;seen.add(id);const f=b.format||{};
      return <span key={id} style={{fontWeight:f.bold?'bold':'normal',fontStyle:f.italic?'italic':'normal',textDecoration:f.underline?'underline':undefined}}>{text(b)}{' '}</span>;
    })}</p>)}</div>);
    return <>{rows}{paragraphs(blocks.filter(b=>!seen.has(b.id)),true)}</>;
  };
  for(const [index,frame] of (page.tables||[]).entries()){
    const xs=snap(frame.cells.flatMap(c=>[c.x,c.x+c.width]),page.width*.007);
    const ys=snap(frame.cells.flatMap(c=>[c.y,c.y+c.height]),page.width*.007);
    if(xs.length<2||ys.length<2||xs.length*ys.length>1600)continue;
    const before=remaining.filter(b=>b.y+b.height/2<frame.y);content.push(...paragraphs(before));
    remaining=remaining.filter(b=>!before.includes(b));
    const inside=remaining.filter(b=>b.height<=b.width*2&&b.x+b.width/2>=frame.x&&b.x+b.width/2<=frame.x+frame.width&&b.y+b.height/2>=frame.y&&b.y+b.height/2<=frame.y+frame.height);
    const nearest=(values:number[],value:number)=>values.reduce((best,v,i)=>Math.abs(v-value)<Math.abs(values[best]-value)?i:best,0);
    const occupied=new Set<string>();
    const cells:{row:number;col:number;rowSpan:number;colSpan:number;blocks:Block[];source:typeof frame.cells[number]}[]=[];
    for(const source of [...frame.cells].sort((a,b)=>b.width*b.height-a.width*a.height)){
      const col=nearest(xs,source.x),endCol=nearest(xs,source.x+source.width),row=nearest(ys,source.y),endRow=nearest(ys,source.y+source.height);
      const slots=Array.from({length:Math.max(0,endRow-row)},(_,r)=>Array.from({length:Math.max(0,endCol-col)},(_,c)=>`${row+r}:${col+c}`)).flat();
      if(!slots.length||slots.some(slot=>occupied.has(slot)))continue;
      slots.forEach(slot=>occupied.add(slot));cells.push({row,col,rowSpan:endRow-row,colSpan:endCol-col,blocks:[],source});
    }
    if(!cells.length)continue;
    for(const block of inside){
      const cx=block.x+block.width/2,cy=block.y+block.height/2;
      const cell=cells.find(c=>cx>=c.source.x-3&&cx<=c.source.x+c.source.width+3&&cy>=c.source.y-3&&cy<=c.source.y+c.source.height+3)||cells.reduce((a,b)=>Math.hypot(a.source.x-cx,a.source.y-cy)<Math.hypot(b.source.x-cx,b.source.y-cy)?a:b);
      cell.blocks.push(block);
    }
    const expanded=(inside.length>35||frame.cells.length>=6)&&frame.width/page.width*180<140;
    content.push(<table key={`table-${index}`} style={{width:expanded?'100%':`${(xs.at(-1)!-xs[0])/page.width*100}%`,marginLeft:expanded?0:`${xs[0]/page.width*100}%`}} aria-label={`Bảng ${index+1} trong bản dịch`}><colgroup>{xs.slice(1).map((x,i)=><col key={i} style={{width:`${(x-xs[i])/(xs.at(-1)!-xs[0])*100}%`}}/>)}</colgroup><tbody>{ys.slice(1).map((_,r)=><tr key={r} data-header={r<(frame.header_rows||0)||undefined}>{xs.slice(1).map((_,c)=>{
      const cell=cells.find(v=>v.row===r&&v.col===c);
      return cell?<td key={c} rowSpan={cell.rowSpan} colSpan={cell.colSpan}>{cellContent(cell.source,cell.blocks)}</td>:occupied.has(`${r}:${c}`)?null:<td key={c}/>;
    })}</tr>)}</tbody></table>);
    remaining=remaining.filter(b=>!inside.includes(b));
  }
  content.push(...paragraphs(remaining));
  return <div className="document-word-preview" lang={language} dir={language==='ar'?'rtl':undefined}><small>Xem trước cấu trúc · Tải Word để xem phân trang đầy đủ</small>{content.length?content:<p>Trang này không có chữ được nhận diện.</p>}</div>;
}
