const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const START_URL = "https://www.econeteditora.com.br/";
const ENV_FILE = path.join(__dirname, "..", "..", ".env");
const OUT_DIR = path.join(__dirname, "..", "..", "backend", "storage", "sessions", "econet");
const OUT_FILE = path.join(OUT_DIR, "manual-storage-state.json");
const ALLOWED_DOMAINS = new Set([".econeteditora.com.br", "www.econeteditora.com.br"]);
const ALLOWED_COOKIE_NAMES = new Set([
  "bG0naW4",
  "bG9naW4",
  "cookiesession1",
  "operacional",
  "PHPSESSID",
  "usuariocopia",
  "spy_copia",
  "cross-site-cookie",
]);
const LOGIN_BUTTON_SELECTOR = ".btn-entrar[onclick='abreModalLogin()']";
const LOGIN_INPUT_SELECTOR = "#inputLogin";
const PASSWORD_INPUT_SELECTOR = "#inputPassword";

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function isAllowedCookie(cookie) {
  return ALLOWED_DOMAINS.has(cookie.domain) && ALLOWED_COOKIE_NAMES.has(cookie.name);
}

function loadDotenvFile(envPath) {
  if (!fs.existsSync(envPath)) {
    return;
  }
  const content = fs.readFileSync(envPath, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    const separatorIndex = line.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }
    const key = line.slice(0, separatorIndex).trim();
    if (!key || Object.prototype.hasOwnProperty.call(process.env, key)) {
      continue;
    }
    let value = line.slice(separatorIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

async function autofillCredentials(page) {
  loadDotenvFile(ENV_FILE);
  const login = (process.env.ECONET_LOGIN_CODE ?? process.env.ECONET_LOGIN ?? "").trim();
  const password = process.env.ECONET_LOGIN_PASSWORD ?? "";

  if (!login || !password) {
    return false;
  }

  const loginButton = page.locator(LOGIN_BUTTON_SELECTOR).first();
  if (await loginButton.count()) {
    await loginButton.click();
  }

  await page.waitForSelector(LOGIN_INPUT_SELECTOR, { timeout: 15000 });
  await page.waitForSelector(PASSWORD_INPUT_SELECTOR, { timeout: 15000 });
  await page.locator(LOGIN_INPUT_SELECTOR).fill(login);
  await page.locator(PASSWORD_INPUT_SELECTOR).fill(password);
  return true;
}

async function main() {
  ensureDir(OUT_DIR);
  const browser = await chromium.launch({
    headless: false,
    channel: "chrome",
    args: ["--new-window", "--start-maximized"],
  });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    serviceWorkers: "block",
  });
  const page = await context.newPage();
  await page.goto(START_URL, { waitUntil: "domcontentloaded" });

  let credentialsAutofilled = false;
  try {
    credentialsAutofilled = await autofillCredentials(page);
  } catch (error) {
    console.log("Nao foi possivel preencher automaticamente o login da Econet; siga com o preenchimento manual.");
  }

  console.log("Login manual da Econet iniciado.");
  if (credentialsAutofilled) {
    console.log("Usuario e senha foram preenchidos a partir do .env.");
    console.log("Resolva o CAPTCHA, confirme o login no navegador e depois volte ao terminal.");
  } else {
    console.log("Conclua usuario, senha e CAPTCHA manualmente no navegador.");
  }
  console.log("Depois volte ao terminal e pressione ENTER para exportar apenas os cookies permitidos.");

  process.stdin.setEncoding("utf8");
  process.stdin.resume();
  await new Promise((resolve) => process.stdin.once("data", resolve));

  const cookies = (await context.cookies())
    .filter((cookie) => isAllowedCookie(cookie))
    .map((cookie) => ({
      name: cookie.name,
      value: cookie.value,
      domain: cookie.domain,
      path: cookie.path,
      expires: cookie.expires,
      httpOnly: cookie.httpOnly,
      secure: cookie.secure,
      sameSite: cookie.sameSite,
    }));

  fs.writeFileSync(OUT_FILE, JSON.stringify({ cookies }, null, 2), "utf8");

  console.log(`Arquivo criado: ${OUT_FILE}`);
  console.log(`Quantidade de cookies: ${cookies.length}`);
  console.log(`Nomes dos cookies: ${cookies.map((cookie) => cookie.name).join(", ") || "(nenhum)"}`);
  console.log(`Dominios: ${Array.from(new Set(cookies.map((cookie) => cookie.domain))).join(", ") || "(nenhum)"}`);
  console.log(`Data de captura: ${new Date().toISOString()}`);
  console.log("Arquivo sensivel e temporario. Exclua manualmente apos a importacao na API.");

  await context.close();
  await browser.close();
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
