import {cp,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
for(const directory of ['cmaps','standard_fonts','wasm']){
  const from=fileURLToPath(new URL(`../node_modules/pdfjs-dist/${directory}`,import.meta.url));
  const to=fileURLToPath(new URL(`../public/pdfjs/${directory}`,import.meta.url));
  await mkdir(to,{recursive:true});await cp(from,to,{recursive:true});
}
