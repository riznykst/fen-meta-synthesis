// Node tests for web/portal/candidate.js pure functions (candidate details).
// Run: node --test web/tests/  (Node >= 18 with node:test).
// Fixtures are SYNTHETIC render inputs, not model output.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const C = require("../portal/candidate.js");

const CANDIDATE = {
  annotation_id: "annotation_1",
  document_id: "d123",
  entity_label: "Sokolowizna",
  status: "pending",
  votes: { validated: 2, disputed: 1, rejected: 0 },
  llm_recommendation: "validated",
  quorum: { votes: 3, required: 3, reached: true },
  qv: { votes: [{ voter: "ana", outcome: "validated", intensity: 2, comment: "Attested locally" }], scores: {}, threshold: 10, reached: false },
  decision: null,
};

test("candidateIdFromSearch parses and defaults safely", () => {
  assert.strictEqual(C.candidateIdFromSearch("?id=annotation_1&x=2"), "annotation_1");
  assert.strictEqual(C.candidateIdFromSearch(""), "");
  assert.strictEqual(C.candidateIdFromSearch("?other=1"), "");
});

test("findCandidate finds by annotation_id or returns null", () => {
  assert.strictEqual(C.findCandidate([CANDIDATE], "annotation_1"), CANDIDATE);
  assert.strictEqual(C.findCandidate([CANDIDATE], "nope"), null);
  assert.strictEqual(C.findCandidate(null, "annotation_1"), null);
});

test("quorumText covers classic quorum and QV threshold", () => {
  assert.match(C.quorumText(CANDIDATE), /3 of 3 votes — quorum reached/);
  const qvOnly = { quorum: {}, qv: { scores: { validated: 7 }, threshold: 10, reached: false } };
  assert.match(C.quorumText(qvOnly), /QV score 7 of 10 threshold — still open/);
});

test("renderCandidateDetail shows what is being voted on before voting", () => {
  const html = C.renderCandidateDetail(CANDIDATE, { found: false, validation_status: "unknown" });
  assert.match(html, /You are voting on this entity/);
  assert.match(html, /Sokolowizna/);
  assert.match(html, /decision-support only — not a vote/);
  assert.match(html, /validated 2 · disputed 1 · rejected 0/);
  assert.match(html, /Peer assessments/);
  assert.match(html, /Attested locally/);
  assert.match(html, /What your vote means/);
  // all three verdict buttons are offered while pending
  for (const o of ["validated", "disputed", "rejected"]) {
    assert.match(html, new RegExp('data-outcome="' + o + '"'));
  }
});

test("renderCandidateDetail: decided candidate closes voting and shows decision", () => {
  const decided = {
    ...CANDIDATE, status: "validated",
    decision: { outcome: "validated", decision_id: "g00042", decided_at: "2026-10-28T12:00:00Z", ledger_anchor: "0xMOCK1" },
  };
  const html = C.renderCandidateDetail(decided, {
    found: true, validation_status: "validated",
    governance_decision_id: "https://w3id.org/fen/id/decision/g00042",
    ledger_anchor: "0xMOCK1", provenance: [],
  });
  assert.match(html, /Voting is closed/);
  assert.match(html, /Recorded decision/);
  assert.match(html, /g00042/);
  assert.doesNotMatch(html, /data-outcome="validated"/);
});

test("renderCandidateDetail escapes candidate fields", () => {
  const evil = { ...CANDIDATE, entity_label: '<img src=x onerror=alert(1)>' };
  const html = C.renderCandidateDetail(evil, null);
  assert.ok(!html.includes("<img src=x"));
  assert.match(html, /&lt;img/);
});

test("renderCandidateDetail: unknown candidate and unavailable registry are graceful", () => {
  assert.match(C.renderCandidateDetail(null, null), /Candidate not found/);
  const html = C.renderCandidateDetail(CANDIDATE, { unavailable: true });
  assert.match(html, /registry read service is unavailable/);
  // voting controls still render despite the registry being down
  assert.match(html, /data-outcome="validated"/);
});
