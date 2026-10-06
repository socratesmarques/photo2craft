import type {Build, Structure, Options, Capabilities} from './types';
async function request<T>(url:string,init?:RequestInit):Promise<T> {
  const response=await fetch(url,init);
  if(!response.ok) {
    const data=await response.json().catch(()=>({detail:'Não foi possível acessar a API.'}));
    throw new Error(typeof data.detail==='string'?data.detail:`Falha na solicitação (HTTP ${response.status}).`);
  }
  return response.status===204?undefined as T:response.json();
}
export const api={
  list:(offset=0)=>request<{items:Build[];total:number}>(`/api/builds?offset=${offset}&limit=30`),
  capabilities:()=>request<Capabilities>('/api/capabilities'),
  structure:(id:string)=>request<Structure>(`/api/builds/${encodeURIComponent(id)}/structure`),
  generate:(file:File|null,options:Options)=>{
    const form=new FormData();if(file)form.append('image',file);form.append('options',JSON.stringify(options));
    return request<Build>('/api/generate',{method:'POST',body:form});
  },
  delete:(id:string)=>request<void>(`/api/builds/${encodeURIComponent(id)}`,{method:'DELETE'})
};
