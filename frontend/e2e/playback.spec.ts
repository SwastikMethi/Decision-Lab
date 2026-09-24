import { test, expect, type APIRequestContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { PlaybackPage } from "../src/types";

async function createRun(request: APIRequestContext, large = false) {
  const values = large
    ? [
        {
          id: "large",
          family_id: "large",
          split: "development",
          domain: "support",
          primitive: "choice",
          variant: "base",
          state: "Find the correct category",
          question: {
            id: "q",
            type: "choice",
            instructions: "Choose a category",
            criteria: Object.fromEntries(
              Array.from({ length: 100 }, (_, i) => [
                `option_${i}`,
                `Category ${i}`,
              ]),
            ),
          },
          expected: { value: "option_99" },
        },
      ]
    : [
        {
          id: "choice",
          family_id: "choice",
          split: "development",
          domain: "support",
          primitive: "choice",
          variant: "base",
          state: "I paid twice for my subscription.",
          question: {
            id: "q",
            type: "choice",
            instructions: "Which team should handle this request?",
            criteria: {
              billing: "Billing and payments",
              technical: "Technical support",
              account: "Account access",
            },
          },
          expected: { value: "billing" },
        },
        {
          id: "noul",
          family_id: "noul",
          split: "development",
          domain: "support",
          primitive: "noul",
          variant: "base",
          state: "Please refund my payment.",
          question: {
            id: "q",
            type: "noul",
            instructions: "Is a refund requested?",
            criteria: "Yes if money is explicitly requested back",
          },
          expected: { value: true },
        },
        {
          id: "score",
          family_id: "score",
          split: "development",
          domain: "support",
          primitive: "score",
          variant: "base",
          state: "The whole service is down.",
          question: {
            id: "q",
            type: "score",
            instructions: "How severe is this issue?",
            criteria: ["Low", "Medium", "High"],
          },
          expected: { value: 2 },
        },
      ];
  const imported = await request.post("/api/v1/datasets/validate", {
    multipart: {
      file: {
        name: "playback.jsonl",
        mimeType: "application/x-ndjson",
        buffer: Buffer.from(values.map((v) => JSON.stringify(v)).join("\n")),
      },
    },
  });
  expect(imported.ok()).toBeTruthy();
  const dataset = await imported.json();
  expect(dataset.valid).toBe(true);
  const response = await request.post("/api/v1/runs", {
    data: {
      dataset_ref: dataset.dataset_id,
      name: "Watch a decision",
      mode: "fake",
      metrics: { bootstrap_samples: 10 },
      suites: {
        repeatability: { enabled: !large, sample_size: 1, repetitions: 2 },
        performance: {
          enabled: !large,
          sample_size: 1,
          concurrency: [1],
          batch_sizes: [5],
        },
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const { run_id } = await response.json();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/v1/runs/${run_id}`)).json()).status,
    )
    .toBe("completed");
  return run_id as string;
}

test("paired playback, controls, refresh, exact batch evidence and dark mode", async ({
  page,
  request,
}, testInfo) => {
  const run = await createRun(request);
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto(`/runs/${run}/live`);
  await expect(
    page.getByRole("heading", { name: "Decision playback" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Explore results" }),
  ).toBeVisible();
  await expect(page.locator(".case-position")).toHaveText("Comparison 1 / 6");
  await expect(
    page.getByLabel("Jev diagram").locator(".verdict-main strong"),
  ).toHaveText(/^(Correct|Incorrect)$/);
  await page.getByRole("button", { name: "Pause playback" }).click();
  await page.screenshot({
    path: testInfo.outputPath("live-paired.png"),
    fullPage: true,
    animations: "disabled",
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Next comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 2 / 6");
  await expect(
    page.getByRole("button", { name: "Play playback", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Playback speed").selectOption("4");
  await page.getByRole("button", { name: "Previous comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 1 / 6");
  await expect(
    page.getByRole("button", { name: "Play playback", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Jump to latest" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 6 / 6");
  await expect(page.getByText(/Batch example:/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Play playback", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Inspect", exact: true }).click();
  await expect(page.getByText("Selected playback request")).toBeVisible();
  await page.getByRole("tab", { name: "Raw", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByText(/"q_4"/).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.reload();
  await expect(page.locator(".case-position")).toHaveText("Comparison 6 / 6");
  await expect(page.getByLabel("Playback speed")).toHaveValue("4");
  await page
    .getByRole("button", { name: "Play playback", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Play playback", exact: true }),
  ).toBeVisible();
  // Pausing the final frame must resume its packet, not restart the input.
  await page.getByLabel("Playback speed").selectOption("1");
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page
    .getByRole("button", { name: "Play playback", exact: true })
    .click();
  await page.clock.runFor(1450);
  await page.getByRole("button", { name: "Pause playback" }).click();
  await page.clock.runFor(50); // Flush the paused animation frame.
  const packet = page.getByLabel("Jev diagram").locator(".answer-packet");
  const packetX = await packet.getAttribute("cx");
  await page.clock.runFor(5000);
  await expect(packet).toHaveAttribute("cx", packetX!);
  await page.screenshot({
    path: testInfo.outputPath("live-packet.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Play playback", exact: true })
    .click();
  await page.clock.runFor(100);
  await expect(
    page.getByLabel("Jev diagram").locator(".verdict-main strong"),
  ).toHaveText("Delivering answer");
  await page.clock.runFor(1600);
  await page.clock.resume();
  await page.getByRole("button", { name: "Dark appearance" }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("live-dark.png"),
    fullPage: true,
    animations: "disabled",
  });
  expect(browserErrors).toEqual([]);
  expect(
    (await (await request.get(`/api/v1/runs/${run}`)).json()).progress
      .completed,
  ).toBe(12);
});

test("large option lists, reduced motion, mobile, failures and sealed placeholders", async ({
  page,
  request,
}, testInfo) => {
  const run = await createRun(request, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/runs/${run}/live`);
  const jev = page.getByLabel("Jev diagram"),
    laya = page.getByLabel("Laya diagram");
  await expect(jev.locator(".diagram-option")).toHaveCount(100);
  const selected = await jev
    .locator(".diagram-option.is-selected")
    .boundingBox();
  const list = await jev.locator(".diagram-options").boundingBox();
  expect(selected!.y).toBeGreaterThanOrEqual(list!.y);
  expect(selected!.y + selected!.height).toBeLessThanOrEqual(
    list!.y + list!.height,
  );
  await jev.scrollIntoViewIfNeeded();
  await expect(jev.locator(".diagram-option.is-selected")).toBeInViewport();
  await expect(jev.locator(".verdict-main strong")).toHaveText(
    /^(Correct|Incorrect)$/,
  );
  expect((await laya.boundingBox())!.y).toBeGreaterThan(
    (await jev.boundingBox())!.y,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("live-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.route("**/playback?*", async (route) => {
    const response = await route.fetch(),
      data = await response.json();
    data.items[0].systems.laya = {
      evaluation_id: "laya-failed",
      state: "failed",
      selected: null,
      probabilities: {},
      correctness: null,
      latency_ms: 25,
      retry_count: 2,
      error: "Provider unavailable",
    };
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  await expect(laya.getByText("No valid response")).toBeVisible();
  await expect(laya.getByText("Provider unavailable")).toBeVisible();
  await page.unroute("**/playback?*");
  await page.route("**/playback?*", async (route) => {
    const response = await route.fetch(),
      data = await response.json();
    data.items = [{ ...data.items[0], sealed: true, case: null, systems: {} }];
    data.withheld_frames = 1;
    data.latest_available = null;
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  await expect(page.getByText("These results are still sealed")).toBeVisible();
  await expect(page.locator(".diagram-option")).toHaveCount(0);
});

test("previous and next cross sealed comparisons and page boundaries", async ({
  page,
  request,
}) => {
  const run = await createRun(request);
  const saved: PlaybackPage = await (
    await request.get(`/api/v1/runs/${run}/playback`)
  ).json();
  const frames = Array.from({ length: 23 }, (_, ordinal) => ({
    ...saved.items[0],
    key: `navigation:${ordinal}`,
    ordinal,
    ...([0, 18, 22].includes(ordinal)
      ? {}
      : { sealed: true, case: null, systems: {} }),
  }));
  await page.route("**/playback?*", async (route) => {
    const after = Number(
      new URL(route.request().url()).searchParams.get("after"),
    );
    const items = frames.slice(after + 1, after + 21);
    await route.fulfill({
      json: {
        ...saved,
        items,
        total_frames: frames.length,
        withheld_frames: 20,
        latest_available: 22,
        next_cursor: after + 21 < frames.length ? items.at(-1)!.ordinal : null,
      },
    });
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/runs/${run}/live`);
  await page.getByRole("button", { name: "Jump to latest" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 23 / 23");
  await page.getByRole("button", { name: "Previous comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 19 / 23");
  await page.getByRole("button", { name: "Previous comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 1 / 23");
  await page.getByRole("button", { name: "Next comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 19 / 23");
  await page.getByRole("button", { name: "Next comparison" }).click();
  await expect(page.locator(".case-position")).toHaveText("Comparison 23 / 23");
});

test("inspection refreshes pending requests without mislabeling them as incorrect", async ({
  page,
  request,
}) => {
  const run = await createRun(request);
  const saved: PlaybackPage = await (
    await request.get(`/api/v1/runs/${run}/playback`)
  ).json();
  const frame = saved.items[0];
  let released = false,
    reads = 0;
  await page.route(`**/api/v1/runs/${run}`, async (route) => {
    const response = await route.fetch(),
      data = await response.json();
    if (!released) {
      data.status = "running";
      data.ended_at = null;
    }
    await route.fulfill({ response, json: data });
  });
  await page.route(
    `**/api/v1/runs/${run}/cases/${frame.case!.id}`,
    async (route) => {
      reads++;
      const response = await route.fetch(),
        data = await response.json();
      if (!released) {
        data.predictions = {};
        data.all_predictions = [];
      }
      await route.fulfill({ response, json: data });
    },
  );
  await page.goto(`/runs/${run}/live`);
  await page.getByRole("button", { name: "Inspect", exact: true }).click();
  const drawer = page.getByRole("dialog");
  await expect(
    drawer.getByText("Awaiting result", { exact: true }),
  ).toHaveCount(2);
  await expect(drawer.getByText("Incorrect or failed")).toHaveCount(0);
  released = true;
  await expect(drawer.locator(".answer-card strong")).toHaveText([
    frame.systems.jev.selected!,
    frame.systems.laya.selected!,
  ]);
  await expect(
    drawer.getByText("Awaiting result", { exact: true }),
  ).toHaveCount(0);
  expect(reads).toBeGreaterThan(1);
});
