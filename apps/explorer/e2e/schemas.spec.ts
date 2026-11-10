import { test, expect } from "@playwright/test";

test("historical artifacts retain an explicit unversioned status", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await expect(
    page.getByText("Independent iid OLS calibration · Milestone14.1"),
  ).toBeVisible();
  await expect(page.getByText("Legacy / unversioned").first()).toBeVisible();
});

test("version and integrity errors remain visible in the artifact browser", async ({
  page,
}) => {
  // Wire-contract presentation fixture; actual integrity rejection is tested by the API suite.
  await page.route("**/api/experiments", (route) =>
    route.fulfill({
      json: [
        {
          id: "future",
          title: "Unsupported fixture",
          state: "INVALID",
          schema_name: "soma.result",
          schema_version: "99.0.0",
          validation_status: "UNSUPPORTED_VERSION",
          migration_status: "NOT_APPLIED",
          metrics: {},
          parameters: {},
          compatibility: {},
          checksums: {},
          figures: [],
          warnings: ["Unsupported schema; no numerical view permitted"],
        },
      ],
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await expect(page.getByText("Schema 99.0.0")).toBeVisible();
  await expect(
    page.getByText("Unsupported schema; no numerical view permitted"),
  ).toBeVisible();
  await expect(page.locator(".artifact-figure")).toHaveCount(0);
});
