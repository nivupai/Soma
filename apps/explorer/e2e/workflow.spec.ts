import { test, expect } from "@playwright/test";
test("workflow DAG supports selection, lineage, zoom and keyboard navigation without submitting jobs", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Scientific workflow lineage" }),
  ).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(10);
  await expect(page.locator(".react-flow__edge")).toHaveCount(9);
  await page.getByText("Keyboard node navigator (10 nodes)").click();
  const button = page.getByRole("button", { name: "stage · psd", exact: true });
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("region", { name: "Selected workflow node" }),
  ).toContainText("eeg.psd");
  await page.getByLabel("Lineage direction").selectOption("downstream");
  await expect(
    page.getByRole("region", { name: "Selected workflow node" }),
  ).toContainText("bands");
  await page.getByRole("button", { name: "Fit workflow to view" }).click();
  await page.getByLabel("Select workflow").selectOption("demo-workflow-mri");
  await expect(page.locator(".react-flow__node")).toHaveCount(12);
  await expect(page.locator(".react-flow__edge")).toHaveCount(12);
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_WORKFLOW === "1")
    await page.screenshot({
      path: "../../reports/milestone18/workflow-explorer.png",
      fullPage: true,
    });
});
