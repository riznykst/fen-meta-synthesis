// Node tests for the simplified demo page (web/portal/demo.js) and the
// ePSD2 dictionary badges in review.js. Fixtures are SYNTHETIC; dictionary
// facts come from the verified candidate register (CC BY-SA 3.0).
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const D = require("../portal/demo.js");
const R = require("../portal/review.js");

test("datasets: exactly synthetic and sumerian, with honest labels", () => {
  assert.deepStrictEqual(D.datasetIds().sort(), ["sumerian", "synthetic"]);
  assert.match(D.getDataset("synthetic").note, /Synthetic demo documents/);
  assert.match(D.getDataset("sumerian").note, /CC BY-SA 3\.0/);
  assert.match(D.getDataset("sumerian").note, /not corpus records and not gold data/);
  assert.strictEqual(D.getDataset("nope"), null);
});

test("datasetFieldValues: synthetic fills two docs, sumerian fills three", () => {
  const syn = D.datasetFieldValues("synthetic");
  assert.strictEqual(syn.showDoc3, false);
  assert.match(syn.doc1, /Koshary/);
  const sum = D.datasetFieldValues("sumerian");
  assert.strictEqual(sum.showDoc3, true);
  assert.match(sum.doc1, /lu \[PERSON\]/);
  assert.match(sum.doc1, /18,895 instances/);
  assert.match(sum.doc2, /bahar \[POTTER\]/);
  assert.match(sum.doc3, /me \[BEING\]/);
  assert.match(sum.doc3, /must not be merged/);
});

test("dictionaryEntryForClaim matches verified lemmas only", () => {
  const lu = R.dictionaryEntryForClaim({ quote: "lu [PERSON] is a noun", statement: "", interpretation: "" });
  assert.strictEqual(lu.id, "o0033207");
  const bahar = R.dictionaryEntryForClaim({ quote: "bahar means potter", statement: "", interpretation: "" });
  assert.strictEqual(bahar.id, "o0024835");
  // me is split by gloss hint: Being vs to be are different headwords
  const meN = R.dictionaryEntryForClaim({ quote: "me: Being, divine properties", statement: "", interpretation: "" });
  assert.strictEqual(meN.id, "o0034101");
  const meV = R.dictionaryEntryForClaim({ quote: "me means to be", statement: "", interpretation: "" });
  assert.strictEqual(meV.id, "o0034109");
  // unrelated text and substring traps do not match
  assert.strictEqual(R.dictionaryEntryForClaim({ quote: "The hill marks the route", statement: "", interpretation: "" }), null);
  assert.strictEqual(R.dictionaryEntryForClaim({ quote: "volume and plume", statement: "", interpretation: "" }), null);
  assert.strictEqual(R.dictionaryEntryForClaim(null), null);
});

test("dictionary badge renders inside claim cards with citation", () => {
  const html = R.renderClaimCard(
    {
      claim_id: "c1", quote: "lu [PERSON] is listed as a noun",
      statement: "lu is a person noun", interpretation: "A person term",
      document_id: "d1", ambiguities: [], uncertainty: "low",
      quote_verified: true, provenance_status: "traced_supported",
    },
    []
  );
  assert.match(html, /Dictionary \(ePSD2\)/);
  assert.match(html, /lu \[PERSON\] \(N\)/);
  assert.match(html, /18,895 attestations/);
  assert.match(html, /oracc\.org\/epsd2\/o0033207/);
  const plain = R.renderClaimCard(
    {
      claim_id: "c2", quote: "The hill marks the route", statement: "s",
      interpretation: "i", document_id: "d1", ambiguities: [],
      uncertainty: "low", quote_verified: true, provenance_status: "traced_supported",
    },
    []
  );
  assert.ok(!plain.includes("dict-badge"));
});
