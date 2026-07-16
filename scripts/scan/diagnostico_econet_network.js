const { chromium } = require('playwright');
const fs = require('fs');

const START_URL = 'https://www.econeteditora.com.br/';
const TARGET_HOSTS = ['econeteditora.com.br', 'www.econeteditora.com.br'];
const OUT = 'econet-network-log.jsonl';

function maskValue(value) {
  if (!value) return value;

  let s = String(value);

  s = s.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [MASKED]');
  s = s.replace(/"token"\s*:\s*"[^"]+"/gi, '"token":"[MASKED]"');
  s = s.replace(/"senha"\s*:\s*"[^"]+"/gi, '"senha":"[MASKED]"');
  s = s.replace(/"password"\s*:\s*"[^"]+"/gi, '"password":"[MASKED]"');
  s = s.replace(/Cookie:\s*.+/gi, 'Cookie: [MASKED]');
  s = s.replace(/PHPSESSID=[^;&\s"]+/gi, 'PHPSESSID=[MASKED]');
  s = s.replace(/ASPSESSIONID[^=]*=[^;&\s"]+/gi, 'ASPSESSIONID=[MASKED]');

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
      key.includes('key') ||
      key.includes('csrf')
    ) {
      out[k] = '[MASKED]';
    } else {
      out[k] = v;
    }
  }
  return out;
}

function isTarget(url) {
  try {
    const u = new URL(url);
    return TARGET_HOSTS.some(h => u.hostname.endsWith(h));
  } catch {
    return false;
  }
}

function truncateBody(body) {
  if (!body) return body;
  const max = 50000;
  return body.length > max ? body.slice(0, max) + '\n...[TRUNCATED]...' : body;
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
    if (!isTarget(url)) return;

    const type = req.resourceType();

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
    if (!isTarget(url)) return;

    const req = res.request();
    const type = req.resourceType();
    const contentType = res.headers()['content-type'] || '';

    let body = null;

    try {
      if (
        contentType.includes('application/json') ||
        contentType.includes('text/plain') ||
        contentType.includes('text/html')
      ) {
        body = await res.text();
        body = truncateBody(maskValue(body));
      }
    } catch (err) {
      body = `[BODY_NOT_READABLE: ${err.message}]`;
    }

    write({
      kind: 'response',
      ts: new Date().toISOString(),
      status: res.status(),
      url,
      resourceType: type,
      fromServiceWorker: res.fromServiceWorker(),
      headers: safeHeaders(res.headers()),
      body
    });
  });

  await page.goto(START_URL, { waitUntil: 'domcontentloaded' });

  console.log('Navegue na Econet normalmente. Faça login, consulte CNAEs/regimes/atividades e depois pressione ENTER aqui.');
  process.stdin.resume();

  process.stdin.on('data', async () => {
    await browser.close();
    console.log(`Log salvo em ${OUT}`);
    process.exit(0);
  });
})();