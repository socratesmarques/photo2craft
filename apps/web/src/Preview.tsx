import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {Box, RotateCcw} from 'lucide-react';
import type {Structure} from './types';

const colors:Record<string,number>={stone_bricks:0x8a9394,cobblestone:0x657576,oak_planks:0xc39c62,spruce_planks:0x67472e,glass:0x91cacc,white_concrete:0xe4e5df,gray_concrete:0x566267,cyan_concrete:0x24afb0,black_concrete:0x232a32,polished_andesite:0x8e9296,bricks:0xa66150,quartz_block:0xf0eada,sea_lantern:0xb6fce2,purple_concrete:0x8764b5,mossy_stone_bricks:0x648276,oak_log:0x7e603a,spruce_stairs:0x67472e};
Object.assign(colors,{orange_concrete:0xe06101,magenta_concrete:0xa9309f,light_blue_concrete:0x2389c6,yellow_concrete:0xf1af15,lime_concrete:0x5ea818,pink_concrete:0xd5658e,light_gray_concrete:0x7d7d73,blue_concrete:0x2c2e8f,brown_concrete:0x603b1f,green_concrete:0x495b24,red_concrete:0x8e2020});
export default function Preview({structure}:{structure:Structure|null}) {
  const host=useRef<HTMLDivElement>(null);
  const reset=useRef<()=>void>(()=>{});
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
    controls.enableDamping=true;controls.maxPolarAngle=Math.PI*.49;
    const {width:w,height:h,depth:d}=structure.size;
    const extent=Math.max(w,h,d);
    const fit=()=>{camera.position.set(extent*1.4,extent*1.05,-extent*1.7);controls.target.set(0,h*.28,0);controls.update();};
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
      const material=new THREE.MeshStandardMaterial({color:colors[block.replace('minecraft:','')]??0x9cbaad,roughness:.92,transparent:block==='minecraft:glass',opacity:block==='minecraft:glass'?.62:1});
      materials.push(material);
      const mesh=new THREE.InstancedMesh(geometry,material,cells.length);
      cells.forEach((b,i)=>{matrix.makeTranslation(b.x-(w-1)/2,b.y,b.z-(d-1)/2);mesh.setMatrixAt(i,matrix);});
      scene.add(mesh);
    }
    const resize=()=>{const width=element.clientWidth,height=element.clientHeight;renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();};
    const observer=new ResizeObserver(resize);observer.observe(element);resize();
    let frame=0;
    const render=()=>{frame=requestAnimationFrame(render);controls.update();renderer.render(scene,camera);};render();
    return()=>{cancelAnimationFrame(frame);observer.disconnect();controls.dispose();geometry.dispose();materials.forEach(m=>m.dispose());grid.geometry.dispose();(grid.material as THREE.Material).dispose();renderer.dispose();renderer.domElement.remove();reset.current=()=>{};};
  },[structure]);
  return <div className="preview-wrap">
    <div ref={host} className="scene" aria-label={structure?'Prévia interativa da construção em blocos':'Área de prévia da construção'}/>
    {!structure&&<div className="preview-empty"><div className="empty-icon"><Box size={42} strokeWidth={1}/></div><h3>Um novo mundo, bloco a bloco.</h3><p>Envie uma referência e escolha as opções.<br/>Sua construção aparecerá aqui.</p></div>}
    {error&&<p className="webgl-error" role="status">{error}</p>}
    {structure&&<><button className="reset icon-button" title="Restaurar câmera" aria-label="Restaurar câmera" onClick={()=>reset.current()}><RotateCcw size={18}/></button><div className="preview-hint">Arraste para girar · Role para aproximar</div></>}
  </div>;
}
