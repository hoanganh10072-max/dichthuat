export type TextBox = { text: string; translation?: string; x: number; y: number; width: number; height: number };
type Metrics = { font: string; measureText: (text: string) => { width: number; actualBoundingBoxAscent?:number; actualBoundingBoxDescent?:number } };
export const fontFamily = '"Segoe UI", Arial, sans-serif';

export function wrapText(ctx: Metrics, text: string, width: number) {
  const lines: string[] = []; let current = '';
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width <= width) { current = candidate; continue; }
    if (current) lines.push(current);
    current = '';
    const letters=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(word)].map(part=>part.segment):Array.from(word);
    for (const letter of letters) {
      if (current && ctx.measureText(current + letter).width > width) { lines.push(current); current = ''; }
      current += letter;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export function planText(ctx: Metrics, regions: TextBox[], imageWidth: number, imageHeight: number, scale: number) {
  const median = (values:number[]) => {
    const sorted=values.filter(n=>Number.isFinite(n)&&n>0).sort((a,b)=>a-b);
    return sorted.length ? sorted[Math.floor(sorted.length/2)] : 12;
  };
  const intersects = (a:{x:number;y:number;width:number;height:number},b:{x:number;y:number;width:number;height:number}) =>
    Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>.5 && Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>.5;
  const metrics = (text:string,size:number) => {
    const m=ctx.measureText(text);
    return {width:m.width,ascent:m.actualBoundingBoxAscent??size*.8,descent:Math.max(0,m.actualBoundingBoxDescent??size*.2)};
  };
  const sourceBounds=regions.map(r=>{
    const x=Math.max(0,Math.min(imageWidth,r.x)), y=Math.max(0,Math.min(imageHeight,r.y));
    return {x,y,width:Math.max(0,Math.min(imageWidth,r.x+r.width)-x),height:Math.max(0,Math.min(imageHeight,r.y+r.height)-y)};
  });
  const boxes=sourceBounds.map(box=>({...box}));
  // Separate small coordinate overlaps at a shared boundary. Erase using the
  // original source bounds later, but draw each translation inside its own area.
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i],b=boxes[j];
    const dx=Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x);
    const dy=Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y);
    if(dx<=0||dy<=0)continue;
    if(dx<=Math.min(a.width,b.width)*.2&&dy>Math.min(a.height,b.height)*.4){
      const left=a.x<b.x?a:b,right=left===a?b:a;
      const edge=(left.x+left.width+right.x)/2,end=right.x+right.width;
      left.width=edge-left.x;right.x=edge;right.width=end-edge;
    }else if(dy<=Math.min(a.height,b.height)*.2&&dx>Math.min(a.width,b.width)*.8){
      const top=a.y<b.y?a:b,bottom=top===a?b:a;
      const edge=(top.y+top.height+bottom.y)/2,end=bottom.y+bottom.height;
      top.height=edge-top.y;bottom.y=edge;bottom.height=end-edge;
    }
  }
  ctx.font=`500 100px ${fontFamily}`;
  const sourceSizes=regions.map((r,i)=>{
    const m=metrics(r.text,100),box=boxes[i];
    // A paragraph is multiple lines. Measuring its full text as one line
    // grossly underestimates its font and sends entire footers to the appendix.
    const widthSize=r.text.length>=90&&box.height>=12&&box.width>=imageWidth*.3
      ? Math.sqrt(box.width*box.height*100/Math.max(1,m.width*1.35))
      : box.width*100/Math.max(1,m.width);
    return Math.max(6,Math.min(box.height*100/Math.max(1,m.ascent+m.descent),widthSize));
  });
  const bodySize=median(sourceSizes),bodyHeight=median(boxes.map(box=>box.height));
  const tallOverlaps=boxes.map((box,index)=>box.height>bodyHeight*2.2&&boxes.some((other,i)=>{
    if(i===index||!intersects(box,other))return false;
    const area=(Math.min(box.x+box.width,other.x+other.width)-Math.max(box.x,other.x))*
      (Math.min(box.y+box.height,other.y+other.height)-Math.max(box.y,other.y));
    return area>Math.min(box.width*box.height,other.width*other.height)*.15;
  }));
  const occupied:{x:number;y:number;width:number;height:number}[]=[];
  return regions.map((r,index)=>{
    const box=boxes[index];
    // OCR can join several table rows into one tall, overlapping box. Its
    // height is not a font size and must not become a large painted rectangle.
    const unsafeBounds=tallOverlaps[index]||boxes.some((other,i)=>{
      if(i===index||tallOverlaps[i]||!intersects(box,other))return false;
      const area=(Math.min(box.x+box.width,other.x+other.width)-Math.max(box.x,other.x))*
        (Math.min(box.y+box.height,other.y+other.height)-Math.max(box.y,other.y));
      // A one-pixel corner contact is not an ambiguous paragraph. Actual ink
      // collisions are still checked below using the fitted text dimensions.
      return area>Math.min(box.width*box.height,other.width*other.height)*.03;
    });
    const sourceSize=Math.min(sourceSizes[index],bodySize*2.2);
    const preferred=Math.max(6,Math.round(sourceSize*scale));
    const minimum=Math.max(6,Math.min(preferred,Math.floor(sourceSize*.7),Math.floor(bodySize*.9)));
    let size=preferred,lines:string[]=[],ascent=0,paintHeight=0,lineHeight=0,inkWidth=0;
    for(;size>=minimum;size--){
      ctx.font=`500 ${size}px ${fontFamily}`;
      lines=wrapText(ctx,r.translation||'',Math.max(1,box.width));
      const measured=lines.map(line=>metrics(line,size));
      ascent=Math.max(0,...measured.map(m=>m.ascent));
      const descent=Math.max(0,...measured.map(m=>m.descent));
      lineHeight=Math.max(size*1.35,ascent+descent+size*.12);
      paintHeight=lines.length ? ascent+descent+(lines.length-1)*lineHeight : 0;
      inkWidth=Math.max(0,...measured.map(m=>m.width));
      if(paintHeight<=box.height&&inkWidth<=box.width)break;
    }
    if(size<minimum)size=minimum;
    const centered=r.text.length<90&&box.width>imageWidth*.2&&Math.abs(box.x+box.width/2-imageWidth/2)<imageWidth*.08;
    const ink={x:centered?box.x+(box.width-inkWidth)/2:box.x,y:box.y,width:inkWidth,height:paintHeight};
    const overflow=unsafeBounds||box.width<=0||box.height<=0||paintHeight>box.height||inkWidth>box.width||occupied.some(other=>intersects(ink,other));
    if(!overflow&&lines.length)occupied.push(ink);
    return {original:r,sourceBounds:sourceBounds[index],...box,size,lines,centered,overflow,ascent,paintHeight,lineHeight,clearSource:!unsafeBounds};
  });
}

