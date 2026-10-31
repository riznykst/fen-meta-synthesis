/**
 * Candidate detail page (voter-facing) — zero-build.
 *
 * Pure render functions are exported for Node tests
 * (web/tests/candidate.test.js); browser wiring runs only with a DOM.
 * Data: mock FEN API GET /candidates (web/api.md) + Status API
 * GET /api/v1/status/{id} for the governance record, when available.
 * The page explains what a vote means BEFORE the voter casts it; the LLM
 * recommendation is decision-support only and is never shown as a vote.
 */
(function (global) {
  "use strict";

  var HTML_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(s) {
    var shared = global.fenEscapeHtml;
    if (typeof shared === "function") return shared(s);
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return HTML_MAP[c]; });
  }

  var OUTCOMES = ["validated", "disputed", "rejected"];
  var OUTCOME_MEANING = {
    validated: "Accept this entity into the knowledge graph as community-validated.",
    disputed: "Flag disagreement — this needs expert / community discussion before it can settle.",
    rejected: "Do not include this entity; the rejection stays in the record.",
  };

  function candidateIdFromSearch(search) {
    try {
      return new URLSearchParams(search || "").get("id") || "";
    } catch (e) {
      return "";
    }
  }

  function findCandidate(candidates, id) {
    return (candidates || []).find(function (c) { return c.annotation_id === id; }) || null;
  }

  function quorumText(candidate) {
    var q = candidate.quorum || {};
    if (q.required) {
      return (q.votes || 0) + " of " + q.required + " votes"
        + (q.reached ? " — quorum reached" : " — quorum not reached yet");
    }
    var qv = candidate.qv || {};
    if (qv.threshold) {
      var scores = qv.scores || {};
      var best = Math.max(0, scores.validated || 0, scores.disputed || 0, scores.rejected || 0);
      return "QV score " + best + " of " + qv.threshold + " threshold"
        + (qv.reached ? " — threshold reached" : " — still open");
    }
    return "no quorum information yet";
  }

  function voteButtons(candidate) {
    if (candidate.status !== "pending") {
      return '<p class="meta">Voting is closed for this candidate (status: '
        + esc(candidate.status) + ").</p>";
    }
    return '<div class="decision-row">' + OUTCOMES.map(function (o) {
      return '<button class="decision-btn ' + o + '" data-vote="' + esc(candidate.annotation_id)
        + '" data-outcome="' + o + '">' + o + "</button>";
    }).join("") + "</div>";
  }

  function renderGovernance(governance) {
    if (!governance) {
      return '<p class="meta">Governance record: not loaded.</p>';
    }
    if (governance.unavailable) {
      return '<p class="meta">Governance record: the registry read service is unavailable '
        + "right now — this does not affect voting; the decision will be recorded when the pipeline runs.</p>";
    }
    if (!governance.found) {
      return '<p class="meta">Governance record: no registry entry yet '
        + "(validation status: " + esc(governance.validation_status || "unknown")
        + "). A record appears after a decision is delivered.</p>";
    }
    var prov = (governance.provenance || []).map(function (p) {
      return "<li><code>" + esc(p.predicate) + "</code> — " + esc(p.value) + "</li>";
    }).join("");
    return '<p class="meta">Registry validation status: <b>' + esc(governance.validation_status) + "</b>"
      + (governance.governance_decision_id
        ? ' · decision <a href="' + esc(governance.governance_decision_id) + '">' + esc(governance.governance_decision_id) + "</a>"
        : "")
      + (governance.ledger_anchor ? " · ledger anchor " + esc(governance.ledger_anchor) : "")
      + "</p>" + (prov ? '<ul class="prov">' + prov + "</ul>" : "");
  }

  function renderCandidateDetail(candidate, governance) {
    if (!candidate) {
      return '<p class="error">Candidate not found in the current registry. '
        + "It may belong to an earlier session (the demo registry is in-memory) — "
        + 'return to the <a href="/web/portal/index.html">candidates list</a> and open a live item.</p>';
    }
    var votes = candidate.votes || {};
    var qvVotes = (candidate.qv && candidate.qv.votes) || [];
    var reviews = qvVotes.filter(function (v) { return v.comment; });
    var decision = candidate.decision;
    return '<article class="item">'
      + '<p class="meta">You are voting on this entity</p>'
      + '<h2 class="statement">' + esc(candidate.entity_label || "(no label)") + "</h2>"
      + '<table class="fields">'
      + "<tr><th>Annotation</th><td><code>" + esc(candidate.annotation_id) + "</code></td></tr>"
      + "<tr><th>Document</th><td>" + esc(candidate.document_id || "—") + "</td></tr>"
      + "<tr><th>Status</th><td>" + esc(candidate.status) + "</td></tr>"
      + "<tr><th>LLM recommendation</th><td>"
      + (candidate.llm_recommendation
        ? esc(candidate.llm_recommendation) + ' <span class="meta">(decision-support only — not a vote, never decides)</span>'
        : "—")
      + "</td></tr>"
      + "<tr><th>Votes so far</th><td>validated " + (Number(votes.validated) || 0)
      + " · disputed " + (Number(votes.disputed) || 0)
      + " · rejected " + (Number(votes.rejected) || 0) + "</td></tr>"
      + "<tr><th>Quorum</th><td>" + esc(quorumText(candidate)) + "</td></tr>"
      + "</table>"
      + (reviews.length
        ? '<h3>Peer assessments</h3>' + reviews.map(function (v) {
          return '<div class="review"><b>' + esc(v.voter) + "</b> · " + esc(v.outcome)
            + " · intensity " + esc(v.intensity) + "<div>" + esc(v.comment) + "</div></div>";
        }).join("")
        : '<p class="meta">No peer assessments with comments yet.</p>')
      + (decision
        ? '<h3>Recorded decision</h3><p class="meta">Outcome: <b>' + esc(decision.outcome) + "</b>"
          + " · decision " + esc(decision.decision_id)
          + " · " + esc(decision.decided_at || "")
          + (decision.ledger_anchor ? " · anchor " + esc(decision.ledger_anchor) + " (simulated in the demo)" : "")
          + "</p>"
        : '<p class="meta">No decision recorded yet.</p>')
      + "<h3>Governance record</h3>" + renderGovernance(governance)
      + "<h3>What your vote means</h3><ul class=\"meaning\">"
      + OUTCOMES.map(function (o) {
        return "<li><b>" + o + ":</b> " + esc(OUTCOME_MEANING[o]) + "</li>";
      }).join("")
      + "</ul>"
      + voteButtons(candidate)
      + '<p class="meta" id="voteNote"></p>'
      + "</article>";
  }

  var api = {
    esc: esc,
    candidateIdFromSearch: candidateIdFromSearch,
    findCandidate: findCandidate,
    quorumText: quorumText,
    renderGovernance: renderGovernance,
    renderCandidateDetail: renderCandidateDetail,
    OUTCOME_MEANING: OUTCOME_MEANING,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.FenCandidate = api;
  }

  // ---------------------------------------------------------- browser wiring
  if (typeof document === "undefined") return;

  var MOCK = global.fenApiBase ? global.fenApiBase("fen_mock_base", "http://localhost:8100") : "http://localhost:8100";
  var STATUS = global.fenApiBase ? global.fenApiBase("fen_status_base", "http://localhost:8082") : "http://localhost:8082";
  function $(id) { return document.getElementById(id); }

  async function loadDetail() {
    var id = candidateIdFromSearch(global.location.search);
    var box = $("detail");
    if (!id) {
      box.innerHTML = renderCandidateDetail(null, null);
      return;
    }
    var candidate = null;
    try {
      var resp = await fetch(MOCK + "/candidates");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      candidate = findCandidate(data.candidates, id);
    } catch (e) {
      box.innerHTML = '<p class="error">Cannot reach the candidates service at '
        + esc(MOCK) + " — start the local demo first (python scripts/start_demo.py).</p>";
      return;
    }
    var governance = null;
    try {
      var gResp = await fetch(STATUS + "/api/v1/status/" + encodeURIComponent(id));
      governance = gResp.ok ? await gResp.json() : { unavailable: true };
    } catch (e) {
      governance = { unavailable: true };
    }
    box.innerHTML = renderCandidateDetail(candidate, governance);
  }

  async function castVote(annotationId, outcome) {
    var note = $("voteNote");
    try {
      var resp = await fetch(MOCK + "/candidates/" + encodeURIComponent(annotationId) + "/vote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome: outcome }),
      });
      var body = {};
      try { body = await resp.json(); } catch (e) { /* non-JSON */ }
      if (resp.status === 409) {
        if (note) note.textContent = body.detail || "Vote rejected (409).";
        return;
      }
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      if (note) {
        note.textContent = body.outcome
          ? "Quorum reached → outcome: " + body.outcome + " (decision being delivered)"
          : "Vote recorded. Reloading details…";
      }
      loadDetail();
    } catch (e) {
      if (note) note.textContent = "Vote failed: " + e.message;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("detail")) return;
    loadDetail();
    document.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-vote]");
      if (btn) castVote(btn.dataset.vote, btn.dataset.outcome);
    });
  });
})(typeof window !== "undefined" ? window : globalThis);
