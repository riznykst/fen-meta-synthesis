// Node tests for quote highlighting in the Review screen (improvement P3).
// Run: node --test web/tests/  (Node >= 18 with node:test).
// Fixtures are SYNTHETIC strings, not model output or corpus data.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const R = require("../portal/review.js");

test("findQuoteRange locates an exact quote in the original text", () => {
  const text = "Before. The hill marks the old route. After.";
  const range = R.findQuoteRange(text, "The hill marks the old route");
  assert.deepStrictEqual(range, { start: 8, end: 36 });
  assert.strictEqual(text.slice(range.start, range.end), "The hill marks the old route");
});

test("findQuoteRange is tolerant to whitespace differences", () => {
  const text = "The hill\n  marks   the old\nroute here.";
  const range = R.findQuoteRange(text, "The hill marks the old route");
  assert.ok(range);
  assert.match(text.slice(range.start, range.end), /The hill\s+marks\s+the old\s+route/);
});

test("findQuoteRange returns null for an invented quote", () => {
  assert.strictEqual(R.findQuoteRange("real text only", "fifty silver coins"), null);
  assert.strictEqual(R.findQuoteRange("real text", ""), null);
  assert.strictEqual(R.findQuoteRange("", "anything"), null);
});

test("highlightQuoteHtml wraps only the located quote in <mark>", () => {
  const html = R.highlightQuoteHtml("Before. The hill marks the old route. After.", "The hill marks the old route");
  assert.strictEqual(html, "Before. <mark>The hill marks the old route</mark>. After.");
});

test("highlightQuoteHtml escapes document HTML — mark is the only markup", () => {
  const html = R.highlightQuoteHtml('A <script>alert(1)</script> and a "quote" here', 'a "quote" here');
  assert.ok(!html.includes("<script>"));
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /<mark>a &quot;quote&quot; here<\/mark>/);
});

test("highlightQuoteHtml without a located quote emits no mark", () => {
  const html = R.highlightQuoteHtml("plain <b>text</b>", "absent quote");
  assert.ok(!html.includes("<mark>"));
  assert.match(html, /&lt;b&gt;text&lt;\/b&gt;/);
});

test("renderClaimCard exposes the Show in source action", () => {
  const html = R.renderClaimCard(
    {
      claim_id: "c1", quote: "q", statement: "s", interpretation: "i",
      document_id: "d1", ambiguities: [], uncertainty: "low",
      quote_verified: true, provenance_status: "traced_supported",
    },
    []
  );
  assert.match(html, /data-action="highlight" data-item="c1"/);
  assert.match(html, /Show in source/);
});
