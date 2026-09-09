import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("consulta fiscal navega e permanece somente leitura", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Consulta Fiscal" }).click();
  await expect(page).toHaveURL(/\/lumen\/consultas/);
  await expect(page.getByText("Base de referência global")).toBeVisible();
  await expect(page.getByRole("button", { name: "Consultar" })).toBeVisible();
});
