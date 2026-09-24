import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("complete simulated workflow, refresh, inspect evidence, export", async ({
  page,
}, testInfo) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page
    .getByRole("link", { name: "New evaluation", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "New evaluation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Execution mode").selectOption("fake");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Start evaluation" }).click();
  await expect(page).toHaveURL(/\/runs\/.+\/live/);
  await page.reload();
  await expect(page.getByRole("link", { name: "Explore results" })).toBeVisible(
    { timeout: 45000 },
  );
  await page.getByRole("link", { name: "Explore results" }).click();
  await expect(
    page.getByRole("heading", { name: "Results overview" }),
  ).toBeVisible();
  await expect(page.locator(".skeletons")).toHaveCount(0);
  await expect(page.getByText(/Simulated outcomes/).first()).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("results.png"),
    fullPage: true,
    animations: "disabled",
  });
  const resultsUrl = page.url();
  for (const [view, title] of [
    ["Reliability", "Reliability & automation"],
    ["Robustness", "Behavioral robustness"],
    ["Methodology", "Methodology & reproducibility"],
  ]) {
    await page.getByRole("link", { name: view, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: title, level: 1 }),
    ).toBeVisible();
    await expect(page.locator(".skeletons")).toHaveCount(0);
    await page.screenshot({
      path: testInfo.outputPath(`${view.toLowerCase()}.png`),
      fullPage: true,
      animations: "disabled",
    });
    expect(
      (await new AxeBuilder({ page }).analyze()).violations.map((v) => ({
        id: v.id,
        targets: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
  }
  await page.goto(resultsUrl);
  await page.getByRole("button", { name: "Dark appearance" }).click();
  await expect(page.locator(".skeletons")).toHaveCount(0);
  expect(
    (await new AxeBuilder({ page }).analyze()).violations.map((v) => ({
      id: v.id,
      targets: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("results-dark.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Light appearance" }).click();
  await page.getByRole("link", { name: "Reliability", exact: true }).click();
  await page.getByLabel("Acceptable observed risk (%)").fill("5");
  await page.getByRole("link", { name: "Cases", exact: true }).click();
  await page
    .getByRole("button", { name: /Inspect case/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("tab", { name: "Raw" }).click();
  await expect(
    page.getByRole("dialog").getByText(/simulated-jev/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence" }).click();
  expect(browserErrors).toEqual([]);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export bundle" }).click();
  expect((await download).suggestedFilename()).toMatch(/decisionlab-.*\.zip/);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        reason: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});

test("mobile reduced motion keeps setup usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/new");
  await expect(
    page.getByRole("heading", { name: "New evaluation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByLabel("Execution mode")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).analyze()).violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        reason: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});

test("custom Choice-only dataset keeps domains selectable and absent primitives unavailable", async ({
  page,
  request,
}) => {
  const value = {
    id: "custom",
    family_id: "custom",
    split: "development",
    domain: "legal_help",
    primitive: "choice",
    variant: "base",
    state: { message: "Reset my password" },
    question: {
      id: "route",
      type: "choice",
      instructions: "Route this request",
      criteria: { reset: "Password reset", billing: "Payment question" },
    },
    expected: { value: "reset" },
  };
  const dataset = await request.post("/api/v1/datasets/validate", {
    multipart: {
      file: {
        name: "custom.jsonl",
        mimeType: "application/x-ndjson",
        buffer: Buffer.from(JSON.stringify(value)),
      },
    },
  });
  const created = await request.post("/api/v1/runs", {
    data: {
      dataset_ref: (await dataset.json()).dataset_id,
      mode: "fake",
      metrics: { bootstrap_samples: 10 },
    },
  });
  const runId = (await created.json()).run_id;
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${runId}`)).json()).status,
    )
    .toBe("completed");
  await page.goto(`/runs/${runId}/results`);
  await expect(
    page.getByRole("heading", { name: "Results overview" }),
  ).toBeVisible();
  await expect(page.locator(".skeletons")).toHaveCount(0);
  const primitiveChart = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", { name: "Correctness by primitive" }),
    })
    .locator("svg");
  await expect(primitiveChart.getByText("Choice", { exact: true })).toHaveCount(
    1,
  );
  await expect(primitiveChart.getByText("Noul", { exact: true })).toHaveCount(
    0,
  );
  await expect(primitiveChart.getByText("Score", { exact: true })).toHaveCount(
    0,
  );
  await page.getByLabel("Domain", { exact: true }).selectOption("legal_help");
  await expect(page).toHaveURL(/domain=legal_help/);
});
