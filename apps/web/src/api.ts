import type {Build, Structure, Options, Capabilities, GenerationJob} from './types';
export class ApiError extends Error {
  constructor(message:string,public status:number){super(message);}
}
async function request<T>(url:string,init?:RequestInit):Promise<T> {
  let response:Response;
  try {
    const timeout=AbortSignal.timeout(30000);
    response=await fetch(url,{...init,signal:init?.signal?AbortSignal.any([init.signal,timeout]):timeout});
  } catch(error) {
    if(init?.signal?.aborted)throw error;
    throw new ApiError('Conexão com a API interrompida. A geração pode continuar no servidor; retome o acompanhamento.',0);
  }
  if(!response.ok) {
    const data=await response.json().catch(()=>({detail:`A API ou o proxy retornou HTTP ${response.status}. Confira os serviços e retome o acompanhamento.`}));
    throw new ApiError(typeof data.detail==='string'?data.detail:`Falha na solicitação (HTTP ${response.status}).`,response.status);
  }
  return response.status===204?undefined as T:response.json();
}
export const api={
  list:(offset=0)=>request<{items:Build[];total:number}>(`/api/builds?offset=${offset}&limit=30`),
  capabilities:()=>request<Capabilities>('/api/capabilities'),
  structure:(id:string)=>request<Structure>(`/api/builds/${encodeURIComponent(id)}/structure`),
  build:(id:string)=>request<Build>(`/api/builds/${encodeURIComponent(id)}`),
  job:(id:string,signal?:AbortSignal)=>request<GenerationJob>(`/api/generation-jobs/${encodeURIComponent(id)}`,{signal,cache:'no-store'}),
  generate:(file:File|null,options:Options)=>{
    const form=new FormData();if(file)form.append('image',file);form.append('options',JSON.stringify(options));
    return request<GenerationJob>('/api/generation-jobs',{method:'POST',body:form});
  },
  delete:(id:string)=>request<void>(`/api/builds/${encodeURIComponent(id)}`,{method:'DELETE'})
};
