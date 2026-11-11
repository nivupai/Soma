import { test, expect } from "@playwright/test";
test("EEG benchmark keeps human evidence separate from the read-only preview", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "EEG decoding benchmark", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "No configured completed aggregate benchmark. Protocol preview only; no performance or human inference is invented.",
    ),
  ).toBeVisible();
  const select = page.getByLabel("Select EEG benchmark");
  if (await select.locator('option[value="research-eeg-benchmark"]').count()) {
    await select.selectOption("research-eeg-benchmark");
    const table = page.getByRole("table", { name: "EEG model performance" });
    await expect(table).toContainText("cross-subject");
    await expect(table).toContainText("N=30");
    await page.getByLabel("EEG sensitivity").selectOption("filter_8_30");
    await expect(table).toContainText("csp_lda");
    if (process.env.CAPTURE_EEG_BENCHMARK === "1")
      await page.screenshot({
        path: "../../reports/milestone22/eeg-explorer.png",
        fullPage: true,
      });
  }
  expect(writes).toEqual([]);
});
