import type {Build, Structure, Options, Capabilities, GenerationJob, Architecture} from './types';
async function request<T>(url:string,init?:RequestInit):Promise<T> {
  const response=await fetch(url,init);
  if(!response.ok) {
    const data=await response.json().catch(()=>({detail:'Não foi possível acessar a API.'}));
    throw new Error(typeof data.detail==='string'?data.detail:`Falha na solicitação (HTTP ${response.status}).`);
  }
  return response.status===204?undefined as T:response.json();
}
const post=<T>(url:string,value:unknown)=>request<T>(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
export const api={
  list:(offset=0)=>request<{items:Build[];total:number}>(`/api/builds?offset=${offset}&limit=30`),
  capabilities:()=>request<Capabilities>('/api/capabilities'),
  build:(id:string)=>request<Build>(`/api/builds/${encodeURIComponent(id)}`),
  structure:(id:string)=>request<Structure>(`/api/builds/${encodeURIComponent(id)}/preview`),
  architecture:(id:string)=>request<Architecture>(`/api/builds/${encodeURIComponent(id)}/architecture`),
  job:(id:string)=>request<GenerationJob>(`/api/generations/${encodeURIComponent(id)}`),
  generate:(file:File|null,options:Options,references:File[]=[],jobs=true)=>{
    const form=new FormData();if(file)form.append('image',file);references.forEach(f=>form.append('references',f));form.append('options',JSON.stringify(options));
    return request<Build|GenerationJob>(jobs?'/api/generations':'/api/generate',{method:'POST',body:form});
  },
  approve:(b:Build,approved:boolean)=>post<Build>(`/api/builds/${b.id}/approval`,{approved,content_hash:b.contentHash}),
  material:(id:string,material_id:string,block:string)=>post<Build>(`/api/builds/${id}/materials`,{material_id,block,states:{}}),
  refine:(id:string,instruction:string)=>post<GenerationJob>(`/api/builds/${id}/refine`,{instruction}),
  delete:(id:string)=>request<void>(`/api/builds/${encodeURIComponent(id)}`,{method:'DELETE'})
};
