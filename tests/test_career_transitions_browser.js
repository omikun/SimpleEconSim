/* Run against a disposable game: advances one turn per viewport. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({ channel: 'chrome', headless: true });
 try {
  for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
   const page=await browser.newPage({viewport});
   await page.route(/\.(js|css)(\?|$)/, async route=>{const fs=require('node:fs');const name=new URL(route.request().url()).pathname.split('/').pop();const path=require('node:path').resolve(__dirname,'../web_client',name);if(fs.existsSync(path))await route.fulfill({body:fs.readFileSync(path),contentType:name.endsWith('.js')?'application/javascript':'text/css'});else await route.continue();});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.CAREER_GAME_URL || 'http://127.0.0.1:8134/');
   await page.waitForFunction(()=>Number((document.querySelector('#val-pop')?.textContent||'').replaceAll(',',''))>0);
   await page.locator('#btn-step').click();
   await page.locator('[data-tab="tab-citizens"]').click();
   await page.locator('[data-cit-sub="labor"]').click();
   const summary=page.locator('.career-transition-summary');
   await summary.waitFor({timeout:30000});
   await summary.locator('summary').click();
   const text=await summary.innerText();
   for(const label of ['Starting workers','Protected','Can leave','Left','Held back']) assert.ok(text.includes(label));
   assert.ok(!text.includes('undefined')&&!text.includes('NaN'));
   await summary.scrollIntoViewIfNeeded();
   await summary.screenshot({path:`/private/tmp/career-summary-${viewport.width}.png`});
   await page.screenshot({path:`/private/tmp/career-web-${viewport.width}.png`,fullPage:true});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);
   console.log('Career moves rendered',viewport.width);
   await page.close();
  }
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
