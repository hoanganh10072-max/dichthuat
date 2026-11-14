import assert from 'node:assert/strict';
import {planText,planImageTranslation} from '../src/imageTypography.ts';

const ctx={font:'',measureText(text){return {width:Array.from(text).length*Number(this.font.match(/([\d.]+)px/)?.[1]||12)*.5};}};
const regions=[
  {text:'title',translation:'Xin chào',x:40,y:30,width:400,height:20},
  {text:'crowded',translation:Array.from({length:100},(_,i)=>`mục${i}`).join(' '),x:40,y:110,width:60,height:12},
  {text:'next row',translation:'Đã dịch đầy đủ',x:40,y:140,width:400,height:24},
];
for(const scale of [.85,1.15,1.9]){
  const page=planImageTranslation(ctx,regions,600,420,scale);
  assert.ok(page.plans[1].overflow,'Fixture must reproduce a crowded OCR box');
  assert.ok(!page.plans[0].overflow&&!page.plans[2].overflow,'Uncrowded regions must remain in place');
  assert.equal(page.continuations.length,1);
  assert.equal(page.continuations[0].number,2,'Reference must identify the original region');
  assert.equal(page.continuations[0].lines.join(' '),regions[1].translation,'Every word must be retained');
  assert.ok(page.continuations[0].y>=420,'Continuation must not overwrite the source');
  assert.ok(page.height>page.continuations[0].y+page.continuations[0].height,'Canvas must include the complete continuation');
}
const fitted=planImageTranslation(ctx,[regions[0]],600,420,1.15);
assert.equal(fitted.continuations.length,0);
assert.equal(fitted.height,420,'Fitted images retain their original layout height');
const adjacent=[{text:'left',translation:'Tên tác giả',x:50,y:200,width:100,height:20},{text:'right',translation:'Công ty',x:250,y:200,width:200,height:20}];
const [left]=planText(ctx,adjacent,600,420,1.15);
assert.ok(left.x+left.width<250,'Fitted regions must respect adjacent columns');
const dense=[
  {text:'Line one',translation:'Dòng thứ nhất',x:30,y:25,width:180,height:15},
  {text:'Line two',translation:'Dòng thứ hai',x:30,y:50,width:180,height:15},
  {text:'Noisy merged OCR rows',translation:'Nội dung trong vùng nhận diện sai chiều cao',x:30,y:85,width:400,height:180},
  {text:'Number',translation:'Mã số',x:35,y:105,width:130,height:14},
  {text:'Left',translation:'Cột trái',x:30,y:300,width:180,height:18},
  {text:'Right',translation:'Cột phải',x:180,y:305,width:190,height:18},
];
for(const scale of [.85,1,1.9]){
  const page=planImageTranslation(ctx,dense,600,500,scale);
  assert.ok(page.plans[2].overflow&&!page.plans[2].clearSource,'Tall merged OCR box must not erase or repaint the form');
  assert.ok(!page.plans[4].overflow&&!page.plans[5].overflow,'Small column overlaps should be split instead of leaving source text');
  assert.ok(page.plans[4].x+page.plans[4].width<=page.plans[5].x,'Repaired column boundaries must not overlap');
  assert.ok(page.plans.every(p=>p.width<=p.original.width&&p.height<=p.original.height),'Never expand into another table cell');
  for(const p of page.plans.filter(p=>!p.overflow)){
    assert.ok(p.paintHeight<=p.height&&p.size<=35,'Text must fit its own box instead of using inflated OCR height');
    assert.ok(p.x>=0&&p.y>=0&&p.x+p.width<=600&&p.y+p.height<=500);
  }
  const ambiguous=page.continuations.find(p=>p.number===3);
  assert.ok(ambiguous.sourceLines.join(' ').includes('Noisy merged OCR rows'),'Unmarked ambiguous regions retain source text for reference');
}
console.log('Image layout regression checks passed (overflow, complete text, markers, font scale, original layout).');
