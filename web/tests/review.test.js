// Node tests for web/portal/review.js pure functions (T6).
// Run: node --test web/tests/  (Node >= 18 with node:test).
// Fixtures are SYNTHETIC render inputs, not model output.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const R = require("../portal/review.js");

const VERIFIED = {
  claim_id: "c1", quote: "The hill marks the old route",
  statement: "Hill as route marker", interpretation: "A landmark claim",
  document_id: "d1", ambiguities: [], uncertainty: "low",
  quote_verified: true, provenance_status: "traced_supported",
};
const UNVERIFIED = {
  claim_id: "c2", quote: "Invented toll of fifty coins",
  statement: "A toll claim", interpretation: "A payment claim",
  document_id: "d1", ambiguities: ["no source"], uncertainty: "high",
  quote_verified: false, provenance_status: "unsupported",
};

test("statusLabel: proposal wording until a human decides", () => {
  assert.match(R.statusLabel("proposed"), /Proposal/);
  assert.match(R.statusLabel("accepted"), /Accepted by a human/);
  assert.match(R.statusLabel("rejected"), /Rejected by a human/);
  assert.match(R.statusLabel("disputed"), /Disputed by a human/);
  assert.match(R.statusLabel("nonsense"), /Proposal/); // safe fallback
});

test("itemStatus derives from decisions, latest wins, default proposed", () => {
  assert.strictEqual(R.itemStatus("c1", []), "proposed");
  const decisions = [
    { item_id: "c1", verdict: "dispute", status: "disputed" },
    { item_id: "c1", verdict: "accept", status: "accepted" },
    { item_id: "c9", verdict: "accept", status: "accepted" },
  ];
  assert.strictEqual(R.itemStatus("c1", decisions), "accepted");
});

test("consensusFor: no votes and single reviewer are not consensus", () => {
  assert.strictEqual(R.consensusFor("c1", []).verdict, null);
  const one = [{ item_id: "c1", reviewer: "ana", status: "accepted" }];
  assert.strictEqual(R.consensusFor("c1", one).verdict, null);
  assert.match(R.consensusFor("c1", one).label, /awaiting more reviewers/);
});

test("consensusFor: strict majority of distinct reviewers wins", () => {
  const decisions = [
    { item_id: "c1", reviewer: "ana", status: "accepted" },
    { item_id: "c1", reviewer: "boris", status: "accepted" },
    { item_id: "c1", reviewer: "cy", status: "disputed" },
  ];
  const c = R.consensusFor("c1", decisions);
  assert.strictEqual(c.total, 3);
  assert.strictEqual(c.verdict, "accepted");
  assert.match(c.label, /2 of 3/);
});

test("consensusFor: split vote has no consensus, latest per reviewer counts", () => {
  const split = [
    { item_id: "c1", reviewer: "ana", status: "accepted" },
    { item_id: "c1", reviewer: "boris", status: "rejected" },
  ];
  assert.strictEqual(R.consensusFor("c1", split).verdict, null);
  const changed = split.concat([{ item_id: "c1", reviewer: "boris", status: "accepted" }]);
  const c = R.consensusFor("c1", changed);
  assert.strictEqual(c.total, 2); // boris counted once, with his latest verdict
  assert.strictEqual(c.verdict, "accepted");
});

test("renderConsensusHtml shows reviewer chips and consensus badge", () => {
  const decisions = [
    { item_id: "c1", reviewer: "ana", status: "accepted" },
    { item_id: "c1", reviewer: "boris", status: "accepted" },
  ];
  const html = R.renderConsensusHtml("c1", decisions);
  assert.match(html, /Community consensus: accepted/);
  assert.match(html, /ana: accepted/);
  assert.match(html, /boris: accepted/);
});

test("canAccept: only verified quotes can be accepted", () => {
  assert.strictEqual(R.canAccept(VERIFIED), true);
  assert.strictEqual(R.canAccept(UNVERIFIED), false);
  assert.strictEqual(R.canAccept({ quotes_verified: true }), true);
  assert.strictEqual(R.canAccept(null), false);
});

test("formatQuote: trims, collapses whitespace, truncates", () => {
  assert.strictEqual(R.formatQuote("  a  b\n c "), "“a b c”");
  const long = R.formatQuote("x".repeat(400));
  assert.ok(long.length <= 282 && long.includes("…"));
});

