/* Optional FR-01..FR-10 browser acceptance. Requires seeded users with locally set passwords. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  assert(process.env.LF_BROWSER_PASSWORD, 'Set LF_BROWSER_PASSWORD for locally prepared demo accounts');
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, headless: true, args: ['--no-sandbox'] });
  const base = process.env.LF_BASE_URL || 'http://127.0.0.1:8000';
  const contexts = [];
  const errors = [];
  async function session(username) {
    const context = await browser.newContext({locale:'ja-JP', timezoneId:'Asia/Tokyo'});
    contexts.push(context);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    if (username) {
      await page.goto(base + '/accounts/login/');
      await page.getByLabel('ユーザー名').fill(username);
      await page.getByLabel('パスワード').fill(process.env.LF_BROWSER_PASSWORD);
      await page.getByRole('button', {name:'ログイン', exact:true}).click();
      await page.waitForURL('**/dashboard/');
    }
    return page;
  }
  try {
    const visitor = await session();
    const subject = `架空ブラウザー検証 ${Date.now()}`;
    await visitor.goto(base + '/inquiry/');
    await visitor.getByLabel('お名前（架空）').fill('架空ブラウザーのお客様');
    await visitor.getByLabel('メールアドレス（架空）').fill(`browser-${Date.now()}@example.test`);
    await visitor.getByLabel('工事種別').selectOption('kitchen');
    await visitor.getByLabel('件名').fill(subject);
    await visitor.getByLabel('お問い合わせ内容').fill('自動テスト専用の架空のご相談です。');
    await visitor.getByRole('button', {name:'デモのお問い合わせを送信'}).click();
    await visitor.waitForURL('**/inquiry/thanks/');
    assert(await visitor.getByRole('heading', {name:'お問い合わせを受け付けました'}).isVisible());

    const manager = await session('demo-manager');
    await manager.goto(base + '/inquiries/?owner=unassigned&q=' + encodeURIComponent(subject));
    await manager.getByRole('link', {name:subject, exact:true}).click();
    const detailURL = manager.url();
    await manager.getByLabel('担当者').selectOption({label:'demo-employee-1'});
    await manager.getByRole('button', {name:'割当を保存'}).click();

    const employee = await session('demo-employee-1');
    await employee.goto(detailURL);
    await employee.getByLabel('対応種別').selectOption('call');
    await employee.getByLabel('対応内容').fill('架空のお電話を記録しました。');
    await employee.getByRole('button', {name:'記録する'}).click();
    await employee.getByRole('link', {name:'＋ 予定を登録'}).click();
    await employee.getByLabel('開始日時').fill('2030-12-20T10:00');
    await employee.getByLabel('終了日時').fill('2030-12-20T11:00');
    await employee.getByLabel('場所').fill('架空市デモ町');
    await employee.getByRole('button', {name:'保存する'}).click();
    await employee.getByRole('link', {name:'＋ 見積を作成'}).click();
    await employee.getByLabel('見積件名').fill('架空のキッチン工事見積');
    await employee.getByLabel('見積状況').selectOption('sent');
    await employee.locator('#id_items-0-description').fill('架空の設備工事');
    await employee.locator('#id_items-0-quantity').fill('1.25');
    await employee.locator('#id_items-0-unit_price').fill('101');
    await employee.locator('#id_items-1-description').fill('架空の施工');
    await employee.locator('#id_items-1-quantity').fill('2');
    await employee.locator('#id_items-1-unit_price').fill('333');
    await employee.getByRole('button', {name:'＋ 明細を追加'}).click();
    assert.equal(await employee.locator('#id_items-TOTAL_FORMS').inputValue(), '5');
    await employee.getByRole('button', {name:'見積を保存'}).click();
    await employee.waitForURL('**/quotations/*/');
    assert((await employee.locator('.quote-total').innerText()).includes('871.25'));
    const printURL = await employee.getByRole('link', {name:'印刷用の見積書'}).getAttribute('href');
    const print = await employee.context().newPage();
    await print.goto(base + printURL);
    assert((await print.locator('body').innerText()).includes('SAMPLE / DEMO'));
    assert.equal(await print.locator('form, button').count(), 0);
    await print.close();
    await employee.goto(detailURL);
    await employee.getByRole('link', {name:'＋ タスクを登録'}).click();
    await employee.getByLabel('タスク名').fill('架空のフォロー連絡');
    await employee.getByLabel('期限').fill('2020-01-01');
    await employee.getByRole('button', {name:'保存する'}).click();
    assert(await employee.getByText('期限超過', {exact:true}).isVisible());
    await employee.getByRole('button', {name:'完了にする',exact:true}).click();
    assert.equal(await employee.getByText('期限超過', {exact:true}).count(), 0);
    await employee.getByLabel('対応状況').selectOption('won');
    await employee.getByRole('button', {name:'状況を更新'}).click();
    assert.equal(await employee.locator('.badge-status').innerText(), '成約');

    const other = await session('demo-employee-2');
    const denied = await other.goto(detailURL);
    assert.equal(denied.status(), 404);
    assert(!(await other.locator('body').innerText()).includes(subject));
    await manager.goto(base + '/dashboard/');
    assert(await manager.getByText('成約率', {exact:true}).isVisible());
    await manager.waitForFunction(() => !!window.Chart && Chart.getChart(document.getElementById('trend-chart')));
    fs.mkdirSync('test-results', {recursive:true});
    await manager.screenshot({path:'test-results/dashboard-desktop.png',fullPage:true});
    for (const path of ['/dashboard/','/customers/','/inquiries/','/quotations/','/schedule/','/inquiry/']) {
      await manager.setViewportSize({width:375,height:812});
      await manager.goto(base + path);
      assert(await manager.locator('h1').isVisible());
      assert(await manager.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile horizontal overflow: ' + path);
    }
    await manager.goto(base + '/dashboard/');
    await manager.screenshot({path:'test-results/dashboard-mobile.png',fullPage:true});
    assert.deepEqual(errors, []);
    console.log('Browser acceptance passed: intake → assignment → note → inspection → quote/print → task → won; cross-owner denial; desktop/mobile layouts; no JS errors.');
  } finally {
    for (const context of contexts) await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
