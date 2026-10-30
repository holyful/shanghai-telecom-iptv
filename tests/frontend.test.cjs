/* Run: node --test tests/frontend.test.cjs (Playwright or playwright-core required).
 * Requests are intercepted in Chromium. No HTTP service is started.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = require('playwright-core')); }
const root = path.resolve(__dirname, '../iptv_lan/static');
const origin = 'http://homecast.test';
const now = Math.floor(Date.now() / 1000);
const current = { title: '午间新闻', start: now - 900, end: now + 1800 };
const next = { title: '纪录时光', start: now + 1800, end: now + 5400 };
const channels = [
  { id: 'general/1', name: '综合频道', group: '综合', quality: '高清', programme_count: 24, current, next },
  { id: 'documentary', name: '纪录频道', group: '纪实', quality: '4K', programme_count: 12, current: null, next },
  { id: 'escape', name: '<img src=x onerror=alert(1)>', group: '测试', quality: 'HD', programme_count: 0, current: null, next: null },
];
function fixture() {
  return {
    status: { state: 'idle', stage: '', progress: 0, last_success: now - 300, last_attempt: now - 300,
      next_refresh: now + 3600, channel_count: 3, programme_count: 36, coverage_end: now + 86400,
      last_error: null, version: '0.1.0', refresh_time: '05:00', auto_refresh: true,
      source: 'Shanghai Telecom', cache_available: true },
    channels: structuredClone(channels), requests: [], fail: new Set(), delays: new Map(), programmes: null,
  };
}
async function setup(browser, viewport = { width: 1440, height: 1000 }, timezoneId = 'Asia/Shanghai') {
  const context = await browser.newContext({ viewport, timezoneId });
  const page = await context.newPage();
  const data = fixture();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(`${origin}/**`, async route => {
    const request = route.request();
    const url = new URL(request.url());
    data.requests.push({ path: url.pathname, search: url.search, method: request.method(),
      headers: request.headers(), body: request.postData() });
    if (data.delays.has(url.pathname)) await data.delays.get(url.pathname);
    if (data.fail.has(url.pathname)) return route.fulfill({ status: 503, json: { error: '暂时不可用' } });
    if (url.pathname === '/api/status') return route.fulfill({ json: data.status });
    if (url.pathname === '/api/channels') return route.fulfill({ json: { channels: data.channels } });
    if (url.pathname.endsWith('/programmes')) return route.fulfill({ json: {
      channel: data.channels.find(c => c.id === decodeURIComponent(url.pathname.split('/')[3])) || data.channels[0],
      date: url.searchParams.get('date'), programmes: data.programmes || [current, next],
    } });
    if (url.pathname === '/api/logs') return route.fulfill({ json: { logs: [
      { time: now - 300, level: 'info', message: '频道与节目单更新完成' },
      { time: now - 400, level: 'error', message: '<script>window.injected=true</script>' },
    ] } });
    if (url.pathname === '/api/refresh') {
      data.status.state = 'refreshing'; data.status.stage = '正在获取节目单'; data.status.progress = 40;
      return route.fulfill({ status: 202, json: { started: true } });
    }
    if (url.pathname === '/api/settings') {
      Object.assign(data.status, request.postDataJSON());
      return route.fulfill({ json: request.postDataJSON() });
    }
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const file = path.join(root, relative);
    const type = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'application/javascript', '.png': 'image/png' }[path.extname(file)];
    if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'Not found' });
    return route.fulfill({ contentType: type || 'text/plain', body: fs.readFileSync(file) });
  });
  return { context, page, data, errors };
}
async function ready(page) {
  await page.goto(origin);
  await page.getByRole('button', { name: '综合频道', exact: true }).waitFor();
  await page.locator('#programme-list .programme').first().waitFor();
}
test('frontend assets exist and contain no unsafe HTML sinks', () => {
  assert.ok(fs.existsSync(path.join(root, 'index.html')), 'The usable first screen must exist');
  const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
  assert.doesNotMatch(js, /\.innerHTML\s*=|insertAdjacentHTML|document\.write\(/);
  assert.ok(fs.existsSync(path.join(root, 'vendor/lucide.LICENSE')));
  assert.ok(fs.existsSync(path.join(root, 'assets/homecast.png')));
});
test('browser workflows and responsive layout', async t => {
  if (!fs.existsSync(path.join(root, 'index.html'))) return t.skip('First screen not implemented yet');
  const browser = await chromium.launch({ headless: true, channel: process.env.FRONTEND_BROWSER || 'chrome' });
  t.after(() => browser.close());
  await t.test('real API data, safe text, channel selection, filters and date navigation', async () => {
    const { context, page, data, errors } = await setup(browser);
    try {
      await ready(page);
      assert.match(await page.locator('header').innerText(), /上海电信/);
      assert.equal(await page.locator('#channel-body tr').count(), 3);
      assert.match(await page.locator('#programme-list').innerText(), /午间新闻/);
      assert.equal(await page.locator('#channel-body img').count(), 0);
      await page.getByLabel('搜索频道').fill('纪录');
      assert.equal(await page.locator('#channel-body tr').count(), 1);
      await page.getByRole('button', { name: '清除搜索' }).click();
      await page.getByRole('button', { name: '纪实', exact: true }).click();
      assert.equal(await page.locator('#channel-body tr').count(), 1);
      await page.getByRole('button', { name: '纪录频道', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('#guide-title').textContent === '纪录频道');
      await page.getByLabel('节目日期').fill('2030-01-02');
      await page.waitForFunction(() => !document.querySelector('#programme-list').hasAttribute('aria-busy'));
      assert.ok(data.requests.some(r => r.search === '?date=2030-01-02'));
      assert.ok(data.requests.some(r => r.path.includes('general%2F1')));
      assert.equal(await page.evaluate(() => window.injected), undefined);
      assert.deepEqual(errors, []);
    } finally { await context.close(); }
  });
  await t.test('refresh and settings use the agreed POST contract', async () => {
    const { context, page, data, errors } = await setup(browser);
    try {
      await ready(page);
      await page.getByRole('button', { name: '立即更新', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('#refresh-button').disabled);
      await page.getByRole('button', { name: '更新设置' }).click();
      await page.getByLabel('每日更新时间').fill('06:30');
      await page.getByLabel('自动更新').uncheck();
      await page.getByRole('button', { name: '保存设置' }).click();
      await page.getByText('设置已保存', { exact: true }).waitFor();
      const refresh = data.requests.find(r => r.path === '/api/refresh');
      const settings = data.requests.find(r => r.path === '/api/settings');
      for (const request of [refresh, settings]) {
        assert.equal(request.method, 'POST');
        assert.equal(request.headers['x-requested-with'], 'HomeCast');
        assert.match(request.headers['content-type'], /application\/json/);
      }
      assert.deepEqual(JSON.parse(refresh.body), {});
      assert.deepEqual(JSON.parse(settings.body), { refresh_time: '06:30', auto_refresh: false });
      assert.deepEqual(errors, []);
    } finally { await context.close(); }
  });
  await t.test('offline startup is honest and retry recovers', async () => {
    const { context, page, data } = await setup(browser);
    try {
      data.fail.add('/api/status'); data.fail.add('/api/channels');
      await page.goto(origin);
      await page.getByRole('button', { name: '重新连接' }).waitFor();
      assert.equal(await page.locator('#channel-body tr').count(), 0);
      data.fail.clear();
      await page.getByRole('button', { name: '重新连接' }).click();
      await page.getByRole('button', { name: '综合频道', exact: true }).waitFor();
    } finally { await context.close(); }
  });
  await t.test('poll interval follows refresh state, and successful updates reload channels', async () => {
    const { context, page, data } = await setup(browser);
    try {
      await page.clock.install();
      await ready(page);
      const count = name => data.requests.filter(r => r.path === name).length;
      const initial = count('/api/status');
      const idlePoll = page.waitForResponse(`${origin}/api/status`);
      await page.clock.fastForward(5000);
      await idlePoll;
      assert.ok(count('/api/status') > initial);
      const channelRequests = count('/api/channels');
      data.status.state = 'refreshing';
      await page.clock.fastForward(5000);
      await page.getByText('更新中', { exact: true }).first().waitFor();
      const refreshing = count('/api/status');
      const busyPoll = page.waitForResponse(`${origin}/api/status`);
      await page.clock.fastForward(2000);
      await busyPoll;
      assert.ok(count('/api/status') > refreshing);
      data.status.state = 'idle'; data.status.last_success += 100;
      await page.clock.fastForward(2000);
      await page.waitForFunction(() => document.querySelector('#connection-label').textContent === '运行正常');
      assert.ok(count('/api/channels') > channelRequests);
    } finally { await context.close(); }
  });
  await t.test('mobile and desktop fit, local logo and icons render, downloads stay compatible', async () => {
    const { context, page, errors } = await setup(browser);
    try {
      await ready(page);
      assert.equal(await page.locator('a[href="/m3u/xteve.m3u"]').count(), 1);
      assert.equal(await page.locator('a[href="/xmltv/xteve.xml"]').count(), 1);
      assert.ok(await page.locator('svg.lucide').count() > 8);
      assert.ok(await page.locator('.brand-logo').evaluate(img => img.complete && img.naturalWidth > 0));
      for (const width of [1440, 1024, 768, 390, 360, 320]) {
        await page.setViewportSize({ width, height: 900 });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `overflow at ${width}px`);
      }
      await page.getByRole('button', { name: '综合频道', exact: true }).click();
      await page.locator('#programme-list .programme').first().waitFor();
      assert.ok(await page.locator('#programme-list').isVisible());
      await page.getByRole('button', { name: '返回频道' }).click();
      assert.ok(await page.locator('#channel-body').isVisible());
      assert.deepEqual(errors, []);
    } finally { await context.close(); }
  });
  await t.test('failed updates preserve cached data; programme and log errors can retry', async () => {
    const { context, page, data } = await setup(browser);
    try {
      await ready(page);
      data.status.state = 'error'; data.status.last_error = '节目源暂时不可用';
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
      await page.locator('#update-error').waitFor();
      assert.match(await page.locator('#update-error').innerText(), /现有缓存仍可使用/);
      assert.equal(await page.locator('#channel-body tr').count(), 3);
      data.fail.add('/api/channels/documentary/programmes');
      await page.getByRole('button', { name: '纪录频道', exact: true }).click();
      await page.getByRole('button', { name: '重试节目单' }).waitFor();
      data.fail.delete('/api/channels/documentary/programmes');
      await page.getByRole('button', { name: '重试节目单' }).click();
      await page.locator('#programme-list .programme').first().waitFor();
      data.fail.add('/api/logs');
      await page.getByRole('button', { name: '刷新日志' }).click();
      await page.locator('#logs-error').waitFor();
      assert.equal(await page.locator('#log-list .log-row').count(), 2);
      data.fail.delete('/api/logs');
      await page.getByRole('button', { name: '刷新日志' }).click();
      await page.locator('#logs-error').waitFor({ state: 'hidden' });
      await page.getByLabel('日志级别').selectOption('error');
      assert.equal(await page.locator('#log-list .log-row').count(), 1);
    } finally { await context.close(); }
  });
  await t.test('pending old guide response cannot overwrite a newly selected channel', async () => {
    const { context, page, data } = await setup(browser);
    let release;
    try {
      await ready(page);
      data.delays.set('/api/channels/documentary/programmes', new Promise(resolve => { release = resolve; }));
      await page.getByRole('button', { name: '纪录频道', exact: true }).click();
      await page.getByRole('button', { name: '综合频道', exact: true }).click();
      await page.locator('#programme-list .programme').first().waitFor();
      release();
      assert.equal(await page.locator('#guide-title').textContent(), '综合频道');
      assert.equal(await page.locator('#programme-list .programme').count(), 2);
    } finally { release?.(); await context.close(); }
  });
  await t.test('settings drafts survive polling and failed saves can retry', async () => {
    const { context, page, data } = await setup(browser);
    try {
      await ready(page);
      await page.getByRole('button', { name: '更新设置' }).click();
      await page.getByLabel('每日更新时间').fill('07:15');
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
      assert.equal(await page.getByLabel('每日更新时间').inputValue(), '07:15');
      data.fail.add('/api/settings');
      await page.getByRole('button', { name: '保存设置' }).click();
      await page.getByText(/保存失败：/).waitFor();
      assert.equal(await page.getByLabel('每日更新时间').inputValue(), '07:15');
      data.fail.delete('/api/settings');
      await page.getByRole('button', { name: '保存设置' }).click();
      await page.getByText('设置已保存', { exact: true }).waitFor();
    } finally { await context.close(); }
  });
  await t.test('empty channel and programme responses are explicit, not sample content', async () => {
    const { context, page, data } = await setup(browser);
    try {
      data.channels = []; data.status.channel_count = 0;
      await page.goto(origin);
      await page.getByText('频道库为空', { exact: true }).waitFor();
      assert.equal(await page.locator('#channel-body tr').count(), 0);
      data.channels = structuredClone(channels); data.programmes = []; data.status.last_success += 1;
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
      await page.getByText('当日暂无节目', { exact: true }).waitFor();
      assert.equal(await page.locator('#programme-list .programme').count(), 0);
    } finally { await context.close(); }
  });
  await t.test('Shanghai programme dates and clocks do not depend on the browser timezone', async () => {
    const { context, page } = await setup(browser, { width: 1440, height: 1000 }, 'America/New_York');
    try {
      await page.clock.install({ time: new Date('2030-01-02T01:00:00+08:00') });
      await ready(page);
      assert.equal(await page.getByLabel('节目日期').inputValue(), '2030-01-02');
      await page.getByRole('button', { name: '前一天' }).click();
      assert.equal(await page.getByLabel('节目日期').inputValue(), '2030-01-01');
      await page.getByRole('button', { name: '今天', exact: true }).click();
      assert.equal(await page.getByLabel('节目日期').inputValue(), '2030-01-02');
    } finally { await context.close(); }
  });
  await t.test('now and next reload when a programme crosses its boundary', async () => {
    const { context, page, data } = await setup(browser);
    try {
      await page.clock.install({ time: new Date(now * 1000) });
      await ready(page);
      const before = data.requests.filter(r => r.path === '/api/channels').length;
      data.channels[0].current = { ...next, title: '下一段直播' };
      data.channels[0].next = { title: '晚间节目', start: next.end, end: next.end + 3600 };
      await page.clock.fastForward(1801000);
      await page.waitForFunction(() => document.querySelector('.current-cell').textContent.includes('下一段直播'), null, { timeout: 3000 });
      assert.ok(data.requests.filter(r => r.path === '/api/channels').length > before);
    } finally { await context.close(); }
  });
  await t.test('slow programme requests do not delay refreshing status polls', async () => {
    const { context, page, data } = await setup(browser);
    let release;
    try {
      await page.clock.install();
      data.status.state = 'refreshing';
      data.delays.set('/api/channels/general%2F1/programmes', new Promise(resolve => { release = resolve; }));
      await page.goto(origin);
      await page.getByText('正在读取节目单', { exact: true }).waitFor();
      const before = data.requests.filter(r => r.path === '/api/status').length;
      const response = page.waitForResponse(`${origin}/api/status`, { timeout: 3000 });
      await page.clock.fastForward(2000);
      await response;
      assert.ok(data.requests.filter(r => r.path === '/api/status').length > before);
      release();
    } finally { release?.(); await context.close(); }
  });
  if (process.env.FRONTEND_SCREENSHOTS) await t.test('capture representative desktop and mobile views', async () => {
    const { context, page, data } = await setup(browser);
    try {
      const names = ['综合频道', '新闻频道', '纪实频道', '城市频道', '体育频道', '电影频道', '少儿频道', '音乐频道', '文化频道', '生活频道', '科教频道', '戏曲频道'];
      data.channels = names.map((name, index) => ({ ...channels[0], id: String(index), name, group: index < 3 ? '综合' : index < 7 ? '地方' : '专题', quality: index === 2 ? '4K' : '高清' }));
      data.status.channel_count = 12; data.status.programme_count = 288;
      data.programmes = Array.from({ length: 24 }, (_, index) => ({ title: ['早间新闻', '城市生活', '纪录时光', '文化视野'][index % 4], start: now + (index - 6) * 3600 - 900, end: now + (index - 5) * 3600 - 900 }));
      await ready(page);
      await page.screenshot({ path: path.join(__dirname, 'frontend-desktop.png'), fullPage: true });
      await page.setViewportSize({ width: 390, height: 900 });
      await page.screenshot({ path: path.join(__dirname, 'frontend-mobile.png'), fullPage: true });
      await page.getByRole('button', { name: '综合频道', exact: true }).click();
      await page.locator('#programme-list .programme').first().waitFor();
      await page.screenshot({ path: path.join(__dirname, 'frontend-mobile-guide.png'), fullPage: true });
    } finally { await context.close(); }
  });
});
