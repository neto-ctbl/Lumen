const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const START_URL = 'https://www.econeteditora.com.br/';
const TARGET_HOSTS = ['econeteditora.com.br', 'www.econeteditora.com.br'];
const SCRIPT_DIR = __dirname;
const LOG_DIR = path.join(SCRIPT_DIR, 'logs');
const OUT_JSONL = path.join(LOG_DIR, 'econet-network-log.jsonl');
const OUT_HAR = path.join(LOG_DIR, 'econet-network.har');
const OUT_BEFORE = path.join(LOG_DIR, 'econet-storage-before.json');
const OUT_AFTER = path.join(LOG_DIR, 'econet-storage-after.json');
const OUT_DIFF = path.join(LOG_DIR, 'econet-storage-diff.json');
const BODY_MAX = 150000;

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function isTarget(url) {
  try {
    const u = new URL(url);
    return TARGET_HOSTS.some((host) => u.hostname === host || u.hostname.endsWith(`.${host}`));
  } catch {
    return false;
  }
}

function maskValue(value) {
  if (value == null) return value;

  let s = typeof value === 'string' ? value : JSON.stringify(value);

  s = s.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [MASKED]');
  s = s.replace(/"token"\s*:\s*"[^"]+"/gi, '"token":"[MASKED]"');
  s = s.replace(/"senha"\s*:\s*"[^"]+"/gi, '"senha":"[MASKED]"');
  s = s.replace(/"password"\s*:\s*"[^"]+"/gi, '"password":"[MASKED]"');
  s = s.replace(/PHPSESSID=[^;&\s"]+/gi, 'PHPSESSID=[MASKED]');
  s = s.replace(/ASPSESSIONID[^=]*=[^;&\s"]+/gi, 'ASPSESSIONID=[MASKED]');
  s = s.replace(/(?:^|[?&])(senha|password|token|access_token|auth)=([^&]+)/gi, (_m, key) => `${key}=[MASKED]`);

  return s;
}

function sanitizeDeep(value) {
  if (value == null) return value;
  if (typeof value === 'string') return maskValue(value);
  if (Array.isArray(value)) return value.map((item) => sanitizeDeep(item));
  if (typeof value === 'object') {
    const out = {};
    for (const [key, inner] of Object.entries(value)) {
      out[key] = sanitizeDeep(inner);
    }
    return out;
  }
  return value;
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
      key.includes('csrf') ||
      key.includes('session')
    ) {
      out[k] = '[MASKED]';
    } else {
      out[k] = v;
    }
  }
  return out;
}

function truncateText(value, max = BODY_MAX) {
  if (!value || value.length <= max) return value;
  return value.slice(0, max) + '\n...[TRUNCATED]...';
}

function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
}

function write(entry) {
  fs.appendFileSync(OUT_JSONL, JSON.stringify(entry) + '\n', 'utf8');
}

function summarizeHtml(title, body, url) {
  const bodyText = body || '';
  const anchors = [...bodyText.matchAll(/<a\b/gi)].length;
  const tables = [...bodyText.matchAll(/<table\b/gi)].length;
  const forms = [...bodyText.matchAll(/<form\b/gi)].length;
  const cnaeMatches = [...bodyText.matchAll(/\b\d{4}-\d\/\d{2}\b/g)].map((match) => match[0]);
  const badges = [];

  if (/fator\s*r/i.test(bodyText)) badges.push('fator-r');
  if (/simples nacional/i.test(bodyText)) badges.push('simples-nacional');
  if (/\bmei\b/i.test(bodyText)) badges.push('mei');
  if (/lucro presumido/i.test(bodyText)) badges.push('lucro-presumido');
  if (/lucro real/i.test(bodyText)) badges.push('lucro-real');
  if (/obriga[cç][õo]es acess[oó]rias/i.test(bodyText)) badges.push('obrigacoes');
  if (/anexo\s+[ivx]+/i.test(bodyText)) badges.push('anexos');

  return {
    title: title || null,
    anchors,
    tables,
    forms,
    cnaes: Array.from(new Set(cnaeMatches)).slice(0, 20),
    badges,
    url
  };
}

function summarizeEconetResponse(url, contentType, body) {
  if (!body) return null;

  const summary = {
    url,
    contentType
  };

  if (contentType.includes('application/json')) {
    try {
      const parsed = JSON.parse(body);
      summary.kind = 'json';
      summary.keys = parsed && typeof parsed === 'object' ? Object.keys(parsed).sort() : [];
      summary.preview = sanitizeDeep(parsed);
      return summary;
    } catch {
      return {
        ...summary,
        kind: 'json-unparsed'
      };
    }
  }

  if (!contentType.includes('text/html') && !contentType.includes('text/plain')) {
    return null;
  }

  const titleMatch = body.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim() : null;

  if (/buscaCnae\.php/i.test(url)) {
    return {
      ...summary,
      kind: 'busca-cnae',
      ...summarizeHtml(title, body, url)
    };
  }

  if (/index\.php\?[^#]*idcnae=/i.test(url) || /acao=abrir/i.test(url)) {
    return {
      ...summary,
      kind: 'cnae-detalhe',
      ...summarizeHtml(title, body, url)
    };
  }

  if (/subAbas\.php/i.test(url)) {
    return {
      ...summary,
      kind: 'sub-aba',
      ...summarizeHtml(title, body, url)
    };
  }

  if (/abas\.php/i.test(url)) {
    return {
      ...summary,
      kind: 'aba',
      ...summarizeHtml(title, body, url)
    };
  }

  if (/login|autentic|captcha/i.test(url) || /senha|login|captcha/i.test(body)) {
    return {
      ...summary,
      kind: 'auth',
      ...summarizeHtml(title, body, url)
    };
  }

  return {
    ...summary,
    kind: 'html',
    ...summarizeHtml(title, body, url)
  };
}

function sanitizeCookie(cookie) {
  return {
    name: cookie.name,
    valueMasked: cookie.value ? `[MASKED:${cookie.value.length}]` : '',
    domain: cookie.domain,
    path: cookie.path,
    expires: cookie.expires,
    httpOnly: cookie.httpOnly,
    secure: cookie.secure,
    sameSite: cookie.sameSite
  };
}

function diffKeyValueMap(before = {}, after = {}) {
  const added = [];
  const removed = [];
  const changed = [];
  const allKeys = new Set([...Object.keys(before), ...Object.keys(after)]);

  for (const key of Array.from(allKeys).sort()) {
    if (!(key in before)) {
      added.push({ key, after: after[key] });
      continue;
    }
    if (!(key in after)) {
      removed.push({ key, before: before[key] });
      continue;
    }
    if (stableStringify(before[key]) !== stableStringify(after[key])) {
      changed.push({ key, before: before[key], after: after[key] });
    }
  }

  return { added, removed, changed };
}

function diffCookies(before = [], after = []) {
  const toMap = (items) => {
    const map = new Map();
    for (const item of items) {
      map.set(`${item.name}|${item.domain}|${item.path}`, item);
    }
    return map;
  };

  const left = toMap(before);
  const right = toMap(after);
  const added = [];
  const removed = [];
  const changed = [];
  const allKeys = new Set([...left.keys(), ...right.keys()]);

  for (const key of Array.from(allKeys).sort()) {
    const beforeItem = left.get(key);
    const afterItem = right.get(key);

    if (!beforeItem) {
      added.push(afterItem);
      continue;
    }
    if (!afterItem) {
      removed.push(beforeItem);
      continue;
    }
    if (stableStringify(beforeItem) !== stableStringify(afterItem)) {
      changed.push({ before: beforeItem, after: afterItem });
    }
  }

  return { added, removed, changed };
}

async function captureIndexedDb(page) {
  return page.evaluate(async () => {
    const toSerializable = (value, seen = new WeakSet()) => {
      if (value === null || value === undefined) return value;
      if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value;
      if (value instanceof Date) return value.toISOString();
      if (Array.isArray(value)) return value.map((item) => toSerializable(item, seen));
      if (typeof value === 'object') {
        if (seen.has(value)) return '[Circular]';
        seen.add(value);
        const out = {};
        for (const [key, inner] of Object.entries(value)) {
          out[key] = toSerializable(inner, seen);
        }
        return out;
      }
      return String(value);
    };

    if (!('indexedDB' in window) || !indexedDB.databases) {
      return { supported: false, databases: [] };
    }

    const dbs = await indexedDB.databases();
    const databases = [];

    for (const info of dbs) {
      if (!info.name) continue;

      const result = await new Promise((resolve) => {
        const req = indexedDB.open(info.name);

        req.onerror = () => {
          resolve({
            name: info.name,
            version: info.version || null,
            error: req.error ? req.error.message : 'open failed',
            objectStores: []
          });
        };

        req.onsuccess = () => {
          const db = req.result;
          const storeNames = Array.from(db.objectStoreNames);

          if (!storeNames.length) {
            db.close();
            resolve({
              name: info.name,
              version: db.version,
              objectStores: []
            });
            return;
          }

          const tx = db.transaction(storeNames, 'readonly');
          const stores = [];
          let remaining = storeNames.length;

          const finish = () => {
            remaining -= 1;
            if (remaining === 0) {
              db.close();
              resolve({
                name: info.name,
                version: db.version,
                objectStores: stores
              });
            }
          };

          for (const storeName of storeNames) {
            const store = tx.objectStore(storeName);
            const item = {
              name: storeName,
              keyPath: store.keyPath || null,
              autoIncrement: store.autoIncrement,
              indexes: Array.from(store.indexNames),
              records: []
            };

            const getAllReq = store.getAll();
            getAllReq.onsuccess = () => {
              item.records = getAllReq.result.slice(0, 100).map((record) => toSerializable(record));
              item.recordCount = getAllReq.result.length;
              stores.push(item);
              finish();
            };
            getAllReq.onerror = () => {
              item.error = getAllReq.error ? getAllReq.error.message : 'getAll failed';
              stores.push(item);
              finish();
            };
          }
        };
      });

      databases.push(result);
    }

    return { supported: true, databases };
  });
}

async function captureStorageSnapshot(context, page, label) {
  const pageData = await page.evaluate(() => {
    const localStorageData = {};
    const sessionStorageData = {};

    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      localStorageData[key] = window.localStorage.getItem(key);
    }

    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const key = window.sessionStorage.key(i);
      sessionStorageData[key] = window.sessionStorage.getItem(key);
    }

    return {
      url: window.location.href,
      origin: window.location.origin,
      title: document.title,
      localStorage: localStorageData,
      sessionStorage: sessionStorageData
    };
  });

  pageData.localStorage = Object.fromEntries(
    Object.entries(pageData.localStorage || {}).map(([key, value]) => [key, maskValue(value)])
  );
  pageData.sessionStorage = Object.fromEntries(
    Object.entries(pageData.sessionStorage || {}).map(([key, value]) => [key, maskValue(value)])
  );

  const indexedDb = sanitizeDeep(await captureIndexedDb(page));
  const cookies = (await context.cookies())
    .filter((cookie) => isTarget(`https://${cookie.domain.replace(/^\./, '')}${cookie.path}`))
    .map(sanitizeCookie)
    .sort((a, b) => `${a.name}|${a.domain}|${a.path}`.localeCompare(`${b.name}|${b.domain}|${b.path}`));

  const snapshot = {
    label,
    capturedAt: nowIso(),
    page: pageData,
    indexedDb,
    cookies
  };

  write({
    kind: 'storage-snapshot',
    ts: snapshot.capturedAt,
    label,
    pageUrl: snapshot.page.url,
    title: snapshot.page.title,
    localStorageKeys: Object.keys(snapshot.page.localStorage),
    sessionStorageKeys: Object.keys(snapshot.page.sessionStorage),
    indexedDbNames: snapshot.indexedDb.databases.map((db) => db.name),
    cookieNames: snapshot.cookies.map((cookie) => cookie.name)
  });

  return snapshot;
}

