// FAQ / user wiki e2e: static page served by status-api (/web).
// From web/: npx playwright test e2e/faq.spec.js
"use strict";
const { test, expect } = require("@playwright/test");

test("faq page loads, expands answers, and links the demo", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto("/web/portal/faq.html");
  await expect(page.locator("h1")).toContainText("User Wiki");
  await expect(page.locator(".toc a[href='#verdicts']")).toBeVisible();

  await page.click(".toc a[href='#verdicts']");
  await expect(page.locator("#verdicts")).toBeVisible();
  await expect(page.locator("#verdicts")).toContainText("What your vote means".slice(0, 0) || "Accept");

  const firstDetails = page.locator("#quotes details").first();
  await firstDetails.locator("summary").click();
  await expect(firstDetails).toContainText("traceability");

  await expect(page.locator("header a[href='/web/portal/demo.html']")).toBeVisible();
  expect(errors).toEqual([]);
});
