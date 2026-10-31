// Registry page e2e (Supabase read-only view). All API calls are intercepted
// with page.route — SYNTHETIC rows, no network to Supabase needed.
"use strict";
const { test, expect } = require("@playwright/test");

const CORS = { "Access-Control-Allow-Origin": "*" };
const PAGE = "/web/portal/registry.html?supabase_url=https://demo.supabase.co&supabase_anon_key=sb_publishable_test";

test("registry page explains missing configuration", async ({ page }) => {
  await page.goto("/web/portal/registry.html");
  await expect(page.locator("#state")).toContainText("not configured");
  await expect(page.locator("#state")).toContainText("publishable key");
});

test("registry page renders accepted rows from the public view", async ({ page }) => {
  await page.route("**/rest/v1/registry_public**", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify([
        {
          item_id: "c1", item_type: "claim", status: "accepted",
          statement: "lu [PERSON] is a noun", quote: "lu [PERSON] is a noun",
          document_id: "d1", reviewer: "reviewer-1", verdict: "accept", comment: "checked",
          recorded_at: "2026-10-31T12:00:00Z", model_returned: "muse-spark-1.3",
          prompt_hash: "sha256:abcdef0123456789", quote_verified: true,
        },
      ]),
    })
  );
  await page.goto(PAGE);
  await expect(page.locator("#state")).toContainText("1 accepted record");
  await expect(page.locator("#rows")).toContainText("lu [PERSON] is a noun");
  await expect(page.locator("#rows")).toContainText("reviewer-1");
  await expect(page.locator("#rows")).toContainText("quote verified: yes");
});

test("registry page surfaces an HTTP error with guidance", async ({ page }) => {
  await page.route("**/rest/v1/registry_public**", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", headers: CORS, body: "{}" })
  );
  await page.goto(PAGE);
  await expect(page.locator("#state")).toContainText("HTTP 401");
  await expect(page.locator("#state")).toContainText("publishable key");
});
