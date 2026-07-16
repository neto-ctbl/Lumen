const { chromium } = require('playwright');
const fs = require('fs');

const OUT = 'sittax-network-log.jsonl';

function maskValue(value) {
  if (!value) return value;

  let s = String(value);

  s = s.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [MASKED]');
  s = s.replace(/"token"\s*:\s*"[^"]+"/gi, '"token":"[MASKED]"');
  s = s.replace(/"senha"\s*:\s*"[^"]+"/gi, '"senha":"[MASKED]"');
  s = s.replace(/"password"\s*:\s*"[^"]+"/gi, '"password":"[MASKED]"');
  s = s.replace(/"apiKeyAcessorias"\s*:\s*"[^"]+"/gi, '"apiKeyAcessorias":"[MASKED]"');
  s = s.replace(/Cookie:\s*.+/gi, 'Cookie: [MASKED]');

  return s;
}

function safeHeaders(headers) {
  const out = {};
  for (const [k, v] of Object.entries(headers || {})) {
    const key = k.toLowerCase();

    if (
      key.includes('authorization') ||
      key.includes('cookie') ||
      key.includes('token') ||
      key.includes('secret') ||
      key.includes('key')
    ) {
      out[k] = '[MASKED]';
    } else {
      out[k] = v;
    }
  }
  return out;
}

function write(entry) {
  fs.appendFileSync(OUT, JSON.stringify(entry) + '\n', 'utf8');
}

(async () => {
  fs.writeFileSync(OUT, '', 'utf8');

  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome'
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    serviceWorkers: 'block',
    ignoreHTTPSErrors: false
  });

  const page = await context.newPage();

  page.on('request', async (req) => {
    const url = req.url();

    if (!url.includes('sittax.com.br')) return;

    const type = req.resourceType();
    if (!['xhr', 'fetch'].includes(type)) return;

    let postData = null;
    try {
      postData = req.postData();
    } catch (_) {}

    write({
      kind: 'request',
      ts: new Date().toISOString(),
      method: req.method(),
      url,
      resourceType: type,
      headers: safeHeaders(req.headers()),
      postData: postData ? maskValue(postData) : null
    });
  });

  page.on('response', async (res) => {
    const url = res.url();

    if (!url.includes('sittax.com.br')) return;

    const req = res.request();
    const type = req.resourceType();

    if (!['xhr', 'fetch'].includes(type)) return;

    let body = null;
    const contentType = res.headers()['content-type'] || '';

    try {
      if (
        contentType.includes('application/json') ||
        contentType.includes('text/plain')
      ) {
        body = await res.text();
        body = maskValue(body);
      }
    } catch (err) {
      body = `[BODY_NOT_READABLE: ${err.message}]`;
    }

    write({
      kind: 'response',
      ts: new Date().toISOString(),
      status: res.status(),
      url,
      fromServiceWorker: res.fromServiceWorker(),
      headers: safeHeaders(res.headers()),
      body
    });
  });

  await page.goto('https://app.sittax.com.br/', { waitUntil: 'domcontentloaded' });

  console.log('Navegue normalmente no Sittax. Quando terminar, volte aqui e pressione ENTER.');
  process.stdin.resume();
  process.stdin.on('data', async () => {
    await browser.close();
    console.log(`Log salvo em ${OUT}`);
    process.exit(0);
  });
})();