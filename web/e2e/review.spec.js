// Review screen e2e (improvement P2). The page is served by status-api
// (/web) and talks to the mock API on :8100; those API calls are intercepted
// with page.route so the test is deterministic and needs no live model —
// the fulfilled bodies are SYNTHETIC fixtures, not model output.
// Run against a live static stack (status-api up), from web/:
//   npx playwright test e2e/review.spec.js
"use strict";
const { test, expect } = require("@playwright/test");

const REVIEW = "/web/portal/review.html";
const CORS = { "Access-Control-Allow-Origin": "*" };

const ANALYSIS = {
  analysis_id: "an_e2e",
  status: "proposed",
  model: { provider: "meta", requested: "muse-spark-1.3", returned: "muse-spark-1.3" },
  prompt_hash: "sha256:e2e",
  created_at: "2026-10-28T12:00:00Z",
  latency_ms: 1,
  analysis: {
    claims: [
      {
        claim_id: "c1", quote: "The hill Koshary marks the old trade route",
        statement: "The hill Koshary marks the old trade route",
        interpretation: "A route landmark.", document_id: "d1",
        ambiguities: [], uncertainty: "low",
        review_recommendation: "proceed_to_human_review",
        quote_verified: true, provenance_status: "traced_supported",
      },
      {
        claim_id: "c2", quote: "Traders paid exactly fifty silver coins",
        statement: "A toll was paid",
        interpretation: "A payment claim.", document_id: "d1",
        ambiguities: [], uncertainty: "high",
        review_recommendation: "more_evidence_required",
        quote_verified: false, provenance_status: "unsupported",
      },
    ],
    contradictions: [],
    summary: "SYNTHETIC e2e fixture",
  },
  provenance_check: { claims_total: 2, quotes_verified: 1, problems: [], ok: false },
};

function collectPageErrors(page) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push("console.error: " + msg.text());
  });
  return errors;
}

test("review screen loads without JS errors and reveals the third document", async ({ page }) => {
  const errors = collectPageErrors(page);
  await page.goto(REVIEW);
  await expect(page.locator("h1")).toContainText("Review");
  await expect(page.locator("#analyzeBtn")).toBeVisible();
  await expect(page.locator("#doc3Block")).toBeHidden();
  await page.click("#addDocBtn");
  await expect(page.locator("#doc3Block")).toBeVisible();
  await expect(page.locator("#doc3")).toBeVisible();
  expect(errors).toEqual([]);
});

test("review flow: proposals, unverified lockout, highlight, human decision", async ({ page }) => {
  await page.route("**/analyze", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(ANALYSIS) })
  );
  await page.route("**/decisions", (route) =>
    route.fulfill({
      status: 201, contentType: "application/json", headers: CORS,
      body: JSON.stringify({ decision_id: "dec_e2e", recorded_at: "2026-10-28T12:01:00Z", event_published: true }),
    })
  );
  await page.route("**/provenance/**", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify({
        item_id: "c1", item_type: "claim", analysis_id: "an_e2e", status: "accepted",
        document: { document_id: "d1", title: "Local oral tradition", text: "The hill Koshary marks the old trade route." },
        documents: [], quotes: [{ document_id: "d1", quote: "The hill Koshary marks the old trade route" }],
        model_proposal: { model: { returned: "muse-spark-1.3" }, prompt_hash: "sha256:e2e", created_at: "2026-10-28T12:00:00Z" },
        decisions: [{ decision_id: "dec_e2e", reviewer: "reviewer-1", verdict: "accept", status: "accepted", comment: "", recorded_at: "2026-10-28T12:01:00Z" }],
        chain_complete: true,
      }),
    })
  );

  await page.goto(REVIEW);
  await page.click("#analyzeBtn");

  const verified = page.locator("article[data-item='c1']");
  const unverified = page.locator("article[data-item='c2']");
  await expect(verified).toBeVisible();
  await expect(verified).toContainText("Proposal — awaiting human decision");
  await expect(unverified).toContainText("Quote NOT verified");
  await expect(unverified.locator("[data-verdict='accept']")).toBeDisabled();
  await expect(verified.locator("[data-verdict='accept']")).toBeEnabled();

  // Highlight: the exact quote is marked inside the source document.
  await verified.locator("[data-action='highlight']").click();
  await expect(page.locator("#sourceView mark")).toHaveText("The hill Koshary marks the old trade route");

  // Human decision: only now may the status become accepted. The decided
  // card leaves the voting window and moves to the results as a short row.
  await verified.locator("[data-verdict='accept']").click();
  await expect(page.locator("#proposals article[data-item='c1']")).toHaveCount(0, { timeout: 10000 });
  const decided = page.locator('#decided [data-item="c1"]');
  await expect(decided).toContainText("Accepted by a human reviewer");
  await expect(decided.locator("button")).toHaveCount(0);
  await expect(page.locator("#history")).toContainText("reviewer-1");

  // Provenance chain renders model + prompt hash + decision (checked from
  // a still-open card; decided rows are button-free by design).
  await unverified.locator("[data-action='provenance']").click();
  await expect(page.locator("#provenance")).toContainText("sha256:e2e");
  await expect(page.locator("#provenance")).toContainText("muse-spark-1.3");
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
