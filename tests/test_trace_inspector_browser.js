const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
  const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'tmp/trace_inspector_fixture.json'),'utf8'));
  const source=fs.readFileSync(path.join(__dirname,'web_client/client.js'),'utf8');
  const helpers=source.slice(source.indexOf('  const TRACE_PAGE_SIZE'),source.indexOf('  function openPriceTraceInspector'));
  const inspector=source.slice(source.indexOf('  function openChartTraceInspector'),source.indexOf('  function renderHistoricalChart'));
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
  const page=await browser.newPage({viewport:{width:1024,height:768},isMobile:true,hasTouch:true});
  await page.setContent('<html><head></head><body style="padding:18px"><main id="target"></main></body></html>');
  await page.addStyleTag({path:path.join(__dirname,'web_client/style.css')});
  await page.addScriptTag({path:path.join(__dirname,'web_client/ui_utils.js')});
  await page.evaluate(fixture => {
    window.fixture=fixture;
    window.fetch=async url=>{
      if (window.failTraceFetch) throw new Error('injected offline state');
      const id=new URL(url,'http://local').searchParams.get('event_id')||fixture.root;
      const row=fixture.rows[id];
      return {ok:true,json:async()=>({events:row?[row]:[],explanations:row?[fixture.explanations[id]]:[],total:row?1:0,boundary:fixture.boundary})};
    };
  },fixture);
  await page.addScriptTag({content:'const worldState={turn:3}; const escapeHtml=globalThis.CoCUIUtils.escapeHtml;'+helpers+inspector});
  await page.evaluate(()=>{const row=window.fixture.rows[window.fixture.root];openChartTraceInspector({metric:'finance.treasury',entity:'nation:'+row.subject.id,turn:row.turn,value:row.value_after,label:'Treasury',container:document.querySelector('#target')});});
  await page.getByText('Opening treasury',{exact:true}).waitFor();
  assert.equal(await page.getByText('Recorded receipts',{exact:true}).count(),1);
  assert.equal(await page.getByText('Unclassified flow residual',{exact:true}).count(),1);
  const button=page.getByRole('button',{name:/Sovereign cash/}).first();
  assert.ok((await button.boundingBox()).height>=44);
  await page.screenshot({path:path.join(__dirname,'tmp/ipad-causal-evidence.png'),fullPage:true});
  await button.click();
  await page.getByText(/public account close/).first().waitFor();
  assert.equal(await page.getByText('Verified formula',{exact:true}).count(),0);
  await page.locator('.trace-event-id').fill('missing-event');
  await page.getByRole('button',{name:'Show records'}).click();
  await page.getByText('No event with that ID was found in this run.',{exact:true}).waitFor();
  await page.evaluate(()=>{window.failTraceFetch=true;});
  await page.getByRole('button',{name:'Show records'}).click();
  await page.getByText(/Could not load metric records: injected offline state/).waitFor();
  console.log('iPad treasury values, touch targets, cause navigation, empty and error states passed');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
