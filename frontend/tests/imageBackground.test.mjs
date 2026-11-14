import assert from 'node:assert/strict';
import {backgroundColor,foregroundColor} from '../src/imageBackground.ts';
import {wrapText} from '../src/imageTypography.ts';

let sample=0;
const yellow=[255,241,113,255];
const dominant=backgroundColor(()=> (++sample%3===0?[42,38,21,255]:yellow),{x:20,y:20,width:300,height:24});
assert.deepEqual(dominant,yellow.slice(0,3),'Dark table rules must not tint a yellow form background');
assert.deepEqual(backgroundColor(()=>[0,0,0,0],{x:0,y:0,width:100,height:20}),[255,255,255]);
assert.equal(foregroundColor([20,20,20]),'#fff4d2');
assert.equal(foregroundColor([255,255,255]),'#493321');
const ctx={font:'',measureText(text){return {width:[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text)].length*10};}};
for(const text of ['TiếngViệt','ภาษาไทย','한국어테스트','中文翻译测试','👩‍👩‍👧‍👦👩‍👩‍👧‍👦']){
  const lines=wrapText(ctx,text,10);
  assert.equal(lines.join(''),text,'Wrapping must retain all Unicode characters');
  assert.ok(lines.every(line=>!/^\p{Mark}/u.test(line)),'Do not split accents from their glyph');
}
console.log('Image background, contrast and Unicode wrapping checks passed.');
