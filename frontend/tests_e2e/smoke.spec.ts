import { expect, test } from "@playwright/test";

test("abre a tela inicial do Lumen em /lumen/painel", async ({ page }) => {
  await page.goto("/lumen/painel");

  await expect(page).toHaveURL(/\/lumen\/painel$/);
  await expect(page.getByText("Lumen Fiscal Cockpit")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Painel" })).toBeVisible();
});
