// Node tests for the Registry showcase in the simplified demo
// (web/portal/demo.js renderRegistryHtml). SYNTHETIC fixtures.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const D = require("../portal/demo.js");

test("renderRegistryHtml: empty registry explains where knowledge lands", () => {
  assert.match(D.renderRegistryHtml([], "http://localhost:8100"), /Registry is empty/);
  assert.match(D.renderRegistryHtml(null, ""), /Registry is empty/);
});

test("renderRegistryHtml: accepted record with quote and export link", () => {
  const html = D.renderRegistryHtml(
    [
      {
        item_id: "c1", statement: "lu is a person noun", quote: "lu [PERSON]",
        document_id: "d1", reviewer: "ana", recorded_at: "2026-10-31T12:00:00Z",
        voter_count: 2,
        votes: [
          { reviewer: "ana", verdict: "accept", status: "accepted", comment: "ok", recorded_at: "2026-10-31T12:00:00Z" },
          { reviewer: "boris", verdict: "accept", status: "accepted", comment: "", recorded_at: "2026-10-31T12:01:00Z" },
        ],
        export_path: "/records/c1?analysis_id=an_1",
      },
    ],
    "http://localhost:8100"
  );
  assert.match(html, /Accepted knowledge/);
  assert.match(html, /lu is a person noun/);
  assert.match(html, /decided by <b>2 reviewers<\/b>/);
  assert.match(html, /Who voted \(2 votes\)/);
  assert.match(html, /ana/);
  assert.match(html, /boris/);
  assert.match(html, /href="http:\/\/localhost:8100\/records\/c1\?analysis_id=an_1"/);
  assert.match(html, /Download record \(JSON-LD\)/);
});

test("renderRegistryHtml escapes registry fields", () => {
  const html = D.renderRegistryHtml(
    [{ item_id: "c1", statement: "<b>x</b>", quote: "q", document_id: "d1", reviewer: "<i>r</i>", recorded_at: "", export_path: "/records/c1" }],
    ""
  );
  assert.ok(!html.includes("<b>x</b>"));
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
});
