import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function accessible(page: Page) {
  const violations = (
    await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze()
  ).violations;
  expect(
    violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        reason: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

async function setupXI(page: Page) {
  await page.goto("/play");
  await page.getByRole("button", { name: "Play as guest" }).click();
  await expect(page).toHaveURL(/\/draft\//);
  await expect(
    page.getByRole("button", { name: /^Select .+, .+, rating/ }).first(),
  ).toBeVisible();
  await accessible(page);
  await expect(page.locator(".player-card .player-attributes")).toHaveCount(0);
  await expect(page.locator(".player-card .attribute-track")).toHaveCount(0);
  await expect(page.locator(".player-card .playstyle")).toHaveCount(0);
  await expect(page.locator(".attribute-guide")).toHaveText(
    "Your approach controls scoring and risk. Adapt your plans to the chase.",
  );
  await expect(page.getByLabel("XI rating limits")).toContainText(
    "One batter and one all-rounder rated 90–100",
  );
  await page.screenshot({
    path: test.info().outputPath("draft.png"),
    fullPage: true,
  });
  for (let slot = 0; slot < 11; slot++) {
    const ratings = await page
      .locator(".player-card .rating")
      .allTextContents();
    expect(ratings).toHaveLength(5);
    for (const text of ratings) {
      const rating = parseInt(text, 10);
      expect(rating).toBeGreaterThanOrEqual(slot === 0 || slot === 6 ? 90 : 75);
      expect(rating).toBeLessThanOrEqual(
        slot === 0 || slot === 6 || slot === 5 || slot >= 8 ? 100 : 89,
      );
    }
    const card = page
      .getByRole("button", { name: /^Select .+, .+, rating/ })
      .first();
    await card.click();
    await expect(card).toHaveAttribute("aria-pressed", "true");
    if (slot < 10)
      await page.getByRole("button", { name: "Next position" }).click();
  }
  await page.getByRole("link", { name: "Set batting order" }).click();
  await expect(page).toHaveURL(/\/team\//);
  await expect(
    page.getByRole("button", { name: "Confirm XI & play" }),
  ).toBeVisible();
  await accessible(page);
  await expect(page.getByLabel("XI rating limits")).toContainText(
    "Core players5/5",
  );
  // Reordering must be available to keyboard users, without drag-and-drop.
  const move = page.getByRole("button", { name: /^Move .+ down$/ }).first();
  await move.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Confirm XI & play" }).click();
  await expect(page).toHaveURL(/\/match\//);
}

test("guest drafts, changes strategy, completes a chase and sees reconciled scorecard", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /One chase/ })).toBeVisible();
  await accessible(page);
  await page.screenshot({
    path: testInfo.outputPath("landing.png"),
    fullPage: true,
  });
  await setupXI(page);
  await expect(page.getByText("How do you play this?")).toBeVisible();
  await expect(
    page.getByText(/Bowlers adapt to repeated approaches/),
  ).toBeVisible();
  const matchUrl = page.url();
  await expect(page.getByRole("radio")).toHaveCount(3);
  await expect(page.locator(".bowler-current")).toBeVisible();
  await expect(page.locator(".bowler-current")).toContainText(
    /OVR · (Pace|Spin)/,
  );
  await expect(page.getByLabel("Chase context")).toContainText("Partnership");
  await expect(
    page.getByText("Two-over game plan", { exact: false }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Aggressive", exact: true }).check();
  await page.getByRole("radio", { name: "Balanced", exact: true }).check();
  await page.reload();
  await expect(page.getByText("How do you play this?")).toBeVisible();
  await expect(
    page.getByText(/Bowlers adapt to repeated approaches/),
  ).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(3);
  await expect(
    page.getByRole("radio", { name: "Balanced", exact: true }),
  ).toBeChecked();
  await page.screenshot({
    path: testInfo.outputPath("match.png"),
    fullPage: true,
  });
  const violations = (
    await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze()
  ).violations;
  expect(violations).toEqual([]);
  for (let step = 0; step < 90; step++) {
    if (page.url().endsWith("/result")) break;
    const button = page.getByRole("button", { name: /^Play next/ });
    if (await button.count()) {
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith("/decisions") && r.request().method() === "POST",
      );
      await button.click();
      const responseBody = await (await response).json();
      const state = responseBody.state;
      const event = responseBody.events.at(-1);
      expect(event.strategy).toBeTruthy();
      expect(event.deliveries.length).toBeGreaterThan(0);
      if (state.status === "LIVE") {
        expect(responseBody.rulesetVersion).toBe("v3.5");
        for (const [
          index,
          assessment,
        ] of responseBody.strategyAssessments.entries()) {
          const probability = assessment.wicketProbability;
          expect(probability).toBeGreaterThanOrEqual(0);
          expect(probability).toBeLessThanOrEqual(1);
          const risk = state.free_hit
            ? "0% · None"
            : `${(probability * 100).toFixed(1)}% · ${assessment.wicketRisk}`;
          if (state.free_hit) expect(probability).toBe(0);
          await expect(page.locator(".plan-card").nth(index)).toContainText(
            `Wicket risk: ${risk}`,
          );
        }
        await expect(page.getByRole("radio")).toHaveCount(3);
        expect(
          responseBody.strategyAssessments.map(
            (a: { strategy: string }) => a.strategy,
          ),
        ).toEqual(["DEFENSIVE", "BALANCED", "AGGRESSIVE"]);
        await expect(
          page
            .getByLabel("Last six deliveries, oldest first")
            .getByRole("listitem"),
        ).toHaveCount(state.recent_outcomes.length);
        if (event.interruption === "WICKET")
          await expect(page.getByRole("status")).toContainText("new batter");
        if (state.free_hit)
          await expect(page.getByRole("status")).toContainText("Free hit");
      }
      if (state.status !== "LIVE") {
        await expect(page).toHaveURL(/\/result$/);
        break;
      }
      await expect(
        page.getByRole("button", { name: /^Play next/ }),
      ).toBeEnabled();
    }
  }
  await expect(page).toHaveURL(`${matchUrl}/result`);
  await expect(
    page.getByRole("table", { name: "Your team batting performance" }),
  ).toBeVisible();
  await expect(page.getByText("MATCH COMPLETE", { exact: true })).toBeVisible();
  await accessible(page);
  await page.screenshot({
    path: testInfo.outputPath("result.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "View match history" }).click();
  await expect(page).toHaveURL(/\/history$/);
  await expect(page.locator(".history-card").first()).toHaveAttribute(
    "href",
    `${new URL(matchUrl).pathname}/result`,
  );
});

test("repeated Aggressive survives reload and completes with ordinary scoring", async ({
  page,
}) => {
  await setupXI(page);
  const matchUrl = page.url();
  await expect(
    page.getByText(/A single approach cannot score past 200/),
  ).toHaveCount(0);
  let final;
  let runs = 0;
  for (let step = 0; step < 90; step++) {
    await page.getByRole("radio", { name: "Aggressive", exact: true }).check();
    const response = page.waitForResponse(
      (r) => r.url().endsWith("/decisions") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /^Play next/ }).click();
    final = await (await response).json();
    expect(final.rulesetVersion).toBe("v3.5");
    expect(final.state.approaches_used).toEqual(["AGGRESSIVE"]);
    for (const delivery of final.events.at(-1).deliveries) {
      const values: Record<string, number> = {
        DOT: 0,
        ONE: 1,
        TWO: 2,
        THREE: 3,
        FOUR: 4,
        SIX: 6,
        WICKET: 0,
        WIDE: 1,
        NO_BALL: 1,
      };
      expect(delivery.runs).toBe(values[delivery.outcome]);
      runs += delivery.runs;
    }
    expect(final.state.runs).toBe(runs);
    if (final.state.status !== "LIVE") break;
    await expect(
      page.getByRole("button", { name: /^Play next/ }),
    ).toBeEnabled();
    if (step === 4) {
      await page.reload();
      await expect(
        page.getByRole("radio", { name: "Aggressive", exact: true }),
      ).toBeVisible();
    }
  }
  expect(final.state.status).not.toBe("LIVE");
  expect(final.state.status === "WON").toBe(final.state.runs >= final.target);
  await expect(page).toHaveURL(`${matchUrl}/result`);
  await accessible(page);
});

test("mocked Google sign-in claims guest match history", async ({ page }) => {
  await setupXI(page);
  const matchId = page.url().split("/").pop();
  await page.route("**/api/v1/auth/google/start", async (route) => {
    const response = await route.fetch({ maxRedirects: 0 });
    const state = new URL(response.headers().location).searchParams.get(
      "state",
    )!;
    await route.fulfill({
      response,
      status: 302,
      headers: {
        ...response.headers(),
        location: `http://localhost:8001/api/v1/auth/google/callback?state=${encodeURIComponent(state)}&code=e2e-google-code`,
      },
    });
  });
  await page.getByRole("link", { name: "Match history", exact: true }).click();
  await page.getByRole("link", { name: /Continue with Google/ }).click();
  await expect(page).toHaveURL(
    new URL("/history", test.info().project.use.baseURL).href,
  );
  await expect(page.getByRole("link", { name: /IN PROGRESS/ })).toHaveAttribute(
    "href",
    `/match/${matchId}`,
  );
  await accessible(page);
  await page.getByRole("link", { name: /IN PROGRESS/ }).click();
  await expect(page.getByText("How do you play this?")).toBeVisible();
  await expect(
    page.getByText(/Bowlers adapt to repeated approaches/),
  ).toBeVisible();
});
