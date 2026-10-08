import {test,expect} from '@playwright/test';
import path from 'node:path';

test('job persistido, múltiplas vistas e aprovação com hash (Gemini simulado)',async({page})=>{
  const id='architectural-test',hash='a'.repeat(64);
  const build={id,contentHash:hash,architectureAvailable:true,name:'Casa 2.0',description:'',createdAt:new Date().toISOString(),size:{width:2,height:2,depth:2},blockCount:8,solidBlockCount:8,status:'pending',importCommand:`/build import ${id}`,thumbnail:null,sourceImages:[{view:'reference',url:`/api/builds/${id}/image`}],options:{},generationInfo:{provider:'gemini',model:'gemini-3.8-flash',mode:'ai',summary:'Casa para revisão',assumptions:['Traseira desconhecida']}};
  const blocks=[];for(let y=0;y<2;y++)for(let x=0;x<2;x++)for(let z=0;z<2;z++)blocks.push({x,y,z,block:'minecraft:white_concrete',states:{}});
  await page.route('**/api/capabilities',r=>r.fulfill({json:{release:'architectural-2.0',generationJobs:true,architecturalPipeline:true,aiConfigured:true,aiProvider:'gemini',aiModel:'gemini-3.8-flash',maxUploadBytes:5242880,maxRequestBytes:8388608,maxDimension:64}}));
  await page.route('**/api/generations',r=>{
    const data=r.request().postData()??'';
    expect(data).toContain('name="references"');expect(data).toContain('name="image"');
    return r.fulfill({status:202,json:{id:'job-test',status:'queued',stage:'received',events:[]}});
  });
  let polls=0;
  await page.route('**/api/generations/job-test',r=>r.fulfill({json:++polls<2?{id:'job-test',status:'running',stage:'architectural_plan',events:[]}:{id:'job-test',status:'ready',stage:'ready_for_review',buildId:id,events:[]}}));
  await page.route(`**/api/builds/${id}`,r=>r.fulfill({json:build}));
  await page.route(`**/api/builds/${id}/preview`,r=>r.fulfill({json:{id,name:build.name,size:build.size,blocks}}));
  await page.route(`**/api/builds/${id}/architecture`,r=>r.fulfill({json:{schema_version:'2.0',palette:[{id:'wall',block:'minecraft:white_concrete',states:{}}],elements:[]}}));
  await page.route(`**/api/builds/${id}/approval`,async r=>{const data=r.request().postDataJSON();expect(data.content_hash).toBe(hash);build.status=data.approved?'ready':'rejected';await r.fulfill({json:build});});
  await page.goto('/');
  await page.locator('#image-upload').setInputFiles(path.resolve('e2e/reference.png'));
  await page.getByLabel('Outras referências').setInputFiles(path.resolve('e2e/reference.png'));
  await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>localStorage.getItem('photo2craft-generation'))).toBe('job-test');
  await page.reload();
  await expect(page.getByRole('button',{name:'Aprovar para Minecraft'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeDisabled();
  await expect(page.locator('.scene canvas')).toBeVisible();
  await page.getByRole('button',{name:'Aprovar para Minecraft'}).click();
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeEnabled();
  await expect(page.locator('.import-box code')).toHaveText(`/build import ${id}`);
  await page.getByRole('button',{name:'Rejeitar',exact:true}).click();
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeDisabled();
  await expect(page.locator('.import-box code')).toHaveText('Construção rejeitada');
});

test('cota gratuita esgotada aparece como erro sem resultado falso',async({page})=>{
  await page.route('**/api/capabilities',r=>r.fulfill({json:{release:'architectural-2.0',generationJobs:true,aiConfigured:true,aiProvider:'gemini',aiModel:'gemini-3.8-flash',maxUploadBytes:5242880,maxDimension:64}}));
  await page.route('**/api/generations',r=>r.fulfill({status:202,json:{id:'quota',status:'queued',stage:'received',events:[]}}));
  await page.route('**/api/generations/quota',r=>r.fulfill({json:{id:'quota',status:'failed',stage:'visual_analysis',events:[],error:'Cota gratuita esgotada; chamadas suspensas.'}}));
  await page.goto('/');
  await page.getByLabel('Instrução complementar (opcional com imagem)').fill('Casa moderna');
  await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Cota gratuita esgotada');
  await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toHaveCount(0);
});
