const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const START_URL = 'https://app.sittax.com.br/';
const TARGET_HOST_FRAGMENT = 'sittax.com.br';
const SCRIPT_DIR = __dirname;
const LOG_DIR = path.join(SCRIPT_DIR, 'logs');
const OUT_JSONL = path.join(LOG_DIR, 'sittax-network-log.jsonl');
const OUT_HAR = path.join(LOG_DIR, 'sittax-network.har');
const OUT_BEFORE = path.join(LOG_DIR, 'sittax-storage-before.json');
const OUT_AFTER = path.join(LOG_DIR, 'sittax-storage-after.json');
const OUT_DIFF = path.join(LOG_DIR, 'sittax-storage-diff.json');
const CONTEXT_ENDPOINT_PATTERNS = [
  /\/api\/apuracao\/retornar-apuracao-sittax/i,
  /\/api\/v2\/painel-contador\/valor-auditoria/i,
  /\/api\/painelprincipal\/retornar-dados-por-empresa/i,
  /\/api\/difal\/obter-valores-difal/i,
  /\/api\/nota-fiscal\/lista-nota-fiscal-(entrada|saida)-paginacao/i,
  /\/api\/tarefa\/paginacao/i
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function maskValue(value) {
  if (value == null) return value;

  let s = typeof value === 'string' ? value : JSON.stringify(value);

  s = s.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [MASKED]');
  s = s.replace(/"token"\s*:\s*"[^"]+"/gi, '"token":"[MASKED]"');
  s = s.replace(/"senha"\s*:\s*"[^"]+"/gi, '"senha":"[MASKED]"');
  s = s.replace(/"password"\s*:\s*"[^"]+"/gi, '"password":"[MASKED]"');
  s = s.replace(/"apiKeyAcessorias"\s*:\s*"[^"]+"/gi, '"apiKeyAcessorias":"[MASKED]"');
  s = s.replace(/Cookie:\s*.+/gi, 'Cookie: [MASKED]');
  s = s.replace(/([?&](?:token|access_token|id_token|refresh_token|jwt)=)[^&\s]+/gi, '$1[MASKED]');

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

function sanitizeUrl(url) {
  if (typeof url !== 'string' || !url) return url;
  return maskValue(url);
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
  fs.appendFileSync(OUT_JSONL, JSON.stringify(entry) + '\n', 'utf8');
}

function isTargetUrl(url) {
  return typeof url === 'string' && url.includes(TARGET_HOST_FRAGMENT);
}

function isContextEndpoint(url) {
  return typeof url === 'string' && CONTEXT_ENDPOINT_PATTERNS.some((pattern) => pattern.test(url));
}

function truncateText(value, max = 100000) {
  if (!value || value.length <= max) return value;
  return value.slice(0, max) + '\n...[TRUNCATED]...';
}

function stableStringify(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return '[' + value.map(stableStringify).join(',') + ']';
  }

  const keys = Object.keys(value).sort();
  return '{' + keys.map((key) => JSON.stringify(key) + ':' + stableStringify(value[key])).join(',') + '}';
}

function isJwtLike(value) {
  return typeof value === 'string' && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value);
}

function fingerprint(value) {
  const s = String(value || '');
  return s.length <= 16 ? s : `${s.slice(0, 8)}...${s.slice(-8)}`;
}

function collectJwtCandidates(source, value, out) {
  if (value == null) return;

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (isJwtLike(trimmed)) {
      out.push({
        source,
        type: 'jwt',
        fingerprint: fingerprint(trimmed),
        length: trimmed.length
      });
    }

    const bearerMatches = trimmed.match(/Bearer\s+([A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+)/gi) || [];
    for (const match of bearerMatches) {
      const token = match.replace(/^Bearer\s+/i, '');
      out.push({
        source,
        type: 'bearer',
        fingerprint: fingerprint(token),
        length: token.length
      });
    }

    const inlineJwtMatches = trimmed.match(/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g) || [];
    for (const token of inlineJwtMatches) {
      if (!isJwtLike(token)) continue;
      out.push({
        source,
        type: 'jwt-inline',
        fingerprint: fingerprint(token),
        length: token.length
      });
    }

    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        const parsed = JSON.parse(trimmed);
        collectJwtCandidates(`${source}.$parsed`, parsed, out);
      } catch (_) {}
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item, index) => collectJwtCandidates(`${source}[${index}]`, item, out));
    return;
  }

  if (typeof value === 'object') {
    for (const [key, inner] of Object.entries(value)) {
      collectJwtCandidates(`${source}.${key}`, inner, out);
    }
  }
}

