import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 15000 },
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1600, height: 1050 },
    headless: true,
    launchOptions: { args: ["--enable-unsafe-swiftshader"] },
  },
  webServer: [
    {
      cwd: "../..",
      command:
        "MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 .venv/bin/python -m uvicorn services.explorer_api.app:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/catalog",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
