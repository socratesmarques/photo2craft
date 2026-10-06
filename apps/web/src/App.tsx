import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import {Box,Plus,Images,Upload,Image as ImageIcon,Check,Copy,Download,Trash2,LoaderCircle,ChevronLeft,X,Layers,Maximize2,ExternalLink} from 'lucide-react';
import Comparison from './Comparison';
import {api} from './api';
import type {Build,Options,Structure,Capabilities} from './types';
const Preview=lazy(()=>import('./Preview'));
const RELEASE='ollama-local-0.5.0';

const defaults:Options={name:'',description:'',mode:'ai',quality:'detailed',subject_scope:'object',max_refinements:null,depth_estimation:true,allow_transparent:true,preserve_symmetry:true,fidelity:95,type:'automatic',size:'large',style:'minecraft',interior:'none',width:64,height:48,depth:64};
const kinds=[['automatic','Automático'],['house','Casa'],['castle','Castelo'],['building','Prédio'],['monument','Monumento'],['other','Outro']];
const styles=[['minecraft','Minecraft'],['medieval','Medieval'],['modern','Moderno'],['fantasy','Fantasia'],['cyberpunk','Cyberpunk']];
const sizes=[['small','Pequeno'],['medium','Médio'],['large','Grande'],['custom','Personalizado']];
const number=(n:number)=>n.toLocaleString('pt-BR');
export default function App(){
  const [page,setPage]=useState<'create'|'builds'>('create');
  const [options,setOptions]=useState<Options>(defaults);
  const [file,setFile]=useState<File|null>(null);
  const [imageUrl,setImageUrl]=useState('');
  const [builds,setBuilds]=useState<Build[]>([]);
  const [total,setTotal]=useState(0);
  const [selected,setSelected]=useState<Build|null>(null);
  const [structure,setStructure]=useState<Structure|null>(null);
  const [busy,setBusy]=useState(false);
  const [elapsed,setElapsed]=useState(0);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [toast,setToast]=useState('');
  const [drag,setDrag]=useState(false);
  const [cap,setCap]=useState<Capabilities|null>(null);
  const [deleteTarget,setDeleteTarget]=useState<Build|null>(null);
  const fileInput=useRef<HTMLInputElement>(null);
  const modal=useRef<HTMLDialogElement>(null);
  const requestId=useRef(0);
  async function refresh(){const r=await api.list();setBuilds(r.items);setTotal(r.total);}
  useEffect(()=>{Promise.all([refresh(),api.capabilities().then(value=>{
    setCap(value);
    if(value.release!==RELEASE)setError('API desatualizada: este site exige Photo2Craft 0.5.0 com Ollama. Execute ATUALIZAR-OLLAMA.ps1 na pasta do projeto.');
  })]).catch(()=>setError('Não foi possível conectar à API. Confira se o backend está em execução.'));},[]);
  useEffect(()=>{if(!file){setImageUrl('');return;}const url=URL.createObjectURL(file);setImageUrl(url);return()=>URL.revokeObjectURL(url);},[file]);
  useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),3500);return()=>clearTimeout(timer);},[toast]);
  useEffect(()=>{if(deleteTarget)modal.current?.showModal();else modal.current?.close();},[deleteTarget]);
  useEffect(()=>{if(!busy){setElapsed(0);return;}const start=Date.now();const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-start)/1000)),1000);return()=>clearInterval(timer);},[busy]);
  const set=(key:keyof Options,value:string|number|boolean|null)=>setOptions(o=>({...o,[key]:value}));
  const isAI=options.mode==='ai';
  const canGenerate=!!cap&&cap.release===RELEASE&&!busy&&(isAI?cap.aiConfigured&&(!!file||!!options.description.trim()):!!file);
  function changeMode(value:'ai'|'procedural'){
    setOptions(o=>({...o,mode:value,type:value==='ai'?'automatic':'house',size:value==='ai'?'large':'small'}));
  }
  function acceptFile(value:File|undefined){
    if(!value)return;
    if(!['image/jpeg','image/png','image/webp'].includes(value.type)){setError('Escolha uma imagem JPG, PNG ou WEBP.');return;}
    if(value.size>(cap?.maxUploadBytes??5242880)){setError('A imagem excede o tamanho máximo permitido.');return;}
    setFile(value);setError('');
  }
  async function open(build:Build){
    const request=++requestId.current;
    setSelected(build);setStructure(null);setLoading(true);setError('');
    try{const s=await api.structure(build.id);if(request===requestId.current)setStructure(s);}
    catch(e){if(request===requestId.current)setError((e as Error).message);}
    finally{if(request===requestId.current)setLoading(false);}
  }
  async function generate(e:React.FormEvent){
    e.preventDefault();if(!canGenerate){setError(isAI?'Configure a IA e envie uma imagem ou descreva a estrutura.':'Escolha uma imagem para testar o modelo pronto.');return;}
    setBusy(true);setError('');
    try{
      const b=await api.generate(file,{...options,name:options.name.trim()||'Minha construção'});
      await open(b);
      await refresh();setToast('Construção pronta para importar!');
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  async function copy(value:string){
    try{await navigator.clipboard.writeText(value);setToast('Comando copiado.');}
    catch{setToast('Selecione e copie o comando exibido abaixo.');}
  }
  async function remove(){
    if(!deleteTarget)return;setBusy(true);
    try{await api.delete(deleteTarget.id);if(selected?.id===deleteTarget.id){requestId.current++;setSelected(null);setStructure(null);setLoading(false);}await refresh();setDeleteTarget(null);setToast('Projeto excluído.');}
    catch(e){setError((e as Error).message);setDeleteTarget(null);}
    finally{setBusy(false);}
  }
  function fresh(){requestId.current++;setSelected(null);setStructure(null);setLoading(false);setPage('create');setError('');}
  function download(){
    if(!structure)return;const url=URL.createObjectURL(new Blob([JSON.stringify(structure,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`photo2craft-${structure.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const detail=<section className="workspace-preview" aria-label="Resultado da construção">
    <div className="panel-heading"><span><Box size={18}/> {selected?selected.name:'Prévia da construção'}</span><span className="badge">{selected?(selected.generationInfo?.mode==='ai'?'IA':'MODELO PRONTO'):'3D'}</span></div>
    <div className="preview-content"><Suspense fallback={<div className="preview-wrap loading-overlay">Carregando prévia…</div>}><Preview structure={structure} referenceCamera={selected?.generationInfo?.camera}/></Suspense>{loading&&<div className="loading-overlay"><LoaderCircle className="spin"/> Carregando construção…</div>}</div>
    {selected?.generationInfo?.renderAvailable&&<Comparison id={selected.id}/>}
    <div className="preview-footer">{selected?<><div className="stats"><span><Layers size={17}/>{number(selected.solidBlockCount)} blocos sólidos</span><span><Maximize2 size={17}/>{selected.size.width} × {selected.size.height} × {selected.size.depth}</span></div><div className="import-box"><div><small>COLE NO CHAT DO MINECRAFT</small><code>{selected.importCommand}</code></div><button className="icon-button" aria-label="Copiar comando" onClick={()=>copy(selected.importCommand)}><Copy size={18}/></button></div><div className="result-actions"><button className="secondary" disabled={!structure} onClick={download}><Download size={16}/> Baixar JSON</button><span>Java 1.21.1 · Fabric</span></div></>:<div className="preview-placeholder-footer"><span className="step-number">02</span><div><strong>Da sua ideia para o seu mundo</strong><p>Gere, confira em 3D e importe com um comando.</p></div></div>}</div>
    {selected?.generationInfo&&<div className="generation-info"><p>{selected.generationInfo.summary}</p>{selected.generationInfo.timings&&<><p>{selected.generationInfo.score?`Fidelidade estimada: ${selected.generationInfo.score.total}/100`:'Fidelidade não avaliada'} · {selected.generationInfo.timings.total}s · {selected.generationInfo.refinementsAccepted}/{selected.generationInfo.refinementsAttempted} correções aceitas</p><small>Estimativa heurística, não uma porcentagem científica.</small><ol className="stage-list">{selected.generationInfo.stagesCompleted?.map(stage=><li key={stage}>{({preprocessing:'Preparação visual',analysis:'Análise concluída',geometry:'Estrutura inicial criada',depth:'Profundidade estimada',comparison:'Comparação visual',final:'Resultado final'} as Record<string,string>)[stage]??stage.replace('refinement_','Refinamento ')}</li>)}</ol></>}{selected.generationInfo.warnings?.map((warning,i)=><p key={i} role="status">⚠ {warning}</p>)}{selected.generationInfo.referenceStudy&&<details><summary>O que a IA identificou na referência</summary><p>{selected.generationInfo.referenceStudy.subject}: {selected.generationInfo.referenceStudy.silhouette}</p><p>{selected.generationInfo.referenceStudy.material_notes}</p><ul>{selected.generationInfo.referenceStudy.landmarks.map((item,i)=><li key={i}>{item}</li>)}</ul><p>Interpretação estimada pelo modelo, não uma medição de semelhança.</p></details>}{selected.generationInfo.assumptions?.length>0&&<details><summary>Partes inferidas e simplificações</summary><ul>{selected.generationInfo.assumptions.map((item,i)=><li key={i}>{item}</li>)}</ul></details>}</div>}
  </section>;
  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={e=>{e.preventDefault();fresh();}}><div className="brand-icon"><Box size={24}/></div><span>Photo<span className="accent">2</span>Craft</span></a><div className="sidebar-label">SEU ESTÚDIO</div><nav><button className={page==='create'?'nav-item active':'nav-item'} onClick={()=>setPage('create')}><Plus size={19}/> Criar construção</button><button className={page==='builds'?'nav-item active':'nav-item'} onClick={()=>{setPage('builds');setSelected(null);setStructure(null);requestId.current++;setLoading(false);}}><Images size={19}/> Minhas construções <span className="count">{total}</span></button></nav><div className="sidebar-bottom"><span className="version">MVP 0.5.0</span><strong>Seu mundo. Suas ideias.</strong><p>Feito para Minecraft Java Edition.</p><a href="/docs" target="_blank" rel="noreferrer">Documentação da API <ExternalLink size={13}/></a></div></aside>
    <main><header className="topbar"><span>Estúdio <span className="crumb">/</span> {page==='create'?'Criar construção':'Minhas construções'}</span><span className="local-label">Espaço local</span></header>
      <div className="main-content"><div className="page-title"><div className="eyebrow">IMAGINE. GERE. CONSTRUA.</div><h1>{page==='create'?'Transforme imagens em construções do Minecraft.':'Minhas construções'}</h1><p>{page==='create'?'Uma referência, algumas escolhas e um novo lugar para explorar.':`${number(total)} ${total===1?'projeto pronto':'projetos prontos'} para fazer parte do seu mundo.`}</p></div>
      {error&&<div role="alert" className="alert"><span>{error}</span><button aria-label="Fechar aviso" onClick={()=>setError('')}><X size={17}/></button></div>}
      {page==='create'?<div className="studio-grid"><form onSubmit={generate} className="creation-form"><fieldset disabled={busy}>
        <label>Modo de geração<select value={options.mode} onChange={e=>changeMode(e.target.value as 'ai'|'procedural')}><option value="ai">IA · Imagem ou texto · Estrutura livre</option><option value="procedural">Demo local · Modelos prontos</option></select></label>
        {isAI&&!cap?.aiConfigured&&<div className="ai-setup" role="status"><strong>Ative a IA local</strong><p>Configure o Ollama e o modelo Gemma 4 no backend. Enquanto isso, o modo demo continua disponível.</p></div>}
        <div className="section-title"><span className="step-number">01</span><h2>Sua referência</h2><span className="required">{isAI?'Opcional':'Obrigatória'}</span></div>
        <input ref={fileInput} id="image-upload" type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={e=>{acceptFile(e.target.files?.[0]);e.target.value='';}}/>
        <button type="button" className={`upload-zone ${drag?'dragging':''} ${file?'with-image':''}`} onClick={()=>fileInput.current?.click()} onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);acceptFile(e.dataTransfer.files[0]);}}>
          {imageUrl?<><img src={imageUrl} alt="Sua referência para a construção"/><span className="replace-image"><ImageIcon size={16}/>{file?.name} · Trocar</span></>:<><div className="upload-icon"><Upload size={23}/></div><strong>Solte sua ideia aqui</strong><span>ou clique para escolher uma imagem</span><small>JPG, PNG ou WEBP · Até {Math.round((cap?.maxUploadBytes??5242880)/1048576)} MB</small></>}
        </button>
        {file&&<button className="secondary remove-reference" type="button" onClick={()=>setFile(null)}>Remover imagem</button>}
        <label>Nome da construção<input maxLength={100} placeholder="Ex.: Refúgio da montanha" value={options.name} onChange={e=>set('name',e.target.value)}/></label>
        <label>Instrução complementar (opcional com imagem)<textarea maxLength={2000} rows={4} placeholder="Uma ponte medieval com três arcos, pilares de pedra e passagem de madeira…" value={options.description} onChange={e=>set('description',e.target.value)}/><span className="field-note">{isAI?'A imagem tem prioridade. Ex.: “Construa somente a igreja; ignore árvores e carros”. Sem imagem, descreva o objeto.':'Na demo, este texto é salvo como referência; o resultado usa um modelo pronto.'}</span></label>
        {isAI&&<label>Qualidade<select value={options.quality} onChange={e=>set('quality',e.target.value)}><option value="quick">Rápido · sem refinamento visual</option><option value="detailed">Detalhado · até 2 correções visuais</option><option value="ultra">Ultra · até 3 correções visuais</option></select><span className="field-note">{options.quality==='ultra'?'Ultra demora mais e pode usar profundidade local opcional.':'Com imagem, o modo Detalhado compara o render com a referência.'} Sem imagem, o planejamento usa apenas o texto.</span></label>}
        <details className="advanced"><summary>Configurações avançadas</summary><div className="section-divider"/>
        <div className="section-title"><h2>Do seu jeito</h2></div>
        <div className="two-columns"><label>{isAI?'Tipo livre':'Modelo'}{isAI?<><input maxLength={120} aria-label="Tipo livre" placeholder="Ponte, navio, estátua…" value={options.type==='automatic'?'':options.type} onChange={e=>set('type',e.target.value||'automatic')}/><span className="field-note">Vazio: inferir da referência.</span></>:<select value={options.type} onChange={e=>set('type',e.target.value)}>{kinds.filter(([value])=>!['automatic','other'].includes(value)).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>}</label><label>Tamanho<select value={options.size} onChange={e=>set('size',e.target.value)}>{sizes.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label></div>
        {options.size==='custom'&&<div className="dimensions">{(['width','height','depth'] as const).map((key,i)=><label key={key}>{['Largura','Altura','Profundidade'][i]}<input type="number" min={9} max={Math.min(64,cap?.maxDimension??64)} required value={options[key]} onChange={e=>set(key,Number(e.target.value))}/></label>)}</div>}
        <label>Estilo</label><div className="style-options" role="group" aria-label="Estilo da construção">{styles.map(([value,label])=><button key={value} type="button" aria-pressed={options.style===value} className={options.style===value?'selected':''} onClick={()=>set('style',value)}>{label}</button>)}</div>
        <label>Interior<select value={options.interior} onChange={e=>set('interior',e.target.value)}><option value="none">Sem interior</option><option value="simple">Interior simples</option><option disabled value="complete">Interior completo · Em breve</option></select></label>
        {isAI&&<><label>Construir<select value={options.subject_scope} onChange={e=>set('subject_scope',e.target.value)}><option value="object">Objeto principal</option><option value="scene">Cena completa</option></select></label><label>Máximo de refinamentos<select value={options.max_refinements??'auto'} onChange={e=>set('max_refinements',e.target.value==='auto'?null:Number(e.target.value))}><option value="auto">Padrão da qualidade</option>{[0,1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select></label><label><input type="checkbox" checked={options.depth_estimation} onChange={e=>set('depth_estimation',e.target.checked)}/> Profundidade opcional no Ultra</label><label><input type="checkbox" checked={options.allow_transparent} onChange={e=>set('allow_transparent',e.target.checked)}/> Permitir vidro</label><label><input type="checkbox" checked={options.preserve_symmetry} onChange={e=>set('preserve_symmetry',e.target.checked)}/> Preservar simetria quando observada</label><p className="field-note">Imagem sempre prioritária. Pequeno/Médio/Grande: limites de 32/48/64 por eixo, preservando proporções. Atualize o mod para 0.3.0 antes de importar a nova paleta.</p></>}
        </details>
        <div className="mvp-note"><Box size={17}/><p>{isAI?`IA local com ${cap?.aiModel||'Gemma 4'} via Ollama: sem chave e sem cobrança por geração. A construção será uma aproximação em blocos; partes invisíveis serão inferidas.`:'Demo gratuita de modelos prontos. Para gerar outros tipos de estrutura e interpretar referências, selecione o modo IA.'}</p></div>
        <button type="submit" className="primary generate" disabled={!canGenerate}>{busy?<LoaderCircle size={19} className="spin"/>:<Box size={19}/>} {busy?(isAI?'IA planejando a estrutura…':'Gerando construção…'):'Gerar construção'}</button>
        {busy&&<p role="status" className="field-note">Aguardando o gerador · {Math.floor(elapsed/60)}min {elapsed%60}s. {isAI&&options.quality!=='quick'?'Análise, render e correções são processados em sequência.':''} Este contador mostra o tempo decorrido, não o progresso. Não clique novamente.</p>}
      </fieldset></form>{detail}</div>:selected?<><button className="back secondary" onClick={()=>{requestId.current++;setSelected(null);setStructure(null);setLoading(false);}}><ChevronLeft size={17}/> Voltar às construções</button><div className="detail-layout">{detail}<div className="detail-info"><h2>{selected.name}</h2>{selected.thumbnail&&<img src={selected.thumbnail} alt="Referência original"/>}<p>{selected.description||'Sem descrição.'}</p><p className="muted">{new Date(selected.createdAt).toLocaleString('pt-BR')}</p><label>ID do projeto<code className="project-id">{selected.id}</code></label></div></div></>:builds.length?<><div className="project-grid">{builds.map(b=><article className="project-card" key={b.id}><button className="card-image" onClick={()=>open(b)} aria-label={`Visualizar ${b.name}`}>{b.thumbnail?<img src={b.thumbnail} alt={`Referência de ${b.name}`}/>:<Box size={50}/>}<span className="card-badge"><Check size={12}/> Pronta</span></button><div className="card-body"><h2>{b.name}</h2><p>{number(b.solidBlockCount)} blocos · {b.size.width} × {b.size.height} × {b.size.depth}</p><small>{new Date(b.createdAt).toLocaleDateString('pt-BR')}</small><code className="card-command">{b.importCommand}</code><div className="card-actions"><button className="secondary" onClick={()=>open(b)}>Visualizar</button><button className="icon-button" aria-label={`Copiar comando de ${b.name}`} onClick={()=>copy(b.importCommand)}><Copy size={17}/></button><button className="icon-button danger" aria-label={`Excluir ${b.name}`} onClick={()=>setDeleteTarget(b)}><Trash2 size={17}/></button></div></div></article>)}</div>{builds.length<total&&<button className="secondary load-more" disabled={loading} onClick={async()=>{setLoading(true);try{const r=await api.list(builds.length);setBuilds(b=>[...b,...r.items]);}catch(e){setError((e as Error).message);}finally{setLoading(false);}}}>{loading?'Carregando…':'Carregar mais'}</button>}</>:<div className="collection-empty"><Images size={44}/><h2>Seu mundo começa com uma ideia.</h2><p>Suas construções ficarão guardadas aqui.</p><button className="primary" onClick={fresh}><Plus size={18}/> Criar primeira construção</button></div>}
      </div><footer className="main-footer"><span>Photo2Craft 0.5.0 · Ollama</span><span>Uma ideia de cada vez. Um bloco de cada vez.</span></footer>
    </main>
    {toast&&<div className="toast" role="status"><Check size={18}/>{toast}</div>}
    <dialog ref={modal} onCancel={()=>setDeleteTarget(null)}><h2>Excluir esta construção?</h2><p>“{deleteTarget?.name}” e sua imagem serão removidas. Os blocos já colocados no Minecraft permanecem.</p><div className="dialog-actions"><button className="secondary" disabled={busy} onClick={()=>setDeleteTarget(null)}>Cancelar</button><button className="delete-button" disabled={busy} onClick={remove}>{busy?'Excluindo…':'Excluir projeto'}</button></div></dialog>
  </div>;
}
