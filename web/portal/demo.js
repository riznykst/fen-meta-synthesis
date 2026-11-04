/**
 * Simplified hackathon demo (one screen) — dataset switcher on top of the
 * Review workflow (review.js owns analysis/decisions/provenance wiring;
 * this file only fills the document fields per dataset).
 *
 * Datasets:
 * - synthetic: the neutral trade-route example, labelled synthetic.
 * - sumerian: short ePSD2 dictionary-entry excerpts for the verified
 *   candidate lemmas lu, bahar, me (eval/candidates/
 *   sumerian-video-candidates.json; ePSD2 data CC BY-SA 3.0, attribution
 *   in eval/dataset/SOURCES.md). These are dictionary excerpts, not corpus
 *   records and not gold data.
 *
 * Pure dataset functions are exported for Node tests.
 */
(function (global) {
  "use strict";

  var DATASETS = {
    synthetic: {
      label: "Demo (synthetic)",
      note: "Synthetic demo documents — invented neutral text, not corpus data. Replace with your own sources at any time.",
      docs: [
        {
          title: "Local oral tradition",
          text: "The hill Koshary marks the old trade route. In the local oral tradition, the hill Koshary is known as a landmark for traders. The river crossing at Sokolowizna was used by traders until 1903.",
        },
        {
          title: "Archive note",
          text: "A 1901 archive note states that the Sokolowizna crossing closed after the bridge was built downstream.",
        },
      ],
    },
    sumerian: {
      label: "Sumerian dictionary entries (ePSD2)",
      note: "Dictionary-entry excerpts from ePSD2 (CC BY-SA 3.0, Oracc) for the verified candidate lemmas. Excerpts, not corpus records and not gold data — attested source texts are selected and verified separately.",
      docs: [
        {
          title: "ePSD2 entry: lu [PERSON] (N)",
          text: "ePSD2 headword lu [PERSON], noun (18,895 instances). Senses: person (18,745 instances), man, who or which, ruler. Main writings: lu₂, lu, lu₂-lu₂, mu-lu. Akkadian equivalent: amēlu.",
        },
        {
          title: "ePSD2 entry: bahar [POTTER] (N)",
          text: "ePSD2 headword bahar [POTTER], noun (613 instances). Sense: potter in all 613 instances. Main writings: baḫar₂, baḫar₃, baḫar₄, baḫar. Akkadian equivalent: pahāru.",
        },
        {
          title: "ePSD2 entries: me [BEING] (N) and me [BE] (V)",
          text: "ePSD2 distinguishes two headwords written me. me [BEING], noun (1,174 instances): Being, divine properties enabling cosmic activity, rites; also cultic ordinance and prayer. me [BE], verb (3,919 instances): to be. The noun and the verb are separate dictionary entries and must not be merged.",
        },
      ],
    },
    // Public regulation texts (EUR-Lex) + one clearly synthetic commentary.
    // The texts below are copies of eval/dataset/eu-ai-act/sources/*.md — a
    // Node test keeps them in sync. Not legal advice.
    "eu-ai-act": {
      label: "EU AI Act — public texts (not legal advice)",
      note: "Public EU AI Act texts. Not legal advice. Articles 11 and 18 from EUR-Lex (Regulation (EU) 2024/1689); the third document is SYNTHETIC commentary written to illustrate a common attribution error.",
      docs: [
        {
          title: "Article 11 — Technical documentation (EUR-Lex)",
          provenance: "primary",
          text:
            "Article 11\n\nTechnical documentation\n\n" +
            "1.   The technical documentation of a high-risk AI system shall be drawn up before that system is placed on the market or put into service and shall be kept up-to date.\n\n" +
            "The technical documentation shall be drawn up in such a way as to demonstrate that the high-risk AI system complies with the requirements set out in this Section and to provide national competent authorities and notified bodies with the necessary information in a clear and comprehensive form to assess the compliance of the AI system with those requirements. It shall contain, at a minimum, the elements set out in Annex IV. SMEs, including start-ups, may provide the elements of the technical documentation specified in Annex IV in a simplified manner. To that end, the Commission shall establish a simplified technical documentation form targeted at the needs of small and microenterprises. Where an SME, including a start-up, opts to provide the information required in Annex IV in a simplified manner, it shall use the form referred to in this paragraph. Notified bodies shall accept the form for the purposes of the conformity assessment.\n\n" +
            "2.   Where a high-risk AI system related to a product covered by the Union harmonisation legislation listed in Section A of Annex I is placed on the market or put into service, a single set of technical documentation shall be drawn up containing all the information set out in paragraph 1, as well as the information required under those legal acts.\n\n" +
            "3.   The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend Annex IV, where necessary, to ensure that, in light of technical progress, the technical documentation provides all the information necessary to assess the compliance of the system with the requirements set out in this Section.",
        },
        {
          title: "Article 18 — Documentation keeping (EUR-Lex)",
          provenance: "primary",
          text:
            "Article 18\n\nDocumentation keeping\n\n" +
            "1.   The provider shall, for a period ending 10 years after the high-risk AI system has been placed on the market or put into service, keep at the disposal of the national competent authorities:\n\n" +
            "(a)\n\nthe technical documentation referred to in Article 11;\n\n" +
            "(b)\n\nthe documentation concerning the quality management system referred to in Article 17;\n\n" +
            "(c)\n\nthe documentation concerning the changes approved by notified bodies, where applicable;\n\n" +
            "(d)\n\nthe decisions and other documents issued by the notified bodies, where applicable;\n\n" +
            "(e)\n\nthe EU declaration of conformity referred to in Article 47.\n\n" +
            "2.   Each Member State shall determine conditions under which the documentation referred to in paragraph 1 remains at the disposal of the national competent authorities for the period indicated in that paragraph for the cases when a provider or its authorised representative established on its territory goes bankrupt or ceases its activity prior to the end of that period.\n\n" +
            "3.   Providers that are financial institutions subject to requirements regarding their internal governance, arrangements or processes under Union financial services law shall maintain the technical documentation as part of the documentation kept under the relevant Union financial services law.",
        },
        {
          title: "Industry commentary — SYNTHETIC",
          provenance: "synthetic",
          text:
            "SYNTHETIC. Written for the demo to illustrate a common attribution error. Not a real commentary, not legal advice.\n\n" +
            "A frequent misreading of the AI Act concerns how long documentation must be kept.\n\n" +
            "1. The Act requires a quality management system for high-risk systems.\n" +
            "2. Article 11 requires the technical documentation to be kept for 10 years after the system has been placed on the market.\n" +
            "3. Providers should therefore plan a ten-year archiving period from day one.",
        },
      ],
    },
  };

  function datasetIds() {
    return Object.keys(DATASETS);
  }

  function getDataset(id) {
    var ds = DATASETS[id];
    if (!ds) return null;
    return {
      label: ds.label,
      note: ds.note,
      docs: ds.docs.map(function (d) {
        return { title: d.title, text: d.text, provenance: d.provenance || "primary" };
      }),
    };
  }

  function datasetFieldValues(id) {
    var ds = getDataset(id);
    if (!ds) return null;
    var values = { showDoc3: ds.docs.length > 2 };
    [1, 2, 3].forEach(function (n) {
      var doc = ds.docs[n - 1];
      values["doc" + n + "Title"] = doc ? doc.title : "";
      values["doc" + n] = doc ? doc.text : "";
      values["doc" + n + "Provenance"] = (doc && doc.provenance) || "primary";
    });
    return values;
  }

  /** document_id -> provenance for the documents currently in the form. */
  function provenanceMapFromValues(values) {
    var map = {};
    [1, 2, 3].forEach(function (n) {
      map["d" + n] = (values && values["doc" + n + "Provenance"]) || "primary";
    });
    return map;
  }

  // ------------------------------------------------------------ upload ----
  // Files are read entirely in the browser and only placed into the
  // document fields; nothing is sent anywhere until the user clicks
  // Analyse (which posts the field texts to the model service as usual).
  var MAX_UPLOAD_DOCS = 3;
  var MAX_ANALYZE_CHARS = 30000; // same total limit as POST /analyze (T3)

  function parseUploadedFile(fileName, content) {
    var name = String(fileName || "document");
    var text = String(content == null ? "" : content);
    if (/\.json$/i.test(name)) {
      try {
        var parsed = JSON.parse(text);
        var list = Array.isArray(parsed) ? parsed : parsed.documents;
        if (Array.isArray(list) && list.length) {
          return list.map(function (d, i) {
            if (!d || typeof d.text !== "string" || !d.text.trim()) {
              throw new Error(name + ": document " + (i + 1) + " has no text");
            }
            return { title: String(d.title || d.document_id || name), text: d.text };
          });
        }
        if (parsed && typeof parsed.text === "string" && parsed.text.trim()) {
          return [{ title: String(parsed.title || name.replace(/\.json$/i, "")), text: parsed.text }];
        }
      } catch (e) {
        if (e instanceof SyntaxError) {
          // Not actually JSON content — fall through and treat as plain text.
        } else {
          throw e;
        }
      }
    }
    if (!text.trim()) throw new Error(name + ": file is empty");
    return [{ title: name.replace(/\.[^.]+$/, ""), text: text }];
  }

  function uploadSizeError(docs) {
    var total = (docs || []).reduce(function (sum, d) { return sum + (d.text || "").length; }, 0);
    if (total > MAX_ANALYZE_CHARS) {
      return "Documents total " + total + " characters — the analysis limit is "
        + MAX_ANALYZE_CHARS + ". Split the text or upload a shorter excerpt; nothing was truncated.";
    }
    return null;
  }

  // Registry showcase (pure): where accepted knowledge lands. Export links
  // point at GET /records/{item_id} on the mock API base passed in.
  function escHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var STATUS_BADGE_REG = { accepted: "b-gr", rejected: "b-rd", disputed: "b-gd", proposed: "b-bl" };

  function renderRegistryHtml(records, exportBase) {
    if (!records || !records.length) {
      return '<p class="note">Registry is empty — accepted proposals will appear here with their record.</p>';
    }
    return records.map(function (r) {
      var votes = Array.isArray(r.votes) ? r.votes : [];
      var voters = r.voter_count != null ? r.voter_count : (function (v) {
        var seen = {}; v.forEach(function (x) { if (x.reviewer) seen[x.reviewer] = true; }); return Object.keys(seen).length;
      })(votes);
      var voteRows = votes.map(function (v) {
        return '<li><span class="badge ' + (STATUS_BADGE_REG[v.status] || "b-bl") + '">' + escHtml(v.status || v.verdict) + "</span> "
          + "<b>" + escHtml(v.reviewer) + "</b>"
          + (v.comment ? " — " + escHtml(v.comment) : "")
          + '<span class="meta"> ' + escHtml(v.recorded_at || "") + "</span></li>";
      }).join("");
      return '<div class="registry-item"><span class="badge b-gr">Accepted knowledge</span> '
        + "<b>" + escHtml(r.statement || r.item_id) + "</b>"
        + '<div class="meta">decided by <b>' + voters + " reviewer" + (voters === 1 ? "" : "s") + "</b>"
        + " · " + escHtml(r.recorded_at)
        + " · document " + escHtml(r.document_id) + "</div>"
        + (r.quote ? '<blockquote class="quote">' + escHtml(r.quote) + "</blockquote>" : "")
        + (votes.length
          ? '<details class="vote-trail"><summary>Who voted (' + votes.length + " vote" + (votes.length === 1 ? "" : "s") + ")</summary><ul class=\"vote-list\">" + voteRows + "</ul></details>"
          : "")
        + '<a class="exp" href="' + escHtml((exportBase || "") + r.export_path)
        + '" download>Download record (JSON-LD)</a></div>';
    }).join("");
  }

  var api = {
    DATASETS: DATASETS,
    datasetIds: datasetIds,
    getDataset: getDataset,
    datasetFieldValues: datasetFieldValues,
    provenanceMapFromValues: provenanceMapFromValues,
    parseUploadedFile: parseUploadedFile,
    uploadSizeError: uploadSizeError,
    renderRegistryHtml: renderRegistryHtml,
    MAX_UPLOAD_DOCS: MAX_UPLOAD_DOCS,
    MAX_ANALYZE_CHARS: MAX_ANALYZE_CHARS,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.FenDemo = api;
  }

  // ---------------------------------------------------------- browser wiring
  if (typeof document === "undefined") return;

  function $(id) { return document.getElementById(id); }

  function fillDocuments(docs, note, activeDataset) {
    [1, 2, 3].forEach(function (n) {
      var doc = docs[n - 1];
      if ($("doc" + n)) $("doc" + n).value = doc ? doc.text : "";
      if ($("doc" + n + "Title")) $("doc" + n + "Title").value = doc ? doc.title : "";
    });
    // Provenance of each document (primary / secondary / synthetic) travels
    // with the analysis request so the reviewer sees it on every claim.
    var provenance = {};
    [1, 2, 3].forEach(function (n) {
      provenance["d" + n] = (docs[n - 1] && docs[n - 1].provenance) || "primary";
    });
    global.FEN_DOC_PROVENANCE = provenance;
    var showThird = docs.length > 2;
    if ($("doc3Block")) $("doc3Block").style.display = showThird ? "block" : "none";
    if ($("addDocBtn")) $("addDocBtn").style.display = showThird ? "none" : "";
    if ($("datasetNote")) $("datasetNote").textContent = note || "";
    ["synthetic", "sumerian", "eu-ai-act"].forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.classList.toggle("active", key === activeDataset);
    });
  }

  function applyDataset(id) {
    var ds = getDataset(id);
    if (!ds) return;
    fillDocuments(ds.docs, ds.note, id);
  }

  // Documents can also arrive from the shared thread (another participant's
  // analysis) rather than a preset. Then NO preset button may stay
  // highlighted — otherwise the screen claims "Demo (synthetic)" while
  // showing, say, ePSD2 entries.
  function clearDatasetSelection(note) {
    ["synthetic", "sumerian", "eu-ai-act"].forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.classList.remove("active");
    });
    if (note && $("datasetNote")) $("datasetNote").textContent = note;
  }
  // Expose for review.js, which fills the fields from the shared thread.
  if (global.FenDemo) global.FenDemo.clearDatasetSelection = clearDatasetSelection;

  async function handleUpload(fileList) {
    var note = $("uploadNote");
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;
    try {
      var docs = [];
      for (var i = 0; i < files.length; i++) {
        var content = await files[i].text();
        docs = docs.concat(parseUploadedFile(files[i].name, content));
      }
      if (docs.length > MAX_UPLOAD_DOCS) {
        throw new Error("At most " + MAX_UPLOAD_DOCS + " documents can be analysed at once — got "
          + docs.length + ". Upload fewer files.");
      }
      var sizeError = uploadSizeError(docs);
      if (sizeError) throw new Error(sizeError);
      fillDocuments(
        docs,
        "Uploaded from your device — the text is in the fields below and is sent to the model service only when you click Analyse.",
        null
      );
      if (note) {
        note.textContent = "Loaded " + docs.length + " document(s) from "
          + files.map(function (f) { return f.name; }).join(", ")
          + " (" + docs.reduce(function (s, d) { return s + d.text.length; }, 0) + " characters). Review, then click Analyse.";
      }
    } catch (e) {
      if (note) note.textContent = "Upload failed: " + e.message;
    }
  }

  var MOCK_FALLBACK = global.fenDefaultMockBase
    ? global.fenDefaultMockBase()
    : "http://localhost:8100";
  var MOCK_BASE = global.fenApiBase
    ? global.fenApiBase("fen_mock_base", MOCK_FALLBACK)
    : MOCK_FALLBACK;

  function apiUrl(path) {
    return global.fenApiUrl ? global.fenApiUrl(MOCK_BASE, path) : MOCK_BASE + path;
  }

  // The badge must describe the backend that is actually answering: the hosted
  // build talks to the Vercel function + Supabase, while a local run talks to
  // the FastAPI process on :8100. Saying "local backend" on the live site would
  // be wrong, and saying "hosted" locally would be worse.
  function describeBackend() {
    var badge = $("modelBadge");
    if (!badge) return;
    var hosted = String(MOCK_BASE).indexOf("/api/index") >= 0;
    badge.textContent = hosted
      ? "Meta Model API · muse-spark-1.3 · hosted on Vercel + Supabase"
      : "Meta Model API · muse-spark-1.3 · local backend";
    badge.title = hosted
      ? "Analyses run in a Vercel function and are stored in Supabase. Nothing runs on your machine."
      : "Analyses run in the local FastAPI process on :8100 (scripts/start_demo.py).";
  }
  describeBackend();

  async function refreshRegistry() {
    var box = $("registry");
    if (!box) return;
    try {
      var resp = await fetch(apiUrl("/registry"));
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      box.innerHTML = renderRegistryHtml(data.records || [], MOCK_BASE);
    } catch (e) {
      box.innerHTML = '<p class="note">Registry unavailable — the demo API did not answer. Retry with Refresh; to run everything locally use <code>python scripts/start_demo.py</code>.</p>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    datasetIds().forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.addEventListener("click", function () { applyDataset(key); });
    });
    refreshRegistry();
    // A recorded decision changes the registry; refresh shortly after any
    // vote click (the decision POST resolves well within this delay).
    document.addEventListener("click", function (ev) {
      if (ev.target.closest("[data-vote]") || ev.target.closest("[data-action='decide']")) {
        setTimeout(refreshRegistry, 900);
      }
    });
    var input = $("docUpload");
    if (input) {
      input.addEventListener("change", function () {
        handleUpload(input.files);
        input.value = ""; // allow re-uploading the same file
      });
    }
    var drop = $("uploadDrop");
    if (drop) {
      ["dragenter", "dragover"].forEach(function (ev) {
        drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("dragover"); });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("dragover"); });
      });
      drop.addEventListener("drop", function (e) {
        handleUpload(e.dataTransfer && e.dataTransfer.files);
      });
    }
  });
})(typeof window !== "undefined" ? window : globalThis);