function normalizeJwtCandidates(candidates) {
  const unique = new Map();
  for (const item of candidates) {
    unique.set(`${item.type}:${item.fingerprint}:${item.length}`, item);
  }
  return Array.from(unique.values()).sort((a, b) => {
    const left = `${a.type}:${a.fingerprint}:${a.length}`;
    const right = `${b.type}:${b.fingerprint}:${b.length}`;
    return left.localeCompare(right);
  });
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
  const index = (items) => {
    const map = new Map();
    for (const item of items) {
      map.set(`${item.name}|${item.domain}|${item.path}`, item);
    }
    return map;
  };

  const left = index(before);
  const right = index(after);
  const added = [];
  const removed = [];
  const changed = [];
  const keys = new Set([...left.keys(), ...right.keys()]);

  for (const key of Array.from(keys).sort()) {
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

async function captureContextProbe(context, page, reason) {
  const state = await page.evaluate(() => {
    const localKeys = Object.keys(window.localStorage || {});
    const sessionKeys = Object.keys(window.sessionStorage || {});
    return {
      url: window.location.href,
      title: document.title,
      localStorageKeys: localKeys,
      sessionStorageKeys: sessionKeys,
      localStorageCurrentUserPresent: Boolean(window.localStorage.getItem('currentUser')),
      localStorageCurrentCompanyHints: {
        empresa: window.localStorage.getItem('EmpresaSelecionada'),
        cnpj: window.localStorage.getItem('CnpjDaEmpresaSelecionada'),
        dataInicial: window.localStorage.getItem('DataInicialSelecionada')
      },
      sessionStorageCompanyHints: {
        empresa: window.sessionStorage.getItem('EmpresaSelecionada'),
        cnpj: window.sessionStorage.getItem('CnpjDaEmpresaSelecionada'),
        dataInicial: window.sessionStorage.getItem('DataInicialSelecionada')
      }
    };
  });

  const cookies = (await context.cookies())
    .filter((cookie) => isTargetUrl(`https://${cookie.domain.replace(/^\./, '')}${cookie.path}`))
    .map((cookie) => cookie.name)
    .sort();

  write({
    kind: 'context-probe',
    ts: nowIso(),
    reason,
    pageUrl: state.url,
    title: state.title,
    localStorageKeys: state.localStorageKeys,
    sessionStorageKeys: state.sessionStorageKeys,
    localStorageCurrentUserPresent: state.localStorageCurrentUserPresent,
    localStorageCompanyHints: sanitizeDeep(state.localStorageCurrentCompanyHints),
    sessionStorageCompanyHints: sanitizeDeep(state.sessionStorageCompanyHints),
    cookieNames: cookies
  });
}

function summarizeContextResponse(url, body) {
  if (!body) return null;
  try {
    const parsed = JSON.parse(body);
    if (!parsed || typeof parsed !== 'object') return null;
    if (/retornar-apuracao-sittax/i.test(url)) {
      return {
        endpoint: 'apuracao',
        ok: parsed.ok,
        status: parsed.status,
        companyCnpj: parsed.data?.empresaCnpj || parsed.data?.empresasApuracao?.[0]?.cnpj || null,
        periodDataInicial: parsed.data?.periodoFiscal?.dataInicial || null,
        companyName: parsed.data?.empresaNome || parsed.data?.empresasApuracao?.[0]?.nome || null
      };
    }
    if (/valor-auditoria/i.test(url)) {
      return {
        endpoint: 'valor-auditoria',
        ok: parsed.ok,
        status: parsed.status,
        dataKeys: parsed.data && typeof parsed.data === 'object' ? Object.keys(parsed.data).sort() : []
      };
    }
    if (/retornar-dados-por-empresa/i.test(url)) {
      return {
        endpoint: 'painelprincipal',
        sucesso: parsed.sucesso,
        mensagem: parsed.mensagem || null,
        nome: parsed.nome || null,
        alertasCount: Array.isArray(parsed.alertas) ? parsed.alertas.length : null
      };
    }
    if (/obter-valores-difal/i.test(url)) {
      return {
        endpoint: 'difal',
        sucesso: parsed.sucesso,
        mensagem: parsed.mensagem || null,
        possuiGuia: parsed.difal?.possuiGuia ?? null
      };
    }
    if (/lista-nota-fiscal-(entrada|saida)-paginacao/i.test(url)) {
      return {
        endpoint: /entrada/i.test(url) ? 'documentos-entrada' : 'documentos-saida',
        sucesso: parsed.sucesso,
        total: parsed.total ?? null,
        totalFiltrado: parsed.totalFiltrado ?? null,
        itens: Array.isArray(parsed.lista) ? parsed.lista.length : null
      };
    }
    if (/\/api\/tarefa\/paginacao/i.test(url)) {
      return {
        endpoint: 'tarefas',
        sucesso: parsed.sucesso,
        total: parsed.total ?? null,
        totalFiltrado: parsed.totalFiltrado ?? null,
        itens: Array.isArray(parsed.lista) ? parsed.lista.length : null
      };
    }
  } catch (_) {}
  return null;
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
      return {
        supported: false,
        databases: []
      };
    }

    const dbs = await indexedDB.databases();
    const databases = [];

    for (const dbInfo of dbs) {
      const name = dbInfo.name;
      if (!name) continue;

      const dbData = await new Promise((resolve) => {
        const openReq = indexedDB.open(name);
        openReq.onerror = () => {
          resolve({
            name,
            version: dbInfo.version || null,
            error: openReq.error ? openReq.error.message : 'open failed',
            objectStores: []
          });
        };
        openReq.onsuccess = () => {
          const db = openReq.result;
          const storeNames = Array.from(db.objectStoreNames);
          if (!storeNames.length) {
            db.close();
            resolve({
              name,
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
                name,
                version: db.version,
                objectStores: stores
              });
            }
          };

          storeNames.forEach((storeName) => {
            const store = tx.objectStore(storeName);
            const item = {
              name: storeName,
              keyPath: store.keyPath || null,
              autoIncrement: store.autoIncrement,
              indexes: Array.from(store.indexNames),
              records: []
            };

            const req = store.getAll();
            req.onsuccess = () => {
              item.records = req.result.slice(0, 200).map((record) => toSerializable(record));
              item.recordCount = req.result.length;
              stores.push(item);
              finish();
            };
            req.onerror = () => {
              item.error = req.error ? req.error.message : 'getAll failed';
              stores.push(item);
              finish();
            };
          });
        };
      });

      databases.push(dbData);
    }

    return {
      supported: true,
      databases
    };
  });
}

