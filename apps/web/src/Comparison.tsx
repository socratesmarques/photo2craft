import {useState} from 'react';
export default function Comparison({id}:{id:string}) {
  const [overlay,setOverlay]=useState(false);
  const [opacity,setOpacity]=useState(50);
  return <section className="comparison" aria-label="Comparação da referência">
    <div className="comparison-heading"><strong>Referência × construção</strong><button className="secondary" onClick={()=>setOverlay(!overlay)}>{overlay?'Lado a lado':'Sobrepor'}</button></div>
    <div className={overlay?'comparison-images overlay':'comparison-images'}>
      <figure><img src={`/api/builds/${id}/image`} alt="Imagem original"/><figcaption>Imagem original</figcaption></figure>
      <figure style={overlay?{opacity:opacity/100}:undefined}><img src={`/api/builds/${id}/render`} alt="Render final na câmera estimada"/><figcaption>Construção · câmera estimada</figcaption></figure>
    </div>
    {overlay&&<label>Opacidade da construção<input aria-label="Opacidade da construção" type="range" min={0} max={100} value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label>}
    <small>Enquadramento aproximado. A sobreposição não faz alinhamento fotogramétrico.</small>
  </section>;
}
