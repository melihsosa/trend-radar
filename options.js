(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var msg = $("msg");

  chrome.storage.sync.get(["ghUser", "ghRepo", "dataUrl"], function (c) {
    $("ghUser").value = c.ghUser || "";
    $("ghRepo").value = c.ghRepo || "trend-radar";
    $("dataUrl").value = c.dataUrl || "";
  });

  $("form").addEventListener("submit", function (e) {
    e.preventDefault();
    var cfg = {
      ghUser: $("ghUser").value.trim().replace(/^@/, ""),
      ghRepo: $("ghRepo").value.trim(),
      dataUrl: $("dataUrl").value.trim()
    };
    chrome.storage.sync.set(cfg, function () {
      var url = cfg.dataUrl ||
        "https://raw.githubusercontent.com/" + cfg.ghUser + "/" + cfg.ghRepo + "/main/data/latest.json";
      msg.className = "";
      msg.textContent = "Kaydedildi, bağlantı deneniyor…";
      fetch(url + "?t=" + Date.now(), { cache: "no-store" })
        .then(function (r) {
          if (!r.ok) throw new Error(r.status === 404 ? "dosya bulunamadı (ilk tarama bitti mi, depo herkese açık mı?)" : "HTTP " + r.status);
          return r.json();
        })
        .then(function (d) {
          msg.className = "ok";
          msg.textContent = "Bağlantı tamam. " + (d.trends || []).length + " akım, " + (d.products || []).length + " ürün bulundu.";
          chrome.storage.local.set({ cache: d });
        })
        .catch(function (err) {
          msg.className = "bad";
          msg.textContent = "Kaydedildi ama veri okunamadı: " + err.message;
        });
    });
  });
})();
