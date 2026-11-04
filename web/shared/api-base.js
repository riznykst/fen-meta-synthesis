/**
 * fenApiBase — ONE API-base override convention for the zero-build web
 * layer (TECH-DEBT P2 consolidation): query param (?key=...) wins and is
 * persisted, then localStorage, then the page default. Trailing slashes are
 * stripped. Portal views use this for fen_mock_base / fen_status_base.
 *
 * Options are injectable so Node tests can fake the browser bits:
 *   fenApiBase("fen_mock_base", "http://localhost:8100")            // browser
 *   fenApiBase("k", "fb", { search: "?k=QV", storage: fakeStorage }) // test
 */
(function (global) {
  "use strict";

  function defaults() {
    var search = "";
    var storage = null;
    try {
      if (global.location && global.location.search) search = global.location.search;
      storage = global.localStorage || null;
    } catch (e) { /* opaque origins throw on localStorage access */ }
    return { search: search, storage: storage };
  }

  function fenApiBase(key, fallback, opts) {
    var o = opts || defaults();
    var search = o.search || "";
    var storage = o.storage || null;
    var value = null;
    try {
      value = new URLSearchParams(search).get(key);
    } catch (e) { /* malformed search */ }
    if (value) {
      if (storage) { try { storage.setItem(key, value); } catch (e) { /* ignore */ } }
      return value.replace(/\/+$/, "");
    }
    if (storage) {
      try { value = storage.getItem(key); } catch (e) { /* ignore */ }
      if (value) return value.replace(/\/+$/, "");
    }
    return String(fallback == null ? "" : fallback).replace(/\/+$/, "");
  }

  // Hosted demo: /api/index is a single Vercel function, so the logical
  // endpoint travels as ?r=/analyze instead of a path segment. Local dev keeps
  // the plain path form against the FastAPI process on :8100.
  function fenApiUrl(base, path) {
    var clean = String(base == null ? "" : base).replace(/\/+$/, "");
    if (clean.slice(-10) === "/api/index") {
      var raw = String(path == null ? "" : path);
      var mark = raw.indexOf("?");
      var route = mark >= 0 ? raw.slice(0, mark) : raw;
      var extra = mark >= 0 ? raw.slice(mark + 1) : "";
      return clean + "?r=" + encodeURIComponent(route) + (extra ? "&" + extra : "");
    }
    return clean + path;
  }

  function fenDefaultMockBase() {
    try {
      var host = global.location && global.location.hostname;
      if (host === "localhost" || host === "127.0.0.1") return "http://localhost:8100";
      return global.location.origin + "/api/index";
    } catch (e) {
      return "http://localhost:8100";
    }
  }

  fenApiBase.url = fenApiUrl;
  fenApiBase.defaultMockBase = fenDefaultMockBase;

  if (typeof module !== "undefined" && module.exports) {
    module.exports = fenApiBase;
  } else {
    global.fenApiBase = fenApiBase;
    global.fenApiUrl = fenApiUrl;
    global.fenDefaultMockBase = fenDefaultMockBase;
  }
})(typeof window !== "undefined" ? window : globalThis);
