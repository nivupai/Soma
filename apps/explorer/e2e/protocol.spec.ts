import { test, expect } from "@playwright/test";
test("protocol histories compare recorded outcomes and expose drift without execution", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Protocols", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Research protocols", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Left execution", { exact: true })
    .selectOption("research-source-execution-1");
  await page
    .getByLabel("Right execution", { exact: true })
    .selectOption("research-source-execution-2");
  await expect(page.getByTestId("replay-status")).toHaveText(
    "NUMERICALLY_EQUIVALENT",
  );
  await expect(
    page.getByRole("img", { name: "Selected summary absolute drift" }),
  ).toBeVisible();
  await page
    .getByLabel("Right execution", { exact: true })
    .selectOption("research-source-execution-4");
  await expect(page.getByTestId("replay-status")).toHaveText("REJECTED");
  await page
    .getByLabel("Replay mode", { exact: true })
    .selectOption("EXPLORATORY");
  await expect(page.getByTestId("replay-status")).toHaveText(
    "EXPLORATORY_DESCRIPTIVE",
  );
  await page
    .getByLabel("Select protocol")
    .selectOption("research-source-protocol-1");
  await page
    .getByLabel("Compare protocol version")
    .selectOption("research-source-protocol-4");
  await expect(
    page.getByRole("region", { name: "Protocol version comparison" }),
  ).toContainText("SCIENTIFIC_AMENDMENT");
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_PROTOCOL === "1")
    await page.screenshot({
      path: "../../reports/milestone19/protocol-explorer.png",
      fullPage: true,
    });
});
