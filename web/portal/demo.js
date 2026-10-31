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

  var api = {
    DATASETS: DATASETS,
    datasetIds: datasetIds,
    getDataset: getDataset,
    datasetFieldValues: datasetFieldValues,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.FenDemo = api;
  }

  // ---------------------------------------------------------- browser wiring
  if (typeof document === "undefined") return;

  function $(id) { return document.getElementById(id); }

  function applyDataset(id) {
    var values = datasetFieldValues(id);
    var ds = getDataset(id);
    if (!values || !ds) return;
    [1, 2, 3].forEach(function (n) {
      if ($("doc" + n)) $("doc" + n).value = values["doc" + n];
      if ($("doc" + n + "Title")) $("doc" + n + "Title").value = values["doc" + n + "Title"];
    });
    if ($("doc3Block")) $("doc3Block").style.display = values.showDoc3 ? "block" : "none";
    if ($("addDocBtn")) $("addDocBtn").style.display = values.showDoc3 ? "none" : "";
    if ($("datasetNote")) $("datasetNote").textContent = ds.note;
    ["synthetic", "sumerian"].forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.classList.toggle("active", key === id);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["synthetic", "sumerian"].forEach(function (key) {
      var btn = $("dataset-" + key);
      if (btn) btn.addEventListener("click", function () { applyDataset(key); });
    });
  });
})(typeof window !== "undefined" ? window : globalThis);