function buildSnapshotDiff(before, after) {
  const diff = {
    generatedAt: nowIso(),
    beforeCapturedAt: before ? before.capturedAt : null,
    afterCapturedAt: after ? after.capturedAt : null,
    pageUrlBefore: before ? before.page.url : null,
    pageUrlAfter: after ? after.page.url : null,
    localStorage: diffKeyValueMap(before?.page.localStorage, after?.page.localStorage),
    sessionStorage: diffKeyValueMap(before?.page.sessionStorage, after?.page.sessionStorage),
    indexedDb: diffKeyValueMap(
      Object.fromEntries((before?.indexedDb.databases || []).map((db) => [db.name, db])),
      Object.fromEntries((after?.indexedDb.databases || []).map((db) => [db.name, db]))
    ),
    cookies: diffCookies(before?.cookies, after?.cookies)
  };

  diff.hasChanges =
    diff.localStorage.added.length > 0 ||
    diff.localStorage.removed.length > 0 ||
    diff.localStorage.changed.length > 0 ||
    diff.sessionStorage.added.length > 0 ||
    diff.sessionStorage.removed.length > 0 ||
    diff.sessionStorage.changed.length > 0 ||
    diff.indexedDb.added.length > 0 ||
    diff.indexedDb.removed.length > 0 ||
    diff.indexedDb.changed.length > 0 ||
    diff.cookies.added.length > 0 ||
    diff.cookies.removed.length > 0 ||
    diff.cookies.changed.length > 0;

  return diff;
}

