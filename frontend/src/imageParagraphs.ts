import type {TextBox} from './imageTypography';

// Vision boxes can overlap by a few pixels around consecutive footer
// paragraphs. Lay out that text as one column instead of leaving it untranslated
// on the image. Keep table cells, short labels and other columns independent.
export function combineImageParagraphs(regions:TextBox[],imageWidth:number,imageHeight:number):TextBox[] {
  const paragraph=(r:TextBox)=>r.text.length>=90&&r.width>=imageWidth*.3&&r.height>=12&&r.height<=imageHeight*.3;
  const overlap=(a:TextBox,b:TextBox)=>Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y));
  const compatible=(a:TextBox,b:TextBox)=>{
    const gap=Math.max(a.y,b.y)-Math.min(a.y+a.height,b.y+b.height);
    return Math.abs(a.x-b.x)<=imageWidth*.045&&Math.abs(a.x+a.width-b.x-b.width)<=imageWidth*.065&&
      gap<=Math.max(2,Math.min(a.height,b.height)*.2);
  };
  const used=new Set<number>();const result:TextBox[]=[];
  regions.forEach((region,index)=>{
    if(used.has(index))return;
    if(!paragraph(region)){result.push(region);return;}
    const members=[index];
    for(let cursor=0;cursor<members.length;cursor++){
      regions.forEach((other,j)=>{
        if(!used.has(j)&&!members.includes(j)&&paragraph(other)&&compatible(regions[members[cursor]],other))members.push(j);
      });
    }
    if(members.length<2){result.push(region);return;}
    const group=members.map(i=>regions[i]).sort((a,b)=>a.y-b.y||a.x-b.x);
    const x=Math.min(...group.map(r=>r.x)),y=Math.min(...group.map(r=>r.y));
    const width=Math.max(...group.map(r=>r.x+r.width))-x,height=Math.max(...group.map(r=>r.y+r.height))-y;
    const box={x,y,width,height,text:'',translation:''};
    // Do not expand a paragraph across a separate label, signature or column.
    if(regions.some((other,j)=>!members.includes(j)&&overlap(box,other)>other.width*other.height*.2)){
      result.push(region);return;
    }
    members.forEach(i=>used.add(i));
    result.push({...box,text:group.map(r=>r.text).join(' '),translation:group.map(r=>r.translation||'').join(' ')});
  });
  return result;
}
