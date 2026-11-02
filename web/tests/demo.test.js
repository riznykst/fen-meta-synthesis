// Node tests for the simplified demo page (web/portal/demo.js) and the
// ePSD2 dictionary badges in review.js. Fixtures are SYNTHETIC; dictionary
// facts come from the verified candidate register (CC BY-SA 3.0).
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const D = require("../portal/demo.js");
const R = require("../portal/review.js");

test("datasets: three presets with honest labels", () => {
  assert.deepStrictEqual(D.datasetIds().sort(), ["eu-ai-act", "sumerian", "synthetic"]);
  assert.match(D.getDataset("synthetic").note, /Synthetic demo documents/);
  assert.match(D.getDataset("sumerian").note, /CC BY-SA 3\.0/);
  assert.match(D.getDataset("sumerian").note, /not corpus records and not gold data/);
  const eu = D.getDataset("eu-ai-act");
  assert.match(eu.note, /Not legal advice/);
  assert.match(eu.note, /SYNTHETIC commentary/);
  assert.strictEqual(D.getDataset("nope"), null);
});

test("eu-ai-act dataset: articles are primary, commentary is synthetic", () => {
  const fields = D.datasetFieldValues("eu-ai-act");
  assert.strictEqual(fields.showDoc3, true);
  assert.match(fields.doc1, /technical documentation of a high-risk AI system/);
  assert.match(fields.doc2, /ending 10 years/);
  assert.match(fields.doc3, /Article 11 requires the technical documentation to be kept for 10 years/);
  assert.strictEqual(fields.doc1Provenance, "primary");
  assert.strictEqual(fields.doc2Provenance, "primary");
  assert.strictEqual(fields.doc3Provenance, "synthetic");

  // The demo case must hold: Art 18 has the 10-year period, Art 11 does not.
  assert.match(fields.doc2, /10 years/);
  assert.doesNotMatch(fields.doc1, /10 years/);

  const map = D.provenanceMapFromValues(fields);
  assert.deepStrictEqual(map, { d1: "primary", d2: "primary", d3: "synthetic" });
});

test("eu-ai-act inline texts stay in sync with eval/dataset sources", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const base = path.join(__dirname, "..", "..", "eval", "dataset", "eu-ai-act", "sources");
  const body = (name) =>
    fs.readFileSync(path.join(base, name), "utf-8").replace(/\r\n/g, "\n").split("---\n\n")[1].trim();
  const fields = D.datasetFieldValues("eu-ai-act");
  const norm = (s) => s.replace(/\s+/g, " ").trim();
  assert.strictEqual(norm(fields.doc1), norm(body("art11.md")));
  assert.strictEqual(norm(fields.doc2), norm(body("art18.md")));
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

test("dictionary badge renders inside claim cards with citation", () => {  const html = R.renderClaimCard(
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
