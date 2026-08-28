import { expect, test } from "@playwright/test";

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.local";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

test("painel, cockpit e integrações preservam leituras S9 como read-only", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page.getByText("DCTFWeb avaliada")).toBeVisible();
  await expect(page.getByText("Fator R calculado")).toBeVisible();

  await page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: "Cockpit", exact: true }).click();
  await expect(page.getByRole("columnheader", { name: "DCTFWeb" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Fator R" })).toBeVisible();

  await page.getByRole("navigation", { name: "Rotas principais" }).getByRole("button", { name: /Integra/i }).click();
  await expect(page.getByRole("heading", { name: "Domínio", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sittax" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Watcher Domínio" })).toBeVisible();
  await expect(page.getByRole("button", { name: /sincronizar|executar|enviar|transmitir/i })).toHaveCount(0);
});

test("empresa comunica leituras S9 e divergência de baixa confiança", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.route("**/api/v1/lumen/companies/999/summary?period=2026-07", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      company: { id: 999, cnpj: "00000000000000", razao_social: "Empresa sintética", nome_fantasia: null, apelido_pasta: null, inscricao_estadual: null, municipio: null, uf: null, active: true, regime_label: "Simples Nacional" },
      period: "2026-07", cnpj: "00000000000000", inscricao_estadual_display: "ISENTO", municipio_uf: "-", regime_label: "Simples Nacional",
      kpis: { obligations_total: 0, delivered_total: 0, pending_total: 0, divergences_total: 1, evidences_total: 0, installments_total: 0 }, obligations: [], evidences_preview: 0, divergences_preview: 1,
      dctfweb_origin: "DP", dctfweb_department: "DP", factor_r_status: "EFFECTIVE", factor_r_calculation_status: "COMPUTED", factor_r_reconciliation_status: "THRESHOLD_DIVERGENCE", factor_r_confidence: "LOW", factor_r_estimated: "0.29", factor_r_observed: "0.27",
      dominio_source_period: "2026-06",
    }) });
  });
  await page.route("**/api/v1/lumen/companies/999/dctfweb-origin?period=2026-07", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      company_id: 999, expected_origin: "DP", expected_department: "DP", dominio_coverage: "MOVEMENT_FOUND",
      dp_signal_present: true, reinf_signal_present: false, mit_signal_present: false, fiscal_signal_present: false,
      dctfweb_observed: true, classification_confidence: "HIGH", reason_codes: [], evaluated_at: "2026-07-31",
    }) });
  });
  await page.route("**/api/v1/lumen/companies/999/factor-r?period=2026-07", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      company_id: 999, applicability_status: "EFFECTIVE", calculation_status: "COMPUTED", fs12_confidence: "LOW",
      factor_r_estimated: "0.29", factor_r_sittax_observed: "0.27", factor_r_delta: "0.02",
      reconciliation_status: "THRESHOLD_DIVERGENCE", payroll_window_start: "2025-07-01", payroll_window_end: "2026-06-01",
      payroll_months_covered: 12, payroll_months_expected: 12,
    }) });
  });
  await page.route("**/api/v1/lumen/companies/999/dominio/payroll?sourcePeriod=2026-06", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      company_id: 999, source_period: "2026-06", assessment_period: "2026-07", coverage_status: "MOVEMENT_FOUND",
      match_status: "MATCHED", warning_codes: [], monetary_summary: { schema_version: 2, confidence: "LOW" },
      signals: { has_employee: true, has_pro_labore: false, has_autonomous: false, has_inss: true, has_fgts: true, has_termination: false, has_vacation: false, has_leave: false },
    }) });
  });
  await page.evaluate(() => {
    window.history.pushState({}, "", "/lumen/empresa/999?companyId=999&period=2026-07");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page.getByRole("heading", { name: "Origem DCTFWeb" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fator R" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Folha Domínio" })).toBeVisible();
  const factorRCard = page.getByRole("heading", { name: "Fator R" }).locator("xpath=ancestor::section[contains(@class, 'card')][1]");
  await expect(factorRCard.getByText("Divergência", { exact: true })).toBeVisible();
  await expect(factorRCard.getByText("Baixa confiança", { exact: true })).toBeVisible();
  await expect(factorRCard.getByText("0.29")).toBeVisible();
  await expect(factorRCard.getByText("0.27")).toBeVisible();
});

test("shell mantém leitura principal em viewport móvel", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Senha").fill(adminPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("DCTFWeb avaliada")).toBeVisible();
  await expect(page.getByText("Fator R calculado")).toBeVisible();
});
