import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("shell protegido mostra rotas principais e navega para envios", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page).toHaveURL(/\/lumen\/painel/);
  await expect(page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Painel" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Cockpit", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Envios" })).toBeVisible();

  await page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Envios" }).click();
  await expect(page).toHaveURL(/\/lumen\/envios/);
  await expect(page.getByText("Modo de leitura")).toBeVisible();
});
