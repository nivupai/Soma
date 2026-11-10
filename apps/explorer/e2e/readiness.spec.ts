import { test, expect } from "@playwright/test";
test("data audit keeps readiness evidence and blocked session comparison read-only", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Data Audit", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Scientific readiness gates",
      exact: true,
    }),
  ).toBeVisible();
  const table = page.getByRole("table", {
    name: "Scientific readiness requirements",
  });
  await expect(table).toContainText("BLOCKED");
  await expect(table).toContainText("INDETERMINATE");
  await expect(
    page.getByRole("table", { name: "Subject and session integrity" }),
  ).toContainText("session-a");
  await expect(
    page.getByRole("table", { name: "Subject and session integrity" }),
  ).toContainText("session-b");
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_READINESS === "1")
    await page.screenshot({
      path: "../../reports/milestone21/data-audit.png",
      fullPage: true,
    });
});
