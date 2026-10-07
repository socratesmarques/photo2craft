import { test, expect } from '@playwright/test';

test('modo IA aceita texto sem imagem e mostra a origem do resultado (API simulada)', async ({page}) => {
  const id = 'a'.repeat(32);
  const build = {
    id, name:'Ponte de pedra', description:'Uma ponte de pedra com dois pilares.',
    size:{width:9,height:7,depth:5}, blockCount:125, solidBlockCount:125,
    thumbnail:null,sourceImages:[],status:'ready',createdAt:new Date().toISOString(),
    importCommand:`/build import ${id}`,options:{},
    generationInfo:{mode:'ai',model:'test-model',summary:'Ponte com dois pilares.',assumptions:['Face traseira inferida por simetria.']}
  };
  const blocks:{x:number;y:number;z:number;block:string;states:Record<string,string>}[]=[];
  for(let z=0;z<5;z++)for(let x=0;x<9;x++) {
    blocks.push({x,y:4,z,block:'minecraft:stone_bricks',states:{}});
    if(x<2||x>6)for(let y=0;y<4;y++)blocks.push({x,y,z,block:'minecraft:stone_bricks',states:{}});
  }
  await page.route('**/api/capabilities',route=>route.fulfill({json:{version:'0.5.0',release:'ollama-local-0.5.0',generationJobs:true,maxUploadBytes:5242880,maxBlocks:50000,maxDimension:64,maxProjects:200,aiConfigured:true,aiProvider:'ollama',aiModel:'test-model'}}));
  await page.route('**/api/generation-jobs',async route=>{
    const body=route.request().postData()||'';
    expect(body).toContain('"mode":"ai"');
    expect(body).toContain('"quality":"detailed"');
    expect(body).toContain('"size":"large"');
    expect(body).toContain('Uma ponte de pedra com dois pilares.');
    expect(body).not.toContain('name="image"');
    await route.fulfill({status:202,json:{id:'test-job',status:'queued',stage:'queued',elapsedSeconds:0}});
  });
  await page.route('**/api/generation-jobs/test-job',route=>route.fulfill({json:{id:'test-job',status:'succeeded',stage:'final',elapsedSeconds:2,buildId:id}}));
  await page.route(`**/api/builds/${id}`,route=>route.fulfill({json:build}));
  await page.route(`**/api/builds/${id}/structure`,route=>route.fulfill({json:{id,name:build.name,size:build.size,blocks}}));
  await page.goto('/');
  await expect(page.getByLabel('Qualidade')).toHaveValue('detailed');
  await page.getByText('Configurações avançadas',{exact:true}).click();
  await page.getByPlaceholder('Ex.: Refúgio da montanha').fill(build.name);
  await page.getByLabel('Instrução complementar (opcional com imagem)').fill(build.description);
  await page.getByLabel('Tipo livre',{exact:true}).fill('ponte');
  await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeEnabled();
  await expect(page.locator('.scene canvas')).toBeVisible();
  await expect(page.getByText('Ponte com dois pilares.',{exact:true})).toBeVisible();
  await page.getByText('Partes inferidas e simplificações',{exact:true}).click();
  await expect(page.getByText('Face traseira inferida por simetria.')).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/ai-mobile.png',fullPage:true});
});

test('identifica a API antiga que ainda pede chave OpenAI', async ({page}) => {
  await page.route('**/api/capabilities', route => route.fulfill({json:{
    maxUploadBytes:5242880,maxBlocks:50000,maxDimension:64,maxProjects:200,
    generationMode:'procedural',aiConfigured:false,aiModel:'gpt-4.1-mini',
    imageInterpretation:false,fullInterior:false
  }}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('API desatualizada');
  await expect(page.getByRole('alert')).toContainText('ATUALIZAR-OLLAMA.ps1');
  await page.getByLabel('Instrução complementar (opcional com imagem)').fill('Uma ponte');
  await expect(page.getByRole('button',{name:'Gerar construção',exact:true})).toBeDisabled();
});
