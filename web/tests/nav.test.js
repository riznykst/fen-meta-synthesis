// Navigation consistency across the portal pages: one primary nav (the four
// hackathon-facing pages) and the pre-hackathon baseline demoted to the footer.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const PAGES = [
  "demo.html", "review.html", "registry.html", "faq.html",
  "index.html", "triadic.html", "candidate.html",
];

const PRIMARY = ["Demo", "Review", "Registry", "Wiki &amp; FAQ"];
const PRIMARY_HREFS = [
  "/web/portal/demo.html",
  "/web/portal/review.html",
  "/web/portal/registry.html",
  "/web/portal/faq.html",
];
const BASELINE_HREFS = ["/web/portal/index.html", "/web/portal/triadic.html"];

function read(name) {
  return fs.readFileSync(path.join(__dirname, "..", "portal", name), "utf-8");
}

for (const page of PAGES) {
  test(`${page}: primary nav has the same four links in the same order`, () => {
    const html = read(page);
    const nav = html.match(/<nav class="mainnav"[\s\S]*?<\/nav>/);
    assert.ok(nav, "missing primary nav");
    const labels = [...nav[0].matchAll(/>([^<>]+)<\/a>/g)].map((m) => m[1].trim());
    assert.deepStrictEqual(labels, PRIMARY);
    for (const href of PRIMARY_HREFS) {
      assert.ok(nav[0].includes(`href="${href}"`), `nav missing ${href}`);
    }
  });

  test(`${page}: baseline demos live in the footer, not the primary nav`, () => {
    const html = read(page);
    const nav = html.match(/<nav class="mainnav"[\s\S]*?<\/nav>/)[0];
    for (const href of BASELINE_HREFS) {
      assert.ok(!nav.includes(href), `${href} must not be in the primary nav`);
    }
    const footer = html.match(/<footer class="baseline-footer">[\s\S]*?<\/footer>/);
    assert.ok(footer, "missing baseline footer");
    for (const href of BASELINE_HREFS) {
      assert.ok(footer[0].includes(`href="${href}"`), `footer missing ${href}`);
    }
  });

  test(`${page}: at most one aria-current in the primary nav`, () => {
    const nav = read(page).match(/<nav class="mainnav"[\s\S]*?<\/nav>/)[0];
    const current = nav.match(/aria-current="page"/g) || [];
    assert.ok(current.length <= 1, `found ${current.length} aria-current`);
  });
}

test("each hackathon page marks itself current in the primary nav", () => {
  const expectations = {
    "demo.html": "/web/portal/demo.html",
    "review.html": "/web/portal/review.html",
    "registry.html": "/web/portal/registry.html",
    "faq.html": "/web/portal/faq.html",
  };
  for (const [page, href] of Object.entries(expectations)) {
    const nav = read(page).match(/<nav class="mainnav"[\s\S]*?<\/nav>/)[0];
    assert.match(nav, new RegExp(`href="${href}" aria-current="page"`), `${page} marks itself`);
  }
});

test("baseline pages mark themselves current in the footer", () => {
  for (const [page, href] of [["index.html", "/web/portal/index.html"], ["triadic.html", "/web/portal/triadic.html"]]) {
    const footer = read(page).match(/<footer class="baseline-footer">[\s\S]*?<\/footer>/)[0];
    assert.match(footer, new RegExp(`href="${href}" aria-current="page"`), `${page} footer current`);
  }
});
