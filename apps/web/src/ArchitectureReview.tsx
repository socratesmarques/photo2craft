import {useEffect,useState} from 'react';
import {api} from './api';
import type {Architecture,Build} from './types';
import catalog from '../../../shared/block-visuals.json';
const blocks=Object.entries(catalog as Record<string,{gravity:boolean;automatic?:boolean}>).filter(([id,v])=>id!=='minecraft:air'&&!v.gravity&&v.automatic!==false).map(([id])=>id);
export default function ArchitectureReview({build,onChange,onRefine,disabled}:{build:Build;onChange:(b:Build)=>void;onRefine:(instruction:string)=>void;disabled:boolean}){
  const [plan,setPlan]=useState<Architecture|null>(null),[error,setError]=useState(''),[instruction,setInstruction]=useState(''),[saving,setSaving]=useState(false);
  useEffect(()=>{let alive=true;setPlan(null);api.architecture(build.id).then(p=>{if(alive)setPlan(p);}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[build.id,build.contentHash]);
  async function change(id:string,block:string){setSaving(true);try{onChange(await api.material(build.id,id,block));setError('');}catch(e){setError((e as Error).message);}finally{setSaving(false);}}
  return <div className="generation-info">
    {error&&<p role="alert">{error}</p>}
    <details><summary>Plano arquitetônico e materiais</summary>
      {plan?.palette.map(m=><label key={m.id}>{m.id}<select aria-label={`Material ${m.id}`} value={m.block} disabled={disabled||saving} onChange={e=>change(m.id,e.target.value)}>{Array.from(new Set([m.block,...blocks])).map(b=><option key={b} value={b}>{b.replace('minecraft:','')}</option>)}</select></label>)}
      <ul>{plan?.elements.map(e=><li key={e.id}>{e.id}: {({visible:'visível',inferred:'inferido',unknown:'desconhecido'} as Record<string,string>)[e.evidence.kind]} — {e.evidence.note}</li>)}</ul>
      <small>Trocar materiais invalida a avaliação e exige nova aprovação. Cores e formas especiais no preview são aproximadas.</small>
    </details>
    {build.sourceImages.length>0&&<><label>O que deve melhorar?<textarea value={instruction} maxLength={2000} onChange={e=>setInstruction(e.target.value)} placeholder="Ex.: preservar a janela central e corrigir o telhado"/></label><button className="secondary" disabled={disabled||saving||!instruction.trim()} onClick={()=>onRefine(instruction)}>Solicitar refinamento</button><small>Cria outra versão e consome a cota gratuita disponível.</small></>}
  </div>;
}
