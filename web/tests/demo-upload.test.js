// Node tests for document upload parsing in the simplified demo
// (web/portal/demo.js). Fixtures are SYNTHETIC file contents.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const D = require("../portal/demo.js");

test("parseUploadedFile: plain text becomes one titled document", () => {
  const docs = D.parseUploadedFile("archive-note.txt", "A 1901 note states the crossing closed.");
  assert.strictEqual(docs.length, 1);
  assert.strictEqual(docs[0].title, "archive-note");
  assert.match(docs[0].text, /1901 note/);
});

test("parseUploadedFile: JSON with documents[] expands to documents", () => {
  const content = JSON.stringify({
    documents: [
      { document_id: "d1", title: "First", text: "text one" },
      { document_id: "d2", text: "text two" },
    ],
  });
  const docs = D.parseUploadedFile("sources.json", content);
  assert.strictEqual(docs.length, 2);
  assert.strictEqual(docs[0].title, "First");
  assert.strictEqual(docs[1].title, "d2");
});

test("parseUploadedFile: single JSON document and invalid JSON fallback", () => {
  const single = D.parseUploadedFile("one.json", JSON.stringify({ title: "T", text: "body" }));
  assert.deepStrictEqual(single, [{ title: "T", text: "body" }]);
  // A .json file that is not JSON content is treated as plain text.
  const fallback = D.parseUploadedFile("notes.json", "plain text, not json");
  assert.strictEqual(fallback[0].text, "plain text, not json");
});

test("parseUploadedFile: rejects empty files and text-less JSON documents", () => {
  assert.throws(() => D.parseUploadedFile("empty.txt", "   "), /empty/);
  assert.throws(
    () => D.parseUploadedFile("bad.json", JSON.stringify({ documents: [{ title: "x" }] })),
    /has no text/
  );
});

test("uploadSizeError enforces the shared 30000 character analysis limit", () => {
  assert.strictEqual(D.uploadSizeError([{ text: "x".repeat(100) }]), null);
  const err = D.uploadSizeError([{ text: "x".repeat(20000) }, { text: "y".repeat(10001) }]);
  assert.match(err, /30000/);
  assert.match(err, /nothing was truncated/);
  assert.strictEqual(D.MAX_UPLOAD_DOCS, 3);
  assert.strictEqual(D.MAX_ANALYZE_CHARS, 30000);
});
