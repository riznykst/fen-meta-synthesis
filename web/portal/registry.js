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
    state.textContent = "Loading accepted knowledge from " + config.url + " …";
    global.fenSupabase.fenFetchRegistry(config, { limit: 100 })
      .then(function (rows) {
        state.textContent = rows.length + " accepted record(s) from " + config.url;
        render(rows, config);
      })
      .catch(function (err) {
        state.innerHTML = '<span class="err">' + esc(err.message) + "</span> — check the URL and the "
          + "publishable key, and that the migrations in <code>supabase/migrations/</code> were applied.";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if ($("rows")) setup();
  });
})(typeof window !== "undefined" ? window : globalThis);