async function captureContextProbe(context, page, reason) {
  const state = await page.evaluate(() => ({
    url: window.location.href,
    title: document.title,
    localStorageKeys: Object.keys(window.localStorage || {}),
    sessionStorageKeys: Object.keys(window.sessionStorage || {}),
    frameCount: window.frames.length
  }));

  const cookies = (await context.cookies())
    .filter((cookie) => isTarget(`https://${cookie.domain.replace(/^\./, '')}${cookie.path}`))
    .map((cookie) => cookie.name)
    .sort();

  write({
    kind: 'context-probe',
    ts: nowIso(),
    reason,
    pageUrl: state.url,
    title: state.title,
    frameCount: state.frameCount,
    localStorageKeys: state.localStorageKeys,
    sessionStorageKeys: state.sessionStorageKeys,
    cookieNames: cookies
  });
}

function attachNetworkCapture(page) {
  if (page.__lumenEconetCaptureAttached) return;
  page.__lumenEconetCaptureAttached = true;

  page.on('request', (req) => {
    const url = req.url();
    if (!isTarget(url)) return;

    let postData = null;
    try {
      postData = req.postData();
    } catch {}

    write({
      kind: 'request',
      ts: nowIso(),
      pageUrl: maskValue(page.url()),
      method: req.method(),
      url: maskValue(url),
      resourceType: req.resourceType(),
      headers: safeHeaders(req.headers()),
      postData: postData ? truncateText(maskValue(postData)) : null
    });
  });

  page.on('response', async (res) => {
    const url = res.url();
    if (!isTarget(url)) return;

    const req = res.request();
    const contentType = (res.headers()['content-type'] || '').toLowerCase();
    let body = null;

    try {
      if (
        contentType.includes('application/json') ||
        contentType.includes('text/plain') ||
        contentType.includes('text/html') ||
        contentType.includes('javascript')
      ) {
        body = truncateText(maskValue(await res.text()));
      }
    } catch (err) {
      body = `[BODY_NOT_READABLE: ${err.message}]`;
    }

    write({
      kind: 'response',
      ts: nowIso(),
      pageUrl: maskValue(page.url()),
      status: res.status(),
      statusText: res.statusText(),
      url: maskValue(url),
      resourceType: req.resourceType(),
      fromServiceWorker: res.fromServiceWorker(),
      headers: safeHeaders(res.headers()),
      body
    });

    const summary = summarizeEconetResponse(url, contentType, body);
    if (summary) {
      write({
        kind: 'response-summary',
        ts: nowIso(),
        pageUrl: maskValue(page.url()),
        summary
      });
    }
  });
}

