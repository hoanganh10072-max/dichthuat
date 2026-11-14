export type OutputDecision={mode:'original'|'a4';reason:string;min_font_pt:number|null};
type Fit={size:number;overflow:boolean;lines:string[]};
// Evaluate at physical A4 size, not screen pixels or the arbitrary raster DPI.
// A wider phone/desktop viewport must not select a different output format.
export function imageOutputDecision(plans:Fit[],width:number,height:number):OutputDecision{
  if(plans.some(p=>p.overflow))return {mode:'a4',reason:'Bản dịch không vừa khung gốc.',min_font_pt:null};
  const sizes=plans.filter(p=>p.lines.length).map(p=>p.size*Math.min(180/25.4*72/width,269/25.4*72/height));
  const smallest=Math.min(...sizes);
  if(!Number.isFinite(smallest)||smallest<9)return {mode:'a4',reason:'Giữ form gốc sẽ làm chữ quá nhỏ.',min_font_pt:Number.isFinite(smallest)?Math.round(smallest*100)/100:null};
  return {mode:'original',reason:'Bản dịch vừa khung và cỡ chữ đủ rõ.',min_font_pt:Math.round(smallest*100)/100};
}
