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
      docs: ds.docs.map(function (d) { return { title: d.title, text: d.text }; }),
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
    });
    return values;
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
    var showThird = docs.length > 2;
    if ($("doc3Block")) $("doc3Block").style.display = showThird ? "block" : "none";
    if ($("addDocBtn")) $("addDocBtn").style.display = showThird ? "none" : "";
    if ($("datasetNote")) $("datasetNote").textContent = note || "";
    ["synthetic", "sumerian"].forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.classList.toggle("active", key === activeDataset);
    });
  }

  function applyDataset(id) {
    var ds = getDataset(id);
    if (!ds) return;
    fillDocuments(ds.docs, ds.note, id);
  }

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

  var MOCK_BASE = global.fenApiBase
    ? global.fenApiBase("fen_mock_base", "http://localhost:8100")
    : "http://localhost:8100";

  async function refreshRegistry() {
    var box = $("registry");
    if (!box) return;
    try {
      var resp = await fetch(MOCK_BASE + "/registry");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      box.innerHTML = renderRegistryHtml(data.records || [], MOCK_BASE);
    } catch (e) {
      box.innerHTML = '<p class="note">Registry unavailable — start the local backend to see accepted knowledge.</p>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["synthetic", "sumerian"].forEach(function (key) {
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
