// Node tests for web/shared/supabase.js (read-only registry adapter).
// All offline: fetch is injected as a fake. Fixtures are SYNTHETIC rows.
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const S = require("../shared/supabase.js");

function fakeStorage(initial) {
  const data = Object.assign({}, initial || {});
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = v; },
    _data: data,
  };
}

test("config: query params win and are persisted", () => {
  const storage = fakeStorage();
  const cfg = S.fenSupabaseConfig({
    search: "?supabase_url=https://proj.supabase.co/&supabase_anon_key=sb_publishable_x",
    storage,
  });
  assert.strictEqual(cfg.url, "https://proj.supabase.co");
  assert.strictEqual(cfg.anonKey, "sb_publishable_x");
  assert.strictEqual(cfg.configured, true);
  assert.strictEqual(storage._data.fen_supabase_url, "https://proj.supabase.co/");
});

test("config: falls back to localStorage, then unconfigured", () => {
  const storage = fakeStorage({
    fen_supabase_url: "https://stored.supabase.co",
    fen_supabase_anon_key: "stored_key",
  });
  const cfg = S.fenSupabaseConfig({ search: "", storage });
  assert.strictEqual(cfg.url, "https://stored.supabase.co");
  assert.strictEqual(cfg.configured, true);

  const empty = S.fenSupabaseConfig({ search: "", storage: fakeStorage() });
  assert.deepStrictEqual(empty, { url: "", anonKey: "", configured: false });
});

test("headers carry apikey and bearer token", () => {
  const h = S.fenSupabaseHeaders({ url: "https://p.supabase.co", anonKey: "k" });
  assert.deepStrictEqual(h, {
    apikey: "k",
    Authorization: "Bearer k",
    Accept: "application/json",
  });
});

test("registry url points at the public view, newest first, with a cap", () => {
  const cfg = { url: "https://p.supabase.co", anonKey: "k", configured: true };
  assert.strictEqual(
    S.fenRegistryUrl(cfg, 25),
    "https://p.supabase.co/rest/v1/registry_public?select=*&order=recorded_at.desc&limit=25"
  );
  assert.match(S.fenRegistryUrl(cfg), /limit=100$/);
});

test("row normalisation is defensive", () => {
  const row = S.fenRegistryRow({
    item_id: "c1", item_type: "claim", statement: "s", quote: "q",
    document_id: "d1", reviewer: "ana", recorded_at: "2026-10-31T12:00:00Z",
    model_returned: "muse-spark-1.3", prompt_hash: "sha256:abc", quote_verified: true,
  });
  assert.strictEqual(row.itemId, "c1");
  assert.strictEqual(row.quoteVerified, true);
  const empty = S.fenRegistryRow(null);
  assert.strictEqual(empty.itemId, "");
  assert.strictEqual(empty.quoteVerified, false);
});

test("fetch uses the registry url and headers; maps rows", async () => {
  const cfg = { url: "https://p.supabase.co", anonKey: "k", configured: true };
  let seenUrl = null;
  let seenHeaders = null;
  const rows = await S.fenFetchRegistry(cfg, {
    limit: 5,
    fetchImpl: (url, init) => {
      seenUrl = url;
      seenHeaders = init.headers;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ item_id: "c1", statement: "s", quote_verified: true }]),
      });
    },
  });
  assert.match(seenUrl, /registry_public\?select=\*&order=recorded_at\.desc&limit=5$/);
  assert.strictEqual(seenHeaders.apikey, "k");
  assert.strictEqual(rows.length, 1);
  assert.strictEqual(rows[0].itemId, "c1");
});

test("fetch rejects on HTTP error and when unconfigured", async () => {
  const cfg = { url: "https://p.supabase.co", anonKey: "k", configured: true };
  await assert.rejects(
    S.fenFetchRegistry(cfg, {
      fetchImpl: () => Promise.resolve({ ok: false, status: 401 }),
    }),
    /HTTP 401/
  );
  await assert.rejects(
    S.fenFetchRegistry({ url: "", anonKey: "", configured: false }, {}),
    /not configured/
  );
});