async function registerPage(page) {
  attachNetworkCapture(page);

  page.on('framenavigated', (frame) => {
    if (frame !== page.mainFrame()) return;
    const url = frame.url();
    if (!isTarget(url)) return;
    write({
      kind: 'navigation',
      ts: nowIso(),
      pageUrl: page.url(),
      url: maskValue(url)
    });
  });

  page.on('popup', (popup) => {
    write({
      kind: 'popup-open',
      ts: nowIso(),
      openerUrl: maskValue(page.url()),
      popupUrl: maskValue(popup.url())
    });
    registerPage(popup).catch(() => {});
  });
}

(async () => {
  ensureDir(LOG_DIR);
  fs.writeFileSync(OUT_JSONL, '', 'utf8');

  let beforeSnapshot = null;
  let afterSnapshot = null;

  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--new-window', '--start-maximized']
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    serviceWorkers: 'block',
    ignoreHTTPSErrors: false,
    recordHar: {
      path: OUT_HAR,
      content: 'embed',
      mode: 'full'
    }
  });

  context.on('page', (newPage) => {
    write({
      kind: 'page-open',
      ts: nowIso(),
      url: maskValue(newPage.url())
    });
    registerPage(newPage).catch(() => {});
  });

  const page = await context.newPage();
  await registerPage(page);
  await page.bringToFront();

  await page.goto(START_URL, { waitUntil: 'domcontentloaded' });

  console.log('Econet aberta para captura manual.');
  console.log(`HAR sera salvo em: ${OUT_HAR}`);
  console.log(`JSONL sera salvo em: ${OUT_JSONL}`);
  console.log('Comandos:');
  console.log('  b + ENTER  => snapshot BEFORE');
  console.log('  a + ENTER  => snapshot AFTER');
  console.log('  c + ENTER  => context probe do estado atual');
  console.log('  q + ENTER  => finalizar, exportar HAR/JSONL/diff e fechar');
  console.log('Fluxo sugerido: capture BEFORE antes do login ou antes de abrir o CNAE alvo; capture AFTER depois de abrir CNAE, subabas, anexos e obrigacoes relevantes.');

  process.stdin.setEncoding('utf8');
  process.stdin.resume();

  process.stdin.on('data', async (chunk) => {
    const command = String(chunk || '').trim().toLowerCase();

    try {
      if (command === 'b') {
        beforeSnapshot = await captureStorageSnapshot(context, page, 'before');
        fs.writeFileSync(OUT_BEFORE, JSON.stringify(beforeSnapshot, null, 2), 'utf8');
        console.log(`Snapshot BEFORE salvo em: ${OUT_BEFORE}`);
        return;
      }

      if (command === 'a') {
        afterSnapshot = await captureStorageSnapshot(context, page, 'after');
        fs.writeFileSync(OUT_AFTER, JSON.stringify(afterSnapshot, null, 2), 'utf8');
        console.log(`Snapshot AFTER salvo em: ${OUT_AFTER}`);
        return;
      }

      if (command === 'c') {
        await captureContextProbe(context, page, 'manual');
        console.log('Context probe registrado no JSONL.');
        return;
      }

      if (command !== 'q') {
        console.log('Comando invalido. Use b, a, c ou q.');
        return;
      }

      if (!afterSnapshot) {
        afterSnapshot = await captureStorageSnapshot(context, page, 'after-final');
        fs.writeFileSync(OUT_AFTER, JSON.stringify(afterSnapshot, null, 2), 'utf8');
      }

      const diff = buildSnapshotDiff(beforeSnapshot, afterSnapshot);
      fs.writeFileSync(OUT_DIFF, JSON.stringify(diff, null, 2), 'utf8');

      write({
        kind: 'final-summary',
        ts: nowIso(),
        outputs: {
          jsonl: OUT_JSONL,
          har: OUT_HAR,
          before: beforeSnapshot ? OUT_BEFORE : null,
          after: OUT_AFTER,
          diff: OUT_DIFF
        },
        diffSummary: {
          hasChanges: diff.hasChanges,
          localStorageChanged: diff.localStorage.added.length + diff.localStorage.removed.length + diff.localStorage.changed.length,
          sessionStorageChanged: diff.sessionStorage.added.length + diff.sessionStorage.removed.length + diff.sessionStorage.changed.length,
          indexedDbChanged: diff.indexedDb.added.length + diff.indexedDb.removed.length + diff.indexedDb.changed.length,
          cookiesChanged: diff.cookies.added.length + diff.cookies.removed.length + diff.cookies.changed.length
        }
      });

      await context.close();
      await browser.close();

      console.log('Captura finalizada.');
      console.log(`HAR: ${OUT_HAR}`);
      console.log(`JSONL: ${OUT_JSONL}`);
      console.log(`AFTER: ${OUT_AFTER}`);
      console.log(`DIFF: ${OUT_DIFF}`);
      if (beforeSnapshot) {
        console.log(`BEFORE: ${OUT_BEFORE}`);
      }
      process.exit(0);
    } catch (err) {
      console.error(`Falha ao processar comando "${command}": ${err.message}`);
    }
  });
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
