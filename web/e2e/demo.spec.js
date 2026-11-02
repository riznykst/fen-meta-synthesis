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
  const recorded = [];
  await page.route("**/analyze", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(ANALYSIS) })
  );
  // Stateful stub: POST records a decision, GET returns what was recorded —
  // the page re-syncs votes after each vote, so an always-empty GET would
  // (correctly) wipe the local view.
  await page.route("**/decisions*", (route) => {
    const req = route.request();
    if (req.method() === "GET") {
      return route.fulfill({
        status: 200, contentType: "application/json", headers: CORS,
        body: JSON.stringify({ decisions: recorded }),
      });
    }
    const body = JSON.parse(req.postData() || "{}");
    recorded.push({
      decision_id: "dec_1", recorded_at: "2026-10-31T12:01:00Z",
      item_id: body.item_id, item_type: body.item_type, verdict: body.verdict,
      status: "accepted", reviewer: body.reviewer, comment: body.comment || "",
    });
    decided = true;
    return route.fulfill({
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
  await expect(page.locator("#decided")).toContainText("Accepted by a human reviewer");
  await expect(page.locator("#decided")).toContainText("c1");
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

test("EU AI Act preset: not-legal-advice banner, articles, synthetic commentary", async ({ page }) => {
  await page.goto(DEMO);
  await page.click("#dataset-eu-ai-act");
  await expect(page.locator("#datasetNote")).toContainText("Not legal advice");
  await expect(page.locator("#datasetNote")).toContainText("SYNTHETIC commentary");
  await expect(page.locator("#doc1")).toHaveValue(/Article 11/);
  await expect(page.locator("#doc2")).toHaveValue(/ending 10 years/);
  await expect(page.locator("#doc3Block")).toBeVisible();
  await expect(page.locator("#doc3")).toHaveValue(/Article 11 requires the technical documentation/);
  // The demo's key fact: Art 11 has no 10-year period, Art 18 does.
  const art11 = await page.locator("#doc1").inputValue();
  expect(art11.includes("10 years")).toBe(false);
});

test("EU AI Act: a claim from the synthetic commentary is badged SYNTHETIC", async ({ page }) => {
  const analysis = {
    analysis_id: "an_eu", status: "proposed",
    model: { provider: "meta", requested: "muse-spark-1.3", returned: "muse-spark-1.3" },
    prompt_hash: "sha256:eu", created_at: "2026-11-02T12:00:00Z", latency_ms: 1,
    analysis: {
      claims: [{
        claim_id: "c1",
        quote: "Article 11 requires the technical documentation to be kept for 10 years",
        statement: "Article 11 requires ten-year retention",
        interpretation: "A retention claim sourced from commentary.",
        document_id: "d3", ambiguities: [], uncertainty: "high",
        review_recommendation: "needs_expert_review",
        quote_verified: true, provenance_status: "traced_supported", provenance: "synthetic",
      }],
      contradictions: [], summary: "SYNTHETIC e2e fixture",
    },
    provenance_check: { claims_total: 1, quotes_verified: 1, problems: [], ok: true },
  };
  await page.route("**/analyze", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(analysis) })
  );
  await page.goto(DEMO);
  await page.click("#dataset-eu-ai-act");
  await page.click("#analyzeBtn");
  const card = page.locator("article[data-item='c1']");
  await expect(card).toContainText("SYNTHETIC source");
  await expect(card).toContainText("not a primary source");
});

// The page joins the newest analysis already on the server ("shared thread").
// Tests must start from a known state, so the analysis list is stubbed empty.
test.beforeEach(async ({ page }) => {
  await page.route("**/analyses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: CORS,
      body: JSON.stringify({ analyses: [] }),
    })
  );
});
