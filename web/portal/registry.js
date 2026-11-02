/**
 * Public registry page — reads accepted knowledge from Supabase.
 * New file on purpose: the demo/review pages are being edited elsewhere,
 * this page only depends on web/shared/supabase.js.
 */
(function (global) {
  "use strict";
  if (typeof document === "undefined") return;

  var esc = global.fenEscapeHtml || function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  function $(id) { return document.getElementById(id); }

  function render(rows, config) {
    var box = $("rows");
    if (!rows.length) {
      box.innerHTML = '<p class="note">No accepted knowledge yet. Accepted items appear here after a human '
        + "records the decision in the demo.</p>";
      return;
    }
    box.innerHTML = rows.map(function (r) {
      // Accepted knowledge still says when its evidence was not a primary
      // source — the database keeps the document provenance (migration 0003).
      var prov = String(r.provenance || "primary");
      var provBadge = prov === "primary" ? ""
        : '<span class="badge prov-' + esc(prov) + '">'
          + (prov === "synthetic" ? "SYNTHETIC source" : "SECONDARY source") + "</span>";
      return '<article class="entry">'
        + '<div class="head"><span class="badge">accepted</span>' + provBadge
        + '<span class="meta">' + esc(r.itemType) + " · " + esc(r.itemId) + "</span></div>"
        + '<p class="statement">' + esc(r.statement || r.quote) + "</p>"
        + (r.quote ? '<blockquote class="quote">' + esc(r.quote) + "</blockquote>" : "")
        + '<p class="meta">decided by <b>' + esc(r.reviewer) + "</b> · " + esc(r.recordedAt)
        + " · document " + esc(r.documentId || "—") + "</p>"
        + (r.comment ? '<p class="meta">comment: ' + esc(r.comment) + "</p>" : "")
        + '<p class="meta">model ' + esc(r.modelReturned || "—")
        + " · prompt " + esc((r.promptHash || "").slice(0, 18)) + "…"
        + " · quote verified: " + (r.quoteVerified ? "yes" : "no")
        + " · source provenance: " + esc(prov) + "</p>"
        + "</article>";
    }).join("");
  }

  // How often the page re-reads the public view. Polling, not Realtime:
  // Supabase Realtime is not enabled on views, and opening the base tables to
  // anon would defeat the RLS model. Tests shorten this via
  // window.FEN_REGISTRY_REFRESH_MS.
  var DEFAULT_REFRESH_MS = 20000;

  function refreshIntervalMs() {
    var custom = Number(global.FEN_REGISTRY_REFRESH_MS);
    return custom > 0 ? custom : DEFAULT_REFRESH_MS;
  }

  function clockLabel() {
    var d = new Date();
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function setup() {
    var config = global.fenSupabase.fenSupabaseConfig();
    var state = $("state");
    if (!config.configured) {
      state.innerHTML = 'Supabase is not configured. Open this page with '
        + '<code>?supabase_url=https://&lt;project&gt;.supabase.co&amp;supabase_anon_key=&lt;publishable key&gt;</code> '
        + "(or set them once in localStorage). The key is public by design: it can read only the "
        + "accepted-knowledge view.";
      return;
    }
    var firstLoad = true;
    var lastSignature = null;

    function load() {
      if (firstLoad) state.textContent = "Loading accepted knowledge from " + config.url + " …";
      return global.fenSupabase.fenFetchRegistry(config, { limit: 100 })
        .then(function (rows) {
          var signature = rows.map(function (r) {
            return r.itemId + "|" + r.recordedAt + "|" + r.provenance;
          }).join(",");
          // Re-render only when something actually changed, so a 20s poll does
          // not fight with a reader who is highlighting text.
          if (firstLoad || signature !== lastSignature) {
            render(rows, config);
            lastSignature = signature;
          }
          var seconds = Math.round(refreshIntervalMs() / 1000);
          state.textContent = rows.length + " accepted record(s) from " + config.url
            + " · updated " + clockLabel() + " · refreshes every " + seconds + "s";
          firstLoad = false;
        })
        .catch(function (err) {
          if (firstLoad) {
            state.innerHTML = '<span class="err">' + esc(err.message) + "</span> — check the URL and the "
              + "publishable key, and that the migrations in <code>supabase/migrations/</code> were applied.";
            return;
          }
          // A later poll failure must not wipe knowledge that is already shown.
          state.textContent = "Could not refresh (" + err.message + ") — showing the last successful read.";
        });
    }

    load().then(function () {
      global.setInterval(load, refreshIntervalMs());
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if ($("rows")) setup();
  });
})(typeof window !== "undefined" ? window : globalThis);
