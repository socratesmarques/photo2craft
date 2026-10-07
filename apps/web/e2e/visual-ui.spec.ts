import {test,expect} from '@playwright/test';
import path from 'node:path';
test('comparação, score, correções e vistas de câmera (API simulada)',async({page})=>{
  await page.addInitScript(()=>{
    const original=window.requestAnimationFrame.bind(window);
    (window as Window & {previewFrames?:number}).previewFrames=0;
    window.requestAnimationFrame=callback=>original(time=>{
      const tracked=window as Window & {previewFrames:number};
      tracked.previewFrames++;callback(time);
    });
  });
  const id='visual-result';
  const build={id,name:'Torre',description:'',createdAt:new Date().toISOString(),size:{width:2,height:4,depth:2},blockCount:16,solidBlockCount:16,status:'ready',importCommand:`/build import ${id}`,thumbnail:null,sourceImages:[],options:{},generationInfo:{mode:'ai',quality:'detailed',summary:'Torre refinada',assumptions:[],renderAvailable:true,score:{total:82,label:'Estimativa'},timings:{total:15},refinementsAttempted:2,refinementsAccepted:1,stagesCompleted:['analysis','geometry','comparison','refinement_1','final'],camera:{yaw:0,pitch:0}}};
  const blocks=[];for(let y=0;y<4;y++)for(let x=0;x<2;x++)for(let z=0;z<2;z++)blocks.push({x,y,z,block:'minecraft:red_terracotta',states:{}});
  await page.route('**/api/capabilities',route=>route.fulfill({json:{release:'ollama-local-0.5.0',generationJobs:true,aiConfigured:true,aiModel:'test-model',maxDimension:64,maxUploadBytes:5242880}}));
  await page.route('**/api/generation-jobs',route=>route.fulfill({status:202,json:{id:'test-job',status:'queued',stage:'queued',elapsedSeconds:0}}));
  await page.route('**/api/generation-jobs/test-job',route=>route.fulfill({json:{id:'test-job',status:'succeeded',stage:'final',elapsedSeconds:2,buildId:id}}));
  await page.route(`**/api/builds/${id}`,route=>route.fulfill({json:build}));
  await page.route(`**/api/builds/${id}/structure`,route=>route.fulfill({json:{id,name:'Torre',size:build.size,blocks}}));
  await page.route(`**/api/builds/${id}/image`,route=>route.fulfill({path:path.resolve('e2e/reference.png'),contentType:'image/png'}));
  await page.route(`**/api/builds/${id}/render`,route=>route.fulfill({path:path.resolve('e2e/reference.png'),contentType:'image/png'}));
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles(path.resolve('e2e/reference.png'));
  await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
  await expect(page.getByText(/Fidelidade estimada: 82/)).toBeVisible();
  await expect(page.getByAltText('Render final na câmera estimada')).toBeVisible();
  await page.getByRole('button',{name:'Sobrepor',exact:true}).click();
  await page.getByLabel('Opacidade da construção').fill('35');
  await expect(page.getByLabel('Opacidade da construção')).toHaveValue('35');
  for(const name of ['Frente','Trás','Esquerda','Direita','Topo','Perspectiva','Referência'])await page.getByRole('button',{name,exact:true}).click();
  // Damping must settle: an idle preview should not keep requesting GPU frames.
  await expect.poll(async()=>{
    const before=await page.evaluate(()=>(window as Window & {previewFrames:number}).previewFrames);
    await page.waitForTimeout(120);
    const after=await page.evaluate(()=>(window as Window & {previewFrames:number}).previewFrames);
    return after-before;
  }).toBe(0);
  const before=await page.evaluate(()=>(window as Window & {previewFrames:number}).previewFrames);
  await page.getByRole('button',{name:'Topo',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>(window as Window & {previewFrames:number}).previewFrames)).toBeGreaterThan(before);
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