async function captureStorageSnapshot(context, page, label) {
  const pageSnapshot = await page.evaluate(() => {
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

  pageSnapshot.localStorage = Object.fromEntries(
    Object.entries(pageSnapshot.localStorage || {}).map(([key, value]) => [key, maskValue(value)])
  );
  pageSnapshot.sessionStorage = Object.fromEntries(
    Object.entries(pageSnapshot.sessionStorage || {}).map(([key, value]) => [key, maskValue(value)])
  );

  const indexedDb = sanitizeDeep(await captureIndexedDb(page));
  const cookies = (await context.cookies())
    .filter((cookie) => isTargetUrl(`https://${cookie.domain.replace(/^\./, '')}${cookie.path}`))
    .map(sanitizeCookie)
    .sort((a, b) => `${a.name}|${a.domain}|${a.path}`.localeCompare(`${b.name}|${b.domain}|${b.path}`));

  const jwtCandidates = [];
  collectJwtCandidates('localStorage', pageSnapshot.localStorage, jwtCandidates);
  collectJwtCandidates('sessionStorage', pageSnapshot.sessionStorage, jwtCandidates);
  collectJwtCandidates('indexedDB', indexedDb, jwtCandidates);
  collectJwtCandidates('cookies', cookies, jwtCandidates);

  const snapshot = {
    label,
    capturedAt: nowIso(),
    page: pageSnapshot,
    indexedDb,
    cookies,
    jwtCandidates: normalizeJwtCandidates(jwtCandidates)
  };

  write({
    kind: 'storage-snapshot',
    ts: snapshot.capturedAt,
    label,
    pageUrl: snapshot.page.url,
    localStorageKeys: Object.keys(snapshot.page.localStorage),
    sessionStorageKeys: Object.keys(snapshot.page.sessionStorage),
    indexedDbNames: snapshot.indexedDb.databases.map((db) => db.name),
    cookieCount: snapshot.cookies.length,
    jwtCandidates: snapshot.jwtCandidates
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
    cookies: diffCookies(before?.cookies, after?.cookies),
    jwtCandidates: diffKeyValueMap(
      Object.fromEntries((before?.jwtCandidates || []).map((item) => [`${item.type}:${item.fingerprint}:${item.length}`, item])),
      Object.fromEntries((after?.jwtCandidates || []).map((item) => [`${item.type}:${item.fingerprint}:${item.length}`, item]))
    )
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
    diff.cookies.changed.length > 0 ||
    diff.jwtCandidates.added.length > 0 ||
    diff.jwtCandidates.removed.length > 0 ||
    diff.jwtCandidates.changed.length > 0;

  return diff;
}

async function attachWebSocketCapture(page) {
  page.on('websocket', (ws) => {
    const url = ws.url();
    const interesting = isTargetUrl(url) || /signalr/i.test(url);
    const safeUrl = sanitizeUrl(url);

    write({
      kind: 'websocket-open',
      ts: nowIso(),
      url: safeUrl,
      interesting
    });

    ws.on('framesent', (event) => {
      if (!interesting) return;
      write({
        kind: 'websocket-frame-sent',
        ts: nowIso(),
        url: safeUrl,
        opcode: event.opcode,
        payload: truncateText(maskValue(event.payload))
      });
    });

    ws.on('framereceived', (event) => {
      if (!interesting) return;
      write({
        kind: 'websocket-frame-received',
        ts: nowIso(),
        url: safeUrl,
        opcode: event.opcode,
        payload: truncateText(maskValue(event.payload))
      });
    });

    ws.on('close', () => {
      if (!interesting) return;
      write({
        kind: 'websocket-close',
        ts: nowIso(),
        url: safeUrl
      });
    });

    ws.on('socketerror', (error) => {
      if (!interesting) return;
      write({
        kind: 'websocket-error',
        ts: nowIso(),
        url: safeUrl,
        error: error ? String(error) : 'unknown error'
      });
    });
  });

  const cdp = await contextForPage(page).newCDPSession(page);

  await cdp.send('Network.enable');

  cdp.on('Network.webSocketCreated', (event) => {
    if (!isTargetUrl(event.url) && !/signalr/i.test(event.url || '')) return;
    write({
      kind: 'cdp-websocket-created',
      ts: nowIso(),
      requestId: event.requestId,
      url: sanitizeUrl(event.url)
    });
  });

  cdp.on('Network.webSocketFrameSent', (event) => {
    if (!isTargetUrl(event.response?.payloadData || '') && !/signalr/i.test(event.response?.payloadData || '')) {
      write({
        kind: 'cdp-websocket-frame-sent',
        ts: nowIso(),
        requestId: event.requestId,
        opcode: event.response?.opcode,
        payload: truncateText(maskValue(event.response?.payloadData || ''))
      });
      return;
    }

    write({
      kind: 'cdp-websocket-frame-sent',
      ts: nowIso(),
      requestId: event.requestId,
      opcode: event.response?.opcode,
      payload: truncateText(maskValue(event.response?.payloadData || ''))
    });
  });

  cdp.on('Network.webSocketFrameReceived', (event) => {
    write({
      kind: 'cdp-websocket-frame-received',
      ts: nowIso(),
      requestId: event.requestId,
      opcode: event.response?.opcode,
      payload: truncateText(maskValue(event.response?.payloadData || ''))
    });
  });

  cdp.on('Network.webSocketClosed', (event) => {
    write({
      kind: 'cdp-websocket-closed',
      ts: nowIso(),
      requestId: event.requestId,
      timestamp: event.timestamp
    });
  });

  cdp.on('Network.webSocketWillSendHandshakeRequest', (event) => {
    if (!isTargetUrl(event.request?.url || '') && !/signalr/i.test(event.request?.url || '')) return;
    write({
      kind: 'cdp-websocket-handshake-request',
      ts: nowIso(),
      requestId: event.requestId,
      url: sanitizeUrl(event.request?.url),
      headers: safeHeaders(event.request?.headers || {})
    });
  });

  cdp.on('Network.webSocketHandshakeResponseReceived', (event) => {
    if (!isTargetUrl(event.response?.url || '') && !/signalr/i.test(event.response?.url || '')) return;
    write({
      kind: 'cdp-websocket-handshake-response',
      ts: nowIso(),
      requestId: event.requestId,
      url: sanitizeUrl(event.response?.url),
      status: event.response?.status,
      statusText: event.response?.statusText,
      headers: safeHeaders(event.response?.headers || {})
    });
  });
}

function contextForPage(page) {
  return page.context();
}

(async () => {
  ensureDir(LOG_DIR);
  fs.writeFileSync(OUT_JSONL, '', 'utf8');

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sittax-incognito-'));

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

  const page = await context.newPage();
  await page.bringToFront();

  await attachWebSocketCapture(page);

  page.on('framenavigated', (frame) => {
    if (frame !== page.mainFrame()) return;
    const url = frame.url();
    if (!isTargetUrl(url)) return;
    write({
      kind: 'navigation',
      ts: nowIso(),
      url: sanitizeUrl(url)
    });
  });

  page.on('request', async (req) => {
    const url = req.url();
    if (!isTargetUrl(url) && !/signalr/i.test(url)) return;

    let postData = null;
    try {
      postData = req.postData();
    } catch (_) {}

    const headers = req.headers();
    const jwtCandidates = [];
    collectJwtCandidates('request.headers', headers, jwtCandidates);
    collectJwtCandidates('request.postData', postData, jwtCandidates);

    write({
      kind: 'request',
      ts: nowIso(),
      method: req.method(),
      url: sanitizeUrl(url),
      resourceType: req.resourceType(),
      headers: safeHeaders(headers),
      postData: postData ? truncateText(maskValue(postData)) : null,
      jwtCandidates: normalizeJwtCandidates(jwtCandidates)
    });
  });

  page.on('response', async (res) => {
    const url = res.url();
    if (!isTargetUrl(url) && !/signalr/i.test(url)) return;

    const req = res.request();
    const contentType = res.headers()['content-type'] || '';
    let body = null;

    try {
      if (
        contentType.includes('application/json') ||
        contentType.includes('text/plain') ||
        contentType.includes('application/problem+json') ||
        contentType.includes('text/html') ||
        contentType.includes('javascript') ||
        contentType.includes('xml')
      ) {
        body = truncateText(maskValue(await res.text()));
      }
    } catch (err) {
      body = `[BODY_NOT_READABLE: ${err.message}]`;
    }

    const jwtCandidates = [];
    collectJwtCandidates('response.headers', res.headers(), jwtCandidates);
    if (body) collectJwtCandidates('response.body', body, jwtCandidates);

    write({
      kind: 'response',
      ts: nowIso(),
      status: res.status(),
      statusText: res.statusText(),
      url: sanitizeUrl(url),
      resourceType: req.resourceType(),
      fromServiceWorker: res.fromServiceWorker(),
      headers: safeHeaders(res.headers()),
      body,
      jwtCandidates: normalizeJwtCandidates(jwtCandidates)
    });

    if (isContextEndpoint(url)) {
      write({
        kind: 'context-response-summary',
        ts: nowIso(),
        url: sanitizeUrl(url),
        summary: summarizeContextResponse(url, body)
      });
      await captureContextProbe(context, page, `after:${url}`);
    }
  });

  page.on('console', (msg) => {
    const text = msg.text();
    if (!/signalr|websocket|hub/i.test(text)) return;
    write({
      kind: 'console',
      ts: nowIso(),
      type: msg.type(),
      text: truncateText(maskValue(text))
    });
  });

  await page.goto(START_URL, { waitUntil: 'domcontentloaded' });

  console.log('Sittax aberto em janela anonima.');
  console.log(`HAR sera salvo em: ${OUT_HAR}`);
  console.log(`JSONL sera salvo em: ${OUT_JSONL}`);
  console.log('Comandos:');
  console.log('  b + ENTER  => snapshot BEFORE');
  console.log('  a + ENTER  => snapshot AFTER');
  console.log('  c + ENTER  => context probe do estado atual');
  console.log('  q + ENTER  => finalizar, exportar HAR/JSONL/diff e fechar');
  console.log('Fluxo manual sugerido: capture BEFORE antes de selecionar empresa/competencia e AFTER logo depois do carregamento completo.');

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
          localStorageChanged: diff.localStorage.changed.length + diff.localStorage.added.length + diff.localStorage.removed.length,
          sessionStorageChanged: diff.sessionStorage.changed.length + diff.sessionStorage.added.length + diff.sessionStorage.removed.length,
          indexedDbChanged: diff.indexedDb.changed.length + diff.indexedDb.added.length + diff.indexedDb.removed.length,
          cookiesChanged: diff.cookies.changed.length + diff.cookies.added.length + diff.cookies.removed.length,
          jwtChanged: diff.jwtCandidates.changed.length + diff.jwtCandidates.added.length + diff.jwtCandidates.removed.length
        }
      });

      await context.close();
      await browser.close();
      fs.rmSync(userDataDir, { recursive: true, force: true });

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
