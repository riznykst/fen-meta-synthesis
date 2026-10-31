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

  // Community consensus over recorded human decisions: each distinct
  // reviewer contributes their LATEST verdict on the item (repeat votes
  // update, never double-count). Consensus needs at least two distinct
  // reviewers and a strict majority for one verdict — a single reviewer
  // is a decision, not a consensus. This aggregates only recorded human
  // decisions; the model never appears here.
  function consensusFor(itemId, decisions) {
    var latestByReviewer = {};
    var order = [];
    (decisions || []).forEach(function (d) {
      if (d.item_id !== itemId) return;
      var reviewer = d.reviewer || "reviewer";
      var status = d.status || VERDICT_STATUS[d.verdict];
      if (!status) return;
      if (!(reviewer in latestByReviewer)) order.push(reviewer);
      latestByReviewer[reviewer] = status;
    });
    var reviewers = order.map(function (name) {
      return { reviewer: name, status: latestByReviewer[name] };
    });
    var counts = { accepted: 0, rejected: 0, disputed: 0 };
    reviewers.forEach(function (r) { if (r.status in counts) counts[r.status] += 1; });
    var total = reviewers.length;
    var verdict = null;
    ["accepted", "rejected", "disputed"].forEach(function (s) {
      if (total >= 2 && counts[s] * 2 > total) verdict = s;
    });
    var label;
    if (total === 0) label = "No reviewer votes yet";
    else if (verdict) label = "Community consensus: " + verdict + " (" + counts[verdict] + " of " + total + " reviewers)";
    else if (total === 1) label = "1 reviewer voted — awaiting more reviewers for consensus";
    else label = "No consensus yet — reviewers are split (" + total + " voted)";
    return { total: total, counts: counts, reviewers: reviewers, verdict: verdict, label: label };
  }

  function renderConsensusHtml(itemId, decisions) {
    var c = consensusFor(itemId, decisions);
    var chips = c.reviewers.map(function (r) {
      return '<span class="badge ' + (STATUS_BADGE[r.status] || "b-bl") + '">' + esc(r.reviewer) + ": " + esc(r.status) + "</span>";
    }).join(" ");
    var head = c.verdict
      ? '<span class="badge ' + (STATUS_BADGE[c.verdict] || "b-bl") + '">' + esc(c.label) + "</span>"
      : '<span class="badge b-gd">' + esc(c.label) + "</span>";
    return '<div class="consensus"><div class="lbl">Community consensus (distinct reviewers, latest vote each)</div>'
      + head + (chips ? ' <span class="reviewer-chips">' + chips + "</span>" : "") + "</div>";
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
      + renderConsensusHtml(claim.claim_id, decisions)
      + dictionaryBadgeHtml(claim)
      + (status === "accepted"
        ? '<div class="decision-row"><button class="decision-btn prov" data-action="export" data-item="' + esc(claim.claim_id) + '">Download record (JSON-LD)</button></div>'
        : "")
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
      + renderConsensusHtml(contra.contradiction_id, decisions)
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

  // Dictionary entries verified against ePSD2 for the Sumerian candidate
  // lemmas (eval/candidates/sumerian-video-candidates.json; CC BY-SA 3.0,
  // attribution in eval/dataset/SOURCES.md). Used only to badge a proposal
  // whose quote/statement actually names the lemma — display metadata,
  // never evidence and never a vote.
  var DICTIONARY_ENTRIES = [
    {
      id: "o0033207", headword: "lu [PERSON] (N)", gloss: "person; man",
      instances: 18895, citation: "http://oracc.org/epsd2/o0033207",
      tokens: ["lu₂", "lu2", "lu"],
    },
    {
      id: "o0024835", headword: "bahar [POTTER] (N)", gloss: "potter",
      instances: 613, citation: "http://oracc.org/epsd2/o0024835",
      tokens: ["baḫar", "bahar"],
    },
    {
      id: "o0034101", headword: "me [BEING] (N)", gloss: "Being, divine properties enabling cosmic activity",
      instances: 1174, citation: "http://oracc.org/epsd2/o0034101",
      tokens: ["me"], glossHints: ["being", "divine properties"],
    },
    {
      id: "o0034109", headword: "me [BE] (V)", gloss: "to be",
      instances: 3919, citation: "http://oracc.org/epsd2/o0034109",
      tokens: ["me"], glossHints: ["to be"],
    },
  ];

  function dictionaryEntryForClaim(claim) {
    if (!claim) return null;
    var haystack = (" " + String(claim.quote || "") + " " + String(claim.statement || "")
      + " " + String(claim.interpretation || "") + " ").toLowerCase();
    for (var i = 0; i < DICTIONARY_ENTRIES.length; i++) {
      var entry = DICTIONARY_ENTRIES[i];
      var tokenHit = entry.tokens.some(function (t) {
        var tok = t.toLowerCase();
        return haystack.includes(" " + tok + " ") || haystack.includes(" " + tok + ",")
          || haystack.includes(" " + tok + ".") || haystack.includes(" " + tok + ":");
      });
      if (!tokenHit) continue;
      if (entry.glossHints && !entry.glossHints.some(function (g) { return haystack.includes(g); })) {
        continue;
      }
      return entry;
    }
    return null;
  }

  function dictionaryBadgeHtml(claim) {
    var entry = dictionaryEntryForClaim(claim);
    if (!entry) return "";
    return '<p class="dict-badge">Dictionary (ePSD2): <a href="' + esc(entry.citation)
      + '" target="_blank" rel="noopener">' + esc(entry.headword) + "</a> · "
      + esc(entry.gloss) + " · " + entry.instances.toLocaleString("en-US")
      + ' attestations <span class="meta">(CC BY-SA 3.0)</span></p>';
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
    stepStates: stepStates,
    consensusFor: consensusFor,
    renderConsensusHtml: renderConsensusHtml,
    orderItems: orderItems,
    renderQuoteCheck: renderQuoteCheck,
    reviewerOptions: reviewerOptions,
    renderDecisionHistory: renderDecisionHistory,
    findQuoteRange: findQuoteRange,
    highlightQuoteHtml: highlightQuoteHtml,
    dictionaryEntryForClaim: dictionaryEntryForClaim,
    dictionaryBadgeHtml: dictionaryBadgeHtml,
    DICTIONARY_ENTRIES: DICTIONARY_ENTRIES,
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

  // Stepper (demo header): pure status derivation so it is unit-testable.
  // done / active / idle per step. Step 1 is done once documents exist;
  // steps 2–4 follow the shared analysis/decisions state.
  function stepStates(analysis, decisions, docCount) {
    var hasDocs = (docCount || 0) > 0;
    var hasAnalysis = !!analysis;
    var pc = (analysis && analysis.provenance_check) || {};
    var votes = (decisions || []).length;
    return {
      sources: hasDocs || hasAnalysis ? "done" : "active",
      proposals: hasAnalysis ? "done" : (hasDocs ? "active" : "idle"),
      quoteCheck: !hasAnalysis ? "idle" : ((pc.quotes_verified || 0) > 0 ? "done" : "active"),
      decision: votes > 0 ? "done" : (hasAnalysis ? "active" : "idle"),
    };
  }

  function docCount() {
    var n = 0;
    [1, 2, 3].forEach(function (i) {
      var f = $("doc" + i);
      if (f && f.value && f.value.trim()) n += 1;
    });
    if (!n && state.documents && state.documents.length) n = state.documents.length;
    return n;
  }

  function updateSteps() {
    var steps = document.querySelectorAll(".steps .step[data-target]");
    if (!steps.length) return;
    var st = stepStates(state.analysis, state.decisions, docCount());
    var map = { "panel-sources": st.sources, "panel-proposals": st.proposals, "panel-quotes": st.quoteCheck, "panel-decision": st.decision };
    steps.forEach(function (el) {
      var key = el.dataset.target;
      var value = map[key];
      if (value) el.dataset.state = value;
    });
  }

  function initStepper() {
    document.querySelectorAll(".steps .step[data-target]").forEach(function (el) {
      el.addEventListener("click", function () {
        var panel = document.getElementById(el.dataset.target);
        if (!panel) return;
        panel.classList.remove("collapsed");
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
        panel.classList.remove("flash");
        void panel.offsetWidth; // restart the highlight animation
        panel.classList.add("flash");
      });
    });
    ["doc1", "doc2", "doc3"].forEach(function (id) {
      var f = $(id);
      if (f) f.addEventListener("input", updateSteps);
    });
  }

  // Dynamic ordering: undecided proposals float up, decided items sink
  // to the bottom — after every vote the open work stays on top. Stable:
  // items keep their relative order within each group. Pure (testable).
  function orderItems(items, decisions, idOf) {
    var list = (items || []).slice();
    list.forEach(function (it, i) { it.__pos = i; });
    list.sort(function (a, b) {
      var da = itemStatus(idOf(a), decisions) !== "proposed" ? 1 : 0;
      var db = itemStatus(idOf(b), decisions) !== "proposed" ? 1 : 0;
      return (da - db) || (a.__pos - b.__pos);
    });
    list.forEach(function (it) { delete it.__pos; });
    return list;
  }

  // Quote-check panel (section 3): verification progress plus the items
  // still needing attention, each with a jump link to its card. Pure.
  function renderQuoteCheck(claims, contras, byId, decisions) {
    claims = claims || [];
    var total = claims.length;
    var verified = claims.filter(function (c) { return canAccept(c); }).length;
    var open = orderItems(claims, decisions, function (c) { return c.claim_id; })
      .filter(function (c) { return itemStatus(c.claim_id, decisions) === "proposed"; });
    var unverified = open.filter(function (c) { return !canAccept(c); });
    var html = '<p class="meta">Quotes verified <b>' + verified + "/" + total + "</b>"
      + " — checked by code against the source documents, not trusted from the model.</p>";
    if (!unverified.length) {
      html += '<p class="note">Nothing needs attention — every open proposal has a verified quote.</p>';
    } else {
      html += '<p class="meta">Needs attention (' + unverified.length + "):</p>"
        + unverified.map(function (c) {
          return '<div class="history-item">'
            + '<span class="badge b-rd">Quote NOT verified</span> '
            + "<b>" + esc(c.claim_id) + "</b> · " + esc(formatQuote(c.quote, 90))
            + ' <button class="decision-btn prov" data-action="jump" data-item="' + esc(c.claim_id) + '"'
            + ' type="button" style="flex:0 1 auto;min-height:32px;padding:4px 12px">Go to card →</button></div>';
        }).join("");
    }
    return html;
  }

  function jumpToCard(itemId) {
    var card = document.querySelector('article[data-item="' + itemId + '"]');
    if (!card) return;
    card.classList.remove("collapsed");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.remove("flash");
    void card.offsetWidth;
    card.classList.add("flash");
  }

  function renderAll() {
    var box = $("proposals");
    if (!state.analysis) { box.innerHTML = ""; var qc0 = $("quoteCheck"); if (qc0) qc0.innerHTML = ""; updateSteps(); return; }
    var claims = state.analysis.analysis.claims || [];
    var contras = state.analysis.analysis.contradictions || [];
    var byId = {};
    claims.forEach(function (c) { byId[c.claim_id] = c; });
    var orderedClaims = orderItems(claims, state.decisions, function (c) { return c.claim_id; });
    var orderedContras = orderItems(contras, state.decisions, function (x) { return x.contradiction_id; });
    box.innerHTML =
      orderedClaims.map(function (c) { return renderClaimCard(c, state.decisions); }).join("")
      + orderedContras.map(function (x) { return renderContradictionCard(x, byId, state.decisions); }).join("");
    var qc = $("quoteCheck");
    if (qc) qc.innerHTML = renderQuoteCheck(claims, orderedContras, byId, state.decisions);
    $("history").innerHTML = renderDecisionHistory(state.decisions);
    var pc = state.analysis.provenance_check || {};
    $("analysisMeta").textContent =
      "Analysis " + state.analysis.analysis_id + " · model " +
      ((state.analysis.model || {}).returned || (state.analysis.model || {}).requested || "") +
      " · quotes verified " + (pc.quotes_verified || 0) + "/" + (pc.claims_total || 0) +
      " · all items are proposals until you decide";
    updateSteps();
  }

  // Shared thread: analyses and decisions live on the server, so a second
  // participant opening this screen in another tab joins the SAME thread
  // (proposals + votes) instead of an empty screen. Loads the newest
  // analysis on page open; the Refresh button re-syncs votes.
  async function loadSharedThread() {
    var note = $("sharedThreadText");
    try {
      var list = await apiFetch("/analyses");
      var items = list.analyses || [];
      if (!items.length) {
        if (note) note.textContent = "Shared thread (" + MOCK + "): no analysis on the server yet — analyse documents to start one.";
        return false;
      }
      var latest = items[0];
      var body = await apiFetch("/analyses/" + encodeURIComponent(latest.analysis_id));
      var votes = await apiFetch("/decisions?analysis_id=" + encodeURIComponent(latest.analysis_id));
      state.analysis = body;
      state.documents = (body.documents || []).map(function (d) {
        return { document_id: d.document_id, title: d.title || null, text: d.text || "" };
      });
      state.decisions = votes.decisions || [];
      // Show the shared sources in the fields so the joining participant
      // sees exactly what was analysed (Show-in-source needs the texts).
      state.documents.forEach(function (d, i) {
        var n = i + 1;
        if ($("doc" + n)) $("doc" + n).value = d.text;
        if ($("doc" + n + "Title")) $("doc" + n + "Title").value = d.title || "";
        if (n === 3 && $("doc3Block")) { $("doc3Block").style.display = "block"; var a = $("addDocBtn"); if (a) a.style.display = "none"; }
      });
      syncReviewerChoices();
      renderAll();
      if (note) {
        note.textContent = "Shared thread (" + MOCK + "): joined analysis " + latest.analysis_id
          + " — " + state.decisions.length + " recorded vote(s). Other participants see the same thread; set your reviewer name and vote.";
      }
      return true;
    } catch (e) {
      if (note) note.textContent = "Shared thread (" + MOCK + "): could not load — " + (e.message || e) + ". If this is wrong, clear the saved API base or open with ?fen_mock_base=http://localhost:8100";
      return false;
    }
  }

  async function refreshVotesOnly() {
    if (!state.analysis) return;
    try {
      var votes = await apiFetch("/decisions?analysis_id=" + encodeURIComponent(state.analysis.analysis_id));
      var fresh = votes.decisions || [];
      if (fresh.length !== state.decisions.length) {
        state.decisions = fresh;
        renderAll();
      }
    } catch (e) { /* server blip: keep current view */ }
  }

  // Participant identities (demo-scope): a dropdown of every reviewer
  // who has voted, so a second participant picks a name instead of typing
  // one — no manual entry needed. The "+ New reviewer…" option reveals a
  // small field for a first-time name. Identity is a free-text name
  // recorded with each decision — a demo stand-in, not a verified account
  // (ADR-005 production identity is out of scope). Pure name-list builder
  // is unit-testable; DOM sync below uses it.
  var NEW_REVIEWER = "__new__";

  function reviewerOptions(decisions) {
    var names = [];
    (decisions || []).forEach(function (d) {
      if (d.reviewer && names.indexOf(d.reviewer) < 0) names.push(d.reviewer);
    });
    ["reviewer-1", "reviewer-2", "reviewer-3"].forEach(function (n) {
      if (names.indexOf(n) < 0) names.push(n);
    });
    return names;
  }

  function reviewerName() {
    var sel = $("reviewer");
    if (!sel) return "";
    if (sel.value === NEW_REVIEWER) {
      var field = $("reviewerNew");
      return field ? field.value.trim() : "";
    }
    return (sel.value || "").trim();
  }

  function syncReviewerChoices() {
    var sel = $("reviewer");
    if (!sel) return;
    var keep = sel.value && sel.value !== NEW_REVIEWER ? sel.value : reviewerName() || null;
    var html = reviewerOptions(state.decisions).map(function (n) {
      return '<option value="' + esc(n) + '"' + (n === keep ? " selected" : "") + ">" + esc(n) + "</option>";
    }).join("");
    html += '<option value="' + NEW_REVIEWER + '">＋ New reviewer…</option>';
    sel.innerHTML = html;
    if (!keep && sel.options.length) sel.selectedIndex = 0;
    toggleReviewerNew();
  }

  function toggleReviewerNew() {
    var sel = $("reviewer");
    var field = $("reviewerNew");
    if (!sel || !field) return;
    var isNew = sel.value === NEW_REVIEWER;
    field.classList.toggle("open", isNew);
    if (isNew) field.focus();
  }

  function initCollapsiblePanels() {
    document.querySelectorAll(".panel > h2").forEach(function (h) {
      h.title = "Collapse / expand this panel";
      h.addEventListener("click", function () { h.parentElement.classList.toggle("collapsed"); });
    });
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
    var reviewer = reviewerName();
    if (!reviewer) {
      $("reviewError").textContent = "Pick your reviewer name from the dropdown — or choose ＋ New reviewer… and type it — before voting.";
      var sel = $("reviewer");
      if (sel) sel.focus();
      return;
    }
    try {
      var resp = await apiFetch("/decisions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: state.analysis.analysis_id,
          item_id: itemId,
          item_type: itemType,
          verdict: verdict,
          comment: commentEl ? commentEl.value.trim() : "",
          reviewer: reviewer,
        }),
      });
      state.decisions.push({
        decision_id: resp.decision_id, recorded_at: resp.recorded_at,
        item_id: itemId, verdict: verdict, status: VERDICT_STATUS[verdict],
        reviewer: reviewer,
        comment: commentEl ? commentEl.value.trim() : "",
      });
      syncReviewerChoices();
      var sel = $("reviewer");
      if (sel) {
        sel.value = reviewer; // keep a just-registered name selected
        toggleReviewerNew();
      }
      var nf = $("reviewerNew");
      if (nf) nf.value = "";
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
        + (chain.status === "accepted"
          ? '<div class="decision-row"><button class="decision-btn prov" data-action="export" data-item="' + esc(itemId) + '">Download record (JSON-LD)</button></div>'
          : "")
        + "<h4>Decision history</h4>" + renderDecisionHistory(chain.decisions);
    } catch (e) {
      box.innerHTML = '<p class="error">' + esc(errorMessage(e.status || 404, e.message)) + "</p>";
    }
  }

  async function downloadRecord(itemId) {
    try {
      var resp = await fetch(MOCK + "/records/" + encodeURIComponent(itemId)
        + "?analysis_id=" + encodeURIComponent(state.analysis.analysis_id));
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var blob = await resp.blob();
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "record-" + itemId + ".jsonld";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      var box = $("reviewError");
      if (box) box.textContent = "Record download failed: " + e.message;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("analyzeBtn")) return;
    $("analyzeBtn").addEventListener("click", runAnalyze);
    initCollapsiblePanels();
    initStepper();
    updateSteps();
    syncReviewerChoices(); // voters dropdown works even before any vote
    var reviewerSel = $("reviewer");
    if (reviewerSel) reviewerSel.addEventListener("change", toggleReviewerNew);
    var refresh = $("refreshThread");
    if (refresh) refresh.addEventListener("click", function () { loadSharedThread(); });
    var reset = $("resetBase");
    if (reset) reset.addEventListener("click", function () {
      try { localStorage.removeItem("fen_mock_base"); } catch (e) { /* ignore */ }
      var u = new URL(window.location.href);
      u.searchParams.delete("fen_mock_base");
      window.location.href = u.toString();
    });
    // Join the shared thread (if any) so additional participants/tabs see
    // the same proposals and votes instead of an empty screen.
    loadSharedThread();
    // Keep votes in sync across tabs/participants (decisions only; the
    // document fields the user may be editing are never touched here).
    setInterval(refreshVotesOnly, 8000);
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
      if (btn.dataset.action === "jump") jumpToCard(btn.dataset.item);
      if (btn.dataset.action === "export") downloadRecord(btn.dataset.item);
    });
  });
})(typeof window !== "undefined" ? window : globalThis);
