/**
 * fenSupabase — read-only Supabase adapter for the public registry (zero-build).
 *
 * The publishable (anon) key is meant to be public: on the database side it
 * can only SELECT `registry_public` (accepted knowledge), never the source
 * documents and never any write (see supabase/migrations/0002_rls_and_rpc.sql).
 *
 * Configuration follows the shared fenApiBase convention: URL query params
 * win and are persisted, then localStorage, then the optional defaults:
 *
 *   ?supabase_url=https://<project>.supabase.co&supabase_anon_key=<publishable key>
 *
 * Pure functions are exported for Node tests; the browser wiring is inert.
 */
(function (global) {
  "use strict";

  var URL_KEY = "fen_supabase_url";
  var KEY_KEY = "fen_supabase_anon_key";
  // Short, user-facing query parameter names (what the registry page documents);
  // the `fen_`-prefixed names are also accepted and are what we persist.
  var URL_PARAM = "supabase_url";
  var KEY_PARAM = "supabase_anon_key";

  function defaults() {
    var search = "";
    var storage = null;
    try {
      if (global.location && global.location.search) search = global.location.search;
      storage = global.localStorage || null;
    } catch (e) { /* opaque origin */ }
    return { search: search, storage: storage };
  }

  function readParam(search, name) {
    try {
      return new URLSearchParams(search || "").get(name);
    } catch (e) {
      return null;
    }
  }

  function stripSlash(v) {
    return String(v || "").replace(/\/+$/, "");
  }

  /** { url, anonKey, configured } — configured is true only with both values. */
  function fenSupabaseConfig(opts) {
    var o = opts || defaults();
    var url = readParam(o.search, URL_PARAM) || readParam(o.search, URL_KEY);
    var anonKey = readParam(o.search, KEY_PARAM) || readParam(o.search, KEY_KEY);
    if (url && o.storage) { try { o.storage.setItem(URL_KEY, url); } catch (e) {} }
    if (anonKey && o.storage) { try { o.storage.setItem(KEY_KEY, anonKey); } catch (e) {} }
    if (!url && o.storage) { try { url = o.storage.getItem(URL_KEY); } catch (e) {} }
    if (!anonKey && o.storage) { try { anonKey = o.storage.getItem(KEY_KEY); } catch (e) {} }
    if (!url) url = o.defaultUrl || "";
    if (!anonKey) anonKey = o.defaultAnonKey || "";
    url = stripSlash(url);
    return { url: url, anonKey: anonKey || "", configured: !!(url && anonKey) };
  }

  /** Headers Supabase requires for REST reads with a publishable key. */
  function fenSupabaseHeaders(config) {
    return {
      apikey: config.anonKey,
      Authorization: "Bearer " + config.anonKey,
      Accept: "application/json",
    };
  }

  /** REST URL for the public registry, newest decision first. */
  function fenRegistryUrl(config, limit) {
    var max = Number(limit) > 0 ? Math.floor(Number(limit)) : 100;
    return config.url + "/rest/v1/registry_public?select=*&order=recorded_at.desc&limit=" + max;
  }

  /** Normalise one registry row for rendering (defensive about types). */
  function fenRegistryRow(row) {
    return {
      itemId: String((row && row.item_id) || ""),
      itemType: String((row && row.item_type) || "claim"),
      statement: String((row && row.statement) || ""),
      quote: String((row && row.quote) || ""),
      documentId: String((row && row.document_id) || ""),
      reviewer: String((row && row.reviewer) || ""),
      status: String((row && row.status) || ""),
      verdict: String((row && row.verdict) || ""),
      comment: String((row && row.comment) || ""),
      recordedAt: String((row && row.recorded_at) || ""),
      modelReturned: String((row && row.model_returned) || ""),
      promptHash: String((row && row.prompt_hash) || ""),
      quoteVerified: row ? row.quote_verified === true : false,
    };
  }

  /** Read the public registry. Resolves to normalised rows; rejects on HTTP error. */
  function fenFetchRegistry(config, options) {
    var opts = options || {};
    if (!config || !config.configured) {
      return Promise.reject(new Error("Supabase is not configured"));
    }
    var fetchImpl = opts.fetchImpl || (global.fetch ? global.fetch.bind(global) : null);
    if (!fetchImpl) return Promise.reject(new Error("fetch is not available"));
    return fetchImpl(fenRegistryUrl(config, opts.limit), {
      headers: fenSupabaseHeaders(config),
    }).then(function (resp) {
      if (!resp.ok) {
        throw new Error("Supabase registry request failed: HTTP " + resp.status);
      }
      return resp.json();
    }).then(function (rows) {
      return (Array.isArray(rows) ? rows : []).map(fenRegistryRow);
    });
  }

  var api = {
    fenSupabaseConfig: fenSupabaseConfig,
    fenSupabaseHeaders: fenSupabaseHeaders,
    fenRegistryUrl: fenRegistryUrl,
    fenRegistryRow: fenRegistryRow,
    fenFetchRegistry: fenFetchRegistry,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.fenSupabase = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
