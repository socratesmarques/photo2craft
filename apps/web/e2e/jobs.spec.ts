import {test,expect} from '@playwright/test';

const id='persisted-job';
const build={id,name:'Ponte persistida',description:'',size:{width:1,height:1,depth:1},blockCount:1,solidBlockCount:1,status:'ready',createdAt:new Date().toISOString(),thumbnail:null,sourceImages:[],options:{},importCommand:`/build import ${id}`,generationInfo:{mode:'ai',summary:'Estrutura preservada.',assumptions:[]}};

test('retoma após recarregar sem enviar uma segunda geração',async({page})=>{
  let submissions=0,ready=false,temporaryFailure=true;
  await page.route('**/api/capabilities',route=>route.fulfill({json:{release:'ollama-local-0.5.0',generationJobs:true,aiConfigured:true,aiModel:'test-model'}}));
  await page.route('**/api/generation-jobs',route=>{submissions++;return route.fulfill({status:202,json:{id,status:'queued',stage:'queued',elapsedSeconds:0}});});
  await page.route(`**/api/generation-jobs/${id}`,route=>{
    if(ready&&temporaryFailure){temporaryFailure=false;return route.fulfill({status:502,contentType:'text/html',body:'<html>Proxy restarting</html>'});}
    return route.fulfill({json:{id,status:ready?'succeeded':'running',stage:'visual.geometry.receiving',elapsedSeconds:700,buildId:ready?id:null}});
  });
  await page.route(`**/api/builds/${id}`,route=>route.fulfill({json:build}));
  await page.route(`**/api/builds/${id}/structure`,route=>route.fulfill({json:{id,name:build.name,size:build.size,blocks:[{x:0,y:0,z:0,block:'minecraft:stone',states:{}}]}}));
  await page.goto('/');
  await page.getByLabel('Instrução complementar (opcional com imagem)').fill('Uma ponte');
  await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
  await expect(page.getByText(/Criando plano da estrutura · recebendo resposta da IA/)).toBeVisible();
  expect(await page.evaluate(()=>localStorage.getItem('photo2craft.activeGeneration'))).toBe(id);
  ready=true;
  await page.reload();
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeEnabled();
  expect(submissions).toBe(1);
  expect(await page.evaluate(()=>localStorage.getItem('photo2craft.activeGeneration'))).toBeNull();
});

test('mostra erro persistido do Ollama e permite corrigir e tentar novamente',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('photo2craft.activeGeneration','failed-job'));
  await page.route('**/api/capabilities',route=>route.fulfill({json:{release:'ollama-local-0.5.0',generationJobs:true,aiConfigured:true,aiModel:'test-model'}}));
  await page.route('**/api/generation-jobs/failed-job',route=>route.fulfill({json:{id:'failed-job',status:'failed',stage:'visual.analysis',elapsedSeconds:900,buildId:null,errorCode:504,error:'O modelo excedeu o tempo na etapa visual.analysis.'}}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('visual.analysis');
  await page.getByLabel('Instrução complementar (opcional com imagem)').fill('Uma torre simples');
  await expect(page.getByRole('button',{name:'Gerar construção',exact:true})).toBeEnabled();
  expect(await page.evaluate(()=>localStorage.getItem('photo2craft.activeGeneration'))).toBeNull();
});
