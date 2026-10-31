// Simplified demo page e2e. Page served by status-api (/web); API calls to
// :8100 are intercepted (SYNTHETIC fixtures) for determinism.
// From web/: npx playwright test e2e/demo.spec.js
"use strict";
const { test, expect } = require("@playwright/test");

const DEMO = "/web/portal/demo.html";
const CORS = { "Access-Control-Allow-Origin": "*" };

const ANALYSIS = {
  analysis_id: "an_demo",
  status: "proposed",
  model: { provider: "meta", requested: "muse-spark-1.3", returned: "muse-spark-1.3" },
  prompt_hash: "sha256:demo",
  created_at: "2026-10-31T12:00:00Z",
  latency_ms: 1,
  analysis: {
    claims: [
      {
        claim_id: "c1", quote: "lu [PERSON] is listed as a noun",
        statement: "lu [PERSON] means person",
        interpretation: "A person term from the dictionary entry.",
        document_id: "d1", ambiguities: [], uncertainty: "low",
        review_recommendation: "proceed_to_human_review",
        quote_verified: true, provenance_status: "traced_supported",
      },
    ],
    contradictions: [],
    summary: "SYNTHETIC e2e fixture",
  },
  provenance_check: { claims_total: 1, quotes_verified: 1, problems: [], ok: true },
};

test("demo loads, dataset switcher fills Sumerian entries", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(DEMO);
  await expect(page.locator("h1")).toContainText("Human-Governed AI Synthesis");
  await expect(page.locator(".steps .step")).toHaveCount(4);
  await expect(page.locator("#doc1")).toHaveValue(/Koshary/);

  await page.click("#dataset-sumerian");
  await expect(page.locator("#doc1")).toHaveValue(/lu \[PERSON\]/);
  await expect(page.locator("#doc3Block")).toBeVisible();
  await expect(page.locator("#doc3")).toHaveValue(/me \[BEING\]/);
  await expect(page.locator("#datasetNote")).toContainText("not gold data");

  await page.click("#dataset-synthetic");
  await expect(page.locator("#doc1")).toHaveValue(/Koshary/);
  await expect(page.locator("#doc3Block")).toBeHidden();
  expect(errors).toEqual([]);
});

test("demo upload fills document fields from a file", async ({ page }) => {
  await page.goto(DEMO);
  await page.setInputFiles("#docUpload", {
    name: "my-source.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Uploaded text about a river crossing used by traders.", "utf-8"),
  });
  await expect(page.locator("#doc1")).toHaveValue(/Uploaded text about a river crossing/);
  await expect(page.locator("#doc1Title")).toHaveValue("my-source");
  await expect(page.locator("#uploadNote")).toContainText("Loaded 1 document(s) from my-source.txt");
});

test("demo registry shows accepted knowledge with a record export", async ({ page }) => {
  let decided = false;
  await page.route("**/analyze", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(ANALYSIS) })
  );
  await page.route("**/decisions", (route) => {
    decided = true;
    route.fulfill({
      status: 201, contentType: "application/json", headers: CORS,
      body: JSON.stringify({ decision_id: "dec_1", recorded_at: "2026-10-31T12:01:00Z", event_published: true }),
    });
  });
  await page.route("**/registry", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify({
        count: decided ? 1 : 0,
        records: decided
          ? [{
              analysis_id: "an_demo", item_id: "c1", item_type: "claim", status: "accepted",
              statement: "lu [PERSON] means person", quote: "lu [PERSON] is listed as a noun",
              document_id: "d1", reviewer: "reviewer-1", verdict: "accept", comment: "",
              recorded_at: "2026-10-31T12:01:00Z", decision_id: "dec_1",
              export_path: "/records/c1?analysis_id=an_demo",
            }]
          : [],
      }),
    })
  );
  await page.goto(DEMO);
  await expect(page.locator("#registry")).toContainText("Registry is empty");
  await page.click("#analyzeBtn");
  await page.locator("article[data-item='c1'] [data-verdict='accept']").click();
  await expect(page.locator("article[data-item='c1']")).toContainText("Accepted by a human reviewer");
  await expect(page.locator("#registry")).toContainText("Accepted knowledge", { timeout: 10000 });
  await expect(page.locator("#registry a.exp")).toHaveAttribute("href", /\/records\/c1/);
});

test("demo analysis shows proposals with the ePSD2 dictionary badge", async ({ page }) => {
  await page.route("**/analyze", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(ANALYSIS) })
  );
  await page.goto(DEMO);
  await page.click("#analyzeBtn");
  const card = page.locator("article[data-item='c1']");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Proposal — awaiting human decision");
  await expect(card.locator(".dict-badge")).toContainText("lu [PERSON] (N)");
  await expect(card.locator(".dict-badge")).toContainText("18,895 attestations");
});