// A crowded OCR box must not prevent every other region from rendering.
// Keep fitted translations at their anchors and give long translations a
// numbered continuation below the source image, at a readable font size.
export function planImageTranslation(ctx: Metrics, regions: TextBox[], imageWidth: number, imageHeight: number, scale: number) {
  const plans = planText(ctx, regions, imageWidth, imageHeight, scale);
  const padding = Math.max(8, Math.min(36, imageWidth * .035));
  const size = Math.max(12, Math.min(26, Math.round(imageWidth * .02 * scale)));
  const labelWidth = Math.max(24, size * 2.8);
  const textWidth = Math.max(size, imageWidth - padding * 2 - labelWidth);
  const lineHeight = size * 1.5;
  let nextY = imageHeight + padding + size * 2.8;
  const continuations = plans.flatMap((plan, index) => {
    if (!plan.overflow) return [];
    ctx.font = `600 ${size}px ${fontFamily}`;
    const lines = wrapText(ctx, plan.original.translation || '', textWidth);
    const sourceLines=plan.clearSource?[]:wrapText(ctx,`Gốc: ${plan.original.text}`,textWidth);
    const sourceHeight=sourceLines.length?sourceLines.length*lineHeight+size*.5:0;
    const entry = { number:index + 1, lines, sourceLines, sourceHeight, y:nextY, height:Math.max(1,lines.length) * lineHeight+sourceHeight };
    nextY += entry.height + padding;
    return [entry];
  });
  return { plans, continuations, padding, size, labelWidth, lineHeight,
    height:continuations.length ? Math.ceil(nextY + padding * .5) : imageHeight };
}
