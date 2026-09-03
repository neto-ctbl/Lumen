import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

type WatcherStatus = "NEVER_SEEN" | "RUNNING" | "DEGRADED" | "STOPPED" | "STALE";

async function openIntegrationsWithWatcher(page: Page, status: WatcherStatus) {
  await page.route("**/api/v1/lumen/integrations/watcher-health", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      status,
      reported_status: status === "NEVER_SEEN" ? null : status,
      received_at: "2026-09-03T12:00:00+00:00",
      last_error_code: null,
      counters: { pending_retry: 0 },
      token: "must-not-render",
      authorization: "must-not-render",
      relative_path: "must-not-render.pdf",
      organization_id: 999,
    }) });
  });
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.evaluate(() => {
    window.history.pushState({}, "", "/lumen/integracoes");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

test("S10.4 watcher health renders human statuses without sensitive payload", async ({ page }) => {
  await openIntegrationsWithWatcher(page, "NEVER_SEEN");
  const card = page.getByRole("heading", { name: "Watcher fiscal" }).locator("xpath=ancestor::section[contains(@class, 'card')][1]");
  await expect(card.getByText("Não iniciado", { exact: true })).toBeVisible();
  await expect(card.getByText("Online", { exact: true })).toHaveCount(0);
  await expect(card).not.toContainText("must-not-render");
});

for (const [status, label] of [["RUNNING", "Online"], ["DEGRADED", "Atenção"], ["STOPPED", "Parado"], ["STALE", "Offline"]] as const) {
  test(`S10.4 watcher health maps ${status} to ${label}`, async ({ page }) => {
    await openIntegrationsWithWatcher(page, status);
    const card = page.getByRole("heading", { name: "Watcher fiscal" }).locator("xpath=ancestor::section[contains(@class, 'card')][1]");
    await expect(card.getByText(label, { exact: true })).toBeVisible();
    if (status === "STALE") await expect(card.getByText("Online", { exact: true })).toHaveCount(0);
  });
}

test("S10.4 watcher health card remains readable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openIntegrationsWithWatcher(page, "RUNNING");
  const card = page.getByRole("heading", { name: "Watcher fiscal" }).locator("xpath=ancestor::section[contains(@class, 'card')][1]");
  await expect(card).toBeVisible();
  await expect.poll(() => page.locator("body").evaluate((body) => body.scrollWidth <= window.innerWidth)).toBe(true);
});
