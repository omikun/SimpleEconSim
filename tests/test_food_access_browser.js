/* Run against a disposable standard game; this test never advances its turn. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(process.env.FOOD_ACCESS_GAME_URL || 'http://127.0.0.1:8131/');
      await page.waitForFunction(() => Number((document.querySelector('#val-pop')?.textContent || '').replaceAll(',', '')) > 0);
      await page.keyboard.press('c');
      const summary = page.locator('.food-access-summary').first();
      await summary.waitFor();
      await summary.locator('summary').click();
      const text = await summary.innerText();
      for (const phrase of ['underfed', 'food supplied', 'Company stocks', 'Granary',
                            'cannot afford meals', 'Adult meal', 'public food units delivered']) {
        assert.ok(text.includes(phrase), `Missing food access explanation: ${phrase}`);
      }
      assert.ok(!text.includes('NaN') && !text.includes('undefined'));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const state = await (await page.request.get(new URL('/api/state', page.url()).href)).json();
      assert.ok(state.nations.some(n => n.food_security && n.food_security.meal_need_units > 0));
      await page.screenshot({ path: `/private/tmp/food-access-web-${viewport.width}.png`, fullPage: true });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Food access: desktop and mobile rendering passed.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
