/**
 * Review screen (T6) — human-governed AI synthesis, zero-build.
 *
 * Pure render/status functions are exported for Node tests
 * (web/tests/review.test.js); browser wiring runs only when a DOM exists.
 * Talks to the mock FEN API (web/api.md): POST /analyze, POST /decisions,
 * GET /provenance/{item_id}. Language rule: model output is always a
 * "Proposal"; a final status (accepted/rejected/disputed) appears only
 * after a recorded human decision — this file never invents one.
 */
(function (global) {
  "use strict";

  var HTML_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(s) {
    var shared = global.fenEscapeHtml;
    if (typeof shared === "function") return shared(s);
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return HTML_MAP[c]; });
  }

  var STATUS_LABELS = {
    proposed: "Proposal — awaiting human decision",
    accepted: "Accepted by a human reviewer",
    rejected: "Rejected by a human reviewer",
    disputed: "Disputed by a human reviewer",
  };
  var STATUS_BADGE = { proposed: "b-bl", accepted: "b-gr", rejected: "b-rd", disputed: "b-gd" };
  var VERDICT_STATUS = { accept: "accepted", reject: "rejected", dispute: "disputed" };

  function statusLabel(status) {
    return STATUS_LABELS[status] || STATUS_LABELS.proposed;
  }

  function itemStatus(itemId, decisions) {
    var status = "proposed";
    (decisions || []).forEach(function (d) {
      if (d.item_id === itemId && d.status) status = d.status;
      else if (d.item_id === itemId && d.verdict) status = VERDICT_STATUS[d.verdict] || status;
    });
    return status;
  }

  function canAccept(item) {
    if (!item) return false;
    if (typeof item.quote_verified === "boolean") return item.quote_verified;
    return !!item.quotes_verified;
  }

  function formatQuote(quote, maxLen) {
    var text = String(quote == null ? "" : quote).trim().replace(/\s+/g, " ");
    var limit = maxLen || 280;
    if (text.length > limit) text = text.slice(0, limit - 1).trimEnd() + "…";
    return "“" + text + "”";
  }

  // Locate `quote` inside `text`, tolerant to whitespace differences:
  // both sides are whitespace-collapsed while an index map remembers where
  // each collapsed character came from, so the returned range addresses the
  // ORIGINAL text. Returns {start, end} or null.
  function findQuoteRange(text, quote) {
    var source = String(text == null ? "" : text);
    var needleRaw = String(quote == null ? "" : quote).trim().replace(/\s+/g, " ");
    if (!needleRaw) return null;
    var collapsed = "";
    var indexMap = [];
    var pendingSpaceAt = -1;
    for (var i = 0; i < source.length; i++) {
      var ch = source[i];
      if (/\s/.test(ch)) {
        if (collapsed.length && pendingSpaceAt < 0) pendingSpaceAt = i;
        continue;
      }
      if (pendingSpaceAt >= 0) {
        collapsed += " ";
        indexMap.push(pendingSpaceAt);
        pendingSpaceAt = -1;
      }
      collapsed += ch;
      indexMap.push(i);
    }
    var at = collapsed.indexOf(needleRaw);
    if (at < 0) return null;
    var start = indexMap[at];
    var end = indexMap[at + needleRaw.length - 1] + 1;
    return { start: start, end: end };
  }

  // Escaped HTML of the document text with the located quote wrapped in
  // <mark>. The document and the quote are always escaped first — the mark
  // is the only markup this function emits.
  function highlightQuoteHtml(text, quote) {
    var source = String(text == null ? "" : text);
    var range = findQuoteRange(source, quote);
    if (!range) return esc(source);
    return esc(source.slice(0, range.start))
      + "<mark>" + esc(source.slice(range.start, range.end)) + "</mark>"
      + esc(source.slice(range.end));
  }

  function errorMessage(status, detail) {
    if (status === 502) {
      return "The model did not respond or returned an answer that could not be read (error 502). "
        + "Nothing was saved and no proposal was created — check that the model service is running, then try again.";
    }
    if (status === 422) {
      return "The documents were not accepted (error 422): " + (detail || "check that at least one document with text is provided and the total size is within the limit.");
    }
    if (status === 409) {
      return "This proposal cannot be accepted while its quote is unverified (error 409). You may still reject or dispute it.";
    }
    if (status === 404) {
      return "This item was not found (error 404). It may belong to an earlier analysis — run the analysis again.";
    }
    return "Request failed (error " + status + ")" + (detail ? ": " + detail : "");
  }

  function decisionButtons(itemId, itemType, item) {
    var acceptDisabled = canAccept(item) ? "" : " disabled title=\"Quote is not verified — acceptance is disabled\"";
    return '<div class="decision-row">'
      + '<button class="decision-btn accept" data-action="decide" data-verdict="accept" data-item="' + esc(itemId) + '" data-type="' + esc(itemType) + '"' + acceptDisabled + ">Accept</button>"
      + '<button class="decision-btn reject" data-action="decide" data-verdict="reject" data-item="' + esc(itemId) + '" data-type="' + esc(itemType) + '">Reject</button>'
      + '<button class="decision-btn dispute" data-action="decide" data-verdict="dispute" data-item="' + esc(itemId) + '" data-type="' + esc(itemType) + '">Dispute</button>'
      + '<button class="decision-btn prov" data-action="provenance" data-item="' + esc(itemId) + '">Provenance</button>'
      + "</div>"
      + '<input class="comment" id="comment-' + esc(itemId) + '" placeholder="Decision comment (optional)" aria-label="Decision comment">';
  }

  function renderClaimCard(claim, decisions) {
    var status = itemStatus(claim.claim_id, decisions);
    var verified = canAccept(claim);
    var classes = "item claim" + (verified ? "" : " unverified");
    var quoteNote = verified
      ? '<span class="badge b-gr">Quote verified in source</span>'
      : '<span class="badge b-rd">Quote NOT verified — acceptance disabled</span>';
    var amb = (claim.ambiguities || []).filter(function (a) { return a && String(a).trim(); });
    return '<article class="' + classes + '" data-item="' + esc(claim.claim_id) + '">'
      + '<div class="card-head"><span class="badge ' + (STATUS_BADGE[status] || "b-bl") + '">' + esc(statusLabel(status)) + "</span>"
      + '<span class="meta">Proposal ' + esc(claim.claim_id) + " · document " + esc(claim.document_id) + "</span></div>"
      + '<p class="statement">' + esc(claim.statement || claim.quote) + "</p>"
      + '<blockquote class="quote">' + esc(formatQuote(claim.quote)) + "</blockquote>"
      + '<p class="interp"><span class="lbl">Model interpretation (separate from the claim)</span>' + esc(claim.interpretation) + "</p>"
      + '<p class="meta">Uncertainty: ' + esc(claim.uncertainty) + " · provenance: " + esc(claim.provenance_status || "") + "</p>"
      + (amb.length ? '<p class="meta">Ambiguities: ' + amb.map(esc).join("; ") + "</p>" : "")
      + quoteNote
      + '<div class="decision-row"><button class="decision-btn prov" data-action="highlight" data-item="' + esc(claim.claim_id) + '">Show in source</button></div>'
      + decisionButtons(claim.claim_id, "claim", claim)
      + "</article>";
  }

  function renderContradictionCard(contra, claimsById, decisions) {
    var status = itemStatus(contra.contradiction_id, decisions);
    function mini(id) {
      var c = (claimsById || {})[id];
      if (!c) return '<div class="mini missing">Unknown claim ' + esc(id) + "</div>";
      return '<div class="mini"><span class="meta">Claim ' + esc(c.claim_id) + " · " + esc(c.document_id) + "</span>"
        + '<blockquote class="quote">' + esc(formatQuote(c.quote)) + "</blockquote>"
        + '<p class="interp">' + esc(c.interpretation) + "</p></div>";
    }
    var alts = (contra.alternative_interpretations || []).filter(function (a) { return a && String(a).trim(); });
    return '<article class="item contradiction" data-item="' + esc(contra.contradiction_id) + '">'
      + '<div class="card-head"><span class="badge b-gd">Possible contradiction</span>'
      + '<span class="badge ' + (STATUS_BADGE[status] || "b-bl") + '">' + esc(statusLabel(status)) + "</span>"
      + '<span class="meta">type: ' + esc(contra.kind) + "</span></div>"
      + '<p class="statement">' + esc(contra.explanation || "") + "</p>"
      + '<div class="contra-grid">' + (contra.claim_ids || []).map(mini).join("") + "</div>"
      + (alts.length
        ? '<p class="meta">Alternative interpretations: ' + alts.map(esc).join("; ") + "</p>"
        : "")
      + decisionButtons(contra.contradiction_id, "contradiction", contra)
      + "</article>";
  }

  function renderDecisionHistory(decisions) {
    if (!decisions || !decisions.length) {
      return '<p class="note">No human decisions yet — every item above is still a proposal.</p>';
    }
    return decisions.map(function (d) {
      return '<div class="history-item"><span class="badge ' + (STATUS_BADGE[d.status] || "b-bl") + '">'
        + esc(statusLabel(d.status || VERDICT_STATUS[d.verdict])) + "</span> "
        + "<b>" + esc(d.reviewer) + "</b> · " + esc(d.item_id)
        + (d.comment ? " — " + esc(d.comment) : "")
        + '<span class="meta"> ' + esc(d.recorded_at || "") + "</span></div>";
    }).join("");
  }

  var api = {
    esc: esc,
    statusLabel: statusLabel,
    itemStatus: itemStatus,
    canAccept: canAccept,
    formatQuote: formatQuote,
    errorMessage: errorMessage,
    renderClaimCard: renderClaimCard,
    renderContradictionCard: renderContradictionCard,
    renderDecisionHistory: renderDecisionHistory,
    findQuoteRange: findQuoteRange,
    highlightQuoteHtml: highlightQuoteHtml,
    VERDICT_STATUS: VERDICT_STATUS,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.FenReview = api;
  }

  // ---------------------------------------------------------- browser wiring
  if (typeof document === "undefined") return;

  var MOCK = global.fenApiBase ? global.fenApiBase("fen_mock_base", "http://localhost:8100") : "http://localhost:8100";
  var state = { analysis: null, decisions: [], documents: [] };
  function $(id) { return document.getElementById(id); }

  async function apiFetch(path, opts) {
    var resp = await fetch(MOCK + path, opts);
    if (!resp.ok) {
      var detail = "";
      try {
        var body = await resp.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || "");
      } catch (e) { /* non-JSON */ }
      var err = new Error(detail || ("HTTP " + resp.status));
      err.status = resp.status;
      throw err;
    }
    return resp.json();
  }

  function setBusy(text) {
    var el = $("analyzeState");
    if (el) el.textContent = text || "";
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = !!text;
  }

  function renderAll() {
    var box = $("proposals");
    if (!state.analysis) { box.innerHTML = ""; return; }
    var claims = state.analysis.analysis.claims || [];
    var contras = state.analysis.analysis.contradictions || [];
    var byId = {};
    claims.forEach(function (c) { byId[c.claim_id] = c; });
    box.innerHTML =
      claims.map(function (c) { return renderClaimCard(c, state.decisions); }).join("")
      + contras.map(function (x) { return renderContradictionCard(x, byId, state.decisions); }).join("");
    $("history").innerHTML = renderDecisionHistory(state.decisions);
    var pc = state.analysis.provenance_check || {};
    $("analysisMeta").textContent =
      "Analysis " + state.analysis.analysis_id + " · model " +
      ((state.analysis.model || {}).returned || (state.analysis.model || {}).requested || "") +
      " · quotes verified " + (pc.quotes_verified || 0) + "/" + (pc.claims_total || 0) +
      " · all items are proposals until you decide";
  }

  async function runAnalyze() {
    var docs = [];
    [1, 2, 3].forEach(function (n) {
      var field = $("doc" + n);
      if (!field) return;
      var text = field.value.trim();
      if (text) docs.push({ document_id: "d" + n, title: $("doc" + n + "Title").value.trim() || null, text: text });
    });
    $("reviewError").textContent = "";
    if (!docs.length) {
      $("reviewError").textContent = errorMessage(422, "add at least one document with text.");
      return;
    }
    setBusy("Waiting for the model… (documents are being analysed; nothing is decided yet)");
    try {
      var result = await apiFetch("/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ documents: docs }),
      });
      state.analysis = result;
      state.documents = docs;
      state.decisions = [];
      renderAll();
    } catch (e) {
      $("reviewError").textContent = errorMessage(e.status || 502, e.message);
    }
    setBusy("");
  }

  async function decide(itemId, itemType, verdict) {
    if (!state.analysis) return;
    var commentEl = $("comment-" + itemId);
    try {
      var resp = await apiFetch("/decisions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: state.analysis.analysis_id,
          item_id: itemId,
          item_type: itemType,
          verdict: verdict,
          comment: commentEl ? commentEl.value.trim() : "",
          reviewer: ($("reviewer").value.trim() || "reviewer-1"),
        }),
      });
      state.decisions.push({
        decision_id: resp.decision_id, recorded_at: resp.recorded_at,
        item_id: itemId, verdict: verdict, status: VERDICT_STATUS[verdict],
        reviewer: ($("reviewer").value.trim() || "reviewer-1"),
        comment: commentEl ? commentEl.value.trim() : "",
      });
      $("reviewError").textContent = "";
      renderAll();
    } catch (e) {
      $("reviewError").textContent = errorMessage(e.status || 502, e.message);
    }
  }

  function showInSource(itemId) {
    if (!state.analysis) return;
    var claim = (state.analysis.analysis.claims || []).find(function (c) { return c.claim_id === itemId; });
    var box = $("sourceView");
    if (!claim || !box) return;
    var doc = (state.documents || []).find(function (d) { return d.document_id === claim.document_id; });
    if (!doc) {
      box.innerHTML = '<p class="error">Source document ' + esc(claim.document_id) + " is not in this session.</p>";
      return;
    }
    var located = !!findQuoteRange(doc.text, claim.quote);
    box.innerHTML = "<h3>Source — document " + esc(doc.document_id) + (doc.title ? ": " + esc(doc.title) : "") + "</h3>"
      + '<p class="source-text">' + highlightQuoteHtml(doc.text, claim.quote) + "</p>"
      + '<p class="meta">' + (located
        ? "The highlighted span is the exact quote this proposal points to."
        : "The quote could not be located in this document — that is why acceptance is disabled.") + "</p>";
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function showProvenance(itemId) {
    var box = $("provenance");
    try {
      var chain = await apiFetch("/provenance/" + encodeURIComponent(itemId) +
        "?analysis_id=" + encodeURIComponent(state.analysis.analysis_id));
      box.innerHTML = "<h3>Provenance — " + esc(itemId) + "</h3>"
        + (chain.document ? '<p class="meta">Document ' + esc(chain.document.document_id) + ": " + esc(chain.document.title || "") + "</p>" : "")
        + (chain.quotes || []).map(function (q) {
          return '<blockquote class="quote">' + esc(formatQuote(q.quote)) + "</blockquote>";
        }).join("")
        + '<p class="meta">Model proposal · ' + esc((chain.model_proposal.model || {}).returned || "")
        + " · prompt " + esc(chain.model_proposal.prompt_hash || "") + " · " + esc(chain.model_proposal.created_at || "") + "</p>"
        + "<h4>Decision history</h4>" + renderDecisionHistory(chain.decisions);
    } catch (e) {
      box.innerHTML = '<p class="error">' + esc(errorMessage(e.status || 404, e.message)) + "</p>";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("analyzeBtn")) return;
    $("analyzeBtn").addEventListener("click", runAnalyze);
    var addDoc = $("addDocBtn");
    if (addDoc) {
      addDoc.addEventListener("click", function () {
        $("doc3Block").style.display = "block";
        addDoc.style.display = "none";
        $("doc3").focus();
      });
    }
    document.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      if (btn.dataset.action === "decide") decide(btn.dataset.item, btn.dataset.type, btn.dataset.verdict);
      if (btn.dataset.action === "provenance") showProvenance(btn.dataset.item);
      if (btn.dataset.action === "highlight") showInSource(btn.dataset.item);
    });
  });
})(typeof window !== "undefined" ? window : globalThis);
