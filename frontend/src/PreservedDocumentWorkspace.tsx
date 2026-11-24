import {useState} from 'react';
import FormTranslationWorkspace from './FormTranslationWorkspace';
import {accountApi,jsonRequest} from './account-api';
type Props={languages:{code:string;name:string}[];onBusy:(busy:boolean)=>void;canTranslate:boolean};
export default function PreservedDocumentWorkspace({languages,onBusy,canTranslate}:Props){
  const [source,setSource]=useState('auto'),[target,setTarget]=useState('vi'),[busy,setBusy]=useState(false);
  return <div className="preserved-document"><div className="trial-languages"><label>Ngôn ngữ nguồn<select aria-label="Ngôn ngữ nguồn tài liệu" value={source} disabled={busy} onChange={e=>setSource(e.target.value)}><option value="auto">Tự phát hiện</option>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label><span/><label>Ngôn ngữ dịch<select aria-label="Ngôn ngữ dịch tài liệu" value={target} disabled={busy} onChange={e=>setTarget(e.target.value)}>{languages.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select></label></div><FormTranslationWorkspace mode="document" source={source} target={target} canTranslate={canTranslate} maxBytes={30*1024*1024} onBusy={value=>{setBusy(value);onBusy(value);}} call={async(body,signal)=>{
    if(body.output==='text'){
      const response=await accountApi('translate',{...jsonRequest('POST',{source,target,text:body.text,document:true}),signal});
      return {ok:true,blocks:[{kind:'paragraph',text:response.text,rows:[]}]};
    }
    return accountApi('form-translate',{...jsonRequest('POST',{source,target,...body}),signal});
  }}/></div>;
}
