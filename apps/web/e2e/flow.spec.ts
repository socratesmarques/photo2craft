import { test, expect } from '@playwright/test';
import path from 'node:path';
test('imagem → geração → JSON → galeria → exclusão, desktop e celular',async({page,request})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  let id='';
  try {
    await page.goto('/');
    await expect(page.getByText('Ative a IA local', {exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Gerar construção',exact:true})).toBeDisabled();
    await page.getByLabel('Modo de geração').selectOption('procedural');
    await page.locator('input[type=file]').setInputFiles(path.resolve('e2e/reference.png'));
    await page.getByPlaceholder('Ex.: Refúgio da montanha').fill('Casa de teste E2E');
    await page.getByRole('button',{name:'Gerar construção',exact:true}).click();
    await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeEnabled();
    await expect(page.locator('.scene canvas')).toBeVisible();
    const command=await page.locator('.import-box code').innerText();
    expect(command).toMatch(/^\/build import [0-9a-f]{32}$/);
    id=command.split(' ')[2];
    const response=await request.get('/api/builds/'+id+'/structure');
    const structure=await response.json();
    expect(structure.id).toBe(id);expect(structure.blocks).toHaveLength(1573);
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:'test-results/desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:'test-results/mobile.png',fullPage:true});
    await page.getByRole('button',{name:/Minhas construções/}).click();
    await page.getByRole('button',{name:'Visualizar Casa de teste E2E',exact:true}).first().click();
    await expect(page.getByRole('button',{name:'Baixar JSON',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Voltar às construções'}).click();
    await page.getByRole('button',{name:'Excluir Casa de teste E2E',exact:true}).first().click();
    await page.getByRole('button',{name:'Excluir projeto',exact:true}).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
    expect((await request.get('/api/builds/'+id)).status()).toBe(404);
    expect(errors).toEqual([]);
  } finally {if(id) await request.delete('/api/builds/'+id);}
});
