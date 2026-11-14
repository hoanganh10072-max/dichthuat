type Box={x:number;y:number;width:number;height:number};
type Pixel=ArrayLike<number>;

// A few samples can all land on table rules or dark letters. Sample a ring
// around the box and use its dominant colour, without averaging ink into it.
export function backgroundColor(read:(x:number,y:number)=>Pixel,box:Box):number[] {
  const samples:number[][]=[];
  const distance=Math.max(1,Math.min(4,box.height*.12));
  for(const offset of [distance,distance+2]){
    for(let i=0;i<11;i++){
      const t=(i+.5)/11;
      for(const [x,y] of [[box.x+box.width*t,box.y-offset],[box.x+box.width*t,box.y+box.height+offset],
        [box.x-offset,box.y+box.height*t],[box.x+box.width+offset,box.y+box.height*t]]){
        const p=read(x,y);
        samples.push(p.length>3&&p[3]<16?[255,255,255]:[p[0],p[1],p[2]]);
      }
    }
  }
  const groups=new Map<string,number[][]>();
  for(const p of samples){const key=p.map(v=>Math.floor(v/24)).join(',');const group=groups.get(key)||[];group.push(p);groups.set(key,group);}
  const dominant=[...groups.values()].sort((a,b)=>b.length-a.length)[0]||[[255,255,255]];
  return [0,1,2].map(channel=>dominant.map(p=>p[channel]).sort((a,b)=>a-b)[Math.floor(dominant.length/2)]);
}

export function foregroundColor(background:number[]):string {
  const luminance=background[0]*.2126+background[1]*.7152+background[2]*.0722;
  return luminance<125?'#fff4d2':'#493321';
}
