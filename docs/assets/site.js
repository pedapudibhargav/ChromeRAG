/* GitHub Pages–safe helpers: highlight current nav via pathname (no client router). */
(function () {
  function pathLeaf() {
    var path = window.location.pathname || "";
    var parts = path.split("/").filter(Boolean);
    var last = parts[parts.length - 1] || "index.html";
    if (!last.includes(".")) last = "index.html";
    return last;
  }
  var leaf = pathLeaf();
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = a.getAttribute("href") || "";
    var target = href.split("/").pop();
    if (target === leaf || (leaf === "index.html" && (target === "" || target === "./" || target === "index.html"))) {
      a.setAttribute("aria-current", "page");
    }
  });

  // Load leaderboard JSON with relative path (works on project pages).
  var mount = document.getElementById("leaderboard");
  var status = document.getElementById("leaderboard-status");
  if (!mount) return;
  fetch("./data/leaderboard.json")
    .then(function (r) {
      if (!r.ok) throw new Error("No leaderboard yet");
      return r.json();
    })
    .then(function (payload) {
      var summary = payload.summary || {};
      var rows = Object.keys(summary).map(function (k) {
        return { method: k, ...(summary[k] || {}) };
      });
      rows.sort(function (a, b) {
        return (b.avg_f_balanced || b.avg_fbal || 0) - (a.avg_f_balanced || a.avg_fbal || 0);
      });
      if (!rows.length) {
        if (status) status.textContent = "Leaderboard is empty — run the corpus comparison first.";
        return;
      }
      var html = "<table><thead><tr>" +
        "<th>Method</th><th>Pages</th><th>Recall ↑</th><th>Noise ret ↓</th><th>Fbal ↑</th><th>Tokens</th>" +
        "</tr></thead><tbody>";
      rows.forEach(function (r) {
        var n = r.pages_scored || r.n || "—";
        var recall = r.avg_content_recall != null ? r.avg_content_recall : r.avg_recall;
        var noise = r.avg_noise_retention != null ? r.avg_noise_retention : r.avg_noise_ret;
        var fbal = r.avg_f_balanced != null ? r.avg_f_balanced : r.avg_fbal;
        var tok = r.avg_tokens != null ? Math.round(r.avg_tokens) : "—";
        html += "<tr><td><code>" + r.method + "</code></td><td>" + n +
          "</td><td>" + (recall != null ? Number(recall).toFixed(3) : "—") +
          "</td><td>" + (noise != null ? Number(noise).toFixed(3) : "—") +
          "</td><td>" + (fbal != null ? Number(fbal).toFixed(3) : "—") +
          "</td><td>" + tok + "</td></tr>";
      });
      html += "</tbody></table>";
      mount.innerHTML = html;
      if (status) status.textContent = "Source: " + (payload.source || "leaderboard.json");
    })
    .catch(function () {
      if (status) {
        status.textContent =
          "Results not exported yet. After a comparison run: python -m poc.export_site_results";
      }
    });
})();
