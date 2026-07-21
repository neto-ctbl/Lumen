import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("integracoes exibe card do Acessorias sem mutacao externa", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page).toHaveURL(/\/lumen\/painel/);
  await page
    .getByRole("navigation", { name: "Rotas principais" })
    .getByRole("button", { name: /Integra/i })
    .click();

  await expect(page).toHaveURL(/\/lumen\/integracoes/);
  const acessoriasCard = page
    .getByRole("heading", { name: /Acess/i })
    .locator("xpath=ancestor::section[contains(@class, 'card')][1]");

  await expect(acessoriasCard.getByRole("heading", { name: /Acess/i })).toBeVisible();
  await expect(acessoriasCard.getByText(/^Configurar$/)).toBeVisible();
  await expect(acessoriasCard.getByText(/Nao configurada|Não configurada/)).toBeVisible();
  await expect(acessoriasCard.getByText(/Sem execucao|Sem execução/)).toBeVisible();

  const sittaxCard = page
    .getByRole("heading", { name: /Sittax/i })
    .locator("xpath=ancestor::section[contains(@class, 'card')][1]");
  await expect(sittaxCard.getByRole("heading", { name: /Sittax/i })).toBeVisible();
  await expect(sittaxCard.getByText(/Configurar|Nao iniciada|Não iniciada/)).toBeVisible();
  await expect(sittaxCard.getByText(/Nao configurada|Não configurada/)).toBeVisible();
  await expect(page.getByRole("button", { name: /sincronizar|executar|enviar|transmitir/i })).toHaveCount(0);

  await page
    .getByRole("navigation", { name: "Rotas principais" })
    .getByRole("button", { name: "Envios" })
    .click();
  await expect(page).toHaveURL(/\/lumen\/envios/);
});
