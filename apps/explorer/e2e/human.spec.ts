import { test, expect } from "@playwright/test";
test("research data audit preserves declared session scope and never launches science", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Data Audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Research data audit", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Subject and session integrity" }),
  ).toContainText("session-a");
  await expect(
    page.getByRole("table", { name: "Subject and session integrity" }),
  ).toContainText("session-b");
  await expect(page.getByText("SYNTHETIC · NOT_RUN")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "External registration evidence" }),
  ).toBeVisible();
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_HUMAN_AUDIT === "1")
    await page.screenshot({
      path: "../../reports/milestone20/data-audit.png",
      fullPage: true,
    });
});
