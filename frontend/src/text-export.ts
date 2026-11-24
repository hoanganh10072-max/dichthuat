export type TextBlock={kind:'heading'|'paragraph'|'table';text:string;rows:string[][]};
export function textContent(blocks:TextBlock[]){return blocks.map(b=>b.kind==='table'?b.rows.map(r=>r.join('\t')).join('\n'):b.text).join('\n\n');}
export function saveBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export async function textWord(blocks:TextBlock[]){
  const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,BorderStyle,HeadingLevel}=await import('docx');
  const border={style:BorderStyle.SINGLE,size:5,color:'9B9B9B'};
  const runs=(text:string)=>text.split('\n').map((line,i)=>new TextRun({text:line,break:i?1:0}));
  const children=blocks.map(b=>b.kind==='table'?new Table({width:{size:100,type:WidthType.PERCENTAGE},borders:{top:border,bottom:border,left:border,right:border,insideHorizontal:border,insideVertical:border},rows:b.rows.map(row=>new TableRow({children:row.map(text=>new TableCell({margins:{top:100,bottom:100,left:100,right:100},children:[new Paragraph({children:runs(text)})]}))}))}):new Paragraph({...(b.kind==='heading'?{heading:HeadingLevel.HEADING_2}:{}),children:runs(b.text),spacing:{after:160}}));
  return Packer.toBlob(new Document({creator:'KUN GLOBAL',title:'Bản dịch',styles:{default:{document:{run:{font:'Arial',size:24,color:'000000'},paragraph:{spacing:{after:160,line:288}}},heading2:{run:{font:'Arial',size:28,bold:true,color:'000000'},paragraph:{spacing:{before:200,after:160}}}}},sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:900,bottom:900,left:1000,right:1000}}},children}]}));
}
