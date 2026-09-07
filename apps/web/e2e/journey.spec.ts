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
  for (let slot = 0; slot < 11; slot++) {
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
  const matchUrl = page.url();
  await page.getByRole("radio", { name: /Attack/ }).check();
  await page.getByRole("radio", { name: "Balanced", exact: true }).check();
  await page.reload();
  await expect(page.getByText("How do you play this?")).toBeVisible();
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
  for (let step = 0; step < 65; step++) {
    if (page.url().endsWith("/result")) break;
    const button = page.getByRole("button", { name: /^Play next/ });
    if (await button.count()) {
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith("/decisions") && r.request().method() === "POST",
      );
      await button.click();
      const state = (await (await response).json()).state;
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
  await expect(page).toHaveURL("http://localhost:3000/history");
  await expect(page.getByRole("link", { name: /IN PROGRESS/ })).toHaveAttribute(
    "href",
    `/match/${matchId}`,
  );
  await accessible(page);
  await page.getByRole("link", { name: /IN PROGRESS/ }).click();
  await expect(page.getByText("How do you play this?")).toBeVisible();
});
