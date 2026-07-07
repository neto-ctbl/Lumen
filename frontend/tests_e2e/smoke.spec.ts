import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("faz login, entra no painel protegido e sai", async ({ page }) => {
  await page.goto("/login");

  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page).toHaveURL(/\/lumen\/painel$/);
  await expect(page.getByText("Lumen Fiscal Cockpit")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Painel" })).toBeVisible();
  await expect(page.getByText(adminEmail)).toBeVisible();

  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
