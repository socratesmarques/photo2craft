import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {Box, RotateCcw} from 'lucide-react';
import type {Structure} from './types';

import catalog from '../../../shared/block-visuals.json';
const visuals=catalog as Record<string,{rgb:number[];transparent:boolean}>;
export default function Preview({structure,referenceCamera}:{structure:Structure|null;referenceCamera?:{yaw:number;pitch:number}}) {
  const host=useRef<HTMLDivElement>(null);
  const reset=useRef<()=>void>(()=>{});
  const view=useRef<(name:string)=>void>(()=>{});
  const [error,setError]=useState('');
  useEffect(()=>{
    if(!host.current||!structure)return;
    setError('');
    let renderer:THREE.WebGLRenderer;
    try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});}
    catch {setError('A prévia 3D precisa de WebGL. Você ainda pode baixar e importar a construção.');return;}
    const element=host.current;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    element.appendChild(renderer.domElement);
    const scene=new THREE.Scene();
    const camera=new THREE.PerspectiveCamera(40,1,0.1,1000);
    const controls=new OrbitControls(camera,renderer.domElement);
    controls.enableDamping=true;controls.enablePan=true;controls.maxPolarAngle=Math.PI;
    const {width:w,height:h,depth:d}=structure.size;
    const extent=Math.max(w,h,d);
    const fit=()=>{camera.position.set(extent*1.4,extent*1.05,-extent*1.7);controls.target.set(0,h*.28,0);controls.update();};
    view.current=(name)=>{
      controls.target.set(0,(h-1)/2,0);
      const distance=extent*2.4;
      const directions:Record<string,number[]>={front:[0,0,-1],back:[0,0,1],left:[-1,0,0],right:[1,0,0],top:[0,1,-.0001]};
      if(name==='reference'&&referenceCamera){
        const yaw=referenceCamera.yaw*Math.PI/180,pitch=referenceCamera.pitch*Math.PI/180;
        directions.reference=[Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),-Math.cos(yaw)*Math.cos(pitch)];
      }
      const direction=directions[name];
      if(!direction){fit();return;}
      camera.position.copy(controls.target).add(new THREE.Vector3(...direction).multiplyScalar(distance));controls.update();
    };
    reset.current=fit;fit();controls.minDistance=3;controls.maxDistance=extent*5;
    scene.add(new THREE.HemisphereLight(0xdffff1,0x536663,2.6));
    const sun=new THREE.DirectionalLight(0xffffff,3);sun.position.set(10,30,20);scene.add(sun);
    const grid=new THREE.GridHelper(extent*3,extent*3,0x53756a,0x263c36);grid.position.y=-.52;scene.add(grid);
    const groups=new Map<string,Structure['blocks']>();
    for(const b of structure.blocks)if(b.block!=='minecraft:air') {
      if(!groups.has(b.block))groups.set(b.block,[]);groups.get(b.block)!.push(b);
    }
    const geometry=new THREE.BoxGeometry(.98,.98,.98);
    const materials:THREE.Material[]=[];
    const matrix=new THREE.Matrix4();
    for(const [block,cells] of groups) {
      const material=new THREE.MeshStandardMaterial({color:new THREE.Color(...(visuals[block]?.rgb??[156,186,173]).map(c=>c/255) as [number,number,number]).convertSRGBToLinear(),roughness:.92,transparent:visuals[block]?.transparent??false,opacity:visuals[block]?.transparent ? .62 : 1});
      materials.push(material);
      const mesh=new THREE.InstancedMesh(geometry,material,cells.length);
      cells.forEach((b,i)=>{matrix.makeTranslation(b.x-(w-1)/2,b.y,b.z-(d-1)/2);mesh.setMatrixAt(i,matrix);});
      scene.add(mesh);
    }
    let frame=0;
    let disposed=false;
    const render=()=>{
      frame=0;
      const moving=controls.update();
      renderer.render(scene,camera);
      if(moving)invalidate();
    };
    const invalidate=()=>{if(!disposed&&!frame)frame=requestAnimationFrame(render);};
    controls.addEventListener('change',invalidate);
    const resize=()=>{const width=element.clientWidth,height=element.clientHeight;renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();invalidate();};
    const observer=new ResizeObserver(resize);observer.observe(element);resize();
    invalidate();
    return()=>{disposed=true;cancelAnimationFrame(frame);controls.removeEventListener('change',invalidate);observer.disconnect();controls.dispose();geometry.dispose();materials.forEach(m=>m.dispose());grid.geometry.dispose();(grid.material as THREE.Material).dispose();renderer.dispose();renderer.domElement.remove();reset.current=()=>{};view.current=()=>{};};
  },[structure,referenceCamera]);
  return <div className="preview-wrap">
    <div ref={host} className="scene" aria-label={structure?'Prévia interativa da construção em blocos':'Área de prévia da construção'}/>
    {!structure&&<div className="preview-empty"><div className="empty-icon"><Box size={42} strokeWidth={1}/></div><h3>Um novo mundo, bloco a bloco.</h3><p>Envie uma referência e escolha as opções.<br/>Sua construção aparecerá aqui.</p></div>}
    {error&&<p className="webgl-error" role="status">{error}</p>}
    {structure&&<><div className="view-buttons">{[['front','Frente'],['back','Trás'],['left','Esquerda'],['right','Direita'],['top','Topo'],['perspective','Perspectiva'],...(referenceCamera?[['reference','Referência']]:[])].map(([key,label])=><button key={key} onClick={()=>view.current(key)}>{label}</button>)}</div><button className="reset icon-button" title="Restaurar câmera" aria-label="Restaurar câmera" onClick={()=>reset.current()}><RotateCcw size={18}/></button><div className="preview-hint">Arraste para girar · Role para zoom · Botão direito para mover</div></>}
  </div>;
}
