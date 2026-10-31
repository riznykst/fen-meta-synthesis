// Candidate detail page e2e. The page is served by status-api (/web) and
// reads the mock API (:8100) + status API; both are intercepted with
// page.route (SYNTHETIC fixtures) so the test is deterministic.
// From web/: npx playwright test e2e/candidate.spec.js
"use strict";
const { test, expect } = require("@playwright/test");

const DETAIL = "/web/portal/candidate.html?id=annotation_1";
const CORS = { "Access-Control-Allow-Origin": "*" };

const CANDIDATES = {
  candidates: [
    {
      annotation_id: "annotation_1", document_id: "d123",
      entity_label: "Sokolowizna", status: "pending",
      votes: { validated: 1, disputed: 0, rejected: 0 },
      llm_recommendation: "validated",
      quorum: { votes: 1, required: 3, reached: false },
      qv: { votes: [], scores: {}, threshold: 10, reached: false },
      decision: null,
    },
  ],
  reputation: {}, reputation_history: [], llm_accuracy: {},
};

test("candidate detail explains the vote and records it", async ({ page }) => {
  await page.route("**/candidates", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(CANDIDATES) })
  );
  await page.route("**/api/v1/status/**", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify({ annotation_id: "annotation_1", found: false, validation_status: "unknown" }),
    })
  );
  let voted = null;
  await page.route("**/candidates/annotation_1/vote", (route) => {
    voted = JSON.parse(route.request().postData() || "{}");
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify({ votes: {}, quorum: { votes: 2, required: 3, reached: false } }),
    });
  });

  await page.goto(DETAIL);
  await expect(page.locator("h1")).toContainText("Candidate details");
  await expect(page.locator("#detail")).toContainText("You are voting on this entity");
  await expect(page.locator("#detail")).toContainText("Sokolowizna");
  await expect(page.locator("#detail")).toContainText("What your vote means");
  await expect(page.locator("#detail")).toContainText("decision-support only");

  await page.locator("[data-vote='annotation_1'][data-outcome='validated']").click();
  await expect(page.locator("#voteNote")).toContainText("Vote recorded");
  expect(voted).toEqual({ outcome: "validated" });
});

test("candidates list links to the detail page", async ({ page }) => {
  await page.route("**/candidates", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(CANDIDATES) })
  );
  await page.route("**/events", (route) => route.fulfill({ status: 200, headers: CORS, body: "" }));
  await page.goto("/web/portal/index.html");
  const link = page.locator("a[href*='candidate.html?id=annotation_1']");
  await expect(link).toBeVisible();
  await expect(link).toContainText("Details");
});

test("unknown candidate id shows a graceful not-found", async ({ page }) => {
  await page.route("**/candidates", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", headers: CORS, body: JSON.stringify(CANDIDATES) })
  );
  await page.route("**/api/v1/status/**", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", headers: CORS,
      body: JSON.stringify({ annotation_id: "ghost", found: false, validation_status: "unknown" }),
    })
  );
  await page.goto("/web/portal/candidate.html?id=ghost");
  await expect(page.locator("#detail")).toContainText("Candidate not found");
});
