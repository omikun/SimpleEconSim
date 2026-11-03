/* Disposable game only: creates a bounded order and advances the simulation. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  for(const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
   const page=await browser.newPage({viewport});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   page.on('response',async response=>{if(response.url().endsWith('/api/command'))console.log('Command response',await response.text());});
   await page.route(/\.(js|css)(\?|$)/,async route=>{
    const fs=require('node:fs'),path=require('node:path');
    const target=path.resolve(__dirname,'../web_client',new URL(route.request().url()).pathname.split('/').pop());
    if(fs.existsSync(target))await route.fulfill({body:fs.readFileSync(target),contentType:target.endsWith('.js')?'application/javascript':'text/css'});
    else await route.continue();
   });
   await page.goto(process.env.FOOD_ECONOMY_GAME_URL||'http://127.0.0.1:8136/');
   await page.waitForFunction(()=>Number((document.querySelector('#val-pop')?.textContent||'').replaceAll(',',''))>0);
   await page.locator('[data-tab="tab-citizens"]').click();
   await page.locator('[data-cit-sub="labor"]').click();
   const panel=page.locator('#food-economy-panel');await panel.waitFor();
   await panel.locator('summary').click();
   const text=await panel.innerText();
   for(const phrase of ['Food support','primary farmers','other residents need','ordinary meals need','Economic needs','Unspent funds return'])assert.ok(text.includes(phrase),phrase);
   const form=panel.locator('form');
   await form.locator('[name="quantity"]').fill('7');
   await page.locator('#btn-step').click();
   await page.waitForTimeout(1200);
   assert.equal(await form.locator('[name="quantity"]').inputValue(),'7','draft survives state updates');
   await form.locator('[name="quantity"]').fill('1');
   await form.locator('[name="budget"]').fill('5');
   await form.locator('[name="duration"]').fill('1');
   await form.locator('[name="good"]').selectOption('wood');
   await form.locator('button[type="submit"]').click();
   await page.waitForFunction(()=>document.querySelector('.production-program-history')?.textContent.includes('active'),null,{timeout:10000}).catch(async e=>{await page.screenshot({path:'/private/tmp/food-browser-failure.png',fullPage:true});console.log(await page.locator('body').innerText());throw e;});
   await page.locator('#btn-step').click();
   await page.waitForFunction(()=>/completed|expired/.test(document.querySelector('.production-program-history > div:last-child')?.textContent||''));
   assert.ok(!/NaN|undefined/.test(await panel.innerText()));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await panel.locator('.food-support-metrics').scrollIntoViewIfNeeded();
   await page.screenshot({path:`/private/tmp/food-economy-support-${viewport.width}.png`});
   await form.locator('button[type="submit"]').scrollIntoViewIfNeeded();
   await page.screenshot({path:`/private/tmp/food-economy-form-${viewport.width}.png`});
   assert.deepEqual(errors,[]);console.log('Food economy and funded order passed',viewport.width);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
