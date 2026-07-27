const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const START_URL = "https://www.econeteditora.com.br/";
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

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function isAllowedCookie(cookie) {
  return ALLOWED_DOMAINS.has(cookie.domain) && ALLOWED_COOKIE_NAMES.has(cookie.name);
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

  console.log("Login manual da Econet iniciado.");
  console.log("Conclua usuario, senha e CAPTCHA manualmente no navegador.");
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
