/* Integration check against disposable standard game (8111) and techsim (8110). */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.ENGINEERING_GAME_URL || 'http://127.0.0.1:8111/');
    await page.locator('[data-drawer="science"]').first().click();
    const card = page.locator('#science-tech-list .item-card').first();
    await card.locator('summary').click();
    await card.locator('.eng-objective').selectOption('performance');
    await card.locator('.eng-budget').fill('25');
    const stateUrl = new URL('/api/state', page.url()).href;
    const before = await (await page.request.get(stateUrl)).json();
    const previewResponse = page.waitForResponse(response => response.url().endsWith('/api/command') && response.request().postDataJSON()?.payload?.action === 'preview_engineering');
    await card.locator('.eng-preview').click();
    const preview = await (await previewResponse).json();
    assert.equal(preview.success, true, JSON.stringify(preview));
    assert.ok(preview.engineering.forecast);
    const after = await (await page.request.get(stateUrl)).json();
    assert.equal(after.macro.treasury_cash, before.macro.treasury_cash);
    assert.deepEqual(after.science_tree.map(t => t.refinement_xp), before.science_tree.map(t => t.refinement_xp));

    const applyResponse = page.waitForResponse(response => response.url().endsWith('/api/command') && response.request().postDataJSON()?.payload?.action === 'set_engineering');
    await card.locator('.eng-apply').click();
    const applied = await (await applyResponse).json();
    assert.equal(applied.success, true);
    assert.equal(applied.engineering.program.budget, 25);
    assert.equal(applied.engineering.program.objective, 'performance');
    await page.waitForFunction(() => !document.querySelector('#science-tech-list .eng-stop').disabled);
    await page.screenshot({ path: '/private/tmp/engineering-web-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await card.locator('.eng-apply').scrollIntoViewIfNeeded();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.ok(await card.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
    assert.ok(await card.locator('.eng-apply').evaluate(el => {
      const r = el.getBoundingClientRect();
      return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
    }));
    await page.screenshot({ path: '/private/tmp/engineering-web-mobile.png', fullPage: true });
    await card.locator('.eng-stop').click();
    assert.deepEqual(errors, []);

    // Rendering fixture: show an actual decision's shape on a known-design card.
    // Economic behavior itself is covered by the live campaign and Python tests.
    const commercial = await browser.newPage({ viewport: { width: 390, height: 844 } });
    commercial.on('pageerror', error => errors.push(error.message));
    const fixtureState = await (await page.request.get(stateUrl + '?compact=1')).json();
    const fixtureTech = fixtureState.science_tree.find(t => t.era === 1);
    fixtureTech.status = 'MASTERED';
    fixtureTech.productivity_effects = fixtureState.science_tree.find(t => t.id === 'steam_engines').productivity_effects;
    assert.equal(fixtureTech.productivity_effects.length, 18);
    fixtureTech.engineering.commercial_decisions = [{
      firm: 'Republic Furniture Works', turn: 11, installed_generation: 1,
      reason_text: 'Investment approved', cost: 800, expected_gain_per_turn: 92.18,
      payback_turns: 8.68, project_status: null, constraint: ''
    }];
    await commercial.route('**/api/state*', async route => {
      await route.fulfill({ json: fixtureState });
    });
    await commercial.goto(page.url());
    await commercial.locator('[data-drawer="science"]').first().click();
    const commercialCard = commercial.locator('#science-tech-list .item-card').first();
    await commercialCard.locator('summary').click();
    await commercialCard.getByText('Republic Furniture Works', { exact: true }).scrollIntoViewIfNeeded();
    assert.match(await commercialCard.innerText(), /Installed tier 1/);
    assert.match(await commercialCard.innerText(), /Turn 11: Investment approved/);
    assert.match(await commercialCard.innerText(), /800 investment/);
    assert.match(await commercialCard.innerText(), /Installed equipment helps: food/);
    assert.match(await commercialCard.innerText(), /wood \+50%/);
    assert.ok(await commercialCard.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
    await commercial.screenshot({ path: '/private/tmp/engineering-commercial-decisions-mobile.png', fullPage: true });
    await commercial.close();

    const simulator = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
    simulator.on('pageerror', error => errors.push(error.message));
    await simulator.goto(process.env.ENGINEERING_SIM_URL || 'http://127.0.0.1:8110/');
    await simulator.evaluate(() => {
      state.discoveryProgress = 100;
      state.refinementXP = 1;
      setSubsidyMode('commercial');
    });
    await simulator.evaluate(() => stepTurns(5));
    assert.equal(await simulator.evaluate(() => state.refinementXP), 1);
    await simulator.locator('#eng-installations').fill('1');
    await simulator.locator('#eng-installations').dispatchEvent('change');
    await simulator.evaluate(() => stepTurns(40));
    assert.ok(await simulator.evaluate(() => state.refinementXP >= 25));
    await simulator.locator('#eng-objective').selectOption('economy');
    await simulator.locator('#btn-sub-crash').click();
    const cash = await simulator.evaluate(() => state.gold);
    await simulator.evaluate(() => stepTurns(3));
    assert.ok(await simulator.evaluate(() => state.gold < 1200));
    assert.ok(cash - await simulator.evaluate(() => state.gold) <= 45);
    await simulator.screenshot({ path: '/private/tmp/engineering-simulator.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('Engineering browser checks passed: preview, funding, stop, mobile layout, idle designs, operational learning, and constrained spending.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
