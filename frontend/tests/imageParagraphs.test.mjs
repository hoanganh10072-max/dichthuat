import assert from 'node:assert/strict';
import {combineImageParagraphs} from '../src/imageParagraphs.ts';
import {planImageTranslation} from '../src/imageTypography.ts';

const ctx={font:'',measureText(text){return {width:Array.from(text).length*Number(this.font.match(/([\d.]+)px/)?.[1]||12)*.5};}};
const paragraph=(y,height,count=200)=>({x:109,y,width:365,height,text:'source '.repeat(Math.ceil(count/7)).slice(0,count),translation:'Dịch đủ nội dung. '.repeat(10)});
const source=[paragraph(591,25,238),paragraph(615,17,215),
  {x:109,y:632,width:263,height:9,text:'s'.repeat(79),translation:'Nội dung cuối đoạn.'},
  paragraph(648,18,208),paragraph(666,25,312),paragraph(698,18,220),paragraph(716,24,285),
  {x:109,y:746,width:179,height:11,text:'Verification address',translation:'Địa chỉ xác minh'},
  {x:18,y:668,width:106,height:79,text:'Seal text '.repeat(10),translation:'Tên cơ quan trên con dấu được dịch đầy đủ.'}];
const prepared=combineImageParagraphs(source,650,802);
assert.ok(prepared.length<source.length,'Consecutive footer paragraphs must be laid out together');
for(const region of source)assert.ok(prepared.some(r=>r.translation.includes(region.translation)),'Never omit an input translation');
const page=planImageTranslation(ctx,prepared,650,802,1);
assert.ok(page.plans.every(p=>!p.overflow&&p.clearSource),'Footer text and nearby seal must render inline');
assert.ok(page.plans.filter(p=>p.original.text.length>=90).every(p=>!p.centered),'Paragraphs retain left alignment');

const columns=[paragraph(600,40),{...paragraph(600,40),x:480,width:150}];
assert.equal(combineImageParagraphs(columns,800,900).length,2,'Do not merge separate columns');
const intrusiveLabel={x:160,y:610,width:80,height:15,text:'Separate field',translation:'Trường khác'};
assert.equal(combineImageParagraphs([paragraph(600,25),paragraph(624,25),intrusiveLabel],650,802).length,3,'Do not merge across a separate form field');
const distant=[paragraph(300,25),paragraph(600,25)];
assert.equal(combineImageParagraphs(distant,650,802).length,2,'Distant sections must remain independent');
assert.deepEqual(source[0],paragraph(591,25,238),'Do not mutate model coordinates');
console.log('Footer layout checks passed: complete inline translation, seal boundaries, paragraph alignment, separate columns.');