test("renderClaimCard: unverified is red with disabled Accept", () => {
  const html = R.renderClaimCard(UNVERIFIED, []);
  assert.match(html, /unverified/);
  assert.match(html, /Quote NOT verified/);
  assert.match(html, /data-verdict="accept"[^>]*disabled/);
  // Reject / Dispute stay enabled for unverified items
  assert.doesNotMatch(html, /data-verdict="reject"[^>]*disabled/);
});

test("renderClaimCard: verified shows status and enabled Accept", () => {
  const html = R.renderClaimCard(VERIFIED, []);
  assert.match(html, /Quote verified in source/);
  assert.match(html, /Proposal — awaiting human decision/);
  assert.doesNotMatch(html, /data-verdict="accept"[^>]*disabled/);
  const decided = R.renderClaimCard(VERIFIED, [
    { item_id: "c1", verdict: "accept", status: "accepted" },
  ]);
  assert.match(decided, /Accepted by a human reviewer/);
});

test("renderClaimCard escapes model text (no HTML injection)", () => {
  const evil = { ...VERIFIED, quote: '<script>alert(1)</script>', interpretation: 'a & "b"' };
  const html = R.renderClaimCard(evil, []);
  assert.ok(!html.includes("<script>alert"));
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /a &amp; &quot;b&quot;/);
});

test("renderContradictionCard: both claims side by side, kind, alternatives", () => {
  const contra = {
    contradiction_id: "x1", claim_ids: ["c1", "c2"], kind: "temporal_mismatch",
    explanation: "1903 vs 1901", alternative_interpretations: ["closure took effect later"],
  };
  const byId = { c1: VERIFIED, c2: { ...UNVERIFIED, quote_verified: true } };
  const html = R.renderContradictionCard(contra, byId, []);
  assert.match(html, /Possible contradiction/);
  assert.match(html, /temporal_mismatch/);
  assert.match(html, /The hill marks the old route/);
  assert.match(html, /Invented toll of fifty coins/);
  assert.match(html, /Alternative interpretations: closure took effect later/);
});

test("renderDecisionHistory: empty state and recorded decisions", () => {
  assert.match(R.renderDecisionHistory([]), /No human decisions yet/);
  const html = R.renderDecisionHistory([
    { item_id: "c1", verdict: "accept", status: "accepted", reviewer: "ana", comment: "checked", recorded_at: "2026-10-28T12:00:00Z" },
  ]);
  assert.match(html, /ana/);
  assert.match(html, /checked/);
  assert.match(html, /Accepted by a human reviewer/);
});

test("stepStates: empty session activates sources, rest idle", () => {
  assert.deepStrictEqual(R.stepStates(null, [], 0),
    { sources: "active", proposals: "idle", quoteCheck: "idle", decision: "idle" });
});

test("stepStates: docs done, analysis done, decisions done", () => {
  const analysis = { provenance_check: { quotes_verified: 2, claims_total: 3 } };
  assert.deepStrictEqual(R.stepStates(analysis, [{}, {}], 2),
    { sources: "done", proposals: "done", quoteCheck: "done", decision: "done" });
});

test("stepStates: analysis without verified quotes keeps quote check active", () => {
  const analysis = { provenance_check: { quotes_verified: 0, claims_total: 2 } };
  const st = R.stepStates(analysis, [], 2);
  assert.strictEqual(st.quoteCheck, "active");
  assert.strictEqual(st.decision, "active");
});

test("orderItems: undecided proposals float up, decided sink, stable within groups", () => {
  const items = [
    { claim_id: "c1" }, { claim_id: "c2" }, { claim_id: "c3" },
  ];
  const decisions = [
    { item_id: "c1", verdict: "accept", status: "accepted" },
    { item_id: "c3", verdict: "dispute", status: "disputed" },
  ];
  const ordered = R.orderItems(items, decisions, (c) => c.claim_id);
  assert.deepStrictEqual(ordered.map((c) => c.claim_id), ["c2", "c1", "c3"]);
  assert.deepStrictEqual(items.map((c) => c.claim_id), ["c1", "c2", "c3"]); // input untouched in order
});

test("renderQuoteCheck: progress counts and jump links for unverified open items", () => {
  const claims = [VERIFIED, UNVERIFIED];
  const html = R.renderQuoteCheck(claims, [], {}, []);
  assert.match(html, /Quotes verified <b>1\/2<\/b>/);
  assert.match(html, /Needs attention \(1\)/);
  assert.match(html, /data-action="jump" data-item="c2"/);
  const clean = R.renderQuoteCheck([VERIFIED], [], {}, []);
  assert.match(clean, /Nothing needs attention/);
});

