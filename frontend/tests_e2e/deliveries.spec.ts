import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("envios mostra modos empresa e todas e permite abrir os seletores", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/lumen\/painel/);

  await page
    .getByRole("navigation", { name: "Rotas principais" })
    .getByRole("button", { name: "Envios" })
    .click();
  await expect(page).toHaveURL(/\/lumen\/envios/);
  await expect(page.getByRole("button", { name: "Empresa", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Todas" })).toBeVisible();

  await page.getByRole("button", { name: "Empresa", exact: true }).click();
  await page.getByRole("button", { name: "Todas" }).click();
  await expect(page.getByText("Tabela operacional de envios")).toBeVisible();

  const periodSelector = page.getByRole("button", { name: "Selecionar competencia" });
  await expect(periodSelector).toBeVisible();
  await periodSelector.click();
  await expect(page.locator(".period-calendar-grid")).toBeVisible();

  const companySelector = page.getByRole("button", { name: "Selecionar empresa" });
  await expect(companySelector).toBeVisible();
  await companySelector.click();
  await expect(page.getByLabel("Buscar empresa")).toBeVisible();
});
