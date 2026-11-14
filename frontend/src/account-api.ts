export type Account = {id:string;username:string;role:'admin'|'user';active:boolean;created_at:number};

export async function accountApi(path:string, init:RequestInit={}) {
  let response:Response;
  try {
    response = await fetch(`/api/${path}`, {...init, credentials:'same-origin',
      headers:{...Object.fromEntries(new Headers(init.headers)), 'X-Kun-Request':'1'}});
  }catch(error){
    if(error instanceof DOMException&&error.name==='AbortError')throw error;
    throw new Error('Mất kết nối máy chủ. Kiểm tra mạng và bấm thử lại; chưa có kết quả mới.');
  }
  const body = await response.json().catch(()=>null);
  if(!response.ok) {
    if(response.status===401&&path!=='auth/login')window.dispatchEvent(new Event('kun-auth-expired'));
    throw new Error(typeof body?.detail==='string'?body.detail:'Máy chủ chưa xử lý được yêu cầu.');
  }
  if(body===null&&response.status!==204)throw new Error('Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.');
  return body;
}

export function jsonRequest(method:string, body:unknown):RequestInit {
  return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
}

export async function accountFile(path:string,init:RequestInit):Promise<Blob>{
  let response:Response;
  try{response=await fetch(`/api/${path}`,{...init,credentials:'same-origin',headers:{...Object.fromEntries(new Headers(init.headers)),'X-Kun-Request':'1'}});}
  catch{throw new Error('Mất kết nối khi xuất Word. Hãy thử tải lại.');}
  if(!response.ok){
    if(response.status===401)window.dispatchEvent(new Event('kun-auth-expired'));
    const body=await response.json().catch(()=>null);
    throw new Error(typeof body?.detail==='string'?body.detail:'Không xuất được Word. Hãy thử lại.');
  }
  const blob=await response.blob();
  if((await blob.slice(0,2).text())!=='PK')throw new Error('Máy chủ chưa trả về file Word hợp lệ. Hãy thử lại.');
  return blob;
}

export function saveWord(blob:Blob,filename='kun-global-ban-dich.docx'){
  const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