test("reviewerOptions: voters first, then free default names, no duplicates", () => {
  assert.deepStrictEqual(R.reviewerOptions([]), ["reviewer-1", "reviewer-2", "reviewer-3"]);
  assert.deepStrictEqual(
    R.reviewerOptions([{ reviewer: "boris" }, { reviewer: "ana" }, { reviewer: "boris" }]),
    ["boris", "ana", "reviewer-1", "reviewer-2", "reviewer-3"]
  );
  assert.deepStrictEqual(
    R.reviewerOptions([{ reviewer: "reviewer-2" }]),
    ["reviewer-2", "reviewer-1", "reviewer-3"]
  );
});

test("sourceInlineHtml: source with highlighted quote inside the card", () => {
  const docs = [{ document_id: "d1", title: "Local oral tradition", text: "Before. The hill marks the old route. After." }];
  const html = R.sourceInlineHtml(
    { claim_id: "c1", document_id: "d1", quote: "The hill marks the old route" }, docs);
  assert.match(html, /<details class="source-inline">/);
  assert.match(html, /document d1/);
  assert.match(html, /<mark>The hill marks the old route<\/mark>/);
  assert.strictEqual(R.sourceInlineHtml({ claim_id: "c1", document_id: "ghost", quote: "x" }, docs), "");
  assert.strictEqual(R.sourceInlineHtml({ claim_id: "c1", document_id: "d1", quote: "x" }, []), "");
});

test("splitDecided: open stays votable, decided moves to results", () => {
  const items = [{ claim_id: "c1" }, { claim_id: "c2" }];
  const split = R.splitDecided(items, [{ item_id: "c2", status: "accepted" }], (c) => c.claim_id);
  assert.deepStrictEqual(split.open.map((c) => c.claim_id), ["c1"]);
  assert.deepStrictEqual(split.decided.map((c) => c.claim_id), ["c2"]);
});

test("renderDecidedList: short rows only, no buttons at all", () => {
  const decisions = [
    { item_id: "c1", verdict: "accept", status: "accepted", reviewer: "ana", comment: "", recorded_at: "2026-10-31T15:52:50Z" },
  ];
  const html = R.renderDecidedList([VERIFIED], [], {}, decisions);
  assert.match(html, /Accepted by a human reviewer/);
  assert.match(html, /ana/);
  assert.match(html, /c1/);
  assert.ok(!html.includes("<article"), "decided list must not render full cards");
  assert.ok(!html.includes("<button"), "decided list must not render any buttons");
  assert.ok(!html.includes("data-verdict"), "decided list must not carry vote buttons");
  const empty = R.renderDecidedList([], [], {}, []);
  assert.match(empty, /Nothing decided yet/);
});

test("pendingFor: reviewer sees only items they have not voted on", () => {
  const items = [{ claim_id: "c1" }, { claim_id: "c2" }, { claim_id: "c3" }];
  const decisions = [
    { item_id: "c1", reviewer: "ana", status: "accepted" },
    { item_id: "c2", reviewer: "boris", status: "rejected" },
  ];
  const idOf = (c) => c.claim_id;
  assert.deepStrictEqual(R.pendingFor(items, decisions, "ana", idOf).map(idOf), ["c2", "c3"]);
  assert.deepStrictEqual(R.pendingFor(items, decisions, "boris", idOf).map(idOf), ["c1", "c3"]);
  assert.deepStrictEqual(R.pendingFor(items, decisions, "", idOf).map(idOf), ["c1", "c2", "c3"]);
});

test("visibleClaims: first 3 by default, all when expanded", () => {
  const open = [{ claim_id: "c1" }, { claim_id: "c2" }, { claim_id: "c3" }, { claim_id: "c4" }];
  assert.deepStrictEqual(R.visibleClaims(open, false).map((c) => c.claim_id), ["c1", "c2", "c3"]);
  assert.deepStrictEqual(R.visibleClaims(open, true).map((c) => c.claim_id), ["c1", "c2", "c3", "c4"]);
  assert.deepStrictEqual(R.visibleClaims([{ claim_id: "c1" }], false).map((c) => c.claim_id), ["c1"]);
  assert.strictEqual(R.MAX_VISIBLE_CLAIMS, 3);
});

test("errorMessage: 502 is understandable and non-technical first", () => {
  const msg = R.errorMessage(502);
  assert.match(msg, /model did not respond/i);
  assert.match(msg, /Nothing was saved/);
  assert.match(R.errorMessage(409), /cannot be accepted/);
  assert.match(R.errorMessage(422, "bad input"), /bad input/);
});
